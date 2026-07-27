"""Workspace-first presentation with wide panels and compact application chrome."""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox

from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_focus import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as FocusWorkspaceWindow,
    _configure_logging,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle


@dataclass(frozen=True)
class WideRect:
    """Pixel rectangle used by the workspace-first grid."""

    x: int
    y: int
    width: int
    height: int


def calculate_wide_grid(
    panel_count: int,
    viewport_width: int,
    viewport_height: int,
    *,
    padding: int = 8,
    gap: int = 10,
) -> tuple[WideRect, ...]:
    """Fill the viewport with useful panels instead of narrow phone-shaped cards."""

    if panel_count < 0:
        raise ValueError("panel_count must be zero or greater")
    if viewport_width <= 0 or viewport_height <= 0:
        raise ValueError("viewport dimensions must be greater than zero")
    if padding < 0 or gap < 0:
        raise ValueError("padding and gap must be zero or greater")
    if panel_count == 0:
        return ()

    columns = panel_count if panel_count <= 3 else math.ceil(math.sqrt(panel_count))
    rows = math.ceil(panel_count / columns)

    usable_width = max(1, viewport_width - padding * 2 - gap * (columns - 1))
    usable_height = max(1, viewport_height - padding * 2 - gap * (rows - 1))
    base_width = max(1, usable_width // columns)
    base_height = max(1, usable_height // rows)
    right_edge = max(padding + 1, viewport_width - padding)
    bottom_edge = max(padding + 1, viewport_height - padding)

    rects: list[WideRect] = []
    for index in range(panel_count):
        row = index // columns
        column = index % columns
        x = padding + column * (base_width + gap)
        y = padding + row * (base_height + gap)
        width = right_edge - x if column == columns - 1 else base_width
        height = bottom_edge - y if row == rows - 1 else base_height
        rects.append(WideRect(x, y, max(1, width), max(1, height)))
    return tuple(rects)


class WorkspaceWindow(FocusWorkspaceWindow):
    """Prioritize live content area while preserving focus and dual-panel modes."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self._wide_padding = 8
        self._wide_gap = 10
        self._fullscreen = False
        super().__init__(root, repository, session_engine)
        self.set_product_stage("WIDE WORKSPACE")
        self.status_text.set(
            "Workspace amplo ativo: painéis ocupam a área útil; F11 alterna tela cheia"
        )
        root.bind("<F11>", self._toggle_fullscreen, add="+")
        root.after_idle(self._maximize_window)
        root.after_idle(self._apply_compact_chrome)
        root.after_idle(self._render_layout)

    def _load_workspace_view(self, message: str) -> None:
        super()._load_workspace_view(message)
        self._apply_compact_chrome()
        self.root.after_idle(self._render_layout)

    def _apply_compact_chrome(self) -> None:
        """Return vertical space to the embedded applications."""

        if not hasattr(self, "header"):
            return

        self.header.configure(height=92)
        for child in self.header.winfo_children():
            info = child.grid_info()
            if not info:
                continue
            row = int(info.get("row", 0))
            child.grid_configure(pady=(6, 2) if row == 0 else (2, 6))

        for child in self.root.pack_slaves():
            info = child.pack_info()
            if info.get("side") == "bottom":
                try:
                    child.configure(height=24)
                except tk.TclError:
                    pass

        for card in self.cards:
            parts = card.frame.winfo_children()
            if len(parts) < 3:
                continue
            header, body, footer = parts[0], parts[1], parts[2]
            header.configure(height=44)
            footer.configure(height=40)

            header_children = header.pack_slaves()
            if header_children:
                icon = header_children[0]
                try:
                    icon.configure(width=30, height=30)
                    icon.pack_configure(padx=(8, 7), pady=6)
                except tk.TclError:
                    pass
            if len(header_children) >= 2:
                header_children[1].pack_configure(pady=5)
            for widget in header_children[2:]:
                widget.pack_configure(padx=(0, 7))

            for widget in body.winfo_children():
                if widget is not card.content_stack:
                    widget.pack_forget()
            if card.content_stack.winfo_manager():
                card.content_stack.pack_configure(padx=4, pady=4)
            else:
                card.content_stack.pack(fill="both", expand=True, padx=4, pady=4)

            for widget in footer.pack_slaves():
                info = widget.pack_info()
                if info.get("side") == "left":
                    widget.pack_configure(pady=6)

    def _render_layout(self) -> None:
        if self._closed:
            return
        if self._view_mode != "all":
            super()._render_layout()
            return

        self._resize_job = None
        if hasattr(self, "_splitter"):
            self._splitter.place_forget()

        panel_ids = tuple(card.panel.id for card in self.cards)
        self._visible_panel_ids = set(panel_ids)
        rects = calculate_wide_grid(
            len(self.cards),
            max(1, self.content.winfo_width()),
            max(1, self.content.winfo_height()),
            padding=self._wide_padding,
            gap=self._wide_gap,
        )
        for card, rect in zip(self.cards, rects, strict=True):
            card.place(rect.x, rect.y, rect.width, rect.height)

        if rects:
            average_width = sum(rect.width for rect in rects) // len(rects)
            average_height = sum(rect.height for rect in rects) // len(rects)
            self.metrics_text.set(
                f"{len(rects)} PAINÉIS · AMPLO · ~{average_width}×{average_height}"
            )
        else:
            self.metrics_text.set("0 PAINÉIS")
        self.status_text.set("Modo amplo: conteúdo priorizado e molduras reduzidas")
        self._refresh_focus_buttons()
        self.root.after_idle(self._resize_runtimes)

    def _maximize_window(self) -> None:
        try:
            self.root.attributes("-zoomed", True)
        except tk.TclError:
            try:
                self.root.state("zoomed")
            except tk.TclError:
                return

    def _toggle_fullscreen(self, _event: tk.Event | None = None) -> str:
        self._fullscreen = not self._fullscreen
        try:
            self.root.attributes("-fullscreen", self._fullscreen)
        except tk.TclError:
            self._fullscreen = False
        return "break"


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
    "WideRect",
    "WorkspaceWindow",
    "calculate_wide_grid",
    "main",
]
