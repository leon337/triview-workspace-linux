from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import triview_workspace.engines.browser_wheel_bridge_xephyr as wheel_bridge


def test_x11_ancestry_cache_avoids_repeated_subprocess_probes(
    monkeypatch: Any,
) -> None:
    wheel_bridge.clear_x11_route_cache()
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
    wheel_bridge.clear_x11_route_cache()
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


def test_x11_geometry_cache_is_root_relative_and_bounded(monkeypatch: Any) -> None:
    wheel_bridge.clear_x11_route_cache()
    calls: list[int] = []

    monkeypatch.setattr(wheel_bridge.shutil, "which", lambda command: "/usr/bin/xwininfo")
    monkeypatch.setattr(wheel_bridge.time, "monotonic", lambda: 30.0)

    def fake_run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        calls.append(int(command[2]))
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "Absolute upper-left X:  450\n"
                "Absolute upper-left Y:  98\n"
                "Width: 400\n"
                "Height: 700\n"
            ),
        )

    monkeypatch.setattr(wheel_bridge.subprocess, "run", fake_run)

    first = wheel_bridge.x11_window_geometry(901)
    second = wheel_bridge.x11_window_geometry("901")

    assert first == wheel_bridge.X11WindowGeometry(450, 98, 400, 700)
    assert second == first
    assert first is not None and first.contains(600, 300)
    assert first is not None and not first.contains(120, 300)
    assert calls == [901]


def test_clear_route_cache_invalidates_ancestry_and_geometry(monkeypatch: Any) -> None:
    wheel_bridge.clear_x11_route_cache()
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(wheel_bridge.shutil, "which", lambda command: "/usr/bin/xwininfo")
    monkeypatch.setattr(wheel_bridge.time, "monotonic", lambda: 40.0)

    def fake_run(command: list[str], **_kwargs: Any) -> SimpleNamespace:
        window_id = int(command[2])
        mode = "tree" if "-tree" in command else "geometry"
        calls.append((mode, window_id))
        if mode == "tree":
            parent = 1 if window_id == 900 else window_id
            return SimpleNamespace(
                returncode=0,
                stdout=f"Parent window id: 0x{parent:x}\n",
            )
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "Absolute upper-left X:  0\n"
                "Absolute upper-left Y:  0\n"
                "Width: 400\n"
                "Height: 700\n"
            ),
        )

    monkeypatch.setattr(wheel_bridge.subprocess, "run", fake_run)

    wheel_bridge.x11_window_ancestry(900)
    wheel_bridge.x11_window_geometry(900)
    wheel_bridge.x11_window_ancestry(900)
    wheel_bridge.x11_window_geometry(900)
    assert calls == [("tree", 900), ("tree", 1), ("geometry", 900)]

    wheel_bridge.clear_x11_route_cache()
    wheel_bridge.x11_window_ancestry(900)
    wheel_bridge.x11_window_geometry(900)
    assert calls == [
        ("tree", 900),
        ("tree", 1),
        ("geometry", 900),
        ("tree", 900),
        ("tree", 1),
        ("geometry", 900),
    ]
