"""RC4 interface: proportional workspace shell with compact VS Code style controls."""

from __future__ import annotations

import shlex
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

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
from triview_workspace.ui_design import (
    APP_BADGE_TEXT,
    FONT_FAMILY,
    MONO_FONT_FAMILY,
    PALETTE,
    button_colors,
    status_color,
)

GLOBAL_BAR_RATIO = 0.04
PANEL_HEADER_RATIO = 0.04


def global_bar_height(total_height: int) -> int:
    """Return the global bar height derived from the current window height."""

    return max(32, round(max(1, total_height) * GLOBAL_BAR_RATIO))


def panel_header_height(total_height: int) -> int:
    """Return a compact panel header derived from the panel height."""

    return max(24, round(max(1, total_height) * PANEL_HEADER_RATIO))


class WorkspaceWindow(FocusWorkspaceWindow):
    """Apply the approved RC4 visual language without replacing runtime engines."""

    VIEW_ACTIONS = {
        "view-all": ("▥", "Mostrar todos os painéis"),
        "view-dual": ("◫", "Dividir em dois painéis"),
        "view-focus": ("▣", "Mostrar um painel"),
    }

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
    ) -> None:
        self._panel_menus: dict[str, tk.Menu] = {}
        self._compact_job: str | None = None
        super().__init__(root, repository, session_engine)
        self._hide_legacy_status_bar()
        root.bind("<Control-k>", lambda _event: self.command_entry.focus_set(), add="+")
        root.bind("<Configure>", self._schedule_compact_chrome, add="+")
        self.set_product_stage("RC4")
        self.status_text.set("Interface proporcional RC4 carregada")
        root.after_idle(self._apply_compact_chrome)

    def _build_header(self) -> None:
        """Build one compact global bar similar to VS Code."""

        self.header = tk.Frame(
            self.root,
            background=PALETTE.surface,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
            height=global_bar_height(820),
        )
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        brand = tk.Frame(self.header, background=PALETTE.surface)
        brand.pack(side="left", padx=(10, 8), fill="y")
        tk.Label(
            brand,
            text="TRIVIEW",
            background=PALETTE.surface,
            foreground=PALETTE.accent_hover,
            font=(FONT_FAMILY, 8, "bold"),
        ).pack(side="left", pady=4)
        tk.Label(
            brand,
            text="Workspace",
            background=PALETTE.surface,
            foreground=PALETTE.text,
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(side="left", padx=(7, 0), pady=4)

        self.workspace_toolbar = tk.Frame(self.header, background=PALETTE.surface)
        self.workspace_toolbar.pack(side="left", fill="y")

        self.workspace_selector = ttk.Combobox(
            self.workspace_toolbar,
            state="readonly",
            width=23,
            style="TriView.TCombobox",
        )
        self.workspace_selector.pack(side="left", padx=(0, 4), pady=3)
        self.workspace_selector.bind("<<ComboboxSelected>>", self._select_workspace)

        self.layout_selector = ttk.Combobox(
            self.workspace_toolbar,
            state="readonly",
            width=18,
            style="TriView.TCombobox",
        )
        self.layout_selector.pack(side="left", padx=(0, 6), pady=3)
        self.layout_selector.bind("<<ComboboxSelected>>", self._select_layout)

        self.command_var = tk.StringVar()
        self.command_entry = tk.Entry(
            self.header,
            textvariable=self.command_var,
            background=PALETTE.surface_raised,
            foreground=PALETTE.text_muted,
            insertbackground=PALETTE.text,
            selectbackground=PALETTE.accent_dark,
            relief="flat",
            bd=0,
            highlightbackground=PALETTE.border,
            highlightcolor=PALETTE.border_focus,
            highlightthickness=1,
            font=(FONT_FAMILY, 8),
        )
        self.command_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=3)
        self.command_entry.insert(0, "Pesquisar comandos e painéis")
        self.command_entry.bind("<FocusIn>", self._clear_command_hint)
        self.command_entry.bind("<FocusOut>", self._restore_command_hint)
        self.command_entry.bind("<Return>", self._execute_command)

        self.extension_actions_frame = tk.Frame(self.header, background=PALETTE.surface)
        self.extension_actions_frame.pack(side="right", padx=(0, 4), fill="y")

        self.product_badge = tk.Label(
            self.header,
            text=APP_BADGE_TEXT,
            background=PALETTE.accent_dark,
            foreground=PALETTE.text,
            font=(FONT_FAMILY, 7, "bold"),
            padx=7,
            pady=3,
        )
        self.product_badge.pack(side="right", padx=(3, 7), pady=3)

        self._global_menu = tk.Menu(
            self.root,
            tearoff=False,
            background=PALETTE.surface_raised,
            foreground=PALETTE.text,
            activebackground=PALETTE.accent_dark,
            activeforeground=PALETTE.text,
        )
        menu_colors = button_colors("ghost")
        self._global_menu_button = tk.Button(
            self.header,
            text="⋯",
            command=self._show_global_menu,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(MONO_FONT_FAMILY, 11, "bold"),
            padx=7,
            pady=2,
            cursor="hand2",
            **menu_colors,
        )
        self._global_menu_button.pack(side="right", padx=(2, 2), pady=3)

        self.workspace_name_text = tk.StringVar()
        self.workspace_context = tk.Label(
            self.header,
            textvariable=self.workspace_name_text,
            background=PALETTE.surface,
            foreground=PALETTE.text_muted,
        )
        self.workspace_context.place_forget()
        self._rebuild_global_menu()

    def _hide_legacy_status_bar(self) -> None:
        """Remove the fixed footer so the content receives the remaining 96%."""

        for child in self.root.winfo_children():
            if child in {self.header, self.content}:
                continue
            try:
                if child.pack_info().get("side") == "bottom":
                    child.pack_forget()
            except (KeyError, tk.TclError):
                continue

    def _render_header_actions(self) -> None:
        for child in self.extension_actions_frame.winfo_children():
            child.destroy()
        colors = button_colors("ghost")
        for action in sorted(
            self._header_actions.values(),
            key=lambda item: (item.order, item.action_id),
        ):
            visual = self.VIEW_ACTIONS.get(action.action_id)
            if visual is None:
                continue
            icon, tooltip = visual
            button = tk.Button(
                self.extension_actions_frame,
                text=icon,
                command=action.command,
                relief="flat",
                bd=0,
                highlightthickness=0,
                font=(MONO_FONT_FAMILY, 11, "bold"),
                padx=7,
                pady=2,
                cursor="hand2",
                **colors,
            )
            button.pack(side="left", padx=1, pady=3)
            button.bind("<Enter>", lambda _event, text=tooltip: self.status_text.set(text))
        self._rebuild_global_menu()

    def _rebuild_global_menu(self) -> None:
        if not hasattr(self, "_global_menu"):
            return
        self._global_menu.delete(0, "end")
        self._global_menu.add_command(label="Novo workspace", command=self._duplicate_workspace)
        self._global_menu.add_command(label="Renomear workspace", command=self._rename_workspace)
        self._global_menu.add_command(label="Editar painéis", command=self._edit_panels)
        self._global_menu.add_command(label="Excluir workspace", command=self._delete_workspace)
        extra_actions = [
            action
            for action in sorted(
                self._header_actions.values(),
                key=lambda item: (item.order, item.action_id),
            )
            if action.action_id not in self.VIEW_ACTIONS
        ]
        if extra_actions:
            self._global_menu.add_separator()
            for action in extra_actions:
                self._global_menu.add_command(label=action.label, command=action.command)
        self._global_menu.add_separator()
        self._global_menu.add_command(label="Sair", command=self._close)

    def _show_global_menu(self) -> None:
        self._rebuild_global_menu()
        x = self._global_menu_button.winfo_rootx()
        y = self._global_menu_button.winfo_rooty() + self._global_menu_button.winfo_height()
        self._global_menu.tk_popup(x, y)

    def _clear_command_hint(self, _event: tk.Event[tk.Misc]) -> None:
        if self.command_var.get() == "Pesquisar comandos e painéis":
            self.command_var.set("")

    def _restore_command_hint(self, _event: tk.Event[tk.Misc]) -> None:
        if not self.command_var.get().strip():
            self.command_var.set("Pesquisar comandos e painéis")

    def _execute_command(self, _event: tk.Event[tk.Misc]) -> None:
        query = self.command_var.get().strip().casefold()
        commands = {
            "novo": self._duplicate_workspace,
            "renomear": self._rename_workspace,
            "editar": self._edit_panels,
            "excluir": self._delete_workspace,
            "todos": lambda: self._set_view_mode("all"),
            "dois": lambda: self._set_view_mode("dual"),
            "foco": lambda: self._set_view_mode("focus"),
        }
        for action in self._header_actions.values():
            commands[action.label.casefold()] = action.command
        for label, command in commands.items():
            if query and (query in label or label in query):
                command()
                self.command_var.set("")
                return
        self.status_text.set(f"Comando não encontrado: {query}")

    def _apply_header_layout(self) -> None:
        if self._closed:
            return
        self._header_job = None
        self.header.configure(height=global_bar_height(self.root.winfo_height()))
        width = self.root.winfo_width()
        self.workspace_selector.configure(width=18 if width < 1180 else 23)
        self.layout_selector.configure(width=14 if width < 1180 else 18)
        if width < 1000:
            self.product_badge.pack_forget()
        elif not self.product_badge.winfo_manager():
            self.product_badge.pack(side="right", padx=(3, 7), pady=3)

    def _load_workspace_view(self, message: str) -> None:
        super()._load_workspace_view(message)
        self.root.after_idle(self._apply_compact_chrome)

    def _render_layout(self) -> None:
        super()._render_layout()
        self._apply_compact_chrome()

    def _schedule_compact_chrome(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self.root or self._closed:
            return
        if self._compact_job is not None:
            self.root.after_cancel(self._compact_job)
        self._compact_job = self.root.after(35, self._apply_compact_chrome)

    def _apply_compact_chrome(self) -> None:
        if self._closed:
            return
        self._compact_job = None
        self._apply_header_layout()
        for card in self.cards:
            self._compact_panel(card)

    def _compact_panel(self, card: PanelCard) -> None:
        card.frame.update_idletasks()
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
            icon_box.pack_configure(padx=(5, 5), pady=max(1, (height - icon_size) // 2))
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
            target_bar = body_children[0]
            target_bar.pack_forget()
        card.content_stack.pack_configure(padx=0, pady=0)
        footer.pack_forget()
        self._ensure_panel_menu(card, header)

    def _ensure_panel_menu(self, card: PanelCard, header: tk.Misc) -> None:
        if card.panel.id in self._panel_menus:
            return
        colors = button_colors("ghost")
        button = tk.Button(
            header,
            text="⋯",
            command=lambda item=card: self._show_panel_menu(item),
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(MONO_FONT_FAMILY, 10, "bold"),
            padx=5,
            pady=1,
            cursor="hand2",
            **colors,
        )
        button.pack(side="right", padx=(0, 2), before=card.badge)
        menu = tk.Menu(
            self.root,
            tearoff=False,
            background=PALETTE.surface_raised,
            foreground=PALETTE.text,
            activebackground=PALETTE.accent_dark,
            activeforeground=PALETTE.text,
        )
        menu._triview_button = button  # type: ignore[attr-defined]
        self._panel_menus[card.panel.id] = menu

    def _show_panel_menu(self, card: PanelCard) -> None:
        menu = self._panel_menus[card.panel.id]
        menu.delete(0, "end")
        menu.add_command(label="Abrir / reabrir", command=card.open_button.invoke)
        menu.add_command(label="Abrir em janela externa", command=lambda: self._open_external(card))
        menu.add_separator()

        capture = self._find_button(card.frame, "Print")
        menu.add_command(
            label="Capturar tela",
            command=capture.invoke if capture is not None else lambda: None,
            state="normal" if capture is not None and str(capture.cget("state")) == "normal" else "disabled",
        )
        record = self._find_button(card.frame, "Parar") or self._find_button(card.frame, "Gravar")
        record_label = "Parar gravação" if record is not None and record.cget("text") == "Parar" else "Iniciar gravação"
        menu.add_command(
            label=record_label,
            command=record.invoke if record is not None else lambda: None,
            state="normal" if record is not None and str(record.cget("state")) == "normal" else "disabled",
        )
        menu.add_separator()
        menu.add_command(label="Foco", command=lambda: self._toggle_focus(card.panel.id))
        menu.add_command(label="Fechar painel", command=lambda: self._close_panel(card))

        button = menu._triview_button  # type: ignore[attr-defined]
        menu.tk_popup(
            button.winfo_rootx(),
            button.winfo_rooty() + button.winfo_height(),
        )

    def _open_external(self, card: PanelCard) -> None:
        panel = self.panel_specs[card.panel.id]
        try:
            if panel.kind.value == "browser":
                command = ["xdg-open", panel.target]
            elif panel.kind.value == "terminal":
                command = ["x-terminal-emulator", "-e", *shlex.split(panel.target)]
            else:
                command = shlex.split(panel.target)
            subprocess.Popen(command, start_new_session=True)  # noqa: S603
        except (OSError, ValueError) as exc:
            messagebox.showerror("Não foi possível abrir", str(exc), parent=self.root)
            return
        card.set_status("EXTERNO", f"{card.panel.title} aberto externamente.")
        self.status_text.set(f"Painel externo aberto: {card.panel.title}")

    def _close_panel(self, card: PanelCard) -> None:
        controller = self.runtime_registry.get(card.panel.adapter_name)
        if controller is not None:
            controller.close(card.panel.id)
        card.show_placeholder()
        card.set_open(True, "Abrir")
        card.set_status(
            "DISPONÍVEL",
            f"{card.panel.title} fechado. Use o menu para abrir novamente.",
            status_color("DISPONÍVEL"),
        )
        self.status_text.set(f"Painel fechado: {card.panel.title}")


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
    "global_bar_height",
    "main",
    "panel_header_height",
]


if __name__ == "__main__":
    raise SystemExit(main())
