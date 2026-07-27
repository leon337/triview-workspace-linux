"""Cold-start X11 remediation for LEA-197.

This module patches the reusable X11 runtime at package import time. It stays
separate so the remediation can be reviewed and removed independently after
validation on Linux Mint.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Sequence

from .panel_runtime import X11PanelRuntimeBackend

LOGGER = logging.getLogger(__name__)
_PATCH_MARKER = "_lea197_cold_start_patch_applied"


def _wait_for_window_cold_start(
    self: X11PanelRuntimeBackend,
    xdotool: str,
    xwininfo: str,
    process: subprocess.Popen[bytes],
    hints: Sequence[str],
    known_window_ids: set[str],
) -> str | None:
    """Wait for a stable new window for the complete launch timeout.

    GUI launchers may exit before their real application window is mapped. The
    previous implementation stopped one second after that exit, which caused
    the first-open external fallback observed on Linux Mint.
    """

    deadline = time.monotonic() + self._launch_timeout
    normalized_hints = tuple(
        dict.fromkeys(hint.strip() for hint in hints if hint.strip())
    )
    observed_family_pids = {int(process.pid)}
    consecutive_candidate: str | None = None
    consecutive_count = 0
    required_candidate_checks = max(3, int(self._stable_parent_checks))
    launcher_exit_logged = False

    while time.monotonic() < deadline:
        observed_family_pids.update(self._process_family(process.pid))
        candidates = self._candidate_window_ids(
            xdotool,
            observed_family_pids,
            normalized_hints,
            known_window_ids,
        )
        candidate = next(
            (
                window_id
                for window_id in candidates
                if self._window_is_viewable(xwininfo, window_id)
            ),
            None,
        )

        if candidate is None:
            consecutive_candidate = None
            consecutive_count = 0
        elif candidate == consecutive_candidate:
            consecutive_count += 1
        else:
            consecutive_candidate = candidate
            consecutive_count = 1

        if candidate is not None and consecutive_count >= required_candidate_checks:
            settle_delay = min(0.4, max(0.15, self._poll_interval * 2))
            time.sleep(settle_delay)
            if self._window_is_viewable(xwininfo, candidate):
                LOGGER.info(
                    "Selected stable new X11 window %s for PID family %s after "
                    "%s consecutive checks.",
                    candidate,
                    sorted(observed_family_pids),
                    consecutive_count,
                )
                return candidate
            consecutive_candidate = None
            consecutive_count = 0

        if process.poll() is not None and not launcher_exit_logged:
            LOGGER.info(
                "Launcher PID %s exited before X11 discovery completed; "
                "continuing until the %.2fs deadline.",
                process.pid,
                self._launch_timeout,
            )
            launcher_exit_logged = True

        time.sleep(self._poll_interval)

    LOGGER.warning(
        "No stable new X11 window was found before the %.2fs deadline for "
        "launcher PID %s and observed PID family %s.",
        self._launch_timeout,
        process.pid,
        sorted(observed_family_pids),
    )
    return None


def _embed_window_cold_start(
    self: X11PanelRuntimeBackend,
    xdotool: str,
    xwininfo: str,
    window_id: str,
    parent_window_id: int,
    panel_id: str,
) -> bool:
    """Reparent a settled window and confirm that the X11 parent stays stable."""

    transition_delay = min(0.25, max(0.08, self._poll_interval))

    for attempt in range(1, self._reparent_attempts + 1):
        LOGGER.info(
            "Embedding panel %s window %s into parent %s: attempt %s/%s.",
            panel_id,
            window_id,
            parent_window_id,
            attempt,
            self._reparent_attempts,
        )

        try:
            time.sleep(transition_delay)
            self._run_xdotool(
                xdotool,
                "windowreparent",
                window_id,
                str(parent_window_id),
            )
            time.sleep(transition_delay)
            self._run_xdotool(xdotool, "windowmap", window_id)
        except Exception:
            LOGGER.warning(
                "Reparent transaction %s failed for panel %s.",
                attempt,
                panel_id,
                exc_info=True,
            )
        else:
            if self._confirm_window_parent(
                xwininfo,
                window_id,
                parent_window_id,
            ):
                return True

        time.sleep(max(self._poll_interval, 0.1))

    return False


def apply_patch() -> None:
    """Apply the LEA-197 remediation exactly once."""

    if getattr(X11PanelRuntimeBackend, _PATCH_MARKER, False):
        return

    X11PanelRuntimeBackend._wait_for_window = _wait_for_window_cold_start
    X11PanelRuntimeBackend._embed_window = _embed_window_cold_start
    setattr(X11PanelRuntimeBackend, _PATCH_MARKER, True)
