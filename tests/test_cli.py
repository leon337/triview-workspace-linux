from pathlib import Path

from triview_workspace.cli import build_parser


def test_cli_opens_gui_by_default() -> None:
    args = build_parser().parse_args([])
    assert args.diagnostic is False
    assert args.workspace == Path("config/workspaces/three-mobile.json")


def test_cli_keeps_explicit_diagnostic_mode() -> None:
    args = build_parser().parse_args(
        ["--diagnostic", "--width", "900", "--height", "600"]
    )
    assert args.diagnostic is True
    assert args.width == 900
    assert args.height == 600
