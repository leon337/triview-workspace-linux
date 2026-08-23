from __future__ import annotations

import json
from pathlib import Path

import pytest

from triview_workspace.mcf_context_fabric import (
    McfContextFabricError,
    McfContextFabricRepositoryReader,
    McfContextRecoveryReceiptParser,
)


def _capsule(project_id: str = "triview-workspace-linux") -> dict[str, object]:
    return {
        "schema_version": 1,
        "project_id": project_id,
        "purpose": "Workspace for governed agent surfaces",
        "lifecycle": "ACTIVE",
        "snapshot": {
            "current_workstream": "context-fabric-lab-integration",
            "current_status": "IMPLEMENTATION_IN_PROGRESS",
            "next_action": "Validate the read-only cockpit",
            "blockers": ["Physical X11 acceptance remains pending"],
        },
        "sources": {"current_state": "docs/architecture/context.md"},
        "observed_at": "2026-08-23T03:09:19-03:00",
    }


def _registry(project_id: str = "triview-workspace-linux") -> dict[str, object]:
    return {
        "schema_version": 1,
        "project": {"id": project_id, "lifecycle": "REGISTERED"},
        "identity": {
            "canonical_repository": "leon337/triview-workspace-linux",
            "aliases": ["TriView", "triview workspace"],
        },
        "ownership": {"project_owner": "LEANDRO"},
        "context": {
            "capsule_path": ".mcf/project-capsule.yaml",
            "canonical_entrypoints": ["README.md"],
        },
        "freshness": {
            "operational_state": "LIVE_REQUIRED",
            "project_identity": "DURABLE",
        },
    }


def _claim(
    key: str,
    *,
    freshness: str = "DURABLE",
    observed_at: str | None = None,
) -> dict[str, object]:
    claim: dict[str, object] = {
        "claim_key": key,
        "type": "IDENTITY" if freshness == "DURABLE" else "OPERATIONAL",
        "value": "triview-workspace-linux",
        "owner": "MCF_PROJECT_REGISTRY",
        "source_ref": "context/projects/triview-workspace-linux.yaml",
        "freshness": freshness,
        "provenance": [
            {
                "source_ref": "context/projects/triview-workspace-linux.yaml",
                "source_revision": "registry-sha",
            }
        ],
        "requires_live_verification": freshness == "LIVE_REQUIRED",
    }
    if observed_at is not None:
        claim["observed_at"] = observed_at
    return claim


def _receipt() -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_id": "context-recovery-001",
        "project_id": "triview-workspace-linux",
        "recovery_state": "RECOVERED",
        "recovered_at": "2026-08-23T06:09:19Z",
        "read_only": True,
        "material_action": False,
        "sources": [
            {
                "role": "REGISTRY",
                "source_ref": "context/projects/triview-workspace-linux.yaml",
                "source_revision": "registry-sha",
            },
            {
                "role": "CAPSULE",
                "source_ref": ".mcf/project-capsule.yaml",
                "source_revision": "capsule-sha",
                "observed_at": "2026-08-23T03:09:19-03:00",
            },
        ],
        "claims": [_claim("project.id")],
        "warnings": [],
        "evidence_only": True,
    }


def _write_pair(project_root: Path, registry_root: Path) -> tuple[Path, Path]:
    capsule_path = project_root / ".mcf/project-capsule.yaml"
    registry_path = registry_root / "context/projects/triview-workspace-linux.yaml"
    capsule_path.parent.mkdir(parents=True)
    registry_path.parent.mkdir(parents=True)
    capsule_path.write_text(json.dumps(_capsule()), encoding="utf-8")
    registry_path.write_text(json.dumps(_registry()), encoding="utf-8")
    return capsule_path, registry_path


def test_reader_pairs_strict_registry_and_capsule_from_separate_roots(tmp_path: Path) -> None:
    project_root = tmp_path / "triview"
    registry_root = tmp_path / "mcf"
    capsule_path, registry_path = _write_pair(project_root, registry_root)

    projection = McfContextFabricRepositoryReader(registry_root=registry_root).inspect(
        project_root
    )

    assert projection.status == "VALID"
    assert projection.project_id == "triview-workspace-linux"
    assert projection.canonical_repository == "leon337/triview-workspace-linux"
    assert projection.aliases == ("TriView", "triview workspace")
    assert projection.registry_path == str(registry_path.resolve())
    assert projection.capsule_path == str(capsule_path.resolve())
    assert projection.operational_freshness == "LIVE_REQUIRED"
    assert projection.project_identity_freshness == "DURABLE"
    assert projection.current_status == "IMPLEMENTATION_IN_PROGRESS"
    assert projection.error_codes == ()


def test_reader_labels_capsule_without_registry_as_partial_not_live_verified(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "triview"
    capsule_path = project_root / ".mcf/project-capsule.yaml"
    capsule_path.parent.mkdir(parents=True)
    capsule_path.write_text(json.dumps(_capsule()), encoding="utf-8")

    projection = McfContextFabricRepositoryReader().inspect(project_root)

    assert projection.status == "PARTIAL"
    assert projection.project_id == "triview-workspace-linux"
    assert projection.operational_freshness is None
    assert projection.error_codes == ("PROJECT_REGISTRY_UNAVAILABLE",)


def test_reader_rejects_unknown_fields_and_registry_capsule_path_drift(tmp_path: Path) -> None:
    project_root = tmp_path / "triview"
    registry_root = tmp_path / "mcf"
    capsule_path, registry_path = _write_pair(project_root, registry_root)
    invalid_capsule = _capsule()
    invalid_capsule["authority"] = "TRIVIEW"
    capsule_path.write_text(json.dumps(invalid_capsule), encoding="utf-8")

    invalid_projection = McfContextFabricRepositoryReader(
        registry_root=registry_root
    ).inspect(project_root)
    assert invalid_projection.status == "INVALID"
    assert invalid_projection.error_codes == ("CAPSULE_UNKNOWN_FIELDS",)

    capsule_path.write_text(json.dumps(_capsule()), encoding="utf-8")
    invalid_registry = _registry()
    context = invalid_registry["context"]
    assert isinstance(context, dict)
    context["capsule_path"] = "state/project-capsule.yaml"
    registry_path.write_text(json.dumps(invalid_registry), encoding="utf-8")

    drifted = McfContextFabricRepositoryReader(registry_root=registry_root).inspect(project_root)
    assert drifted.status == "INVALID"
    assert drifted.error_codes == ("REGISTRY_CAPSULE_PATH_MISMATCH",)


def test_reader_rejects_yaml_aliases_and_symlinked_capsule(tmp_path: Path) -> None:
    project_root = tmp_path / "triview"
    capsule_path = project_root / ".mcf/project-capsule.yaml"
    capsule_path.parent.mkdir(parents=True)
    capsule_path.write_text("schema_version: &version 1\nproject_id: *version\n", encoding="utf-8")

    aliased = McfContextFabricRepositoryReader().inspect(project_root)
    assert aliased.status == "INVALID"
    assert aliased.error_codes == ("CAPSULE_SOURCE_YAML_ALIAS_FORBIDDEN",)

    capsule_path.unlink()
    external = tmp_path / "external.yaml"
    external.write_text(json.dumps(_capsule()), encoding="utf-8")
    capsule_path.symlink_to(external)

    symlinked = McfContextFabricRepositoryReader().inspect(project_root)
    assert symlinked.status == "INVALID"
    assert symlinked.error_codes == ("CAPSULE_SOURCE_SYMLINK_FORBIDDEN",)


def test_reader_bounds_repository_inputs(tmp_path: Path) -> None:
    project_root = tmp_path / "triview"
    capsule_path = project_root / ".mcf/project-capsule.yaml"
    capsule_path.parent.mkdir(parents=True)
    capsule_path.write_text(json.dumps(_capsule()), encoding="utf-8")

    projection = McfContextFabricRepositoryReader(max_source_bytes=16).inspect(project_root)

    assert projection.status == "INVALID"
    assert projection.error_codes == ("CAPSULE_SOURCE_TOO_LARGE",)


def test_receipt_parser_accepts_only_sanitized_read_only_evidence() -> None:
    projection = McfContextRecoveryReceiptParser().parse(_receipt())

    assert projection.receipt_id == "context-recovery-001"
    assert projection.project_id == "triview-workspace-linux"
    assert projection.recovery_state == "RECOVERED"
    assert projection.read_only is True
    assert projection.material_action is False
    assert projection.evidence_only is True
    assert projection.freshness == ("DURABLE",)
    assert projection.requires_live_verification is False
    assert [source.role for source in projection.sources] == ["REGISTRY", "CAPSULE"]
    assert projection.claims[0].claim_key == "project.id"
    assert not hasattr(projection.claims[0], "value")


def test_receipt_parser_uses_the_mcf_rfc3339_profile() -> None:
    receipt = _receipt()
    receipt["recovered_at"] = "2026-08-23t06:09:19z"

    projection = McfContextRecoveryReceiptParser().parse(receipt)

    assert projection.recovered_at == "2026-08-23t06:09:19z"

    for invalid in ("2026-08-23 06:09:19+00:00", "2026-02-30T06:09:19Z"):
        receipt["recovered_at"] = invalid
        with pytest.raises(McfContextFabricError, match="^RECEIPT_RECOVERED_AT_INVALID$"):
            McfContextRecoveryReceiptParser().parse(receipt)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("read_only", False, "RECEIPT_NOT_READ_ONLY"),
        ("material_action", True, "RECEIPT_NOT_READ_ONLY"),
        ("evidence_only", False, "RECEIPT_NOT_EVIDENCE_ONLY"),
    ],
)
def test_receipt_parser_rejects_authority_or_action_modes(
    field: str,
    value: object,
    code: str,
) -> None:
    receipt = _receipt()
    receipt[field] = value

    with pytest.raises(McfContextFabricError, match=f"^{code}$"):
        McfContextRecoveryReceiptParser().parse(receipt)


def test_receipt_parser_preserves_live_required_freshness_without_claiming_verification() -> None:
    receipt = _receipt()
    receipt["recovery_state"] = "PARTIAL_RECOVERY"
    receipt["claims"] = [_claim("snapshot.current_status", freshness="LIVE_REQUIRED")]
    receipt["warnings"] = ["LIVE_VERIFICATION_UNAVAILABLE:READ_ONLY_CONTEXT_ONLY"]

    projection = McfContextRecoveryReceiptParser().parse(receipt)

    assert projection.recovery_state == "PARTIAL_RECOVERY"
    assert projection.freshness == ("LIVE_REQUIRED",)
    assert projection.requires_live_verification is True
    assert projection.warnings == ("LIVE_VERIFICATION_UNAVAILABLE:READ_ONLY_CONTEXT_ONLY",)


def test_receipt_parser_rejects_unknown_fields_and_incomplete_recovered_evidence() -> None:
    receipt = _receipt()
    receipt["owner"] = "TRIVIEW"
    with pytest.raises(McfContextFabricError, match="^RECEIPT_UNKNOWN_FIELDS$"):
        McfContextRecoveryReceiptParser().parse(receipt)

    incomplete = _receipt()
    incomplete["sources"] = []
    with pytest.raises(
        McfContextFabricError,
        match="^RECEIPT_RECOVERED_EVIDENCE_INCOMPLETE$",
    ):
        McfContextRecoveryReceiptParser().parse(incomplete)
