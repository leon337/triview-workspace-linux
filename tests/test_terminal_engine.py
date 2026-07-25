from __future__ import annotations

import pytest

from triview_workspace.domain import PanelKind, PanelSpec
from triview_workspace.engines.panel_runtime import (
    PanelRuntimeAvailability,
    PanelRuntimeLaunchRequest,
    PanelRuntimeSession,
)
from triview_workspace.engines.terminal import (
    TerminalEngine,
    TerminalPanelAdapter,
    X11TerminalBackend,
)


class FakeRuntime:
    def __init__(self, *, embedded: bool = True) -> None:
        self.embedded = embedded
        self.requests: list[PanelRuntimeLaunchRequest] = []
        self.resizes: list[tuple[str, int, int]] = []
        self.closed: list[str] = []

    def availability(self, command: tuple[str, ...]) -> PanelRuntimeAvailability:
        return PanelRuntimeAvailability(True, self.embedded, "ok", executable=command[0])

    def launch(
        self,
        request: PanelRuntimeLaunchRequest,
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        del parent_window_id
        self.requests.append(request)
        return PanelRuntimeSession(
            panel_id=request.panel_id,
            command=request.command,
            process=None,
            window_id="321" if self.embedded else None,
            embedded=self.embedded,
            external=not self.embedded,
        )

    def resize(self, session: PanelRuntimeSession, width: int, height: int) -> None:
        self.resizes.append((session.panel_id, width, height))

    def close(self, session: PanelRuntimeSession) -> None:
        self.closed.append(session.panel_id)


def test_terminal_adapter_supports_terminal_and_validates_shell() -> None:
    adapter = TerminalPanelAdapter()
    panel = PanelSpec(
        id="terminal-1",
        title="Terminal",
        kind=PanelKind.TERMINAL,
        target="bash --noprofile",
    )
    assert adapter.supports(PanelKind.TERMINAL)
    request = adapter.build_launch_request(panel)
    assert request["shell_command"] == ("bash", "--noprofile")


def test_terminal_backend_builds_xterm_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = FakeRuntime()
    backend = X11TerminalBackend(runtime)  # type: ignore[arg-type]
    monkeypatch.setattr(backend, "_terminal_emulator", lambda: "/usr/bin/xterm")
    monkeypatch.setattr(
        "triview_workspace.engines.terminal.resolve_command",
        lambda command: ("/usr/bin/bash",),
    )

    session = backend.launch("term-1", "Meu Terminal", ("bash",), 99)

    assert session.embedded
    assert runtime.requests[0].command == (
        "/usr/bin/xterm",
        "-T",
        "Meu Terminal",
        "-e",
        "/usr/bin/bash",
    )


def test_terminal_engine_manages_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = FakeRuntime()
    backend = X11TerminalBackend(runtime)  # type: ignore[arg-type]
    engine = TerminalEngine(backend)
    monkeypatch.setattr(backend, "_terminal_emulator", lambda: "/usr/bin/xterm")
    monkeypatch.setattr(
        "triview_workspace.engines.terminal.resolve_command",
        lambda command: ("/usr/bin/bash",),
    )

    session = engine.open("term-1", "Terminal", "bash", 99, 640, 480)

    assert session.embedded
    assert engine.has_session("term-1")
    assert runtime.resizes == [("term-1", 640, 480)]
    engine.resize("term-1", 800, 600)
    assert runtime.resizes[-1] == ("term-1", 800, 600)
    engine.close_all()
    assert runtime.closed == ["term-1"]


def test_terminal_backend_reports_missing_emulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11TerminalBackend(FakeRuntime())  # type: ignore[arg-type]
    monkeypatch.setattr(backend, "_terminal_emulator", lambda: None)
    monkeypatch.setattr(
        "triview_workspace.engines.terminal.resolve_command",
        lambda command: ("/usr/bin/bash",),
    )

    report = backend.availability(("bash",))

    assert report.available is False
    assert "Nenhum emulador" in report.reason
