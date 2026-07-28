"""Release-candidate entry point for live workspaces and hardened X11 startup."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

from triview_workspace.catalog_migrations import (
    ensure_three_gpt_workspace,
    migrate_persisted_terminal_panel,
)
from triview_workspace.engines.browser_live import (
    LiveBrowserEngine,
    NO_FLASH_BROWSER_BACKEND_NAME,
)
from triview_workspace.engines.browser_live_rc import (
    HARDENED_BROWSER_BACKEND_NAME,
    ImmediateHideXfwm4FinalClientX11BraveBrowserBackend,
)
from triview_workspace.engines.runtime_controllers import BrowserRuntimeController
from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_rc4_live import (
    APP_TITLE,
    BROWSER_BACKEND_NAME,
    DEFAULT_WORKSPACE,
    EMERGENCY_SHORTCUTS,
    POPUP_FAILSAFE_MS,
    POPUP_WATCH_INTERVAL_MS,
    PanelCard,
    PanelEditorDialog,
    THREE_GPT_WORKSPACE,
    WorkspaceViewState,
    WorkspaceWindow as LiveWorkspaceWindow,
    _configure_logging,
    deferred_menu_action,
    global_bar_height,
    panel_header_height,
    parse_work_area,
    proportional_panel_bounds,
    release_menu_grab,
    request_managed_maximize,
    runtime_panel_id,
    safe_popup_menu,
    workspace_panel_signature,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle
from triview_workspace.runtime_observability import (
    record_runtime_event,
    write_runtime_snapshot,
)

# Preserve the first LEA-247 public constant for compatibility with the initial
# tests and diagnostics. The actual RC backend is explicitly named separately.
LIVE_BROWSER_BACKEND_NAME = NO_FLASH_BROWSER_BACKEND_NAME
RC_BROWSER_BACKEND_NAME = HARDENED_BROWSER_BACKEND_NAME


class WorkspaceWindow(LiveWorkspaceWindow):
    """Final RC runtime with bounded focus behavior and generation isolation."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        super().__init__(root, repository, session_engine)

        # Replace the initial no-flash backend before any user-triggered panel
        # opening. The hardened selector hides every candidate window at first
        # observation, not only after final-client stability.
        backend = ImmediateHideXfwm4FinalClientX11BraveBrowserBackend()
        self.runtime_registry.register(
            BrowserRuntimeController(LiveBrowserEngine(backend))
        )
        self._configure_panel_states()
        self._sync_cards_from_runtime()
        record_runtime_event(
            "browser_backend_hardened",
            backend=RC_BROWSER_BACKEND_NAME,
            compatibility_name=BROWSER_BACKEND_NAME,
            backend_module=type(backend).__module__,
        )

    def _load_workspace_view(self, message: str) -> None:
        """Invalidate stale capture/recording results without closing runtimes."""

        if hasattr(self, "_generation"):
            self._generation += 1
        super()._load_workspace_view(message)

    def _poll_browser_pointer_focus(self) -> None:
        """Do not implement focus-follows-mouse.

        Continuous pointer polling can steal keyboard focus from a conversation
        while the user is typing in another Browser Panel. Scroll routing and
        explicit clicks remain available, but the RC never changes keyboard
        focus merely because the pointer moved.
        """

        return


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    """Start the hardened live-workspace RC4 candidate."""

    log_path = _configure_logging()
    provenance_path = write_runtime_snapshot(
        module_name="triview_workspace.gui",
        backend_name=RC_BROWSER_BACKEND_NAME,
    )
    record_runtime_event(
        "application_starting",
        log_path=str(log_path),
        provenance_path=str(provenance_path),
        backend=RC_BROWSER_BACKEND_NAME,
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

        three_gpt_workspace, three_gpt_layout = load_workspace_bundle(THREE_GPT_WORKSPACE)
        catalog, workspace_added, workspace_activated = ensure_three_gpt_workspace(
            repository,
            catalog,
            three_gpt_workspace,
            three_gpt_layout,
        )
        record_runtime_event(
            "three_gpt_workspace_reconciled",
            workspace_id=three_gpt_workspace.id,
            added=workspace_added,
            activated=workspace_activated,
            active_workspace_id=catalog.active_workspace_id,
        )
        if workspace_path is not None:
            workspace, layout = load_workspace_bundle(workspace_path)
            catalog = repository.save_workspace(catalog, workspace, layout, make_active=True)

        session_engine = WorkspaceSessionEngine(repository, catalog)
        root = tk.Tk()
        WorkspaceWindow(root, repository, session_engine)
        record_runtime_event(
            "application_ready",
            backend=RC_BROWSER_BACKEND_NAME,
            active_workspace_id=catalog.active_workspace_id,
        )
        root.mainloop()
        record_runtime_event("application_stopped", reason="mainloop_returned")
        return 0
    except Exception as exc:  # noqa: BLE001
        logging.exception("Unable to start hardened live-workspace TriView RC4")
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
    "LIVE_BROWSER_BACKEND_NAME",
    "POPUP_FAILSAFE_MS",
    "POPUP_WATCH_INTERVAL_MS",
    "PanelCard",
    "PanelEditorDialog",
    "RC_BROWSER_BACKEND_NAME",
    "THREE_GPT_WORKSPACE",
    "WorkspaceViewState",
    "WorkspaceWindow",
    "deferred_menu_action",
    "global_bar_height",
    "main",
    "panel_header_height",
    "parse_work_area",
    "proportional_panel_bounds",
    "release_menu_grab",
    "request_managed_maximize",
    "runtime_panel_id",
    "safe_popup_menu",
    "workspace_panel_signature",
]


if __name__ == "__main__":
    raise SystemExit(main())
