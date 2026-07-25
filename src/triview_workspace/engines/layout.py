"""Responsive proportional layout engine."""

from __future__ import annotations

from triview_workspace.domain import LayoutSpec, NormalizedRect, PixelRect


class LayoutEngine:
    """Converts normalized slots to pixel rectangles for the current viewport."""

    def calculate(
        self,
        layout: LayoutSpec,
        viewport_width: int,
        viewport_height: int,
    ) -> tuple[PixelRect, ...]:
        if viewport_width <= 0 or viewport_height <= 0:
            raise ValueError("Viewport dimensions must be greater than zero.")

        return tuple(
            self._slot_to_pixels(slot, viewport_width, viewport_height)
            for slot in layout.slots
        )

    @staticmethod
    def _slot_to_pixels(
        slot: NormalizedRect,
        viewport_width: int,
        viewport_height: int,
    ) -> PixelRect:
        region_x = round(slot.x * viewport_width)
        region_y = round(slot.y * viewport_height)
        region_width = max(1, round(slot.width * viewport_width))
        region_height = max(1, round(slot.height * viewport_height))

        if slot.aspect_ratio is None:
            return PixelRect(region_x, region_y, region_width, region_height)

        current_ratio = region_width / region_height
        if current_ratio > slot.aspect_ratio:
            fitted_height = region_height
            fitted_width = max(1, round(fitted_height * slot.aspect_ratio))
        else:
            fitted_width = region_width
            fitted_height = max(1, round(fitted_width / slot.aspect_ratio))

        return PixelRect(
            x=region_x + (region_width - fitted_width) // 2,
            y=region_y + (region_height - fitted_height) // 2,
            width=fitted_width,
            height=fitted_height,
        )
