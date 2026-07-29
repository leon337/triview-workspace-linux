"""Persistent operational sessions layered over the approved atomic RC4 runtime."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from typing import Any

from triview_workspace.catalog_migrations import (
    ensure_three_gpt_workspace,
    migrate_persisted_terminal_panel,
)
from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_rc4_atomic import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    EMERGENCY_SHORTCUTS,
    LIVE_BROWSER_BACKEND_NAME,
    POPUP_FAILSAFE_MS,
    POPUP_WATCH_INTERVAL_MS,
    RC_BROWSER_BACKEND_NAME,
    THREE_GPT_WORKSPACE,
    WHEEL_ROUTE_SYNC_MS,
    PanelCard,
    PanelEditorDialog,
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
from triview_workspace.infrastructure import (
    SessionStateRepository,
    WorkspaceRepository,
    load_workspace_bundle,
    restore_catalog_sessions,
)
from triview_workspace.runtime_observability import (
    record_runtime_event,
    write_runtime_snapshot,
)

SESSION_CHECKPOINT_INTERVAL_MS = 5_000


class WorkspaceWindow(AtomicWorkspaceWindow):
    """Restore safe operational state and checkpoint all live workspace views."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self._session_checkpoint_job: str | None = None
        super().__init__(root, repository, session_engine)
        self._restore_view_preferences()
        self._schedule_session_checkpoint()

    def _load_workspace_view(self, message: str) -> None:
        super()._load_workspace_view(message)
        if hasattr(self, "session_engine"):
            self._restore_view_preferences()

    def _restore_view_preferences(self) -> None:
        try:
            result = self.session_engine.load_session(self.workspace.id)
        except Exception:  # noqa: BLE001
            logging.exception("Unable to read operational session for %s", self.workspace.id)
            return
        for diagnostic in result.diagnostics:
            logging.warning("Session restore: %s", diagnostic)
            record_runtime_event(
                "session_restore_diagnostic",
                workspace_id=self.workspace.id,
                diagnostic=diagnostic,
            )
        snapshot = result.snapshot
        if snapshot is None:
            return
        panel_ids = {panel.id for panel in self.workspace.panels}
        self._view_mode = snapshot.view_mode
        if snapshot.focused_panel_id in panel_ids:
            self._focused_panel_id = snapshot.focused_panel_id
        state = getattr(self, "_workspace_views", {}).get(self.workspace.id)
        if state is not None:
            state.view_mode = self._view_mode
            state.focused_panel_id = self._focused_panel_id
        record_runtime_event(
            "session_preferences_restored",
            workspace_id=self.workspace.id,
            view_mode=self._view_mode,
            focused_panel_id=self._focused_panel_id,
            saved_at=snapshot.saved_at,
        )
        self.root.after_idle(self._render_layout)

    def _runtime_state_for(self, state: WorkspaceViewState, panel_id: str) -> dict[str, Any]:
        card = state.cards_by_id.get(panel_id)
        if card is None:
            return {}
        controller = self.runtime_registry.get(card.panel.adapter_name)
        runtime_id = state.runtime_ids.get(panel_id, panel_id)
        session = self._runtime_session(controller, runtime_id) if controller else None
        panel = state.panel_specs.get(panel_id)
        if panel is None:
            return {}
        operational: dict[str, Any] = {}
        if panel.kind.value == "browser":
            for attribute in ("current_url", "url", "target"):
                value = getattr(session, attribute, None)
                if isinstance(value, str) and value.strip():
                    operational["url"] = value
                    break
        elif panel.kind.value in {"application", "terminal"}:
            for attribute in ("working_directory", "cwd"):
                value = getattr(session, attribute, None)
                if isinstance(value, (str, Path)):
                    operational["working_directory"] = str(value)
                    break
        elif panel.kind.value == "pdf":
            for attribute, key in (("path", "path"), ("page", "page"), ("zoom", "zoom")):
                value = getattr(session, attribute, None)
                if value is not None:
                    operational[key] = value
        return operational

    def _checkpoint_session_states(self) -> None:
        views = getattr(self, "_workspace_views", {})
        for workspace_id, state in tuple(views.items()):
            runtime_states = {
                panel_id: self._runtime_state_for(state, panel_id)
                for panel_id in state.panel_specs
            }
            try:
                self.session_engine.checkpoint(
                    workspace_id,
                    focused_panel_id=state.focused_panel_id,
                    view_mode=state.view_mode,
                    runtime_states=runtime_states,
                )
                record_runtime_event(
                    "session_checkpoint_saved",
                    workspace_id=workspace_id,
                    focused_panel_id=state.focused_panel_id,
                    view_mode=state.view_mode,
                    panel_count=len(state.panel_specs),
                )
            except Exception:  # noqa: BLE001
                logging.exception("Unable to checkpoint operational session for %s", workspace_id)
                record_runtime_event(
                    "session_checkpoint_failed",
                    workspace_id=workspace_id,
                )

    def _schedule_session_checkpoint(self) -> None:
        if self._closed:
            return
        self._session_checkpoint_job = self.root.after(
            SESSION_CHECKPOINT_INTERVAL_MS,
            self._periodic_session_checkpoint,
        )

    def _periodic_session_checkpoint(self) -> None:
        self._session_checkpoint_job = None
        if self._closed:
            return
        self._snapshot_active_state()
        self._checkpoint_session_states()
        self._schedule_session_checkpoint()

    def _cancel_session_checkpoint(self) -> None:
        if self._session_checkpoint_job is None:
            return
        try:
            self.root.after_cancel(self._session_checkpoint_job)
        except tk.TclError:
            pass
        self._session_checkpoint_job = None

    def _close(self) -> None:
        if not self._closed:
            self._snapshot_active_state()
            self._checkpoint_session_states()
            self._cancel_session_checkpoint()
        super()._close()

    def _emergency_exit(self, event: tk.Event[tk.Misc] | None = None) -> str:
        if not self._closed:
            self._snapshot_active_state()
            self._checkpoint_session_states()
            self._cancel_session_checkpoint()
        return super()._emergency_exit(event)


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    """Start the approved runtime with safe cross-restart session recovery."""

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
        session_schema=1,
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

        three_gpt_workspace, three_gpt_layout = load_workspace_bundle(THREE_GPT_WORKSPACE)
        catalog, workspace_added, workspace_activated = ensure_three_gpt_workspace(
            repository,
            catalog,
            three_gpt_workspace,
            three_gpt_layout,
        )
        if workspace_path is not None:
            workspace, layout = load_workspace_bundle(workspace_path)
            catalog = repository.save_workspace(catalog, workspace, layout, make_active=True)

        session_repository = SessionStateRepository()
        catalog, session_diagnostics = restore_catalog_sessions(catalog, session_repository)
        for diagnostic in session_diagnostics:
            logging.warning("Session startup: %s", diagnostic)
            record_runtime_event("session_restore_diagnostic", diagnostic=diagnostic)

        session_engine = WorkspaceSessionEngine(
            repository,
            catalog,
            session_repository=session_repository,
        )
        root = tk.Tk()
        WorkspaceWindow(root, repository, session_engine)
        record_runtime_event(
            "application_ready",
            backend=RC_BROWSER_BACKEND_NAME,
            active_workspace_id=catalog.active_workspace_id,
            workspace_added=workspace_added,
            workspace_activated=workspace_activated,
            session_diagnostics=len(session_diagnostics),
        )
        root.mainloop()
        record_runtime_event("application_stopped", reason="mainloop_returned")
        return 0
    except Exception as exc:  # noqa: BLE001
        logging.exception("Unable to start TriView with persistent sessions")
        record_runtime_event(
            "application_start_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        print(f"TriView Workspace não pôde abrir: {exc}\nLog: {log_path}")
        return 1


__all__ = [
    "APP_TITLE",
    "DEFAULT_WORKSPACE",
    "EMERGENCY_SHORTCUTS",
    "LIVE_BROWSER_BACKEND_NAME",
    "POPUP_FAILSAFE_MS",
    "POPUP_WATCH_INTERVAL_MS",
    "PanelCard",
    "PanelEditorDialog",
    "RC_BROWSER_BACKEND_NAME",
    "SESSION_CHECKPOINT_INTERVAL_MS",
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
