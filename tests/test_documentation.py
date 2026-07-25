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
    "docs/decisions/ADR-0001-workspace-platform.md",
    "docs/decisions/ADR-0002-documentation-source-of-truth.md",
    "docs/decisions/ADR-0003-browser-x11-reparenting.md",
    "docs/decisions/ADR-0004-versioned-workspace-catalog.md",
    "docs/work/LEA-196.md",
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


def test_roadmap_distinguishes_completed_and_planned_capabilities() -> None:
    roadmap = (ROOT / "docs/product/ROADMAP.md").read_text(encoding="utf-8")
    for heading in (
        "Primeiro painel funcional",
        "Workspaces persistentes",
        "Captura individual de imagem",
        "Gravação individual por painel",
        "Plugins",
    ):
        assert heading in roadmap
    assert "catálogo JSON com esquema versionado" in roadmap
    assert roadmap.count("Status: **planejado**") >= 7
