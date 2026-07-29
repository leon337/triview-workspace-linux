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
from triview_workspace.ui_design import (
    FONT_FAMILY,
    MONO_FONT_FAMILY,
    PALETTE,
    button_colors,
)


def _button(parent: tk.Misc, text: str, command, *, primary: bool = False) -> tk.Button:
    colors = button_colors("primary" if primary else "secondary")
    return tk.Button(
        parent,
        text=text,
        command=command,
        relief="flat",
        bd=0,
        highlightthickness=0,
        font=(FONT_FAMILY, 8, "bold"),
        padx=11,
        pady=6,
        cursor="hand2",
        **colors,
    )


def _entry(parent: tk.Misc, variable: tk.Variable, width: int) -> tk.Entry:
    return tk.Entry(
        parent,
        textvariable=variable,
        width=width,
        background=PALETTE.surface_raised,
        foreground=PALETTE.text,
        insertbackground=PALETTE.text,
        selectbackground=PALETTE.accent_dark,
        selectforeground=PALETTE.text,
        highlightbackground=PALETTE.border,
        highlightcolor=PALETTE.border_focus,
        highlightthickness=1,
        relief="flat",
        bd=0,
        font=(MONO_FONT_FAMILY, 8),
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
        self.window.configure(background=PALETTE.app)
        self.window.geometry("900x680")
        self.window.minsize(760, 560)
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
        shell = tk.Frame(
            self.window,
            background=PALETTE.surface,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
        )
        shell.pack(fill="both", expand=True, padx=16, pady=16)

        heading = tk.Frame(shell, background=PALETTE.surface)
        heading.pack(fill="x", padx=16, pady=(16, 12))
        tk.Label(
            heading,
            text="Editor de layout",
            background=PALETTE.surface,
            foreground=PALETTE.text,
            font=(FONT_FAMILY, 16, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            heading,
            text="Defina posições normalizadas e valide a composição em tempo real.",
            background=PALETTE.surface,
            foreground=PALETTE.text_muted,
            font=(FONT_FAMILY, 9),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        form = tk.Frame(shell, background=PALETTE.surface)
        form.pack(fill="x", padx=16, pady=(0, 12))
        for column, label in enumerate(("ID", "Nome", "Preset")):
            tk.Label(
                form,
                text=label.upper(),
                background=PALETTE.surface,
                foreground=PALETTE.text_subtle,
                font=(FONT_FAMILY, 7, "bold"),
            ).grid(row=0, column=column, sticky="w", padx=(0, 10), pady=(0, 5))
        _entry(form, self.layout_id, 24).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=(0, 10),
            ipady=6,
        )
        _entry(form, self.layout_name, 30).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(0, 10),
            ipady=6,
        )
        values = ["columns", "stack", "grid", "focus-left"]
        if self.panel_count == 3:
            values.append("two-plus-one")
        preset = ttk.Combobox(
            form,
            textvariable=self.preset,
            values=values,
            state="readonly",
            width=22,
            style="TriView.TCombobox",
        )
        preset.grid(row=1, column=2, sticky="ew", padx=(0, 10), ipady=3)
        _button(form, "Aplicar preset", self._apply_preset).grid(
            row=1,
            column=3,
            sticky="ew",
        )
        form.columnconfigure(1, weight=1)

        editor_shell = tk.Frame(
            shell,
            background=PALETTE.surface_raised,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
        )
        editor_shell.pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(
            editor_shell,
            text="COORDENADAS DOS SLOTS",
            background=PALETTE.surface_raised,
            foreground=PALETTE.text_subtle,
            font=(FONT_FAMILY, 7, "bold"),
            anchor="w",
            padx=12,
            pady=10,
        ).pack(fill="x")

        editor = tk.Frame(editor_shell, background=PALETTE.surface)
        editor.pack(fill="x", padx=8, pady=(0, 8))
        for column, label in enumerate(("Slot", "X", "Y", "Largura", "Altura")):
            tk.Label(
                editor,
                text=label.upper(),
                background=PALETTE.surface,
                foreground=PALETTE.text_subtle,
                font=(FONT_FAMILY, 7, "bold"),
            ).grid(row=0, column=column, padx=6, pady=6, sticky="w")
        for index in range(self.panel_count):
            variables = tuple(tk.DoubleVar(value=0.0) for _ in range(4))
            self.rows.append(variables)  # type: ignore[arg-type]
            tk.Label(
                editor,
                text=f"{index + 1:02d}",
                background=PALETTE.surface,
                foreground=PALETTE.accent_hover,
                font=(MONO_FONT_FAMILY, 8, "bold"),
            ).grid(row=index + 1, column=0, padx=6, pady=5, sticky="w")
            for column, variable in enumerate(variables, start=1):
                _entry(editor, variable, 12).grid(
                    row=index + 1,
                    column=column,
                    padx=6,
                    pady=5,
                    sticky="ew",
                    ipady=5,
                )
                editor.columnconfigure(column, weight=1)

        preview_shell = tk.Frame(
            shell,
            background=PALETTE.surface_raised,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
        )
        preview_shell.pack(fill="both", expand=True, padx=16)
        tk.Label(
            preview_shell,
            text="PRÉVIA RESPONSIVA",
            background=PALETTE.surface_raised,
            foreground=PALETTE.text_subtle,
            font=(FONT_FAMILY, 7, "bold"),
            anchor="w",
            padx=12,
            pady=10,
        ).pack(fill="x")
        self.canvas = tk.Canvas(
            preview_shell,
            width=640,
            height=360,
            background=PALETTE.app,
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.canvas.bind("<Configure>", lambda _event: self._preview())

        actions = tk.Frame(shell, background=PALETTE.surface)
        actions.pack(fill="x", padx=16, pady=16)
        _button(actions, "Atualizar prévia", self._preview).pack(side="left")
        _button(actions, "Cancelar", self.window.destroy).pack(
            side="right",
            padx=(8, 0),
        )
        _button(actions, "Salvar layout", self._save, primary=True).pack(side="right")

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
            width = max(1, int(self.canvas.winfo_width() or 640))
            height = max(1, int(self.canvas.winfo_height() or 360))
            self.canvas.create_text(
                width / 2,
                height / 2,
                text=str(exc),
                fill="#fca5a5",
                width=max(120, width - 80),
            )
            return
        width = max(1, int(self.canvas.winfo_width() or 640))
        height = max(1, int(self.canvas.winfo_height() or 360))
        margin = 12
        usable_width = max(1, width - margin * 2)
        usable_height = max(1, height - margin * 2)
        for index, slot in enumerate(layout.slots, start=1):
            x1 = margin + slot.x * usable_width
            y1 = margin + slot.y * usable_height
            x2 = margin + (slot.x + slot.width) * usable_width
            y2 = margin + (slot.y + slot.height) * usable_height
            self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline=PALETTE.accent_hover,
                fill=PALETTE.surface_soft,
                width=2,
            )
            self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=f"PAINEL {index}",
                fill=PALETTE.text,
                font=(FONT_FAMILY, 9, "bold"),
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
