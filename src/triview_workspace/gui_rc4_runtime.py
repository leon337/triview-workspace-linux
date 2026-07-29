"""Runtime hardening for the approved RC4 interface."""

from __future__ import annotations

import re
import threading
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
from triview_workspace.ui_design import (
    FONT_FAMILY,
    MONO_FONT_FAMILY,
    PALETTE,
    button_colors,
)


WorkArea = tuple[int, int, int, int]
PanelBound = tuple[int, int]
EMERGENCY_SHORTCUTS = ("<Control-Alt-q>", "<Control-Shift-Escape>")


def proportional_panel_bounds(total_width: int, panel_count: int) -> tuple[PanelBound, ...]:
    """Divide the complete workspace width without outer gutters or lost pixels."""

    safe_width = max(1, int(total_width))
    safe_count = max(0, int(panel_count))
    if safe_count == 0:
        return ()
    edges = [round(index * safe_width / safe_count) for index in range(safe_count + 1)]
    return tuple(
        (edges[index], max(1, edges[index + 1] - edges[index]))
        for index in range(safe_count)
    )


def parse_work_area(
    output: str,
    fallback_width: int,
    fallback_height: int,
) -> WorkArea:
    """Parse the first EWMH work area for diagnostics and compatibility tests."""

    values = [int(value) for value in re.findall(r"-?\d+", output)]
    if len(values) >= 4 and values[2] > 0 and values[3] > 0:
        return values[0], values[1], values[2], values[3]
    return 0, 0, max(1, int(fallback_width)), max(1, int(fallback_height))


def release_menu_grab(menu: tk.Menu) -> None:
    """Best-effort release of a menu grab without hiding the original failure."""

    try:
        menu.grab_release()
    except (tk.TclError, AttributeError):
        pass


def safe_popup_menu(menu: tk.Menu, x: int, y: int) -> None:
    """Post a Tk popup and guarantee that its global input grab is released."""

    try:
        menu.tk_popup(int(x), int(y))
    finally:
        release_menu_grab(menu)


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
        except (tk.TclError, AttributeError):
            pass
        release_menu_grab(menu)
        root.after(max(1, int(delay_ms)), command)

    return invoke


def request_managed_maximize(root: tk.Misc) -> bool:
    """Ask the window manager to maximize the normal managed window."""

    try:
        root.wm_attributes("-zoomed", True)
        return True
    except (tk.TclError, TypeError, AttributeError):
        pass
    try:
        root.state("zoomed")
        return True
    except (tk.TclError, TypeError, AttributeError):
        return False


class WorkspaceWindow(RC4WorkspaceWindow):
    """Use a Cinnamon/Muffin-managed window and embedded-only terminals."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self._compact_in_progress = False
        self._last_compact_root_size: tuple[int, int] | None = None
        self._last_compact_panel_sizes: dict[str, tuple[int, int]] = {}
        super().__init__(root, repository, session_engine)
        self.runtime_registry.register(build_embedded_terminal_controller())
        self._configure_panel_states()
        self._install_managed_window_contract()
        root.after_idle(self._request_managed_maximize)
        self.status_text.set(
            "RC4 gerenciada pelo Cinnamon/Muffin · saída de emergência: Ctrl+Alt+Q"
        )

    def _load_workspace_view(self, message: str) -> None:
        for menu in self._panel_menus.values():
            try:
                menu.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._panel_menus.clear()
        self._last_compact_panel_sizes.clear()
        super()._load_workspace_view(message)

    def _render_layout(self) -> None:
        """Make all three panels consume the complete content workspace."""

        if getattr(self, "_view_mode", "all") != "all":
            super()._render_layout()
            return
        if self._closed:
            return

        self._resize_job = None
        width = max(1, self.content.winfo_width())
        height = max(1, self.content.winfo_height())
        cards = list(self.cards)
        panel_ids = tuple(card.panel.id for card in cards)
        self._visible_panel_ids = set(panel_ids)

        if hasattr(self, "_splitter"):
            self._splitter.place_forget()

        for card, (x, panel_width) in zip(
            cards,
            proportional_panel_bounds(width, len(cards)),
            strict=False,
        ):
            card.place(x, 0, panel_width, height)

        self.metrics_text.set(f"{len(cards)} PAINÉIS · 100% WORKSPACE · {width}×{height}")
        self._refresh_focus_buttons()
        self._queue_compact_chrome(20)
        self.root.after_idle(self._resize_runtimes)

    def _schedule_compact_chrome(self, event: tk.Event[tk.Misc]) -> None:
        """Debounce root geometry changes without forcing synchronous Tk layout."""

        if event.widget is not self.root or self._closed:
            return
        self._queue_compact_chrome(60)

    def _queue_compact_chrome(self, delay_ms: int) -> None:
        if self._closed:
            return
        if self._compact_job is not None:
            try:
                self.root.after_cancel(self._compact_job)
            except tk.TclError:
                pass
        self._compact_job = self.root.after(
            max(0, int(delay_ms)),
            self._apply_compact_chrome,
        )

    def _apply_compact_chrome(self) -> None:
        """Apply compact chrome once per stable geometry, without update_idletasks."""

        self._compact_job = None
        if self._closed or self._compact_in_progress:
            return

        self._compact_in_progress = True
        try:
            root_size = (self.root.winfo_width(), self.root.winfo_height())
            if root_size != self._last_compact_root_size:
                self._apply_header_layout()
                self._last_compact_root_size = root_size

            active_ids: set[str] = set()
            for card in self.cards:
                panel_id = card.panel.id
                active_ids.add(panel_id)
                panel_size = (card.frame.winfo_width(), card.frame.winfo_height())
                if self._last_compact_panel_sizes.get(panel_id) == panel_size:
                    continue
                self._compact_panel(card)
                self._last_compact_panel_sizes[panel_id] = panel_size

            stale_ids = set(self._last_compact_panel_sizes) - active_ids
            for panel_id in stale_ids:
                self._last_compact_panel_sizes.pop(panel_id, None)
        finally:
            self._compact_in_progress = False

    def _compact_panel(self, card: PanelCard) -> None:
        """Compact one panel without synchronously flushing Tk geometry events."""

        children = card.frame.winfo_children()
        if len(children) < 3:
            return
        header, body, footer = children[0], children[1], children[-1]
        height = panel_header_height(card.frame.winfo_height())
        header.configure(height=height)
        header.pack_propagate(False)

        header_children = header.winfo_children()
        if header_children:
            icon_box = header_children[0]
            icon_size = max(18, round(height * 0.72))
            icon_box.configure(width=icon_size, height=icon_size)
            icon_box.pack_configure(
                padx=(5, 5),
                pady=max(1, (height - icon_size) // 2),
            )
        if len(header_children) > 1:
            identity = header_children[1]
            identity.pack_configure(pady=1)
            labels = identity.winfo_children()
            if labels:
                labels[0].configure(font=(FONT_FAMILY, 8, "bold"))
            if len(labels) > 1:
                labels[1].pack_forget()
        card.badge.configure(font=(FONT_FAMILY, 6, "bold"), padx=5, pady=1)
        card.badge.pack_configure(padx=4)

        body_children = body.winfo_children()
        if body_children:
            body_children[0].pack_forget()
        card.content_stack.pack_configure(padx=0, pady=0)
        footer.pack_forget()
        self._ensure_panel_menu(card, header)

    def _install_managed_window_contract(self) -> None:
        """Keep the native title bar and delegate window lifecycle to Muffin."""

        self.root.title(APP_TITLE)
        self.root.resizable(True, True)
        try:
            self.root.wm_attributes("-topmost", False)
        except (tk.TclError, TypeError, AttributeError):
            pass
        for shortcut in EMERGENCY_SHORTCUTS:
            self.root.bind_all(shortcut, self._emergency_exit, add="+")

    def _request_managed_maximize(self) -> None:
        if self._closed:
            return
        request_managed_maximize(self.root)

    def _release_popup_grabs(self) -> None:
        menus = list(self._panel_menus.values())
        if hasattr(self, "_global_menu"):
            menus.append(self._global_menu)
        for menu in menus:
            try:
                menu.unpost()
            except (tk.TclError, AttributeError):
                pass
            release_menu_grab(menu)
        try:
            self.root.grab_release()
        except (tk.TclError, AttributeError):
            pass

    def _close(self) -> None:
        """Destroy the managed window before best-effort runtime cleanup."""

        if self._closed:
            return
        self._closed = True
        self._release_popup_grabs()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        try:
            self.runtime_registry.close_all()
        except Exception:  # noqa: BLE001
            pass

    def _emergency_exit(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        """Release the desktop immediately and clean runtimes in a daemon thread."""

        if self._closed:
            return "break"
        self._closed = True
        self._release_popup_grabs()
        threading.Thread(
            target=self.runtime_registry.close_all,
            name="triview-emergency-cleanup",
            daemon=True,
        ).start()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        return "break"

    def _menu_action(
        self,
        menu: tk.Menu,
        command: Callable[[], object],
    ) -> Callable[[], None]:
        return deferred_menu_action(self.root, menu, command)

    def _show_global_menu(self) -> None:
        """Open the global menu and always release its grab."""

        self._rebuild_global_menu()
        x = self._global_menu_button.winfo_rootx()
        y = self._global_menu_button.winfo_rooty() + self._global_menu_button.winfo_height()
        safe_popup_menu(self._global_menu, x, y)

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
