from __future__ import annotations

import json
from pathlib import Path

import pytest

from triview_workspace.mcf_binding import (
    BINDING_SCHEMA_VERSION,
    McfBindingError,
    McfBindingRepository,
    McfWorkspaceBinder,
)


def _write_mcf_project(root: Path, project_id: str = "project-a") -> Path:
    intent = root / ".mcf" / "intent"
    intent.mkdir(parents=True)
    payload = {
        "artifactType": "PROJECT_INTENT_PACKAGE",
        "schemaVersion": "1.0",
        "projectId": project_id,
        "revisionId": "pip-r1",
        "createdAt": "2026-08-17T06:00:00Z",
        "methodologyPin": {
            "version": "v1.1.0",
            "immutableRef": "5d79f488407c77f7b9f21ecfefb41ddfb3a52aef",
        },
    }
    (intent / "pip-r1.json").write_text(json.dumps(payload), encoding="utf-8")
    return root


def test_bind_persists_only_validated_reference_fields(tmp_path: Path) -> None:
    project_root = _write_mcf_project(tmp_path / "project")
    path = tmp_path / "mcf-bindings.json"
    repository = McfBindingRepository(path)
    binder = McfWorkspaceBinder(repository)

    binding = binder.bind(
        "workspace-a",
        project_root,
        mission_id="mission-1",
        runtime_url="https://mcf.example.test/",
    )

    assert binding.workspace_id == "workspace-a"
    assert binding.project_root == project_root.resolve()
    assert binding.project_id == "project-a"
    assert binding.mission_id == "mission-1"
    assert binding.runtime_url == "https://mcf.example.test/"
    assert repository.get("workspace-a") == binding

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == BINDING_SCHEMA_VERSION
    assert persisted["bindings"] == [
        {
            "workspace_id": "workspace-a",
            "project_root": str(project_root.resolve()),
            "project_id": "project-a",
            "mission_id": "mission-1",
            "runtime_url": "https://mcf.example.test/",
        }
    ]
    serialized = path.read_text(encoding="utf-8").casefold()
    for forbidden in (
        "token",
        "authorization",
        "project_intent_package",
        "project_reality_report",
        "standing_authorization",
        "human_gate",
        "checkpoint",
    ):
        assert forbidden not in serialized


def test_binding_replaces_same_workspace_and_unbinds_without_touching_other_workspace(
    tmp_path: Path,
) -> None:
    project_a = _write_mcf_project(tmp_path / "a", "project-a")
    project_b = _write_mcf_project(tmp_path / "b", "project-b")
    repository = McfBindingRepository(tmp_path / "bindings.json")
    binder = McfWorkspaceBinder(repository)

    binder.bind("workspace-a", project_a)
    binder.bind("workspace-b", project_b)
    replaced = binder.bind("workspace-a", project_b, mission_id="mission-b")

    assert replaced.project_id == "project-b"
    assert repository.get("workspace-a") == replaced
    assert repository.get("workspace-b") is not None
    assert binder.unbind("workspace-a") is True
    assert repository.get("workspace-a") is None
    assert repository.get("workspace-b") is not None
    assert binder.unbind("workspace-a") is False


def test_invalid_binding_file_is_quarantined_and_empty_store_is_restored(tmp_path: Path) -> None:
    path = tmp_path / "mcf-bindings.json"
    path.write_text("{invalid", encoding="utf-8")
    repository = McfBindingRepository(path)

    assert repository.load_or_empty() == ()
    assert repository.last_recovery_message is not None
    assert list(tmp_path.glob("mcf-bindings.corrupt-*.json"))
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": BINDING_SCHEMA_VERSION,
        "bindings": [],
    }


def test_binding_store_rejects_unknown_or_credential_fields(tmp_path: Path) -> None:
    path = tmp_path / "mcf-bindings.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": BINDING_SCHEMA_VERSION,
                "bindings": [
                    {
                        "workspace_id": "workspace-a",
                        "project_root": "/tmp/project-a",
                        "project_id": "project-a",
                        "mission_id": None,
                        "runtime_url": None,
                        "session_token": "must-never-be-accepted",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(McfBindingError, match="campos não suportados"):
        McfBindingRepository(path).load()


def test_binder_rejects_non_mcf_root(tmp_path: Path) -> None:
    binder = McfWorkspaceBinder(McfBindingRepository(tmp_path / "bindings.json"))

    with pytest.raises(McfBindingError, match="não é um projeto MCF"):
        binder.bind("workspace-a", tmp_path / "plain-project")


def test_resolve_revalidates_canonical_project_identity(tmp_path: Path) -> None:
    project_root = _write_mcf_project(tmp_path / "project", "project-a")
    repository = McfBindingRepository(tmp_path / "bindings.json")
    binder = McfWorkspaceBinder(repository)
    binder.bind("workspace-a", project_root)

    pip_path = project_root / ".mcf" / "intent" / "pip-r1.json"
    payload = json.loads(pip_path.read_text(encoding="utf-8"))
    payload["projectId"] = "project-b"
    pip_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(McfBindingError, match="project_id"):
        binder.resolve("workspace-a")


def test_resolve_returns_none_for_unbound_workspace(tmp_path: Path) -> None:
    binder = McfWorkspaceBinder(McfBindingRepository(tmp_path / "bindings.json"))

    assert binder.resolve("missing-workspace") is None
