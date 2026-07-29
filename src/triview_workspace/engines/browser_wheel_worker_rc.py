"""Release-candidate fix for the isolated Browser wheel worker."""

from __future__ import annotations

import subprocess
from typing import Any

from triview_workspace.engines.browser_wheel_worker import (
    ANY_MODIFIER,
    BUTTON_PRESS_MASK,
    BUTTON_RELEASE_MASK,
    GRAB_MODE_ASYNC,
    WheelRoute,
    WheelWorker,
    emit,
)


class ReleaseCandidateWheelWorker(WheelWorker):
    """Forward wheel buttons with a string-safe subprocess argument vector."""

    def _forward(
        self,
        route: WheelRoute,
        button: int,
        pointer_x: int,
        pointer_y: int,
    ) -> None:
        self.x11.XUngrabButton(
            self.display,
            button,
            ANY_MODIFIER,
            route.host_window_id,
        )
        self.x11.XSync(self.display, 0)
        try:
            result = subprocess.run(
                [
                    self.xdotool,
                    "click",
                    "--window",
                    route.browser_window_id,
                    str(button),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            delivered = result.returncode == 0
            error = result.stderr.strip()[:300] if not delivered else ""
        except (OSError, subprocess.SubprocessError) as exc:
            delivered = False
            error = str(exc)[:300]
        finally:
            self.x11.XGrabButton(
                self.display,
                button,
                ANY_MODIFIER,
                route.host_window_id,
                0,
                BUTTON_PRESS_MASK | BUTTON_RELEASE_MASK,
                GRAB_MODE_ASYNC,
                GRAB_MODE_ASYNC,
                0,
                0,
            )
            self.x11.XSync(self.display, 0)
        emit(
            "wheel_event_forwarded",
            **route.as_payload(),
            button=button,
            steps=1 if button == 4 else -1,
            pointer_x=pointer_x,
            pointer_y=pointer_y,
            delivered=delivered,
            error=error,
        )


def main() -> int:
    try:
        worker = ReleaseCandidateWheelWorker()
    except Exception as exc:  # noqa: BLE001
        emit("wheel_bridge_unavailable", error=str(exc))
        return 2
    try:
        return worker.run()
    except Exception as exc:  # noqa: BLE001
        emit("wheel_bridge_failed", error=f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        worker.close()


__all__ = ["ReleaseCandidateWheelWorker", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
