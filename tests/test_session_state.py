from __future__ import annotations

import json
import stat
from pathlib import Path

from triview_workspace.domain import (
    LayoutSpec,
    NormalizedRect,
    PanelKind,
    PanelSpec,
    WorkspaceSpec,
)
from triview_workspace.infrastructure import (
    SESSION_SCHEMA_VERSION,
    SessionStateRepository,
    WorkspaceCatalog,
    apply_snapshot_to_workspace,
    restore_catalog_sessions,
    snapshot_from_workspace,
)


def _layout() -> LayoutSpec:
    return LayoutSpec(
        id="layout-main",
        name="Principal",
        slots=(
            NormalizedRect(0.0, 0.0, 0.5, 1.0),
            NormalizedRect(0.5, 0.0, 0.5, 1.0),
        ),
    )


def _workspace(workspace_id: str = "work-main") -> WorkspaceSpec:
    return WorkspaceSpec(
        id=workspace_id,
        name="Trabalho",
        layout_id="layout-main",
        panels=(
            PanelSpec(
                id="browser-main",
                title="Navegador",
                kind=PanelKind.BROWSER,
                target="https://example.test/inicial",
            ),
            PanelSpec(
                id="terminal-main",
                title="Terminal",
                kind=PanelKind.TERMINAL,
                target="bash -l",
                metadata={"working_directory": "/tmp/original"},
            ),
        ),
    )


def test_session_roundtrip_restores_supported_state_without_secrets(tmp_path: Path) -> None:
    repository = SessionStateRepository(tmp_path / "sessions")
    workspace = _workspace()
    snapshot = snapshot_from_workspace(
        workspace,
        focused_panel_id="terminal-main",
        view_mode="focus",
        runtime_states={
            "browser-main": {
                "url": "https://example.test/app?page=2&access_token=private#secret",
                "cookie": "must-not-persist",
                "password": "must-not-persist",
            },
            "terminal-main": {"working_directory": "/tmp/project"},
        },
    )

    path = repository.save(snapshot)
    result = repository.load(workspace.id)

    assert result.diagnostics == ()
    assert result.snapshot is not None
    assert result.snapshot.schema_version == SESSION_SCHEMA_VERSION
    assert result.snapshot.focused_panel_id == "terminal-main"
    assert result.snapshot.view_mode == "focus"
    browser_state = result.snapshot.panels[0].state
    assert browser_state == {"url": "https://example.test/app?page=2"}
    assert "private" not in path.read_text(encoding="utf-8")
    assert "must-not-persist" not in path.read_text(encoding="utf-8")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    restored, diagnostics = apply_snapshot_to_workspace(workspace, result.snapshot)
    assert diagnostics == ()
    assert restored.panels[0].target == "https://example.test/app?page=2"
    assert restored.panels[1].metadata["working_directory"] == "/tmp/project"


def test_incompatible_schema_is_ignored_with_diagnostic(tmp_path: Path) -> None:
    repository = SessionStateRepository(tmp_path / "sessions")
    path = repository.path_for("work-main")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "workspace_id": "work-main",
                "layout_id": "layout-main",
                "panels": [],
            }
        ),
        encoding="utf-8",
    )

    result = repository.load("work-main")

    assert result.snapshot is None
    assert result.diagnostics
    assert "esquema 999" in result.diagnostics[0]
    assert path.exists()


def test_invalid_panel_entry_does_not_block_valid_session_state(tmp_path: Path) -> None:
    repository = SessionStateRepository(tmp_path / "sessions")
    path = repository.path_for("work-main")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": SESSION_SCHEMA_VERSION,
                "workspace_id": "work-main",
                "layout_id": "layout-main",
                "focused_panel_id": "browser-main",
                "view_mode": "all",
                "saved_at": "2026-07-29T00:00:00+00:00",
                "panels": [
                    {
                        "panel_id": "../../unsafe",
                        "kind": "browser",
                        "state": {"url": "https://invalid.test"},
                    },
                    {
                        "panel_id": "browser-main",
                        "kind": "browser",
                        "state": {"url": "https://example.test/restored"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = repository.load("work-main")

    assert result.snapshot is not None
    assert len(result.snapshot.panels) == 1
    assert result.snapshot.panels[0].panel_id == "browser-main"
    assert result.diagnostics
    restored, _ = apply_snapshot_to_workspace(_workspace(), result.snapshot)
    assert restored.panels[0].target == "https://example.test/restored"


def test_corrupt_workspace_session_is_quarantined_without_blocking_catalog(
    tmp_path: Path,
) -> None:
    repository = SessionStateRepository(tmp_path / "sessions")
    first = _workspace("work-first")
    second = _workspace("work-second")
    catalog = WorkspaceCatalog(
        schema_version=1,
        active_workspace_id=first.id,
        layouts=(_layout(),),
        workspaces=(first, second),
    )
    repository.save(
        snapshot_from_workspace(
            first,
            runtime_states={
                "browser-main": {"url": "https://example.test/recovered"}
            },
        )
    )
    broken = repository.path_for(second.id)
    broken.write_text("{not-json", encoding="utf-8")

    restored, diagnostics = restore_catalog_sessions(catalog, repository)

    assert restored.workspace_by_id(first.id).panels[0].target == (
        "https://example.test/recovered"
    )
    assert restored.workspace_by_id(second.id) == second
    assert diagnostics
    assert not broken.exists()
    assert list(repository.root.glob("work-second.invalid-*.json"))
