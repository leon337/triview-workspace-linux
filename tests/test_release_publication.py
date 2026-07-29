from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-bootstrap-release.yml"


def test_existing_release_must_point_to_current_main_sha() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "resolve_remote_tag_sha" in text
    assert 'existing_tag_sha="$(resolve_remote_tag_sha)"' in text
    assert '"$existing_tag_sha" != "$GITHUB_SHA"' in text
    assert "Release $TAG existe sem uma tag verificável no SHA atual." in text
    assert "--verify-tag" in text
    assert "fetch-depth: 0" in text


def test_release_creation_remains_after_full_verification() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "release:\n    needs: verify" in text
    assert "pytest --junitxml=release-pytest-results.xml" in text
    assert "tests/test_browser_wheel_x11_integration.py" in text
    assert "tests/test_browser_xephyr_x11_integration.py" in text
    assert 'gh release create "${release_args[@]}"' in text
