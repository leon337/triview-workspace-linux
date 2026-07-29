"""Recording-enabled extension of the capture workspace shell."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from triview_workspace.engines import RecordingEngine, WorkspaceSessionEngine
from triview_workspace.gui_capture import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as CaptureWorkspaceWindow,
    _configure_logging,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle


class WorkspaceWindow(CaptureWorkspaceWindow):
    """Enable start/stop recording for each panel."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self.recording_engine = RecordingEngine()
        self._recording_results: queue.SimpleQueue[
            tuple[str, str, str | None, str | None, int]
        ] = queue.SimpleQueue()
        super().__init__(root, repository, session_engine)
        self.set_product_stage("RECORDING")
        root.after(100, self._drain_recording_results)

    def _load_workspace_view(self, message: str) -> None:
        self.recording_engine.stop_all()
        super()._load_workspace_view(message)
        self._wire_recording_buttons()

    def _wire_recording_buttons(self) -> None:
        report = self.recording_engine.availability()
        for card in self.cards:
            button = self._find_button(card.frame, "Gravar")
            if button is None:
                continue
            button.configure(
                state="normal" if report.available else "disabled",
                command=lambda item=card, control=button: self._toggle_recording(
                    item,
                    control,
                ),
            )
        if not report.available:
            self.status_text.set(report.reason)

    def _toggle_recording(self, card: PanelCard, button: tk.Button) -> None:
        if self._closed:
            return
        if self.recording_engine.is_recording(card.panel.id):
            self._stop_recording(card, button)
        else:
            self._start_recording(card, button)

    def _start_recording(self, card: PanelCard, button: tk.Button) -> None:
        report = self.recording_engine.availability()
        if not report.available:
            messagebox.showerror("Gravação indisponível", report.reason, parent=self.root)
            return
        card.frame.update_idletasks()
        geometry = (
            int(card.frame.winfo_rootx()),
            int(card.frame.winfo_rooty()),
            max(1, int(card.frame.winfo_width())),
            max(1, int(card.frame.winfo_height())),
        )
        generation = self._generation
        button.configure(state="disabled", text="Iniciando…")

        def start() -> None:
            try:
                session = self.recording_engine.start(
                    self.workspace.id,
                    card.panel.id,
                    card.panel.title,
                    *geometry,
                )
            except Exception as exc:  # noqa: BLE001
                self._recording_results.put(
                    (card.panel.id, "error-start", None, str(exc), generation)
                )
                return
            self._recording_results.put(
                (
                    card.panel.id,
                    "started",
                    str(session.request.output_path),
                    None,
                    generation,
                )
            )

        threading.Thread(
            target=start,
            name=f"triview-record-start-{card.panel.id}",
            daemon=True,
        ).start()

    def _stop_recording(self, card: PanelCard, button: tk.Button) -> None:
        generation = self._generation
        button.configure(state="disabled", text="Finalizando…")

        def stop() -> None:
            try:
                result = self.recording_engine.stop(card.panel.id)
            except Exception as exc:  # noqa: BLE001
                self._recording_results.put(
                    (card.panel.id, "error-stop", None, str(exc), generation)
                )
                return
            self._recording_results.put(
                (card.panel.id, "stopped", result.path, None, generation)
            )

        threading.Thread(
            target=stop,
            name=f"triview-record-stop-{card.panel.id}",
            daemon=True,
        ).start()

    def _drain_recording_results(self) -> None:
        if self._closed:
            return
        while True:
            try:
                panel_id, state, path, error, generation = (
                    self._recording_results.get_nowait()
                )
            except queue.Empty:
                break
            if generation != self._generation or panel_id not in self.cards_by_id:
                continue
            card = self.cards_by_id[panel_id]
            button = (
                self._find_button(card.frame, "Iniciando…")
                or self._find_button(card.frame, "Finalizando…")
                or self._find_button(card.frame, "Parar")
                or self._find_button(card.frame, "Gravar")
            )
            if state == "started":
                if button is not None:
                    button.configure(state="normal", text="Parar")
                card.set_status(
                    "GRAVANDO",
                    f"Gravando somente o painel {card.panel.title}.",
                )
                self.status_text.set(f"Gravação iniciada: {path}")
            elif state == "stopped":
                if button is not None:
                    button.configure(state="normal", text="Gravar")
                card.set_status(
                    "GRAVADO",
                    f"Vídeo do painel salvo em {path}",
                )
                self.status_text.set(f"Gravação salva: {path}")
                messagebox.showinfo(
                    "Gravação concluída",
                    f"Painel: {card.panel.title}\n\nArquivo:\n{path}",
                    parent=self.root,
                )
            else:
                if button is not None:
                    button.configure(state="normal", text="Gravar")
                card.set_status("ERRO", error or "Falha desconhecida.")
                self.status_text.set(error or "Falha na gravação")
                messagebox.showerror(
                    "Falha na gravação",
                    error or "Falha desconhecida.",
                    parent=self.root,
                )
        self.root.after(100, self._drain_recording_results)

    @staticmethod
    def _replace_engine_badge(_widget: tk.Misc) -> None:
        """Deprecated: the product badge now has one explicit source."""

    def _close(self) -> None:
        self.recording_engine.stop_all()
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
