from __future__ import annotations

from typing import Any

from triview_workspace.engines.browser_embedded import exact_x11_pattern
from triview_workspace.engines.terminal_embedded import (
    EmbeddedFirstX11PanelRuntimeBackend,
    build_staged_terminal_command,
)


class _FakeProcess:
    pid = 4321

    @staticmethod
    def poll() -> None:
        return None


def test_xfce_terminal_command_is_staged_offscreen() -> None:
    command = build_staged_terminal_command(
        "/usr/bin/xfce4-terminal",
        "TriView-Terminal-terminal",
        ("/usr/bin/bash", "-l"),
    )

    assert "--disable-server" in command
    assert "--title=TriView-Terminal-terminal" in command
    assert "--geometry=80x24-32000-32000" in command
    assert command[-2:] == ("/usr/bin/bash", "-l")


def test_terminal_selects_unique_title_instead_of_first_pid_helper(
    monkeypatch: Any,
) -> None:
    runtime = EmbeddedFirstX11PanelRuntimeBackend()
    staged: list[str] = []
    searches: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(runtime, "_process_family", lambda _pid: {4321})

    def search(
        _xdotool: str,
        selector: str,
        value: str,
        *,
        only_visible: bool = True,
    ) -> list[str]:
        searches.append((selector, value, only_visible))
        return ["helper-window", "terminal-window"]

    monkeypatch.setattr(runtime, "_search_windows", search)
    monkeypatch.setattr(
        runtime,
        "_window_pid",
        lambda _xdotool, window_id: 9999 if window_id == "helper-window" else 4321,
    )
    monkeypatch.setattr(runtime, "_stage_window", lambda _xdotool, window_id: staged.append(window_id))

    result = runtime._wait_for_window(
        "xdotool",
        "xwininfo",
        _FakeProcess(),  # type: ignore[arg-type]
        ("TriView-Terminal-terminal",),
        set(),
    )

    assert result == "terminal-window"
    assert staged == ["terminal-window"]
    assert searches == [
        (
            "--name",
            exact_x11_pattern("TriView-Terminal-terminal"),
            False,
        )
    ]


def test_terminal_ignores_preexisting_unique_title_window(monkeypatch: Any) -> None:
    runtime = EmbeddedFirstX11PanelRuntimeBackend()
    calls = 0

    monkeypatch.setattr(runtime, "_process_family", lambda _pid: {4321})

    def search(*_args: object, **_kwargs: object) -> list[str]:
        nonlocal calls
        calls += 1
        return ["old-window", "new-window"]

    monkeypatch.setattr(runtime, "_search_windows", search)
    monkeypatch.setattr(runtime, "_window_pid", lambda *_args: 4321)
    monkeypatch.setattr(runtime, "_stage_window", lambda *_args: None)

    result = runtime._wait_for_window(
        "xdotool",
        "xwininfo",
        _FakeProcess(),  # type: ignore[arg-type]
        ("TriView-Terminal-terminal",),
        {"old-window"},
    )

    assert calls == 1
    assert result == "new-window"
