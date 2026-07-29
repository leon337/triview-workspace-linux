"""Focused workspace views for practical use of embedded panels."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.gui_hub import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as HubWorkspaceWindow,
    _configure_logging,
)
from triview_workspace.gui_model import PanelViewModel
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle
from triview_workspace.ui_design import FONT_FAMILY, PALETTE, button_colors

VIEW_PADDING = 16
VIEW_GAP = 14
MIN_DUAL_RATIO = 0.25
MAX_DUAL_RATIO = 0.75


def select_visible_panel_ids(
    panel_ids: tuple[str, ...],
    mode: str,
    focused_id: str | None,
) -> tuple[str, ...]:
    """Return the stable panel subset for all, dual or focus view modes."""

    if not panel_ids:
        return ()
    if mode == "all":
        return panel_ids

    focus = focused_id if focused_id in panel_ids else panel_ids[0]
    if mode == "focus" or len(panel_ids) == 1:
        return (focus,)
    if mode != "dual":
        raise ValueError(f"Modo de visualização desconhecido: {mode}")

    focus_index = panel_ids.index(focus)
    second = panel_ids[(focus_index + 1) % len(panel_ids)]
    return (focus, second)


def dual_orientation(width: int, height: int) -> str:
    """Choose the split direction that preserves the largest useful panel area."""

    return "horizontal" if width >= max(900, int(height * 1.35)) else "vertical"


class WorkspaceWindow(HubWorkspaceWindow):
    """Add maximization, dual view and a draggable splitter to the complete shell."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self._view_mode = "all"
        self._focused_panel_id: str | None = None
        self._visible_panel_ids: set[str] = set()
        self._focus_buttons: dict[str, tk.Button] = {}
        self._dual_ratio = 0.5
        self._dual_orientation = "horizontal"
        super().__init__(root, repository, session_engine)

        self._splitter = tk.Frame(
            self.content,
            background=PALETTE.border_focus,
            cursor="sb_h_double_arrow",
        )
        self._splitter.bind("<B1-Motion>", self._drag_splitter)

        self.register_header_action(
            "view-all",
            "Todos",
            lambda: self._set_view_mode("all"),
            order=70,
        )
        self.register_header_action(
            "view-dual",
            "2 painéis",
            lambda: self._set_view_mode("dual"),
            order=71,
        )
        self.register_header_action(
            "view-focus",
            "1 painel",
            lambda: self._set_view_mode("focus"),
            order=72,
        )

        root.bind("<Escape>", lambda _event: self._set_view_mode("all"), add="+")
        root.bind("<Control-Key-1>", lambda _event: self._set_view_mode("focus"), add="+")
        root.bind("<Control-Key-2>", lambda _event: self._set_view_mode("dual"), add="+")
        root.bind("<Control-Key-3>", lambda _event: self._set_view_mode("all"), add="+")
        self.set_product_stage("FOCUS WORKSPACE")
        self.status_text.set(
            "Visualização pronta: Todos, 2 painéis ou 1 painel; Esc restaura todos"
        )
        root.after_idle(self._render_layout)

    def _load_workspace_view(self, message: str) -> None:
        super()._load_workspace_view(message)
        panel_ids = tuple(card.panel.id for card in self.cards)
        if self._focused_panel_id not in panel_ids:
            self._focused_panel_id = panel_ids[0] if panel_ids else None
        self._wire_focus_controls()
        self.root.after_idle(self._render_layout)

    def _wire_focus_controls(self) -> None:
        self._focus_buttons.clear()
        colors = button_colors("ghost")
        for card in self.cards:
            children = card.frame.winfo_children()
            if not children:
                continue
            header = children[0]
            button = tk.Button(
                header,
                text="Foco",
                command=lambda panel_id=card.panel.id: self._toggle_focus(panel_id),
                relief="flat",
                bd=0,
                highlightthickness=0,
                font=(FONT_FAMILY, 7, "bold"),
                padx=7,
                pady=3,
                cursor="hand2",
                **colors,
            )
            button.pack(side="right", padx=(0, 4), before=card.badge)
            self._focus_buttons[card.panel.id] = button
        self._refresh_focus_buttons()

    def _toggle_focus(self, panel_id: str) -> None:
        if self._view_mode == "focus" and self._focused_panel_id == panel_id:
            self._set_view_mode("all")
            return
        self._set_view_mode("focus", panel_id)

    def _set_view_mode(self, mode: str, panel_id: str | None = None) -> None:
        if mode not in {"all", "dual", "focus"}:
            raise ValueError(f"Modo de visualização desconhecido: {mode}")
        if panel_id in self.cards_by_id:
            self._focused_panel_id = panel_id
        elif self._focused_panel_id not in self.cards_by_id and self.cards:
            self._focused_panel_id = self.cards[0].panel.id
        self._view_mode = mode
        self._refresh_focus_buttons()
        self._render_layout()

    def _refresh_focus_buttons(self) -> None:
        for panel_id, button in self._focus_buttons.items():
            is_focused = self._view_mode == "focus" and panel_id == self._focused_panel_id
            button.configure(text="Restaurar" if is_focused else "Foco")

    def _open_panel(self, view: PanelViewModel, card: PanelCard) -> None:
        self._focused_panel_id = view.id
        super()._open_panel(view, card)

    def _render_layout(self) -> None:
        if self._closed:
            return
        self._resize_job = None
        width = max(1, self.content.winfo_width() - VIEW_PADDING * 2)
        height = max(1, self.content.winfo_height() - VIEW_PADDING * 2)
        panel_ids = tuple(card.panel.id for card in self.cards)
        visible = select_visible_panel_ids(panel_ids, self._view_mode, self._focused_panel_id)
        self._visible_panel_ids = set(visible)

        if hasattr(self, "_splitter"):
            self._splitter.place_forget()

        if self._view_mode == "all":
            super()._render_layout()
            self._visible_panel_ids = set(panel_ids)
            self._refresh_focus_buttons()
            return

        for card in self.cards:
            if card.panel.id not in self._visible_panel_ids:
                card.frame.place_forget()

        visible_cards = [self.cards_by_id[panel_id] for panel_id in visible]
        if len(visible_cards) == 1:
            visible_cards[0].place(VIEW_PADDING, VIEW_PADDING, width, height)
            self.metrics_text.set(f"1 PAINEL · FOCO · {width}×{height}")
        else:
            self._render_dual(visible_cards, width, height)
            self.metrics_text.set(
                f"2 PAINÉIS · {self._dual_orientation.upper()} · {width}×{height}"
            )

        focused_title = (
            self.cards_by_id[self._focused_panel_id].panel.title
            if self._focused_panel_id in self.cards_by_id
            else "painel"
        )
        self.status_text.set(
            f"Modo {'foco' if self._view_mode == 'focus' else 'duplo'}: {focused_title}"
        )
        self._refresh_focus_buttons()
        self.root.after_idle(self._resize_runtimes)

    def _render_dual(self, cards: list[PanelCard], width: int, height: int) -> None:
        self._dual_orientation = dual_orientation(width, height)
        ratio = min(MAX_DUAL_RATIO, max(MIN_DUAL_RATIO, self._dual_ratio))
        if self._dual_orientation == "horizontal":
            usable = max(2, width - VIEW_GAP)
            first_width = max(1, int(usable * ratio))
            second_width = max(1, usable - first_width)
            cards[0].place(VIEW_PADDING, VIEW_PADDING, first_width, height)
            cards[1].place(
                VIEW_PADDING + first_width + VIEW_GAP,
                VIEW_PADDING,
                second_width,
                height,
            )
            if hasattr(self, "_splitter"):
                self._splitter.configure(cursor="sb_h_double_arrow")
                self._splitter.place(
                    x=VIEW_PADDING + first_width,
                    y=VIEW_PADDING,
                    width=VIEW_GAP,
                    height=height,
                )
        else:
            usable = max(2, height - VIEW_GAP)
            first_height = max(1, int(usable * ratio))
            second_height = max(1, usable - first_height)
            cards[0].place(VIEW_PADDING, VIEW_PADDING, width, first_height)
            cards[1].place(
                VIEW_PADDING,
                VIEW_PADDING + first_height + VIEW_GAP,
                width,
                second_height,
            )
            if hasattr(self, "_splitter"):
                self._splitter.configure(cursor="sb_v_double_arrow")
                self._splitter.place(
                    x=VIEW_PADDING,
                    y=VIEW_PADDING + first_height,
                    width=width,
                    height=VIEW_GAP,
                )

    def _drag_splitter(self, _event: tk.Event[tk.Misc]) -> None:
        width = max(1, self.content.winfo_width() - VIEW_PADDING * 2)
        height = max(1, self.content.winfo_height() - VIEW_PADDING * 2)
        if self._dual_orientation == "horizontal":
            pointer = self.content.winfo_pointerx() - self.content.winfo_rootx() - VIEW_PADDING
            usable = max(1, width - VIEW_GAP)
        else:
            pointer = self.content.winfo_pointery() - self.content.winfo_rooty() - VIEW_PADDING
            usable = max(1, height - VIEW_GAP)
        self._dual_ratio = min(
            MAX_DUAL_RATIO,
            max(MIN_DUAL_RATIO, pointer / usable),
        )
        self._render_layout()

    def _resize_runtimes(self) -> None:
        if self._closed:
            return
        visible = self._visible_panel_ids or {card.panel.id for card in self.cards}
        for card in self.cards:
            if card.panel.id not in visible:
                continue
            controller = self.runtime_registry.get(card.panel.adapter_name)
            if controller is None or not controller.has_session(card.panel.id):
                continue
            width, height = card.host_dimensions()
            try:
                controller.resize(card.panel.id, width, height)
            except Exception as exc:  # noqa: BLE001
                logging.warning("Unable to resize panel %s: %s", card.panel.id, exc)


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
    "dual_orientation",
    "main",
    "select_visible_panel_ids",
]


if __name__ == "__main__":
    raise SystemExit(main())
