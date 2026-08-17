from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_release_candidate_has_new_unique_version() -> None:
    assert _project_version() == "1.0.0a4"


def test_readme_release_status_matches_package_version() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "versão de liberação: `1.0.0a4`" in readme


def test_changelog_starts_with_candidate_release() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 1.0.0a4 —" in changelog
