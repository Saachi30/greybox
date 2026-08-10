"""
Opt-in, anonymous install/usage ping. Disabled unless the user explicitly
sets GREYBOX_TELEMETRY_URL (and GREYBOX_TELEMETRY_OPT_IN=true) in their
.env - by default nothing is ever sent anywhere.

The instance id is a random UUID cached locally; it identifies "one
installation exists and is being used", nothing more.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import requests

INSTANCE_ID_FILE = Path.home() / ".greybox" / "instance_id"


def _get_or_create_instance_id() -> str:
    INSTANCE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if INSTANCE_ID_FILE.exists():
        return INSTANCE_ID_FILE.read_text().strip()
    new_id = uuid.uuid4().hex
    INSTANCE_ID_FILE.write_text(new_id)
    return new_id


def send_ping(event: str = "heartbeat") -> None:
    if os.environ.get("GREYBOX_TELEMETRY_OPT_IN", "false").lower() != "true":
        return
    url = os.environ.get("GREYBOX_TELEMETRY_URL")
    if not url:
        return
    try:
        requests.post(
            f"{url.rstrip('/')}/ping",
            json={"instance_id": _get_or_create_instance_id(), "event": event},
            timeout=3,
        )
    except requests.exceptions.RequestException:
        pass  # telemetry must never break the actual tool
