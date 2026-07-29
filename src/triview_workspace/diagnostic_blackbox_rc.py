"""Release-candidate wrapper for byte-safe TriView black-box event tailing."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from triview_workspace.diagnostic_blackbox import (
    DEFAULT_TIMEOUT_SECONDS,
    BlackboxCollector,
    DiagnosticWindow,
    event_base,
    sanitize_runtime_value,
)


class ByteSafeBlackboxCollector(BlackboxCollector):
    """Tail UTF-8 JSONL using byte offsets instead of invalid text cookies."""

    def _runtime_event_loop(self) -> None:
        offset = self.runtime_start_offset
        pending = b""
        while not self.stop_event.wait(0.15):
            if not self.runtime_events_path.exists():
                continue
            try:
                size = self.runtime_events_path.stat().st_size
                if size < offset:
                    offset = 0
                    pending = b""
                if size == offset:
                    continue
                with self.runtime_events_path.open("rb") as handle:
                    handle.seek(offset)
                    chunk = handle.read()
                    offset = handle.tell()
            except OSError as exc:
                self.state.errors.append(f"runtime event reader: {exc}")
                continue

            combined = pending + chunk
            lines = combined.split(b"\n")
            pending = lines.pop() if lines else b""
            for raw_line in lines:
                self._emit_runtime_line(raw_line)

        if pending.strip():
            self._emit_runtime_line(pending)

    def _emit_runtime_line(self, raw_line: bytes) -> None:
        try:
            original = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.state.errors.append("invalid runtime event JSON line")
            return
        if not isinstance(original, dict):
            return
        sanitized = sanitize_runtime_value(original, self.state.redactions)
        payload = {
            **event_base(
                self.state.session_id,
                "triview",
                str(sanitized.get("event", "runtime_event")),
            ),
            "runtime_event": sanitized,
        }
        self.emit("triview", payload)
        if (
            self.auto_stop_on_application_exit
            and sanitized.get("event") == "application_stopped"
            and (
                not sanitized.get("diagnostic_session_id")
                or sanitized.get("diagnostic_session_id") == self.state.session_id
            )
        ):
            self.request_stop("application_stopped")


def run_blackbox(
    output_dir: Path,
    timeout_seconds: int,
    *,
    auto_launch: bool = False,
    auto_stop_on_application_exit: bool = False,
) -> Path:
    collector = ByteSafeBlackboxCollector(
        output_dir,
        timeout_seconds,
        auto_launch=auto_launch,
        auto_stop_on_application_exit=auto_stop_on_application_exit,
    )
    window = DiagnosticWindow(collector)
    window.run()
    return collector.finalize()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sessão explícita e byte-safe de diagnóstico caixa-preta"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--auto-launch", action="store_true")
    parser.add_argument("--auto-stop-on-application-exit", action="store_true")
    arguments = parser.parse_args(argv)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    package = run_blackbox(
        arguments.output_dir,
        arguments.timeout_seconds,
        auto_launch=arguments.auto_launch,
        auto_stop_on_application_exit=arguments.auto_stop_on_application_exit,
    )
    print(package)
    return 0


__all__ = ["ByteSafeBlackboxCollector", "main", "run_blackbox"]


if __name__ == "__main__":
    raise SystemExit(main())
