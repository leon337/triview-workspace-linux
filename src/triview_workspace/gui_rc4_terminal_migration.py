"""RC4 entry point with persisted Terminal routing migration."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

from triview_workspace.catalog_migrations import migrate_persisted_terminal_panel
from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_rc4_popup import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    EMERGENCY_SHORTCUTS,
    POPUP_FAILSAFE_MS,
    POPUP_WATCH_INTERVAL_MS,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow,
    _configure_logging,
    deferred_menu_action,
    global_bar_height,
    panel_header_height,
    parse_work_area,
    proportional_panel_bounds,
    release_menu_grab,
    request_managed_maximize,
    safe_popup_menu,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    """Start RC4 after idempotently migrating the proven legacy Terminal panel."""

    log_path = _configure_logging()
    try:
        seed_workspace, seed_layout = load_workspace_bundle(DEFAULT_WORKSPACE)
        repository = WorkspaceRepository(data_file)
        catalog = repository.load_or_bootstrap(seed_workspace, seed_layout)
        catalog, migrated_panels = migrate_persisted_terminal_panel(repository, catalog)
        if migrated_panels:
            logging.info(
                "Migrated %s persisted Terminal panel(s) to terminal/bash -l",
                migrated_panels,
            )
        if workspace_path is not None:
            workspace, layout = load_workspace_bundle(workspace_path)
            catalog = repository.save_workspace(catalog, workspace, layout, make_active=True)
        session_engine = WorkspaceSessionEngine(repository, catalog)
        root = tk.Tk()
        WorkspaceWindow(root, repository, session_engine)
        root.mainloop()
        return 0
    except Exception as exc:  # noqa: BLE001
        logging.exception("Unable to start migrated TriView Workspace RC4")
        print(f"TriView Workspace não pôde abrir: {exc}\nLog: {log_path}")
        return 1


__all__ = [
    "APP_TITLE",
    "DEFAULT_WORKSPACE",
    "EMERGENCY_SHORTCUTS",
    "POPUP_FAILSAFE_MS",
    "POPUP_WATCH_INTERVAL_MS",
    "PanelCard",
    "PanelEditorDialog",
    "WorkspaceWindow",
    "deferred_menu_action",
    "global_bar_height",
    "main",
    "panel_header_height",
    "parse_work_area",
    "proportional_panel_bounds",
    "release_menu_grab",
    "request_managed_maximize",
    "safe_popup_menu",
]


if __name__ == "__main__":
    raise SystemExit(main())
