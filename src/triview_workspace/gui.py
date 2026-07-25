"""Tkinter desktop shell for TriView Workspace."""

from __future__ import annotations

import logging
import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk

from triview_workspace.engines import (
    BrowserEngine,
    BrowserEngineError,
    BrowserPanelAdapter,
    LayoutEngine,
    PanelRegistry,
    PlaceholderPanelAdapter,
    WorkspaceEngine,
    X11BraveBrowserBackend,
)
from triview_workspace.gui_model import PanelViewModel, build_panel_view_models
from triview_workspace.infrastructure import load_workspace_bundle

APP_TITLE = "TriView Workspace"
DEFAULT_WORKSPACE = Path("config/workspaces/three-mobile.json")
CONTENT_PADDING = 12


class PanelCard:
    """Visual shell and native host for one workspace panel."""

    def __init__(
        self,
        parent: tk.Misc,
        panel: PanelViewModel,
        on_open: Callable[[PanelViewModel, PanelCard], None] | None = None,
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

        header = tk.Frame(self.frame, background="#172033", height=46)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text=self._icon_for(panel.kind),
            background="#172033",
            foreground="#f8fafc",
            font=("Sans", 16),
        ).pack(side="left", padx=(12, 8))

        tk.Label(
            header,
            text=panel.title,
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

        body = tk.Frame(self.frame, background="#0f172a")
        body.pack(fill="both", expand=True, padx=1, pady=1)

        target_bar = tk.Frame(body, background="#1e293b", height=36)
        target_bar.pack(fill="x", padx=12, pady=(12, 0))
        target_bar.pack_propagate(False)
        tk.Label(
            target_bar,
            text=panel.target,
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
            text=self._icon_for(panel.kind),
            background="#0f172a",
            foreground="#38bdf8",
            font=("Sans", 34),
        ).pack(pady=(18, 8))
        tk.Label(
            self.placeholder,
            text=panel.title,
            background="#0f172a",
            foreground="#f8fafc",
            font=("Sans", 15, "bold"),
        ).pack()

        self.status_message = tk.StringVar(value=panel.status)
        tk.Label(
            self.placeholder,
            textvariable=self.status_message,
            background="#0f172a",
            foreground="#94a3b8",
            font=("Sans", 9),
            wraplength=240,
            justify="center",
        ).pack(pady=(8, 0))

        self.browser_host = tk.Frame(
            self.content_stack,
            background="#020617",
            highlightbackground="#1e293b",
            highlightthickness=1,
            bd=0,
        )

        footer = tk.Frame(self.frame, background="#172033", height=48)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        self.open_button = tk.Button(
            footer,
            text="Abrir",
            command=self._request_open,
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

    def _request_open(self) -> None:
        if self._on_open is not None:
            self._on_open(self.panel, self)

    def configure_browser(self, *, available: bool, message: str) -> None:
        if available:
            self.open_button.configure(state="normal")
            self.set_status("DISPONÍVEL", message, "#0f766e")
        else:
            self.open_button.configure(state="disabled")
            self.set_status("INDISPONÍVEL", message, "#991b1b")

    def set_status(self, badge: str, message: str, badge_background: str) -> None:
        self.badge.configure(text=badge, background=badge_background)
        self.status_message.set(message)

    def set_open_enabled(self, enabled: bool, label: str | None = None) -> None:
        self.open_button.configure(state="normal" if enabled else "disabled")
        if label is not None:
            self.open_button.configure(text=label)

    def show_browser_host(self) -> None:
        self.placeholder.pack_forget()
        if not self.browser_host.winfo_manager():
            self.browser_host.pack(fill="both", expand=True)
        self.browser_host.update_idletasks()

    def show_placeholder(self) -> None:
        self.browser_host.pack_forget()
        if not self.placeholder.winfo_manager():
            self.placeholder.pack(fill="both", expand=True)

    def native_host_id(self) -> int:
        self.browser_host.update_idletasks()
        return int(self.browser_host.winfo_id())

    def host_dimensions(self) -> tuple[int, int]:
        self.browser_host.update_idletasks()
        return (
            max(1, self.browser_host.winfo_width()),
            max(1, self.browser_host.winfo_height()),
        )

    @staticmethod
    def _icon_for(kind: str) -> str:
        return {
            "browser": "🌐",
            "application": "▣",
            "terminal": ">_",
            "pdf": "PDF",
        }.get(kind, "◇")

    def place(self, *, x: int, y: int, width: int, height: int) -> None:
        self.frame.place(x=x, y=y, width=max(1, width), height=max(1, height))


class WorkspaceWindow:
    """Responsive desktop window backed by the modular workspace engines."""

    def __init__(self, root: tk.Tk, workspace_path: Path) -> None:
        self.root = root
        self.workspace_path = workspace_path
        self.workspace, self.layout = load_workspace_bundle(workspace_path)
        self.browser_engine = BrowserEngine(X11BraveBrowserBackend())
        self.browser_availability = self.browser_engine.availability()
        self.registry = PanelRegistry()
        self.registry.register(BrowserPanelAdapter())
        self.registry.register(PlaceholderPanelAdapter())
        self.engine = WorkspaceEngine(LayoutEngine(), self.registry)
        self._resize_job: str | None = None
        self._launching: set[str] = set()
        self._browser_results: queue.SimpleQueue[tuple[str, str, str | None]] = (
            queue.SimpleQueue()
        )
        self._closed = False

        root.title(f"{APP_TITLE} — {self.workspace.name}")
        root.geometry("1280x760")
        root.minsize(820, 540)
        root.configure(background="#020617")
        root.protocol("WM_DELETE_WINDOW", self._close)

        self._configure_style()
        self._build_header()

        self.content = tk.Frame(root, background="#020617")
        self.content.pack(fill="both", expand=True)

        self.status_text = tk.StringVar(value="Workspace carregado")
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

        prepared = self.engine.prepare(self.workspace, self.layout, 1200, 650)
        views = build_panel_view_models(prepared)
        self.cards = [PanelCard(self.content, view, self._open_browser) for view in views]
        self.cards_by_id = {card.panel.id: card for card in self.cards}
        self._configure_panel_states()

        self.content.bind("<Configure>", self._schedule_layout)
        root.after(60, self._render_layout)
        root.after(80, self._drain_browser_results)

    @staticmethod
    def _configure_style() -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    def _build_header(self) -> None:
        header = tk.Frame(self.root, background="#0f172a", height=66)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        left = tk.Frame(header, background="#0f172a")
        left.pack(side="left", fill="y", padx=18)
        tk.Label(
            left,
            text=APP_TITLE,
            background="#0f172a",
            foreground="#f8fafc",
            font=("Sans", 16, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(11, 0))
        tk.Label(
            left,
            text=f"Workspace: {self.workspace.name}",
            background="#0f172a",
            foreground="#94a3b8",
            font=("Sans", 9),
            anchor="w",
        ).pack(anchor="w")

        right = tk.Frame(header, background="#0f172a")
        right.pack(side="right", fill="y", padx=16)
        tk.Label(
            right,
            text="BROWSER ENGINE 0.2.0",
            background="#1d4ed8",
            foreground="#eff6ff",
            font=("Sans", 8, "bold"),
            padx=10,
            pady=5,
        ).pack(side="right", pady=20)

    def _configure_panel_states(self) -> None:
        for card in self.cards:
            if card.panel.adapter_name == "browser":
                message = self.browser_availability.reason
                if self.browser_availability.available:
                    message = f"{message} Clique em Abrir para carregar {card.panel.title}."
                card.configure_browser(
                    available=self.browser_availability.available,
                    message=message,
                )
            else:
                card.set_status("PLANEJADO", card.panel.status, "#475569")

    def _open_browser(self, panel: PanelViewModel, card: PanelCard) -> None:
        if self._closed or panel.adapter_name != "browser" or panel.id in self._launching:
            return
        if not self.browser_availability.available:
            card.configure_browser(available=False, message=self.browser_availability.reason)
            return

        self._launching.add(panel.id)
        card.show_browser_host()
        card.set_open_enabled(False, "Abrindo…")
        card.set_status(
            "ABRINDO",
            f"Inicializando {panel.title} e incorporando a janela no painel.",
            "#a16207",
        )
        self.root.update_idletasks()
        parent_window_id = card.native_host_id()
        width, height = card.host_dimensions()

        def launch() -> None:
            try:
                self.browser_engine.open(
                    panel.id,
                    panel.target,
                    parent_window_id,
                    width,
                    height,
                )
            except Exception as exc:  # noqa: BLE001
                self._browser_results.put(("error", panel.id, str(exc)))
                return

            if self._closed:
                self.browser_engine.close(panel.id)
                return
            self._browser_results.put(("opened", panel.id, None))

        threading.Thread(
            target=launch,
            name=f"triview-browser-{panel.id}",
            daemon=True,
        ).start()

    def _drain_browser_results(self) -> None:
        if self._closed:
            return

        while True:
            try:
                result, panel_id, message = self._browser_results.get_nowait()
            except queue.Empty:
                break

            if result == "opened":
                self._browser_opened(panel_id)
            else:
                self._browser_failed(panel_id, message or "Falha desconhecida ao abrir o painel.")

        self.root.after(80, self._drain_browser_results)

    def _browser_opened(self, panel_id: str) -> None:
        self._launching.discard(panel_id)
        card = self.cards_by_id[panel_id]
        card.show_browser_host()
        card.set_open_enabled(True, "Reabrir")
        card.set_status(
            "ATIVO",
            f"{card.panel.title} está executando dentro do painel.",
            "#15803d",
        )
        self.status_text.set(f"Painel {card.panel.title} aberto com Browser Engine X11")
        self._resize_browsers()

    def _browser_failed(self, panel_id: str, message: str) -> None:
        self._launching.discard(panel_id)
        card = self.cards_by_id[panel_id]
        card.show_placeholder()
        card.set_open_enabled(self.browser_availability.available, "Tentar novamente")
        card.set_status("ERRO", message, "#991b1b")
        self.status_text.set(f"Falha ao abrir {card.panel.title}: {message}")
        logging.error("Unable to open browser panel %s: %s", panel_id, message)

    def _schedule_layout(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(30, self._render_layout)

    def _render_layout(self) -> None:
        self._resize_job = None
        width = max(1, self.content.winfo_width() - CONTENT_PADDING * 2)
        height = max(1, self.content.winfo_height() - CONTENT_PADDING * 2)
        runtime_panels = self.engine.prepare(self.workspace, self.layout, width, height)
        views = build_panel_view_models(runtime_panels)

        for card, view in zip(self.cards, views, strict=False):
            bounds = view.bounds
            card.place(
                x=CONTENT_PADDING + bounds.x,
                y=CONTENT_PADDING + bounds.y,
                width=bounds.width,
                height=bounds.height,
            )

        if self.browser_availability.available:
            backend_state = "browser disponível"
        else:
            backend_state = "browser indisponível"
        self.status_text.set(
            f"{self.workspace.name} · {len(views)} painéis · {backend_state} · "
            f"área útil {width} × {height}"
        )
        self.root.after_idle(self._resize_browsers)

    def _resize_browsers(self) -> None:
        if self._closed:
            return
        for card in self.cards:
            if not self.browser_engine.has_session(card.panel.id):
                continue
            width, height = card.host_dimensions()
            try:
                self.browser_engine.resize(card.panel.id, width, height)
            except (BrowserEngineError, OSError) as exc:
                logging.warning("Unable to resize browser panel %s: %s", card.panel.id, exc)

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.browser_engine.close_all()
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


def main(workspace_path: Path = DEFAULT_WORKSPACE) -> int:
    """Start the desktop window and keep it alive until the user closes it."""

    log_path = _configure_logging()
    try:
        root = tk.Tk()
        WorkspaceWindow(root, workspace_path)
        logging.info("TriView Workspace GUI started with %s", workspace_path)
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


if __name__ == "__main__":
    raise SystemExit(main())
