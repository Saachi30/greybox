"""
Shared data schema for greybox.

A Session represents one engagement (one declared scope/target).
Every tool invocation during that session is logged as a Finding.
The report generator consumes a Session and produces a PDF from it.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: str = Field(default_factory=_now)
    tool: str
    command: str
    target: str
    raw_output_path: Optional[str] = None
    summary: Optional[str] = None
    severity: Severity = Severity.INFO
    notes: Optional[str] = None


class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    scope: str  # declared target/domain/CIDR the user authorized for this session
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    findings: list[Finding] = Field(default_factory=list)

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)
        self.updated_at = _now()

    def in_scope(self, target: str) -> bool:
        """Very simple scope check: target must contain or equal the declared scope.
        This is intentionally conservative - it errs toward asking again rather
        than silently allowing an out-of-scope target.
        """
        target = target.lower().strip().rstrip("/")
        scope = self.scope.lower().strip().rstrip("/")
        if not scope:
            # An empty scope must never mean "anything is in scope" - it's a
            # substring of every string, which would silently disable this
            # check entirely. Treat it as "nothing is in scope" instead.
            return False
        return target == scope or target.endswith("." + scope) or scope in target