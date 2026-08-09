from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import typer
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

# `core` and `report` are bundled into this package's wheel (see
# cli/pyproject.toml) so a normal `pip install`/`pipx install` is
# self-contained. This fallback only matters if someone runs this file
# directly out of a repo clone without installing the package at all.
try:
    import core  # noqa: F401
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# .env search order: current directory (useful in dev), then the
# installed CLI's canonical config location, then a repo checkout if
# running unpackaged. Later calls don't override values already set by
# an earlier one - load_dotenv default keeps first-seen values.
load_dotenv(Path.cwd() / ".env")
load_dotenv(Path.home() / ".greybox" / ".env")
_repo_env = Path(__file__).resolve().parents[2] / ".env"
if _repo_env.exists():
    load_dotenv(_repo_env)

from core import llm, session_store, tools
from core.schema import Finding, Session, Severity

app = typer.Typer(
    name="greybox",
    help="Local, natural-language pentesting assistant. Nothing here auto-executes.",
    add_completion=False,
)
console = Console()


class _ConsoleLogHandler(logging.Handler):
    """Renders library-level warnings (e.g. an LLM backend falling back)
    through the same Console everything else uses, instead of a bare
    stderr print that breaks the Rich-styled flow."""

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        style = "red" if record.levelno >= logging.ERROR else "yellow"
        console.print(f"[{style}]\u26a0 {msg}[/{style}]")


_greybox_logger = logging.getLogger("greybox")
_greybox_logger.addHandler(_ConsoleLogHandler())
_greybox_logger.setLevel(logging.INFO)
_greybox_logger.propagate = False  # don't also let Python's default handler print this raw

CURRENT_SESSION_FILE = Path.home() / ".greybox" / "current_session"


# --------------------------------------------------------------------------
# session / scope handling
# --------------------------------------------------------------------------

def _get_current_session() -> Session | None:
    if not CURRENT_SESSION_FILE.exists():
        return None
    session_id = CURRENT_SESSION_FILE.read_text().strip()
    try:
        return session_store.load(session_id)
    except FileNotFoundError:
        return None


def _set_current_session(session: Session) -> None:
    CURRENT_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURRENT_SESSION_FILE.write_text(session.id)


@app.command()
def scope(target: str):
    """Declare the target/scope for this engagement. Required before scanning."""
    target = target.strip()
    if not target:
        console.print(
            "[red]Scope can't be empty.[/red] An empty scope would match every target, "
            "which defeats the whole point - give a real domain/host, e.g. `greybox scope example.com`."
        )
        raise typer.Exit(1)

    session = Session(scope=target)
    session_store.save(session)
    _set_current_session(session)
    console.print(
        Panel(
            f"Scope set to [bold]{target}[/bold]\nSession id: {session.id}\n\n"
            "Only this target (and its subdomains) will be allowed for the rest "
            "of this session. Start a new scope to change targets.",
            title="greybox",
            border_style="grey50",
        )
    )


@app.command()
def sessions():
    """List local sessions."""
    ids = session_store.list_sessions()
    if not ids:
        console.print("No sessions yet. Run `greybox scope <target>` to start one.")
        return
    for sid in ids:
        s = session_store.load(sid)
        console.print(f"{sid}  scope={s.scope}  findings={len(s.findings)}  updated={s.updated_at}")


# --------------------------------------------------------------------------
# natural language assistant
# --------------------------------------------------------------------------

_OUTPUT_PATH_RE = re.compile(r"Results saved to:\s*(\S+)")


def _extract_output_path(output: str) -> str | None:
    """Pulls the real output file path out of a tool's own "Results saved
    to: ..." line, when it printed a single concrete file (some scripts
    print a `.txt.*`-style pattern covering multiple extensions - that's
    not a real path, so it's skipped)."""
    match = _OUTPUT_PATH_RE.search(output)
    if not match:
        return None
    path = match.group(1)
    return None if path.endswith(".*") else path


def _find_latest_output(session: Session, tool_name: str) -> str | None:
    """Most recent output file this session has from a given tool, if any."""
    for f in reversed(session.findings):
        if f.tool == tool_name and f.raw_output_path:
            return f.raw_output_path
    return None


def _auto_chain_httprobe_input(args: dict[str, str], session: Session) -> dict[str, str]:
    """httprobe against a bare domain only checks that one host - almost
    never what someone means by "check which subdomains are alive" right
    after running subdomain_enum. If the resolved input isn't already a
    real file path, prefer the most recent subdomain_enum output from this
    session instead of silently under-delivering.
    """
    input_value = args.get("input", "")
    looks_like_a_file = input_value.endswith(".txt") or "/" in input_value
    if input_value and not looks_like_a_file:
        latest_file = _find_latest_output(session, "subdomain_enum")
        if latest_file:
            return {**args, "input": latest_file}
    return args


def _confirm_and_run(tool_name: str, args: dict[str, str], session: Session) -> None:
    if tool_name not in tools.REGISTRY:
        console.print(f"[red]Unknown tool suggested: {tool_name}[/red]")
        return
    tool = tools.REGISTRY[tool_name]

    if tool_name == "httprobe":
        original_input = args.get("input", "")
        args = _auto_chain_httprobe_input(args, session)
        if args.get("input") != original_input:
            console.print(
                f"[dim]No subdomain list given - using the most recent subdomain_enum "
                f"output from this session instead of just checking '{original_input}'.[/dim]"
            )

    # scope check on whatever looks like the target argument
    target_value = args.get("target") or args.get("domain") or args.get("target_host") or args.get("input") or ""
    if target_value and not session.in_scope(target_value):
        console.print(
            Panel(
                f"[bold red]Out of scope[/bold red]\n\n"
                f"'{target_value}' does not match the declared scope '{session.scope}'.\n"
                f"Run `greybox scope {target_value}` first if this is intentional.",
                border_style="red",
            )
        )
        return

    preview = tools.preview_command(tool, args)
    style = "red" if tool.destructive else "grey50"
    console.print(
        Panel(
            f"[bold]{tool.name}[/bold] — {tool.description}\n\n"
            f"[dim]{preview}[/dim]"
            + ("\n\n[bold red]This action is flagged destructive/intrusive.[/bold red]" if tool.destructive else ""),
            title="Proposed command",
            border_style=style,
        )
    )
    if not Confirm.ask("Run this command?", default=False):
        console.print("Skipped.")
        return

    eta_note = (
        " - this can take several minutes" if tool.name in ("nikto", "sqlmap", "subdomain_enum", "metasploit")
        else ""
    )
    console.print(f"[dim]Running{eta_note}... (Ctrl+C to stop watching, the scan keeps going in the container)[/dim]")

    output = _run_with_progress(tool, args)

    finding = Finding(
        tool=tool.name,
        command=preview,
        target=target_value or session.scope,
        summary=output,  # full output - see report/generate.py for where LLM-prompt-specific truncation happens
        raw_output_path=_extract_output_path(output),
        severity=Severity.INFO,
    )
    session.add_finding(finding)
    session_store.save(session)
    console.print(f"[dim]Logged as finding {finding.id} in session {session.id}[/dim]")


def _run_with_progress(tool, args: dict[str, str], heartbeat_secs: int = 12) -> str:
    """Streams a tool's output live instead of blocking silently until it
    finishes, and prints a heartbeat during quiet phases (nikto in
    particular can go 30+ seconds with no output at all right at the
    start) so it's clear the scan is still running, not hung.
    """
    q: "queue.Queue[tuple[str, str | None]]" = queue.Queue()

    def reader():
        try:
            for line in tools.run_tool_streaming(tool, args):
                q.put(("line", line))
        except Exception as e:  # noqa: BLE001 - surface any execution error as output rather than crashing the thread silently
            q.put(("line", f"[error running {tool.name}: {e}]"))
        q.put(("done", None))

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    lines: list[str] = []
    start = time.monotonic()
    last_activity = start
    try:
        while True:
            try:
                kind, payload = q.get(timeout=1)
            except queue.Empty:
                now = time.monotonic()
                if now - last_activity >= heartbeat_secs:
                    console.print(f"[dim]... still running ({int(now - start)}s elapsed)[/dim]")
                    last_activity = now
                continue
            if kind == "done":
                break
            lines.append(payload)
            console.print(payload)
            last_activity = time.monotonic()
    except KeyboardInterrupt:
        console.print(
            "\n[yellow]Stopped watching - the scan may still be running inside the container. "
            "Check `docker exec greybox-kali ps aux` if you want to confirm.[/yellow]"
        )

    return "\n".join(lines)


_CONVERSATIONAL_MARKERS = (
    "weird", "hello", "hi there", "hey", "thanks", "thank you", "lol", "haha",
    "wtf", "cool", "nice", "sup", "yo ", "sorry", "bye", "who are you",
    "what are you", "how are you", "are you", "you are", "u are", "ur weird",
)


def _looks_like_a_real_request(user_text: str) -> bool:
    """Cheap deterministic backstop, checked before the model ever sees a
    tool schema. Real incident: 'u are weird' triggered a full nmap scan
    against a live domain, because a small local model will often comply
    with tool-calling rather than decline even when explicitly instructed
    to - the system prompt telling it to decline is necessary but not
    sufficient on its own. This doesn't replace that instruction, it's a
    second, non-probabilistic layer underneath it.
    """
    text = user_text.lower().strip()
    word_count = len(text.split())
    if word_count <= 6 and any(marker in text for marker in _CONVERSATIONAL_MARKERS):
        return False
    return True


def _parse_intent(user_text: str, default_target: str = "") -> tuple[str, dict[str, str]] | None:
    """Ask the local LLM to map plain English to a registered tool call."""
    if not _looks_like_a_real_request(user_text):
        console.print(
            "[yellow]That doesn't look like a scan/recon request - try being specific about "
            "what you want checked, e.g. \"check open ports\" or \"find subdomains\".[/yellow]"
        )
        return None

    if not llm.is_available():
        console.print(
            "[yellow]Ollama isn't reachable - falling back to keyword matching. "
            "Start it with `ollama serve` for better intent parsing.[/yellow]"
        )
        return _keyword_fallback(user_text, default_target)

    messages = [
        {
            "role": "system",
            "content": "You map a pentester's plain-English request to AT MOST one tool call "
            "from the provided tool list. Never invent tools or arguments not in the schema. "
            "If the request is unclear, conversational, unrelated to security testing, or "
            "doesn't clearly and confidently match one of the available tools, do NOT call a "
            "tool - respond with plain text saying you didn't find a matching action, and ask "
            "the person to rephrase or be more specific. Only call a tool when you are genuinely "
            f"confident it's what they're asking for. If a target isn't named, use '{default_target}'.",
        },
        {"role": "user", "content": user_text},
    ]
    message = llm.chat_with_tools(messages, tools.tool_schema_for_llm())
    calls = message.get("tool_calls") or []
    if not calls:
        console.print(f"[dim]Model response:[/dim] {message.get('content', '(no tool call suggested)')}")
        return None
    call = calls[0]["function"]
    name = call["name"]
    args = call.get("arguments", {})
    if isinstance(args, str):
        args = json.loads(args)
    if name in tools.REGISTRY:
        args = tools.filter_llm_args(tools.REGISTRY[name], args)
    return name, args


def _keyword_fallback(user_text: str, default_target: str = "") -> tuple[str, dict[str, str]] | None:
    text = user_text.lower()
    words = user_text.split()
    target = next((w for w in words if "." in w or "/" in w), "") or default_target
    if "email" in text or "hunter" in text:
        return "hunter_email", {"domain": target}
    if "crt.sh" in text or "certificate" in text:
        return "crtsh", {"domain": target}
    if "technolog" in text or "whatweb" in text or "tech stack" in text or "what's running" in text:
        return "whatweb", {"target": target}
    if "alive" in text or "httprobe" in text or ("which" in text and "up" in text):
        return "httprobe", {"input": target}
    if "subdomain" in text:
        return "subdomain_enum", {"domain": target}
    if "sql" in text or "injection" in text:
        return "sqlmap", {"target": target}
    if "nikto" in text or "web vuln" in text or "web server" in text:
        return "nikto", {"target": target}
    if "metasploit" in text or "msf" in text:
        action = "smb" if "smb" in text else "ssh" if "ssh" in text else "web" if "web" in text else "scan"
        return "metasploit", {"action": action, "target": target}
    if "port" in text or "nmap" in text or "scan" in text:
        return "nmap", {"target": target, "scan_type": "quick"}
    console.print("[yellow]Couldn't match a tool from that phrasing - try being more specific.[/yellow]")
    return None


@app.command()
def ask(request: str):
    """Ask in plain English what you want to check, e.g. `greybox ask "scan example.com for open ports"`."""
    session = _get_current_session()
    if session is None:
        console.print("[red]No scope declared yet.[/red] Run `greybox scope <target>` first.")
        raise typer.Exit(1)

    parsed = _parse_intent(request, default_target=session.scope)
    if parsed is None:
        return
    tool_name, args = parsed
    _confirm_and_run(tool_name, args, session)


@app.command()
def chat():
    """Interactive loop: keep asking in plain English until you exit."""
    session = _get_current_session()
    if session is None:
        console.print("[red]No scope declared yet.[/red] Run `greybox scope <target>` first.")
        raise typer.Exit(1)

    console.print(
        Panel(
            f"Scope: [bold]{session.scope}[/bold]\nType what you want to check, or 'exit' to quit.",
            border_style="grey50",
        )
    )
    while True:
        try:
            text = Prompt.ask("[bold]greybox[/bold]")
        except (EOFError, KeyboardInterrupt):
            break
        if text.strip().lower() in {"exit", "quit"}:
            break
        parsed = _parse_intent(text, default_target=session.scope)
        if parsed:
            _confirm_and_run(parsed[0], parsed[1], session)


# --------------------------------------------------------------------------
# config / setup - staged install support (deployment doc, Sections 3 & 7)
# --------------------------------------------------------------------------

ENGINE_DIR = Path.home() / ".greybox" / "engine"
DEFAULT_REPO_URL = "https://github.com/Saachi30/greybox.git"  # fill in once published


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _kali_container_running() -> bool:
    if not _docker_available():
        return False
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", tools.KALI_CONTAINER],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


@app.command()
def config():
    """Show what's configured and what's reachable right now - the
    'why isn't this working' command."""
    ollama_ok = llm.is_available()
    backend_status = llm.report_backend_status()
    docker_ok = _docker_available()
    kali_ok = _kali_container_running()
    hunter_set = bool(os.environ.get("HUNTER_API_KEY"))

    def mark(ok: bool) -> str:
        return "[green]yes[/green]" if ok else "[red]no[/red]"

    console.print(Panel(
        f"Intent parsing (always local): Ollama reachable at {llm.OLLAMA_HOST} -> {mark(ollama_ok)}\n"
        f"Report synthesis backend: [bold]{backend_status['backend']}[/bold] ({backend_status['detail']})\n"
        f"Docker available: {mark(docker_ok)}\n"
        f"Kali container ('{tools.KALI_CONTAINER}') running: {mark(kali_ok)}\n"
        f"HUNTER_API_KEY set: {mark(hunter_set)}\n"
        f"Telemetry opt-in: {os.environ.get('GREYBOX_TELEMETRY_OPT_IN', 'false')}\n\n"
        f"Config loaded from (first match wins): ./.env, ~/.greybox/.env, repo .env if present.",
        title="greybox config",
        border_style="grey50",
    ))
    if not docker_ok or not kali_ok:
        console.print(
            "[dim]Recon/lookup tools that need only Python (hunter_email, crtsh) work without "
            "Docker. Everything that needs the Kali container needs `greybox setup`.[/dim]"
        )
    if not hunter_set:
        console.print(
            "[dim]No HUNTER_API_KEY set - get a free-tier key at hunter.io, then run "
            "`greybox set-key HUNTER_API_KEY <your-key>`.[/dim]"
        )


@app.command("set-key")
def set_key(name: str, value: str):
    """Save a config value (e.g. HUNTER_API_KEY) to ~/.greybox/.env.
    Example: greybox set-key HUNTER_API_KEY abc123
    """
    env_path = Path.home() / ".greybox" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    key_upper = name.upper().strip()

    lines = env_path.read_text().splitlines() if env_path.exists() else []
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key_upper}="):
            new_lines.append(f"{key_upper}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key_upper}={value}")

    env_path.write_text("\n".join(new_lines) + "\n")
    console.print(f"[green]Saved {key_upper} to {env_path}[/green]")
    console.print("[dim]Takes effect on your next `greybox` command.[/dim]")


def _ensure_compose_env(engine_dir: Path) -> None:
    """docker-compose.yml needs a real .env file sitting next to it - both
    for its own ${HOME} substitution (the volumes: mount) and for the
    backend service's env_file: directive. Neither installer ever created
    this (they only write ~/.greybox/.env, a different file the CLI reads
    directly) - on Linux/Mac this went unnoticed because $HOME happens to
    already be in the shell environment Compose falls back to, but HOME
    isn't a standard Windows environment variable at all, so ${HOME} would
    silently resolve to empty there and break the volume mount entirely.
    Writing HOME explicitly here makes this deterministic on every
    platform instead of depending on shell-environment ambiguity.
    """
    compose_env = engine_dir / ".env"
    lines: list[str] = []

    # Carry over whatever the user already configured via `greybox set-key`
    # or by hand, so the backend container actually sees the same settings
    # the CLI itself uses - this was silently not happening before.
    user_env = Path.home() / ".greybox" / ".env"
    if user_env.exists():
        lines = [
            line for line in user_env.read_text().splitlines()
            if line.strip() and not line.strip().startswith("HOME=")
        ]

    lines.append(f"HOME={Path.home()}")
    compose_env.write_text("\n".join(lines) + "\n")


@app.command()
def setup():
    """Set up the full scanning engine (Kali container + Docker Compose).
    Safe to run later - the CLI itself already works without this."""
    if not _docker_available():
        console.print(
            "[red]Docker isn't installed.[/red] Install it from "
            "https://docs.docker.com/engine/install/ and re-run `greybox setup`."
        )
        raise typer.Exit(1)

    # If we're being run from inside an existing checkout (e.g. install.sh
    # calls this without changing directory), use that directly instead of
    # cloning a second copy.
    cwd_compose = Path.cwd() / "docker-compose.yml"
    if cwd_compose.exists():
        engine_dir = Path.cwd()
    elif (ENGINE_DIR / "docker-compose.yml").exists():
        engine_dir = ENGINE_DIR
    else:
        console.print(f"[*] Full engine not found locally - fetching it into {ENGINE_DIR}")
        repo_url = os.environ.get("GREYBOX_REPO_URL", DEFAULT_REPO_URL)
        if not Confirm.ask(f"Clone {repo_url} into {ENGINE_DIR}?", default=True):
            console.print("Skipped. Set GREYBOX_REPO_URL in .env if you want a different source.")
            raise typer.Exit(0)
        ENGINE_DIR.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(["git", "clone", repo_url, str(ENGINE_DIR)])
        if result.returncode != 0:
            console.print("[red]Clone failed.[/red] Check the URL/network and try again.")
            raise typer.Exit(1)
        engine_dir = ENGINE_DIR

    _ensure_compose_env(engine_dir)

    console.print(f"[*] Building the Kali + backend containers from {engine_dir} (this can take a few minutes)...")
    build = subprocess.run(["docker", "compose", "build"], cwd=engine_dir)
    if build.returncode != 0:
        console.print("[red]Build failed.[/red] See output above.")
        raise typer.Exit(1)

    subprocess.run(["docker", "compose", "up", "-d"], cwd=engine_dir)
    console.print("[green]Kali + backend containers are up.[/green]")

    if shutil.which("ollama") is None:
        console.print(
            "[yellow]Ollama isn't installed.[/yellow] Get it from https://ollama.com, then run:\n"
            "  ollama pull llama3.2:3b\n  ollama pull llama3.1:8b"
        )
    elif Confirm.ask(
        "Pull the local models now? llama3.2:3b (~2GB) for intent parsing + "
        "llama3.1:8b (~4.7GB) for report writing - about 6.7GB total.",
        default=True,
    ):
        subprocess.run(["ollama", "pull", "llama3.2:3b"])
        subprocess.run(["ollama", "pull", "llama3.1:8b"])

    console.print("[green]Setup complete.[/green] Try: greybox scope example.com")


report_app = typer.Typer(help="Generate reports from a session.")
app.add_typer(report_app, name="report")


def _generate_report(session_id: str, output: str | None = None) -> None:
    """Shared by `report generate` and `scan` - prefers the backend
    container (already has WeasyPrint's native libs), falls back to local
    generation with a friendly error only if the backend isn't reachable.
    """
    from report.generate import build_report  # local import keeps CLI fast to start

    try:
        session = session_store.load(session_id)
    except FileNotFoundError:
        console.print(
            f"[red]No session found with id '{session_id}'.[/red] "
            f"Run `greybox sessions` to see what's actually available."
        )
        raise typer.Exit(1)

    backend_url = "http://localhost:8000"
    try:
        health = requests.get(f"{backend_url}/health", timeout=2)
        backend_up = health.status_code == 200
    except requests.exceptions.RequestException:
        backend_up = False

    if backend_up:
        try:
            resp = requests.post(f"{backend_url}/api/sessions/{session_id}/report", timeout=180)
            resp.raise_for_status()
            container_path = resp.json()["report_path"]
            # The backend container mounts ~/.greybox at /root/.greybox (see
            # docker-compose.yml), so this translates straight back to a
            # real path on your machine.
            host_path = container_path.replace("/root/.greybox", str(Path.home() / ".greybox"))
            console.print(f"[green]Report written to {host_path}[/green]")
            return
        except requests.exceptions.RequestException as e:
            console.print(f"[yellow]Backend was reachable but the report request failed ({e}). "
                           f"Falling back to local generation.[/yellow]")

    try:
        out_path = build_report(session, output_path=output)
        console.print(f"[green]Report written to {out_path}[/green]")
    except RuntimeError as e:
        console.print(Panel(str(e), title="Report generation needs one more thing", border_style="yellow"))
        raise typer.Exit(1)


@report_app.command("generate")
def report_generate(session_id: str, output: str = typer.Option(None, "--output", "-o")):
    """Generate a PDF report from a session's logged findings.

    Prefers the backend container if it's running, since it already has
    WeasyPrint's native rendering libraries baked into its image - no setup
    needed on your host for that path. Falls back to generating locally
    only if the backend isn't reachable.
    """
    _generate_report(session_id, output)


# --------------------------------------------------------------------------
# scan - the flagship command: one call, full non-destructive recon sweep,
# report generated automatically at the end. Destructive-tier tools
# (sqlmap, metasploit, privesc_*) are deliberately excluded - those need
# explicit, specific targeting, not a default batch run.
# --------------------------------------------------------------------------

FULL_SCAN_SEQUENCE = [
    ("crtsh", lambda target: {"domain": target}),
    ("subdomain_enum", lambda target: {"domain": target}),
    ("httprobe", lambda target: {"input": target}),  # auto-chains to subdomain_enum output
    ("whatweb", lambda target: {"target": f"https://{target}"}),
    ("nmap", lambda target: {"target": target, "scan_type": "quick"}),
    ("nikto", lambda target: {"target": f"https://{target}"}),
]


@app.command()
def scan(target: str):
    """Run a full non-destructive recon sweep against a target - certificate
    transparency, subdomains, live-host check, tech fingerprinting, port
    scan, web vulnerability scan - and generate the report automatically at
    the end. The fastest path from a domain to a complete first-pass
    assessment. Does not include sqlmap/metasploit/privesc - those need
    explicit, deliberate targeting, not a default batch run.
    """
    target = target.strip()
    if not target:
        console.print("[red]Give a target, e.g. `greybox scan example.com`.[/red]")
        raise typer.Exit(1)

    session = _get_current_session()
    if session is None or not session.in_scope(target):
        session = Session(scope=target)
        session_store.save(session)
        _set_current_session(session)
        console.print(f"[dim]Scope set to {target} for this scan.[/dim]")

    steps = "\n".join(f"  {i+1}. {name}" for i, (name, _) in enumerate(FULL_SCAN_SEQUENCE))
    console.print(Panel(
        f"This runs, in order, all non-destructive:\n{steps}\n\n"
        "Then generates a full PDF report automatically.\n\n"
        "[dim]sqlmap, metasploit, and privilege-escalation tools are NOT included - "
        "those need explicit, deliberate targeting on their own.[/dim]",
        title="Full scan",
        border_style="grey50",
    ))
    if not Confirm.ask(f"Run the full non-destructive scan against {target}?", default=True):
        console.print("Cancelled.")
        return

    for tool_name, arg_builder in FULL_SCAN_SEQUENCE:
        tool = tools.REGISTRY[tool_name]
        args = arg_builder(target)
        if tool_name == "httprobe":
            original_input = args.get("input", "")
            args = _auto_chain_httprobe_input(args, session)
            if args.get("input") != original_input:
                console.print(f"[dim]Using the subdomain_enum output from this run instead of just '{original_input}'.[/dim]")

        console.print(f"\n[bold]== {tool_name} ==[/bold]  {tool.description}")
        output = _run_with_progress(tool, args)

        finding = Finding(
            tool=tool.name,
            command=tools.preview_command(tool, args),
            target=target,
            summary=output,  # full output - see report/generate.py for where LLM-prompt-specific truncation happens
            raw_output_path=_extract_output_path(output),
            severity=Severity.INFO,
        )
        session.add_finding(finding)
        session_store.save(session)

    console.print(f"\n[bold]All {len(FULL_SCAN_SEQUENCE)} checks complete. Generating report...[/bold]")
    _generate_report(session.id)


def main():
    from core.telemetry import send_ping

    send_ping("heartbeat")  # no-op unless the user has opted in - see core/telemetry.py
    app()


if __name__ == "__main__":
    main()