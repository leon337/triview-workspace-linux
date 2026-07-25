from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from triview_workspace.engines.capture import (
    CaptureAvailability,
    CaptureEngine,
    CaptureEngineError,
    CaptureRequest,
    X11CaptureBackend,
)


class FakeCaptureBackend:
    def availability(self) -> CaptureAvailability:
        return CaptureAvailability(True, "ok", "fake", "/usr/bin/fake")

    def capture(self, request: CaptureRequest) -> str:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"PNG")
        return "fake"


def test_capture_engine_organizes_file_and_history(tmp_path: Path) -> None:
    engine = CaptureEngine(FakeCaptureBackend(), tmp_path)
    result = engine.capture(
        "Meu Workspace",
        "Painel / 1",
        "ChatGPT",
        123,
        now=datetime(2026, 7, 25, 3, 4, 5, 6000, tzinfo=UTC),
    )

    path = Path(result.path)
    assert path.is_file()
    assert path.relative_to(tmp_path).parts[:3] == (
        "Meu-Workspace",
        "Painel-1",
        "2026-07-25",
    )
    assert path.name == "030405-006000.png"
    history = engine.history_path.read_text(encoding="utf-8").splitlines()
    assert len(history) == 1
    payload = json.loads(history[0])
    assert payload["panel_id"] == "Painel / 1"
    assert payload["backend"] == "fake"
    assert payload["window_id"] == 123


def test_capture_engine_rejects_invalid_window_id(tmp_path: Path) -> None:
    engine = CaptureEngine(FakeCaptureBackend(), tmp_path)
    with pytest.raises(CaptureEngineError, match="identificador"):
        engine.capture("workspace", "panel", "Panel", 0)


def test_x11_capture_backend_reports_missing_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    report = X11CaptureBackend().availability()
    assert report.available is False
    assert "DISPLAY" in report.reason


def test_x11_capture_backend_reports_missing_capture_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setattr("triview_workspace.engines.capture.shutil.which", lambda name: None)
    report = X11CaptureBackend().availability()
    assert report.available is False
    assert "maim" in report.reason
