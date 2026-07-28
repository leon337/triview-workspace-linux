"""XFCE/Xfwm4 compatibility for final Chromium client selection.

On the physical Linux Mint/Xfwm4 environment, ``xdotool search --class``
correctly locates the TriView browser windows, but
``xdotool getwindowclassname`` returns an empty string for those same windows.
The base final-client selector therefore rejects a valid, titled browser client
because its redundant class re-read is blank.

This backend treats an exact successful ``xdotool search --class`` result as the
class proof for that window ID. It preserves all remaining checks: process
group, managed parent, visibility, non-empty page title and placeholder
rejection.
"""

from __future__ import annotations

from dataclasses import replace
from threading import RLock

from triview_workspace.engines.browser_final_client import (
    BrowserWindowIdentity,
    FinalClientX11BraveBrowserBackend,
)
from triview_workspace.runtime_observability import record_runtime_event


class Xfwm4FinalClientX11BraveBrowserBackend(FinalClientX11BraveBrowserBackend):
    """Recover WM_CLASS from the exact search that produced each candidate."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._confirmed_class_by_window: dict[str, str] = {}
        self._confirmed_class_lock = RLock()

    def _search_matching_windows(
        self,
        xdotool: str,
        value: str,
        *,
        only_visible: bool,
    ) -> list[str]:
        window_ids = super()._search_matching_windows(
            xdotool,
            value,
            only_visible=only_visible,
        )
        with self._confirmed_class_lock:
            for window_id in window_ids:
                self._confirmed_class_by_window[window_id] = value
        return window_ids

    def _window_identity(
        self,
        xdotool: str,
        xwininfo: str,
        window_id: str,
    ) -> BrowserWindowIdentity:
        identity = super()._window_identity(xdotool, xwininfo, window_id)
        if identity.window_class.strip():
            return identity

        with self._confirmed_class_lock:
            confirmed_class = self._confirmed_class_by_window.get(window_id, "")
        if not confirmed_class:
            return identity

        record_runtime_event(
            "browser_window_class_recovered_from_exact_search",
            browser_window_id=window_id,
            recovered_window_class=confirmed_class,
            title=identity.title,
            window_pid=identity.pid,
            window_process_group=identity.process_group,
            parent=identity.parent,
            viewable=identity.viewable,
        )
        return replace(identity, window_class=confirmed_class)


__all__ = ["Xfwm4FinalClientX11BraveBrowserBackend"]
