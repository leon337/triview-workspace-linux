from __future__ import annotations

import os
import sys

import pytest

from triview_workspace.engines.panel_runtime import (
    X11PanelRuntimeBackend,
    normalize_command,
    resolve_command,
    safe_panel_token,
    split_command,
)


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
