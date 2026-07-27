from __future__ import annotations

import pytest

from triview_workspace.engines.panel_runtime import X11PanelRuntimeBackend


class ExitedLauncher:
    pid = 4242

    def poll(self) -> int:
        return 0


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def test_wait_for_window_survives_launcher_exit_until_real_window_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend(
        launch_timeout=3.0,
        poll_interval=0.25,
        stable_parent_checks=3,
    )
    clock = FakeClock()
    process = ExitedLauncher()

    monkeypatch.setattr(
        "triview_workspace.engines._panel_runtime_cold_start_patch.time.monotonic",
        clock.monotonic,
    )
    monkeypatch.setattr(
        "triview_workspace.engines._panel_runtime_cold_start_patch.time.sleep",
        clock.sleep,
    )
    monkeypatch.setattr(backend, "_process_family", lambda _pid: {4242})

    def candidates(
        _xdotool: str,
        _family_pids: set[int],
        _hints: tuple[str, ...],
        _known_window_ids: set[str],
    ) -> list[str]:
        return ["900"] if clock.value >= 1.25 else []

    monkeypatch.setattr(backend, "_candidate_window_ids", candidates)
    monkeypatch.setattr(
        backend,
        "_window_is_viewable",
        lambda _xwininfo, _window_id: True,
    )

    window_id = backend._wait_for_window(
        "/usr/bin/xdotool",
        "/usr/bin/xwininfo",
        process,  # type: ignore[arg-type]
        ("xed",),
        set(),
    )

    assert window_id == "900"
    assert clock.value >= 1.25


def test_embedding_uses_unmap_reparent_map_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend(
        poll_interval=0.01,
        reparent_attempts=1,
    )
    commands: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: commands.append(tuple(arguments)),
    )
    monkeypatch.setattr(
        backend,
        "_confirm_window_parent",
        lambda *_args: True,
    )
    monkeypatch.setattr(
        "triview_workspace.engines._panel_runtime_cold_start_patch.time.sleep",
        lambda _seconds: None,
    )

    embedded = backend._embed_window(
        "/usr/bin/xdotool",
        "/usr/bin/xwininfo",
        "900",
        99,
        "editor",
    )

    assert embedded is True
    assert commands == [
        ("windowunmap", "900"),
        ("windowreparent", "900", "99"),
        ("windowmap", "900"),
    ]
