from __future__ import annotations

import os
import sys

import pytest

from triview_workspace.engines.panel_runtime import (
    PanelRuntimeAvailability,
    PanelRuntimeLaunchRequest,
    X11PanelRuntimeBackend,
    descendant_process_ids,
    normalize_command,
    parse_parent_window_id,
    parse_process_table,
    resolve_command,
    safe_panel_token,
    split_command,
)


class FakeProcess:
    pid = 4242

    def __init__(self) -> None:
        self.terminated = False

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: int) -> int:
        del timeout
        return 0

    def kill(self) -> None:
        self.terminated = True


def test_split_command_does_not_use_shell_operators() -> None:
    assert split_command('python3 -c "print(1)"') == (
        "python3",
        "-c",
        "print(1)",
    )


def test_split_command_rejects_empty_or_unbalanced_input() -> None:
    with pytest.raises(ValueError):
        split_command("   ")
    with pytest.raises(ValueError):
        split_command('"unterminated')


def test_normalize_command_quotes_arguments_consistently() -> None:
    assert normalize_command('demo "two words"') == "demo 'two words'"


def test_resolve_command_accepts_absolute_executable() -> None:
    resolved = resolve_command((sys.executable, "-V"))
    assert resolved[0] == os.path.realpath(sys.executable)
    assert resolved[1:] == ("-V",)


def test_resolve_command_rejects_missing_program() -> None:
    with pytest.raises(ValueError, match="não foi encontrado"):
        resolve_command(("triview-program-that-does-not-exist",))


def test_safe_panel_token_removes_unsafe_characters() -> None:
    assert safe_panel_token("Meu painel / 1") == "Meu-painel-1"


def test_parse_parent_window_id_accepts_hexadecimal_and_decimal() -> None:
    assert parse_parent_window_id("Parent window id: 0x2a (has no name)") == 42
    assert parse_parent_window_id("Parent window id: 42") == 42
    assert parse_parent_window_id("sem informação de parent") is None


def test_process_family_includes_recursive_descendants() -> None:
    process_table = parse_process_table(
        """
        10 1
        11 10
        12 11
        13 1
        invalid row
        """
    )

    assert descendant_process_ids(10, process_table) == {10, 11, 12}


def test_x11_backend_reports_external_fallback_without_xdotool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend()
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setattr(
        "triview_workspace.engines.panel_runtime.resolve_command",
        lambda command: ("/usr/bin/demo-app",),
    )
    monkeypatch.setattr(backend, "_xdotool_command", lambda: None)

    availability = backend.availability(("demo-app",))

    assert availability.available is True
    assert availability.can_embed is False
    assert "externamente" in availability.reason


def test_x11_backend_requires_xwininfo_to_confirm_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend()
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setattr(
        "triview_workspace.engines.panel_runtime.resolve_command",
        lambda command: ("/usr/bin/demo-app",),
    )
    monkeypatch.setattr(backend, "_xdotool_command", lambda: "/usr/bin/xdotool")
    monkeypatch.setattr(backend, "_xwininfo_command", lambda: None)

    availability = backend.availability(("demo-app",))

    assert availability.available is True
    assert availability.can_embed is False
    assert "xwininfo" in availability.reason


def test_candidate_windows_ignore_preexisting_and_unrelated_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend()

    def fake_search(_xdotool: str, selector: str, value: str) -> list[str]:
        if selector == "--pid" and value == "100":
            return ["10"]
        if selector == "--pid" and value == "101":
            return ["11"]
        return ["9", "11", "12", "13"]

    monkeypatch.setattr(backend, "_search_windows", fake_search)
    monkeypatch.setattr(
        backend,
        "_window_pid",
        lambda _xdotool, window_id: {
            "9": 999,
            "11": 101,
            "12": 777,
            "13": None,
        }[window_id],
    )

    candidates = backend._candidate_window_ids(
        "/usr/bin/xdotool",
        {100, 101},
        ("demo",),
        {"9", "10"},
    )

    assert candidates == ["11"]


def test_ambiguous_unowned_hint_windows_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend()

    def fake_search(
        _xdotool: str,
        selector: str,
        _value: str,
        **_kwargs: object,
    ) -> list[str]:
        if selector == "--pid":
            return []
        return ["20", "21"]

    monkeypatch.setattr(backend, "_search_windows", fake_search)
    monkeypatch.setattr(backend, "_window_pid", lambda *_args: None)

    candidates = backend._candidate_window_ids(
        "/usr/bin/xdotool",
        {100},
        ("demo",),
        set(),
    )

    assert candidates == []


def test_prelaunch_snapshot_includes_hidden_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend()
    calls: list[bool] = []

    def fake_search(
        _xdotool: str,
        _selector: str,
        _value: str,
        *,
        only_visible: bool = True,
    ) -> list[str]:
        calls.append(only_visible)
        return ["10"]

    monkeypatch.setattr(backend, "_search_windows", fake_search)

    assert backend._visible_window_ids("xdotool") == {"10"}
    assert calls == [False]


def test_embedding_retries_until_parent_is_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend(
        poll_interval=0.001,
        reparent_attempts=3,
    )
    commands: list[tuple[str, ...]] = []
    confirmations = iter((False, True))
    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: commands.append(tuple(arguments)),
    )
    monkeypatch.setattr(
        backend,
        "_confirm_window_parent",
        lambda *_args: next(confirmations),
    )
    monkeypatch.setattr(
        "triview_workspace.engines.panel_runtime.time.sleep",
        lambda _seconds: None,
    )

    embedded = backend._embed_window(
        "/usr/bin/xdotool",
        "/usr/bin/xwininfo",
        "123",
        99,
        "editor",
    )

    assert embedded is True
    assert commands == [
        ("windowreparent", "123", "99"),
        ("windowmap", "123"),
        ("windowreparent", "123", "99"),
        ("windowmap", "123"),
    ]


def test_parent_confirmation_requires_consecutive_stable_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend(
        poll_interval=0.001,
        stable_parent_checks=3,
    )
    parents = iter((99, 0, 99, 99, 99))
    monkeypatch.setattr(
        backend,
        "_read_parent_window_id",
        lambda *_args: next(parents),
    )
    monkeypatch.setattr(
        "triview_workspace.engines.panel_runtime.time.sleep",
        lambda _seconds: None,
    )

    assert backend._confirm_window_parent("xwininfo", "123", 99) is True


def test_launch_uses_prelaunch_snapshot_and_new_window_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend()
    fake_process = FakeProcess()
    request = PanelRuntimeLaunchRequest(
        panel_id="editor",
        command=("demo-app",),
        window_hints=("demo-app",),
    )
    monkeypatch.setattr(
        backend,
        "availability",
        lambda command: PanelRuntimeAvailability(
            True,
            True,
            "ok",
            executable="/usr/bin/demo-app",
            xdotool_command="/usr/bin/xdotool",
            xwininfo_command="/usr/bin/xwininfo",
        ),
    )
    monkeypatch.setattr(
        "triview_workspace.engines.panel_runtime.resolve_command",
        lambda command: ("/usr/bin/demo-app",),
    )
    monkeypatch.setattr(
        "triview_workspace.engines.panel_runtime.subprocess.Popen",
        lambda *args, **kwargs: fake_process,
    )
    monkeypatch.setattr(backend, "_visible_window_ids", lambda _xdotool: {"old"})

    def fake_wait(*args: object) -> str:
        assert args[-1] == {"old"}
        return "new"

    monkeypatch.setattr(backend, "_wait_for_window", fake_wait)
    monkeypatch.setattr(backend, "_embed_window", lambda *args: True)

    session = backend.launch(request, parent_window_id=99)

    assert session.embedded is True
    assert session.external is False
    assert session.window_id == "new"


def test_x11_backend_downgrades_false_embedding_to_external(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = X11PanelRuntimeBackend()
    fake_process = FakeProcess()
    request = PanelRuntimeLaunchRequest(
        panel_id="editor",
        command=("demo-app",),
        window_hints=("demo-app",),
    )
    monkeypatch.setattr(
        backend,
        "availability",
        lambda command: PanelRuntimeAvailability(
            True,
            True,
            "ok",
            executable="/usr/bin/demo-app",
            xdotool_command="/usr/bin/xdotool",
            xwininfo_command="/usr/bin/xwininfo",
        ),
    )
    monkeypatch.setattr(
        "triview_workspace.engines.panel_runtime.resolve_command",
        lambda command: ("/usr/bin/demo-app",),
    )
    monkeypatch.setattr(
        "triview_workspace.engines.panel_runtime.subprocess.Popen",
        lambda *args, **kwargs: fake_process,
    )
    monkeypatch.setattr(backend, "_visible_window_ids", lambda _xdotool: set())
    monkeypatch.setattr(backend, "_wait_for_window", lambda *args: "123")
    monkeypatch.setattr(backend, "_embed_window", lambda *args: False)

    session = backend.launch(request, parent_window_id=99)

    assert session.embedded is False
    assert session.external is True
    assert session.window_id is None
    assert session.process is fake_process
