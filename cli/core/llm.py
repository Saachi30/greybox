"""
LLM access, split exactly the way the deployment doc requires:

- Intent parsing (mapping plain English to a tool call) is ALWAYS local,
  regardless of any config. It's small, latency-sensitive, and a network
  round-trip would be a bad trade even for someone who's opted into hosted
  inference for report writing.
- Report synthesis (turning collected findings into prose) can be either
  local (Ollama, default) or hosted (an OpenAI-compatible endpoint the user
  points this at and supplies their own key for). This is the one place
  where offloading makes sense, because by the time this runs, no scan
  traffic is involved - it's NLP over text the user already collected
  locally.

Nothing about the Kali container or scan execution lives in this file, on
purpose - that stays local unconditionally and isn't a config option.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import requests

logger = logging.getLogger("greybox")

OLLAMA_HOST = os.environ.get("GREYBOX_OLLAMA_HOST", "http://localhost:11434")
INTENT_MODEL = os.environ.get("GREYBOX_INTENT_MODEL", "llama3.2:3b")
REPORT_MODEL = os.environ.get("GREYBOX_REPORT_MODEL", "llama3.1:8b")


def _backend() -> str:
    """Read fresh each call (not cached at import time) so `greybox config`
    and tests can flip this without restarting a process."""
    value = os.environ.get("GREYBOX_LLM_BACKEND", "local").strip().lower()
    return value if value in ("local", "hosted") else "local"


def _hosted_config() -> tuple[str, str] | None:
    url = os.environ.get("GREYBOX_HOSTED_INFERENCE_URL", "").strip()
    key = os.environ.get("GREYBOX_HOSTED_INFERENCE_KEY", "").strip()
    if not url:
        return None
    return url, key


class OllamaError(RuntimeError):
    pass


class HostedInferenceError(RuntimeError):
    pass


def _post_ollama(path: str, payload: dict) -> dict:
    try:
        resp = requests.post(f"{OLLAMA_HOST}{path}", json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError as e:
        raise OllamaError(
            f"Could not reach Ollama at {OLLAMA_HOST}. Is it running? (`ollama serve`)"
        ) from e
    except requests.exceptions.HTTPError as e:
        model = payload.get("model", "?")
        raise OllamaError(
            f"Ollama rejected the request for model '{model}' ({e}). "
            f"Check it's actually pulled: `ollama list` (pull it with `ollama pull {model}` if not)."
        ) from e
    except requests.exceptions.Timeout as e:
        raise OllamaError(
            "Ollama didn't respond in time - this can happen on the very first call to a model "
            "while it's still loading into memory. Try again in a moment."
        ) from e
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"Request to Ollama failed: {e}") from e


def _warn(message: str) -> None:
    """Fail-loud helper: this setting affects where data goes, so a
    misconfiguration is surfaced, never silently swallowed. Uses logging
    rather than a raw print so the CLI can render it consistently with
    everything else (a styled panel) instead of a bare stderr line, while
    the backend just gets a normal log line.
    """
    logger.warning(message)


# --------------------------------------------------------------------------
# intent parsing - always local, never configurable to hosted
# --------------------------------------------------------------------------

def chat_with_tools(
    messages: list[dict[str, str]],
    tools: list[dict],
    model: str = INTENT_MODEL,
) -> dict[str, Any]:
    """Send a chat turn with tool-calling enabled, against the local Ollama
    instance only. Returns the raw message object, which may contain a
    `tool_calls` list.
    """
    result = _post_ollama(
        "/api/chat",
        {"model": model, "messages": messages, "tools": tools, "stream": False},
    )
    return result.get("message", {})


def is_available() -> bool:
    """Whether local Ollama (used for intent parsing, always) is reachable."""
    try:
        requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return True
    except requests.exceptions.RequestException:
        return False


# --------------------------------------------------------------------------
# report synthesis - local (default) or hosted (explicit opt-in)
# --------------------------------------------------------------------------

def generate_text(prompt: str, model: str = REPORT_MODEL, context: Optional[str] = None) -> str:
    """One-shot generation used for report section synthesis. Backend
    (local vs hosted) is controlled by GREYBOX_LLM_BACKEND - see
    report_backend_status() for what a caller can show the user about
    which one actually ran.
    """
    full_prompt = prompt if not context else f"{context}\n\n{prompt}"

    if _backend() == "hosted":
        hosted = _hosted_config()
        if hosted is None:
            _warn(
                "GREYBOX_LLM_BACKEND=hosted but GREYBOX_HOSTED_INFERENCE_URL is not set - "
                "falling back to local Ollama for this report. Set the URL (and key, if your "
                "endpoint needs one) in .env, or switch back to LLM_BACKEND=local."
            )
        else:
            try:
                return _generate_hosted(full_prompt, hosted)
            except HostedInferenceError as e:
                _warn(f"Hosted inference failed ({e}) - falling back to local Ollama for this report.")

    try:
        return _generate_local(full_prompt, model)
    except OllamaError as e:
        _warn(f"{e} Report will include raw findings without an AI-written summary.")
        return ""


def _generate_local(prompt: str, model: str) -> str:
    result = _post_ollama("/api/generate", {"model": model, "prompt": prompt, "stream": False})
    return result.get("response", "").strip()


def _generate_hosted(prompt: str, hosted: tuple[str, str]) -> str:
    """Calls an OpenAI-compatible /chat/completions endpoint. This is
    deliberately generic - it works against a Greybox-run endpoint, a
    self-hosted vLLM/Ollama-with-a-public-URL, or any provider that speaks
    the same wire format, as long as the user supplies the URL and key.
    """
    url, key = hosted
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        resp = requests.post(
            url.rstrip("/") + "/chat/completions",
            headers=headers,
            json={
                "model": os.environ.get("GREYBOX_HOSTED_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except (requests.exceptions.RequestException, KeyError, IndexError) as e:
        raise HostedInferenceError(str(e)) from e


def report_backend_status() -> dict[str, str]:
    """What actually ran, for transparency in the report footer and
    `greybox config` - per the deployment doc's 'no dark patterns' rule,
    the report itself should say plainly which backend wrote it.
    """
    backend = _backend()
    if backend == "hosted" and _hosted_config() is not None:
        url, _ = _hosted_config()
        return {"backend": "hosted", "detail": url}
    return {"backend": "local", "detail": OLLAMA_HOST}