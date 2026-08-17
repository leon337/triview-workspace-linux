from __future__ import annotations

from pathlib import Path

from triview_workspace.mcf_bridge import (
    McfArtifactProjection,
    McfBridgeSnapshot,
    McfRepositorySnapshot,
)
from triview_workspace.mcf_cockpit import build_cockpit_model
from triview_workspace.mcf_continuity import McfContinuityDecision


def _snapshot(root: Path) -> McfBridgeSnapshot:
    project = McfRepositorySnapshot(
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
    return McfBridgeSnapshot(project=project, runtime=None)


def _decision() -> McfContinuityDecision:
    return McfContinuityDecision(
        route="RECONCILE",
        reason_codes=("EXPLAINABLE_FORWARD_DRIFT",),
        drift="EXPLAINABLE",
        checkpoint_path="/project/.mcf/continuity/checkpoint-1.json",
        checkpoint_sha="a" * 40,
        live_sha="b" * 40,
        checkpoint_branch="feat/r5",
        live_branch="feat/r5",
        checkpoint_repository="leon337/project",
        live_repository="leon337/project",
        transferability="TRANSFERABLE",
        checkpoint_route_hint="FAST_RESUME",
        worktree_status="CLEAN",
        authoritative_records_resolved=True,
        methodology_pin_valid=True,
        checkpoint_integrity_valid=True,
        material_drift_explainable=True,
        next_action="Continue from checkpoint",
    )


def test_cockpit_projects_derived_r5_continuity_without_mutating_authority(
    tmp_path: Path,
) -> None:
    model = build_cockpit_model(_snapshot(tmp_path), continuity=_decision())

    assert model.continuity == {
        "route": "RECONCILE",
        "reason": "EXPLAINABLE_FORWARD_DRIFT",
        "checkpoint": "aaaaaaaaaaaa",
        "live": "bbbbbbbbbbbb",
        "drift": "EXPLAINABLE",
        "transferability": "TRANSFERABLE",
        "next_action": "Continue from checkpoint",
        "authority": "ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS",
    }
    assert model.mode == "READ_ONLY"


def test_cockpit_projects_missing_evidence_conservatively(tmp_path: Path) -> None:
    decision = McfContinuityDecision(
        route="RECOVER_MCF_PROJECT",
        reason_codes=("CHECKPOINT_ABSENT",),
        drift="UNKNOWN",
        checkpoint_path=None,
        checkpoint_sha=None,
        live_sha=None,
        checkpoint_branch=None,
        live_branch=None,
        checkpoint_repository=None,
        live_repository=None,
        transferability=None,
        checkpoint_route_hint=None,
        worktree_status="UNAVAILABLE",
        authoritative_records_resolved=False,
        methodology_pin_valid=False,
        checkpoint_integrity_valid=False,
        material_drift_explainable=False,
        next_action="",
    )

    model = build_cockpit_model(_snapshot(tmp_path), continuity=decision)

    assert model.continuity["route"] == "RECOVER_MCF_PROJECT"
    assert model.continuity["reason"] == "CHECKPOINT_ABSENT"
    assert model.continuity["checkpoint"] == "AUSENTE"
    assert model.continuity["live"] == "INDISPONÍVEL"
    assert model.continuity["drift"] == "UNKNOWN"
    assert model.continuity["transferability"] == "N/A"
    assert model.continuity["next_action"] == "N/A"
    assert model.continuity["authority"] == "ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS"
