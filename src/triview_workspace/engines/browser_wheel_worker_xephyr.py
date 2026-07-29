"""Correlated wheel worker that preserves live route ancestry and geometry."""

from __future__ import annotations

import json

from triview_workspace.engines.browser_wheel_worker import emit
from triview_workspace.engines.browser_wheel_worker_final import CorrelatedWheelWorker


class XephyrWheelRoute:
    def __init__(
        self,
        runtime_id: str,
        host_window_id: int,
        browser_window_id: str,
        host_ancestry: tuple[int, ...] = (),
        browser_ancestry: tuple[int, ...] = (),
        host_x: int | None = None,
        host_y: int | None = None,
        host_width: int | None = None,
        host_height: int | None = None,
    ) -> None:
        self.runtime_id = runtime_id
        self.host_window_id = int(host_window_id)
        self.browser_window_id = str(browser_window_id)
        self.host_ancestry = tuple(int(item) for item in host_ancestry)
        self.browser_ancestry = tuple(int(item) for item in browser_ancestry)
        self.host_x = int(host_x) if host_x is not None else None
        self.host_y = int(host_y) if host_y is not None else None
        self.host_width = int(host_width) if host_width is not None else None
        self.host_height = int(host_height) if host_height is not None else None

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "XephyrWheelRoute":
        return cls(
            runtime_id=str(payload["runtime_id"]),
            host_window_id=int(payload["host_window_id"]),
            browser_window_id=str(payload["browser_window_id"]),
            host_ancestry=tuple(int(item) for item in payload.get("host_ancestry", [])),
            browser_ancestry=tuple(
                int(item) for item in payload.get("browser_ancestry", [])
            ),
            host_x=payload.get("host_x"),
            host_y=payload.get("host_y"),
            host_width=payload.get("host_width"),
            host_height=payload.get("host_height"),
        )

    def as_payload(self) -> dict[str, object]:
        return {
            "runtime_id": self.runtime_id,
            "host_window_id": self.host_window_id,
            "browser_window_id": self.browser_window_id,
            "host_ancestry": list(self.host_ancestry),
            "browser_ancestry": list(self.browser_ancestry),
            "host_x": self.host_x,
            "host_y": self.host_y,
            "host_width": self.host_width,
            "host_height": self.host_height,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, XephyrWheelRoute):
            return False
        return self.as_payload() == other.as_payload()


class XephyrCorrelatedWheelWorker(CorrelatedWheelWorker):
    """Parse geometry-aware routes while retaining exact X11 correlation."""

    def _handle_command(self, line: str) -> None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            emit("wheel_bridge_command_rejected", reason="invalid_json")
            return
        action = payload.get("action")
        if action == "stop":
            self.running = False
            return
        if action != "sync":
            emit("wheel_bridge_command_rejected", reason="unknown_action")
            return
        routes: dict[int, XephyrWheelRoute] = {}
        try:
            for item in payload.get("routes", []):
                route = XephyrWheelRoute.from_payload(item)
                routes[route.host_window_id] = route
        except (KeyError, TypeError, ValueError) as exc:
            emit("wheel_bridge_command_rejected", reason=str(exc))
            return
        self._sync_routes(routes)


def main() -> int:
    try:
        worker = XephyrCorrelatedWheelWorker()
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


__all__ = ["XephyrCorrelatedWheelWorker", "XephyrWheelRoute", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
