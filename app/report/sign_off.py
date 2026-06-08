"""Human sign-off, overrides, and the audit trail.

Nothing is dispositioned without sign-off: an engineer confirms or overrides
each clause's verdict. An override sets the final status and **requires a
justification note**. Every clause becomes an immutable ``AuditEvent``
(original -> final, who, when, action) — the chain that makes the report
auditable. ``signed_at`` is injected so this layer is pure and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.check.types import VerdictStatus
from app.pipeline import CheckReport, ClauseResult

CONFIRM = "confirm"
OVERRIDE = "override"


@dataclass(frozen=True)
class Decision:
    """The engineer's call for one clause. ``final_status`` and ``note`` are
    required for an override (the justification)."""

    action: str  # CONFIRM | OVERRIDE
    final_status: VerdictStatus | None = None
    note: str = ""


@dataclass(frozen=True)
class Disposition:
    clause: ClauseResult
    action: str
    final_status: VerdictStatus
    note: str

    @property
    def is_override(self) -> bool:
        return self.action == OVERRIDE

    @property
    def requirement(self):
        return self.clause.requirement


@dataclass(frozen=True)
class AuditEvent:
    requirement_id: str
    action: str
    original_status: VerdictStatus
    final_status: VerdictStatus
    note: str
    approver: str
    timestamp: datetime


@dataclass(frozen=True)
class SignedReport:
    report: CheckReport
    dispositions: list[Disposition]
    approver: str
    signed_at: datetime
    audit_trail: list[AuditEvent]

    def count(self, status: VerdictStatus) -> int:
        return sum(1 for d in self.dispositions if d.final_status is status)

    @property
    def override_count(self) -> int:
        return sum(1 for d in self.dispositions if d.is_override)


def _disposition(clause: ClauseResult, decision: Decision) -> Disposition:
    if decision.action == OVERRIDE:
        if decision.final_status is None:
            raise ValueError("an override requires a final_status")
        if not decision.note.strip():
            raise ValueError("an override requires a justification note")
        return Disposition(clause, OVERRIDE, decision.final_status, decision.note.strip())
    if decision.action == CONFIRM:
        return Disposition(clause, CONFIRM, clause.status, decision.note.strip())
    raise ValueError(f"unknown decision action {decision.action!r}")


def sign_off(
    report: CheckReport, decisions: list[Decision], *, approver: str, signed_at: datetime
) -> SignedReport:
    """Apply the engineer's per-clause decisions, producing dispositions and the
    audit trail. Requires one decision per clause and a named approver."""
    if not approver.strip():
        raise ValueError("an approver name is required to sign off")
    if len(decisions) != len(report.results):
        raise ValueError("exactly one decision is required per clause")

    dispositions: list[Disposition] = []
    trail: list[AuditEvent] = []
    for clause, decision in zip(report.results, decisions, strict=True):
        disp = _disposition(clause, decision)
        dispositions.append(disp)
        trail.append(
            AuditEvent(
                requirement_id=clause.requirement.id,
                action=disp.action,
                original_status=clause.status,
                final_status=disp.final_status,
                note=disp.note,
                approver=approver.strip(),
                timestamp=signed_at,
            )
        )
    return SignedReport(report, dispositions, approver.strip(), signed_at, trail)
