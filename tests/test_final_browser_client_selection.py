from __future__ import annotations

from pathlib import Path
from typing import Any

from triview_workspace.engines.browser import BrowserLaunchRequest, BrowserSession
from triview_workspace.engines.browser_final_client import (
    BrowserWindowIdentity,
    FinalClientX11BraveBrowserBackend,
    is_final_browser_client,
)


class _FakeProcess:
    pid = 4242

    @staticmethod
    def poll() -> None:
        return None


def _identity(
    window_id: str,
    *,
    title: str,
    process_group: int = 4242,
    window_class: str = "TriView-chatgpt",
) -> BrowserWindowIdentity:
    return BrowserWindowIdentity(
        window_id=window_id,
        title=title,
        window_class=window_class,
        pid=process_group + 1,
        process_group=process_group,
        parent=900,
        viewable=True,
    )


def _request(tmp_path: Path) -> BrowserLaunchRequest:
    return BrowserLaunchRequest(
        panel_id="chatgpt",
        url="https://chatgpt.com",
        profile_dir=tmp_path / "chatgpt",
        window_class="TriView-chatgpt",
    )


def test_final_client_rejects_placeholder_and_accepts_titled_app() -> None:
    placeholder = _identity("10", title="TriView-chatgpt")
    final = _identity("11", title="ChatGPT")

    assert not is_final_browser_client(
        placeholder,
        expected_class="TriView-chatgpt",
        expected_process_group=4242,
    )
    assert is_final_browser_client(
        final,
        expected_class="TriView-chatgpt",
        expected_process_group=4242,
    )


def test_final_client_rejects_window_from_another_process_group() -> None:
    foreign = _identity("12", title="ChatGPT", process_group=7777)

    assert not is_final_browser_client(
        foreign,
        expected_class="TriView-chatgpt",
        expected_process_group=4242,
    )


def test_backend_waits_past_placeholder_and_selects_stable_final_client(
    monkeypatch: Any,
) -> None:
    backend = FinalClientX11BraveBrowserBackend(
        launch_timeout=1.0,
        poll_interval=0.001,
        final_window_checks=2,
    )
    process = _FakeProcess()
    recorded: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(
        "triview_workspace.engines.browser_final_client.shutil.which",
        lambda _name: "/usr/bin/xwininfo",
    )
    monkeypatch.setattr(
        backend,
        "_search_matching_windows",
        lambda *_args, **_kwargs: ["old", "placeholder", "final"],
    )
    monkeypatch.setattr(
        backend,
        "_window_identity",
        lambda _xdotool, _xwininfo, window_id: (
            _identity(window_id, title="TriView-chatgpt")
            if window_id == "placeholder"
            else _identity(window_id, title="ChatGPT")
        ),
    )
    monkeypatch.setattr(
        "triview_workspace.engines.browser_final_client.record_runtime_event",
        lambda event, **fields: recorded.append((event, fields)),
    )

    selected = backend._wait_for_unique_window(
        "xdotool",
        "TriView-chatgpt",
        process,  # type: ignore[arg-type]
        {"old"},
    )

    assert selected == "final"
    assert any(event == "browser_final_client_selected" for event, _ in recorded)
    placeholder_events = [
        fields
        for event, fields in recorded
        if event == "browser_window_candidate_observed"
        and fields["browser_window_id"] == "placeholder"
    ]
    assert placeholder_events[-1]["eligible_final_client"] is False


def test_cleanup_closes_only_same_process_placeholder(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    backend = FinalClientX11BraveBrowserBackend()
    process = _FakeProcess()
    session = BrowserSession(
        panel_id="chatgpt",
        url="https://chatgpt.com",
        process=process,  # type: ignore[arg-type]
        window_id="final",
        embedded=True,
    )
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(backend, "_xdotool_command", lambda: "xdotool")
    monkeypatch.setattr(
        "triview_workspace.engines.browser_final_client.shutil.which",
        lambda _name: "/usr/bin/xwininfo",
    )
    monkeypatch.setattr(
        backend,
        "_search_matching_windows",
        lambda *_args, **_kwargs: ["final", "placeholder", "foreign"],
    )

    def identity(_xdotool: str, _xwininfo: str, window_id: str) -> BrowserWindowIdentity:
        if window_id == "placeholder":
            return _identity(window_id, title="TriView-chatgpt")
        if window_id == "foreign":
            return _identity(window_id, title="TriView-chatgpt", process_group=9999)
        return _identity(window_id, title="ChatGPT")

    monkeypatch.setattr(backend, "_window_identity", identity)
    monkeypatch.setattr(
        backend,
        "_run_xdotool",
        lambda _xdotool, *arguments: calls.append(tuple(arguments)),
    )
    monkeypatch.setattr(
        "triview_workspace.engines.browser_final_client.record_runtime_event",
        lambda *_args, **_kwargs: None,
    )

    backend._close_stale_placeholders(_request(tmp_path), session)

    assert calls == [("windowclose", "placeholder")]
