from __future__ import annotations

from typing import Any

import triview_workspace.gui as active_gui
import triview_workspace.gui_rc4_atomic as atomic_gui
from triview_workspace.engines.browser_final_client import (
    BrowserWindowIdentity,
    FinalClientX11BraveBrowserBackend,
    is_final_browser_client,
)
from triview_workspace.engines.browser_final_client_xfwm4 import (
    Xfwm4FinalClientX11BraveBrowserBackend,
)


def _identity(*, window_class: str) -> BrowserWindowIdentity:
    return BrowserWindowIdentity(
        window_id="77",
        title="ChatGPT",
        window_class=window_class,
        pid=4243,
        process_group=4242,
        parent=900,
        viewable=True,
    )


def test_xfwm4_backend_recovers_blank_class_from_exact_search(
    monkeypatch: Any,
) -> None:
    backend = Xfwm4FinalClientX11BraveBrowserBackend()
    recorded: list[tuple[str, dict[str, object]]] = []

    monkeypatch.setattr(
        FinalClientX11BraveBrowserBackend,
        "_search_matching_windows",
        staticmethod(lambda *_args, **_kwargs: ["77"]),
    )
    monkeypatch.setattr(
        FinalClientX11BraveBrowserBackend,
        "_window_identity",
        lambda *_args, **_kwargs: _identity(window_class=""),
    )
    monkeypatch.setattr(
        "triview_workspace.engines.browser_final_client_xfwm4.record_runtime_event",
        lambda event, **fields: recorded.append((event, fields)),
    )

    assert backend._search_matching_windows(
        "xdotool",
        "TriView-chatgpt",
        only_visible=False,
    ) == ["77"]
    recovered = backend._window_identity("xdotool", "xwininfo", "77")

    assert recovered.window_class == "TriView-chatgpt"
    assert is_final_browser_client(
        recovered,
        expected_class="TriView-chatgpt",
        expected_process_group=4242,
    )
    assert recorded[-1][0] == "browser_window_class_recovered_from_exact_search"


def test_xfwm4_backend_does_not_invent_class_without_exact_match(
    monkeypatch: Any,
) -> None:
    backend = Xfwm4FinalClientX11BraveBrowserBackend()
    monkeypatch.setattr(
        FinalClientX11BraveBrowserBackend,
        "_window_identity",
        lambda *_args, **_kwargs: _identity(window_class=""),
    )

    observed = backend._window_identity("xdotool", "xwininfo", "77")

    assert observed.window_class == ""
    assert not is_final_browser_client(
        observed,
        expected_class="TriView-chatgpt",
        expected_process_group=4242,
    )


def test_active_gui_registers_xfwm4_final_client_backend() -> None:
    assert active_gui.main is atomic_gui.main
    assert atomic_gui.BROWSER_BACKEND_NAME == (
        "Xfwm4FinalClientX11BraveBrowserBackend"
    )
