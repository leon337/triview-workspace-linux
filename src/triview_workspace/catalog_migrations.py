"""Targeted, idempotent migrations for persisted workspace catalogs."""

from __future__ import annotations

from triview_workspace.domain import PanelKind, PanelSpec, WorkspaceSpec
from triview_workspace.infrastructure import WorkspaceCatalog, WorkspaceRepository

DEVELOPMENT_WORKSPACE_ID = "development-demo"
TERMINAL_PANEL_ID = "terminal"
TERMINAL_TITLE = "Terminal"
TERMINAL_TARGET = "bash -l"
LEGACY_TERMINAL_TARGETS = frozenset(
    {
        "x-terminal-emulator",
        "x-terminal-simulator",
        "xed",
    }
)


def _is_canonical_development_terminal(workspace: WorkspaceSpec, panel: PanelSpec) -> bool:
    return (
        workspace.id.casefold() == DEVELOPMENT_WORKSPACE_ID
        and panel.id.casefold() == TERMINAL_PANEL_ID
        and panel.title == TERMINAL_TITLE
        and panel.kind is PanelKind.TERMINAL
        and panel.target == TERMINAL_TARGET
    )


def _is_development_terminal_slot(workspace: WorkspaceSpec, panel: PanelSpec) -> bool:
    """Identify only the canonical Terminal slot of the Development workspace."""

    return (
        workspace.id.casefold() == DEVELOPMENT_WORKSPACE_ID
        and panel.id.casefold() == TERMINAL_PANEL_ID
    )


def migrate_persisted_terminal_panel(
    repository: WorkspaceRepository,
    catalog: WorkspaceCatalog,
) -> tuple[WorkspaceCatalog, int]:
    """Restore the Development workspace Terminal contract without touching others.

    The stable contract is workspace ``development-demo`` plus panel ``terminal``.
    Earlier acceptance tests changed that slot to an application or a third ChatGPT
    browser. This migration restores only that stable slot to ``Terminal`` / terminal
    / ``bash -l``. The separate ``three-gpt-chats`` workspace and every unrelated
    workspace remain byte-for-byte equivalent at the domain level. Re-running the
    migration is a no-op.
    """

    updated_catalog = catalog
    migrated_panels = 0

    for workspace in catalog.workspaces:
        changed = False
        panels: list[PanelSpec] = []

        for panel in workspace.panels:
            if not _is_development_terminal_slot(workspace, panel):
                panels.append(panel)
                continue
            if _is_canonical_development_terminal(workspace, panel):
                panels.append(panel)
                continue

            panels.append(
                PanelSpec(
                    id=panel.id,
                    title=TERMINAL_TITLE,
                    kind=PanelKind.TERMINAL,
                    target=TERMINAL_TARGET,
                    metadata=panel.metadata,
                )
            )
            migrated_panels += 1
            changed = True

        if not changed:
            continue

        migrated_workspace = WorkspaceSpec(
            id=workspace.id,
            name=workspace.name,
            layout_id=workspace.layout_id,
            panels=tuple(panels),
        )
        updated_catalog = repository.save_workspace(
            updated_catalog,
            migrated_workspace,
            make_active=False,
        )

    return updated_catalog, migrated_panels


__all__ = [
    "DEVELOPMENT_WORKSPACE_ID",
    "LEGACY_TERMINAL_TARGETS",
    "TERMINAL_PANEL_ID",
    "TERMINAL_TARGET",
    "TERMINAL_TITLE",
    "migrate_persisted_terminal_panel",
]
