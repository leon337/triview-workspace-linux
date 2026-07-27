from __future__ import annotations

import pytest

from triview_workspace.gui_workspace_v2 import (
    calculate_percentage_slots,
    calculate_wide_grid,
)


def test_three_panels_use_exact_horizontal_thirds_and_96_percent_height() -> None:
    slots = calculate_percentage_slots(3)

    assert len(slots) == 3
    assert slots[0].x == pytest.approx(0.0)
    assert slots[1].x == pytest.approx(1 / 3)
    assert slots[2].x == pytest.approx(2 / 3)
    assert all(slot.width == pytest.approx(1 / 3) for slot in slots)
    assert all(slot.y == pytest.approx(0.02) for slot in slots)
    assert all(slot.height == pytest.approx(0.96) for slot in slots)


def test_pixel_conversion_preserves_the_percentage_contract() -> None:
    rects = calculate_wide_grid(3, 1366, 700)

    assert len(rects) == 3
    assert rects[0].x == 0
    assert rects[-1].x + rects[-1].width == 1366
    assert sum(rect.width for rect in rects) == 1366
    assert all(rect.y == 14 for rect in rects)
    assert all(rect.height == 672 for rect in rects)


def test_single_panel_uses_full_width_and_96_percent_height() -> None:
    (rect,) = calculate_wide_grid(1, 1200, 700)

    assert rect.x == 0
    assert rect.y == 14
    assert rect.width == 1200
    assert rect.height == 672


def test_more_than_three_panels_create_a_percentage_grid() -> None:
    slots = calculate_percentage_slots(4)

    assert len(slots) == 4
    assert all(slot.width == pytest.approx(0.5) for slot in slots)
    assert all(slot.height == pytest.approx(0.48) for slot in slots)
    assert slots[0].y == pytest.approx(0.02)
    assert slots[2].y == pytest.approx(0.50)


def test_invalid_viewport_is_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_wide_grid(3, 0, 700)


@pytest.mark.parametrize("vertical_share", [0, -0.1, 1.01])
def test_invalid_vertical_share_is_rejected(vertical_share: float) -> None:
    with pytest.raises(ValueError):
        calculate_percentage_slots(3, vertical_share=vertical_share)
