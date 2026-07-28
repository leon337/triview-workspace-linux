from __future__ import annotations

import inspect
import threading
from typing import Any

import pytest

import triview_workspace.gui_rc4_runtime as runtime_module
from triview_workspace.engines.panel_runtime import PanelRuntimeSession
from triview_workspace.engines.terminal_embedded import (
    EmbeddedFirstX11PanelRuntimeBackend,
    EmbeddedOnlyTerminalBackend,
)
from triview_workspace.gui_rc4_runtime import (
    EMERGENCY_SHORTCUTS,
    WorkspaceWindow,
    deferred_menu_action,
    parse_work_area,
    proportional_panel_bounds,
    request_managed_maximize,
    safe_popup_menu,
)


class _FakeRoot:
    def __init__(self) -> None:
        self.events: list[object] = []

    def after(self, delay: int, command: Any) -> None:
        self.events.append(("after", delay))
        command()


class _FakeMenu:
    def __init__(self, events: list[object], *, popup_error: Exception | None = None) -> None:
        self.events = events
        self.popup_error = popup_error

    def tk_popup(self, x: int, y: int) -> None:
        self.events.append(("popup", x, y))
        if self.popup_error is not None:
            raise self.popup_error

    def unpost(self) -> None:
        self.events.append("unpost")

    def grab_release(self) -> None:
        self.events.append("release")


class _FakeManagedRoot:
    def __init__(self, *, reject_attributes: bool = False) -> None:
        self.reject_attributes = reject_attributes
        self.attribute_calls: list[tuple[object, ...]] = []
        self.state_calls: list[str] = []
        self.bindings: list[tuple[str, object, str]] = []
        self.title_text = ""
        self.resizable_value: tuple[bool, bool] | None = None
        self.destroyed = False
        self.grab_released = False

    def wm_attributes(self, *args: object) -> None:
        self.attribute_calls.append(args)
        if self.reject_attributes and args[:1] == ("-zoomed",):
            raise runtime_module.tk.TclError("zoomed unsupported")

    def state(self, value: str) -> None:
        self.state_calls.append(value)

    def bind_all(self, shortcut: str, command: object, *, add: str) -> None:
        self.bindings.append((shortcut, command, add))

    def title(self, value: str) -> None:
        self.title_text = value

    def resizable(self, width: bool, height: bool) -> None:
        self.resizable_value = (width, height)

    def grab_release(self) -> None:
        self.grab_released = True

    def destroy(self) -> None:
        self.destroyed = True


class _FakeRuntimeRegistry:
    def __init__(self) -> None:
        self.closed = threading.Event()

    def close_all(self) -> None:
        self.closed.set()


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


def test_menu_action_releases_grab_before_capture_without_forcing_layout() -> None:
    root = _FakeRoot()
    menu = _FakeMenu(root.events)
    action = deferred_menu_action(
        root,  # type: ignore[arg-type]
        menu,  # type: ignore[arg-type]
        lambda: root.events.append("capture"),
    )

    action()

    assert root.events == ["unpost", "release", ("after", 120), "capture"]


def test_popup_always_releases_grab() -> None:
    events: list[object] = []
    menu = _FakeMenu(events)

    safe_popup_menu(menu, 10, 20)  # type: ignore[arg-type]

    assert events == [("popup", 10, 20), "release"]


def test_popup_releases_grab_when_tk_raises() -> None:
    events: list[object] = []
    menu = _FakeMenu(events, popup_error=RuntimeError("popup failed"))

    with pytest.raises(RuntimeError, match="popup failed"):
        safe_popup_menu(menu, 10, 20)  # type: ignore[arg-type]

    assert events == [("popup", 10, 20), "release"]


def test_managed_maximize_delegates_to_window_manager() -> None:
    root = _FakeManagedRoot()

    assert request_managed_maximize(root) is True  # type: ignore[arg-type]
    assert root.attribute_calls == [("-zoomed", True)]
    assert root.state_calls == []


def test_managed_maximize_falls_back_to_zoomed_state() -> None:
    root = _FakeManagedRoot(reject_attributes=True)

    assert request_managed_maximize(root) is True  # type: ignore[arg-type]
    assert root.state_calls == ["zoomed"]


def test_rc4_runtime_has_no_borderless_reactivation_or_sync_layout_flush() -> None:
    module_source = inspect.getsource(runtime_module)
    render_source = inspect.getsource(WorkspaceWindow._render_layout)
    compact_source = inspect.getsource(WorkspaceWindow._compact_panel)

    assert "overrideredirect(" not in module_source
    assert 'bind("<Map>"' not in module_source
    assert "update_idletasks" not in render_source
    assert "update_idletasks" not in compact_source


def test_managed_window_contract_binds_emergency_shortcuts() -> None:
    root = _FakeManagedRoot()
    window = WorkspaceWindow.__new__(WorkspaceWindow)
    window.root = root  # type: ignore[assignment]

    window._install_managed_window_contract()

    assert root.title_text == runtime_module.APP_TITLE
    assert root.resizable_value == (True, True)
    assert [item[0] for item in root.bindings] == list(EMERGENCY_SHORTCUTS)
    assert ("-topmost", False) in root.attribute_calls


def test_emergency_exit_destroys_window_and_starts_runtime_cleanup() -> None:
    root = _FakeManagedRoot()
    registry = _FakeRuntimeRegistry()
    window = WorkspaceWindow.__new__(WorkspaceWindow)
    window.root = root  # type: ignore[assignment]
    window.runtime_registry = registry  # type: ignore[assignment]
    window._panel_menus = {}
    window._global_menu = _FakeMenu([])  # type: ignore[assignment]
    window._closed = False

    result = window._emergency_exit()

    assert result == "break"
    assert root.destroyed is True
    assert root.grab_released is True
    assert registry.closed.wait(timeout=1)


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


def test_work_area_parser_remains_available_for_diagnostics() -> None:
    output = "_NET_WORKAREA(CARDINAL) = 0, 0, 1366, 742, 0, 0, 1366, 742"

    assert parse_work_area(output, 1366, 768) == (0, 0, 1366, 742)
    assert parse_work_area("", 1366, 768) == (0, 0, 1366, 768)


def test_terminal_window_is_hidden_as_soon_as_it_is_discovered(monkeypatch: Any) -> None:
    runtime = EmbeddedFirstX11PanelRuntimeBackend()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(runtime, "_process_family", lambda _pid: {1234})
    monkeypatch.setattr(
        runtime,
        "_search_windows",
        lambda *_args, **_kwargs: ["55"],
    )
    monkeypatch.setattr(runtime, "_window_pid", lambda *_args: 1234)
    monkeypatch.setattr(
        runtime,
        "_run_xdotool",
        lambda _xdotool, *args: calls.append(tuple(args)),
    )

    window_id = runtime._wait_for_window(
        "xdotool",
        "xwininfo",
        _FakeProcess(),  # type: ignore[arg-type]
        ("TriView-Terminal-terminal",),
        set(),
    )

    assert window_id == "55"
    assert calls == [
        ("windowunmap", "55"),
        ("windowmove", "55", "-32000", "-32000"),
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
    assert runtime.request.window_hints == ("TriView-Terminal-terminal",)
