"""Release-candidate hardening for hidden Chromium client discovery."""

from __future__ import annotations

import shutil
import subprocess
import time

from triview_workspace.engines.browser import BrowserLaunchError
from triview_workspace.engines.browser_live import (
    NoFlashXfwm4FinalClientX11BraveBrowserBackend,
    is_final_browser_candidate,
)
from triview_workspace.runtime_observability import record_runtime_event


HARDENED_BROWSER_BACKEND_NAME = (
    "ImmediateHideXfwm4FinalClientX11BraveBrowserBackend"
)


class ImmediateHideXfwm4FinalClientX11BraveBrowserBackend(
    NoFlashXfwm4FinalClientX11BraveBrowserBackend
):
    """Hide every newly observed Chromium candidate before stability polling.

    ``--start-minimized`` and an off-screen position are requested at process
    launch, but Chromium or the window manager may briefly ignore those hints.
    This selector therefore unmaps and stages every new matching window as soon
    as it is discovered, instead of waiting until the final titled client has
    passed several stability checks.
    """

    def _wait_for_unique_window(
        self,
        xdotool: str,
        window_class: str,
        process: subprocess.Popen[bytes],
        known_window_ids: set[str],
    ) -> str:
        xwininfo = shutil.which("xwininfo")
        if xwininfo is None:
            raise BrowserLaunchError(
                "O utilitário xwininfo não está disponível para selecionar a janela final."
            )

        deadline = time.monotonic() + self._launch_timeout
        stability: dict[str, int] = {}
        staged_ids: set[str] = set()
        process_exit_seen_at: float | None = None
        last_observation: dict[str, tuple[object, ...]] = {}

        while time.monotonic() < deadline:
            candidates = self._search_matching_windows(
                xdotool,
                window_class,
                only_visible=False,
            )
            current_new_ids = {
                window_id for window_id in candidates if window_id not in known_window_ids
            }
            for window_id in candidates:
                if window_id in known_window_ids:
                    continue

                identity = self._window_identity(xdotool, xwininfo, window_id)
                if window_id not in staged_ids:
                    visible_before_hide = identity.viewable
                    parent_before_hide = identity.parent
                    self._hide_and_stage_window(xdotool, window_id)
                    staged_ids.add(window_id)
                    record_runtime_event(
                        "browser_candidate_forced_hidden",
                        browser_window_id=window_id,
                        expected_window_class=window_class,
                        browser_process_group=process.pid,
                        title=identity.title,
                        window_pid=identity.pid,
                        window_process_group=identity.process_group,
                        parent_before=parent_before_hide,
                        visible_before_hide=visible_before_hide,
                    )
                    identity = self._window_identity(xdotool, xwininfo, window_id)

                eligible = is_final_browser_candidate(
                    identity,
                    expected_class=window_class,
                    expected_process_group=process.pid,
                )
                signature = (
                    identity.title,
                    identity.window_class,
                    identity.pid,
                    identity.process_group,
                    identity.parent,
                    identity.viewable,
                    eligible,
                )
                if last_observation.get(window_id) != signature:
                    record_runtime_event(
                        "browser_window_candidate_observed",
                        browser_window_id=window_id,
                        expected_window_class=window_class,
                        browser_process_group=process.pid,
                        title=identity.title,
                        window_class=identity.window_class,
                        window_pid=identity.pid,
                        window_process_group=identity.process_group,
                        parent=identity.parent,
                        viewable=identity.viewable,
                        eligible_final_client=eligible,
                        forced_hidden=True,
                    )
                    last_observation[window_id] = signature

                if eligible:
                    stability[window_id] = stability.get(window_id, 0) + 1
                    if stability[window_id] >= self._final_window_checks:
                        record_runtime_event(
                            "browser_final_client_selected",
                            browser_window_id=window_id,
                            expected_window_class=window_class,
                            title=identity.title,
                            window_pid=identity.pid,
                            window_process_group=identity.process_group,
                            parent=identity.parent,
                            viewable=identity.viewable,
                            stable_checks=stability[window_id],
                            selected_after_forced_hide=True,
                        )
                        return window_id
                else:
                    stability[window_id] = 0

            for stale_id in set(stability) - current_new_ids:
                stability.pop(stale_id, None)
                staged_ids.discard(stale_id)

            if process.poll() is not None:
                if process_exit_seen_at is None:
                    process_exit_seen_at = time.monotonic()
                elif time.monotonic() - process_exit_seen_at >= min(
                    3.0,
                    self._launch_timeout,
                ):
                    break
            time.sleep(self._poll_interval)

        raise BrowserLaunchError(
            "O Brave iniciou em staging, mas nenhuma janela final titulada foi identificada."
        )


__all__ = [
    "HARDENED_BROWSER_BACKEND_NAME",
    "ImmediateHideXfwm4FinalClientX11BraveBrowserBackend",
]
