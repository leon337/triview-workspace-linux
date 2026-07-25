"""Workspace Hub extension of the operational-session workspace shell."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.engines.workspace_hub import (
    HubEntry,
    WorkspaceHubError,
    WorkspaceHubRepository,
)
from triview_workspace.gui_sessions import (
    APP_TITLE,
    DEFAULT_WORKSPACE,
    PanelCard,
    PanelEditorDialog,
    WorkspaceWindow as SessionWorkspaceWindow,
    _configure_logging,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle


class WorkspaceHubDialog:
    """Search, preview and reuse local workspace bundles without launching them."""

    def __init__(
        self,
        parent: tk.Tk,
        window: "WorkspaceWindow",
        hub: WorkspaceHubRepository,
    ) -> None:
        self.window = window
        self.hub = hub
        self.entries: tuple[HubEntry, ...] = ()
        self.top = tk.Toplevel(parent)
        self.top.title("Workspace Hub")
        self.top.geometry("820x520")
        self.top.minsize(700, 440)
        self.top.transient(parent)

        self.query = tk.StringVar()
        self.favorites_only = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Biblioteca local carregada")

        toolbar = ttk.Frame(self.top, padding=10)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Buscar:").pack(side="left")
        search = ttk.Entry(toolbar, textvariable=self.query, width=34)
        search.pack(side="left", padx=(6, 12))
        search.bind("<KeyRelease>", lambda _event: self.refresh())
        ttk.Checkbutton(
            toolbar,
            text="Somente favoritos",
            variable=self.favorites_only,
            command=self.refresh,
        ).pack(side="left")

        content = ttk.Panedwindow(self.top, orient="horizontal")
        content.pack(fill="both", expand=True, padx=10)

        left = ttk.Frame(content)
        right = ttk.Frame(content)
        content.add(left, weight=2)
        content.add(right, weight=3)

        self.listbox = tk.Listbox(left, exportselection=False)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", lambda _event: self.show_preview())

        self.preview = tk.Text(right, wrap="word", state="disabled", padx=10, pady=10)
        self.preview.pack(fill="both", expand=True)

        actions = ttk.Frame(self.top, padding=10)
        actions.pack(fill="x")
        for label, command in (
            ("Salvar atual", lambda: self.save_current("workspace")),
            ("Criar template", lambda: self.save_current("template")),
            ("Importar", self.import_file),
            ("Exportar", self.export_selected),
            ("Favoritar", self.toggle_favorite),
            ("Usar selecionado", self.use_selected),
        ):
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 6))
        ttk.Label(actions, textvariable=self.status).pack(side="right")

        self.refresh()
        search.focus_set()

    def refresh(self) -> None:
        self.entries = self.hub.search(
            self.query.get(),
            favorites_only=self.favorites_only.get(),
        )
        self.listbox.delete(0, "end")
        for entry in self.entries:
            star = "★" if entry.favorite else "☆"
            category = f" · {entry.category}" if entry.category else ""
            self.listbox.insert(
                "end",
                f"{star} {entry.name} [{entry.kind}]{category}",
            )
        self.status.set(f"{len(self.entries)} item(ns)")
        self._set_preview("Selecione um item para visualizar sua estrutura.")

    def selected(self) -> HubEntry | None:
        selection = self.listbox.curselection()
        if not selection:
            return None
        index = int(selection[0])
        if index >= len(self.entries):
            return None
        return self.entries[index]

    def show_preview(self) -> None:
        entry = self.selected()
        if entry is None:
            return
        try:
            preview = self.hub.preview(entry.id)
        except WorkspaceHubError as exc:
            self._error(exc)
            return
        lines = [
            preview.name,
            "",
            f"Tipo: {preview.kind}",
            f"Categoria: {preview.category or 'Sem categoria'}",
            f"Layout: {preview.layout_name}",
            f"Slots: {preview.slot_count}",
            "",
            "Painéis:",
        ]
        lines.extend(
            f"- {title} ({kind})"
            for title, kind in zip(preview.panel_titles, preview.panel_kinds, strict=True)
        )
        self._set_preview("\n".join(lines))

    def save_current(self, kind: str) -> None:
        category = simpledialog.askstring(
            "Categoria",
            "Informe uma categoria opcional:",
            parent=self.top,
        )
        if category is None:
            return
        try:
            entry = self.hub.add_bundle(
                self.window.workspace,
                self.window.layout,
                kind=kind,
                category=category,
            )
        except WorkspaceHubError as exc:
            self._error(exc)
            return
        self.status.set(f"{entry.name} salvo")
        self.refresh()

    def import_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.top,
            title="Importar Workspace Hub",
            filetypes=(("Workspace Hub JSON", "*.json"),),
        )
        if not path:
            return
        try:
            entry = self.hub.import_file(path)
        except (OSError, ValueError, WorkspaceHubError) as exc:
            self._error(exc)
            return
        self.status.set(f"{entry.name} importado")
        self.refresh()

    def export_selected(self) -> None:
        entry = self.selected()
        if entry is None:
            self._error("Selecione um item para exportar.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.top,
            title="Exportar item do Workspace Hub",
            defaultextension=".json",
            initialfile=f"{entry.id}.json",
            filetypes=(("JSON", "*.json"),),
        )
        if not path:
            return
        try:
            exported = self.hub.export_entry(entry.id, path)
        except (OSError, ValueError, WorkspaceHubError) as exc:
            self._error(exc)
            return
        self.status.set(f"Exportado para {exported.name}")

    def toggle_favorite(self) -> None:
        entry = self.selected()
        if entry is None:
            self._error("Selecione um item para favoritar.")
            return
        try:
            self.hub.set_favorite(entry.id, not entry.favorite)
        except WorkspaceHubError as exc:
            self._error(exc)
            return
        self.refresh()

    def use_selected(self) -> None:
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
            self.window.session_engine.catalog = self.window.repository.save_workspace(
                catalog,
                workspace,
                layout,
                make_active=True,
            )
            self.window._load_workspace_view("Workspace criado pelo Hub")
        except (OSError, ValueError, WorkspaceHubError) as exc:
            self._error(exc)
            return
        self.status.set(f"{workspace.name} criado e ativado")

    def _set_preview(self, text: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _error(self, error: object) -> None:
        messagebox.showerror("Workspace Hub", str(error), parent=self.top)


class WorkspaceWindow(SessionWorkspaceWindow):
    """Expose the local Workspace Hub over the complete session shell."""

    def __init__(
        self,
        root: tk.Tk,
        repository: WorkspaceRepository,
        session_engine: WorkspaceSessionEngine,
        hub_repository: WorkspaceHubRepository | None = None,
    ) -> None:
        self.hub_repository = hub_repository or WorkspaceHubRepository()
        super().__init__(root, repository, session_engine)
        self._add_hub_button(root)
        self._replace_hub_badge(root)
        self.status_text.set("Workspace Hub 0.12.0 carregado")

    def _add_hub_button(self, root: tk.Tk) -> None:
        header = next(
            (child for child in root.winfo_children() if isinstance(child, tk.Frame)),
            None,
        )
        if header is None:
            return
        tk.Button(
            header,
            text="Workspace Hub",
            command=lambda: WorkspaceHubDialog(root, self, self.hub_repository),
            background="#1e293b",
            foreground="#e2e8f0",
            activebackground="#334155",
            activeforeground="#f8fafc",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
        ).pack(side="right", padx=(0, 8), pady=32)

    @staticmethod
    def _replace_hub_badge(widget: tk.Misc) -> None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Label) and str(child.cget("text")).startswith(
                "SESSION ENGINE"
            ):
                child.configure(text="WORKSPACE HUB 0.12.0")
            WorkspaceWindow._replace_hub_badge(child)


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
    "WorkspaceHubDialog",
    "WorkspaceWindow",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
