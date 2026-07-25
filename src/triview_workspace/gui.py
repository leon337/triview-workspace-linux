"""Tkinter desktop shell for TriView Workspace."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from triview_workspace.engines import (
    LayoutEngine,
    PanelRegistry,
    PlaceholderPanelAdapter,
    WorkspaceEngine,
)
from triview_workspace.gui_model import PanelViewModel, build_panel_view_models
from triview_workspace.infrastructure import load_workspace_bundle

APP_TITLE = "TriView Workspace"
DEFAULT_WORKSPACE = Path("config/workspaces/three-mobile.json")
CONTENT_PADDING = 12


class PanelCard:
    """Visual shell for one future embedded panel."""

    def __init__(self, parent: tk.Misc, panel: PanelViewModel) -> None:
        self.panel = panel
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

        tk.Label(
            header,
            text="PRONTO",
            background="#0f766e",
            foreground="#ecfeff",
            font=("Sans", 8, "bold"),
            padx=8,
            pady=3,
        ).pack(side="right", padx=10)

        body = tk.Frame(self.frame, background="#0f172a")
        body.pack(fill="both", expand=True, padx=1, pady=1)

        mock_top = tk.Frame(body, background="#1e293b", height=36)
        mock_top.pack(fill="x", padx=12, pady=(16, 0))
        mock_top.pack_propagate(False)
        tk.Label(
            mock_top,
            text=panel.target,
            background="#1e293b",
            foreground="#cbd5e1",
            font=("Sans", 8),
            anchor="w",
            padx=10,
        ).pack(fill="both", expand=True)

        center = tk.Frame(body, background="#0f172a")
        center.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(
            center,
            text=self._icon_for(panel.kind),
            background="#0f172a",
            foreground="#38bdf8",
            font=("Sans", 34),
        ).pack(pady=(12, 8))
        tk.Label(
            center,
            text=panel.title,
            background="#0f172a",
            foreground="#f8fafc",
            font=("Sans", 15, "bold"),
        ).pack()
        tk.Label(
            center,
            text=panel.status,
            background="#0f172a",
            foreground="#94a3b8",
            font=("Sans", 9),
            wraplength=220,
            justify="center",
        ).pack(pady=(8, 0))

        footer = tk.Frame(self.frame, background="#172033", height=48)
        footer.pack(fill="x")
        footer.pack_propagate(False)
        for label in ("Abrir", "Print", "Gravar"):
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
        self.registry = PanelRegistry()
        self.registry.register(PlaceholderPanelAdapter())
        self.engine = WorkspaceEngine(LayoutEngine(), self.registry)
        self._resize_job: str | None = None

        root.title(f"{APP_TITLE} — {self.workspace.name}")
        root.geometry("1280x760")
        root.minsize(820, 540)
        root.configure(background="#020617")

        self._configure_style()
        self._build_header()

        self.content = tk.Frame(root, background="#020617")
        self.content.pack(fill="both", expand=True)

        self.status_text = tk.StringVar(value="Workspace carregado · 3 painéis preparados")
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
        self.cards = [PanelCard(self.content, view) for view in build_panel_view_models(prepared)]

        self.content.bind("<Configure>", self._schedule_layout)
        root.after(60, self._render_layout)

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
            text="FUNDAÇÃO GRÁFICA 0.1.2",
            background="#1d4ed8",
            foreground="#eff6ff",
            font=("Sans", 8, "bold"),
            padx=10,
            pady=5,
        ).pack(side="right", pady=20)

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

        self.status_text.set(
            f"{self.workspace.name} · {len(views)} painéis · área útil {width} × {height}"
        )


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
