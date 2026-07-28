"""Runtime provenance, event logging and standalone diagnostics for TriView."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

_EVENT_LOCK = threading.Lock()


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def runtime_root() -> Path:
    configured = os.environ.get("TRIVIEW_RUNTIME_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    # .../<release>/src/triview_workspace/runtime_observability.py
    return Path(__file__).resolve().parents[2]


def state_root() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".local" / "state"
    path = base / "triview-workspace"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_candidate_metadata(root: Path | None = None) -> dict[str, Any]:
    path = (root or runtime_root()) / "candidate-release.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _module_origin(module_name: str) -> str | None:
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ValueError):
        return None
    if spec is None or spec.origin is None:
        return None
    return str(Path(spec.origin).resolve())


def runtime_identity(
    *,
    module_name: str = "triview_workspace.gui",
    backend_name: str | None = None,
) -> dict[str, Any]:
    root = runtime_root()
    metadata = load_candidate_metadata(root)
    return {
        "recorded_at": _utc_now(),
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cwd": str(Path.cwd().resolve()),
        "runtime_root": str(root),
        "runtime_root_env": os.environ.get("TRIVIEW_RUNTIME_ROOT"),
        "runtime_sha_env": os.environ.get("TRIVIEW_RUNTIME_SHA"),
        "runtime_module_env": os.environ.get("TRIVIEW_RUNTIME_MODULE"),
        "candidate_metadata": metadata,
        "module_name": module_name,
        "module_origin": _module_origin(module_name),
        "backend_name": backend_name,
        "display": os.environ.get("DISPLAY"),
        "session_type": os.environ.get("XDG_SESSION_TYPE"),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP"),
        "python_path": list(sys.path),
    }


def write_runtime_snapshot(
    *,
    module_name: str = "triview_workspace.gui",
    backend_name: str | None = None,
) -> Path:
    destination = state_root() / "runtime-provenance.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            runtime_identity(module_name=module_name, backend_name=backend_name),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def record_runtime_event(event: str, **fields: Any) -> Path:
    metadata = load_candidate_metadata()
    payload: dict[str, Any] = {
        "timestamp": _utc_now(),
        "event": str(event),
        "pid": os.getpid(),
        "runtime_root": str(runtime_root()),
        "runtime_sha": os.environ.get("TRIVIEW_RUNTIME_SHA")
        or metadata.get("resolved_sha"),
        "runtime_module": os.environ.get("TRIVIEW_RUNTIME_MODULE")
        or metadata.get("module"),
    }
    payload.update(fields)
    destination = state_root() / "runtime-events.jsonl"
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    with _EVENT_LOCK:
        with destination.open("a", encoding="utf-8") as handle:
            handle.write(serialized + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return destination


def _command_report(command: list[str], *, timeout: float = 5.0) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if executable is None:
        return {
            "command": command,
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{command[0]} não encontrado",
        }
    try:
        result = subprocess.run(
            [executable, *command[1:]],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "command": command,
            "available": True,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "command": command,
        "available": True,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def collect_diagnostic_report() -> dict[str, Any]:
    root = runtime_root()
    state = state_root()
    files: dict[str, Any] = {}
    for name in (
        "runtime-provenance.json",
        "runtime-events.jsonl",
        "launcher.log",
        "app.stdout.log",
        "app.stderr.log",
    ):
        path = state / name
        files[name] = {
            "path": str(path),
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
        }

    return {
        "generated_at": _utc_now(),
        "identity": runtime_identity(),
        "runtime_root_exists": root.exists(),
        "candidate_release_path": str(root / "candidate-release.json"),
        "state_files": files,
        "environment": {
            key: os.environ.get(key)
            for key in (
                "DISPLAY",
                "XDG_SESSION_TYPE",
                "XDG_CURRENT_DESKTOP",
                "XDG_DATA_HOME",
                "XDG_STATE_HOME",
                "PYTHONPATH",
                "TRIVIEW_RUNTIME_ROOT",
                "TRIVIEW_RUNTIME_SHA",
                "TRIVIEW_RUNTIME_MODULE",
            )
        },
        "commands": {
            "python": _command_report([sys.executable, "--version"]),
            "xdotool_version": _command_report(["xdotool", "version"]),
            "xwininfo_root": _command_report(["xwininfo", "-root", "-tree"], timeout=8),
            "wmctrl": _command_report(["wmctrl", "-m"]),
            "processes": _command_report(
                ["ps", "-eo", "pid,ppid,pgid,lstart,args"], timeout=8
            ),
        },
    }


def write_diagnostic_report(output_dir: Path | None = None) -> tuple[Path, Path]:
    destination = output_dir or state_root() / "diagnostics"
    destination.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = destination / f"triview-diagnostic-{stamp}.json"
    text_path = destination / f"triview-diagnostic-{stamp}.txt"
    report = collect_diagnostic_report()
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    identity = report["identity"]
    metadata = identity.get("candidate_metadata", {})
    lines = [
        "TRIVIEW WORKSPACE — RELATÓRIO DE DIAGNÓSTICO",
        "=" * 56,
        f"Gerado em: {report['generated_at']}",
        f"Runtime root: {identity.get('runtime_root')}",
        f"SHA instalado: {metadata.get('resolved_sha') or identity.get('runtime_sha_env')}",
        f"Módulo: {metadata.get('module') or identity.get('runtime_module_env')}",
        f"Origem do módulo: {identity.get('module_origin')}",
        f"Python: {identity.get('python_executable')}",
        f"DISPLAY: {identity.get('display')}",
        f"Sessão: {identity.get('session_type')}",
        "",
        "ARQUIVOS DE ESTADO",
        "-" * 56,
    ]
    for name, details in report["state_files"].items():
        lines.append(
            f"{name}: exists={details['exists']} size={details['size']} path={details['path']}"
        )
    lines.extend(("", "COMANDOS", "-" * 56))
    for name, details in report["commands"].items():
        lines.extend(
            (
                f"[{name}] returncode={details['returncode']} available={details['available']}",
                details["stdout"].rstrip(),
                details["stderr"].rstrip(),
                "",
            )
        )
    text_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return text_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico independente do TriView")
    parser.add_argument("--report", action="store_true", help="gera relatório TXT e JSON")
    parser.add_argument("--output-dir", type=Path)
    arguments = parser.parse_args(argv)
    if not arguments.report:
        parser.error("use --report")
    text_path, json_path = write_diagnostic_report(arguments.output_dir)
    print(text_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
