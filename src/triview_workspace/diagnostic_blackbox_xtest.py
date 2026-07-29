"""XTEST-aware final diagnostics for the physically accepted Xephyr runtime.

The Browser wheel bridge forwards one physical wheel release with ``xdotool``.
That forwarding uses the XTEST virtual pointer and is visible to ``xinput
 test-xi2`` as a second XI2 event. This collector keeps both events for audit,
but only physical-device events participate in the one-to-one release verdict.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from triview_workspace.diagnostic_blackbox import (
    DEFAULT_TIMEOUT_SECONDS,
    DiagnosticWindow,
    event_base,
    pointer_snapshot,
)
from triview_workspace.diagnostic_blackbox_shareable import (
    parse_shareable_xinput_event,
)
from triview_workspace.diagnostic_blackbox_xephyr import (
    XephyrVerifiedBlackboxCollector,
)

_DEVICE_ID_PATTERN = re.compile(r"\bid=(\d+)\b")
_INTEGER_PATTERN = re.compile(r"-?\d+")


def xtest_device_ids() -> frozenset[int]:
    """Return XTEST virtual-device IDs without exporting device names."""

    executable = shutil.which("xinput")
    if executable is None:
        return frozenset()
    try:
        result = subprocess.run(
            [executable, "list", "--short"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if result.returncode != 0:
        return frozenset()
    device_ids: set[int] = set()
    for line in result.stdout.splitlines():
        if "xtest" not in line.casefold():
            continue
        match = _DEVICE_ID_PATTERN.search(line)
        if match is not None:
            device_ids.add(int(match.group(1)))
    return frozenset(device_ids)


def xi2_device_pair(lines: list[str]) -> tuple[int | None, int | None]:
    """Extract XI2 master/source IDs from one sanitized event block."""

    details: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.strip().split(":", 1)
        details[key.strip().casefold().replace(" ", "_")] = value.strip()

    device_numbers = [
        int(value) for value in _INTEGER_PATTERN.findall(details.get("device", ""))
    ]
    device_id = device_numbers[0] if device_numbers else None
    source_device_id = device_numbers[1] if len(device_numbers) > 1 else None
    explicit_source = _INTEGER_PATTERN.search(
        details.get("sourceid", "") or details.get("source_id", "")
    )
    if explicit_source is not None:
        source_device_id = int(explicit_source.group(0))
    return device_id, source_device_id


def annotate_xinput_origin(
    payload: dict[str, Any],
    lines: list[str],
    *,
    synthetic_device_ids: frozenset[int],
) -> dict[str, Any]:
    """Attach non-sensitive XI2 origin metadata and classify XTEST events."""

    device_id, source_device_id = xi2_device_pair(lines)
    direct_xtest_device = device_id in synthetic_device_ids
    source_identity_available = source_device_id is not None
    classifier_available = bool(synthetic_device_ids) and (
        source_identity_available or direct_xtest_device
    )
    synthetic = bool(
        classifier_available
        and (
            direct_xtest_device
            or source_device_id in synthetic_device_ids
        )
    )
    return {
        **payload,
        "device_id": device_id,
        "source_device_id": source_device_id,
        "synthetic": synthetic,
        "synthetic_origin": "x11_xtest" if synthetic else None,
        "synthetic_classifier_available": classifier_available,
    }


class XTestAwareXephyrBlackboxCollector(XephyrVerifiedBlackboxCollector):
    """Keep XTEST evidence while excluding it from physical-input accounting."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.synthetic_device_ids = xtest_device_ids()

    def _emit_xinput_block(self, block: list[str]) -> None:
        parsed = parse_shareable_xinput_event(
            block,
            safe_keymap=self.safe_keymap,
            pointer=pointer_snapshot(),
        )
        if parsed is None:
            return
        parsed = annotate_xinput_origin(
            parsed,
            block,
            synthetic_device_ids=self.synthetic_device_ids,
        )
        if parsed.get("input_category") == "text_key":
            self.state.redactions["literal_keyboard_key"] += 1
        self.emit(
            "user",
            {
                **event_base(
                    self.state.session_id,
                    "user_input",
                    "user_input_observed",
                ),
                **parsed,
            },
        )

    @staticmethod
    def _correlated_scroll_finding(
        runtime_records: list[tuple[dict[str, Any], dict[str, Any]]],
        input_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        observed_wheel = [
            event
            for event in input_events
            if event.get("input_category") == "mouse_wheel"
        ]
        classifier_available = bool(observed_wheel) and all(
            event.get("synthetic_classifier_available") is True
            for event in observed_wheel
        )
        synthetic_wheel = [
            event for event in observed_wheel if event.get("synthetic") is True
        ]
        physical_events = [
            event
            for event in input_events
            if event.get("input_category") != "mouse_wheel"
            or event.get("synthetic") is not True
        ]
        finding = XephyrVerifiedBlackboxCollector._correlated_scroll_finding(
            runtime_records,
            physical_events,
        )
        finding.update(
            observed_wheel_events=len(observed_wheel),
            physical_wheel_events=len(observed_wheel) - len(synthetic_wheel),
            synthetic_wheel_events=len(synthetic_wheel),
            synthetic_classifier_available=classifier_available,
        )
        if observed_wheel and not classifier_available:
            finding["status"] = "INDETERMINATE_XTEST_CLASSIFIER_UNAVAILABLE"
        elif synthetic_wheel and str(finding.get("status", "")).startswith("PASS_"):
            finding["status"] = "PASS_ONE_TO_ONE_MATCHED_X11_PANEL_FILTERED_XTEST"
        return finding


def run_blackbox(
    output_dir: Path,
    timeout_seconds: int,
    *,
    auto_launch: bool = False,
    auto_stop_on_application_exit: bool = False,
) -> Path:
    collector = XTestAwareXephyrBlackboxCollector(
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
        description="Diagnóstico Xephyr com separação de entrada física e XTEST"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
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


__all__ = [
    "XTestAwareXephyrBlackboxCollector",
    "annotate_xinput_origin",
    "main",
    "run_blackbox",
    "xi2_device_pair",
    "xtest_device_ids",
]


if __name__ == "__main__":
    raise SystemExit(main())
