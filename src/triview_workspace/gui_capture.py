"""Capture-enabled extension of the PDF workspace shell."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from triview_workspace.engines import CaptureEngine, CaptureEngineError, WorkspaceSessionEngine
from triview_workspace.gui_pdf import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as PdfWorkspaceWindow,
    _configure_logging,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle


class WorkspaceWindow(PdfWorkspaceWindow):
    """Enable the Print action for every rendered panel."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self.capture_engine = CaptureEngine()
        self._capture_results: queue.SimpleQueue[
            tuple[str, str | None, str | None, int]
        ] = queue.SimpleQueue()
        super().__init__(root, repository, session_engine)
        self._replace_engine_badge(root)
        root.after(100, self._drain_capture_results)

    def _load_workspace_view(self, message: str) -> None:
        super()._load_workspace_view(message)
        self._wire_capture_buttons()

    def _wire_capture_buttons(self) -> None:
        report = self.capture_engine.availability()
        for card in self.cards:
            button = self._find_button(card.frame, "Print")
            if button is None:
                continue
            button.configure(
                state="normal" if report.available else "disabled",
                command=lambda item=card, control=button: self._capture_panel(item, control),
            )
            if not report.available:
                button.configure(disabledforeground="#64748b")
        if not report.available:
            self.status_text.set(report.reason)

    def _capture_panel(self, card: PanelCard, button: tk.Button) -> None:
        if self._closed:
            return
        report = self.capture_engine.availability()
        if not report.available:
            messagebox.showerror("Captura indisponível", report.reason, parent=self.root)
            return
        card.frame.update_idletasks()
        window_id = int(card.frame.winfo_id())
        generation = self._generation
        button.configure(state="disabled", text="Capturando…")
        self.status_text.set(f"Capturando o painel {card.panel.title}…")

        def capture() -> None:
            try:
                result = self.capture_engine.capture(
                    self.workspace.id,
                    card.panel.id,
                    card.panel.title,
                    window_id,
                )
            except Exception as exc:  # noqa: BLE001
                self._capture_results.put((card.panel.id, None, str(exc), generation))
                return
            self._capture_results.put((card.panel.id, result.path, None, generation))

        threading.Thread(
            target=capture,
            name=f"triview-capture-{card.panel.id}",
            daemon=True,
        ).start()

    def _drain_capture_results(self) -> None:
        if self._closed:
            return
        while True:
            try:
                panel_id, path, error, generation = self._capture_results.get_nowait()
            except queue.Empty:
                break
            if generation != self._generation or panel_id not in self.cards_by_id:
                continue
            card = self.cards_by_id[panel_id]
            button = self._find_button(card.frame, "Capturando…") or self._find_button(
                card.frame, "Print"
            )
            if button is not None:
                button.configure(state="normal", text="Print")
            if error:
                self.status_text.set(f"Falha ao capturar {card.panel.title}: {error}")
                messagebox.showerror("Falha na captura", error, parent=self.root)
            else:
                self.status_text.set(f"Captura salva: {path}")
                messagebox.showinfo(
                    "Captura concluída",
                    f"Painel: {card.panel.title}\n\nArquivo:\n{path}",
                    parent=self.root,
                )
        self.root.after(100, self._drain_capture_results)

    @staticmethod
    def _find_button(parent: tk.Misc, text: str) -> tk.Button | None:
        for child in parent.winfo_children():
            if isinstance(child, tk.Button) and child.cget("text") == text:
                return child
            found = WorkspaceWindow._find_button(child, text)
            if found is not None:
                return found
        return None

    @staticmethod
    def _replace_engine_badge(widget: tk.Misc) -> None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Label) and str(child.cget("text")).startswith(
                ("PDF ENGINE", "TERMINAL ENGINE")
            ):
                child.configure(text="CAPTURE ENGINE 0.7.0")
            WorkspaceWindow._replace_engine_badge(child)


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
