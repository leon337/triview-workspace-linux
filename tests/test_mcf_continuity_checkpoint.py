from __future__ import annotations

import json
from pathlib import Path

from triview_workspace.mcf_bridge import (
    McfArtifactProjection,
    McfRepositorySnapshot,
    McfRuntimeProjection,
)
from triview_workspace.mcf_continuity import (
    McfCheckpointInspector,
    canonical_json_digest,
)


METHODOLOGY_REF = "5d79f488407c77f7b9f21ecfefb41ddfb3a52aef"


def _project(
    root: Path,
    *,
    project_id: str = "project-1",
    pip_status: str = "VALID",
    prr_status: str = "VALID",
    alignment_status: str = "VALID",
    alignment_decision: str = "PASS",
    methodology_version: str = "v1.1.0",
    methodology_ref: str = METHODOLOGY_REF,
) -> McfRepositorySnapshot:
    return McfRepositorySnapshot(
        root=root,
        is_mcf_project=True,
        project_id=project_id,
        methodology_version=methodology_version,
        pip=McfArtifactProjection(
            status=pip_status,  # type: ignore[arg-type]
            artifact_type="PROJECT_INTENT_PACKAGE",
            path=str(root / ".mcf/intent/pip-r1.json"),
            project_id=project_id,
            revision_id="pip-r1",
            schema_version="1.0",
            methodology_version=methodology_version,
            methodology_ref=methodology_ref,
        ),
        prr=McfArtifactProjection(
            status=prr_status,  # type: ignore[arg-type]
            artifact_type="PROJECT_REALITY_REPORT",
            path=str(root / ".mcf/reality/prr-r1.json"),
            project_id=project_id,
            revision_id="prr-r1",
            schema_version="1.0",
            methodology_version=methodology_version,
            methodology_ref=methodology_ref,
        ),
        alignment=McfArtifactProjection(
            status=alignment_status,  # type: ignore[arg-type]
            artifact_type="INTENT_ALIGNMENT_RECEIPT",
            path=str(root / ".mcf/receipts/intent-alignment-a1.json"),
            project_id=project_id,
            revision_id="a1",
            schema_version="1.0",
            decision=alignment_decision,
        ),
    )


def _checkpoint(
    *,
    project_id: str = "project-1",
    mission_id: str = "mission-1",
    captured_at: str = "2026-08-17T08:00:00Z",
    methodology_version: str = "v1.1.0",
    methodology_ref: str = METHODOLOGY_REF,
) -> dict[str, object]:
    return {
        "schemaVersion": "1.1",
        "projectId": project_id,
        "missionId": mission_id,
        "methodologyPin": {
            "version": methodology_version,
            "immutableRef": methodology_ref,
        },
        "alignedPipRef": {
            "artifactType": "PROJECT_INTENT_PACKAGE",
            "schemaVersion": "1.0",
            "projectId": project_id,
            "revisionId": "pip-r1",
            "path": ".mcf/intent/pip-r1.json",
        },
        "projectRealityReportRef": {
            "artifactType": "PROJECT_REALITY_REPORT",
            "schemaVersion": "1.0",
            "projectId": project_id,
            "revisionId": "prr-r1",
            "path": ".mcf/reality/prr-r1.json",
        },
        "missionContractRef": f".mcf/missions/{mission_id}.json",
        "repositoryState": {
            "repository": "leon337/project",
            "branch": "feat/r5",
            "checkpointSha": "a" * 40,
            "capturedAt": captured_at,
            "volatile": True,
        },
        "resumeRouteHint": "FAST_RESUME",
        "transferability": "TRANSFERABLE",
        "objetivo": "Continue mission",
        "estado": "EM_EXECUCAO",
        "ultimo_sucesso": "Checkpoint persisted",
        "falha_atual": "nenhuma",
        "classe_da_falha": "NENHUMA",
        "efeito_confirmado": "No failure effect",
        "recuperacao_escolhida": "nenhuma",
        "proxima_acao": "Continue from canonical checkpoint",
        "destinatario": "MESTRE",
        "artefatos": [{"tipo": "commit", "referencia": "a" * 40}],
    }


def _write_checkpoint(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / ".mcf/continuity" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _runtime(ref: dict[str, object]) -> McfRuntimeProjection:
    return McfRuntimeProjection(
        mission={
            "id": "mission-1",
            "contract": {"continuityCheckpointRef": ref},
        },
        timeline={},
        observability={},
    )


def _ref(path: str, payload: dict[str, object], *, project_id: str = "project-1") -> dict[str, object]:
    return {
        "artifactType": "MCF_CHECKPOINT",
        "schemaVersion": "1.1",
        "projectId": project_id,
        "revisionId": "checkpoint-1",
        "path": path,
        "contentDigest": canonical_json_digest(payload),
        "repository": "leon337/project",
        "commitSha": "a" * 40,
    }


def test_runtime_checkpoint_ref_wins_and_validates_canonical_evidence(tmp_path: Path) -> None:
    payload = _checkpoint()
    path = _write_checkpoint(tmp_path, "checkpoint-1.json", payload)
    runtime = _runtime(_ref(".mcf/continuity/checkpoint-1.json", payload))

    evidence = McfCheckpointInspector().inspect(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=runtime,
        mission_id="mission-1",
    )

    assert evidence.checkpoint is not None
    assert evidence.checkpoint.path == str(path.resolve())
    assert evidence.checkpoint.project_id == "project-1"
    assert evidence.checkpoint.mission_id == "mission-1"
    assert evidence.checkpoint.repository == "leon337/project"
    assert evidence.checkpoint.branch == "feat/r5"
    assert evidence.checkpoint.checkpoint_sha == "a" * 40
    assert evidence.checkpoint.transferability == "TRANSFERABLE"
    assert evidence.checkpoint.resume_route_hint == "FAST_RESUME"
    assert evidence.checkpoint.next_action == "Continue from canonical checkpoint"
    assert evidence.checkpoint.responsible_agent == "MESTRE"
    assert evidence.checkpoint_integrity_valid is True
    assert evidence.authoritative_records_resolved is True
    assert evidence.methodology_pin_valid is True
    assert evidence.reason_codes == ()


def test_runtime_checkpoint_ref_rejects_digest_mismatch(tmp_path: Path) -> None:
    payload = _checkpoint()
    _write_checkpoint(tmp_path, "checkpoint-1.json", payload)
    ref = _ref(".mcf/continuity/checkpoint-1.json", payload)
    ref["contentDigest"] = "sha256:" + "0" * 64

    evidence = McfCheckpointInspector().inspect(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=_runtime(ref),
        mission_id="mission-1",
    )

    assert evidence.checkpoint is None
    assert evidence.checkpoint_integrity_valid is False
    assert "CHECKPOINT_DIGEST_MISMATCH" in evidence.reason_codes


def test_runtime_checkpoint_ref_cannot_escape_project_root(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-checkpoint.json"
    payload = _checkpoint()
    outside.write_text(json.dumps(payload), encoding="utf-8")

    evidence = McfCheckpointInspector().inspect(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=_runtime(_ref("../outside-checkpoint.json", payload)),
        mission_id="mission-1",
    )

    assert evidence.checkpoint is None
    assert "UNSAFE_CHECKPOINT_PATH" in evidence.reason_codes


def test_local_fallback_selects_newest_matching_checkpoint_when_runtime_is_absent(
    tmp_path: Path,
) -> None:
    older = _checkpoint(captured_at="2026-08-17T07:00:00Z")
    newer = _checkpoint(captured_at="2026-08-17T08:00:00Z")
    _write_checkpoint(tmp_path, "checkpoint-old.json", older)
    newest_path = _write_checkpoint(tmp_path, "checkpoint-new.json", newer)

    evidence = McfCheckpointInspector().inspect(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=None,
        mission_id="mission-1",
    )

    assert evidence.checkpoint is not None
    assert evidence.checkpoint.path == str(newest_path.resolve())
    assert evidence.checkpoint_integrity_valid is True
    assert evidence.authoritative_records_resolved is True


def test_local_fallback_rejects_ambiguous_latest_checkpoint(tmp_path: Path) -> None:
    first = _checkpoint(captured_at="2026-08-17T08:00:00Z")
    second = _checkpoint(captured_at="2026-08-17T08:00:00Z")
    _write_checkpoint(tmp_path, "checkpoint-a.json", first)
    _write_checkpoint(tmp_path, "checkpoint-b.json", second)

    evidence = McfCheckpointInspector().inspect(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=None,
        mission_id="mission-1",
    )

    assert evidence.checkpoint is None
    assert evidence.checkpoint_integrity_valid is False
    assert "CHECKPOINT_AMBIGUOUS" in evidence.reason_codes


def test_checkpoint_project_or_mission_identity_mismatch_is_not_authoritative(tmp_path: Path) -> None:
    project_mismatch = _checkpoint(project_id="other-project")
    project_path = _write_checkpoint(tmp_path, "checkpoint-project.json", project_mismatch)
    project_evidence = McfCheckpointInspector().inspect(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=_runtime(_ref(str(project_path.relative_to(tmp_path)), project_mismatch, project_id="other-project")),
        mission_id="mission-1",
    )

    assert project_evidence.authoritative_records_resolved is False
    assert "PROJECT_ID_MISMATCH" in project_evidence.reason_codes

    mission_mismatch = _checkpoint(mission_id="other-mission")
    mission_path = _write_checkpoint(tmp_path, "checkpoint-mission.json", mission_mismatch)
    mission_evidence = McfCheckpointInspector().inspect(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=_runtime(_ref(str(mission_path.relative_to(tmp_path)), mission_mismatch)),
        mission_id="mission-1",
    )

    assert mission_evidence.authoritative_records_resolved is False
    assert "MISSION_ID_MISMATCH" in mission_evidence.reason_codes


def test_missing_or_non_pass_project_records_force_authoritative_resolution_failure(
    tmp_path: Path,
) -> None:
    payload = _checkpoint()
    _write_checkpoint(tmp_path, "checkpoint-1.json", payload)
    runtime = _runtime(_ref(".mcf/continuity/checkpoint-1.json", payload))

    evidence = McfCheckpointInspector().inspect(
        root=tmp_path,
        project=_project(tmp_path, alignment_status="ABSENT", alignment_decision=""),
        runtime=runtime,
        mission_id="mission-1",
    )

    assert evidence.authoritative_records_resolved is False
    assert "AUTHORITATIVE_RECORDS_UNRESOLVED" in evidence.reason_codes


def test_checkpoint_methodology_must_match_both_canonical_pip_and_prr(tmp_path: Path) -> None:
    payload = _checkpoint(methodology_version="v9.9.9", methodology_ref="different-ref")
    _write_checkpoint(tmp_path, "checkpoint-1.json", payload)
    runtime = _runtime(_ref(".mcf/continuity/checkpoint-1.json", payload))

    evidence = McfCheckpointInspector().inspect(
        root=tmp_path,
        project=_project(tmp_path),
        runtime=runtime,
        mission_id="mission-1",
    )

    assert evidence.methodology_pin_valid is False
    assert "METHODOLOGY_PIN_MISMATCH" in evidence.reason_codes
