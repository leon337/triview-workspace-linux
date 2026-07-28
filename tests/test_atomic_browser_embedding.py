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


def test_browser_stage_unmaps_before_moving_offscreen(monkeypatch: Any) -> None:
    backend = AtomicX11BraveBrowserBackend()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: calls.append(tuple(arguments)),
    )

    backend._stage_window("xdotool", "77")

    assert calls == [
        ("windowunmap", "77"),
        ("windowmove", "77", "-32000", "-32000"),
    ]
