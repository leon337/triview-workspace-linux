"""Plugin-enabled extension of the recording workspace shell."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog

from triview_workspace.engines import (
    ApplicationEngine,
    PluginEngine,
    PluginEngineError,
    PluginPanelAdapter,
    PluginRuntimeController,
    WorkspaceSessionEngine,
    X11ApplicationBackend,
)
from triview_workspace.gui_recording import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as RecordingWorkspaceWindow,
    _configure_logging,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle


class WorkspaceWindow(RecordingWorkspaceWindow):
    """Register declarative plugins and expose explicit activation controls."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self.plugin_engine = PluginEngine(ApplicationEngine(X11ApplicationBackend()))
        super().__init__(root, repository, session_engine)
        self.registry.register(PluginPanelAdapter())
        self.runtime_registry.register(PluginRuntimeController(self.plugin_engine))
        self.register_header_action(
            "plugins",
            "Plugins",
            self._manage_plugins,
            order=30,
        )
        self.set_product_stage("PLUGINS")
        self._load_workspace_view("Plugin Engine carregado")

    def _add_plugin_button(self, _root: tk.Tk) -> None:
        """Compatibility wrapper for older callers."""

        self.register_header_action(
            "plugins",
            "Plugins",
            self._manage_plugins,
            order=30,
        )

    def _manage_plugins(self) -> None:
        diagnostics = self.plugin_engine.reload()
        if diagnostics:
            lines = [
                f"{item.plugin_id}: "
                f"{'ATIVO' if item.enabled else 'DESATIVADO' if item.valid else 'INVÁLIDO'} — "
                f"{item.message}"
                for item in diagnostics
            ]
        else:
            lines = [f"Nenhum plugin encontrado em {self.plugin_engine.root}"]
        plugin_id = simpledialog.askstring(
            "Gerenciar plugins",
            "\n".join(lines)
            + "\n\nDigite o ID de um plugin válido para ativar ou desativar."
            + "\nDeixe vazio para apenas fechar:",
            parent=self.root,
        )
        if not plugin_id:
            return
        plugin_id = plugin_id.strip()
        try:
            if plugin_id in self.plugin_engine.enabled_ids():
                self.plugin_engine.disable(plugin_id)
                action = "desativado"
            else:
                self.plugin_engine.enable(plugin_id)
                action = "ativado"
        except PluginEngineError as exc:
            messagebox.showerror("Plugin rejeitado", str(exc), parent=self.root)
            return
        self._load_workspace_view(f"Plugin {plugin_id} {action}")
        messagebox.showinfo(
            "Plugins",
            f"Plugin '{plugin_id}' {action}.",
            parent=self.root,
        )

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
