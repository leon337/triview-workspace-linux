from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from triview_workspace.cli import DEFAULT_WORKSPACE, build_parser, resolve_workspace
from triview_workspace.infrastructure import (
    WorkspaceRepository,
    load_workspace_bundle,
    workspace_bundle_to_dict,
)


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


def test_explicit_diagnostic_bundle_does_not_change_persisted_active_workspace(
    tmp_path: Path,
) -> None:
    seed_workspace, seed_layout = load_workspace_bundle(DEFAULT_WORKSPACE)
    data_file = tmp_path / "workspaces.json"
    repository = WorkspaceRepository(data_file)
    catalog = repository.load_or_bootstrap(seed_workspace, seed_layout)
    second = replace(seed_workspace, id="second", name="Segundo")
    repository.save_workspace(catalog, second, make_active=True)

    explicit_bundle = tmp_path / "explicit.json"
    explicit_bundle.write_text(
        json.dumps(workspace_bundle_to_dict(seed_workspace, seed_layout)),
        encoding="utf-8",
    )

    _, catalog_after, inspected, _ = resolve_workspace(explicit_bundle, data_file)

    assert inspected.id == seed_workspace.id
    assert catalog_after.active_workspace_id == "second"
    assert repository.load().active_workspace_id == "second"
