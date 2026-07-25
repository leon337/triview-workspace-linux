from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from triview_workspace.domain import (
    LayoutSpec,
    NormalizedRect,
    PanelKind,
    PanelSpec,
    WorkspaceSpec,
)
from triview_workspace.infrastructure import (
    SCHEMA_VERSION,
    WorkspaceRepository,
    WorkspaceStorageError,
    workspace_bundle_to_dict,
)


def sample_bundle() -> tuple[WorkspaceSpec, LayoutSpec]:
    layout = LayoutSpec(
        id="three-mobile",
        name="Três painéis",
        slots=(
            NormalizedRect(0, 0, 0.3, 1),
            NormalizedRect(0.35, 0, 0.3, 1),
            NormalizedRect(0.7, 0, 0.3, 1),
        ),
    )
    workspace = WorkspaceSpec(
        id="development",
        name="Desenvolvimento",
        layout_id=layout.id,
        panels=(
            PanelSpec("chatgpt", "ChatGPT", PanelKind.BROWSER, "https://chatgpt.com"),
            PanelSpec("github", "GitHub", PanelKind.BROWSER, "https://github.com"),
            PanelSpec("terminal", "Terminal", PanelKind.APPLICATION, "x-terminal-emulator"),
        ),
    )
    return workspace, layout


def test_bootstrap_persists_versioned_catalog_and_reopens_active_workspace(tmp_path: Path) -> None:
    workspace, layout = sample_bundle()
    path = tmp_path / "workspaces.json"
    repository = WorkspaceRepository(path)

    catalog = repository.load_or_bootstrap(workspace, layout)
    assert path.exists()
    assert catalog.schema_version == SCHEMA_VERSION
    assert repository.active_bundle(catalog) == (workspace, layout)

    reopened = WorkspaceRepository(path).load()
    assert reopened.active_workspace_id == workspace.id
    assert reopened.workspaces == (workspace,)


def test_create_edit_switch_and_delete_workspace(tmp_path: Path) -> None:
    workspace, layout = sample_bundle()
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    catalog = repository.load_or_bootstrap(workspace, layout)

    copied = replace(workspace, id="research", name="Pesquisa")
    catalog = repository.save_workspace(catalog, copied)
    assert catalog.active_workspace_id == "research"

    renamed = replace(copied, name="Pesquisa técnica")
    catalog = repository.save_workspace(catalog, renamed)
    assert catalog.workspace_by_id("research").name == "Pesquisa técnica"

    catalog = repository.set_active(catalog, workspace.id)
    assert WorkspaceRepository(repository.path).load().active_workspace_id == workspace.id

    catalog = repository.delete_workspace(catalog, "research")
    assert [item.id for item in catalog.workspaces] == [workspace.id]
    with pytest.raises(WorkspaceStorageError, match="último workspace"):
        repository.delete_workspace(catalog, workspace.id)


def test_legacy_bundle_is_migrated_to_versioned_catalog(tmp_path: Path) -> None:
    workspace, layout = sample_bundle()
    path = tmp_path / "workspaces.json"
    path.write_text(
        json.dumps(workspace_bundle_to_dict(workspace, layout)),
        encoding="utf-8",
    )

    catalog = WorkspaceRepository(path).load()
    assert catalog.schema_version == SCHEMA_VERSION
    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == SCHEMA_VERSION
    assert migrated["active_workspace_id"] == workspace.id


def test_invalid_catalog_is_quarantined_and_default_is_restored(tmp_path: Path) -> None:
    workspace, layout = sample_bundle()
    path = tmp_path / "workspaces.json"
    path.write_text("{invalid", encoding="utf-8")
    repository = WorkspaceRepository(path)

    catalog = repository.load_or_bootstrap(workspace, layout)

    assert repository.active_bundle(catalog) == (workspace, layout)
    assert repository.last_recovery_message is not None
    assert list(tmp_path.glob("workspaces.corrupt-*.json"))


def test_workspace_id_is_stable_and_collision_safe() -> None:
    existing = {"meu-workspace", "meu-workspace-2"}
    assert WorkspaceRepository.create_workspace_id("Meu Workspace", existing) == "meu-workspace-3"
