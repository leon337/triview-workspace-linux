"""Targeted, idempotent migrations for persisted workspace catalogs."""

from __future__ import annotations

from triview_workspace.domain import PanelKind, PanelSpec, WorkspaceSpec
from triview_workspace.infrastructure import WorkspaceCatalog, WorkspaceRepository

LEGACY_TERMINAL_TARGETS = frozenset(
    {
        "x-terminal-emulator",
        "x-terminal-simulator",
        "xed",
    }
)
TERMINAL_TARGET = "bash -l"


def _is_known_legacy_terminal(panel: PanelSpec) -> bool:
    """Recognize only the proven legacy/diagnostic Terminal configuration."""

    return (
        panel.id.casefold() == "terminal"
        and panel.title.strip().casefold() == "terminal"
        and panel.kind is PanelKind.APPLICATION
        and panel.target.strip().casefold() in LEGACY_TERMINAL_TARGETS
    )


def migrate_persisted_terminal_panel(
    repository: WorkspaceRepository,
    catalog: WorkspaceCatalog,
) -> tuple[WorkspaceCatalog, int]:
    """Route known legacy Terminal panels to the embedded terminal engine.

    The migration is deliberately narrow: it only changes a panel whose stable
    identity is ``terminal`` and whose application target matches one of the
    configurations observed during the Linux Mint acceptance loop. All layouts,
    active workspace selection, unrelated workspaces, panel titles and metadata
    are preserved. Re-running the migration is a no-op.
    """

    updated_catalog = catalog
    migrated_panels = 0

    for workspace in catalog.workspaces:
        changed = False
        panels: list[PanelSpec] = []

        for panel in workspace.panels:
            if not _is_known_legacy_terminal(panel):
                panels.append(panel)
                continue

            panels.append(
                PanelSpec(
                    id=panel.id,
                    title=panel.title,
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
    "LEGACY_TERMINAL_TARGETS",
    "TERMINAL_TARGET",
    "migrate_persisted_terminal_panel",
]
