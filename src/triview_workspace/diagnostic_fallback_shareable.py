"""Sanitized fallback package when the interactive black-box cannot start."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from triview_workspace.diagnostic_blackbox import runtime_identity, state_root
from triview_workspace.diagnostic_blackbox_final import (
    strict_relevant_processes,
    strict_sanitize_runtime_value,
)
from triview_workspace.diagnostic_blackbox_shareable import (
    sanitize_generic_string,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sanitized_log(path: Path, redactions: Counter[str], limit: int = 300) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return []
    return [sanitize_generic_string(line, redactions) for line in lines]


def _sanitized_runtime_events(
    path: Path,
    redactions: Counter[str],
    limit: int = 500,
) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            sanitized = strict_sanitize_runtime_value(payload, redactions)
            if isinstance(sanitized, dict):
                events.append(sanitized)
    return events


def build_shareable_fallback(output_dir: Path, reason: str) -> Path:
    redactions: Counter[str] = Counter()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = output_dir / f"triview-fallback-shareable-{stamp}"
    root.mkdir(parents=True, exist_ok=False)
    state = state_root()

    provenance_source = state / "runtime-provenance.json"
    provenance = _read_json(provenance_source) or runtime_identity()
    sanitized_provenance = strict_sanitize_runtime_value(provenance, redactions)
    (root / "runtime-provenance.json").write_text(
        json.dumps(sanitized_provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    runtime_events = _sanitized_runtime_events(
        state / "runtime-events.jsonl",
        redactions,
    )
    with (root / "runtime-events.jsonl").open("w", encoding="utf-8") as handle:
        for event in runtime_events:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    processes = strict_relevant_processes(redactions)
    (root / "processes.json").write_text(
        json.dumps(
            [
                {
                    "pid": pid,
                    "ppid": values[0],
                    "pgid": values[1],
                    "elapsed_seconds": values[2],
                    "command": values[3],
                    "arguments": values[4],
                }
                for pid, values in sorted(processes.items())
            ],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    logs = {
        "launcher": _sanitized_log(state / "launcher.log", redactions),
        "application_stderr": _sanitized_log(state / "app.stderr.log", redactions),
        "diagnostic_stderr": _sanitized_log(
            state / "diagnostic-blackbox.stderr.log",
            redactions,
        ),
    }
    (root / "logs-sanitized.json").write_text(
        json.dumps(logs, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "FALLBACK_SANITIZED_PARTIAL_EVIDENCE",
        "interactive_blackbox_completed": False,
        "shareable": True,
        "reason": sanitize_generic_string(reason, redactions),
        "runtime_event_count": len(runtime_events),
        "process_count": len(processes),
        "limitations": [
            "não contém a linha do tempo completa de input da sessão",
            "não pode emitir PASS para scroll, exposição externa ou continuidade",
            "serve apenas para diagnosticar por que a caixa-preta interativa falhou",
        ],
    }
    (root / "fallback-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    privacy = {
        "mode": "shareable_sanitized_fallback",
        "literal_text_captured": False,
        "clipboard_captured": False,
        "screenshots_captured": False,
        "audio_captured": False,
        "raw_provenance_included": False,
        "raw_process_arguments_included": False,
        "raw_runtime_events_included": False,
        "redaction_counts": dict(redactions),
    }
    (root / "privacy-redaction-report.json").write_text(
        json.dumps(privacy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / "README.txt").write_text(
        "TriView — diagnóstico de contingência sanitizado\n\n"
        "Este pacote pode ser compartilhado. Ele não contém o registro completo da "
        "sessão e não deve ser interpretado como PASS funcional.\n",
        encoding="utf-8",
    )

    package = root.with_suffix(".zip")
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.iterdir()):
            archive.write(path, arcname=path.name)
    shutil.rmtree(root)
    return package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fallback sanitizado do TriView")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reason", required=True)
    arguments = parser.parse_args(argv)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    package = build_shareable_fallback(arguments.output_dir, arguments.reason)
    print(package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
