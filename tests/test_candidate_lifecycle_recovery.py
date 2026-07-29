from __future__ import annotations

import fcntl
import json
import os
import subprocess
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-module-candidate.sh"
UPDATER = ROOT / "scripts" / "candidate-update.sh"
ROLLBACK = ROOT / "scripts" / "candidate-rollback.sh"


def _source_archive(destination: Path) -> Path:
    with tarfile.open(destination, "w:gz") as archive:
        for relative in (
            Path("pyproject.toml"),
            Path("config"),
            Path("scripts"),
            Path("src"),
        ):
            source = ROOT / relative
            archive.add(source, arcname=Path("snapshot") / relative)
    return destination


def _candidate_env(tmp_path: Path, archive: Path) -> tuple[dict[str, str], Path, Path, Path]:
    home = tmp_path / "home"
    app_root = tmp_path / "candidate"
    data_root = tmp_path / "data"
    state_root = tmp_path / "state"
    home.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_CANDIDATE_ROOT": str(app_root),
            "TRIVIEW_CANDIDATE_DATA_ROOT": str(data_root),
            "TRIVIEW_CANDIDATE_STATE_ROOT": str(state_root),
            "TRIVIEW_TEST_SOURCE_ARCHIVE": str(archive),
            "TRIVIEW_NONINTERACTIVE": "1",
        }
    )
    return env, app_root, data_root, state_root


def test_post_switch_interruption_is_repaired_by_idempotent_rerun(tmp_path: Path) -> None:
    archive = _source_archive(tmp_path / "source.tar.gz")
    env, app_root, _data_root, state_root = _candidate_env(tmp_path, archive)
    sha = "c" * 40
    args = [
        "bash",
        str(INSTALLER),
        "RECOVERY-TEST",
        sha,
        "triview_workspace.gui",
        sha,
    ]

    interrupted_env = env | {"TRIVIEW_TEST_FAIL_AFTER_SWITCH": "1"}
    interrupted = subprocess.run(
        args,
        env=interrupted_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert interrupted.returncode != 0
    assert "Interrupção controlada depois da troca atômica" in interrupted.stderr
    assert (app_root / "current").is_symlink()
    assert not (Path(env["HOME"]) / ".local/bin/triview-workspace-recovery-test").exists()

    pending = state_root / "triview-workspace/transactions"
    assert len(list(pending.glob("*.json"))) == 1

    recovered = subprocess.run(
        args,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert "Reconciliando a instalação existente" in recovered.stdout

    bin_dir = Path(env["HOME"]) / ".local/bin"
    applications = Path(env["HOME"]) / ".local/share/applications"
    desktop = Path(env["HOME"]) / "Área de Trabalho"
    expected = {
        "triview-workspace-recovery-test",
        "triview-workspace-recovery-test-update",
        "triview-workspace-recovery-test-diagnose",
        "triview-workspace-recovery-test-rollback",
    }
    assert {path.name for path in bin_dir.glob("triview-workspace-recovery-test*")} == expected
    assert len(list(applications.glob("triview-workspace-recovery-test*.desktop"))) == 4
    assert len(list(desktop.glob("triview-workspace-recovery-test*.desktop"))) == 4
    assert list(pending.glob("*.json")) == []
    assert len(list((pending / "reconciled").glob("*.json"))) == 1

    reports = sorted((state_root / "triview-workspace/switch-reports").glob("*.json"))
    payload = json.loads(reports[-1].read_text(encoding="utf-8"))
    assert payload["event"] == "idempotent_update_reconciled"
    assert payload["changed"] is False
    assert payload["reconciled_transactions"] == 1


def test_shared_lifecycle_lock_rejects_install_update_and_rollback(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app_root = tmp_path / "candidate"
    data_root = tmp_path / "data"
    state_root = tmp_path / "state"
    release = app_root / "releases/current-release"
    home.mkdir()
    release.mkdir(parents=True)
    data_root.mkdir()
    state_root.mkdir()
    (app_root / "current").symlink_to(release)

    app_state = state_root / "triview-workspace"
    app_state.mkdir(parents=True)
    lock_path = app_state / "lifecycle.lock"
    env = os.environ.copy() | {
        "HOME": str(home),
        "TRIVIEW_CANDIDATE_ROOT": str(app_root),
        "TRIVIEW_CANDIDATE_DATA_ROOT": str(data_root),
        "TRIVIEW_CANDIDATE_STATE_ROOT": str(state_root),
        "TRIVIEW_NONINTERACTIVE": "1",
    }

    with lock_path.open("w") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        commands = (
            [
                "bash",
                str(INSTALLER),
                "LOCK-TEST",
                "d" * 40,
                "triview_workspace.gui",
                "d" * 40,
            ],
            [
                "bash",
                str(UPDATER),
                "LOCK-TEST",
                str(app_root),
                str(data_root),
                str(state_root),
                "triview_workspace.gui",
                "d" * 40,
                "leon337/triview-workspace-linux",
            ],
            [
                "bash",
                str(ROLLBACK),
                "LOCK-TEST",
                str(app_root),
                str(data_root),
                str(state_root),
                "triview_workspace.gui",
            ],
        )
        for command in commands:
            result = subprocess.run(
                command,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 2
            assert "outra operação de instalação, atualização ou rollback" in (
                result.stdout + result.stderr
            )
