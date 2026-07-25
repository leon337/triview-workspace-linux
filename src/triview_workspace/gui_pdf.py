"""PDF-enabled extension of the generic workspace shell."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from triview_workspace.engines import PdfEngine, PdfPanelAdapter, PdfRuntimeController, WorkspaceSessionEngine
from triview_workspace.gui_shell import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as BaseWorkspaceWindow,
    _configure_logging,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle


class WorkspaceWindow(BaseWorkspaceWindow):
    """Add PDF adapter/controller without duplicating the base shell."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        super().__init__(root, repository, session_engine)
        self.registry.register(PdfPanelAdapter())
        self.runtime_registry.register(PdfRuntimeController(PdfEngine()))
        self._replace_engine_badge(root)
        self._load_workspace_view("PDF Engine carregado")

    @staticmethod
    def _replace_engine_badge(widget: tk.Misc) -> None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Label) and str(child.cget("text")).startswith(
                "TERMINAL ENGINE"
            ):
                child.configure(text="PDF ENGINE 0.6.0")
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
