from triview_workspace.gui_rc4 import (
    GLOBAL_BAR_RATIO,
    PANEL_HEADER_RATIO,
    WorkspaceWindow,
    global_bar_height,
    panel_header_height,
)


def test_global_bar_uses_four_percent_of_available_height() -> None:
    assert GLOBAL_BAR_RATIO == 0.04
    assert global_bar_height(1000) == 40
    assert global_bar_height(820) == 33


def test_panel_header_is_derived_from_panel_height() -> None:
    assert PANEL_HEADER_RATIO == 0.04
    assert panel_header_height(1000) == 40
    assert panel_header_height(600) == 24


def test_view_controls_remain_in_the_global_bar() -> None:
    assert WorkspaceWindow.VIEW_ACTIONS == {
        "view-all": ("▥", "Mostrar todos os painéis"),
        "view-dual": ("◫", "Dividir em dois painéis"),
        "view-focus": ("▣", "Mostrar um painel"),
    }
