"""LEA-252 entry point with browsers born inside nested Xephyr panels."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

from triview_workspace.catalog_migrations import (
    ensure_three_gpt_workspace,
    migrate_persisted_terminal_panel,
)
from triview_workspace.engines.browser_live import LiveBrowserEngine
from triview_workspace.engines.browser_wheel_bridge_xephyr import (
    XephyrBrowserWheelBridge,
    XephyrBrowserWheelRoute,
    x11_window_ancestry,
)
from triview_workspace.engines.browser_xephyr import (
    XEPHYR_BROWSER_BACKEND_NAME,
    XephyrEmbeddedBraveBrowserBackend,
)
from triview_workspace.engines.runtime_controllers import BrowserRuntimeController
from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_rc4_atomic import (
    APP_TITLE,
    BROWSER_BACKEND_NAME,
    DEFAULT_WORKSPACE,
    EMERGENCY_SHORTCUTS,
    LIVE_BROWSER_BACKEND_NAME,
    POPUP_FAILSAFE_MS,
    POPUP_WATCH_INTERVAL_MS,
    PanelCard,
    PanelEditorDialog,
    THREE_GPT_WORKSPACE,
    WHEEL_ROUTE_SYNC_MS,
    WorkspaceViewState,
    WorkspaceWindow as AtomicWorkspaceWindow,
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


RC_BROWSER_BACKEND_NAME = XEPHYR_BROWSER_BACKEND_NAME


class WorkspaceWindow(AtomicWorkspaceWindow):
    """Use a nested X server per Browser Panel to eliminate desktop flash."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        super().__init__(root, repository, session_engine)

        previous_bridge = self._wheel_bridge
        if previous_bridge is not None:
            previous_bridge.close()
        self._wheel_bridge = XephyrBrowserWheelBridge()
        self._wheel_bridge.start()

        backend = XephyrEmbeddedBraveBrowserBackend()
        self.runtime_registry.register(
            BrowserRuntimeController(LiveBrowserEngine(backend))
        )
        self._configure_panel_states()
        self._sync_cards_from_runtime()
        record_runtime_event(
            "browser_backend_nested_containment_ready",
            backend=RC_BROWSER_BACKEND_NAME,
            previous_backend="ImmediateHideXfwm4FinalClientX11BraveBrowserBackend",
            backend_module=type(backend).__module__,
            containment="nested_xephyr",
            external_root_mapping_possible=False,
        )

    def _sync_wheel_bridge_routes(self) -> None:
        """Publish host/browser ancestry while the X11 hierarchy is live."""

        if self._closed:
            return
        bridge = self._wheel_bridge
        controller = self.runtime_registry.get("browser")
        engine = getattr(controller, "engine", None)
        routes: list[XephyrBrowserWheelRoute] = []
        if bridge is not None and engine is not None and hasattr(engine, "session"):
            for state in self._workspace_views.values():
                for panel_id, runtime_id in state.runtime_ids.items():
                    card = state.cards_by_id.get(panel_id)
                    if card is None or card.panel.adapter_name != "browser":
                        continue
                    session = engine.session(runtime_id)
                    if session is None or not session.window_id:
                        continue
                    try:
                        host_window_id = int(card.native_host_id())
                    except (AttributeError, tk.TclError, ValueError):
                        continue
                    browser_window_id = str(session.window_id)
                    routes.append(
                        XephyrBrowserWheelRoute(
                            runtime_id=runtime_id,
                            host_window_id=host_window_id,
                            browser_window_id=browser_window_id,
                            host_ancestry=x11_window_ancestry(host_window_id),
                            browser_ancestry=x11_window_ancestry(browser_window_id),
                        )
                    )
            bridge.sync(routes)
        self.root.after(WHEEL_ROUTE_SYNC_MS, self._sync_wheel_bridge_routes)


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    """Start the nested-X11 release candidate."""

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
            catalog = repository.save_workspace(
                catalog,
                workspace,
                layout,
                make_active=True,
            )

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
        logging.exception("Unable to start Xephyr-contained TriView RC4")
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
    "WHEEL_ROUTE_SYNC_MS",
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
