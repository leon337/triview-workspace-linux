"""Responsive layout and activation hardening for the Workspace Hub dialog."""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog
from typing import Any

from triview_workspace.engines.workspace_hub import WorkspaceHubError
from triview_workspace.gui_hub import WorkspaceHubDialog as BaseWorkspaceHubDialog
from triview_workspace.gui_sessions import WorkspaceWindow as SessionWorkspaceWindow

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


def activate_hub_catalog(window: Any, catalog: Any, message: str) -> None:
    """Activate one persisted Hub workspace without losing the prior runtime checkpoint.

    SessionWorkspaceWindow normally checkpoints the current workspace before every
    reload. The Hub already persisted a different active workspace, so this helper
    performs that checkpoint while the old window state is still selected, updates
    both the engine and window state, then resumes the lower rendering chain.
    """

    recovery_engine = getattr(window, "recovery_engine", None)
    if recovery_engine is not None:
        window._sync_runtime_state(force=True)

    window.session_engine.catalog = catalog
    window.workspace = window.session_engine.current_workspace
    window.layout = window.session_engine.current_layout

    # Skip only SessionWorkspaceWindow._load_workspace_view because its pre-sync
    # has already run against the correct previous workspace. All lower GUI layers
    # (recording, capture, shell, RC4 runtime wiring) still execute normally.
    super(SessionWorkspaceWindow, window)._load_workspace_view(message)

    if recovery_engine is not None:
        recovery_engine.begin(window.workspace)
        window._runtime_signature = window._signature({})


class ResponsiveWorkspaceHubDialog(BaseWorkspaceHubDialog):
    """Keep Hub actions visible and fully activate workspaces created from entries."""

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

    def use_selected(self) -> None:
        """Instantiate, persist and render a selected Hub entry as a new workspace."""

        entry = self.selected()
        if entry is None:
            self._error("Selecione um workspace ou template.")
            return
        name = simpledialog.askstring(
            "Novo workspace independente",
            "Nome do workspace que será criado:",
            initialvalue=entry.name,
            parent=self.top,
        )
        if name is None:
            return

        catalog = self.window.session_engine.catalog
        try:
            workspace, layout = self.hub.instantiate(
                entry.id,
                name,
                existing_workspace_ids={item.id for item in catalog.workspaces},
                existing_layout_ids={item.id for item in catalog.layouts},
            )
            persisted_catalog = self.window.repository.save_workspace(
                catalog,
                workspace,
                layout,
                make_active=True,
            )
            activate_hub_catalog(
                self.window,
                persisted_catalog,
                "Workspace criado pelo Hub",
            )
        except (OSError, ValueError, WorkspaceHubError) as exc:
            self._error(exc)
            return
        self.status.set(f"{workspace.name} criado e ativado")


__all__ = [
    "HUB_ACTION_LABELS",
    "ResponsiveWorkspaceHubDialog",
    "activate_hub_catalog",
    "find_hub_action_frame",
    "reserve_hub_action_bar",
    "responsive_hub_geometry",
]
