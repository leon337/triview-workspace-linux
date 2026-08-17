from __future__ import annotations

from pathlib import Path

from triview_workspace.mcf_bridge import (
    McfArtifactProjection,
    McfRepositorySnapshot,
)
from triview_workspace.mcf_continuity import (
    McfCheckpointEvidence,
    McfCheckpointProjection,
    McfContinuityAnalyzer,
    McfGitEvidence,
    McfLiveRepositoryState,
)


def _project(root: Path) -> McfRepositorySnapshot:
    return McfRepositorySnapshot(
        root=root,
        is_mcf_project=True,
        project_id="project-1",
        methodology_version="v1.1.0",
        pip=McfArtifactProjection(
            status="VALID",
            artifact_type="PROJECT_INTENT_PACKAGE",
            project_id="project-1",
            revision_id="pip-r1",
            methodology_version="v1.1.0",
            methodology_ref="mcf-ref",
        ),
        prr=McfArtifactProjection(
            status="VALID",
            artifact_type="PROJECT_REALITY_REPORT",
            project_id="project-1",
            revision_id="prr-r1",
            methodology_version="v1.1.0",
            methodology_ref="mcf-ref",
        ),
        alignment=McfArtifactProjection(
            status="VALID",
            artifact_type="INTENT_ALIGNMENT_RECEIPT",
            project_id="project-1",
            revision_id="alignment-r1",
            decision="PASS",
        ),
    )


def _checkpoint() -> McfCheckpointProjection:
    return McfCheckpointProjection(
        path="/project/.mcf/continuity/checkpoint-1.json",
        project_id="project-1",
        mission_id="mission-1",
        methodology_version="v1.1.0",
        methodology_ref="mcf-ref",
        repository="leon337/project",
        branch="feat/r5",
        checkpoint_sha="a" * 40,
        captured_at="2026-08-17T08:00:00Z",
        transferability="TRANSFERABLE",
        resume_route_hint="FAST_RESUME",
        next_action="Continue from checkpoint",
        responsible_agent="MESTRE",
    )


class FakeCheckpointInspector:
    def __init__(self, evidence: McfCheckpointEvidence) -> None:
        self.evidence = evidence
        self.calls: list[tuple[Path, str | None]] = []

    def inspect(self, *, root: Path, project: object, runtime: object, mission_id: str | None):
        del project, runtime
        self.calls.append((Path(root), mission_id))
        return self.evidence


class FakeGitObserver:
    def __init__(self, evidence: McfGitEvidence) -> None:
        self.evidence = evidence
        self.calls: list[tuple[Path, McfCheckpointProjection]] = []

    def observe(self, root: Path, checkpoint: McfCheckpointProjection) -> McfGitEvidence:
        self.calls.append((Path(root), checkpoint))
        return self.evidence


def _checkpoint_evidence() -> McfCheckpointEvidence:
    return McfCheckpointEvidence(
        checkpoint=_checkpoint(),
        checkpoint_integrity_valid=True,
        authoritative_records_resolved=True,
        methodology_pin_valid=True,
        reason_codes=(),
    )


def _live(
    *,
    branch: str = "feat/r5",
    sha: str = "a" * 40,
    clean: bool = True,
) -> McfLiveRepositoryState:
    return McfLiveRepositoryState(
        repository="leon337/project",
        branch=branch,
        head_sha=sha,
        worktree_clean=clean,
    )


def test_analyzer_projects_exact_compatible_state_as_fast_resume(tmp_path: Path) -> None:
    inspector = FakeCheckpointInspector(_checkpoint_evidence())
    observer = FakeGitObserver(McfGitEvidence(_live(), False, None, ()))

    decision = McfContinuityAnalyzer(
        checkpoint_inspector=inspector,  # type: ignore[arg-type]
        git_observer=observer,  # type: ignore[arg-type]
    ).analyze(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=None,
        mission_id="mission-1",
    )

    assert decision.route == "FAST_RESUME"
    assert decision.reason_codes == ("EXACT_LIVE_MATCH",)
    assert decision.drift == "EXACT"
    assert decision.checkpoint_sha == "a" * 40
    assert decision.live_sha == "a" * 40
    assert decision.checkpoint_branch == "feat/r5"
    assert decision.live_branch == "feat/r5"
    assert decision.transferability == "TRANSFERABLE"
    assert decision.worktree_status == "CLEAN"
    assert decision.next_action == "Continue from checkpoint"
    assert decision.authority_notice == "ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS"
    assert len(observer.calls) == 1


def test_analyzer_projects_provable_drift_as_reconcile(tmp_path: Path) -> None:
    observer = FakeGitObserver(
        McfGitEvidence(
            _live(sha="b" * 40),
            True,
            "EXPLAINABLE_FORWARD_DRIFT",
            (),
        )
    )

    decision = McfContinuityAnalyzer(
        checkpoint_inspector=FakeCheckpointInspector(_checkpoint_evidence()),  # type: ignore[arg-type]
        git_observer=observer,  # type: ignore[arg-type]
    ).analyze(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=None,
        mission_id="mission-1",
    )

    assert decision.route == "RECONCILE"
    assert decision.reason_codes == ("EXPLAINABLE_FORWARD_DRIFT",)
    assert decision.drift == "EXPLAINABLE"
    assert decision.live_sha == "b" * 40
    assert decision.material_drift_explainable is True


def test_analyzer_preserves_dirty_worktree_as_primary_recovery_reason(tmp_path: Path) -> None:
    observer = FakeGitObserver(
        McfGitEvidence(_live(sha="b" * 40, clean=False), False, None, ("WORKTREE_DIRTY",))
    )

    decision = McfContinuityAnalyzer(
        checkpoint_inspector=FakeCheckpointInspector(_checkpoint_evidence()),  # type: ignore[arg-type]
        git_observer=observer,  # type: ignore[arg-type]
    ).analyze(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=None,
        mission_id="mission-1",
    )

    assert decision.route == "RECOVER_MCF_PROJECT"
    assert decision.reason_codes[0] == "WORKTREE_DIRTY"
    assert "UNEXPLAINED_DIVERGENCE" in decision.reason_codes
    assert decision.drift == "UNEXPLAINED"
    assert decision.worktree_status == "DIRTY"


def test_analyzer_does_not_invoke_git_without_canonical_checkpoint(tmp_path: Path) -> None:
    checkpoint_evidence = McfCheckpointEvidence(
        checkpoint=None,
        checkpoint_integrity_valid=False,
        authoritative_records_resolved=False,
        methodology_pin_valid=False,
        reason_codes=("CHECKPOINT_ABSENT",),
    )
    observer = FakeGitObserver(McfGitEvidence(_live(), False, None, ()))

    decision = McfContinuityAnalyzer(
        checkpoint_inspector=FakeCheckpointInspector(checkpoint_evidence),  # type: ignore[arg-type]
        git_observer=observer,  # type: ignore[arg-type]
    ).analyze(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=None,
        mission_id="mission-1",
    )

    assert decision.route == "RECOVER_MCF_PROJECT"
    assert decision.reason_codes[0] == "CHECKPOINT_ABSENT"
    assert decision.checkpoint_sha is None
    assert decision.live_sha is None
    assert decision.worktree_status == "UNAVAILABLE"
    assert observer.calls == []
