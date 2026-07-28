from __future__ import annotations

from pathlib import Path
from typing import Any

import triview_workspace.gui as active_gui
import triview_workspace.gui_rc4_atomic as atomic_gui
from triview_workspace.engines.browser import BrowserLaunchRequest
from triview_workspace.engines.browser_embedded import (
    AtomicX11BraveBrowserBackend,
    build_staged_browser_command,
    exact_x11_pattern,
)


class _FakeProcess:
    pid = 1234

    @staticmethod
    def poll() -> None:
        return None


def _request(tmp_path: Path) -> BrowserLaunchRequest:
    return BrowserLaunchRequest(
        panel_id="chatgpt",
        url="https://chatgpt.com",
        profile_dir=tmp_path / "chatgpt",
        window_class="TriView-chatgpt",
    )


def test_active_gui_uses_atomic_runtime_entry_point() -> None:
    assert active_gui.main is atomic_gui.main
    assert active_gui.WorkspaceWindow is atomic_gui.WorkspaceWindow


def test_browser_command_stages_window_outside_visible_desktop(tmp_path: Path) -> None:
    command = build_staged_browser_command("/usr/bin/brave-browser", _request(tmp_path))

    assert "--class=TriView-chatgpt" in command
    assert "--name=TriView-chatgpt" in command
    assert "--window-position=-32000,-32000" in command
    assert "--window-size=800,600" in command


def test_exact_x11_pattern_escapes_regex_metacharacters() -> None:
    assert exact_x11_pattern("TriView Terminal [terminal]") == (
        r"^TriView\ Terminal\ \[terminal\]$"
    )


def test_browser_discovers_unmapped_new_window_and_excludes_old_one(
    monkeypatch: Any,
) -> None:
    backend = AtomicX11BraveBrowserBackend(launch_timeout=1.0, poll_interval=0.01)
    calls: list[tuple[str, bool]] = []

    def search(
        _xdotool: str,
        value: str,
        *,
        only_visible: bool,
    ) -> list[str]:
        calls.append((value, only_visible))
        return ["old-window", "new-window"]

    monkeypatch.setattr(backend, "_search_matching_windows", search)

    result = backend._wait_for_unique_window(
        "xdotool",
        "TriView-chatgpt",
        _FakeProcess(),  # type: ignore[arg-type]
        {"old-window"},
    )

    assert result == "new-window"
    assert calls == [("TriView-chatgpt", False)]


def test_browser_stage_moves_window_without_unmapping_first_map(
    monkeypatch: Any,
) -> None:
    backend = AtomicX11BraveBrowserBackend()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: calls.append(tuple(arguments)),
    )

    backend._stage_window("xdotool", "77")

    assert calls == [("windowmove", "77", "-32000", "-32000")]


def test_browser_waits_for_first_managed_map_before_reparenting(
    monkeypatch: Any,
) -> None:
    backend = AtomicX11BraveBrowserBackend(launch_timeout=1.0, poll_interval=0.01)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: calls.append(tuple(arguments)),
    )
    monkeypatch.setattr(backend, "_window_is_viewable", lambda *_args: True)

    backend._wait_for_first_managed_map(
        "xdotool",
        "xwininfo",
        "77",
        _FakeProcess(),  # type: ignore[arg-type]
    )

    assert calls == [("windowmap", "77")]


def test_browser_reparents_only_after_first_map_and_confirms_after_final_map(
    monkeypatch: Any,
) -> None:
    backend = AtomicX11BraveBrowserBackend(reparent_attempts=2)
    events: list[object] = []
    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: events.append(tuple(arguments)),
    )

    def confirm(*_args: object) -> bool:
        events.append("confirm")
        return True

    monkeypatch.setattr(backend, "_confirm_mapped_parent", confirm)

    result = backend._reparent_after_first_map(
        "xdotool",
        "xwininfo",
        "77",
        900,
        "chatgpt",
    )

    assert result is True
    assert events == [
        ("windowmove", "77", "-32000", "-32000"),
        ("windowunmap", "77"),
        ("windowreparent", "77", "900"),
        ("windowmove", "77", "0", "0"),
        ("windowmap", "77"),
        "confirm",
    ]


def test_browser_retries_when_window_manager_reclaims_mapped_window(
    monkeypatch: Any,
) -> None:
    backend = AtomicX11BraveBrowserBackend(
        poll_interval=0.01,
        reparent_attempts=3,
    )
    calls: list[tuple[str, ...]] = []
    confirmations = iter((False, True))
    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: calls.append(tuple(arguments)),
    )
    monkeypatch.setattr(
        backend,
        "_confirm_mapped_parent",
        lambda *_args: next(confirmations),
    )

    result = backend._reparent_after_first_map(
        "xdotool",
        "xwininfo",
        "77",
        900,
        "chatgpt",
    )

    assert result is True
    assert calls.count(("windowreparent", "77", "900")) == 2
    assert calls.count(("windowmap", "77")) == 2
