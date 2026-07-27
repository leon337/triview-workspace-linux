"""Workspace-first presentation with percentage-based panels and minimal chrome."""

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
class PercentageSlot:
    """Normalized panel area expressed as percentages of the useful viewport."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class WideRect:
    """Pixel rectangle produced only at the final Tkinter rendering boundary."""

    x: int
    y: int
    width: int
    height: int


def calculate_percentage_slots(
    panel_count: int,
    *,
    vertical_share: float = 0.96,
) -> tuple[PercentageSlot, ...]:
    """Describe the workspace using proportions, not fixed desktop dimensions."""

    if panel_count < 0:
        raise ValueError("panel_count must be zero or greater")
    if not 0 < vertical_share <= 1:
        raise ValueError("vertical_share must be greater than zero and at most one")
    if panel_count == 0:
        return ()

    columns = panel_count if panel_count <= 3 else math.ceil(math.sqrt(panel_count))
    rows = math.ceil(panel_count / columns)
    column_share = 1.0 / columns
    row_share = vertical_share / rows
    top_share = (1.0 - vertical_share) / 2.0

    return tuple(
        PercentageSlot(
            x=(index % columns) * column_share,
            y=top_share + (index // columns) * row_share,
            width=column_share,
            height=row_share,
        )
        for index in range(panel_count)
    )


def calculate_wide_grid(
    panel_count: int,
    viewport_width: int,
    viewport_height: int,
    *,
    vertical_share: float = 0.96,
) -> tuple[WideRect, ...]:
    """Convert the percentage contract to pixels only when Tkinter needs it."""

    if viewport_width <= 0 or viewport_height <= 0:
        raise ValueError("viewport dimensions must be greater than zero")

    slots = calculate_percentage_slots(panel_count, vertical_share=vertical_share)
    rects: list[WideRect] = []
    for slot in slots:
        left = round(slot.x * viewport_width)
        top = round(slot.y * viewport_height)
        right = round((slot.x + slot.width) * viewport_width)
        bottom = round((slot.y + slot.height) * viewport_height)
        rects.append(
            WideRect(
                x=left,
                y=top,
                width=max(1, right - left),
                height=max(1, bottom - top),
            )
        )
    return tuple(rects)


class WorkspaceWindow(FocusWorkspaceWindow):
    """Make live applications dominant and reduce the surrounding interface."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self._workspace_vertical_share = 0.96
        self._fullscreen = False
        super().__init__(root, repository, session_engine)
        self.set_product_stage("WORKSPACE 33×96")
        self.status_text.set(
            "Área útil prioritária: 33% por painel e 96% da altura do workspace"
        )
        root.bind("<F11>", self._toggle_fullscreen, add="+")
        root.after_idle(self._maximize_window)
        root.after_idle(self._apply_workspace_first_chrome)
        root.after_idle(self._render_layout)

    def _load_workspace_view(self, message: str) -> None:
        super()._load_workspace_view(message)
        self._apply_workspace_first_chrome()
        self.root.after_idle(self._render_layout)

    def _apply_workspace_first_chrome(self) -> None:
        """Collapse controls so the embedded content owns the visible window."""

        if not hasattr(self, "header"):
            return

        allowed_header_children = {
            self.workspace_toolbar,
            self.extension_actions_frame,
        }
        for child in self.header.winfo_children():
            if child in allowed_header_children:
                continue
            if child.grid_info():
                child.grid_remove()
            else:
                child.place_forget()

        self.header.configure(height=52)
        self.workspace_toolbar.grid_configure(
            row=0,
            column=0,
            sticky="w",
            padx=8,
            pady=7,
        )
        self.extension_actions_frame.grid_configure(
            row=0,
            column=1,
            sticky="e",
            padx=8,
            pady=7,
        )

        for child in self.root.pack_slaves():
            try:
                if child.pack_info().get("side") == "bottom":
                    child.pack_forget()
            except tk.TclError:
                continue

        for card in self.cards:
            self._compact_card(card)

    def _compact_card(self, card: PanelCard) -> None:
        parts = card.frame.winfo_children()
        if len(parts) < 3:
            return

        header, body, footer = parts[0], parts[1], parts[2]
        header.configure(height=32)
        footer.configure(height=28)

        header_children = header.pack_slaves()
        if header_children:
            header_children[0].pack_forget()
        if len(header_children) >= 2:
            identity = header_children[1]
            identity.pack_configure(padx=(8, 2), pady=4)
            identity_children = identity.pack_slaves()
            if identity_children:
                identity_children[0].configure(font=("DejaVu Sans", 10, "bold"))
            for widget in identity_children[1:]:
                widget.pack_forget()
        for widget in header_children[2:]:
            try:
                widget.configure(font=("DejaVu Sans", 7, "bold"), padx=6, pady=2)
                widget.pack_configure(padx=(0, 5))
            except tk.TclError:
                continue

        for widget in body.winfo_children():
            if widget is not card.content_stack:
                widget.pack_forget()
        if card.content_stack.winfo_manager():
            card.content_stack.pack_configure(padx=0, pady=0)
        else:
            card.content_stack.pack(fill="both", expand=True, padx=0, pady=0)

        for widget in footer.pack_slaves():
            try:
                if widget.cget("text") == card.panel.adapter_name.upper():
                    widget.pack_forget()
                    continue
            except tk.TclError:
                pass
            try:
                widget.configure(font=("DejaVu Sans", 7, "bold"), padx=6, pady=2)
                widget.pack_configure(padx=(4, 0), pady=3)
            except tk.TclError:
                continue

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
            vertical_share=self._workspace_vertical_share,
        )
        for card, rect in zip(self.cards, rects, strict=True):
            card.place(rect.x, rect.y, rect.width, rect.height)

        if rects:
            horizontal_share = 100 / min(len(rects), 3)
            self.metrics_text.set(
                f"{len(rects)} PAINÉIS · {horizontal_share:.1f}% × "
                f"{self._workspace_vertical_share * 100:.0f}%"
            )
        else:
            self.metrics_text.set("0 PAINÉIS")
        self.status_text.set("Área útil máxima: moldura mínima, conteúdo prioritário")
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
    "PercentageSlot",
    "WideRect",
    "WorkspaceWindow",
    "calculate_percentage_slots",
    "calculate_wide_grid",
    "main",
]
