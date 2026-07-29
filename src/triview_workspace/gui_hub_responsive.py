"""Responsive layout hardening for the Workspace Hub dialog."""

from __future__ import annotations

import tkinter as tk
from typing import Any

from triview_workspace.gui_hub import WorkspaceHubDialog as BaseWorkspaceHubDialog

HUB_ACTION_LABELS = frozenset(
    {
        "Salvar atual",
        "Criar template",
        "Importar",
        "Exportar",
        "Favoritar",
        "Usar selecionado",
    }
)


def responsive_hub_geometry(screen_width: int, screen_height: int) -> tuple[int, int]:
    """Fit the Hub inside the desktop work area without hiding fixed controls."""

    usable_width = max(1, int(screen_width) - 64)
    usable_height = max(1, int(screen_height) - 110)
    return min(940, usable_width), min(600, usable_height)


def _widget_text(widget: Any) -> str | None:
    try:
        return str(widget.cget("text"))
    except (AttributeError, tk.TclError):
        return None


def find_hub_action_frame(shell: Any) -> Any:
    """Locate the fixed action row by its complete public button contract."""

    for child in shell.winfo_children():
        labels = {
            text
            for widget in child.winfo_children()
            if (text := _widget_text(widget)) is not None
        }
        if HUB_ACTION_LABELS.issubset(labels):
            return child
    raise RuntimeError("A barra de ações do Workspace Hub não foi encontrada.")


def reserve_hub_action_bar(content: Any, actions: Any) -> None:
    """Pack the fixed action row first so expandable content cannot clip it."""

    content.pack_forget()
    actions.pack_forget()
    actions.pack(side="bottom", fill="x", padx=16, pady=(8, 16))
    content.pack(fill="both", expand=True, padx=16)


class ResponsiveWorkspaceHubDialog(BaseWorkspaceHubDialog):
    """Keep all Workspace Hub actions visible on constrained Linux desktops."""

    def __init__(self, parent: tk.Tk, window: Any, hub: Any) -> None:
        super().__init__(parent, window, hub)

        content = self.listbox.master.master
        shell = content.master
        actions = find_hub_action_frame(shell)
        reserve_hub_action_bar(content, actions)

        width, height = responsive_hub_geometry(
            self.top.winfo_screenwidth(),
            self.top.winfo_screenheight(),
        )
        self.top.geometry(f"{width}x{height}")
        self.top.minsize(min(760, width), min(440, height))
        self.top.update_idletasks()


__all__ = [
    "HUB_ACTION_LABELS",
    "ResponsiveWorkspaceHubDialog",
    "find_hub_action_frame",
    "reserve_hub_action_bar",
    "responsive_hub_geometry",
]
