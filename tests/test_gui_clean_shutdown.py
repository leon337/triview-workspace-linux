from __future__ import annotations

from types import SimpleNamespace

import triview_workspace.gui as gui


def _window() -> gui.WorkspaceWindow:
    window = object.__new__(gui.WorkspaceWindow)
    window._closed = False
    window.workspace = SimpleNamespace(id="workspace-main")
    window._runtime_statuses = lambda: {
        "browser": ("browser", True, False),
        "terminal": ("terminal", True, False),
    }
    return window


def test_normal_close_finishes_session_before_hardened_runtime_cleanup(monkeypatch) -> None:
    sequence: list[object] = []

    class RecoveryEngine:
        def finish(self, workspace, statuses) -> None:
            sequence.append(("finish", workspace.id, tuple(sorted(statuses))))

    window = _window()
    window.recovery_engine = RecoveryEngine()
    parent = gui.WorkspaceWindow.__mro__[1]
    monkeypatch.setattr(parent, "_close", lambda _self: sequence.append("parent-close"))
    monkeypatch.setattr(
        gui,
        "record_runtime_event",
        lambda event, **_fields: sequence.append(event),
    )

    gui.WorkspaceWindow._close(window)

    assert sequence == [
        ("finish", "workspace-main", ("browser", "terminal")),
        "session_clean_shutdown_recorded",
        "parent-close",
    ]


def test_session_checkpoint_failure_does_not_trap_the_desktop(monkeypatch) -> None:
    sequence: list[str] = []

    class FailingRecoveryEngine:
        def finish(self, _workspace, _statuses) -> None:
            raise RuntimeError("disk unavailable")

    window = _window()
    window.recovery_engine = FailingRecoveryEngine()
    parent = gui.WorkspaceWindow.__mro__[1]
    monkeypatch.setattr(parent, "_close", lambda _self: sequence.append("parent-close"))
    monkeypatch.setattr(
        gui,
        "record_runtime_event",
        lambda event, **_fields: sequence.append(event),
    )

    gui.WorkspaceWindow._close(window)

    assert sequence == ["session_clean_shutdown_failed", "parent-close"]


def test_observability_failure_does_not_trap_the_desktop(monkeypatch) -> None:
    sequence: list[str] = []

    class RecoveryEngine:
        def finish(self, _workspace, _statuses) -> None:
            sequence.append("finish")

    window = _window()
    window.recovery_engine = RecoveryEngine()
    parent = gui.WorkspaceWindow.__mro__[1]
    monkeypatch.setattr(parent, "_close", lambda _self: sequence.append("parent-close"))
    monkeypatch.setattr(
        gui,
        "record_runtime_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("log unavailable")),
    )

    gui.WorkspaceWindow._close(window)

    assert sequence == ["finish", "parent-close"]


def test_close_without_session_engine_preserves_existing_runtime_path(monkeypatch) -> None:
    sequence: list[str] = []
    window = _window()
    window.recovery_engine = None
    parent = gui.WorkspaceWindow.__mro__[1]
    monkeypatch.setattr(parent, "_close", lambda _self: sequence.append("parent-close"))
    monkeypatch.setattr(gui, "record_runtime_event", lambda *_args, **_kwargs: None)

    gui.WorkspaceWindow._close(window)

    assert sequence == ["parent-close"]
