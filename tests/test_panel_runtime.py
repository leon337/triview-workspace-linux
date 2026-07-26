from __future__ import annotations

import os
import sys

import pytest

from triview_workspace.engines.panel_runtime import (
    PanelRuntimeAvailability,
    PanelRuntimeLaunchRequest,
    X11PanelRuntimeBackend,
    normalize_command,
    parse_parent_window_id,
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
    monkeypatch.setattr(backend, "_wait_for_window", lambda *args: "123")
    monkeypatch.setattr(backend, "_run_xdotool", lambda *args: None)
    monkeypatch.setattr(backend, "_confirm_window_parent", lambda *args: False)

    session = backend.launch(request, parent_window_id=99)

    assert session.embedded is False
    assert session.external is True
    assert session.window_id is None
    assert session.process is fake_process
