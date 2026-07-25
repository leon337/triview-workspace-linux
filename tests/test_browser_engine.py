from __future__ import annotations

from pathlib import Path

import pytest

from triview_workspace.domain import PanelKind, PanelSpec
from triview_workspace.engines import (
    BrowserBackendAvailability,
    BrowserBackendUnavailable,
    BrowserEngine,
    BrowserPanelAdapter,
    BrowserSession,
    normalize_browser_url,
)


class FakeBackend:
    def __init__(self, *, available: bool = True, fail_resize: bool = False) -> None:
        self.available = available
        self.fail_resize = fail_resize
        self.launched: list[tuple[object, int]] = []
        self.resized: list[tuple[str, int, int]] = []
        self.closed: list[str] = []

    def availability(self) -> BrowserBackendAvailability:
        return BrowserBackendAvailability(
            self.available,
            "pronto" if self.available else "backend indisponível",
            browser_command="brave" if self.available else None,
            xdotool_command="xdotool" if self.available else None,
        )

    def launch(self, request: object, parent_window_id: int) -> BrowserSession:
        self.launched.append((request, parent_window_id))
        panel_id = getattr(request, "panel_id")
        url = getattr(request, "url")
        return BrowserSession(
            panel_id=panel_id,
            url=url,
            process=None,
            window_id=f"window-{len(self.launched)}",
            embedded=True,
        )

    def resize(self, session: BrowserSession, width: int, height: int) -> None:
        self.resized.append((session.panel_id, width, height))
        if self.fail_resize:
            raise RuntimeError("resize failed")

    def close(self, session: BrowserSession) -> None:
        self.closed.append(session.panel_id)


def test_normalize_browser_url_adds_https() -> None:
    assert normalize_browser_url("chatgpt.com") == "https://chatgpt.com"


def test_normalize_browser_url_preserves_http_path_query_and_fragment() -> None:
    target = "http://localhost:3000/path?a=1#section"
    assert normalize_browser_url(target) == target


@pytest.mark.parametrize(
    "target",
    ["", "   ", "ftp://example.com", "https://exa mple.com", "https://", "https://a:wrong"],
)
def test_normalize_browser_url_rejects_invalid_targets(target: str) -> None:
    with pytest.raises(ValueError):
        normalize_browser_url(target)


def test_browser_panel_adapter_only_supports_browser_panels() -> None:
    adapter = BrowserPanelAdapter()
    panel = PanelSpec(
        id="chatgpt",
        title="ChatGPT",
        kind=PanelKind.BROWSER,
        target="chatgpt.com",
    )

    assert adapter.supports(PanelKind.BROWSER)
    assert not adapter.supports(PanelKind.APPLICATION)
    assert adapter.build_launch_request(panel) == {
        "mode": "browser",
        "panel_id": "chatgpt",
        "url": "https://chatgpt.com",
    }


def test_browser_engine_manages_open_resize_reopen_and_close(tmp_path: Path) -> None:
    backend = FakeBackend()
    engine = BrowserEngine(backend, profile_root=tmp_path)

    first = engine.open("chatgpt", "chatgpt.com", 100, 320, 640)
    assert first.embedded
    assert engine.has_session("chatgpt")
    assert backend.resized[-1] == ("chatgpt", 320, 640)

    engine.resize("chatgpt", 400, 700)
    assert backend.resized[-1] == ("chatgpt", 400, 700)

    engine.open("chatgpt", "https://github.com", 101, 300, 600)
    assert backend.closed == ["chatgpt"]
    assert len(backend.launched) == 2

    request = backend.launched[-1][0]
    assert getattr(request, "profile_dir") == tmp_path / "chatgpt"
    assert getattr(request, "window_class") == "TriView-chatgpt"

    engine.close_all()
    assert backend.closed == ["chatgpt", "chatgpt"]
    assert not engine.has_session("chatgpt")


def test_browser_engine_sanitizes_profile_and_window_tokens(tmp_path: Path) -> None:
    backend = FakeBackend()
    engine = BrowserEngine(backend, profile_root=tmp_path)

    engine.open("../../painel especial", "example.com", 100, 320, 640)

    request = backend.launched[-1][0]
    assert getattr(request, "profile_dir") == tmp_path / "painel-especial"
    assert getattr(request, "window_class") == "TriView-painel-especial"


def test_browser_engine_closes_session_when_initial_resize_fails(tmp_path: Path) -> None:
    backend = FakeBackend(fail_resize=True)
    engine = BrowserEngine(backend, profile_root=tmp_path)

    with pytest.raises(RuntimeError, match="resize failed"):
        engine.open("chatgpt", "https://chatgpt.com", 100, 320, 640)

    assert backend.closed == ["chatgpt"]
    assert not engine.has_session("chatgpt")


def test_browser_engine_reports_unavailable_backend(tmp_path: Path) -> None:
    engine = BrowserEngine(FakeBackend(available=False), profile_root=tmp_path)

    with pytest.raises(BrowserBackendUnavailable, match="backend indisponível"):
        engine.open("chatgpt", "https://chatgpt.com", 100, 320, 640)
