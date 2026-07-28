from __future__ import annotations

from collections.abc import Callable

import pytest

import triview_workspace.gui as active_gui
from triview_workspace.gui_rc4_popup import WorkspaceWindow, safe_popup_menu


class _FakeMenu:
    def __init__(self, *, popup_error: Exception | None = None) -> None:
        self.events: list[object] = []
        self.callbacks: list[tuple[int, Callable[[], None]]] = []
        self.mapped = True
        self.popup_error = popup_error

    def tk_popup(self, x: int, y: int) -> None:
        self.events.append(("popup", x, y))
        if self.popup_error is not None:
            raise self.popup_error

    def after(self, delay: int, command: Callable[[], None]) -> None:
        self.callbacks.append((delay, command))
        self.events.append(("watch", delay))

    def winfo_ismapped(self) -> bool:
        return self.mapped

    def unpost(self) -> None:
        self.mapped = False
        self.events.append("unpost")

    def grab_release(self) -> None:
        self.events.append("release")

    def run_next(self) -> None:
        _delay, command = self.callbacks.pop(0)
        command()


def test_active_gui_uses_popup_lifecycle_runtime() -> None:
    assert active_gui.WorkspaceWindow is WorkspaceWindow


def test_popup_keeps_native_grab_until_outside_click_unmaps_menu() -> None:
    menu = _FakeMenu()

    safe_popup_menu(
        menu, 10, 20, watch_interval_ms=40, failsafe_ms=1_000, clock=lambda: 0.0
    )  # type: ignore[arg-type]

    assert menu.events == [("popup", 10, 20), ("watch", 40)]
    menu.mapped = False
    menu.run_next()

    assert menu.events == [("popup", 10, 20), ("watch", 40), "release"]


def test_popup_failsafe_unposts_and_releases_stale_menu() -> None:
    timestamps = iter((0.0, 16.0))
    menu = _FakeMenu()

    safe_popup_menu(
        menu,
        10,
        20,
        watch_interval_ms=40,
        failsafe_ms=15_000,
        clock=lambda: next(timestamps),
    )  # type: ignore[arg-type]
    menu.run_next()

    assert menu.events == [
        ("popup", 10, 20),
        ("watch", 40),
        "unpost",
        "release",
    ]


def test_popup_releases_grab_when_posting_raises() -> None:
    menu = _FakeMenu(popup_error=RuntimeError("popup failed"))

    with pytest.raises(RuntimeError, match="popup failed"):
        safe_popup_menu(menu, 10, 20)  # type: ignore[arg-type]

    assert menu.events == [("popup", 10, 20), "release"]
