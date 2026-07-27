"""Runtime hardening for the approved RC4 interface."""

from __future__ import annotations

import re
import subprocess
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
from triview_workspace.ui_design import MONO_FONT_FAMILY, PALETTE, button_colors


WorkArea = tuple[int, int, int, int]
PanelBound = tuple[int, int]


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
    """Parse the first EWMH work area and fall back to the physical screen size."""

    values = [int(value) for value in re.findall(r"-?\d+", output)]
    if len(values) >= 4 and values[2] > 0 and values[3] > 0:
        return values[0], values[1], values[2], values[3]
    return 0, 0, max(1, int(fallback_width)), max(1, int(fallback_height))


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
    """Use the complete workspace, borderless chrome and embedded-only terminals."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self._drag_offset: tuple[int, int] | None = None
        self._normal_geometry: str | None = None
        self._maximized = False
        self._restore_borderless_after_map = False
        root.overrideredirect(True)
        super().__init__(root, repository, session_engine)
        self.runtime_registry.register(build_embedded_terminal_controller())
        self._configure_panel_states()
        self._install_window_chrome()
        root.after_idle(self._maximize_to_work_area)

    def _load_workspace_view(self, message: str) -> None:
        for menu in self._panel_menus.values():
            try:
                menu.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._panel_menus.clear()
        super()._load_workspace_view(message)

    def _render_layout(self) -> None:
        """Make all three panels consume 100% of the 96% content workspace."""

        if getattr(self, "_view_mode", "all") != "all":
            super()._render_layout()
            return
        if self._closed:
            return

        self._resize_job = None
        self.content.update_idletasks()
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
        self._apply_compact_chrome()
        self.root.after_idle(self._resize_runtimes)

    def _install_window_chrome(self) -> None:
        """Replace the white desktop title bar with controls inside the global bar."""

        for widget in (
            self.extension_actions_frame,
            self.product_badge,
            self._global_menu_button,
        ):
            widget.pack_forget()

        self._window_controls = tk.Frame(self.header, background=PALETTE.surface)
        self._window_controls.pack(side="right", fill="y")
        self._window_buttons: dict[str, tk.Button] = {}
        for key, label, command, variant in (
            ("minimize", "─", self._minimize_window, "ghost"),
            ("maximize", "□", self._toggle_maximize, "ghost"),
            ("close", "×", self._close, "danger"),
        ):
            button = tk.Button(
                self._window_controls,
                text=label,
                command=command,
                relief="flat",
                bd=0,
                highlightthickness=0,
                font=(MONO_FONT_FAMILY, 10, "bold"),
                padx=9,
                pady=2,
                cursor="hand2",
                **button_colors(variant),
            )
            button.pack(side="left", fill="y")
            self._window_buttons[key] = button

        self.extension_actions_frame.pack(side="right", padx=(0, 2), fill="y")
        self.product_badge.pack(side="right", padx=(3, 5), pady=3)
        self._global_menu_button.pack(side="right", padx=(2, 2), pady=3)

        self.header.bind("<ButtonPress-1>", self._start_window_drag, add="+")
        self.header.bind("<B1-Motion>", self._drag_window, add="+")
        self.header.bind("<Double-Button-1>", lambda _event: self._toggle_maximize(), add="+")
        self.root.bind("<Map>", self._restore_borderless_on_map, add="+")

    def _work_area(self) -> WorkArea:
        fallback_width = self.root.winfo_screenwidth()
        fallback_height = self.root.winfo_screenheight()
        try:
            result = subprocess.run(
                ["xprop", "-root", "_NET_WORKAREA"],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return parse_work_area("", fallback_width, fallback_height)
        return parse_work_area(result.stdout, fallback_width, fallback_height)

    def _maximize_to_work_area(self) -> None:
        self.root.update_idletasks()
        x, y, width, height = self._work_area()
        if self._normal_geometry is None:
            normal_width = max(720, round(width * 0.84))
            normal_height = max(520, round(height * 0.84))
            normal_x = x + max(0, (width - normal_width) // 2)
            normal_y = y + max(0, (height - normal_height) // 2)
            self._normal_geometry = (
                f"{normal_width}x{normal_height}+{normal_x}+{normal_y}"
            )
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self._maximized = True
        self._window_buttons.get("maximize", tk.Button()).configure(text="❐")

    def _toggle_maximize(self) -> None:
        if self._maximized:
            if self._normal_geometry is not None:
                self.root.geometry(self._normal_geometry)
            self._maximized = False
            self._window_buttons["maximize"].configure(text="□")
            return
        self._normal_geometry = self.root.geometry()
        self._maximize_to_work_area()

    def _minimize_window(self) -> None:
        self._restore_borderless_after_map = True
        self.root.overrideredirect(False)
        self.root.iconify()

    def _restore_borderless_on_map(self, _event: tk.Event[tk.Misc]) -> None:
        if not self._restore_borderless_after_map:
            return
        self._restore_borderless_after_map = False
        self.root.after_idle(lambda: self.root.overrideredirect(True))

    def _start_window_drag(self, event: tk.Event[tk.Misc]) -> None:
        if self._maximized:
            self._drag_offset = None
            return
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )

    def _drag_window(self, event: tk.Event[tk.Misc]) -> None:
        if self._drag_offset is None or self._maximized:
            return
        offset_x, offset_y = self._drag_offset
        self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

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
    "parse_work_area",
    "proportional_panel_bounds",
]
