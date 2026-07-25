from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from triview_workspace.engines.recording import (
    RecordingAvailability,
    RecordingEngine,
    RecordingEngineError,
    RecordingRequest,
    RecordingSession,
    X11FfmpegRecordingBackend,
)


class FakeRecordingBackend:
    def __init__(self) -> None:
        self.started: list[RecordingRequest] = []
        self.stopped: list[str] = []

    def availability(self) -> RecordingAvailability:
        return RecordingAvailability(True, "ok", "fake", "/usr/bin/fake")

    def start(self, request: RecordingRequest) -> RecordingSession:
        self.started.append(request)
        temporary = request.output_path.with_name(".partial.mp4")
        return RecordingSession(
            panel_id=request.panel_id,
            request=request,
            process=None,  # type: ignore[arg-type]
            temporary_path=temporary,
            backend="fake",
            started_at="2026-07-25T03:04:05+00:00",
        )

    def stop(self, session: RecordingSession) -> None:
        session.request.output_path.parent.mkdir(parents=True, exist_ok=True)
        session.request.output_path.write_bytes(b"MP4")
        self.stopped.append(session.panel_id)

    def pause(self, session: RecordingSession) -> None:
        session.paused = True

    def resume(self, session: RecordingSession) -> None:
        session.paused = False


def test_recording_engine_tracks_session_and_history(tmp_path: Path) -> None:
    backend = FakeRecordingBackend()
    engine = RecordingEngine(backend, tmp_path, frame_rate=24)
    session = engine.start(
        "Meu Workspace",
        "Painel / 1",
        "ChatGPT",
        10,
        20,
        640,
        480,
        now=datetime(2026, 7, 25, 3, 4, 5, 6000, tzinfo=UTC),
    )

    assert engine.is_recording("Painel / 1")
    assert session.request.frame_rate == 24
    assert session.request.output_path.relative_to(tmp_path).parts[:3] == (
        "Meu-Workspace",
        "Painel-1",
        "2026-07-25",
    )

    engine.pause("Painel / 1")
    assert session.paused
    engine.resume("Painel / 1")
    assert not session.paused

    result = engine.stop("Painel / 1")
    assert Path(result.path).is_file()
    assert not engine.is_recording("Painel / 1")
    payload = json.loads(engine.history_path.read_text(encoding="utf-8").strip())
    assert payload["backend"] == "fake"
    assert payload["frame_rate"] == 24


def test_recording_engine_rejects_duplicate_panel(tmp_path: Path) -> None:
    engine = RecordingEngine(FakeRecordingBackend(), tmp_path)
    engine.start("w", "p", "Panel", 0, 0, 100, 100)
    with pytest.raises(RecordingEngineError, match="já está sendo gravado"):
        engine.start("w", "p", "Panel", 0, 0, 100, 100)


def test_recording_engine_stop_all(tmp_path: Path) -> None:
    backend = FakeRecordingBackend()
    engine = RecordingEngine(backend, tmp_path)
    engine.start("w", "p1", "One", 0, 0, 100, 100)
    engine.start("w", "p2", "Two", 100, 0, 100, 100)
    results = engine.stop_all()
    assert len(results) == 2
    assert set(backend.stopped) == {"p1", "p2"}


def test_ffmpeg_backend_requires_display(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    report = X11FfmpegRecordingBackend().availability()
    assert not report.available
    assert "DISPLAY" in report.reason


def test_ffmpeg_backend_requires_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setattr("triview_workspace.engines.recording.shutil.which", lambda name: None)
    report = X11FfmpegRecordingBackend().availability()
    assert not report.available
    assert "FFmpeg" in report.reason
