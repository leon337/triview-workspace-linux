"""RC4 entry point with atomic browser and terminal X11 embedding."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

from triview_workspace.catalog_migrations import migrate_persisted_terminal_panel
from triview_workspace.engines.browser import BrowserEngine
from triview_workspace.engines.browser_embedded import AtomicX11BraveBrowserBackend
from triview_workspace.engines.runtime_controllers import BrowserRuntimeController
from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_rc4_terminal_migration import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    EMERGENCY_SHORTCUTS,
    POPUP_FAILSAFE_MS,
    POPUP_WATCH_INTERVAL_MS,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as MigratedWorkspaceWindow,
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
from triview_workspace.runtime_observability import (
    record_runtime_event,
    write_runtime_snapshot,
)

BROWSER_BACKEND_NAME = "AtomicX11BraveBrowserBackend"


class WorkspaceWindow(MigratedWorkspaceWindow):
    """Replace the legacy visible-first browser backend in the active RC4 shell."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        super().__init__(root, repository, session_engine)
        backend = AtomicX11BraveBrowserBackend()
        self.runtime_registry.register(BrowserRuntimeController(BrowserEngine(backend)))
        record_runtime_event(
            "browser_backend_registered",
            backend=BROWSER_BACKEND_NAME,
            backend_module=type(backend).__module__,
        )
        self._configure_panel_states()


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    """Start RC4 with canonical migration, provenance and atomic X11 backends."""

    log_path = _configure_logging()
    provenance_path = write_runtime_snapshot(
        module_name="triview_workspace.gui",
        backend_name=BROWSER_BACKEND_NAME,
    )
    record_runtime_event(
        "application_starting",
        log_path=str(log_path),
        provenance_path=str(provenance_path),
        backend=BROWSER_BACKEND_NAME,
    )
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
            record_runtime_event(
                "terminal_catalog_migrated",
                migrated_panels=migrated_panels,
            )
        if workspace_path is not None:
            workspace, layout = load_workspace_bundle(workspace_path)
            catalog = repository.save_workspace(catalog, workspace, layout, make_active=True)
        session_engine = WorkspaceSessionEngine(repository, catalog)
        root = tk.Tk()
        WorkspaceWindow(root, repository, session_engine)
        record_runtime_event("application_ready", backend=BROWSER_BACKEND_NAME)
        root.mainloop()
        record_runtime_event("application_stopped", reason="mainloop_returned")
        return 0
    except Exception as exc:  # noqa: BLE001
        logging.exception("Unable to start atomic TriView Workspace RC4")
        record_runtime_event(
            "application_start_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        print(f"TriView Workspace não pôde abrir: {exc}\nLog: {log_path}")
        return 1


__all__ = [
    "APP_TITLE",
    "BROWSER_BACKEND_NAME",
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
