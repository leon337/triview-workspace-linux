"""Generic Tkinter shell for persistent executable panel workspaces."""

from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from triview_workspace.domain import PanelKind, PanelSpec
from triview_workspace.engines import (
    ApplicationEngine,
    ApplicationPanelAdapter,
    ApplicationRuntimeController,
    BrowserEngine,
    BrowserPanelAdapter,
    BrowserRuntimeController,
    LayoutEngine,
    PanelRegistry,
    PlaceholderPanelAdapter,
    RuntimeControllerRegistry,
    TerminalEngine,
    TerminalPanelAdapter,
    TerminalRuntimeController,
    WorkspaceEngine,
    WorkspaceSessionEngine,
    X11ApplicationBackend,
    X11BraveBrowserBackend,
    normalize_browser_url,
    normalize_command,
)
from triview_workspace.gui_model import PanelViewModel, build_panel_view_models
from triview_workspace.infrastructure import (
    WorkspaceRepository,
    WorkspaceStorageError,
    load_workspace_bundle,
)
from triview_workspace.ui_design import (
    APP_BADGE_TEXT,
    FONT_FAMILY,
    MONO_FONT_FAMILY,
    PALETTE,
    button_colors,
    header_layout_mode,
    status_color,
)

APP_TITLE = "TriView Workspace"
DEFAULT_WORKSPACE = Path("config/workspaces/three-mobile.json")
CONTENT_PADDING = 16


def _button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], None] | None = None,
    *,
    variant: str = "secondary",
    compact: bool = False,
    state: str = "normal",
) -> tk.Button:
    """Create one consistently styled Tk button."""

    colors = button_colors(variant)
    return tk.Button(
        parent,
        text=text,
        command=command,
        state=state,
        disabledforeground=PALETTE.text_subtle,
        relief="flat",
        bd=0,
        highlightthickness=0,
        font=(FONT_FAMILY, 8 if compact else 9, "bold"),
        padx=8 if compact else 12,
        pady=4 if compact else 6,
        cursor="hand2",
        **colors,
    )


def _entry(parent: tk.Misc, variable: tk.StringVar, *, width: int = 24) -> tk.Entry:
    """Create one dark entry field."""

    return tk.Entry(
        parent,
        textvariable=variable,
        width=width,
        background=PALETTE.surface_soft,
        foreground=PALETTE.text,
        insertbackground=PALETTE.text,
        selectbackground=PALETTE.accent_dark,
        selectforeground=PALETTE.text,
        highlightbackground=PALETTE.border,
        highlightcolor=PALETTE.border_focus,
        highlightthickness=1,
        relief="flat",
        bd=0,
        font=(FONT_FAMILY, 9),
    )


@dataclass(frozen=True)
class HeaderAction:
    """Declarative extension action rendered by the central header."""

    action_id: str
    label: str
    command: Callable[[], None]
    order: int


class PanelEditorDialog:
    """Edit panel title, kind and target with kind-specific validation."""

    def __init__(self, parent: tk.Misc, panels: tuple[PanelSpec, ...]) -> None:
        self.result: tuple[PanelSpec, ...] | None = None
        self.window = tk.Toplevel(parent)
        self.window.title("Editar painéis")
        self.window.configure(background=PALETTE.surface)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.minsize(820, 280)
        self._rows: list[
            tuple[PanelSpec, tk.StringVar, tk.StringVar, tk.StringVar]
        ] = []

        shell = tk.Frame(
            self.window,
            background=PALETTE.surface,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
            bd=0,
        )
        shell.pack(fill="both", expand=True, padx=16, pady=16)

        title_area = tk.Frame(shell, background=PALETTE.surface)
        title_area.grid(row=0, column=0, columnspan=4, sticky="ew", padx=16, pady=(16, 12))
        tk.Label(
            title_area,
            text="Configuração dos painéis",
            background=PALETTE.surface,
            foreground=PALETTE.text,
            font=(FONT_FAMILY, 15, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            title_area,
            text="Altere nome, tipo e destino sem perder o identificador interno.",
            background=PALETTE.surface,
            foreground=PALETTE.text_muted,
            font=(FONT_FAMILY, 9),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        for column, label in enumerate(("Painel", "Título", "Tipo", "Destino")):
            tk.Label(
                shell,
                text=label.upper(),
                background=PALETTE.surface,
                foreground=PALETTE.text_subtle,
                font=(FONT_FAMILY, 8, "bold"),
            ).grid(row=1, column=column, sticky="w", padx=10, pady=(4, 6))

        for row, panel in enumerate(panels, start=2):
            title = tk.StringVar(value=panel.title)
            kind = tk.StringVar(value=panel.kind.value)
            target = tk.StringVar(value=panel.target)
            self._rows.append((panel, title, kind, target))
            tk.Label(
                shell,
                text=panel.id,
                background=PALETTE.surface,
                foreground=PALETTE.text_muted,
                font=(MONO_FONT_FAMILY, 8),
            ).grid(row=row, column=0, sticky="w", padx=10, pady=6)
            _entry(shell, title, width=22).grid(
                row=row, column=1, sticky="ew", padx=10, pady=6, ipady=6
            )
            ttk.Combobox(
                shell,
                textvariable=kind,
                values=[item.value for item in PanelKind],
                state="readonly",
                width=14,
                style="TriView.TCombobox",
            ).grid(row=row, column=2, sticky="ew", padx=10, pady=6, ipady=3)
            _entry(shell, target, width=48).grid(
                row=row, column=3, sticky="ew", padx=10, pady=6, ipady=6
            )

        actions = tk.Frame(shell, background=PALETTE.surface)
        actions.grid(
            row=len(panels) + 2,
            column=0,
            columnspan=4,
            sticky="e",
            padx=16,
            pady=16,
        )
        _button(actions, "Cancelar", self.window.destroy, variant="ghost").pack(
            side="right", padx=(8, 0)
        )
        _button(actions, "Salvar alterações", self._save, variant="primary").pack(
            side="right"
        )
        shell.columnconfigure(1, weight=1)
        shell.columnconfigure(3, weight=3)
        self.window.wait_window()

    def _save(self) -> None:
        try:
            panels = tuple(self._validated_panel(*row) for row in self._rows)
        except ValueError as exc:
            messagebox.showerror("Dados inválidos", str(exc), parent=self.window)
            return
        self.result = panels
        self.window.destroy()

    @staticmethod
    def _validated_panel(
        original: PanelSpec,
        title_var: tk.StringVar,
        kind_var: tk.StringVar,
        target_var: tk.StringVar,
    ) -> PanelSpec:
        title = title_var.get().strip()
        target = target_var.get().strip()
        if not title:
            raise ValueError(f"O painel {original.id} precisa de um título.")
        if not target:
            raise ValueError(f"O painel {original.id} precisa de um destino.")
        kind = PanelKind(kind_var.get())
        if kind is PanelKind.BROWSER:
            target = normalize_browser_url(target)
        elif kind in {PanelKind.APPLICATION, PanelKind.TERMINAL}:
            target = normalize_command(target)
        return PanelSpec(
            id=original.id,
            title=title,
            kind=kind,
            target=target,
            metadata=original.metadata,
        )


class PanelCard:
    """Visual shell and native host for one workspace panel."""

    def __init__(
        self,
        parent: tk.Misc,
        panel: PanelViewModel,
        on_open: Callable[[PanelViewModel, "PanelCard"], None],
    ) -> None:
        self.panel = panel
        self._on_open = on_open
        self.frame = tk.Frame(
            parent,
            background=PALETTE.surface_raised,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
            bd=0,
        )
        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self) -> None:
        header = tk.Frame(self.frame, background=PALETTE.surface_soft, height=54)
        header.pack(fill="x")
        header.pack_propagate(False)

        icon_box = tk.Frame(
            header,
            background=PALETTE.accent_dark,
            width=34,
            height=34,
        )
        icon_box.pack(side="left", padx=(10, 9), pady=10)
        icon_box.pack_propagate(False)
        tk.Label(
            icon_box,
            text=self._icon_for(self.panel.kind),
            background=PALETTE.accent_dark,
            foreground=PALETTE.text,
            font=(MONO_FONT_FAMILY, 12, "bold"),
        ).pack(fill="both", expand=True)

        identity = tk.Frame(header, background=PALETTE.surface_soft)
        identity.pack(side="left", fill="both", expand=True, pady=8)
        tk.Label(
            identity,
            text=self.panel.title,
            background=PALETTE.surface_soft,
            foreground=PALETTE.text,
            font=(FONT_FAMILY, 11, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            identity,
            text=self.panel.kind.upper(),
            background=PALETTE.surface_soft,
            foreground=PALETTE.text_subtle,
            font=(FONT_FAMILY, 7, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(1, 0))

        self.badge = tk.Label(
            header,
            text="PLANEJADO",
            background=status_color("PLANEJADO"),
            foreground=PALETTE.text,
            font=(FONT_FAMILY, 7, "bold"),
            padx=8,
            pady=3,
        )
        self.badge.pack(side="right", padx=10)

    def _build_body(self) -> None:
        body = tk.Frame(self.frame, background=PALETTE.surface)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        target_bar = tk.Frame(body, background=PALETTE.surface_raised, height=38)
        target_bar.pack(fill="x", padx=10, pady=(10, 0))
        target_bar.pack_propagate(False)
        tk.Label(
            target_bar,
            text="DESTINO",
            background=PALETTE.surface_raised,
            foreground=PALETTE.text_subtle,
            font=(FONT_FAMILY, 7, "bold"),
            padx=9,
        ).pack(side="left")
        tk.Label(
            target_bar,
            text=self.panel.target,
            background=PALETTE.surface_raised,
            foreground=PALETTE.text_muted,
            font=(MONO_FONT_FAMILY, 8),
            anchor="w",
            padx=8,
        ).pack(side="left", fill="both", expand=True)

        self.content_stack = tk.Frame(body, background=PALETTE.surface)
        self.content_stack.pack(fill="both", expand=True, padx=10, pady=10)

        self.placeholder = tk.Frame(self.content_stack, background=PALETTE.surface)
        self.placeholder.pack(fill="both", expand=True)

        center = tk.Frame(self.placeholder, background=PALETTE.surface)
        center.place(relx=0.5, rely=0.46, anchor="center")
        tk.Label(
            center,
            text=self._icon_for(self.panel.kind),
            background=PALETTE.surface,
            foreground=PALETTE.accent_hover,
            font=(MONO_FONT_FAMILY, 28, "bold"),
        ).pack(pady=(0, 8))
        tk.Label(
            center,
            text=self.panel.title,
            background=PALETTE.surface,
            foreground=PALETTE.text,
            font=(FONT_FAMILY, 14, "bold"),
        ).pack()
        self.status_message = tk.StringVar(value=self.panel.status)
        tk.Label(
            center,
            textvariable=self.status_message,
            background=PALETTE.surface,
            foreground=PALETTE.text_muted,
            font=(FONT_FAMILY, 9),
            wraplength=250,
            justify="center",
        ).pack(pady=(8, 0))

        self.runtime_host = tk.Frame(
            self.content_stack,
            background="#030712",
            highlightbackground=PALETTE.border,
            highlightthickness=1,
            bd=0,
        )

    def _build_footer(self) -> None:
        footer = tk.Frame(self.frame, background=PALETTE.surface_soft, height=52)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        self.open_button = _button(
            footer,
            "Abrir",
            lambda: self._on_open(self.panel, self),
            variant="primary",
            compact=True,
            state="disabled",
        )
        self.open_button.pack(side="left", padx=(10, 0), pady=10)

        for label in ("Print", "Gravar"):
            _button(
                footer,
                label,
                variant="ghost",
                compact=True,
                state="disabled",
            ).pack(side="left", padx=(7, 0), pady=10)

        tk.Label(
            footer,
            text=self.panel.adapter_name.upper(),
            background=PALETTE.surface_soft,
            foreground=PALETTE.text_subtle,
            font=(FONT_FAMILY, 7, "bold"),
        ).pack(side="right", padx=10)

    def configure_runtime(self, available: bool, message: str) -> None:
        self.open_button.configure(state="normal" if available else "disabled")
        state = "DISPONÍVEL" if available else "INDISPONÍVEL"
        self.set_status(state, message, status_color(state))

    def set_status(self, badge: str, message: str, background: str | None = None) -> None:
        self.badge.configure(text=badge, background=background or status_color(badge))
        self.status_message.set(message)

    def set_open(self, enabled: bool, label: str) -> None:
        self.open_button.configure(state="normal" if enabled else "disabled", text=label)

    def show_host(self) -> None:
        self.placeholder.pack_forget()
        if not self.runtime_host.winfo_manager():
            self.runtime_host.pack(fill="both", expand=True)
        self.runtime_host.update_idletasks()

    def show_placeholder(self) -> None:
        self.runtime_host.pack_forget()
        if not self.placeholder.winfo_manager():
            self.placeholder.pack(fill="both", expand=True)

    def native_host_id(self) -> int:
        self.runtime_host.update_idletasks()
        return int(self.runtime_host.winfo_id())

    def host_dimensions(self) -> tuple[int, int]:
        self.runtime_host.update_idletasks()
        return (
            max(1, self.runtime_host.winfo_width()),
            max(1, self.runtime_host.winfo_height()),
        )

    def place(self, x: int, y: int, width: int, height: int) -> None:
        self.frame.place(x=x, y=y, width=max(1, width), height=max(1, height))

    def destroy(self) -> None:
        self.frame.destroy()

    @staticmethod
    def _icon_for(kind: str) -> str:
        return {
            "browser": "◎",
            "application": "▣",
            "terminal": ">_",
            "pdf": "PDF",
            "plugin": "◇",
        }.get(kind, "◇")


class WorkspaceWindow:
    """Persistent responsive workspace using generic runtime controllers."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self.root = root
        self.repository = repository
        self.session_engine = session_engine
        self.workspace = session_engine.current_workspace
        self.layout = session_engine.current_layout
        self.registry = PanelRegistry()
        for adapter in (
            BrowserPanelAdapter(),
            ApplicationPanelAdapter(),
            TerminalPanelAdapter(),
            PlaceholderPanelAdapter(),
        ):
            self.registry.register(adapter)
        self.workspace_engine = WorkspaceEngine(LayoutEngine(), self.registry)
        self.runtime_registry = RuntimeControllerRegistry(
            (
                BrowserRuntimeController(BrowserEngine(X11BraveBrowserBackend())),
                ApplicationRuntimeController(ApplicationEngine(X11ApplicationBackend())),
                TerminalRuntimeController(TerminalEngine()),
            )
        )
        self._generation = 0
        self._launching: set[str] = set()
        self._results: queue.SimpleQueue[
            tuple[str, str, str | None, int, bool, bool]
        ] = queue.SimpleQueue()
        self._resize_job: str | None = None
        self._header_job: str | None = None
        self._header_mode: str | None = None
        self._closed = False
        self._updating_controls = False
        self._header_actions: dict[str, HeaderAction] = {}
        self.cards: list[PanelCard] = []
        self.cards_by_id: dict[str, PanelCard] = {}
        self.panel_specs: dict[str, PanelSpec] = {}

        root.geometry("1366x820")
        root.minsize(960, 600)
        root.configure(background=PALETTE.app)
        root.protocol("WM_DELETE_WINDOW", self._close)
        self._configure_style()
        self._build_header()

        self.content = tk.Frame(root, background=PALETTE.app)
        self.content.pack(fill="both", expand=True)

        self.status_text = tk.StringVar(value="Workspace persistente carregado")
        self.metrics_text = tk.StringVar(value="")
        self.stage_text = tk.StringVar(value="CORE")

        status_bar = tk.Frame(
            root,
            background=PALETTE.surface,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
            height=30,
        )
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        tk.Label(
            status_bar,
            textvariable=self.status_text,
            anchor="w",
            background=PALETTE.surface,
            foreground=PALETTE.text_muted,
            font=(FONT_FAMILY, 8),
            padx=14,
        ).pack(side="left", fill="both", expand=True)
        tk.Label(
            status_bar,
            textvariable=self.stage_text,
            background=PALETTE.surface,
            foreground=PALETTE.accent_hover,
            font=(FONT_FAMILY, 7, "bold"),
            padx=10,
        ).pack(side="right")
        tk.Label(
            status_bar,
            textvariable=self.metrics_text,
            background=PALETTE.surface,
            foreground=PALETTE.text_subtle,
            font=(MONO_FONT_FAMILY, 7),
            padx=10,
        ).pack(side="right")

        self.content.bind("<Configure>", self._schedule_layout)
        root.bind("<Configure>", self._schedule_header_layout, add="+")
        self._load_workspace_view("Workspace restaurado automaticamente")
        root.after(80, self._drain_results)
        root.after_idle(self._apply_header_layout)
        if repository.last_recovery_message:
            root.after(150, self._show_recovery_warning)

    @staticmethod
    def _configure_style() -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "TriView.TCombobox",
            fieldbackground=PALETTE.surface_raised,
            background=PALETTE.surface_soft,
            foreground=PALETTE.text,
            arrowcolor=PALETTE.text_muted,
            bordercolor=PALETTE.border,
            lightcolor=PALETTE.border,
            darkcolor=PALETTE.border,
            padding=5,
        )
        style.map(
            "TriView.TCombobox",
            fieldbackground=[("readonly", PALETTE.surface_raised)],
            foreground=[("readonly", PALETTE.text)],
            selectbackground=[("readonly", PALETTE.surface_raised)],
            selectforeground=[("readonly", PALETTE.text)],
        )

    def _build_header(self) -> None:
        self.header = tk.Frame(
            self.root,
            background=PALETTE.surface,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
            height=116,
        )
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)
        self.header.columnconfigure(0, weight=1)

        brand = tk.Frame(self.header, background=PALETTE.surface)
        brand.grid(row=0, column=0, sticky="w", padx=18, pady=(10, 4))
        tk.Label(
            brand,
            text="TRIVIEW",
            background=PALETTE.surface,
            foreground=PALETTE.accent_hover,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(side="left", padx=(0, 9))
        tk.Label(
            brand,
            text=APP_TITLE,
            background=PALETTE.surface,
            foreground=PALETTE.text,
            font=(FONT_FAMILY, 17, "bold"),
            anchor="w",
        ).pack(side="left")

        self.product_badge = tk.Label(
            self.header,
            text=APP_BADGE_TEXT,
            background=PALETTE.accent_dark,
            foreground=PALETTE.text,
            font=(FONT_FAMILY, 8, "bold"),
            padx=12,
            pady=6,
        )
        self.product_badge.grid(row=0, column=1, sticky="e", padx=18, pady=(10, 4))

        self.workspace_toolbar = tk.Frame(self.header, background=PALETTE.surface)
        self.workspace_toolbar.grid(row=1, column=0, sticky="w", padx=18, pady=(4, 12))

        selector_group = tk.Frame(self.workspace_toolbar, background=PALETTE.surface)
        selector_group.pack(side="left")
        self.workspace_selector = ttk.Combobox(
            selector_group,
            state="readonly",
            width=29,
            style="TriView.TCombobox",
        )
        self.workspace_selector.pack(side="left", padx=(0, 6))
        self.workspace_selector.bind("<<ComboboxSelected>>", self._select_workspace)
        self.layout_selector = ttk.Combobox(
            selector_group,
            state="readonly",
            width=22,
            style="TriView.TCombobox",
        )
        self.layout_selector.pack(side="left", padx=(0, 10))
        self.layout_selector.bind("<<ComboboxSelected>>", self._select_layout)

        workspace_actions = tk.Frame(self.workspace_toolbar, background=PALETTE.surface)
        workspace_actions.pack(side="left")
        for label, command, variant in (
            ("Novo", self._duplicate_workspace, "primary"),
            ("Renomear", self._rename_workspace, "secondary"),
            ("Editar painéis", self._edit_panels, "secondary"),
            ("Excluir", self._delete_workspace, "danger"),
        ):
            _button(
                workspace_actions,
                label,
                command,
                variant=variant,
                compact=True,
            ).pack(side="left", padx=(0, 6))

        self.extension_actions_frame = tk.Frame(self.header, background=PALETTE.surface)
        self.extension_actions_frame.grid(
            row=1,
            column=1,
            sticky="e",
            padx=18,
            pady=(4, 12),
        )

        self.workspace_name_text = tk.StringVar()
        self.workspace_context = tk.Label(
            self.header,
            textvariable=self.workspace_name_text,
            background=PALETTE.surface,
            foreground=PALETTE.text_muted,
            font=(FONT_FAMILY, 8),
            anchor="w",
        )
        self.workspace_context.place_forget()

    def register_header_action(
        self,
        action_id: str,
        label: str,
        command: Callable[[], None],
        *,
        order: int = 100,
    ) -> None:
        """Register or replace a stable extension action in the central header."""

        self._header_actions[action_id] = HeaderAction(action_id, label, command, order)
        self._render_header_actions()
        self.root.after_idle(self._apply_header_layout)

    def unregister_header_action(self, action_id: str) -> None:
        """Remove one extension action from the central header."""

        self._header_actions.pop(action_id, None)
        self._render_header_actions()
        self.root.after_idle(self._apply_header_layout)

    def _render_header_actions(self) -> None:
        for child in self.extension_actions_frame.winfo_children():
            child.destroy()
        for action in sorted(
            self._header_actions.values(),
            key=lambda item: (item.order, item.action_id),
        ):
            _button(
                self.extension_actions_frame,
                action.label,
                action.command,
                variant="ghost",
                compact=True,
            ).pack(side="left", padx=(6, 0))

    def set_product_stage(self, stage: str) -> None:
        """Expose the active application layer without mutating the product version."""

        self.stage_text.set(stage.upper())

    def set_product_badge(self, text: str = APP_BADGE_TEXT) -> None:
        """Set the product badge from one explicit source."""

        self.product_badge.configure(text=text)

    def _schedule_header_layout(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self.root or self._closed:
            return
        if self._header_job is not None:
            self.root.after_cancel(self._header_job)
        self._header_job = self.root.after(40, self._apply_header_layout)

    def _apply_header_layout(self) -> None:
        if self._closed:
            return
        self._header_job = None
        mode = header_layout_mode(max(1, self.root.winfo_width()))
        if mode == self._header_mode:
            return
        self._header_mode = mode
        self.extension_actions_frame.grid_forget()
        if mode == "wide":
            self.header.configure(height=116)
            self.extension_actions_frame.grid(
                row=1,
                column=1,
                sticky="e",
                padx=18,
                pady=(4, 12),
            )
        else:
            self.header.configure(height=154)
            self.extension_actions_frame.grid(
                row=2,
                column=0,
                columnspan=2,
                sticky="w",
                padx=12,
                pady=(0, 10),
            )

    def _refresh_controls(self) -> None:
        self._updating_controls = True
        try:
            workspaces = [
                f"{item.name} [{item.id}]" for item in self.session_engine.catalog.workspaces
            ]
            layouts = [
                f"{item.name} [{item.id}]" for item in self.session_engine.catalog.layouts
            ]
            self.workspace_selector.configure(values=workspaces)
            self.layout_selector.configure(values=layouts)
            self.workspace_selector.set(f"{self.workspace.name} [{self.workspace.id}]")
            self.layout_selector.set(f"{self.layout.name} [{self.layout.id}]")
            self.workspace_name_text.set(
                f"Workspace: {self.workspace.name} · catálogo: {self.repository.path}"
            )
            self.root.title(f"{APP_TITLE} — {self.workspace.name}")
        finally:
            self._updating_controls = False

    @staticmethod
    def _selected_id(display: str) -> str:
        return display.rsplit("[", 1)[1][:-1] if display.endswith("]") else display

    def _select_workspace(self, _event: tk.Event[tk.Misc]) -> None:
        if self._updating_controls:
            return
        try:
            self.workspace, self.layout = self.session_engine.switch(
                self._selected_id(self.workspace_selector.get())
            )
        except (KeyError, WorkspaceStorageError) as exc:
            messagebox.showerror("Não foi possível abrir", str(exc), parent=self.root)
            self._refresh_controls()
            return
        self._load_workspace_view("Workspace selecionado e persistido")

    def _select_layout(self, _event: tk.Event[tk.Misc]) -> None:
        if self._updating_controls:
            return
        try:
            self.workspace, self.layout = self.session_engine.change_layout(
                self._selected_id(self.layout_selector.get())
            )
        except (KeyError, ValueError, WorkspaceStorageError) as exc:
            messagebox.showerror("Layout incompatível", str(exc), parent=self.root)
            self._refresh_controls()
            return
        self._load_workspace_view("Layout selecionado e persistido")

    def _duplicate_workspace(self) -> None:
        name = simpledialog.askstring(
            "Novo workspace",
            "Nome do novo workspace:",
            parent=self.root,
        )
        if name is None:
            return
        try:
            self.workspace, self.layout = self.session_engine.duplicate_current(name)
        except (ValueError, WorkspaceStorageError) as exc:
            messagebox.showerror("Não foi possível criar", str(exc), parent=self.root)
            return
        self._load_workspace_view("Novo workspace criado e salvo")

    def _rename_workspace(self) -> None:
        name = simpledialog.askstring(
            "Renomear workspace",
            "Novo nome:",
            initialvalue=self.workspace.name,
            parent=self.root,
        )
        if name is None:
            return
        try:
            self.workspace, self.layout = self.session_engine.rename_current(name)
        except (ValueError, WorkspaceStorageError) as exc:
            messagebox.showerror("Não foi possível renomear", str(exc), parent=self.root)
            return
        self._load_workspace_view("Workspace renomeado e salvo")

    def _edit_panels(self) -> None:
        dialog = PanelEditorDialog(self.root, self.workspace.panels)
        if dialog.result is None:
            return
        try:
            self.workspace, self.layout = self.session_engine.update_panels(dialog.result)
        except (ValueError, WorkspaceStorageError) as exc:
            messagebox.showerror("Não foi possível salvar", str(exc), parent=self.root)
            return
        self._load_workspace_view("Painéis editados e persistidos")

    def _delete_workspace(self) -> None:
        if not messagebox.askyesno(
            "Excluir workspace",
            f"Excluir o workspace '{self.workspace.name}'?",
            parent=self.root,
        ):
            return
        try:
            self.workspace, self.layout = self.session_engine.delete_current()
        except WorkspaceStorageError as exc:
            messagebox.showerror("Não foi possível excluir", str(exc), parent=self.root)
            return
        self._load_workspace_view("Workspace excluído")

    def _load_workspace_view(self, message: str) -> None:
        self._generation += 1
        self.runtime_registry.close_all()
        self._launching.clear()
        for card in self.cards:
            card.destroy()
        prepared = self.workspace_engine.prepare(self.workspace, self.layout, 1200, 650)
        views = build_panel_view_models(prepared)
        self.panel_specs = {item.id: item for item in self.workspace.panels}
        self.cards = [PanelCard(self.content, item, self._open_panel) for item in views]
        self.cards_by_id = {card.panel.id: card for card in self.cards}
        self._configure_panel_states()
        self._refresh_controls()
        self.status_text.set(message)
        self.root.after_idle(self._render_layout)

    def _configure_panel_states(self) -> None:
        for card in self.cards:
            controller = self.runtime_registry.get(card.panel.adapter_name)
            if controller is None:
                card.set_status("PLANEJADO", card.panel.status)
                continue
            availability = controller.availability(self.panel_specs[card.panel.id])
            message = availability.reason
            if availability.available:
                message += (
                    " A janela será incorporada quando compatível."
                    if availability.can_embed
                    else " Será aberta em janela externa controlada."
                )
            card.configure_runtime(availability.available, message)

    def _open_panel(self, view: PanelViewModel, card: PanelCard) -> None:
        controller = self.runtime_registry.get(view.adapter_name)
        if controller is None or self._closed or view.id in self._launching:
            return
        panel = self.panel_specs[view.id]
        availability = controller.availability(panel)
        if not availability.available:
            card.configure_runtime(False, availability.reason)
            return
        generation = self._generation
        self._launching.add(view.id)
        card.show_host()
        card.set_open(False, "Abrindo…")
        card.set_status("ABRINDO", f"Inicializando {view.title}.")
        self.root.update_idletasks()
        host_id = card.native_host_id()
        width, height = card.host_dimensions()

        def launch() -> None:
            try:
                result = controller.open(panel, host_id, width, height)
            except Exception as exc:  # noqa: BLE001
                self._results.put((view.id, "error", str(exc), generation, False, False))
                return
            if self._closed or generation != self._generation:
                controller.close(view.id)
                return
            self._results.put(
                (
                    view.id,
                    "opened",
                    None,
                    generation,
                    result.embedded,
                    result.external,
                )
            )

        threading.Thread(
            target=launch,
            name=f"triview-{view.adapter_name}-{view.id}",
            daemon=True,
        ).start()

    def _drain_results(self) -> None:
        if self._closed:
            return
        while True:
            try:
                panel_id, state, error, generation, embedded, external = (
                    self._results.get_nowait()
                )
            except queue.Empty:
                break
            if generation != self._generation or panel_id not in self.cards_by_id:
                continue
            card = self.cards_by_id[panel_id]
            self._launching.discard(panel_id)
            if state == "error":
                card.show_placeholder()
                card.set_open(True, "Tentar novamente")
                card.set_status("ERRO", error or "Falha desconhecida.")
                self.status_text.set(f"Falha ao abrir {card.panel.title}")
                continue
            card.set_open(True, "Reabrir")
            if embedded:
                card.show_host()
                card.set_status(
                    "ATIVO",
                    f"{card.panel.title} está executando dentro do painel.",
                )
            elif external:
                card.show_placeholder()
                card.set_status(
                    "EXTERNO",
                    f"{card.panel.title} está em uma janela externa controlada.",
                )
            self.status_text.set(f"Painel {card.panel.title} aberto")
            self._resize_runtimes()
        self.root.after(80, self._drain_results)

    def _schedule_layout(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(30, self._render_layout)

    def _render_layout(self) -> None:
        if self._closed:
            return
        self._resize_job = None
        width = max(1, self.content.winfo_width() - CONTENT_PADDING * 2)
        height = max(1, self.content.winfo_height() - CONTENT_PADDING * 2)
        views = build_panel_view_models(
            self.workspace_engine.prepare(self.workspace, self.layout, width, height)
        )
        for card, view in zip(self.cards, views, strict=False):
            bounds = view.bounds
            card.place(
                CONTENT_PADDING + bounds.x,
                CONTENT_PADDING + bounds.y,
                bounds.width,
                bounds.height,
            )
        active_types = sorted(
            {item.adapter_name for item in views if item.adapter_name != "placeholder"}
        )
        self.metrics_text.set(
            f"{len(views)} PAINÉIS · {width}×{height} · "
            f"{'/'.join(active_types) or 'SEM ENGINE'}"
        )
        self.root.after_idle(self._resize_runtimes)

    def _resize_runtimes(self) -> None:
        if self._closed:
            return
        for card in self.cards:
            controller = self.runtime_registry.get(card.panel.adapter_name)
            if controller is None or not controller.has_session(card.panel.id):
                continue
            width, height = card.host_dimensions()
            try:
                controller.resize(card.panel.id, width, height)
            except Exception as exc:  # noqa: BLE001
                logging.warning("Unable to resize panel %s: %s", card.panel.id, exc)

    def _show_recovery_warning(self) -> None:
        if self.repository.last_recovery_message:
            messagebox.showwarning(
                "Catálogo recuperado",
                self.repository.last_recovery_message,
                parent=self.root,
            )

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.runtime_registry.close_all()
        self.root.destroy()


def _configure_logging() -> Path:
    state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    log_dir = state_root / "triview-workspace"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "gui.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return log_path


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    """Start the persistent desktop window until the user closes it."""

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
        logging.exception("Unable to start TriView Workspace GUI")
        try:
            messagebox.showerror(
                APP_TITLE,
                f"Não foi possível abrir a interface.\n\n{exc}\n\nLog: {log_path}",
            )
        except Exception:  # noqa: BLE001
            pass
        print(f"TriView Workspace não pôde abrir: {exc}\nLog: {log_path}")
        return 1
