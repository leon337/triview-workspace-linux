"""Derived, read-only MCF continuity decisions for TriView.

This module mirrors the MCF v1.1 resume-route decision semantics without
executing resume, reconciliation, recovery, or any authority-bearing action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

McfResumeRoute = Literal["FAST_RESUME", "RECONCILE", "RECOVER_MCF_PROJECT"]
McfDriftStatus = Literal["EXACT", "EXPLAINABLE", "UNEXPLAINED", "UNKNOWN"]


@dataclass(frozen=True, slots=True)
class McfLiveRepositoryState:
    """Small live-repository fact set consumed by the pure route decision."""

    repository: str
    branch: str
    head_sha: str
    worktree_clean: bool


@dataclass(frozen=True, slots=True)
class McfResumeDecisionInput:
    """Explicit facts required by the MCF v1.1 continuity route contract."""

    checkpoint_available: bool
    live_repository_state: McfLiveRepositoryState | None
    authoritative_records_resolved: bool
    methodology_pin_valid: bool
    checkpoint_integrity_valid: bool
    transferability: str | None
    checkpoint_repository: str | None
    checkpoint_branch: str | None
    checkpoint_sha: str | None
    material_drift_explainable: bool
    drift_reason: str | None = None


@dataclass(frozen=True, slots=True)
class McfRouteDecision:
    """Rebuildable orientation-only route projection."""

    route: McfResumeRoute
    reason_codes: tuple[str, ...]
    drift: McfDriftStatus


def decide_resume_route(input: McfResumeDecisionInput) -> McfRouteDecision:
    """Mirror the official MCF v1.1 resume decision from explicit evidence."""

    failures: list[str] = []
    if not input.checkpoint_available:
        failures.append("CHECKPOINT_ABSENT")
    if input.live_repository_state is None:
        failures.append("LIVE_GIT_UNAVAILABLE")
    if not input.authoritative_records_resolved:
        failures.append("AUTHORITATIVE_RECORDS_UNRESOLVED")
    if not input.methodology_pin_valid:
        failures.append("METHODOLOGY_PIN_MISMATCH")
    if not input.checkpoint_integrity_valid:
        failures.append("CHECKPOINT_INTEGRITY_INVALID")
    if input.transferability != "TRANSFERABLE":
        failures.append("CHECKPOINT_NOT_TRANSFERABLE")
    if input.checkpoint_sha is None:
        failures.append("CHECKPOINT_SHA_ABSENT")
    if failures:
        return McfRouteDecision(
            route="RECOVER_MCF_PROJECT",
            reason_codes=tuple(failures),
            drift="UNKNOWN",
        )

    live = input.live_repository_state
    assert live is not None

    if input.checkpoint_repository != live.repository:
        return McfRouteDecision(
            route="RECOVER_MCF_PROJECT",
            reason_codes=("REPOSITORY_IDENTITY_MISMATCH",),
            drift="UNEXPLAINED",
        )

    if input.checkpoint_branch == live.branch and input.checkpoint_sha == live.head_sha:
        return McfRouteDecision(
            route="FAST_RESUME",
            reason_codes=("EXACT_LIVE_MATCH",),
            drift="EXACT",
        )

    if input.material_drift_explainable:
        return McfRouteDecision(
            route="RECONCILE",
            reason_codes=(input.drift_reason or "EXPLAINABLE_DRIFT",),
            drift="EXPLAINABLE",
        )

    return McfRouteDecision(
        route="RECOVER_MCF_PROJECT",
        reason_codes=("UNEXPLAINED_DIVERGENCE",),
        drift="UNEXPLAINED",
    )


__all__ = [
    "McfDriftStatus",
    "McfLiveRepositoryState",
    "McfResumeDecisionInput",
    "McfResumeRoute",
    "McfRouteDecision",
    "decide_resume_route",
]
