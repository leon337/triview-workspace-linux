"""Operational-session extension of the advanced-layout workspace shell."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from triview_workspace.engines.runtime_state import (
    RecoveryPlan,
    RuntimeStateRepository,
    SessionRecoveryEngine,
)
from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_layouts import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as LayoutWorkspaceWindow,
    _configure_logging,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle


class WorkspaceWindow(LayoutWorkspaceWindow):
    """Persist open-panel intent and offer explicit session restoration."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
        runtime_state_repository: RuntimeStateRepository | None = None,
    ) -> None:
        self.runtime_state_repository = runtime_state_repository or RuntimeStateRepository()
        previous_snapshot = self.runtime_state_repository.load_or_recover()
        self.recovery_engine: SessionRecoveryEngine | None = None
        self._runtime_signature: tuple[object, ...] | None = None
        super().__init__(root, repository, session_engine)

        self.recovery_engine = SessionRecoveryEngine(
            self.runtime_state_repository,
            previous_snapshot,
        )
        plan = self.recovery_engine.recovery_plan(self.workspace)
        self.recovery_engine.begin(self.workspace)
        self._runtime_signature = self._signature({})
        self._replace_engine_badge(root)
        root.after(500, self._periodic_runtime_sync)
        if self.runtime_state_repository.last_recovery_message:
            root.after(250, self._show_runtime_state_warning)
        if plan.has_sessions:
            root.after(350, lambda: self._offer_restore(plan))

    def _load_workspace_view(self, message: str) -> None:
        if self.recovery_engine is not None:
            self._sync_runtime_state(force=True)
        super()._load_workspace_view(message)
        if self.recovery_engine is not None:
            self.recovery_engine.begin(self.workspace)
            self._runtime_signature = self._signature({})

    def _periodic_runtime_sync(self) -> None:
        if self._closed:
            return
        self._sync_runtime_state()
        self.root.after(2000, self._periodic_runtime_sync)

    def _sync_runtime_state(self, *, force: bool = False) -> None:
        if self.recovery_engine is None:
            return
        statuses = self._runtime_statuses()
        signature = self._signature(statuses)
        if not force and signature == self._runtime_signature:
            return
        self.recovery_engine.sync(self.workspace, statuses, clean_shutdown=False)
        self._runtime_signature = signature

    def _runtime_statuses(self) -> dict[str, tuple[str, bool, bool]]:
        statuses: dict[str, tuple[str, bool, bool]] = {}
        for card in self.cards:
            controller = self.runtime_registry.get(card.panel.adapter_name)
            if controller is None or not controller.has_session(card.panel.id):
                continue
            embedded, external = self._session_mode(controller, card.panel.id)
            statuses[card.panel.id] = (
                card.panel.adapter_name,
                embedded,
                external,
            )
        return statuses

    @staticmethod
    def _session_mode(controller: object, panel_id: str) -> tuple[bool, bool]:
        if getattr(controller, "adapter_name", "") == "browser":
            return True, False
        engine = getattr(controller, "engine", None)
        if engine is None:
            return False, True
        session = None
        session_reader = getattr(engine, "session", None)
        if callable(session_reader):
            session = session_reader(panel_id)
        if session is None:
            sessions = getattr(engine, "_sessions", None)
            if isinstance(sessions, dict):
                session = sessions.get(panel_id)
        if session is None:
            application_engine = getattr(engine, "application_engine", None)
            nested_reader = getattr(application_engine, "session", None)
            if callable(nested_reader):
                session = nested_reader(panel_id)
        return (
            bool(getattr(session, "embedded", False)),
            bool(getattr(session, "external", session is not None)),
        )

    def _signature(
        self,
        statuses: dict[str, tuple[str, bool, bool]],
    ) -> tuple[object, ...]:
        return (
            self.workspace.id,
            self.workspace.layout_id,
            tuple(sorted((panel_id, *state) for panel_id, state in statuses.items())),
        )

    def _offer_restore(self, plan: RecoveryPlan) -> None:
        if self._closed or plan.workspace_id != self.workspace.id:
            return
        shutdown = (
            "encerrada corretamente"
            if plan.previous_clean_shutdown
            else "interrompida sem encerramento completo"
        )
        panel_names = [
            self.cards_by_id[panel_id].panel.title
            for panel_id in plan.panel_ids
            if panel_id in self.cards_by_id
        ]
        if not panel_names:
            return
        confirmed = messagebox.askyesno(
            "Restaurar sessão anterior",
            "A sessão anterior foi "
            f"{shutdown}.\n\nPainéis disponíveis para restauração:\n- "
            + "\n- ".join(panel_names)
            + "\n\nAbrir esses painéis novamente?",
            parent=self.root,
        )
        if not confirmed:
            self.status_text.set("Restauração da sessão anterior ignorada")
            return
        delay = 0
        for panel_id in plan.panel_ids:
            card = self.cards_by_id.get(panel_id)
            if card is None:
                continue
            self.root.after(
                delay,
                lambda item=card: self._open_panel(item.panel, item),
            )
            delay += 350
        self.status_text.set("Restauração explícita da sessão iniciada")

    def _show_runtime_state_warning(self) -> None:
        message = self.runtime_state_repository.last_recovery_message
        if message:
            messagebox.showwarning(
                "Estado operacional recuperado",
                message,
                parent=self.root,
            )

    @staticmethod
    def _replace_engine_badge(widget: tk.Misc) -> None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Label) and str(child.cget("text")).startswith(
                ("LAYOUT ENGINE", "PLUGIN ENGINE", "RECORDING ENGINE")
            ):
                child.configure(text="SESSION ENGINE 0.11.0")
            WorkspaceWindow._replace_engine_badge(child)

    def _close(self) -> None:
        if self._closed:
            return
        statuses = self._runtime_statuses()
        if self.recovery_engine is not None:
            self.recovery_engine.finish(self.workspace, statuses)
        super()._close()


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    log_path = _configure_logging()
    try:
        seed_workspace, seed_layout = load_workspace_bundle(DEFAULT_WORKSPACE)
        repository = WorkspaceRepository(data_file)
        catalog = repository.load_or_bootstrap(seed_workspace, seed_layout)
        if workspace_path is not None:
            workspace, layout = load_workspace_bundle(workspace_path)
            catalog = repository.save_workspace(catalog, workspace, layout, make_active=True)
        session_engine = WorkspaceSessionEngine(repository, catalog)
        root = tk.Tk()
        WorkspaceWindow(root, repository, session_engine)
        root.mainloop()
        return 0
    except Exception as exc:  # noqa: BLE001
        try:
            messagebox.showerror(
                APP_TITLE,
                f"Não foi possível abrir a interface.\n\n{exc}\n\nLog: {log_path}",
            )
        except Exception:  # noqa: BLE001
            pass
        print(f"TriView Workspace não pôde abrir: {exc}\nLog: {log_path}")
        return 1


__all__ = [
    "APP_TITLE",
    "DEFAULT_WORKSPACE",
    "PanelCard",
    "PanelEditorDialog",
    "WorkspaceWindow",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
