import pytest

from triview_workspace.gui_focus import dual_orientation, select_visible_panel_ids


def test_all_mode_keeps_every_panel_in_original_order() -> None:
    panel_ids = ("chatgpt", "github", "terminal")

    assert select_visible_panel_ids(panel_ids, "all", "github") == panel_ids


def test_focus_mode_uses_requested_panel() -> None:
    panel_ids = ("chatgpt", "github", "terminal")

    assert select_visible_panel_ids(panel_ids, "focus", "github") == ("github",)


def test_focus_mode_falls_back_to_first_panel() -> None:
    panel_ids = ("chatgpt", "github", "terminal")

    assert select_visible_panel_ids(panel_ids, "focus", "missing") == ("chatgpt",)


def test_dual_mode_uses_focus_and_next_panel_cyclically() -> None:
    panel_ids = ("chatgpt", "github", "terminal")

    assert select_visible_panel_ids(panel_ids, "dual", "github") == (
        "github",
        "terminal",
    )
    assert select_visible_panel_ids(panel_ids, "dual", "terminal") == (
        "terminal",
        "chatgpt",
    )


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="Modo de visualização desconhecido"):
        select_visible_panel_ids(("chatgpt",), "grid", "chatgpt")


def test_dual_orientation_preserves_useful_space() -> None:
    assert dual_orientation(1366, 700) == "horizontal"
    assert dual_orientation(760, 900) == "vertical"
