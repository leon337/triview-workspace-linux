"""Read-only MCF v1.1 continuity evidence and route derivation for TriView.

The module observes canonical MCF checkpoint/project evidence plus live Git state,
then mirrors the MCF v1.1 resume-route decision. It never executes recovery,
mutates Git, writes ``.mcf`` artifacts, or creates authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from triview_workspace.mcf_bridge import (
    McfArtifactProjection,
    McfRepositorySnapshot,
    McfRuntimeProjection,
)

McfResumeRoute = Literal["FAST_RESUME", "RECONCILE", "RECOVER_MCF_PROJECT"]
McfDriftStatus = Literal["EXACT", "EXPLAINABLE", "UNEXPLAINED", "UNKNOWN"]

_ROUTES = frozenset({"FAST_RESUME", "RECONCILE", "RECOVER_MCF_PROJECT"})
_TRANSFERABILITY = frozenset({"TRANSFERABLE", "BLOCKED_LOCAL_ONLY_STATE"})
_SHA_PATTERN = re.compile(r"^[a-f0-9]{40,64}$")
_DIGEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_GIT_TIMEOUT = 3.0
_AUTHORITY_NOTICE = "ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS"


@dataclass(frozen=True, slots=True)
class McfLiveRepositoryState:
    repository: str
    branch: str
    head_sha: str
    worktree_clean: bool


@dataclass(frozen=True, slots=True)
class McfResumeDecisionInput:
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
    route: McfResumeRoute
    reason_codes: tuple[str, ...]
    drift: McfDriftStatus


@dataclass(frozen=True, slots=True)
class McfCheckpointProjection:
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
    checkpoint: McfCheckpointProjection | None
    checkpoint_integrity_valid: bool
    authoritative_records_resolved: bool
    methodology_pin_valid: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class McfGitEvidence:
    live_state: McfLiveRepositoryState | None
    material_drift_explainable: bool
    drift_reason: str | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class McfContinuityDecision:
    """Rebuildable R5 projection; orientation only, never an execution command."""

    route: McfResumeRoute
    reason_codes: tuple[str, ...]
    drift: McfDriftStatus
    checkpoint_path: str | None
    checkpoint_sha: str | None
    live_sha: str | None
    checkpoint_branch: str | None
    live_branch: str | None
    checkpoint_repository: str | None
    live_repository: str | None
    transferability: str | None
    checkpoint_route_hint: McfResumeRoute | None
    worktree_status: str
    authoritative_records_resolved: bool
    methodology_pin_valid: bool
    checkpoint_integrity_valid: bool
    material_drift_explainable: bool
    next_action: str
    authority_notice: str = _AUTHORITY_NOTICE


def decide_resume_route(input: McfResumeDecisionInput) -> McfRouteDecision:
    """Mirror ``ContinuityRecoveryService.decideResumeRoute`` from MCF v1.1."""

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
        return McfRouteDecision("RECOVER_MCF_PROJECT", tuple(failures), "UNKNOWN")

    live = input.live_repository_state
    assert live is not None
    if input.checkpoint_repository != live.repository:
        return McfRouteDecision(
            "RECOVER_MCF_PROJECT",
            ("REPOSITORY_IDENTITY_MISMATCH",),
            "UNEXPLAINED",
        )
    if input.checkpoint_branch == live.branch and input.checkpoint_sha == live.head_sha:
        return McfRouteDecision("FAST_RESUME", ("EXACT_LIVE_MATCH",), "EXACT")
    if input.material_drift_explainable:
        return McfRouteDecision(
            "RECONCILE",
            (input.drift_reason or "EXPLAINABLE_DRIFT",),
            "EXPLAINABLE",
        )
    return McfRouteDecision(
        "RECOVER_MCF_PROJECT",
        ("UNEXPLAINED_DIVERGENCE",),
        "UNEXPLAINED",
    )


def _sort_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _sort_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sort_json(item) for item in value]
    return value


def canonical_json_digest(payload: Mapping[str, object]) -> str:
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


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for reason in group:
            _append_once(merged, reason)
    return tuple(merged)


class McfCheckpointInspector:
    """Resolve canonical checkpoint evidence without writing to the MCF project."""

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
                None,
                False,
                False,
                False,
                ("MISSION_ID_ABSENT", "CHECKPOINT_ABSENT"),
            )

        resolved = (
            self._from_runtime_ref(project_root, runtime)
            if runtime is not None
            else self._from_local_fallback(project_root, target_mission)
        )
        if isinstance(resolved, tuple):
            return McfCheckpointEvidence(None, False, False, False, resolved)

        checkpoint = resolved
        reasons: list[str] = []
        authoritative = self._authoritative_records_resolved(
            project_root,
            project,
            checkpoint,
            target_mission,
            reasons,
        )
        methodology_valid = self._methodology_pin_valid(project, checkpoint)
        if not methodology_valid:
            _append_once(reasons, "METHODOLOGY_PIN_MISMATCH")
        return McfCheckpointEvidence(
            checkpoint,
            True,
            authoritative,
            methodology_valid,
            tuple(reasons),
        )

    def _from_runtime_ref(
        self,
        root: Path,
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
        path = self._safe_path(root, raw_path)
        if path is None:
            return ("UNSAFE_CHECKPOINT_PATH",)
        payload = self._read_payload(path)
        if payload is None:
            return ("CHECKPOINT_REF_INVALID",)

        expected_digest = _text(ref.get("contentDigest"))
        if expected_digest is not None:
            if not _DIGEST_PATTERN.fullmatch(expected_digest):
                return ("CHECKPOINT_REF_INVALID",)
            if canonical_json_digest(payload) != expected_digest:
                return ("CHECKPOINT_DIGEST_MISMATCH",)

        checkpoint = self._parse_checkpoint(path, payload)
        if checkpoint is None:
            return ("CHECKPOINT_INTEGRITY_INVALID",)
        if _text(ref.get("projectId")) != checkpoint.project_id:
            return ("CHECKPOINT_REF_INVALID",)
        return checkpoint

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
            if payload is None or _text(payload.get("missionId")) != mission_id:
                continue
            checkpoint = self._parse_checkpoint(path.resolve(), payload)
            if checkpoint is None:
                invalid_matching = True
                continue
            captured = _iso_timestamp(checkpoint.captured_at)
            if captured is None:
                invalid_matching = True
                continue
            candidates.append((captured, checkpoint))

        if not candidates:
            return (
                ("CHECKPOINT_INTEGRITY_INVALID",)
                if invalid_matching
                else ("CHECKPOINT_ABSENT",)
            )
        newest = max(timestamp for timestamp, _ in candidates)
        latest = [checkpoint for timestamp, checkpoint in candidates if timestamp == newest]
        if len(latest) != 1:
            return ("CHECKPOINT_AMBIGUOUS",)
        return latest[0]

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
        return payload if isinstance(payload, dict) else None

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
        raw_sha = repository_state.get("checkpointSha")
        checkpoint_sha = _text(raw_sha) if raw_sha is not None else None
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
            aligned_pip_ref=_mapping(payload.get("alignedPipRef")),
            project_reality_report_ref=_mapping(payload.get("projectRealityReportRef")),
        )

    def _artifact_ref_matches_projection(
        self,
        root: Path,
        ref: Mapping[str, object] | None,
        projection: McfArtifactProjection,
        *,
        artifact_type: str,
        project_id: str,
    ) -> bool:
        if ref is None:
            return True
        if (
            _text(ref.get("artifactType")) != artifact_type
            or _text(ref.get("schemaVersion")) != projection.schema_version
            or _text(ref.get("projectId")) != project_id
            or _text(ref.get("revisionId")) != projection.revision_id
        ):
            return False

        raw_ref_path = _text(ref.get("path"))
        projection_path = _text(projection.path)
        if raw_ref_path is None or projection_path is None:
            return False
        resolved_ref_path = self._safe_path(root, raw_ref_path)
        if resolved_ref_path is None or resolved_ref_path != Path(projection_path).resolve():
            return False

        expected_digest = _text(ref.get("contentDigest"))
        if expected_digest is None:
            return True
        if not _DIGEST_PATTERN.fullmatch(expected_digest):
            return False
        payload = self._read_payload(resolved_ref_path)
        return payload is not None and canonical_json_digest(payload) == expected_digest

    def _authoritative_records_resolved(
        self,
        root: Path,
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
            and self._artifact_ref_matches_projection(
                root,
                checkpoint.aligned_pip_ref,
                project.pip,
                artifact_type="PROJECT_INTENT_PACKAGE",
                project_id=checkpoint.project_id,
            )
            and self._artifact_ref_matches_projection(
                root,
                checkpoint.project_reality_report_ref,
                project.prr,
                artifact_type="PROJECT_REALITY_REPORT",
                project_id=checkpoint.project_id,
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


def normalize_github_repository(remote_url: str) -> str | None:
    raw = remote_url.strip()
    if not raw:
        return None
    if raw.startswith("git@github.com:"):
        path = raw.split(":", 1)[1]
    else:
        parsed = urlparse(raw)
        if (parsed.hostname or "").casefold() != "github.com":
            return None
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [part for part in path.split("/") if part]
    if len(parts) != 2:
        return None
    return f"{parts[0]}/{parts[1]}".casefold()


GitRunner = Callable[..., subprocess.CompletedProcess[str]]


class McfGitObserver:
    """Read only the Git facts needed for conservative continuity drift analysis."""

    def __init__(self, *, runner: GitRunner = subprocess.run) -> None:
        self._runner = runner

    def observe(
        self,
        root: str | Path,
        checkpoint: McfCheckpointProjection,
    ) -> McfGitEvidence:
        project_root = Path(root).expanduser().resolve()
        prefix = ["git", "-C", str(project_root)]
        origin = self._run([*prefix, "config", "--get", "remote.origin.url"])
        branch = self._run([*prefix, "rev-parse", "--abbrev-ref", "HEAD"])
        head = self._run([*prefix, "rev-parse", "HEAD"])
        status = self._run([*prefix, "status", "--porcelain"])
        if any(result is None or result.returncode != 0 for result in (origin, branch, head, status)):
            return McfGitEvidence(None, False, None, ("LIVE_GIT_UNAVAILABLE",))

        assert origin is not None and branch is not None and head is not None and status is not None
        repository = normalize_github_repository(origin.stdout)
        branch_name = _text(branch.stdout)
        head_sha = _text(head.stdout)
        if (
            repository is None
            or branch_name is None
            or branch_name == "HEAD"
            or head_sha is None
            or not _SHA_PATTERN.fullmatch(head_sha)
        ):
            return McfGitEvidence(None, False, None, ("LIVE_GIT_UNAVAILABLE",))

        live = McfLiveRepositoryState(
            repository=repository,
            branch=branch_name,
            head_sha=head_sha,
            worktree_clean=not bool(status.stdout.strip()),
        )
        if checkpoint.repository.casefold() != live.repository:
            return McfGitEvidence(live, False, None, ("REPOSITORY_IDENTITY_MISMATCH",))
        if not live.worktree_clean:
            return McfGitEvidence(live, False, None, ("WORKTREE_DIRTY",))
        checkpoint_sha = checkpoint.checkpoint_sha
        if checkpoint_sha is None:
            return McfGitEvidence(live, False, None, ("CHECKPOINT_SHA_ABSENT",))
        if checkpoint_sha == live.head_sha:
            if checkpoint.branch != live.branch:
                return McfGitEvidence(live, True, "EXPLAINABLE_BRANCH_DRIFT", ())
            return McfGitEvidence(live, False, None, ())

        exists = self._run([*prefix, "cat-file", "-e", f"{checkpoint_sha}^{{commit}}"])
        if exists is None or exists.returncode != 0:
            return McfGitEvidence(live, False, None, ("CHECKPOINT_COMMIT_UNAVAILABLE",))
        forward = self._run(
            [*prefix, "merge-base", "--is-ancestor", checkpoint_sha, live.head_sha]
        )
        if forward is None or forward.returncode not in {0, 1}:
            return McfGitEvidence(live, False, None, ("LIVE_GIT_UNAVAILABLE",))
        if forward.returncode == 0:
            return McfGitEvidence(live, True, "EXPLAINABLE_FORWARD_DRIFT", ())
        backward = self._run(
            [*prefix, "merge-base", "--is-ancestor", live.head_sha, checkpoint_sha]
        )
        if backward is None or backward.returncode not in {0, 1}:
            return McfGitEvidence(live, False, None, ("LIVE_GIT_UNAVAILABLE",))
        if backward.returncode == 0:
            return McfGitEvidence(live, True, "EXPLAINABLE_BACKWARD_DRIFT", ())
        return McfGitEvidence(live, False, None, ("UNEXPLAINED_DIVERGENCE",))

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return self._runner(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None


class McfContinuityAnalyzer:
    """Compose checkpoint + Git evidence into one orientation-only R5 decision."""

    def __init__(
        self,
        *,
        checkpoint_inspector: McfCheckpointInspector | None = None,
        git_observer: McfGitObserver | None = None,
    ) -> None:
        self.checkpoint_inspector = checkpoint_inspector or McfCheckpointInspector()
        self.git_observer = git_observer or McfGitObserver()

    def analyze(
        self,
        *,
        root: str | Path,
        project: McfRepositorySnapshot,
        runtime: McfRuntimeProjection | None,
        mission_id: str | None,
    ) -> McfContinuityDecision:
        project_root = Path(root).expanduser().resolve()
        checkpoint_evidence = self.checkpoint_inspector.inspect(
            root=project_root,
            project=project,
            runtime=runtime,
            mission_id=mission_id,
        )
        checkpoint = checkpoint_evidence.checkpoint
        git_evidence = (
            McfGitEvidence(None, False, None, ())
            if checkpoint is None
            else self.git_observer.observe(project_root, checkpoint)
        )

        route = decide_resume_route(
            McfResumeDecisionInput(
                checkpoint_available=checkpoint is not None,
                live_repository_state=git_evidence.live_state,
                authoritative_records_resolved=checkpoint_evidence.authoritative_records_resolved,
                methodology_pin_valid=checkpoint_evidence.methodology_pin_valid,
                checkpoint_integrity_valid=checkpoint_evidence.checkpoint_integrity_valid,
                transferability=checkpoint.transferability if checkpoint else None,
                checkpoint_repository=checkpoint.repository if checkpoint else None,
                checkpoint_branch=checkpoint.branch if checkpoint else None,
                checkpoint_sha=checkpoint.checkpoint_sha if checkpoint else None,
                material_drift_explainable=git_evidence.material_drift_explainable,
                drift_reason=git_evidence.drift_reason,
            )
        )
        live = git_evidence.live_state
        reasons = _merge_reasons(
            checkpoint_evidence.reason_codes,
            git_evidence.reason_codes,
            route.reason_codes,
        )
        worktree_status = (
            "UNAVAILABLE"
            if live is None
            else "CLEAN"
            if live.worktree_clean
            else "DIRTY"
        )
        return McfContinuityDecision(
            route=route.route,
            reason_codes=reasons,
            drift=route.drift,
            checkpoint_path=checkpoint.path if checkpoint else None,
            checkpoint_sha=checkpoint.checkpoint_sha if checkpoint else None,
            live_sha=live.head_sha if live else None,
            checkpoint_branch=checkpoint.branch if checkpoint else None,
            live_branch=live.branch if live else None,
            checkpoint_repository=checkpoint.repository if checkpoint else None,
            live_repository=live.repository if live else None,
            transferability=checkpoint.transferability if checkpoint else None,
            checkpoint_route_hint=checkpoint.resume_route_hint if checkpoint else None,
            worktree_status=worktree_status,
            authoritative_records_resolved=checkpoint_evidence.authoritative_records_resolved,
            methodology_pin_valid=checkpoint_evidence.methodology_pin_valid,
            checkpoint_integrity_valid=checkpoint_evidence.checkpoint_integrity_valid,
            material_drift_explainable=git_evidence.material_drift_explainable,
            next_action=checkpoint.next_action if checkpoint else "",
        )


__all__ = [
    "McfCheckpointEvidence",
    "McfCheckpointInspector",
    "McfCheckpointProjection",
    "McfContinuityAnalyzer",
    "McfContinuityDecision",
    "McfDriftStatus",
    "McfGitEvidence",
    "McfGitObserver",
    "McfLiveRepositoryState",
    "McfResumeDecisionInput",
    "McfResumeRoute",
    "McfRouteDecision",
    "canonical_json_digest",
    "decide_resume_route",
    "normalize_github_repository",
]
