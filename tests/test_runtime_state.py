from __future__ import annotations

import json
from pathlib import Path

from triview_workspace.domain import PanelKind, PanelSpec, WorkspaceSpec
from triview_workspace.engines.runtime_state import (
    RuntimeStateRepository,
    RuntimeStateSnapshot,
    SessionRecoveryEngine,
)


def workspace(target: str = "https://example.com") -> WorkspaceSpec:
    return WorkspaceSpec(
        "workspace",
        "Workspace",
        "layout",
        (
            PanelSpec("browser", "Browser", PanelKind.BROWSER, target),
            PanelSpec("terminal", "Terminal", PanelKind.TERMINAL, "bash"),
        ),
    )


def test_runtime_state_roundtrip_does_not_persist_raw_targets(tmp_path: Path) -> None:
    repository = RuntimeStateRepository(tmp_path / "runtime.json")
    engine = SessionRecoveryEngine(repository, RuntimeStateSnapshot.empty())
    current = workspace("https://private.example/path?token=secret")

    engine.sync(
        current,
        {"browser": ("browser", True, False)},
        clean_shutdown=False,
    )

    text = repository.path.read_text(encoding="utf-8")
    assert "private.example" not in text
    assert "token=secret" not in text
    loaded = repository.load()
    assert loaded.clean_shutdown is False
    assert loaded.workspace("workspace") is not None
    assert loaded.workspace("workspace").panels[0].was_open is True  # type: ignore[union-attr]


def test_recovery_plan_filters_changed_panel_configuration(tmp_path: Path) -> None:
    repository = RuntimeStateRepository(tmp_path / "runtime.json")
    engine = SessionRecoveryEngine(repository, RuntimeStateSnapshot.empty())
    original = workspace()
    engine.finish(
        original,
        {
            "browser": ("browser", True, False),
            "terminal": ("terminal", False, True),
        },
    )

    loaded = SessionRecoveryEngine(repository, repository.load())
    unchanged = loaded.recovery_plan(original)
    assert unchanged.previous_clean_shutdown is True
    assert unchanged.panel_ids == ("browser", "terminal")

    changed = loaded.recovery_plan(workspace("https://changed.example"))
    assert changed.panel_ids == ("terminal",)


def test_begin_marks_dirty_and_finish_marks_clean(tmp_path: Path) -> None:
    repository = RuntimeStateRepository(tmp_path / "runtime.json")
    engine = SessionRecoveryEngine(repository, RuntimeStateSnapshot.empty())
    current = workspace()

    engine.begin(current)
    assert repository.load().clean_shutdown is False

    engine.finish(current, {"terminal": ("terminal", True, False)})
    loaded = repository.load()
    assert loaded.clean_shutdown is True
    assert loaded.workspace("workspace").panels[1].was_open is True  # type: ignore[union-attr]


def test_invalid_runtime_state_is_quarantined(tmp_path: Path) -> None:
    path = tmp_path / "runtime.json"
    path.write_text("{invalid", encoding="utf-8")
    repository = RuntimeStateRepository(path)

    snapshot = repository.load_or_recover()

    assert snapshot.clean_shutdown is True
    assert repository.last_recovery_message is not None
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert len(tuple(tmp_path.glob("runtime.json.invalid-*"))) == 1
