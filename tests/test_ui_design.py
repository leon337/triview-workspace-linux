from triview_workspace.ui_design import (
    APP_BADGE_TEXT,
    PALETTE,
    header_layout_mode,
    status_color,
)


def test_header_uses_compact_mode_on_small_notebook_width() -> None:
    assert header_layout_mode(1024) == "compact"


def test_header_uses_wide_mode_on_desktop_width() -> None:
    assert header_layout_mode(1366) == "wide"


def test_status_colors_are_semantic_and_deterministic() -> None:
    assert status_color("ATIVO") == PALETTE.success
    assert status_color("ERRO") == PALETTE.danger
    assert status_color("desconhecido") == PALETTE.neutral


def test_product_badge_uses_package_version() -> None:
    assert APP_BADGE_TEXT.startswith("TRIVIEW 1.0.0")
