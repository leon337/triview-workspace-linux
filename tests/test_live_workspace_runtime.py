from __future__ import annotations

import inspect
from collections import Counter
from pathlib import Path
from typing import Any

import triview_workspace.gui as active_gui
import triview_workspace.gui_rc4_atomic as atomic_gui
from triview_workspace.diagnostic_blackbox import (
    classify_key,
    parse_xinput_event_block,
    parse_xinput_keymap,
    sanitize_runtime_value,
    sanitized_arguments,
    sanitized_window_title,
)
from triview_workspace.domain import PanelKind, PanelSpec, WorkspaceSpec
from triview_workspace.engines.browser import BrowserLaunchRequest, BrowserSession
from triview_workspace.engines.browser_final_client import BrowserWindowIdentity
from triview_workspace.engines.browser_live import (
    LiveBrowserEngine,
    NoFlashXfwm4FinalClientX11BraveBrowserBackend,
    build_no_flash_browser_command,
    is_final_browser_candidate,
)
from triview_workspace.gui_rc4_live import (
    WorkspaceWindow,
    runtime_panel_id,
    workspace_panel_signature,
)


class _FakeProcess:
    pid = 4242

    @staticmethod
    def poll() -> None:
        return None


def _request(tmp_path: Path) -> BrowserLaunchRequest:
    return BrowserLaunchRequest(
        panel_id="three-gpt-agents::agent-gpt-1",
        url="https://chatgpt.com",
        profile_dir=tmp_path / "profile",
        window_class="TriView-three-gpt-agents-agent-gpt-1",
    )


def _identity(*, viewable: bool, title: str = "ChatGPT") -> BrowserWindowIdentity:
    return BrowserWindowIdentity(
        window_id="77",
        title=title,
        window_class="TriView-three-gpt-agents-agent-gpt-1",
        pid=4243,
        process_group=4242,
        parent=900,
        viewable=viewable,
    )


def test_active_gui_keeps_the_compatibility_entry_point() -> None:
    assert active_gui.main is atomic_gui.main
    assert active_gui.WorkspaceWindow is atomic_gui.WorkspaceWindow
    assert atomic_gui.BROWSER_BACKEND_NAME == (
        "Xfwm4FinalClientX11BraveBrowserBackend"
    )
    assert atomic_gui.LIVE_BROWSER_BACKEND_NAME == (
        "NoFlashXfwm4FinalClientX11BraveBrowserBackend"
    )


def test_runtime_panel_id_namespaces_equal_panel_ids() -> None:
    first = runtime_panel_id("three-gpt-agents", "agent-1")
    second = runtime_panel_id("social", "agent-1")

    assert first == "three-gpt-agents::agent-1"
    assert second == "social::agent-1"
    assert first != second


def test_workspace_signature_changes_only_with_panel_definition() -> None:
    base_panel = PanelSpec("one", "One", PanelKind.BROWSER, "https://example.com")
    first = WorkspaceSpec("a", "Workspace A", "layout-1", (base_panel,))
    renamed_workspace = WorkspaceSpec("a", "Renamed", "layout-2", (base_panel,))
    changed_panel = WorkspaceSpec(
        "a",
        "Workspace A",
        "layout-1",
        (PanelSpec("one", "One", PanelKind.BROWSER, "https://example.org"),),
    )

    assert workspace_panel_signature(first) == workspace_panel_signature(
        renamed_workspace
    )
    assert workspace_panel_signature(first) != workspace_panel_signature(changed_panel)


def test_workspace_switch_path_does_not_close_all_runtimes() -> None:
    source = inspect.getsource(WorkspaceWindow._load_workspace_view)
    park_source = inspect.getsource(WorkspaceWindow._park_workspace)

    assert "runtime_registry.close_all" not in source
    assert "_park_workspace" in source
    assert "place_forget" in park_source
    assert "destroyed_runtimes=0" in park_source


def test_no_flash_command_starts_minimized_outside_the_desktop(tmp_path: Path) -> None:
    command = build_no_flash_browser_command("/usr/bin/brave-browser", _request(tmp_path))

    assert "--ozone-platform=x11" in command
    assert "--start-minimized" in command
    assert "--window-position=-32000,-32000" in command
    assert "--window-size=800,600" in command


def test_hidden_titled_final_client_is_eligible() -> None:
    assert is_final_browser_candidate(
        _identity(viewable=False),
        expected_class="TriView-three-gpt-agents-agent-gpt-1",
        expected_process_group=4242,
    )
    assert not is_final_browser_candidate(
        _identity(
            viewable=False,
            title="TriView-three-gpt-agents-agent-gpt-1",
        ),
        expected_class="TriView-three-gpt-agents-agent-gpt-1",
        expected_process_group=4242,
    )


def test_staging_unmaps_before_moving(monkeypatch: Any) -> None:
    backend = NoFlashXfwm4FinalClientX11BraveBrowserBackend()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: calls.append(tuple(arguments)),
    )

    backend._hide_and_stage_window("xdotool", "77")

    assert calls == [
        ("windowunmap", "77"),
        ("windowmove", "77", "-32000", "-32000"),
    ]


def test_scroll_is_delivered_only_to_requested_embedded_window(
    monkeypatch: Any,
) -> None:
    backend = NoFlashXfwm4FinalClientX11BraveBrowserBackend()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(backend, "_xdotool_command", lambda: "xdotool")
    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: calls.append(tuple(arguments)),
    )
    session = BrowserSession(
        panel_id="workspace::one",
        url="https://example.com",
        process=_FakeProcess(),  # type: ignore[arg-type]
        window_id="77",
        embedded=True,
    )

    assert backend.scroll(session, -3)
    assert calls == [
        ("click", "--window", "77", "--repeat", "3", "5"),
    ]


def test_live_engine_exposes_sessions_without_relaunching() -> None:
    class Backend:
        pass

    engine = LiveBrowserEngine(Backend())  # type: ignore[arg-type]
    session = BrowserSession(
        panel_id="workspace::one",
        url="https://example.com",
        process=None,
        window_id="77",
        embedded=True,
    )
    engine._sessions[session.panel_id] = session

    assert engine.session(session.panel_id) is session
    assert engine.has_session(session.panel_id)


def test_diagnostic_keymap_keeps_controls_and_redacts_text_keys() -> None:
    mapping = parse_xinput_keymap(
        "keycode  36 = Return NoSymbol Return\n"
        "keycode  38 = a A a A\n"
        "keycode  64 = Alt_L Meta_L Alt_L Meta_L\n"
    )

    assert mapping == {36: "Return", 64: "Alt_L"}
    assert classify_key(36, mapping) == ("control_key", "Return")
    assert classify_key(38, mapping) == ("text_key", None)


def test_xinput_event_never_exports_literal_text() -> None:
    event = parse_xinput_event_block(
        [
            "EVENT type 13 (RawKeyPress)\n",
            "    detail: 38\n",
        ],
        safe_keymap={},
        pointer={"x": 20, "y": 30, "window": 77},
    )

    assert event is not None
    assert event["input_category"] == "text_key"
    assert event["key_name"] is None
    assert event["literal_text_captured"] is False
    assert "detail" not in event


def test_shareable_diagnostic_redacts_titles_urls_and_secret_arguments() -> None:
    redactions: Counter[str] = Counter()
    assert sanitized_window_title(
        "Confidential project discussion - ChatGPT", redactions
    ) == "ChatGPT"
    arguments = sanitized_arguments(
        "brave --app=https://example.com/path?token=abc --token=secret",
        redactions,
    )
    assert "token=abc" not in arguments
    assert "secret" not in arguments
    payload = sanitize_runtime_value(
        {
            "event": "test",
            "url": "https://example.com/path?secret=yes",
            "message_text": "private message",
        },
        redactions,
    )
    assert payload["url"] == "https://example.com/path"
    assert payload["message_text"] == "[REDACTED]"


def test_candidate_diagnostic_uses_explicit_blackbox_session() -> None:
    script = Path("scripts/candidate-diagnose.sh").read_text(encoding="utf-8")
    module = Path("src/triview_workspace/diagnostic_blackbox.py").read_text(
        encoding="utf-8"
    )

    assert "triview_workspace.diagnostic_blackbox" in script
    assert "--auto-launch" in script
    assert "--auto-stop-on-application-exit" in script
    assert "triview-blackbox" in module
    assert "literal_text_captured" in module
