"""Derived, read-only MCF continuity decisions for TriView.

This module mirrors the MCF v1.1 continuity semantics without executing resume,
reconciliation, recovery, or any authority-bearing action. Canonical MCF files
are only read; they are never rewritten by this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from triview_workspace.mcf_bridge import McfRepositorySnapshot, McfRuntimeProjection

McfResumeRoute = Literal["FAST_RESUME", "RECONCILE", "RECOVER_MCF_PROJECT"]
McfDriftStatus = Literal["EXACT", "EXPLAINABLE", "UNEXPLAINED", "UNKNOWN"]

_ROUTES = frozenset({"FAST_RESUME", "RECONCILE", "RECOVER_MCF_PROJECT"})
_TRANSFERABILITY = frozenset({"TRANSFERABLE", "BLOCKED_LOCAL_ONLY_STATE"})
_SHA_PATTERN = re.compile(r"^[a-f0-9]{40,64}$")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


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


@dataclass(frozen=True, slots=True)
class McfCheckpointProjection:
    """Validated subset of one canonical MCF v1.1 checkpoint."""

    path: str
    project_id: str
    mission_id: str
    methodology_version: str
    methodology_ref: str
    repository: str
    branch: str
    checkpoint_sha: str | None
    captured_at: str
    transferability: str
    resume_route_hint: McfResumeRoute
    next_action: str
    responsible_agent: str
    aligned_pip_ref: Mapping[str, object] | None = None
    project_reality_report_ref: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class McfCheckpointEvidence:
    """Checkpoint plus conservative authority/integrity checks."""

    checkpoint: McfCheckpointProjection | None
    checkpoint_integrity_valid: bool
    authoritative_records_resolved: bool
    methodology_pin_valid: bool
    reason_codes: tuple[str, ...]


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


def _sort_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _sort_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sort_json(item) for item in value]
    return value


def canonical_json_digest(payload: Mapping[str, object]) -> str:
    """Hash canonical UTF-8 JSON using the MCF recursive-key ordering convention."""

    canonical = json.dumps(
        _sort_json(dict(payload)),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _iso_timestamp(value: object) -> float | None:
    raw = _text(value)
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _append_once(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


class McfCheckpointInspector:
    """Resolve and validate canonical continuity evidence without writing it."""

    def inspect(
        self,
        *,
        root: str | Path,
        project: McfRepositorySnapshot,
        runtime: McfRuntimeProjection | None,
        mission_id: str | None,
    ) -> McfCheckpointEvidence:
        project_root = Path(root).expanduser().resolve()
        target_mission = _text(mission_id)
        if target_mission is None:
            return McfCheckpointEvidence(
                checkpoint=None,
                checkpoint_integrity_valid=False,
                authoritative_records_resolved=False,
                methodology_pin_valid=False,
                reason_codes=("MISSION_ID_ABSENT", "CHECKPOINT_ABSENT"),
            )

        if runtime is not None:
            resolved = self._from_runtime_ref(project_root, project, runtime)
        else:
            resolved = self._from_local_fallback(project_root, target_mission)

        if isinstance(resolved, tuple):
            return McfCheckpointEvidence(
                checkpoint=None,
                checkpoint_integrity_valid=False,
                authoritative_records_resolved=False,
                methodology_pin_valid=False,
                reason_codes=resolved,
            )

        checkpoint = resolved
        reasons: list[str] = []
        authoritative = self._authoritative_records_resolved(
            project,
            checkpoint,
            target_mission,
            reasons,
        )
        methodology_valid = self._methodology_pin_valid(project, checkpoint)
        if not methodology_valid:
            _append_once(reasons, "METHODOLOGY_PIN_MISMATCH")

        return McfCheckpointEvidence(
            checkpoint=checkpoint,
            checkpoint_integrity_valid=True,
            authoritative_records_resolved=authoritative,
            methodology_pin_valid=methodology_valid,
            reason_codes=tuple(reasons),
        )

    def _from_runtime_ref(
        self,
        root: Path,
        project: McfRepositorySnapshot,
        runtime: McfRuntimeProjection,
    ) -> McfCheckpointProjection | tuple[str, ...]:
        mission = _mapping(runtime.mission)
        contract = _mapping(mission.get("contract") if mission is not None else None)
        raw_ref = contract.get("continuityCheckpointRef") if contract is not None else None
        if raw_ref is None:
            return ("CHECKPOINT_ABSENT",)
        ref = _mapping(raw_ref)
        if ref is None:
            return ("CHECKPOINT_REF_INVALID",)

        if (
            _text(ref.get("artifactType")) != "MCF_CHECKPOINT"
            or _text(ref.get("schemaVersion")) != "1.1"
        ):
            return ("CHECKPOINT_REF_INVALID",)

        raw_path = _text(ref.get("path"))
        if raw_path is None:
            return ("CHECKPOINT_REF_INVALID",)
        safe_path = self._safe_path(root, raw_path)
        if safe_path is None:
            return ("UNSAFE_CHECKPOINT_PATH",)

        payload = self._read_payload(safe_path)
        if payload is None:
            return ("CHECKPOINT_REF_INVALID",)

        expected_digest = _text(ref.get("contentDigest"))
        if expected_digest is not None:
            if not _DIGEST_PATTERN.fullmatch(expected_digest):
                return ("CHECKPOINT_REF_INVALID",)
            if canonical_json_digest(payload) != expected_digest:
                return ("CHECKPOINT_DIGEST_MISMATCH",)

        projection = self._parse_checkpoint(safe_path, payload)
        if projection is None:
            return ("CHECKPOINT_INTEGRITY_INVALID",)

        ref_project = _text(ref.get("projectId"))
        if ref_project is None or ref_project != projection.project_id:
            return ("CHECKPOINT_REF_INVALID",)

        return projection

    def _from_local_fallback(
        self,
        root: Path,
        mission_id: str,
    ) -> McfCheckpointProjection | tuple[str, ...]:
        directory = root / ".mcf" / "continuity"
        if not directory.is_dir():
            return ("CHECKPOINT_ABSENT",)

        candidates: list[tuple[float, McfCheckpointProjection]] = []
        invalid_matching = False
        for path in sorted(directory.glob("*.json")):
            payload = self._read_payload(path)
            if payload is None:
                continue
            payload_mission = _text(payload.get("missionId"))
            if payload_mission != mission_id:
                continue
            projection = self._parse_checkpoint(path.resolve(), payload)
            if projection is None:
                invalid_matching = True
                continue
            timestamp = _iso_timestamp(projection.captured_at)
            if timestamp is None:
                invalid_matching = True
                continue
            candidates.append((timestamp, projection))

        if not candidates:
            if invalid_matching:
                return ("CHECKPOINT_INTEGRITY_INVALID",)
            return ("CHECKPOINT_ABSENT",)

        newest = max(timestamp for timestamp, _ in candidates)
        newest_candidates = [projection for timestamp, projection in candidates if timestamp == newest]
        if len(newest_candidates) != 1:
            return ("CHECKPOINT_AMBIGUOUS",)
        return newest_candidates[0]

    @staticmethod
    def _safe_path(root: Path, raw_path: str) -> Path | None:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            return None
        return resolved

    @staticmethod
    def _read_payload(path: Path) -> dict[str, object] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _parse_checkpoint(
        path: Path,
        payload: Mapping[str, object],
    ) -> McfCheckpointProjection | None:
        if _text(payload.get("schemaVersion")) != "1.1":
            return None
        project_id = _text(payload.get("projectId"))
        mission_id = _text(payload.get("missionId"))
        methodology = _mapping(payload.get("methodologyPin"))
        methodology_version = _text(methodology.get("version")) if methodology else None
        methodology_ref = _text(methodology.get("immutableRef")) if methodology else None
        mission_contract_ref = _text(payload.get("missionContractRef"))
        repository_state = _mapping(payload.get("repositoryState"))
        if repository_state is None:
            return None
        repository = _text(repository_state.get("repository"))
        branch = _text(repository_state.get("branch"))
        captured_at = _text(repository_state.get("capturedAt"))
        checkpoint_sha_raw = repository_state.get("checkpointSha")
        checkpoint_sha = _text(checkpoint_sha_raw) if checkpoint_sha_raw is not None else None
        transferability = _text(payload.get("transferability"))
        route_hint = _text(payload.get("resumeRouteHint"))
        next_action = _text(payload.get("nextAction") or payload.get("proxima_acao"))
        responsible_agent = _text(
            payload.get("responsibleAgent") or payload.get("destinatario")
        )

        if not all(
            (
                project_id,
                mission_id,
                methodology_version,
                methodology_ref,
                mission_contract_ref,
                repository,
                branch,
                captured_at,
                transferability,
                route_hint,
                next_action,
                responsible_agent,
            )
        ):
            return None
        if repository_state.get("volatile") is not True:
            return None
        if checkpoint_sha is not None and not _SHA_PATTERN.fullmatch(checkpoint_sha):
            return None
        if _iso_timestamp(captured_at) is None:
            return None
        if transferability not in _TRANSFERABILITY or route_hint not in _ROUTES:
            return None

        aligned_pip_ref = _mapping(payload.get("alignedPipRef"))
        prr_ref = _mapping(payload.get("projectRealityReportRef"))
        return McfCheckpointProjection(
            path=str(path.resolve()),
            project_id=project_id,
            mission_id=mission_id,
            methodology_version=methodology_version,
            methodology_ref=methodology_ref,
            repository=repository,
            branch=branch,
            checkpoint_sha=checkpoint_sha,
            captured_at=captured_at,
            transferability=transferability,
            resume_route_hint=route_hint,  # type: ignore[arg-type]
            next_action=next_action,
            responsible_agent=responsible_agent,
            aligned_pip_ref=aligned_pip_ref,
            project_reality_report_ref=prr_ref,
        )

    @staticmethod
    def _ref_matches_projection(
        ref: Mapping[str, object] | None,
        *,
        artifact_type: str,
        project_id: str,
        revision_id: str | None,
    ) -> bool:
        if ref is None:
            return True
        return (
            _text(ref.get("artifactType")) == artifact_type
            and _text(ref.get("projectId")) == project_id
            and _text(ref.get("revisionId")) == revision_id
        )

    def _authoritative_records_resolved(
        self,
        project: McfRepositorySnapshot,
        checkpoint: McfCheckpointProjection,
        mission_id: str,
        reasons: list[str],
    ) -> bool:
        valid = True
        if project.project_id != checkpoint.project_id:
            _append_once(reasons, "PROJECT_ID_MISMATCH")
            valid = False
        if checkpoint.mission_id != mission_id:
            _append_once(reasons, "MISSION_ID_MISMATCH")
            valid = False

        records_valid = (
            project.is_mcf_project
            and not project.consistency_errors
            and project.project_id is not None
            and project.pip.status == "VALID"
            and project.prr.status == "VALID"
            and project.alignment.status == "VALID"
            and project.alignment.decision == "PASS"
            and project.pip.project_id == checkpoint.project_id
            and project.prr.project_id == checkpoint.project_id
            and project.alignment.project_id == checkpoint.project_id
            and self._ref_matches_projection(
                checkpoint.aligned_pip_ref,
                artifact_type="PROJECT_INTENT_PACKAGE",
                project_id=checkpoint.project_id,
                revision_id=project.pip.revision_id,
            )
            and self._ref_matches_projection(
                checkpoint.project_reality_report_ref,
                artifact_type="PROJECT_REALITY_REPORT",
                project_id=checkpoint.project_id,
                revision_id=project.prr.revision_id,
            )
        )
        if not records_valid:
            _append_once(reasons, "AUTHORITATIVE_RECORDS_UNRESOLVED")
            valid = False
        return valid

    @staticmethod
    def _methodology_pin_valid(
        project: McfRepositorySnapshot,
        checkpoint: McfCheckpointProjection,
    ) -> bool:
        return (
            project.pip.status == "VALID"
            and project.prr.status == "VALID"
            and project.pip.methodology_version == checkpoint.methodology_version
            and project.prr.methodology_version == checkpoint.methodology_version
            and project.pip.methodology_ref == checkpoint.methodology_ref
            and project.prr.methodology_ref == checkpoint.methodology_ref
        )


__all__ = [
    "McfCheckpointEvidence",
    "McfCheckpointInspector",
    "McfCheckpointProjection",
    "McfDriftStatus",
    "McfLiveRepositoryState",
    "McfResumeDecisionInput",
    "McfResumeRoute",
    "McfRouteDecision",
    "canonical_json_digest",
    "decide_resume_route",
]
