"""Generic Tkinter shell for persistent executable panel workspaces."""

from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
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

APP_TITLE = "TriView Workspace"
DEFAULT_WORKSPACE = Path("config/workspaces/three-mobile.json")
CONTENT_PADDING = 12


class PanelEditorDialog:
    """Edit panel title, kind and target with kind-specific validation."""

    def __init__(self, parent: tk.Misc, panels: tuple[PanelSpec, ...]) -> None:
        self.result: tuple[PanelSpec, ...] | None = None
        self.window = tk.Toplevel(parent)
        self.window.title("Editar painéis do workspace")
        self.window.configure(background="#0f172a")
        self.window.transient(parent)
        self.window.grab_set()
        self._rows: list[
            tuple[PanelSpec, tk.StringVar, tk.StringVar, tk.StringVar]
        ] = []

        tk.Label(
            self.window,
            text="Edite os títulos, tipos e destinos dos painéis",
            background="#0f172a",
            foreground="#f8fafc",
            font=("Sans", 12, "bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(14, 10))

        for column, label in enumerate(("Painel", "Título", "Tipo", "Destino")):
            tk.Label(
                self.window,
                text=label,
                background="#0f172a",
                foreground="#94a3b8",
                font=("Sans", 9, "bold"),
            ).grid(row=1, column=column, sticky="w", padx=8, pady=4)

        for row, panel in enumerate(panels, start=2):
            title = tk.StringVar(value=panel.title)
            kind = tk.StringVar(value=panel.kind.value)
            target = tk.StringVar(value=panel.target)
            self._rows.append((panel, title, kind, target))
            tk.Label(
                self.window,
                text=panel.id,
                background="#0f172a",
                foreground="#cbd5e1",
            ).grid(row=row, column=0, sticky="w", padx=8, pady=5)
            tk.Entry(self.window, textvariable=title, width=22).grid(
                row=row, column=1, sticky="ew", padx=8, pady=5
            )
            ttk.Combobox(
                self.window,
                textvariable=kind,
                values=[item.value for item in PanelKind],
                state="readonly",
                width=14,
            ).grid(row=row, column=2, sticky="ew", padx=8, pady=5)
            tk.Entry(self.window, textvariable=target, width=48).grid(
                row=row, column=3, sticky="ew", padx=8, pady=5
            )

        actions = tk.Frame(self.window, background="#0f172a")
        actions.grid(
            row=len(panels) + 2,
            column=0,
            columnspan=4,
            sticky="e",
            padx=14,
            pady=14,
        )
        tk.Button(actions, text="Cancelar", command=self.window.destroy).pack(
            side="right", padx=4
        )
        tk.Button(actions, text="Salvar", command=self._save).pack(
            side="right", padx=4
        )
        self.window.columnconfigure(3, weight=1)
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
            background="#111827",
            highlightbackground="#334155",
            highlightthickness=1,
            bd=0,
        )
        self._build_header()
        self._build_body()
        self._build_footer()

    def _build_header(self) -> None:
        header = tk.Frame(self.frame, background="#172033", height=46)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=self._icon_for(self.panel.kind),
            background="#172033",
            foreground="#f8fafc",
            font=("Sans", 16),
        ).pack(side="left", padx=(12, 8))
        tk.Label(
            header,
            text=self.panel.title,
            background="#172033",
            foreground="#f8fafc",
            font=("Sans", 11, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        self.badge = tk.Label(
            header,
            text="PLANEJADO",
            background="#475569",
            foreground="#f8fafc",
            font=("Sans", 8, "bold"),
            padx=8,
            pady=3,
        )
        self.badge.pack(side="right", padx=10)

    def _build_body(self) -> None:
        body = tk.Frame(self.frame, background="#0f172a")
        body.pack(fill="both", expand=True, padx=1, pady=1)
        target_bar = tk.Frame(body, background="#1e293b", height=36)
        target_bar.pack(fill="x", padx=12, pady=(12, 0))
        target_bar.pack_propagate(False)
        tk.Label(
            target_bar,
            text=self.panel.target,
            background="#1e293b",
            foreground="#cbd5e1",
            font=("Sans", 8),
            anchor="w",
            padx=10,
        ).pack(fill="both", expand=True)

        self.content_stack = tk.Frame(body, background="#0f172a")
        self.content_stack.pack(fill="both", expand=True, padx=12, pady=12)
        self.placeholder = tk.Frame(self.content_stack, background="#0f172a")
        self.placeholder.pack(fill="both", expand=True)
        tk.Label(
            self.placeholder,
            text=self._icon_for(self.panel.kind),
            background="#0f172a",
            foreground="#38bdf8",
            font=("Sans", 34),
        ).pack(pady=(18, 8))
        tk.Label(
            self.placeholder,
            text=self.panel.title,
            background="#0f172a",
            foreground="#f8fafc",
            font=("Sans", 15, "bold"),
        ).pack()
        self.status_message = tk.StringVar(value=self.panel.status)
        tk.Label(
            self.placeholder,
            textvariable=self.status_message,
            background="#0f172a",
            foreground="#94a3b8",
            font=("Sans", 9),
            wraplength=240,
            justify="center",
        ).pack(pady=(8, 0))
        self.runtime_host = tk.Frame(
            self.content_stack,
            background="#020617",
            highlightbackground="#1e293b",
            highlightthickness=1,
            bd=0,
        )

    def _build_footer(self) -> None:
        footer = tk.Frame(self.frame, background="#172033", height=48)
        footer.pack(fill="x")
        footer.pack_propagate(False)
        self.open_button = tk.Button(
            footer,
            text="Abrir",
            command=lambda: self._on_open(self.panel, self),
            state="disabled",
            disabledforeground="#64748b",
            background="#1e293b",
            foreground="#e2e8f0",
            activebackground="#334155",
            activeforeground="#f8fafc",
            relief="flat",
            bd=0,
            font=("Sans", 8),
            padx=8,
        )
        self.open_button.pack(side="left", padx=(8, 0), pady=9)
        for label in ("Print", "Gravar"):
            tk.Button(
                footer,
                text=label,
                state="disabled",
                disabledforeground="#64748b",
                background="#1e293b",
                relief="flat",
                bd=0,
                font=("Sans", 8),
                padx=8,
            ).pack(side="left", padx=(8, 0), pady=9)

    def configure_runtime(self, available: bool, message: str) -> None:
        self.open_button.configure(state="normal" if available else "disabled")
        self.set_status(
            "DISPONÍVEL" if available else "INDISPONÍVEL",
            message,
            "#0f766e" if available else "#991b1b",
        )

    def set_status(self, badge: str, message: str, background: str) -> None:
        self.badge.configure(text=badge, background=background)
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
            "browser": "🌐",
            "application": "▣",
            "terminal": ">_",
            "pdf": "PDF",
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
        self._closed = False
        self._updating_controls = False
        self.cards: list[PanelCard] = []
        self.cards_by_id: dict[str, PanelCard] = {}
        self.panel_specs: dict[str, PanelSpec] = {}

        root.geometry("1280x760")
        root.minsize(900, 560)
        root.configure(background="#020617")
        root.protocol("WM_DELETE_WINDOW", self._close)
        self._configure_style()
        self._build_header()
        self.content = tk.Frame(root, background="#020617")
        self.content.pack(fill="both", expand=True)
        self.status_text = tk.StringVar(value="Workspace persistente carregado")
        tk.Label(
            root,
            textvariable=self.status_text,
            anchor="w",
            background="#0f172a",
            foreground="#94a3b8",
            font=("Sans", 8),
            padx=12,
            height=1,
        ).pack(fill="x", side="bottom")
        self.content.bind("<Configure>", self._schedule_layout)
        self._load_workspace_view("Workspace restaurado automaticamente")
        root.after(80, self._drain_results)
        if repository.last_recovery_message:
            root.after(150, self._show_recovery_warning)

    @staticmethod
    def _configure_style() -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    def _build_header(self) -> None:
        header = tk.Frame(self.root, background="#0f172a", height=104)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        left = tk.Frame(header, background="#0f172a")
        left.pack(side="left", fill="both", expand=True, padx=18, pady=8)
        tk.Label(
            left,
            text=APP_TITLE,
            background="#0f172a",
            foreground="#f8fafc",
            font=("Sans", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.workspace_name_text = tk.StringVar()
        tk.Label(
            left,
            textvariable=self.workspace_name_text,
            background="#0f172a",
            foreground="#94a3b8",
            font=("Sans", 9),
        ).grid(row=1, column=0, sticky="w", pady=(0, 6))

        controls = tk.Frame(left, background="#0f172a")
        controls.grid(row=2, column=0, sticky="w")
        self.workspace_selector = ttk.Combobox(controls, state="readonly", width=30)
        self.workspace_selector.pack(side="left", padx=(0, 6))
        self.workspace_selector.bind("<<ComboboxSelected>>", self._select_workspace)
        self.layout_selector = ttk.Combobox(controls, state="readonly", width=22)
        self.layout_selector.pack(side="left", padx=(0, 8))
        self.layout_selector.bind("<<ComboboxSelected>>", self._select_layout)
        for label, command in (
            ("Novo", self._duplicate_workspace),
            ("Renomear", self._rename_workspace),
            ("Editar painéis", self._edit_panels),
            ("Excluir", self._delete_workspace),
        ):
            tk.Button(
                controls,
                text=label,
                command=command,
                background="#1e293b",
                foreground="#e2e8f0",
                activebackground="#334155",
                activeforeground="#f8fafc",
                relief="flat",
                bd=0,
                padx=8,
                pady=4,
            ).pack(side="left", padx=3)

        tk.Label(
            header,
            text="TERMINAL ENGINE 0.5.0",
            background="#1d4ed8",
            foreground="#eff6ff",
            font=("Sans", 8, "bold"),
            padx=10,
            pady=5,
        ).pack(side="right", padx=16, pady=32)

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
                card.set_status("PLANEJADO", card.panel.status, "#475569")
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
        card.set_status("ABRINDO", f"Inicializando {view.title}.", "#a16207")
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
                card.set_status("ERRO", error or "Falha desconhecida.", "#991b1b")
                continue
            card.set_open(True, "Reabrir")
            if embedded:
                card.show_host()
                card.set_status(
                    "ATIVO",
                    f"{card.panel.title} está executando dentro do painel.",
                    "#15803d",
                )
            elif external:
                card.show_placeholder()
                card.set_status(
                    "EXTERNO",
                    f"{card.panel.title} está em uma janela externa controlada.",
                    "#7c3aed",
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
        active_types = sorted({item.adapter_name for item in views if item.adapter_name != "placeholder"})
        self.status_text.set(
            f"{self.workspace.name} · {len(views)} painéis · "
            f"engines: {', '.join(active_types) or 'nenhum'} · {width} × {height}"
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
