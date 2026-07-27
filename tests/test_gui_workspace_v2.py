from __future__ import annotations

import pytest

from triview_workspace.gui_workspace_v2 import calculate_wide_grid


def test_three_panels_use_the_full_desktop_width() -> None:
    rects = calculate_wide_grid(3, 1366, 680)

    assert len(rects) == 3
    assert all(rect.width >= 440 for rect in rects)
    assert all(rect.height == 664 for rect in rects)
    assert rects[0].x == 8
    assert rects[-1].x + rects[-1].width == 1358


def test_single_panel_uses_the_complete_content_area() -> None:
    (rect,) = calculate_wide_grid(1, 1200, 700)

    assert rect.x == 8
    assert rect.y == 8
    assert rect.width == 1184
    assert rect.height == 684


def test_more_than_three_panels_create_a_balanced_grid() -> None:
    rects = calculate_wide_grid(4, 1200, 700)

    assert len(rects) == 4
    assert rects[0].y == rects[1].y
    assert rects[2].y > rects[0].y
    assert rects[0].width >= 580
    assert rects[0].height >= 330


def test_invalid_viewport_is_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_wide_grid(3, 0, 700)
