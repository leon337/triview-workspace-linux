from pathlib import Path

from triview_workspace.cli import build_parser


def test_cli_restores_persisted_workspace_by_default() -> None:
    args = build_parser().parse_args([])
    assert args.diagnostic is False
    assert args.workspace is None
    assert args.data_file is None


def test_cli_keeps_explicit_diagnostic_mode() -> None:
    args = build_parser().parse_args(
        [
            "--diagnostic",
            "--width",
            "900",
            "--height",
            "600",
            "--data-file",
            "/tmp/triview-test.json",
        ]
    )
    assert args.diagnostic is True
    assert args.width == 900
    assert args.height == 600
    assert args.data_file == Path("/tmp/triview-test.json")
