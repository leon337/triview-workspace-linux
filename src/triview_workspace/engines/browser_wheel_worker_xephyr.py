"""Correlated wheel worker that preserves live X11 route ancestry."""

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
    ) -> None:
        self.runtime_id = runtime_id
        self.host_window_id = int(host_window_id)
        self.browser_window_id = str(browser_window_id)
        self.host_ancestry = tuple(int(item) for item in host_ancestry)
        self.browser_ancestry = tuple(int(item) for item in browser_ancestry)

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
        )

    def as_payload(self) -> dict[str, object]:
        return {
            "runtime_id": self.runtime_id,
            "host_window_id": self.host_window_id,
            "browser_window_id": self.browser_window_id,
            "host_ancestry": list(self.host_ancestry),
            "browser_ancestry": list(self.browser_ancestry),
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, XephyrWheelRoute):
            return False
        return self.as_payload() == other.as_payload()


class XephyrCorrelatedWheelWorker(CorrelatedWheelWorker):
    """Parse ancestry-aware routes while retaining the final correlation logic."""

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
