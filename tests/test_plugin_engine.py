from __future__ import annotations

import json
from pathlib import Path

import pytest

from triview_workspace.domain import PanelKind, PanelSpec
from triview_workspace.engines.panel_runtime import (
    PanelRuntimeAvailability,
    PanelRuntimeSession,
)
from triview_workspace.engines.plugin import (
    PluginEngine,
    PluginEngineError,
    PluginPanelAdapter,
    parse_plugin_target,
)


class FakeApplicationEngine:
    def __init__(self) -> None:
        self.opened: list[tuple[str, str]] = []
        self.sessions: set[str] = set()

    def availability(self, target: str) -> PanelRuntimeAvailability:
        return PanelRuntimeAvailability(True, True, f"ok: {target}")

    def open(
        self,
        panel_id: str,
        target: str,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> PanelRuntimeSession:
        del parent_window_id, width, height
        self.opened.append((panel_id, target))
        self.sessions.add(panel_id)
        return PanelRuntimeSession(panel_id, (target,), None, "1", True, False)

    def has_session(self, panel_id: str) -> bool:
        return panel_id in self.sessions

    def resize(self, panel_id: str, width: int, height: int) -> None:
        del panel_id, width, height

    def close(self, panel_id: str) -> None:
        self.sessions.discard(panel_id)

    def close_all(self) -> None:
        self.sessions.clear()


def write_manifest(root: Path, plugin_id: str, **changes: object) -> Path:
    directory = root / plugin_id
    directory.mkdir(parents=True)
    payload: dict[str, object] = {
        "schema_version": 1,
        "api_version": "1",
        "id": plugin_id,
        "name": "Plugin de teste",
        "description": "Teste",
        "command": "demo-app --safe",
        "allow_arguments": False,
    }
    payload.update(changes)
    path = directory / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_parse_plugin_target() -> None:
    target = parse_plugin_target("plugin:text-editor arquivo.txt")
    assert target.plugin_id == "text-editor"
    assert target.arguments == ("arquivo.txt",)
    with pytest.raises(ValueError):
        parse_plugin_target("text-editor")


def test_valid_plugin_requires_explicit_enable(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    state = tmp_path / "enabled.json"
    write_manifest(root, "text-editor", allow_arguments=True)
    engine = PluginEngine(FakeApplicationEngine(), root, state)  # type: ignore[arg-type]

    diagnostics = engine.diagnostics()
    assert diagnostics[0].valid
    assert not diagnostics[0].enabled
    assert not engine.availability("plugin:text-editor").available

    engine.enable("text-editor")
    assert engine.enabled_ids() == {"text-editor"}
    assert engine.command_for("plugin:text-editor notes.txt") == (
        "demo-app",
        "--safe",
        "notes.txt",
    )
    assert engine.availability("plugin:text-editor").available


def test_plugin_arguments_are_denied_by_manifest(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    state = tmp_path / "enabled.json"
    write_manifest(root, "locked-plugin", allow_arguments=False)
    engine = PluginEngine(FakeApplicationEngine(), root, state)  # type: ignore[arg-type]
    engine.enable("locked-plugin")
    with pytest.raises(PluginEngineError, match="não aceita argumentos"):
        engine.command_for("plugin:locked-plugin extra")


def test_invalid_api_is_diagnosed_without_crashing(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    write_manifest(root, "old-plugin", api_version="0")
    engine = PluginEngine(FakeApplicationEngine(), root, tmp_path / "state.json")  # type: ignore[arg-type]
    diagnostic = engine.diagnostics()[0]
    assert not diagnostic.valid
    assert "API" in diagnostic.message
    with pytest.raises(PluginEngineError):
        engine.enable("old-plugin")


def test_plugin_adapter_never_executes_or_loads_code() -> None:
    adapter = PluginPanelAdapter()
    panel = PanelSpec(
        "custom-1",
        "Plugin",
        PanelKind.CUSTOM,
        "plugin:text-editor notes.txt",
    )
    assert adapter.supports(PanelKind.CUSTOM)
    request = adapter.build_launch_request(panel)
    assert request["plugin_id"] == "text-editor"
    assert request["arguments"] == ("notes.txt",)


def test_plugin_engine_delegates_to_application_runtime(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    write_manifest(root, "text-editor", allow_arguments=True)
    app = FakeApplicationEngine()
    engine = PluginEngine(app, root, tmp_path / "state.json")  # type: ignore[arg-type]
    engine.enable("text-editor")
    session = engine.open("p1", "plugin:text-editor file.txt", 1, 100, 100)
    assert session.embedded
    assert app.opened == [("p1", "demo-app --safe file.txt")]
