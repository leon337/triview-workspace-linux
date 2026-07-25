from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCUMENTS = (
    "docs/README.md",
    "docs/product/VISION.md",
    "docs/product/PRINCIPLES.md",
    "docs/product/ROADMAP.md",
    "docs/product/RELEASE_HISTORY.md",
    "docs/architecture/README.md",
    "docs/architecture/ENGINES.md",
    "docs/factory/SOFTWARE_FACTORY_WORKFLOW.md",
    "docs/factory/DEVELOPMENT_TRAIN_LEA-197-205.md",
    "docs/decisions/ADR-0005-application-engine-panel-runtime.md",
    "docs/decisions/ADR-0006-terminal-engine-emulator-adapters.md",
    "docs/decisions/ADR-0007-pdf-viewer-runtime.md",
    "docs/decisions/ADR-0008-panel-window-capture.md",
    "docs/decisions/ADR-0009-panel-region-recording-ffmpeg.md",
    "docs/work/LEA-197.md",
    "docs/work/LEA-198.md",
    "docs/work/LEA-199.md",
    "docs/work/LEA-200.md",
    "docs/work/LEA-201.md",
)
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")


def test_required_documentation_exists() -> None:
    missing = [path for path in REQUIRED_DOCUMENTS if not (ROOT / path).is_file()]
    assert not missing, f"Required documentation is missing: {missing}"


def test_internal_markdown_links_resolve() -> None:
    broken: list[str] = []
    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    for document in markdown_files:
        text = document.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(text):
            target = raw_target.split("#", 1)[0]
            if not target or target.startswith(("http://", "https://")):
                continue
            resolved = (document.parent / target).resolve()
            if not resolved.is_file():
                broken.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not broken, "Broken Markdown links:\n" + "\n".join(broken)


def test_roadmap_tracks_the_development_train() -> None:
    roadmap = (ROOT / "docs/product/ROADMAP.md").read_text(encoding="utf-8")
    for heading in (
        "Application Engine",
        "Terminal Engine",
        "PDF Engine",
        "Capture Engine",
        "Recording Engine",
        "Plugin Engine",
        "Layout Engine avançado",
        "Session Engine completo",
        "Workspace Hub",
    ):
        assert heading in roadmap
    assert "train/road-to-1.0" in roadmap
    for identifier in ("LEA-197", "LEA-198", "LEA-199", "LEA-200", "LEA-201"):
        assert identifier in roadmap
    assert roadmap.count("Status: **planejado**") >= 4


def test_candidate_documentation_distinguishes_stable_and_candidate() -> None:
    index = (ROOT / "docs/README.md").read_text(encoding="utf-8").lower()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "versão estável" in index
    assert "candidato atual" in index
    assert "`main`: estável" in readme
    assert "TriView Workspace — LEA-201" in readme
