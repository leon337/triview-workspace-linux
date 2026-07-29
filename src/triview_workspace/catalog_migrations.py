"""Targeted, idempotent migrations for persisted workspace catalogs."""

from __future__ import annotations

from triview_workspace.domain import LayoutSpec, PanelKind, PanelSpec, WorkspaceSpec
from triview_workspace.infrastructure import WorkspaceCatalog, WorkspaceRepository

DEVELOPMENT_WORKSPACE_ID = "development-demo"
THREE_GPT_WORKSPACE_ID = "three-gpt-agents"
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
    / ``bash -l``. The separate three-agent workspace and every unrelated workspace
    remain byte-for-byte equivalent at the domain level. Re-running the migration is
    a no-op.
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


def ensure_three_gpt_workspace(
    repository: WorkspaceRepository,
    catalog: WorkspaceCatalog,
    workspace: WorkspaceSpec,
    layout: LayoutSpec,
) -> tuple[WorkspaceCatalog, bool, bool]:
    """Install the canonical three-agent workspace once without erasing user edits.

    Existing copies are preserved exactly so panel titles can be customized as agent
    functions. On a catalog that still contains only the technical Development
    workspace, the new operational workspace becomes active. Catalogs with custom
    workspaces keep their current selection.
    """

    if workspace.id != THREE_GPT_WORKSPACE_ID:
        raise ValueError(
            f"Workspace canônico inválido: esperado {THREE_GPT_WORKSPACE_ID!r}, "
            f"recebido {workspace.id!r}."
        )
    if workspace.layout_id != layout.id:
        raise ValueError("Workspace canônico e layout de três agentes são incompatíveis.")
    if any(item.id == THREE_GPT_WORKSPACE_ID for item in catalog.workspaces):
        return catalog, False, False

    activate = (
        len(catalog.workspaces) == 1
        and catalog.active_workspace_id == DEVELOPMENT_WORKSPACE_ID
        and catalog.workspaces[0].id == DEVELOPMENT_WORKSPACE_ID
    )
    updated = repository.save_workspace(
        catalog,
        workspace,
        layout,
        make_active=activate,
    )
    return updated, True, activate


__all__ = [
    "DEVELOPMENT_WORKSPACE_ID",
    "LEGACY_TERMINAL_TARGETS",
    "TERMINAL_PANEL_ID",
    "TERMINAL_TARGET",
    "TERMINAL_TITLE",
    "THREE_GPT_WORKSPACE_ID",
    "ensure_three_gpt_workspace",
    "migrate_persisted_terminal_panel",
]
