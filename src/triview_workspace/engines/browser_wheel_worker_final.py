"""Final wheel worker with deterministic X11 event correlation."""

from __future__ import annotations

import ctypes
import subprocess

from triview_workspace.engines.browser_wheel_worker import (
    ANY_MODIFIER,
    BUTTON_PRESS_MASK,
    BUTTON_RELEASE,
    BUTTON_RELEASE_MASK,
    GRAB_MODE_ASYNC,
    WHEEL_BUTTONS,
    WheelRoute,
    XEvent,
    emit,
)
from triview_workspace.engines.browser_wheel_worker_rc import (
    ReleaseCandidateWheelWorker,
)


class CorrelatedWheelWorker(ReleaseCandidateWheelWorker):
    """Forward wheel releases and expose the original X server timestamp."""

    def _drain_x_events(self) -> None:
        while self.x11.XPending(self.display) > 0:
            event = XEvent()
            self.x11.XNextEvent(self.display, ctypes.byref(event))
            if event.type != BUTTON_RELEASE:
                continue
            button = int(event.xbutton.button)
            if button not in WHEEL_BUTTONS:
                continue
            host_window_id = int(event.xbutton.window)
            route = self.routes.get(host_window_id)
            if route is None:
                emit(
                    "wheel_event_unrouted",
                    host_window_id=host_window_id,
                    button=button,
                    x11_time=int(event.xbutton.time),
                    x11_serial=int(event.xbutton.serial),
                )
                continue
            self._forward_correlated(
                route,
                button,
                int(event.xbutton.x_root),
                int(event.xbutton.y_root),
                int(event.xbutton.time),
                int(event.xbutton.serial),
            )

    def _forward_correlated(
        self,
        route: WheelRoute,
        button: int,
        pointer_x: int,
        pointer_y: int,
        x11_time: int,
        x11_serial: int,
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
            x11_time=x11_time,
            x11_serial=x11_serial,
            input_correlation_id=f"wheel:{x11_time}:{button}",
            delivered=delivered,
            error=error,
        )


def main() -> int:
    try:
        worker = CorrelatedWheelWorker()
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


__all__ = ["CorrelatedWheelWorker", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
