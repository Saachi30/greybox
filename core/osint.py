"""
OSINT lookups that make more sense as direct HTTP calls from the host
process (CLI or backend) than as something shelled out to inside the Kali
container - no API key management inside a container, no reason to route
a plain HTTPS GET through docker exec.

Each function takes the same `values: dict[str, str]` shape the tool
registry passes to Kali-script tools, and returns a plain-text summary
string, so both execution paths look the same to the caller.
"""
from __future__ import annotations

import os
import time

import requests

HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "")


def hunter_domain_search(values: dict[str, str]) -> str:
    """Find email addresses associated with a domain via hunter.io.
    Requires HUNTER_API_KEY in .env - this is a paid/rate-limited third
    party service, not bundled or proxied by greybox itself.
    """
    domain = values.get("domain", "")
    if not HUNTER_API_KEY:
        return (
            "No HUNTER_API_KEY set. Get a free-tier key at hunter.io, then run:\n"
            "  greybox set-key HUNTER_API_KEY <your-key>"
        )
    resp = requests.get(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 25},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    emails = data.get("emails", [])
    if not emails:
        return f"No email addresses found for {domain} via hunter.io."
    lines = [f"{len(emails)} email address(es) found for {domain}:"]
    for e in emails:
        lines.append(f"  - {e.get('value')} ({e.get('type', 'unknown')}, confidence {e.get('confidence')})")
    return "\n".join(lines)


# crt.sh returns 502/503 fairly often under load - these are transient,
# server-side, and worth retrying harder for than a normal HTTP error
# would justify. 5 attempts with longer backoff, specifically because this
# exact failure mode (502 on a real, otherwise-healthy domain) has shown
# up repeatedly in testing rather than being a one-off.
_TRANSIENT_STATUS_CODES = {502, 503, 504}


def crtsh_lookup(values: dict[str, str]) -> str:
    """Passive subdomain discovery via certificate transparency logs (crt.sh).
    No API key needed - this is a free public service, but it's known to be
    flaky/slow under load, so this retries several times before giving up
    rather than treating the first failure as final.
    """
    domain = values.get("domain", "")
    last_error = None

    for attempt in range(5):
        try:
            resp = requests.get(
                "https://crt.sh/", params={"q": f"%.{domain}", "output": "json"}, timeout=30
            )
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            time.sleep(2 * (attempt + 1))
            continue

        if resp.status_code == 200 and resp.text.strip():
            try:
                entries = resp.json()
            except ValueError:
                return f"crt.sh returned an unexpected (non-JSON) response for {domain}."
            names: set[str] = set()
            for entry in entries:
                for name in entry.get("name_value", "").split("\n"):
                    names.add(name.strip().lstrip("*."))
            names.discard("")
            if not names:
                return f"No certificate-transparency records found for {domain}."
            sorted_names = sorted(names)
            lines = [f"{len(sorted_names)} unique name(s) found via crt.sh for {domain}:"]
            lines.extend(f"  - {n}" for n in sorted_names[:100])
            if len(sorted_names) > 100:
                lines.append(f"  ... and {len(sorted_names) - 100} more")
            return "\n".join(lines)

        last_error = f"HTTP {resp.status_code}"
        # transient server errors get a longer wait before retrying - crt.sh
        # under load can take a bit to recover, a quick retry just hits the
        # same overloaded state again
        wait = 4 * (attempt + 1) if resp.status_code in _TRANSIENT_STATUS_CODES else 2 * (attempt + 1)
        time.sleep(wait)

    return (
        f"crt.sh didn't return usable results for {domain} after 5 attempts "
        f"(last issue: {last_error}). This is a known-flaky free public service - "
        f"try again in a bit, or check https://crt.sh/?q=%25.{domain} directly."
    )


# Maps a registry tool name (kind="api") to its handler function.
HANDLERS = {
    "hunter_email": hunter_domain_search,
    "crtsh": crtsh_lookup,
}