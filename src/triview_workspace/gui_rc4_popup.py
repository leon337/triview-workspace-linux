"""Popup lifecycle hardening for the managed RC4 desktop shell."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable
from pathlib import Path

from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_rc4_runtime import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    EMERGENCY_SHORTCUTS,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as ManagedWorkspaceWindow,
    _configure_logging,
    deferred_menu_action,
    global_bar_height,
    panel_header_height,
    parse_work_area,
    proportional_panel_bounds,
    release_menu_grab,
    request_managed_maximize,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle

POPUP_WATCH_INTERVAL_MS = 50
POPUP_FAILSAFE_MS = 15_000


def _unpost_and_release(menu: tk.Menu) -> None:
    """Fail closed by hiding the popup and releasing any remaining grab."""

    try:
        menu.unpost()
    except (tk.TclError, AttributeError):
        pass
    release_menu_grab(menu)


def safe_popup_menu(
    menu: tk.Menu,
    x: int,
    y: int,
    *,
    watch_interval_ms: int = POPUP_WATCH_INTERVAL_MS,
    failsafe_ms: int = POPUP_FAILSAFE_MS,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Keep Tk's native outside-click dismissal and guarantee eventual grab release.

    ``tk_popup`` needs its grab while the menu is mapped so clicks outside the menu
    are routed back to Tk and dismiss it. Releasing that grab immediately leaves a
    visible orphan popup. This watchdog keeps the native behavior and releases the
    grab as soon as the popup is unmapped, with a bounded fail-safe timeout.
    """

    started_at = clock()
    interval = max(1, int(watch_interval_ms))
    timeout = max(1, int(failsafe_ms))

    def watch_popup() -> None:
        try:
            mapped = bool(menu.winfo_ismapped())
        except (tk.TclError, AttributeError):
            release_menu_grab(menu)
            return

        if not mapped:
            release_menu_grab(menu)
            return

        elapsed_ms = (clock() - started_at) * 1000
        if elapsed_ms >= timeout:
            _unpost_and_release(menu)
            return

        try:
            menu.after(interval, watch_popup)
        except (tk.TclError, AttributeError):
            _unpost_and_release(menu)

    try:
        menu.tk_popup(int(x), int(y))
    except Exception:
        release_menu_grab(menu)
        raise

    try:
        menu.after(interval, watch_popup)
    except (tk.TclError, AttributeError):
        _unpost_and_release(menu)


class WorkspaceWindow(ManagedWorkspaceWindow):
    """Use the corrected popup lifecycle on top of the managed RC4 window."""

    def _show_global_menu(self) -> None:
        self._rebuild_global_menu()
        x = self._global_menu_button.winfo_rootx()
        y = self._global_menu_button.winfo_rooty() + self._global_menu_button.winfo_height()
        safe_popup_menu(self._global_menu, x, y)

    def _show_panel_menu(self, card: PanelCard) -> None:
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
        safe_popup_menu(
            menu,
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
    "EMERGENCY_SHORTCUTS",
    "POPUP_FAILSAFE_MS",
    "POPUP_WATCH_INTERVAL_MS",
    "PanelCard",
    "PanelEditorDialog",
    "WorkspaceWindow",
    "deferred_menu_action",
    "global_bar_height",
    "main",
    "panel_header_height",
    "parse_work_area",
    "proportional_panel_bounds",
    "release_menu_grab",
    "request_managed_maximize",
    "safe_popup_menu",
]


if __name__ == "__main__":
    raise SystemExit(main())
