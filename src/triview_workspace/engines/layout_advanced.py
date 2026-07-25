"""Validated presets, responsive breakpoints and custom layout construction."""

from __future__ import annotations

import math
import re
from dataclasses import replace

from triview_workspace.domain import LayoutSpec, NormalizedRect, PixelRect, Viewport
from triview_workspace.engines.layout import LayoutEngine

_LAYOUT_ID = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_EPSILON = 1e-9


class LayoutValidationError(ValueError):
    """Raised when a persisted or edited layout is unsafe or ambiguous."""


def validate_layout(layout: LayoutSpec) -> LayoutSpec:
    """Validate bounds and reject overlapping normalized slots."""

    if not _LAYOUT_ID.fullmatch(layout.id):
        raise LayoutValidationError(
            "O ID do layout precisa usar letras minúsculas, números e hífens."
        )
    if not layout.name.strip():
        raise LayoutValidationError("O layout precisa de um nome.")
    for index, slot in enumerate(layout.slots, start=1):
        if slot.x < 0 or slot.y < 0:
            raise LayoutValidationError(f"O slot {index} começa fora da área normalizada.")
        if slot.x + slot.width > 1 + _EPSILON:
            raise LayoutValidationError(f"O slot {index} ultrapassa a largura normalizada.")
        if slot.y + slot.height > 1 + _EPSILON:
            raise LayoutValidationError(f"O slot {index} ultrapassa a altura normalizada.")
    for first_index, first in enumerate(layout.slots):
        for second_index in range(first_index + 1, len(layout.slots)):
            second = layout.slots[second_index]
            if _overlap(first, second):
                raise LayoutValidationError(
                    f"Os slots {first_index + 1} e {second_index + 1} se sobrepõem."
                )
    return layout


def create_layout(
    layout_id: str,
    name: str,
    slots: tuple[NormalizedRect, ...],
) -> LayoutSpec:
    return validate_layout(LayoutSpec(layout_id.strip(), name.strip(), slots))


def preset_slots(preset: str, panel_count: int) -> tuple[NormalizedRect, ...]:
    if panel_count <= 0:
        raise LayoutValidationError("O layout precisa de ao menos um painel.")
    normalized = preset.strip().lower()
    if normalized == "columns":
        width = 1 / panel_count
        return tuple(
            NormalizedRect(index * width, 0, width, 1)
            for index in range(panel_count)
        )
    if normalized == "stack":
        height = 1 / panel_count
        return tuple(
            NormalizedRect(0, index * height, 1, height)
            for index in range(panel_count)
        )
    if normalized == "grid":
        columns = math.ceil(math.sqrt(panel_count))
        rows = math.ceil(panel_count / columns)
        width = 1 / columns
        height = 1 / rows
        return tuple(
            NormalizedRect((index % columns) * width, (index // columns) * height, width, height)
            for index in range(panel_count)
        )
    if normalized == "two-plus-one" and panel_count == 3:
        return (
            NormalizedRect(0, 0, 0.5, 0.5),
            NormalizedRect(0.5, 0, 0.5, 0.5),
            NormalizedRect(0, 0.5, 1, 0.5),
        )
    if normalized == "focus-left":
        if panel_count == 1:
            return (NormalizedRect(0, 0, 1, 1),)
        side_height = 1 / (panel_count - 1)
        return (
            NormalizedRect(0, 0, 0.68, 1),
            *tuple(
                NormalizedRect(0.68, index * side_height, 0.32, side_height)
                for index in range(panel_count - 1)
            ),
        )
    raise LayoutValidationError(
        f"O preset '{preset}' não é compatível com {panel_count} painel(is)."
    )


def build_preset_layout(
    preset: str,
    panel_count: int,
    layout_id: str,
    name: str,
) -> LayoutSpec:
    return create_layout(layout_id, name, preset_slots(preset, panel_count))


def _overlap(first: NormalizedRect, second: NormalizedRect) -> bool:
    return (
        first.x < second.x + second.width - _EPSILON
        and second.x < first.x + first.width - _EPSILON
        and first.y < second.y + second.height - _EPSILON
        and second.y < first.y + first.height - _EPSILON
    )


class ResponsiveLayoutEngine(LayoutEngine):
    """Use persisted wide layouts and derived medium/narrow variants."""

    def __init__(self, narrow_breakpoint: int = 760, wide_breakpoint: int = 1100) -> None:
        self.narrow_breakpoint = narrow_breakpoint
        self.wide_breakpoint = wide_breakpoint

    def arrange(self, layout: LayoutSpec, viewport: Viewport) -> tuple[PixelRect, ...]:
        validated = validate_layout(layout)
        responsive = self._responsive_variant(validated, viewport)
        return super().arrange(responsive, viewport)

    def _responsive_variant(self, layout: LayoutSpec, viewport: Viewport) -> LayoutSpec:
        count = len(layout.slots)
        if viewport.width >= self.wide_breakpoint:
            return layout
        if viewport.width < self.narrow_breakpoint:
            slots = preset_slots("stack", count)
        elif count == 3:
            slots = preset_slots("two-plus-one", count)
        elif count >= 4:
            slots = preset_slots("grid", count)
        else:
            slots = preset_slots("columns", count)
        # Derived variants should fill the available area rather than preserve
        # phone aspect ratios inherited from a wide-screen layout.
        slots = tuple(replace(slot, aspect_ratio=None) for slot in slots)
        return LayoutSpec(layout.id, layout.name, slots)
