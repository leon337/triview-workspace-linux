from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import triview_workspace.engines.browser_wheel_bridge_xephyr as wheel_bridge


def test_x11_ancestry_cache_avoids_repeated_subprocess_probes(
    monkeypatch: Any,
) -> None:
    wheel_bridge.clear_x11_ancestry_cache()
    calls: list[int] = []
    parents = {900: 500, 500: 100, 100: 1, 1: 1}

    monkeypatch.setattr(wheel_bridge.shutil, "which", lambda command: "/usr/bin/xwininfo")
    monkeypatch.setattr(wheel_bridge.time, "monotonic", lambda: 10.0)

    def fake_run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        window_id = int(command[2])
        calls.append(window_id)
        parent = parents[window_id]
        return SimpleNamespace(
            returncode=0,
            stdout=f"Parent window id: 0x{parent:x}\n",
        )

    monkeypatch.setattr(wheel_bridge.subprocess, "run", fake_run)

    first = wheel_bridge.x11_window_ancestry(900)
    second = wheel_bridge.x11_window_ancestry("900")

    assert first == (900, 500, 100, 1)
    assert second == first
    assert calls == [900, 500, 100, 1]


def test_x11_ancestry_cache_refreshes_after_ttl(monkeypatch: Any) -> None:
    wheel_bridge.clear_x11_ancestry_cache()
    now = [20.0]
    calls: list[int] = []

    monkeypatch.setattr(wheel_bridge.shutil, "which", lambda command: "/usr/bin/xwininfo")
    monkeypatch.setattr(wheel_bridge.time, "monotonic", lambda: now[0])

    def fake_run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        window_id = int(command[2])
        calls.append(window_id)
        parent = 1 if window_id == 900 else window_id
        return SimpleNamespace(
            returncode=0,
            stdout=f"Parent window id: 0x{parent:x}\n",
        )

    monkeypatch.setattr(wheel_bridge.subprocess, "run", fake_run)

    assert wheel_bridge.x11_window_ancestry(900) == (900, 1)
    now[0] += wheel_bridge._ANCESTRY_CACHE_TTL_SECONDS + 0.01
    assert wheel_bridge.x11_window_ancestry(900) == (900, 1)
    assert calls == [900, 1, 900, 1]
