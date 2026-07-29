from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STABLE_LAUNCH = ROOT / "scripts" / "stable-launch.sh"
STABLE_DIAGNOSE = ROOT / "scripts" / "stable-diagnose.sh"


def _base_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path, Path]:
    home = tmp_path / "home"
    app_root = tmp_path / "app"
    data_home = tmp_path / "data"
    state_home = tmp_path / "state"
    home.mkdir()
    (app_root / "releases").mkdir(parents=True)
    data_home.mkdir()
    state_home.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(app_root),
            "XDG_DATA_HOME": str(data_home),
            "XDG_STATE_HOME": str(state_home),
            "TRIVIEW_DISABLE_SYSTEM_PACKAGE_INSTALL": "1",
        }
    )
    return env, app_root, data_home, state_home


def test_stable_launcher_sets_runtime_provenance_and_forwards_arguments(
    tmp_path: Path,
) -> None:
    env, app_root, data_home, state_home = _base_environment(tmp_path)
    release = app_root / "releases" / "1.0.0a3"
    source = release / "src"
    source.mkdir(parents=True)
    output = tmp_path / "probe.json"
    (source / "stable_probe.py").write_text(
        """from __future__ import annotations

import json
import os
import pathlib
import sys

payload = {
    "argv": sys.argv[1:],
    "data_home": os.environ["XDG_DATA_HOME"],
    "state_home": os.environ["XDG_STATE_HOME"],
    "app_root": os.environ["TRIVIEW_APP_ROOT"],
    "runtime_root": os.environ["TRIVIEW_RUNTIME_ROOT"],
    "runtime_sha": os.environ["TRIVIEW_RUNTIME_SHA"],
    "runtime_version": os.environ["TRIVIEW_RUNTIME_VERSION"],
    "runtime_module": os.environ["TRIVIEW_RUNTIME_MODULE"],
}
pathlib.Path(os.environ["PROBE_OUTPUT"]).write_text(json.dumps(payload), encoding="utf-8")
""",
        encoding="utf-8",
    )
    (app_root / "current").symlink_to(release)
    (app_root / "VERSION").write_text("1.0.0a3\n", encoding="utf-8")
    (app_root / "ACTIVE-CANDIDATE.json").write_text(
        json.dumps({"ref": "a" * 40}),
        encoding="utf-8",
    )
    env.update(
        {
            "TRIVIEW_STABLE_MODULE": "stable_probe",
            "PROBE_OUTPUT": str(output),
        }
    )

    subprocess.run(
        ["bash", str(STABLE_LAUNCH), "--sample", "value"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["argv"] == ["--sample", "value"]
    assert payload["data_home"] == str(data_home)
    assert payload["state_home"] == str(state_home)
    assert payload["app_root"] == str(app_root)
    assert payload["runtime_root"] == str(release)
    assert payload["runtime_sha"] == "a" * 40
    assert payload["runtime_version"] == "1.0.0a3"
    assert payload["runtime_module"] == "stable_probe"
    assert not (state_home / "triview-workspace" / "app.pid").exists()
    launch_log = (state_home / "triview-workspace" / "launcher.log").read_text(
        encoding="utf-8"
    )
    assert "version=1.0.0a3" in launch_log
    assert "exit_status=0" in launch_log


def test_stable_launcher_reuses_the_single_instance_lock(tmp_path: Path) -> None:
    env, app_root, _data_home, state_home = _base_environment(tmp_path)
    release = app_root / "releases" / "1.0.0a3"
    (release / "src").mkdir(parents=True)
    (app_root / "current").symlink_to(release)
    lock_dir = state_home / "triview-workspace"
    lock_dir.mkdir(parents=True)
    lock_file = lock_dir / "app.lock"
    ready = tmp_path / "ready"
    holder = subprocess.Popen(
        [
            "flock",
            str(lock_file),
            "bash",
            "-c",
            'touch "$1"; sleep 30',
            "holder",
            str(ready),
        ],
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        completed = subprocess.run(
            ["bash", str(STABLE_LAUNCH)],
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0
        launch_log = (lock_dir / "launcher.log").read_text(encoding="utf-8")
        assert "result=existing_instance_activated" in launch_log
    finally:
        if holder.poll() is None:
            os.killpg(holder.pid, signal.SIGTERM)
            holder.wait(timeout=5)


def test_stable_diagnostic_controller_returns_one_sanitized_package(
    tmp_path: Path,
) -> None:
    env, app_root, _data_home, state_home = _base_environment(tmp_path)
    release = app_root / "releases" / "1.0.0a3"
    package = release / "src" / "triview_workspace"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "diagnostic_blackbox_xtest.py").write_text(
        """from __future__ import annotations

import pathlib
import sys

output_dir = pathlib.Path(sys.argv[sys.argv.index("--output-dir") + 1])
output_dir.mkdir(parents=True, exist_ok=True)
archive = output_dir / "stable-diagnostic.zip"
archive.write_bytes(b"PK\\x05\\x06" + b"\\x00" * 18)
print(archive)
""",
        encoding="utf-8",
    )
    (package / "diagnostic_fallback_shareable.py").write_text(
        "raise SystemExit(99)\n",
        encoding="utf-8",
    )
    (app_root / "current").symlink_to(release)
    (app_root / "VERSION").write_text("1.0.0a3\n", encoding="utf-8")
    (app_root / "ACTIVE-CANDIDATE.json").write_text(
        json.dumps({"ref": "b" * 40}),
        encoding="utf-8",
    )
    env.update(
        {
            "TRIVIEW_DIAGNOSTIC_NO_OPEN": "1",
            "TRIVIEW_STABLE_MODULE": "triview_workspace.cli",
        }
    )

    completed = subprocess.run(
        ["bash", str(STABLE_DIAGNOSE)],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    report_dir = state_home / "triview-workspace" / "diagnostics"
    archives = list(report_dir.glob("*.zip"))
    assert len(archives) == 1
    assert archives[0].is_file()
    assert "Pacote de diagnóstico estável:" in completed.stdout
    assert str(archives[0]) in completed.stdout
