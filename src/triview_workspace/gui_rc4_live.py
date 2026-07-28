"""RC4 live workspaces with persistent runtimes and correlated observability."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from triview_workspace.catalog_migrations import (
    ensure_three_gpt_workspace,
    migrate_persisted_terminal_panel,
)
from triview_workspace.domain import PanelSpec, WorkspaceSpec
from triview_workspace.engines.browser_live import (
    LiveBrowserEngine,
    NO_FLASH_BROWSER_BACKEND_NAME,
    NoFlashXfwm4FinalClientX11BraveBrowserBackend,
)
from triview_workspace.engines.runtime_controllers import BrowserRuntimeController
from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_model import build_panel_view_models
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

# Kept for compatibility with the already validated RC4 contract/tests.
BROWSER_BACKEND_NAME = "Xfwm4FinalClientX11BraveBrowserBackend"
LIVE_BROWSER_BACKEND_NAME = NO_FLASH_BROWSER_BACKEND_NAME
THREE_GPT_WORKSPACE = Path("config/workspaces/three-gpt-agents.json")


def runtime_panel_id(workspace_id: str, panel_id: str) -> str:
    """Namespace one runtime so equal panel IDs can coexist across workspaces."""

    return f"{workspace_id}::{panel_id}"


def workspace_panel_signature(workspace: WorkspaceSpec) -> tuple[str, ...]:
    """Return the panel definition signature that requires a view rebuild."""

    return tuple(
        json.dumps(
            {
                "id": panel.id,
                "title": panel.title,
                "kind": panel.kind.value,
                "target": panel.target,
                "metadata": panel.metadata,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        for panel in workspace.panels
    )


@dataclass(slots=True)
class WorkspaceViewState:
    """Tk cards and runtime identities retained while a workspace is parked."""

    workspace_id: str
    signature: tuple[str, ...]
    cards: list[PanelCard]
    cards_by_id: dict[str, PanelCard]
    panel_specs: dict[str, PanelSpec]
    runtime_ids: dict[str, str]
    focus_buttons: dict[str, tk.Button] = field(default_factory=dict)
    panel_menus: dict[str, tk.Menu] = field(default_factory=dict)
    focused_panel_id: str | None = None
    view_mode: str = "all"
    visible_panel_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class WorkspaceLaunchResult:
    workspace_id: str
    panel_id: str
    runtime_id: str
    adapter_name: str
    state: str
    error: str | None
    embedded: bool
    external: bool
    correlation_id: str


class WorkspaceWindow(MigratedWorkspaceWindow):
    """Keep browser/terminal runtimes alive while switching workspace views."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self._workspace_views: dict[str, WorkspaceViewState] = {}
        self._displayed_workspace_id: str | None = None
        self._runtime_ids: dict[str, str] = {}
        self._live_launching: set[str] = set()
        self._live_results: queue.SimpleQueue[WorkspaceLaunchResult] = queue.SimpleQueue()
        self._live_result_pump_started = False
        self._pointer_focus_runtime_id: str | None = None
        super().__init__(root, repository, session_engine)

        backend = NoFlashXfwm4FinalClientX11BraveBrowserBackend()
        self.runtime_registry.register(
            BrowserRuntimeController(LiveBrowserEngine(backend))
        )
        record_runtime_event(
            "browser_backend_registered",
            backend=LIVE_BROWSER_BACKEND_NAME,
            compatibility_name=BROWSER_BACKEND_NAME,
            backend_module=type(backend).__module__,
        )
        self._configure_panel_states()
        self._sync_cards_from_runtime()
        if not self._live_result_pump_started:
            self._live_result_pump_started = True
            root.after(80, self._drain_live_results)
        root.after(80, self._poll_browser_pointer_focus)
        record_runtime_event(
            "live_workspace_registry_ready",
            active_workspace_id=self.workspace.id,
            cached_workspace_ids=sorted(self._workspace_views),
        )

    def _load_workspace_view(self, message: str) -> None:
        """Park the old Tk view and restore/create the requested one without close_all."""

        previous_id = self._displayed_workspace_id
        current_id = self.workspace.id
        recovery_engine = getattr(self, "recovery_engine", None)
        if recovery_engine is not None and previous_id is not None:
            try:
                self._sync_runtime_state(force=True)
            except Exception:  # noqa: BLE001
                logging.exception("Unable to sync runtime state before workspace switch")

        if previous_id is not None and previous_id in self._workspace_views:
            self._snapshot_active_state()
            if previous_id != current_id:
                self._park_workspace(previous_id)

        self._drop_removed_workspace_views()
        signature = workspace_panel_signature(self.workspace)
        state = self._workspace_views.get(current_id)
        if state is not None and state.signature != signature:
            self._destroy_workspace_state(current_id, reason="panel_definition_changed")
            state = None
        if state is None:
            state = self._create_workspace_state(signature)
            restored = False
        else:
            restored = True

        self._activate_workspace_state(state)
        self._displayed_workspace_id = current_id
        self._refresh_controls()
        self.status_text.set(message)
        if recovery_engine is not None:
            recovery_engine.begin(self.workspace)
            self._runtime_signature = self._signature({})

        event = "workspace_view_restored" if restored else "workspace_view_created"
        record_runtime_event(
            event,
            previous_workspace_id=previous_id,
            workspace_id=current_id,
            panel_ids=[card.panel.id for card in self.cards],
            runtime_ids=sorted(self._runtime_ids.values()),
            live_runtime_count=self._count_live_runtimes(state),
        )
        self.root.after_idle(self._render_layout)

    def _create_workspace_state(
        self,
        signature: tuple[str, ...],
    ) -> WorkspaceViewState:
        self._panel_menus = {}
        self._focus_buttons = {}
        self._view_mode = "all"
        self._visible_panel_ids = set()
        self._focused_panel_id = None
        self._last_compact_panel_sizes.clear()

        prepared = self.workspace_engine.prepare(self.workspace, self.layout, 1200, 650)
        views = build_panel_view_models(prepared)
        self.panel_specs = {item.id: item for item in self.workspace.panels}
        self.cards = [PanelCard(self.content, item, self._open_panel) for item in views]
        self.cards_by_id = {card.panel.id: card for card in self.cards}
        self._runtime_ids = {
            panel_id: runtime_panel_id(self.workspace.id, panel_id)
            for panel_id in self.panel_specs
        }
        self._configure_panel_states()
        if hasattr(self, "_wire_capture_buttons"):
            self._wire_capture_buttons()
        if hasattr(self, "_wire_recording_buttons"):
            self._wire_recording_buttons()
        self._focused_panel_id = self.cards[0].panel.id if self.cards else None
        if hasattr(self, "_wire_focus_controls"):
            self._wire_focus_controls()
        for card in self.cards:
            self._wire_panel_input(card, self.workspace.id)

        state = WorkspaceViewState(
            workspace_id=self.workspace.id,
            signature=signature,
            cards=self.cards,
            cards_by_id=self.cards_by_id,
            panel_specs=self.panel_specs,
            runtime_ids=self._runtime_ids,
            focus_buttons=self._focus_buttons,
            panel_menus=self._panel_menus,
            focused_panel_id=self._focused_panel_id,
            view_mode=self._view_mode,
            visible_panel_ids=set(self._visible_panel_ids),
        )
        self._workspace_views[state.workspace_id] = state
        return state

    def _snapshot_active_state(self) -> None:
        workspace_id = self._displayed_workspace_id
        if workspace_id is None:
            return
        state = self._workspace_views.get(workspace_id)
        if state is None:
            return
        state.cards = self.cards
        state.cards_by_id = self.cards_by_id
        state.panel_specs = self.panel_specs
        state.runtime_ids = self._runtime_ids
        state.focus_buttons = self._focus_buttons
        state.panel_menus = self._panel_menus
        state.focused_panel_id = self._focused_panel_id
        state.view_mode = self._view_mode
        state.visible_panel_ids = set(self._visible_panel_ids)

    def _activate_workspace_state(self, state: WorkspaceViewState) -> None:
        self.cards = state.cards
        self.cards_by_id = state.cards_by_id
        self.panel_specs = state.panel_specs
        self._runtime_ids = state.runtime_ids
        self._focus_buttons = state.focus_buttons
        self._panel_menus = state.panel_menus
        self._focused_panel_id = state.focused_panel_id
        self._view_mode = state.view_mode
        self._visible_panel_ids = set(state.visible_panel_ids)
        self._last_compact_panel_sizes.clear()
        self._sync_cards_from_runtime()

    def _park_workspace(self, workspace_id: str) -> None:
        state = self._workspace_views[workspace_id]
        for card in state.cards:
            card.frame.place_forget()
        record_runtime_event(
            "workspace_view_parked",
            workspace_id=workspace_id,
            panel_ids=[card.panel.id for card in state.cards],
            runtime_ids=sorted(state.runtime_ids.values()),
            live_runtime_count=self._count_live_runtimes(state),
            destroyed_runtimes=0,
        )

    def _sync_cards_from_runtime(self) -> None:
        for card in self.cards:
            controller = self.runtime_registry.get(card.panel.adapter_name)
            runtime_id = self._runtime_ids.get(card.panel.id, card.panel.id)
            if controller is None or not controller.has_session(runtime_id):
                continue
            card.show_host()
            card.set_open(True, "Reabrir")
            card.set_status(
                "ATIVO",
                f"{card.panel.title} permaneceu ativo neste workspace.",
            )

    def _count_live_runtimes(self, state: WorkspaceViewState) -> int:
        count = 0
        for panel_id, runtime_id in state.runtime_ids.items():
            card = state.cards_by_id.get(panel_id)
            if card is None:
                continue
            controller = self.runtime_registry.get(card.panel.adapter_name)
            if controller is not None and controller.has_session(runtime_id):
                count += 1
        return count

    def _destroy_workspace_state(self, workspace_id: str, *, reason: str) -> None:
        state = self._workspace_views.pop(workspace_id, None)
        if state is None:
            return
        closed = 0
        for panel_id, runtime_id in state.runtime_ids.items():
            card = state.cards_by_id.get(panel_id)
            controller = (
                self.runtime_registry.get(card.panel.adapter_name) if card is not None else None
            )
            if controller is not None and controller.has_session(runtime_id):
                try:
                    controller.close(runtime_id)
                    closed += 1
                except Exception:  # noqa: BLE001
                    logging.exception("Unable to close runtime %s", runtime_id)
        for menu in state.panel_menus.values():
            try:
                menu.destroy()
            except Exception:  # noqa: BLE001
                pass
        for card in state.cards:
            try:
                card.destroy()
            except Exception:  # noqa: BLE001
                pass
        record_runtime_event(
            "workspace_view_destroyed",
            workspace_id=workspace_id,
            reason=reason,
            closed_runtimes=closed,
        )

    def _drop_removed_workspace_views(self) -> None:
        valid_ids = {item.id for item in self.session_engine.catalog.workspaces}
        for workspace_id in tuple(self._workspace_views):
            if workspace_id not in valid_ids:
                self._destroy_workspace_state(workspace_id, reason="workspace_removed")

    def _open_panel(self, view: Any, card: PanelCard) -> None:
        controller = self.runtime_registry.get(view.adapter_name)
        runtime_id = self._runtime_ids.get(view.id, runtime_panel_id(self.workspace.id, view.id))
        if controller is None or self._closed or runtime_id in self._live_launching:
            return
        panel = replace(self.panel_specs[view.id], id=runtime_id)
        availability = controller.availability(panel)
        if not availability.available:
            card.configure_runtime(False, availability.reason)
            return

        workspace_id = self.workspace.id
        correlation_id = f"open-{time.monotonic_ns()}"
        self._live_launching.add(runtime_id)
        card.show_host()
        card.set_open(False, "Abrindo…")
        card.set_status("ABRINDO", f"Inicializando {view.title} sem janela externa.")
        self.root.update_idletasks()
        host_id = card.native_host_id()
        width, height = card.host_dimensions()
        record_runtime_event(
            "panel_open_requested",
            correlation_id=correlation_id,
            workspace_id=workspace_id,
            panel_id=view.id,
            runtime_id=runtime_id,
            adapter=view.adapter_name,
            host_window_id=host_id,
        )

        def launch() -> None:
            try:
                result = controller.open(panel, host_id, width, height)
            except Exception as exc:  # noqa: BLE001
                self._live_results.put(
                    WorkspaceLaunchResult(
                        workspace_id,
                        view.id,
                        runtime_id,
                        view.adapter_name,
                        "error",
                        str(exc),
                        False,
                        False,
                        correlation_id,
                    )
                )
                return
            if self._closed:
                controller.close(runtime_id)
                return
            self._live_results.put(
                WorkspaceLaunchResult(
                    workspace_id,
                    view.id,
                    runtime_id,
                    view.adapter_name,
                    "opened",
                    None,
                    result.embedded,
                    result.external,
                    correlation_id,
                )
            )

        threading.Thread(
            target=launch,
            name=f"triview-live-{view.adapter_name}-{runtime_id}",
            daemon=True,
        ).start()

    def _drain_live_results(self) -> None:
        if self._closed:
            return
        while True:
            try:
                result = self._live_results.get_nowait()
            except queue.Empty:
                break
            self._live_launching.discard(result.runtime_id)
            state = self._workspace_views.get(result.workspace_id)
            if state is None or result.panel_id not in state.cards_by_id:
                controller = self.runtime_registry.get(result.adapter_name)
                if controller is not None and controller.has_session(result.runtime_id):
                    controller.close(result.runtime_id)
                continue
            card = state.cards_by_id[result.panel_id]
            if result.state == "error":
                card.show_placeholder()
                card.set_open(True, "Tentar novamente")
                card.set_status("ERRO", result.error or "Falha desconhecida.")
                record_runtime_event(
                    "panel_open_failed",
                    correlation_id=result.correlation_id,
                    workspace_id=result.workspace_id,
                    panel_id=result.panel_id,
                    runtime_id=result.runtime_id,
                    error=result.error,
                )
                continue
            card.set_open(True, "Reabrir")
            if result.embedded:
                card.show_host()
                card.set_status(
                    "ATIVO",
                    f"{card.panel.title} está ativo dentro do painel.",
                )
            elif result.external:
                card.show_placeholder()
                card.set_status(
                    "EXTERNO",
                    f"{card.panel.title} abriu externamente e falhou no contrato RC4.",
                )
            record_runtime_event(
                "panel_open_completed",
                correlation_id=result.correlation_id,
                workspace_id=result.workspace_id,
                panel_id=result.panel_id,
                runtime_id=result.runtime_id,
                embedded=result.embedded,
                external=result.external,
                active_workspace_id=self._displayed_workspace_id,
            )
            if result.workspace_id == self._displayed_workspace_id:
                self.status_text.set(f"Painel {card.panel.title} aberto")
                self._resize_runtimes()
        self.root.after(80, self._drain_live_results)

    def _controller_for_runtime(self, runtime_id: str) -> Any | None:
        for state in self._workspace_views.values():
            for panel_id, candidate in state.runtime_ids.items():
                if candidate != runtime_id:
                    continue
                card = state.cards_by_id.get(panel_id)
                if card is not None:
                    return self.runtime_registry.get(card.panel.adapter_name)
        return None

    def _resize_runtimes(self) -> None:
        if self._closed:
            return
        visible = self._visible_panel_ids or {card.panel.id for card in self.cards}
        for card in self.cards:
            if card.panel.id not in visible:
                continue
            controller = self.runtime_registry.get(card.panel.adapter_name)
            runtime_id = self._runtime_ids.get(card.panel.id, card.panel.id)
            if controller is None or not controller.has_session(runtime_id):
                continue
            width, height = card.host_dimensions()
            try:
                controller.resize(runtime_id, width, height)
            except Exception as exc:  # noqa: BLE001
                logging.warning("Unable to resize runtime %s: %s", runtime_id, exc)

    def _runtime_statuses(self) -> dict[str, tuple[str, bool, bool]]:
        statuses: dict[str, tuple[str, bool, bool]] = {}
        for card in self.cards:
            controller = self.runtime_registry.get(card.panel.adapter_name)
            runtime_id = self._runtime_ids.get(card.panel.id, card.panel.id)
            if controller is None or not controller.has_session(runtime_id):
                continue
            embedded, external = self._session_mode(controller, runtime_id)
            statuses[card.panel.id] = (
                card.panel.adapter_name,
                embedded,
                external,
            )
        return statuses

    def _close_panel(self, card: PanelCard) -> None:
        controller = self.runtime_registry.get(card.panel.adapter_name)
        runtime_id = self._runtime_ids.get(card.panel.id, card.panel.id)
        if controller is not None:
            try:
                controller.close(runtime_id)
            except Exception as exc:  # noqa: BLE001
                logging.warning("Unable to close runtime %s: %s", runtime_id, exc)
        card.show_placeholder()
        card.set_open(True, "Abrir")
        card.set_status("DISPONÍVEL", "Painel fechado explicitamente.")
        record_runtime_event(
            "panel_runtime_closed",
            workspace_id=self.workspace.id,
            panel_id=card.panel.id,
            runtime_id=runtime_id,
            reason="user_requested",
        )

    def _wire_panel_input(self, card: PanelCard, workspace_id: str) -> None:
        widgets = (card.frame, card.content_stack, card.runtime_host)
        for widget in widgets:
            widget.bind(
                "<Button-4>",
                lambda event, ws=workspace_id, panel=card.panel.id: self._route_scroll(
                    event, ws, panel
                ),
                add="+",
            )
            widget.bind(
                "<Button-5>",
                lambda event, ws=workspace_id, panel=card.panel.id: self._route_scroll(
                    event, ws, panel
                ),
                add="+",
            )
            widget.bind(
                "<MouseWheel>",
                lambda event, ws=workspace_id, panel=card.panel.id: self._route_scroll(
                    event, ws, panel
                ),
                add="+",
            )
            widget.bind(
                "<Button-1>",
                lambda _event, ws=workspace_id, panel=card.panel.id: self._focus_runtime(
                    ws, panel
                ),
                add="+",
            )
            widget.bind(
                "<Enter>",
                lambda _event, ws=workspace_id, panel=card.panel.id: self._focus_runtime(
                    ws, panel
                ),
                add="+",
            )

    def _poll_browser_pointer_focus(self) -> None:
        if self._closed:
            return
        controller = self.runtime_registry.get("browser")
        engine = getattr(controller, "engine", None)
        runtime_id = (
            engine.focus_under_pointer()
            if engine is not None and hasattr(engine, "focus_under_pointer")
            else None
        )
        if runtime_id != self._pointer_focus_runtime_id:
            record_runtime_event(
                "browser_pointer_focus_changed",
                previous_runtime_id=self._pointer_focus_runtime_id,
                runtime_id=runtime_id,
                active_workspace_id=self._displayed_workspace_id,
            )
            self._pointer_focus_runtime_id = runtime_id
        self.root.after(80, self._poll_browser_pointer_focus)

    def _route_scroll(
        self,
        event: tk.Event[tk.Misc],
        workspace_id: str,
        panel_id: str,
    ) -> str | None:
        state = self._workspace_views.get(workspace_id)
        runtime_id = state.runtime_ids.get(panel_id) if state is not None else None
        card = state.cards_by_id.get(panel_id) if state is not None else None
        if runtime_id is None or card is None or card.panel.adapter_name != "browser":
            return None
        controller = self.runtime_registry.get("browser")
        engine = getattr(controller, "engine", None)
        if engine is None or not engine.has_session(runtime_id):
            return None
        button_number = int(getattr(event, "num", 0) or 0)
        delta = int(getattr(event, "delta", 0) or 0)
        if button_number == 4:
            steps = 1
        elif button_number == 5:
            steps = -1
        elif delta:
            steps = max(-12, min(12, int(delta / 120) or (1 if delta > 0 else -1)))
        else:
            return None
        record_runtime_event(
            "mouse_wheel_received",
            workspace_id=workspace_id,
            panel_id=panel_id,
            runtime_id=runtime_id,
            steps=steps,
            pointer_x=getattr(event, "x_root", None),
            pointer_y=getattr(event, "y_root", None),
        )
        delivered = bool(engine.scroll(runtime_id, steps))
        record_runtime_event(
            "mouse_wheel_delivered",
            workspace_id=workspace_id,
            panel_id=panel_id,
            runtime_id=runtime_id,
            steps=steps,
            delivered=delivered,
        )
        return "break" if delivered else None

    def _focus_runtime(self, workspace_id: str, panel_id: str) -> None:
        state = self._workspace_views.get(workspace_id)
        runtime_id = state.runtime_ids.get(panel_id) if state is not None else None
        card = state.cards_by_id.get(panel_id) if state is not None else None
        if runtime_id is None or card is None or card.panel.adapter_name != "browser":
            return
        controller = self.runtime_registry.get("browser")
        engine = getattr(controller, "engine", None)
        focused = bool(engine.focus(runtime_id)) if engine is not None else False
        record_runtime_event(
            "browser_focus_forwarded",
            workspace_id=workspace_id,
            panel_id=panel_id,
            runtime_id=runtime_id,
            focused=focused,
        )


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    """Start the live-workspace RC4 candidate with full runtime provenance."""

    log_path = _configure_logging()
    provenance_path = write_runtime_snapshot(
        module_name="triview_workspace.gui",
        backend_name=LIVE_BROWSER_BACKEND_NAME,
    )
    record_runtime_event(
        "application_starting",
        log_path=str(log_path),
        provenance_path=str(provenance_path),
        backend=LIVE_BROWSER_BACKEND_NAME,
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
            backend=LIVE_BROWSER_BACKEND_NAME,
            active_workspace_id=catalog.active_workspace_id,
        )
        root.mainloop()
        record_runtime_event("application_stopped", reason="mainloop_returned")
        return 0
    except Exception as exc:  # noqa: BLE001
        logging.exception("Unable to start live-workspace TriView RC4")
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
