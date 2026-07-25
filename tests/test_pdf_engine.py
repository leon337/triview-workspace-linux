from __future__ import annotations

from pathlib import Path

import pytest

from triview_workspace.domain import PanelKind, PanelSpec
from triview_workspace.engines.panel_runtime import (
    PanelRuntimeAvailability,
    PanelRuntimeLaunchRequest,
    PanelRuntimeSession,
)
from triview_workspace.engines.pdf import (
    PdfEngine,
    PdfPanelAdapter,
    X11PdfBackend,
    normalize_pdf_path,
)


class FakeRuntime:
    def __init__(self, embedded: bool = True) -> None:
        self.embedded = embedded
        self.requests: list[PanelRuntimeLaunchRequest] = []
        self.resized: list[tuple[str, int, int]] = []
        self.closed: list[str] = []

    def availability(self, command: tuple[str, ...]) -> PanelRuntimeAvailability:
        return PanelRuntimeAvailability(True, self.embedded, "ok", executable=command[0])

    def launch(self, request: PanelRuntimeLaunchRequest, parent_window_id: int) -> PanelRuntimeSession:
        del parent_window_id
        self.requests.append(request)
        return PanelRuntimeSession(
            request.panel_id,
            request.command,
            None,
            "55" if self.embedded else None,
            self.embedded,
            not self.embedded,
        )

    def resize(self, session: PanelRuntimeSession, width: int, height: int) -> None:
        self.resized.append((session.panel_id, width, height))

    def close(self, session: PanelRuntimeSession) -> None:
        self.closed.append(session.panel_id)


def test_pdf_path_requires_existing_pdf(tmp_path: Path) -> None:
    document = tmp_path / "manual.pdf"
    document.write_bytes(b"%PDF-1.4\n")
    assert normalize_pdf_path(str(document)) == str(document.resolve())
    with pytest.raises(ValueError, match="extensão"):
        normalize_pdf_path(str(tmp_path / "manual.txt"))
    with pytest.raises(ValueError, match="não foi encontrado"):
        normalize_pdf_path(str(tmp_path / "missing.pdf"))


def test_pdf_adapter_validates_document(tmp_path: Path) -> None:
    document = tmp_path / "manual.pdf"
    document.write_bytes(b"%PDF-1.4\n")
    panel = PanelSpec("pdf-1", "Manual", PanelKind.PDF, str(document))
    request = PdfPanelAdapter().build_launch_request(panel)
    assert request["document"] == str(document.resolve())


def test_pdf_engine_manages_viewer_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = tmp_path / "manual.pdf"
    document.write_bytes(b"%PDF-1.4\n")
    runtime = FakeRuntime()
    backend = X11PdfBackend(runtime)  # type: ignore[arg-type]
    monkeypatch.setattr(backend, "_viewer", lambda: "/usr/bin/xreader")
    engine = PdfEngine(backend)

    session = engine.open("pdf-1", "Manual", str(document), 1, 640, 480)

    assert session.embedded
    assert runtime.requests[0].command == ("/usr/bin/xreader", str(document.resolve()))
    assert runtime.resized == [("pdf-1", 640, 480)]
    engine.close_all()
    assert runtime.closed == ["pdf-1"]


def test_pdf_engine_supports_external_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = tmp_path / "manual.pdf"
    document.write_bytes(b"%PDF-1.4\n")
    runtime = FakeRuntime(embedded=False)
    backend = X11PdfBackend(runtime)  # type: ignore[arg-type]
    monkeypatch.setattr(backend, "_viewer", lambda: "/usr/bin/evince")
    session = PdfEngine(backend).open("pdf-1", "Manual", str(document), 1, 100, 100)
    assert session.external
    assert runtime.resized == []
