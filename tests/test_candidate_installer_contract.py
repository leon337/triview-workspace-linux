from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_INSTALLER = ROOT / "scripts" / "install-module-candidate.sh"
RC4_INSTALLER = ROOT / "scripts" / "install-train-candidate.sh"


def test_module_installer_resolves_mutable_ref_to_immutable_sha() -> None:
    script = MODULE_INSTALLER.read_text(encoding="utf-8")

    assert "https://api.github.com/repos/$REPO/commits/$encoded_ref" in script
    assert "RESOLVED_SHA" in script
    assert "archive/$RESOLVED_SHA.tar.gz" in script
    assert '[[ "$RESOLVED_SHA" =~ ^[0-9a-f]{40}$ ]]' in script


def test_module_installer_records_release_identity_and_previous_candidate() -> None:
    script = MODULE_INSTALLER.read_text(encoding="utf-8")

    assert "candidate-release.json" in script
    assert '"resolved_sha": resolved_sha' in script
    assert 'previous_link="$APP_ROOT/previous"' in script
    assert 'mv -Tf "$current_temp" "$current_link"' in script


def test_module_installer_rejects_unsafe_archive_entries() -> None:
    script = MODULE_INSTALLER.read_text(encoding="utf-8")

    assert "path.is_absolute()" in script
    assert '".." in path.parts' in script


def test_rc4_installer_requires_full_sha_and_opens_approved_gui() -> None:
    script = RC4_INSTALLER.read_text(encoding="utf-8")

    assert "TRIVIEW_CANDIDATE_REF" in script
    assert "git -C \"$REPO_ROOT\" rev-parse HEAD" in script
    assert '[[ ! "$SOURCE_REF" =~ ^[0-9a-fA-F]{40}$ ]]' in script
    assert '"RC4-1.0.0A1"' in script
    assert '"triview_workspace.gui"' in script
    assert "train/road-to-1.0" not in script
    assert "triview_workspace.gui_hub" not in script
