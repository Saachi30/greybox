"""
Minimal local backend.

This is intentionally thin: it's an HTTP wrapper around `core/` so the
optional web dashboard (or the menu bar app, later) can talk to the same
logic the CLI uses, over localhost. It stores nothing beyond what
core.session_store already writes to disk as JSON - no Postgres, no
Alembic, no ORM, no user accounts. There is exactly one user: whoever is
running this on their own machine.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for `core` import

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from core import session_store, tools
from core.schema import Finding, Session, Severity

app = FastAPI(title="greybox-backend", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


# --------------------------------------------------------------------------
# sessions
# --------------------------------------------------------------------------

class ScopeRequest(BaseModel):
    scope: str


@app.post("/api/sessions")
def create_session(req: ScopeRequest):
    session = Session(scope=req.scope)
    session_store.save(session)
    return session.model_dump()


@app.get("/api/sessions")
def list_sessions():
    return session_store.list_sessions()


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    try:
        return session_store.load(session_id).model_dump()
    except FileNotFoundError:
        raise HTTPException(404, "session not found")


# --------------------------------------------------------------------------
# scans - every call here still requires the caller (CLI/menu bar/dashboard)
# to have already confirmed with the user. This endpoint does not itself
# prompt for confirmation - it executes what it's told, so whoever calls it
# is responsible for the human-in-the-loop step.
# --------------------------------------------------------------------------

class ScanRequest(BaseModel):
    session_id: str
    tool: str
    args: dict[str, str]


@app.post("/api/scan")
def run_scan(req: ScanRequest):
    if req.tool not in tools.REGISTRY:
        raise HTTPException(400, f"unknown tool: {req.tool}")
    try:
        session = session_store.load(req.session_id)
    except FileNotFoundError:
        raise HTTPException(404, "session not found")

    target_value = req.args.get("target") or req.args.get("domain") or ""
    if target_value and not session.in_scope(target_value):
        raise HTTPException(400, f"'{target_value}' is out of scope for session {session.id}")

    tool = tools.REGISTRY[req.tool]
    output = tools.run_tool(tool, req.args)

    finding = Finding(
        tool=tool.name,
        command=tools.preview_command(tool, req.args),
        target=target_value or session.scope,
        summary=output[:500],
        severity=Severity.INFO,
    )
    session.add_finding(finding)
    session_store.save(session)
    return {"finding": finding.model_dump(), "output": output}


# --------------------------------------------------------------------------
# quick scan - one call for lightweight clients (menu bar app) that just
# want "scan this domain, tell me what you found" without managing session
# ids or picking tools themselves. Deliberately limited to non-destructive,
# fast checks - anything deeper belongs in the CLI, which has the full
# registry and per-tool confirmation.
# --------------------------------------------------------------------------

QUICKSCAN_TOOLS = ["whatweb", "nmap"]

# Arg builders for single-tool quick actions from lightweight clients (menu
# bar app) that just want "run this one check against this domain" without
# knowing each tool's exact argument shape.
QUICK_ACTION_ARG_BUILDERS = {
    "nmap": lambda domain: {"target": domain, "scan_type": "quick"},
    "whatweb": lambda domain: {"target": f"https://{domain}"},
    "nikto": lambda domain: {"target": f"https://{domain}"},
    "subdomain_enum": lambda domain: {"domain": domain},
    "crtsh": lambda domain: {"domain": domain},
}


class QuickScanRequest(BaseModel):
    domain: str


@app.post("/api/quickscan")
def quick_scan(req: QuickScanRequest):
    session = session_store.find_by_scope(req.domain)
    if session is None:
        session = Session(scope=req.domain)
        session_store.save(session)

    results = []
    for tool_name in QUICKSCAN_TOOLS:
        tool = tools.REGISTRY[tool_name]
        args = QUICK_ACTION_ARG_BUILDERS[tool_name](req.domain)
        try:
            output = tools.run_tool(tool, args)
        except Exception as e:  # noqa: BLE001 - surface any single tool failure without aborting the whole quickscan
            output = f"error running {tool_name}: {e}"

        finding = Finding(tool=tool.name, command=tools.preview_command(tool, args), target=req.domain,
                           summary=output, severity=Severity.INFO)  # full output - was truncated to 500 chars, same bug already fixed in the CLI
        session.add_finding(finding)
        results.append(finding.model_dump())

    session_store.save(session)
    return {"session_id": session.id, "domain": req.domain, "findings": results}


class QuickActionRequest(BaseModel):
    domain: str
    tool: str


@app.post("/api/quickaction")
def quick_action(req: QuickActionRequest):
    """Run a single named tool against a domain - find-or-create the
    session, execute, log the finding. This is what powers the menu bar
    app's individual quick-action buttons (check open ports, find
    subdomains, etc.) as opposed to /api/quickscan's fixed bundle.
    """
    if req.tool not in QUICK_ACTION_ARG_BUILDERS or req.tool not in tools.REGISTRY:
        raise HTTPException(400, f"quick action not supported for tool: {req.tool}")

    session = session_store.find_by_scope(req.domain)
    if session is None:
        session = Session(scope=req.domain)
        session_store.save(session)

    tool = tools.REGISTRY[req.tool]
    args = QUICK_ACTION_ARG_BUILDERS[req.tool](req.domain)
    try:
        output = tools.run_tool(tool, args)
    except Exception as e:  # noqa: BLE001
        output = f"error running {req.tool}: {e}"

    finding = Finding(tool=tool.name, command=tools.preview_command(tool, args), target=req.domain,
                       summary=output, severity=Severity.INFO)
    session.add_finding(finding)
    session_store.save(session)
    return {"session_id": session.id, "domain": req.domain, "finding": finding.model_dump()}


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

@app.post("/api/sessions/{session_id}/report")
def generate_report(session_id: str):
    from report.generate import build_report

    try:
        session = session_store.load(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "session not found")
    path = build_report(session)
    return {"report_path": str(path)}


@app.post("/api/sessions/{session_id}/report/download")
def download_report(session_id: str):
    """Same report generation as /report, but returns the actual PDF bytes
    in the response body instead of a container-side path. This is what
    the menu bar app should call - no dependency on the host/container
    bind mount being correctly configured, since the bytes travel over the
    HTTP response directly.
    """
    from report.generate import build_report

    try:
        session = session_store.load(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "session not found")

    path = build_report(session)
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=Path(path).name,
    )