"""
Anonymous install/usage counter - the ONLY server-side piece of greybox,
and entirely optional/opt-in from the user's side.

This exists to answer one question for the maintainer: "how many people
have installed and are actively using this?" It stores nothing about who a
user is - just a random local instance id (generated once on the user's
machine, never tied to a name/email/IP retained beyond the request) and a
ping counter. No scan data, targets, or findings ever touch this service.

Run with: uvicorn app:app --host 0.0.0.0 --port 9000
Data lives in a single SQLite file - no migrations framework needed for
one table.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

DB_PATH = Path(__file__).parent / "telemetry.db"

app = FastAPI(title="greybox-telemetry", version="0.1.0")


def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pings (
                instance_id TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                ping_count INTEGER NOT NULL DEFAULT 1
            )
            """
        )


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@app.on_event("startup")
def startup():
    _init_db()


class PingRequest(BaseModel):
    instance_id: str  # random UUID generated once by the CLI, not linked to identity
    event: str = "heartbeat"  # "install" or "heartbeat"


@app.post("/ping")
def ping(req: PingRequest):
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        row = conn.execute(
            "SELECT ping_count FROM pings WHERE instance_id = ?", (req.instance_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO pings (instance_id, first_seen, last_seen, ping_count) VALUES (?, ?, ?, 1)",
                (req.instance_id, now, now),
            )
        else:
            conn.execute(
                "UPDATE pings SET last_seen = ?, ping_count = ping_count + 1 WHERE instance_id = ?",
                (now, req.instance_id),
            )
    return {"status": "ok"}


@app.get("/count")
def count():
    """Total distinct installs and total pings - the only stats exposed."""
    with _db() as conn:
        installs = conn.execute("SELECT COUNT(*) FROM pings").fetchone()[0]
        total_pings = conn.execute("SELECT COALESCE(SUM(ping_count), 0) FROM pings").fetchone()[0]
    return {"installs": installs, "total_pings": total_pings}
