"""
Local, file-based session storage.

No database is needed for engagement data - sessions are just JSON files
on disk under ~/.greybox/sessions/. This is deliberately simple: the data
never leaves the user's machine and there is exactly one user.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .schema import Session

SESSIONS_DIR = Path.home() / ".greybox" / "sessions"


def _path_for(session_id: str) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR / f"{session_id}.json"


def save(session: Session) -> Path:
    path = _path_for(session.id)
    path.write_text(session.model_dump_json(indent=2))
    _write_integrity_hash(path)
    return path


def load(session_id: str) -> Session:
    path = _path_for(session_id)
    data = json.loads(path.read_text())
    return Session.model_validate(data)


def list_sessions() -> list[str]:
    if not SESSIONS_DIR.exists():
        return []
    return sorted(p.stem for p in SESSIONS_DIR.glob("*.json"))


def find_by_scope(scope: str) -> Session | None:
    """Find the most recently updated session whose scope matches exactly.
    Used by callers (like the menu bar app) that key off a domain rather
    than a session id, so repeated scans against the same site accumulate
    into one session instead of creating a new one each time.
    """
    matches = [load(sid) for sid in list_sessions()]
    matches = [s for s in matches if s.scope.lower() == scope.lower()]
    if not matches:
        return None
    return max(matches, key=lambda s: s.updated_at)


def _write_integrity_hash(path: Path) -> None:
    """Write a sidecar .sha256 file as a lightweight local audit trail.

    This is the local, dependency-free replacement for the old blockchain
    audit trail: it proves a session file wasn't silently edited after the
    fact, without needing a wallet, gas fees, or a smart contract.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".sha256").write_text(digest + "\n")


def verify_integrity(session_id: str) -> bool:
    path = _path_for(session_id)
    hash_path = path.with_suffix(".sha256")
    if not hash_path.exists():
        return False
    expected = hash_path.read_text().strip()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    return expected == actual
