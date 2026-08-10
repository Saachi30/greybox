"""
Report generation: takes a Session (declared scope + logged findings) and
produces a PDF. The only thing that changed from the old NEXUS version is
the model backend - Gemini calls are replaced with local Ollama calls via
core.llm. Everything else (structure, CVSS-style severity, WeasyPrint
rendering) works the same way.
"""
from __future__ import annotations

import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core import llm
from core.schema import Session
from core.tools import REGISTRY as TOOL_REGISTRY

TEMPLATE_DIR = Path(__file__).parent
DEFAULT_OUTPUT_DIR = Path.home() / ".greybox" / "reports"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    """Removes terminal color/formatting escape codes. Scan tools
    (whatweb in particular) can emit these even when told not to, and
    older sessions logged before that fix will still have them saved -
    stripping defensively here means the report is clean either way.
    """
    return _ANSI_RE.sub("", text or "")


_MARKDOWN_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MARKDOWN_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)")
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_MARKDOWN_BULLET_RE = re.compile(r"^[ \t]*[-*]\s+", re.MULTILINE)


def _strip_markdown_noise(text: str) -> str:
    """The LLM prompts explicitly ask for plain text with no markdown, but
    local models don't reliably follow that - this cleans up the common
    artifacts (**bold**, *italic*, # headings, - bullets) rather than
    trusting the instruction alone, so raw ** characters don't show up in
    the finished report.
    """
    if not text:
        return text
    text = _MARKDOWN_BOLD_RE.sub(r"\1", text)
    text = _MARKDOWN_ITALIC_RE.sub(r"\1", text)
    text = _MARKDOWN_HEADING_RE.sub("", text)
    text = _MARKDOWN_BULLET_RE.sub("", text)
    return text

NATIVE_DEPS_HELP = """
WeasyPrint (PDF rendering) needs native Pango/Cairo libraries installed on
this machine, separately from the Python package. This is a one-time setup
step, not a bug in your session data.

  macOS:            brew install pango
  Debian/Ubuntu:    sudo apt install libpango-1.0-0 libpangocairo-1.0-0 \\
                     libgdk-pixbuf-2.0-0 libcairo2
  Windows:           install the GTK3 runtime -
                     https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

If the full scanning engine is set up (`greybox setup`), you don't need
any of this on the host at all - re-run report generation and it will use
the backend container instead, which already has these libraries.

Full troubleshooting: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting
"""

SYNTHESIS_PROMPT = """You are writing the executive summary of a penetration test report.
Scope tested: {scope}
Number of checks run: {count}

Raw findings (tool: summary):
{findings_text}

Write a concise, professional 2-3 paragraph executive summary in plain
language for a non-technical stakeholder. Do not invent findings that
aren't in the list above. If the list is empty or inconclusive, say so
plainly rather than padding the summary.
"""

ANALYSIS_PROMPT = """You are a security analyst reviewing raw scan output from an
authorized penetration test. Scope tested: {scope}

Raw output from each tool that ran:
{findings_text}

Produce a plain-text analysis in exactly this structure, with these exact
section headers, nothing else:

METHODOLOGY:
One short paragraph explaining, in plain language a non-technical reader
can follow, which checks were run and what each one looks for.

KEY FINDINGS:
One line per real issue you can actually identify in the raw output above
(missing security headers, outdated/unsupported software versions, open
ports worth a second look, likely misconfigurations, etc). Format each
line exactly as:
[SEVERITY] short description - which tool found it
SEVERITY must be one of CRITICAL, HIGH, MEDIUM, LOW, INFO. Do not invent
issues that aren't actually in the raw output - if there is nothing
noteworthy, write a single line: [INFO] No significant issues identified
in this pass.

RECOMMENDED FIXES:
One line per finding above, in the same order, with a short concrete
remediation step. If a finding is informational only and needs no action,
write "No action needed."

Do not use markdown formatting (no **, no #, no bullet characters). Keep
every line plain and scannable.
"""


def _findings_text(session: Session) -> str:
    lines = []
    for f in session.findings:
        clean_summary = _strip_ansi(f.summary or "").strip()
        lines.append(f"- [{f.tool}] {f.target}: {clean_summary[:300]}")
    return "\n".join(lines) if lines else "(no findings logged)"


def _findings_text_detailed(session: Session) -> str:
    """More context per finding than _findings_text - the vulnerability
    analysis needs enough raw detail (actual header names, version
    strings, etc.) to identify real issues, not just a one-line gist."""
    lines = []
    for f in session.findings:
        clean_summary = _strip_ansi(f.summary or "").strip()
        lines.append(f"=== [{f.tool}] {f.target} ===\n{clean_summary[:1500]}")
    return "\n\n".join(lines) if lines else "(no findings logged)"


_SEVERITY_LINE_RE = re.compile(r"^\[?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\]?\s*[:\-]?\s*(.+)$", re.IGNORECASE)
_SECTION_MARKERS = [
    ("METHODOLOGY:", "methodology"),
    ("KEY FINDINGS:", "key_findings"),
    ("RECOMMENDED FIXES:", "recommended_fixes"),
]


def _split_analysis(text: str) -> dict[str, str]:
    """Lenient split of the model's structured response into sections.
    Local models don't always follow formatting instructions perfectly -
    if none of the expected headers show up at all, the whole response
    falls back into key_findings so nothing is silently dropped.
    """
    sections = {"methodology": "", "key_findings": "", "recommended_fixes": ""}
    text_upper = text.upper()
    positions = []
    for marker, key in _SECTION_MARKERS:
        idx = text_upper.find(marker)
        if idx != -1:
            positions.append((idx, marker, key))
    positions.sort()
    for i, (idx, marker, key) in enumerate(positions):
        start = idx + len(marker)
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        sections[key] = text[start:end].strip()
    if not positions and text.strip():
        sections["key_findings"] = text.strip()
    return sections


def _parse_severity_lines(text: str) -> list[dict[str, str]]:
    """Parses '[SEVERITY] description' lines into structured rows so the
    template can render each as a colored badge, matching the same
    severity styling already used for raw findings."""
    items = []
    for line in text.splitlines():
        line = line.strip("-\u2022 \t")
        if not line:
            continue
        m = _SEVERITY_LINE_RE.match(line)
        if m:
            items.append({"severity": m.group(1).lower(), "text": m.group(2).strip()})
        else:
            items.append({"severity": "info", "text": line})
    return items


def _parse_fixes(text: str) -> list[str]:
    return [line.strip("-\u2022 \t") for line in text.splitlines() if line.strip()]


def _count_severities(findings: list[dict]) -> list[dict]:
    """Ordered counts for the at-a-glance summary bar - only severities
    that actually occurred are included, so an all-clear scan doesn't
    show a row of zeroes."""
    order = ["critical", "high", "medium", "low", "info"]
    counts = {level: 0 for level in order}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in counts:
            counts[sev] += 1
    return [{"severity": level, "count": counts[level]} for level in order if counts[level] > 0]


def _synthesize_summary(session: Session) -> str:
    if not llm.is_available():
        return (
            "Local LLM (Ollama) was not reachable when this report was generated, "
            "so this summary was not synthesized. Raw findings are listed below."
        )
    prompt = SYNTHESIS_PROMPT.format(
        scope=session.scope,
        count=len(session.findings),
        findings_text=_findings_text(session),
    )
    return _strip_markdown_noise(llm.generate_text(prompt))


def _synthesize_analysis(session: Session) -> dict:
    """Structured vulnerability analysis: methodology in plain language,
    findings tagged by severity, and a matching remediation step per
    finding. Degrades gracefully (empty sections, no crash) if the LLM
    isn't reachable - same fallback behavior as the narrative summary.
    """
    if not llm.is_available():
        return {"methodology": "", "findings": [], "fixes": []}
    prompt = ANALYSIS_PROMPT.format(
        scope=session.scope,
        findings_text=_findings_text_detailed(session),
    )
    raw = _strip_markdown_noise(llm.generate_text(prompt))
    if not raw:
        return {"methodology": "", "findings": [], "fixes": []}
    sections = _split_analysis(raw)
    return {
        "methodology": sections["methodology"],
        "findings": _parse_severity_lines(sections["key_findings"]),
        "fixes": _parse_fixes(sections["recommended_fixes"]),
    }


_UNSAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_filename(text: str) -> str:
    cleaned = _UNSAFE_FILENAME_RE.sub("_", text.strip())
    return cleaned.strip("_") or "session"


def build_report(session: Session, output_path: str | None = None) -> Path:
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as e:
        raise RuntimeError(NATIVE_DEPS_HELP.strip()) from e

    summary = _synthesize_summary(session)
    analysis = _synthesize_analysis(session)
    severity_counts = _count_severities(analysis.get("findings", []))
    backend_status = llm.report_backend_status()

    clean_session = deepcopy(session)
    for f in clean_session.findings:
        f.summary = _strip_ansi(f.summary or "")

    tool_descriptions = {name: tool.description for name, tool in TOOL_REGISTRY.items()}

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("template.html")
    html_str = template.render(
        session=clean_session,
        summary=summary,
        analysis=analysis,
        severity_counts=severity_counts,
        tool_descriptions=tool_descriptions,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        backend_status=backend_status,
    )

    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = str(DEFAULT_OUTPUT_DIR / f"{_safe_filename(session.scope)}_{timestamp}.pdf")

    try:
        HTML(string=html_str).write_pdf(output_path)
        os.chmod(output_path, 0o644)  # backend runs as root in the container - make sure the
        # host's regular user can actually read the file it just wrote via the bind mount
    except OSError as e:
        raise RuntimeError(NATIVE_DEPS_HELP.strip()) from e

    return Path(output_path)