from __future__ import annotations

from typing import Any

from triview_workspace.engines.panel_runtime import PanelRuntimeSession
from triview_workspace.engines.terminal_embedded import (
    EmbeddedFirstX11PanelRuntimeBackend,
    EmbeddedOnlyTerminalBackend,
)
from triview_workspace.gui_rc4_runtime import (
    deferred_menu_action,
    parse_work_area,
    proportional_panel_bounds,
)


class _FakeRoot:
    def __init__(self) -> None:
        self.events: list[object] = []

    def update_idletasks(self) -> None:
        self.events.append("idle")

    def after(self, delay: int, command: Any) -> None:
        self.events.append(("after", delay))
        command()


class _FakeMenu:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def unpost(self) -> None:
        self.events.append("unpost")

    def grab_release(self) -> None:
        self.events.append("release")


class _FakeProcess:
    pid = 1234

    @staticmethod
    def poll() -> None:
        return None


class _FakeRuntime:
    def __init__(self) -> None:
        self.request = None
        self.parent_window_id = None

    def launch(self, request: Any, parent_window_id: int) -> PanelRuntimeSession:
        self.request = request
        self.parent_window_id = parent_window_id
        return PanelRuntimeSession(
            panel_id=request.panel_id,
            command=request.command,
            process=None,
            window_id="99",
            embedded=True,
            external=False,
        )


def test_menu_action_releases_grab_before_capture() -> None:
    root = _FakeRoot()
    menu = _FakeMenu(root.events)
    action = deferred_menu_action(
        root,  # type: ignore[arg-type]
        menu,  # type: ignore[arg-type]
        lambda: root.events.append("capture"),
    )

    action()

    assert root.events == ["unpost", "release", "idle", ("after", 120), "capture"]


def test_three_panels_fill_the_complete_workspace_width() -> None:
    bounds = proportional_panel_bounds(1366, 3)

    assert bounds[0][0] == 0
    assert bounds[-1][0] + bounds[-1][1] == 1366
    assert sum(width for _x, width in bounds) == 1366
    assert max(width for _x, width in bounds) - min(width for _x, width in bounds) <= 1
    assert all(
        bounds[index][0] + bounds[index][1] == bounds[index + 1][0]
        for index in range(len(bounds) - 1)
    )


def test_work_area_uses_desktop_limits_instead_of_native_title_bar_space() -> None:
    output = "_NET_WORKAREA(CARDINAL) = 0, 0, 1366, 742, 0, 0, 1366, 742"

    assert parse_work_area(output, 1366, 768) == (0, 0, 1366, 742)
    assert parse_work_area("", 1366, 768) == (0, 0, 1366, 768)


def test_terminal_window_is_hidden_as_soon_as_it_is_discovered(monkeypatch: Any) -> None:
    runtime = EmbeddedFirstX11PanelRuntimeBackend()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(runtime, "_process_family", lambda _pid: {1234})
    monkeypatch.setattr(
        runtime,
        "_candidate_window_ids",
        lambda *_args, **_kwargs: ["55"],
    )
    monkeypatch.setattr(runtime, "_window_is_viewable", lambda *_args: True)
    monkeypatch.setattr(
        runtime,
        "_run_xdotool",
        lambda _xdotool, *args: calls.append(tuple(args)),
    )

    window_id = runtime._wait_for_window(
        "xdotool",
        "xwininfo",
        _FakeProcess(),  # type: ignore[arg-type]
        ("TriView Terminal",),
        set(),
    )

    assert window_id == "55"
    assert calls == [
        ("windowmove", "55", "-32000", "-32000"),
        ("windowunmap", "55"),
    ]


def test_terminal_backend_disables_external_fallback(monkeypatch: Any) -> None:
    runtime = _FakeRuntime()
    backend = EmbeddedOnlyTerminalBackend.__new__(EmbeddedOnlyTerminalBackend)
    backend._runtime = runtime  # type: ignore[attr-defined]
    monkeypatch.setattr(backend, "_terminal_emulator", lambda: "/bin/echo")

    session = backend.launch("terminal", "Terminal", ("bash",), 777)

    assert session.embedded is True
    assert runtime.parent_window_id == 777
    assert runtime.request is not None
    assert runtime.request.allow_external_fallback is False
    assert "TriView Terminal [terminal]" in runtime.request.window_hints
