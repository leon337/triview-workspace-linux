"""Advanced-layout extension of the plugin workspace shell."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from triview_workspace.engines import (
    ResponsiveLayoutEngine,
    WorkspaceEngine,
    WorkspaceSessionEngine,
)
from triview_workspace.gui_plugins import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as PluginWorkspaceWindow,
    _configure_logging,
)
from triview_workspace.infrastructure import (
    WorkspaceRepository,
    WorkspaceStorageError,
    load_workspace_bundle,
)
from triview_workspace.layout_editor import LayoutEditorDialog


class WorkspaceWindow(PluginWorkspaceWindow):
    """Use responsive breakpoints and allow validated custom layouts."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        super().__init__(root, repository, session_engine)
        self.workspace_engine = WorkspaceEngine(ResponsiveLayoutEngine(), self.registry)
        self.register_header_action(
            "new-layout",
            "Novo layout",
            self._create_layout,
            order=20,
        )
        self.set_product_stage("LAYOUTS")
        self._load_workspace_view("Layout Engine avançado carregado")

    def _add_layout_button(self, _root: tk.Tk) -> None:
        """Compatibility wrapper for older callers."""

        self.register_header_action(
            "new-layout",
            "Novo layout",
            self._create_layout,
            order=20,
        )

    def _create_layout(self) -> None:
        dialog = LayoutEditorDialog(
            self.root,
            len(self.workspace.panels),
            {item.id for item in self.session_engine.catalog.layouts},
        )
        if dialog.result is None:
            return
        try:
            self.workspace, self.layout = self.session_engine.save_layout(
                dialog.result,
                select=True,
            )
        except (ValueError, WorkspaceStorageError) as exc:
            messagebox.showerror("Não foi possível salvar", str(exc), parent=self.root)
            return
        self._load_workspace_view("Novo layout salvo e selecionado")

    @staticmethod
    def _replace_engine_badge(_widget: tk.Misc) -> None:
        """Deprecated: the product badge now has one explicit source."""


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
