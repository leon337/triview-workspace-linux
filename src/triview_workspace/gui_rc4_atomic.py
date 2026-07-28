"""Release-candidate entry point with live workspaces and nested X11 containment."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from pathlib import Path
from typing import Any

from triview_workspace.catalog_migrations import (
    ensure_three_gpt_workspace,
    migrate_persisted_terminal_panel,
)
from triview_workspace.engines.browser_live import (
    LiveBrowserEngine,
    NO_FLASH_BROWSER_BACKEND_NAME,
)
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

# Preserve public compatibility constants while the active RC uses nested Xephyr.
LIVE_BROWSER_BACKEND_NAME = NO_FLASH_BROWSER_BACKEND_NAME
RC_BROWSER_BACKEND_NAME = XEPHYR_BROWSER_BACKEND_NAME
WHEEL_ROUTE_SYNC_MS = 250


class WorkspaceWindow(LiveWorkspaceWindow):
    """Live sessions with nested Browser containment and auditable wheel routes."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self._wheel_bridge: XephyrBrowserWheelBridge | None = None
        super().__init__(root, repository, session_engine)

        backend = XephyrEmbeddedBraveBrowserBackend()
        self.runtime_registry.register(
            BrowserRuntimeController(LiveBrowserEngine(backend))
        )
        self._configure_panel_states()
        self._sync_cards_from_runtime()
        record_runtime_event(
            "browser_backend_nested_containment_ready",
            backend=RC_BROWSER_BACKEND_NAME,
            compatibility_name=BROWSER_BACKEND_NAME,
            backend_module=type(backend).__module__,
            containment="nested_xephyr",
            external_root_mapping_possible=False,
        )

        self._wheel_bridge = XephyrBrowserWheelBridge()
        self._wheel_bridge.start()
        root.after(WHEEL_ROUTE_SYNC_MS, self._sync_wheel_bridge_routes)

    def _load_workspace_view(self, message: str) -> None:
        """Invalidate stale UI jobs, preserve runtimes and snapshot restored state."""

        if hasattr(self, "_generation"):
            self._generation += 1
        super()._load_workspace_view(message)
        workspace_id = getattr(self, "_displayed_workspace_id", None)
        if workspace_id:
            self._record_workspace_runtime_snapshot("restored", workspace_id)

    def _park_workspace(self, workspace_id: str) -> None:
        self._record_workspace_runtime_snapshot("before_park", workspace_id)
        super()._park_workspace(workspace_id)
        self._record_workspace_runtime_snapshot("parked", workspace_id)

    def _poll_browser_pointer_focus(self) -> None:
        """Do not implement focus-follows-mouse.

        The wheel bridge captures only buttons 4 and 5 on the Browser host and
        never observes or changes keyboard focus.
        """

        return

    def _sync_wheel_bridge_routes(self) -> None:
        """Publish live host/browser ancestry for exact physical correlation."""

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

    def _runtime_session(self, controller: Any, runtime_id: str) -> Any | None:
        engine = getattr(controller, "engine", None)
        if engine is None:
            return None
        getter = getattr(engine, "session", None)
        if callable(getter):
            try:
                return getter(runtime_id)
            except Exception:  # noqa: BLE001
                return None
        sessions = getattr(engine, "_sessions", None)
        if isinstance(sessions, dict):
            return sessions.get(runtime_id)
        return None

    def _workspace_runtime_inventory(self, workspace_id: str) -> list[dict[str, Any]]:
        state = self._workspace_views.get(workspace_id)
        if state is None:
            return []
        inventory: list[dict[str, Any]] = []
        for panel_id, runtime_id in sorted(state.runtime_ids.items()):
            card = state.cards_by_id.get(panel_id)
            adapter = card.panel.adapter_name if card is not None else "unknown"
            controller = self.runtime_registry.get(adapter)
            active = bool(controller is not None and controller.has_session(runtime_id))
            session = self._runtime_session(controller, runtime_id) if controller else None
            process = getattr(session, "process", None)
            pid = getattr(process, "pid", None)
            try:
                pgid = os.getpgid(int(pid)) if pid is not None else None
            except (OSError, TypeError, ValueError):
                pgid = None
            window_id = getattr(session, "window_id", None)
            try:
                host_window_id = int(card.native_host_id()) if card is not None else None
            except (AttributeError, tk.TclError, ValueError):
                host_window_id = None
            inventory.append(
                {
                    "workspace_id": workspace_id,
                    "panel_id": panel_id,
                    "runtime_id": runtime_id,
                    "adapter": adapter,
                    "active": active,
                    "pid": pid,
                    "pgid": pgid,
                    "window_id": str(window_id) if window_id is not None else None,
                    "host_window_id": host_window_id,
                }
            )
        return inventory

    def _record_workspace_runtime_snapshot(self, phase: str, workspace_id: str) -> None:
        inventory = self._workspace_runtime_inventory(workspace_id)
        record_runtime_event(
            "workspace_runtime_snapshot",
            phase=phase,
            workspace_id=workspace_id,
            runtimes=inventory,
            active_count=sum(bool(item["active"]) for item in inventory),
        )

    def _close(self) -> None:
        bridge = self._wheel_bridge
        if bridge is not None:
            bridge.close()
            self._wheel_bridge = None
        super()._close()


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    """Start the nested-X11 live-workspace RC4 candidate."""

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
        logging.exception("Unable to start nested-X11 TriView RC4")
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
