"""Runtime hardening for the approved RC4 interface."""

from __future__ import annotations

from pathlib import Path

from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_rc4 import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as RC4WorkspaceWindow,
    _configure_logging,
    global_bar_height,
    panel_header_height,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle


class WorkspaceWindow(RC4WorkspaceWindow):
    """Dispose stale Tk menus before rebuilding a workspace view."""

    def _load_workspace_view(self, message: str) -> None:
        for menu in self._panel_menus.values():
            try:
                menu.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._panel_menus.clear()
        super()._load_workspace_view(message)


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
        import tkinter as tk

        root = tk.Tk()
        WorkspaceWindow(root, repository, session_engine)
        root.mainloop()
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"TriView Workspace não pôde abrir: {exc}\nLog: {log_path}")
        return 1


__all__ = [
    "APP_TITLE",
    "DEFAULT_WORKSPACE",
    "PanelCard",
    "PanelEditorDialog",
    "WorkspaceWindow",
    "global_bar_height",
    "main",
    "panel_header_height",
]
