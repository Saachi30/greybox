"""
Tool registry: the schema fed to the LLM for tool-calling, and the actual
execution logic (docker exec into the Kali container).

Design rule: the LLM only ever picks a name + arguments from this registry.
It never generates a raw shell string. This keeps command construction
predictable and auditable.
"""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass, field
from typing import Callable

KALI_CONTAINER = "greybox-kali"


@dataclass
class ToolArg:
    name: str
    description: str
    required: bool = True
    default: str | None = None
    llm_controlled: bool = True  # False = never exposed to the model's tool schema,
    # and stripped from its returned args even if it tries anyway. For things like
    # output_dir, where the model has no legitimate reason to pick a value and
    # doing so has produced real bugs (e.g. a model inventing "output_dir=.",
    # scattering results outside the expected scans directory and breaking the
    # httprobe/subdomain_enum auto-chaining that depends on predictable paths).


@dataclass
class Tool:
    name: str
    description: str
    args: list[ToolArg]
    kind: str = "kali"  # "kali" = docker exec into the Kali container, "api" = direct host-side call
    script: str | None = None  # required when kind == "kali": script name inside /root/scripts
    destructive: bool = False  # True = extra confirmation wording in the CLI

    def build_argv(self, values: dict[str, str]) -> list[str]:
        if self.kind != "kali":
            raise ValueError(f"build_argv only applies to kali-script tools, not '{self.kind}'")
        argv = [self.script]
        for a in self.args:
            v = values.get(a.name, a.default)
            if v is None and a.required:
                raise ValueError(f"missing required argument: {a.name}")
            if v is not None:
                argv.append(str(v))
        return argv

    def example(self) -> str:
        parts = [self.script or self.name] + [
            f"<{a.name}>" if a.required else f"[{a.name}]" for a in self.args
        ]
        return " ".join(parts)


REGISTRY: dict[str, Tool] = {
    "nmap": Tool(
        name="nmap",
        description="Port scan and service/version detection against a host or range.",
        script="nmap_scan.sh",
        args=[
            ToolArg("target", "IP, hostname, or CIDR range"),
            ToolArg("output_dir", "where to write results", required=False, default="/root/workdir/scans", llm_controlled=False),
            ToolArg("scan_type", "quick | full | vuln | comprehensive", required=False, default="quick"),
        ],
    ),
    "nikto": Tool(
        name="nikto",
        description="Web server vulnerability scan (misconfig, outdated software, known issues).",
        script="nikto_scan.sh",
        args=[
            ToolArg("target", "full URL, e.g. https://example.com"),
            ToolArg("output_dir", "where to write results", required=False, default="/root/workdir/scans", llm_controlled=False),
            ToolArg("tuning", "nikto tuning codes", required=False, default="4,6,8,b"),
        ],
    ),
    "sqlmap": Tool(
        name="sqlmap",
        description="Test a URL with parameters for SQL injection. Only use on a URL with a query string.",
        script="sqlmap_scan.sh",
        args=[
            ToolArg("target", "URL including query string, e.g. https://example.com/page?id=1"),
            ToolArg("output_dir", "where to write results", required=False, default="/root/workdir/scans", llm_controlled=False),
            ToolArg("level", "1-5 test depth", required=False, default="3"),
            ToolArg("risk", "1-3 query risk", required=False, default="2"),
        ],
        destructive=True,
    ),
    "subdomain_enum": Tool(
        name="subdomain_enum",
        description="Passive subdomain discovery for a domain (subfinder + theHarvester).",
        script="subdomain_enum.sh",
        args=[
            ToolArg("domain", "root domain, e.g. example.com"),
            ToolArg("output_dir", "where to write results", required=False, default="/root/workdir/scans", llm_controlled=False),
        ],
    ),
    "privesc_linux": Tool(
        name="privesc_linux",
        description="Enumerate local privilege escalation vectors on a Linux host (LinPEAS + manual checks). "
        "Only meaningful once you already have a foothold on the target.",
        script="privesc_linux.sh",
        args=[
            ToolArg("output_dir", "where to write results", required=False, default="/root/workdir/scans/privesc", llm_controlled=False),
            ToolArg("target_host", "label for the host being enumerated", required=False, default="localhost"),
        ],
        destructive=True,
    ),
    "privesc_windows": Tool(
        name="privesc_windows",
        description="Generate Windows privilege-escalation enumeration scripts (PowerShell + WinPEAS + Metasploit "
        "post modules) for manual transfer/execution against a host you already have access to.",
        script="privesc_windows.sh",
        args=[
            ToolArg("output_dir", "where to write results", required=False, default="/root/workdir/scans/privesc", llm_controlled=False),
            ToolArg("target_host", "hostname or IP"),
        ],
        destructive=True,
    ),
    "metasploit": Tool(
        name="metasploit",
        description="Metasploit auxiliary scans: port scan / SMB enum / SSH enum / web enum. "
        "Does not launch exploits - enumeration only.",
        script="metasploit_scan.sh",
        args=[
            ToolArg("action", "scan | smb | ssh | web"),
            ToolArg("target", "IP or hostname"),
            ToolArg("port", "specific port", required=False, default=""),
            ToolArg("output_dir", "where to write results", required=False, default="/root/workdir/scans", llm_controlled=False),
        ],
        destructive=True,
    ),
    "whatweb": Tool(
        name="whatweb",
        description="Identify website technologies: CMS, server software, JS frameworks, analytics, etc.",
        script="whatweb_scan.sh",
        args=[
            ToolArg("target", "full URL, e.g. https://example.com"),
            ToolArg("output_dir", "where to write results", required=False, default="/root/workdir/scans", llm_controlled=False),
            ToolArg("aggression", "1 (passive) - 4 (aggressive)", required=False, default="1"),
        ],
    ),
    "httprobe": Tool(
        name="httprobe",
        description="Check which hosts from a domain or a subdomain list actually respond over HTTP/HTTPS. "
        "Most useful right after subdomain_enum to filter out dead subdomains.",
        script="httprobe_scan.sh",
        args=[
            ToolArg("input", "a single domain, or the path to a subdomain list already on disk"),
            ToolArg("output_dir", "where to write results", required=False, default="/root/workdir/scans", llm_controlled=False),
        ],
    ),
    "hunter_email": Tool(
        name="hunter_email",
        description="Find email addresses associated with a domain via hunter.io. Requires HUNTER_API_KEY in .env.",
        kind="api",
        args=[ToolArg("domain", "root domain, e.g. example.com")],
    ),
    "crtsh": Tool(
        name="crtsh",
        description="Passive subdomain discovery via certificate transparency logs (crt.sh). No API key needed.",
        kind="api",
        args=[ToolArg("domain", "root domain, e.g. example.com")],
    ),
}


def tool_schema_for_llm() -> list[dict]:
    """OpenAI/Ollama-style function-calling schema built from the registry.
    Only args marked llm_controlled=True are exposed - output_dir and
    similar path-only args are never offered as something for the model
    to fill in (see ToolArg.llm_controlled for why)."""
    schema = []
    for tool in REGISTRY.values():
        controlled_args = [a for a in tool.args if a.llm_controlled]
        props = {
            a.name: {"type": "string", "description": a.description}
            for a in controlled_args
        }
        required = [a.name for a in controlled_args if a.required]
        schema.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    },
                },
            }
        )
    return schema


def run_in_kali(tool: Tool, values: dict[str, str], container: str = KALI_CONTAINER) -> subprocess.CompletedProcess:
    """Execute a kali-script tool inside the Kali container via `docker exec`.

    Callers are responsible for confirming with the user before calling this -
    this function performs no confirmation itself, by design, so it stays
    testable and side-effect-free to reason about.
    """
    argv = tool.build_argv(values)
    docker_cmd = ["docker", "exec", container] + argv
    return subprocess.run(docker_cmd, capture_output=True, text=True, timeout=60 * 45)


def run_in_kali_streaming(tool: Tool, values: dict[str, str], container: str = KALI_CONTAINER):
    """Same as run_in_kali, but yields output line-by-line as it arrives
    instead of blocking silently until the whole scan finishes. Some tools
    (nikto especially, also subdomain_enum/sqlmap) can take minutes with no
    output at all in the first phase - this is for showing real progress
    instead of the CLI looking hung.
    """
    argv = tool.build_argv(values)
    docker_cmd = ["docker", "exec", container] + argv
    process = subprocess.Popen(
        docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    try:
        for line in iter(process.stdout.readline, ""):
            yield line.rstrip("\n")
    finally:
        process.stdout.close()
        process.wait()


def preview_command(tool: Tool, values: dict[str, str], container: str = KALI_CONTAINER) -> str:
    """Human-readable command/action preview shown to the user before confirmation."""
    if tool.kind == "api":
        args_str = ", ".join(f"{k}={v}" for k, v in values.items())
        return f"[API call] {tool.name}({args_str})"
    argv = tool.build_argv(values)
    return "docker exec " + container + " " + " ".join(shlex.quote(a) for a in argv)


def filter_llm_args(tool: Tool, args: dict[str, str]) -> dict[str, str]:
    """Drops any argument the model returned that it wasn't offered in the
    schema (llm_controlled=False fields like output_dir). Belt-and-braces:
    tool_schema_for_llm() already excludes these, but a model that ignores
    schema constraints shouldn't get a second channel to slip one through.
    """
    allowed = {a.name for a in tool.args if a.llm_controlled}
    return {k: v for k, v in args.items() if k in allowed}


def run_tool(tool: Tool, values: dict[str, str], container: str = KALI_CONTAINER) -> str:
    """Unified entry point used by both the CLI and the backend: runs a tool
    regardless of whether it's a Kali-container script or a host-side API
    call, and always returns a plain-text output string.
    """
    if tool.kind == "api":
        from . import osint

        handler = osint.HANDLERS.get(tool.name)
        if handler is None:
            raise ValueError(f"no handler registered for api tool '{tool.name}'")
        return handler(values)

    result = run_in_kali(tool, values, container)
    return (result.stdout or "") + (("\n" + result.stderr) if result.stderr else "")


def run_tool_streaming(tool: Tool, values: dict[str, str], container: str = KALI_CONTAINER):
    """Streaming counterpart to run_tool, for interactive callers (the CLI)
    that want to show live progress. API-kind tools yield their single
    result at once, since those are fast HTTP calls with nothing to stream.
    """
    if tool.kind == "api":
        from . import osint

        handler = osint.HANDLERS.get(tool.name)
        if handler is None:
            raise ValueError(f"no handler registered for api tool '{tool.name}'")
        yield handler(values)
        return

    yield from run_in_kali_streaming(tool, values, container)