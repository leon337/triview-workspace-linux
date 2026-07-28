from __future__ import annotations

from pathlib import Path

import pytest

import triview_workspace.gui as active_gui
import triview_workspace.gui_rc4_terminal_migration as migrated_gui
from triview_workspace.catalog_migrations import (
    LEGACY_TERMINAL_TARGETS,
    TERMINAL_TARGET,
    TERMINAL_TITLE,
    migrate_persisted_terminal_panel,
)
from triview_workspace.domain import (
    LayoutSpec,
    NormalizedRect,
    PanelKind,
    PanelSpec,
    WorkspaceSpec,
)
from triview_workspace.infrastructure import SCHEMA_VERSION, WorkspaceCatalog, WorkspaceRepository


def _layout() -> LayoutSpec:
    return LayoutSpec(
        id="layout",
        name="Layout",
        slots=(
            NormalizedRect(0.0, 0.0, 0.5, 1.0),
            NormalizedRect(0.5, 0.0, 0.5, 1.0),
        ),
    )


def _catalog(
    target: str,
    *,
    kind: PanelKind = PanelKind.APPLICATION,
    title: str = "Terminal",
) -> WorkspaceCatalog:
    development = WorkspaceSpec(
        id="development-demo",
        name="Desenvolvimento",
        layout_id="layout",
        panels=(
            PanelSpec(
                id="terminal",
                title=title,
                kind=kind,
                target=target,
                metadata={"preserve": True},
            ),
        ),
    )
    protected = WorkspaceSpec(
        id="three-gpt-chats",
        name="Três chats GPT",
        layout_id="layout",
        panels=(
            PanelSpec(
                id="chatgpt-1",
                title="ChatGPT 1",
                kind=PanelKind.BROWSER,
                target="https://chatgpt.com",
            ),
        ),
    )
    unrelated = WorkspaceSpec(
        id="custom-tools",
        name="Ferramentas",
        layout_id="layout",
        panels=(
            PanelSpec(
                id="terminal",
                title="Editor customizado",
                kind=PanelKind.APPLICATION,
                target="code",
            ),
        ),
    )
    return WorkspaceCatalog(
        schema_version=SCHEMA_VERSION,
        active_workspace_id=protected.id,
        layouts=(_layout(),),
        workspaces=(development, protected, unrelated),
    )


@pytest.mark.parametrize("legacy_target", sorted(LEGACY_TERMINAL_TARGETS))
def test_known_persisted_terminal_variants_are_migrated(
    tmp_path: Path,
    legacy_target: str,
) -> None:
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    original = _catalog(legacy_target)

    migrated, count = migrate_persisted_terminal_panel(repository, original)

    assert count == 1
    assert migrated.active_workspace_id == "three-gpt-chats"
    assert migrated.layouts == original.layouts
    assert migrated.workspace_by_id("three-gpt-chats") == original.workspace_by_id(
        "three-gpt-chats"
    )
    assert migrated.workspace_by_id("custom-tools") == original.workspace_by_id("custom-tools")

    terminal = migrated.workspace_by_id("development-demo").panels[0]
    assert terminal.title == TERMINAL_TITLE
    assert terminal.kind is PanelKind.TERMINAL
    assert terminal.target == TERMINAL_TARGET
    assert terminal.metadata == {"preserve": True}
    assert repository.load() == migrated


def test_development_terminal_slot_is_restored_after_becoming_third_chatgpt(
    tmp_path: Path,
) -> None:
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    original = _catalog(
        "https://chatgpt.com",
        kind=PanelKind.BROWSER,
        title="ChatGPT 3",
    )

    migrated, count = migrate_persisted_terminal_panel(repository, original)

    assert count == 1
    terminal = migrated.workspace_by_id("development-demo").panels[0]
    assert terminal == PanelSpec(
        id="terminal",
        title="Terminal",
        kind=PanelKind.TERMINAL,
        target="bash -l",
        metadata={"preserve": True},
    )
    assert migrated.workspace_by_id("three-gpt-chats") == original.workspace_by_id(
        "three-gpt-chats"
    )


def test_terminal_migration_is_idempotent(tmp_path: Path) -> None:
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    migrated, first_count = migrate_persisted_terminal_panel(
        repository,
        _catalog("https://chatgpt.com", kind=PanelKind.BROWSER, title="ChatGPT 3"),
    )

    repeated, second_count = migrate_persisted_terminal_panel(repository, migrated)

    assert first_count == 1
    assert second_count == 0
    assert repeated == migrated
    assert repository.load() == migrated


def test_same_panel_id_outside_development_workspace_is_preserved(tmp_path: Path) -> None:
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    original = _catalog(TERMINAL_TARGET, kind=PanelKind.TERMINAL, title=TERMINAL_TITLE)

    result, count = migrate_persisted_terminal_panel(repository, original)

    assert count == 0
    assert result == original
    assert not repository.path.exists()
    assert result.workspace_by_id("custom-tools").panels[0].target == "code"


def test_active_gui_runs_the_terminal_migration_entry_point() -> None:
    assert active_gui.main is migrated_gui.main
    assert active_gui.WorkspaceWindow is migrated_gui.WorkspaceWindow
