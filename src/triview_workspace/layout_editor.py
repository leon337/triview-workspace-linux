"""Tkinter editor with validated normalized slots and live preview."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from triview_workspace.domain import LayoutSpec, NormalizedRect
from triview_workspace.engines.layout_advanced import (
    LayoutValidationError,
    create_layout,
    preset_slots,
)


class LayoutEditorDialog:
    """Edit normalized coordinates while previewing the resulting layout."""

    def __init__(
        self,
        parent: tk.Misc,
        panel_count: int,
        existing_ids: set[str],
    ) -> None:
        self.result: LayoutSpec | None = None
        self.panel_count = panel_count
        self.existing_ids = existing_ids
        self.window = tk.Toplevel(parent)
        self.window.title("Novo layout personalizado")
        self.window.configure(background="#0f172a")
        self.window.transient(parent)
        self.window.grab_set()
        self.layout_id = tk.StringVar(value="custom-layout")
        self.layout_name = tk.StringVar(value="Layout personalizado")
        self.preset = tk.StringVar(value="columns")
        self.rows: list[
            tuple[tk.DoubleVar, tk.DoubleVar, tk.DoubleVar, tk.DoubleVar]
        ] = []
        self._build()
        self._apply_preset()
        self.window.wait_window()

    def _build(self) -> None:
        form = tk.Frame(self.window, background="#0f172a")
        form.pack(fill="x", padx=14, pady=12)
        tk.Label(form, text="ID", background="#0f172a", foreground="#cbd5e1").grid(
            row=0, column=0, sticky="w", padx=4
        )
        tk.Entry(form, textvariable=self.layout_id, width=24).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        tk.Label(form, text="Nome", background="#0f172a", foreground="#cbd5e1").grid(
            row=0, column=2, sticky="w", padx=4
        )
        tk.Entry(form, textvariable=self.layout_name, width=30).grid(
            row=0, column=3, sticky="ew", padx=4
        )
        tk.Label(
            form, text="Preset", background="#0f172a", foreground="#cbd5e1"
        ).grid(row=1, column=0, sticky="w", padx=4, pady=(8, 0))
        values = ["columns", "stack", "grid", "focus-left"]
        if self.panel_count == 3:
            values.append("two-plus-one")
        ttk.Combobox(
            form,
            textvariable=self.preset,
            values=values,
            state="readonly",
            width=22,
        ).grid(row=1, column=1, sticky="ew", padx=4, pady=(8, 0))
        tk.Button(form, text="Aplicar preset", command=self._apply_preset).grid(
            row=1, column=2, sticky="w", padx=4, pady=(8, 0)
        )

        editor = tk.Frame(self.window, background="#0f172a")
        editor.pack(fill="x", padx=14)
        for column, label in enumerate(("Slot", "X", "Y", "Largura", "Altura")):
            tk.Label(
                editor,
                text=label,
                background="#0f172a",
                foreground="#94a3b8",
                font=("Sans", 9, "bold"),
            ).grid(row=0, column=column, padx=4, pady=4)
        for index in range(self.panel_count):
            variables = tuple(tk.DoubleVar(value=0.0) for _ in range(4))
            self.rows.append(variables)  # type: ignore[arg-type]
            tk.Label(
                editor,
                text=str(index + 1),
                background="#0f172a",
                foreground="#e2e8f0",
            ).grid(row=index + 1, column=0, padx=4, pady=3)
            for column, variable in enumerate(variables, start=1):
                tk.Entry(editor, textvariable=variable, width=10).grid(
                    row=index + 1, column=column, padx=4, pady=3
                )

        self.canvas = tk.Canvas(
            self.window,
            width=640,
            height=360,
            background="#020617",
            highlightbackground="#334155",
            highlightthickness=1,
        )
        self.canvas.pack(fill="both", expand=True, padx=14, pady=12)

        actions = tk.Frame(self.window, background="#0f172a")
        actions.pack(fill="x", padx=14, pady=(0, 14))
        tk.Button(actions, text="Atualizar prévia", command=self._preview).pack(
            side="left"
        )
        tk.Button(actions, text="Cancelar", command=self.window.destroy).pack(
            side="right", padx=4
        )
        tk.Button(actions, text="Salvar layout", command=self._save).pack(
            side="right", padx=4
        )

    def _apply_preset(self) -> None:
        try:
            slots = preset_slots(self.preset.get(), self.panel_count)
        except LayoutValidationError as exc:
            messagebox.showerror("Preset inválido", str(exc), parent=self.window)
            return
        for variables, slot in zip(self.rows, slots, strict=True):
            values = (slot.x, slot.y, slot.width, slot.height)
            for variable, value in zip(variables, values, strict=True):
                variable.set(round(value, 6))
        self._preview()

    def _slots(self) -> tuple[NormalizedRect, ...]:
        return tuple(
            NormalizedRect(
                float(x.get()),
                float(y.get()),
                float(width.get()),
                float(height.get()),
            )
            for x, y, width, height in self.rows
        )

    def _layout(self) -> LayoutSpec:
        return create_layout(
            self.layout_id.get().strip(),
            self.layout_name.get().strip(),
            self._slots(),
        )

    def _preview(self) -> None:
        self.canvas.delete("all")
        try:
            layout = self._layout()
        except (ValueError, tk.TclError) as exc:
            self.canvas.create_text(
                320,
                180,
                text=str(exc),
                fill="#fca5a5",
                width=560,
            )
            return
        width = max(1, int(self.canvas.winfo_width() or 640))
        height = max(1, int(self.canvas.winfo_height() or 360))
        for index, slot in enumerate(layout.slots, start=1):
            x1 = slot.x * width
            y1 = slot.y * height
            x2 = (slot.x + slot.width) * width
            y2 = (slot.y + slot.height) * height
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#38bdf8", width=2)
            self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=f"Painel {index}",
                fill="#f8fafc",
            )

    def _save(self) -> None:
        try:
            layout = self._layout()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Layout inválido", str(exc), parent=self.window)
            return
        if layout.id in self.existing_ids:
            messagebox.showerror(
                "ID já utilizado",
                "Escolha outro identificador para não sobrescrever um layout existente.",
                parent=self.window,
            )
            return
        self.result = layout
        self.window.destroy()
