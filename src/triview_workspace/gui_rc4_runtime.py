"""Runtime hardening for the approved RC4 interface."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path

from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.engines.terminal_embedded import build_embedded_terminal_controller
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


def deferred_menu_action(
    root: tk.Misc,
    menu: tk.Menu,
    command: Callable[[], object],
    *,
    delay_ms: int = 120,
) -> Callable[[], None]:
    """Close the Tk menu grab before running capture, recording or panel actions."""

    def invoke() -> None:
        try:
            menu.unpost()
        except tk.TclError:
            pass
        try:
            menu.grab_release()
        except tk.TclError:
            pass
        root.update_idletasks()
        root.after(max(1, int(delay_ms)), command)

    return invoke


class WorkspaceWindow(RC4WorkspaceWindow):
    """Dispose stale menus and keep terminal sessions inside their panel hosts."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        super().__init__(root, repository, session_engine)
        self.runtime_registry.register(build_embedded_terminal_controller())
        self._configure_panel_states()

    def _load_workspace_view(self, message: str) -> None:
        for menu in self._panel_menus.values():
            try:
                menu.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._panel_menus.clear()
        super()._load_workspace_view(message)

    def _menu_action(
        self,
        menu: tk.Menu,
        command: Callable[[], object],
    ) -> Callable[[], None]:
        return deferred_menu_action(self.root, menu, command)

    def _show_panel_menu(self, card: PanelCard) -> None:
        """Open a panel menu whose actions run only after the menu disappears."""

        menu = self._panel_menus[card.panel.id]
        menu.delete(0, "end")
        menu.add_command(
            label="Abrir / reabrir",
            command=self._menu_action(menu, card.open_button.invoke),
        )
        menu.add_command(
            label="Abrir em janela externa",
            command=self._menu_action(menu, lambda: self._open_external(card)),
        )
        menu.add_separator()

        capture = self._find_button(card.frame, "Print")
        capture_available = capture is not None and str(capture.cget("state")) == "normal"
        menu.add_command(
            label="Capturar tela",
            command=self._menu_action(menu, capture.invoke) if capture is not None else None,
            state="normal" if capture_available else "disabled",
        )

        record = self._find_button(card.frame, "Parar") or self._find_button(
            card.frame,
            "Gravar",
        )
        record_available = record is not None and str(record.cget("state")) == "normal"
        record_label = (
            "Parar gravação"
            if record is not None and record.cget("text") == "Parar"
            else "Iniciar gravação"
        )
        menu.add_command(
            label=record_label,
            command=self._menu_action(menu, record.invoke) if record is not None else None,
            state="normal" if record_available else "disabled",
        )
        menu.add_separator()
        menu.add_command(
            label="Foco",
            command=self._menu_action(menu, lambda: self._toggle_focus(card.panel.id)),
        )
        menu.add_command(
            label="Fechar painel",
            command=self._menu_action(menu, lambda: self._close_panel(card)),
        )

        button = menu._triview_button  # type: ignore[attr-defined]
        menu.tk_popup(
            button.winfo_rootx(),
            button.winfo_rooty() + button.winfo_height(),
        )


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
        print(f"TriView Workspace não pôde abrir: {exc}\nLog: {log_path}")
        return 1


__all__ = [
    "APP_TITLE",
    "DEFAULT_WORKSPACE",
    "PanelCard",
    "PanelEditorDialog",
    "WorkspaceWindow",
    "deferred_menu_action",
    "global_bar_height",
    "main",
    "panel_header_height",
]
