from __future__ import annotations

import pytest

from triview_workspace.domain import PanelKind, PanelSpec
from triview_workspace.engines.application import ApplicationEngine, ApplicationPanelAdapter
from triview_workspace.engines.panel_runtime import (
    PanelRuntimeAvailability,
    PanelRuntimeLaunchRequest,
    PanelRuntimeSession,
)


class FakeApplicationBackend:
    def __init__(self, *, embedded: bool = True) -> None:
        self.embedded = embedded
        self.launched: list[PanelRuntimeLaunchRequest] = []
        self.resized: list[tuple[str, int, int]] = []
        self.closed: list[str] = []

    def availability(self, command: tuple[str, ...]) -> PanelRuntimeAvailability:
        return PanelRuntimeAvailability(
            True,
            self.embedded,
            "ok",
            executable=command[0],
            xdotool_command="/usr/bin/xdotool" if self.embedded else None,
        )

    def launch(
        self,
        request: PanelRuntimeLaunchRequest,
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        del parent_window_id
        self.launched.append(request)
        return PanelRuntimeSession(
            panel_id=request.panel_id,
            command=request.command,
            process=None,
            window_id="123" if self.embedded else None,
            embedded=self.embedded,
            external=not self.embedded,
        )

    def resize(self, session: PanelRuntimeSession, width: int, height: int) -> None:
        self.resized.append((session.panel_id, width, height))

    def close(self, session: PanelRuntimeSession) -> None:
        self.closed.append(session.panel_id)


def test_application_adapter_prepares_command_without_shell() -> None:
    adapter = ApplicationPanelAdapter()
    panel = PanelSpec(
        id="editor",
        title="Editor",
        kind=PanelKind.APPLICATION,
        target='python3 -c "print(1)"',
    )

    assert adapter.supports(PanelKind.APPLICATION)
    request = adapter.build_launch_request(panel)

    assert request["mode"] == "application"
    assert request["command"] == ("python3", "-c", "print(1)")


def test_application_engine_manages_embedded_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = FakeApplicationBackend(embedded=True)
    engine = ApplicationEngine(backend)
    monkeypatch.setattr(
        "triview_workspace.engines.application.resolve_command",
        lambda value: ("/usr/bin/demo-app", "--demo"),
    )

    session = engine.open("app-1", "demo-app --demo", 99, 640, 480)

    assert session.embedded is True
    assert engine.has_session("app-1")
    assert backend.launched[0].command == ("/usr/bin/demo-app", "--demo")
    assert backend.resized == [("app-1", 640, 480)]

    engine.resize("app-1", 800, 600)
    assert backend.resized[-1] == ("app-1", 800, 600)

    engine.close("app-1")
    assert not engine.has_session("app-1")
    assert backend.closed == ["app-1"]


def test_application_engine_replaces_previous_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = FakeApplicationBackend()
    engine = ApplicationEngine(backend)
    monkeypatch.setattr(
        "triview_workspace.engines.application.resolve_command",
        lambda value: ("/usr/bin/demo-app",),
    )

    engine.open("app-1", "demo-app", 1, 100, 100)
    engine.open("app-1", "demo-app", 1, 100, 100)

    assert backend.closed == ["app-1"]
    assert len(backend.launched) == 2


def test_application_engine_accepts_external_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = FakeApplicationBackend(embedded=False)
    engine = ApplicationEngine(backend)
    monkeypatch.setattr(
        "triview_workspace.engines.application.resolve_command",
        lambda value: ("/usr/bin/demo-app",),
    )

    session = engine.open("app-1", "demo-app", 1, 100, 100)

    assert session.external is True
    assert session.embedded is False
    assert backend.resized == []
