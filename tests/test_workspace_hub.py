from __future__ import annotations

import json
from pathlib import Path

import pytest

from triview_workspace.domain import (
    LayoutSpec,
    NormalizedRect,
    PanelKind,
    PanelSpec,
    WorkspaceSpec,
)
from triview_workspace.engines.workspace_hub import (
    HUB_SCHEMA_VERSION,
    WorkspaceHubError,
    WorkspaceHubRepository,
)


def bundle() -> tuple[WorkspaceSpec, LayoutSpec]:
    layout = LayoutSpec(
        "three-columns",
        "Three columns",
        (
            NormalizedRect(0, 0, 1 / 3, 1),
            NormalizedRect(1 / 3, 0, 1 / 3, 1),
            NormalizedRect(2 / 3, 0, 1 / 3, 1),
        ),
    )
    workspace = WorkspaceSpec(
        "developer-desk",
        "Developer Desk",
        layout.id,
        (
            PanelSpec("browser", "Browser", PanelKind.BROWSER, "https://example.com"),
            PanelSpec("terminal", "Terminal", PanelKind.TERMINAL, "/bin/bash"),
            PanelSpec("editor", "Editor", PanelKind.APPLICATION, "/usr/bin/xed"),
        ),
    )
    return workspace, layout


def test_workspace_roundtrip_export_and_import_without_structural_loss(tmp_path: Path) -> None:
    workspace, layout = bundle()
    source_hub = WorkspaceHubRepository(tmp_path / "source-hub")
    entry = source_hub.add_bundle(workspace, layout, category="Development")
    exported = source_hub.export_entry(entry.id, tmp_path / "shared-workspace.json")

    target_hub = WorkspaceHubRepository(tmp_path / "target-hub")
    imported = target_hub.import_file(exported)
    imported_workspace, imported_layout = target_hub.load_bundle(imported.id)

    assert imported_workspace == workspace
    assert imported_layout == layout
    assert imported.category == "Development"


def test_template_creates_independent_workspace_and_layout(tmp_path: Path) -> None:
    workspace, layout = bundle()
    hub = WorkspaceHubRepository(tmp_path / "hub")
    entry = hub.add_bundle(workspace, layout, kind="template")

    created_workspace, created_layout = hub.instantiate(
        entry.id,
        "Client Project",
        existing_workspace_ids={workspace.id, "client-project"},
        existing_layout_ids={layout.id, "client-project-2-layout"},
    )

    assert created_workspace.id == "client-project-2"
    assert created_layout.id == "client-project-2-layout-2"
    assert created_workspace.layout_id == created_layout.id
    assert created_workspace.name == "Client Project"
    assert created_workspace.panels == workspace.panels
    assert hub.load_bundle(entry.id) == (workspace, layout)


def test_incompatible_and_symbolic_link_imports_are_rejected(tmp_path: Path) -> None:
    incompatible = tmp_path / "incompatible.json"
    incompatible.write_text(
        json.dumps(
            {
                "hub_schema_version": HUB_SCHEMA_VERSION + 1,
                "document_kind": "workspace",
            }
        ),
        encoding="utf-8",
    )
    hub = WorkspaceHubRepository(tmp_path / "hub")

    with pytest.raises(WorkspaceHubError, match="incompatível"):
        hub.import_file(incompatible)

    workspace, layout = bundle()
    source = WorkspaceHubRepository(tmp_path / "source")
    entry = source.add_bundle(workspace, layout)
    link = tmp_path / "linked.json"
    link.symlink_to(entry.path)
    with pytest.raises(WorkspaceHubError, match="simbólico"):
        hub.import_file(link)


def test_search_categories_and_favorites(tmp_path: Path) -> None:
    workspace, layout = bundle()
    hub = WorkspaceHubRepository(tmp_path / "hub")
    workspace_entry = hub.add_bundle(
        workspace,
        layout,
        category="Development",
        favorite=True,
    )
    template_workspace = WorkspaceSpec(
        "support-desk",
        "Support Desk",
        workspace.layout_id,
        workspace.panels,
    )
    template_entry = hub.add_bundle(
        template_workspace,
        layout,
        kind="template",
        category="Support",
    )

    assert hub.search("developer") == (workspace_entry,)
    assert hub.search(category="Support") == (template_entry,)
    assert hub.search(favorites_only=True) == (workspace_entry,)

    updated = hub.set_favorite(template_entry.id, True)
    assert updated.favorite is True
    assert {item.id for item in hub.search(favorites_only=True)} == {
        workspace_entry.id,
        template_entry.id,
    }


def test_hub_prevents_silent_overwrite(tmp_path: Path) -> None:
    workspace, layout = bundle()
    hub = WorkspaceHubRepository(tmp_path / "hub")
    hub.add_bundle(workspace, layout)

    with pytest.raises(WorkspaceHubError, match="já existe"):
        hub.add_bundle(workspace, layout)
