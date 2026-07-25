"""Panel-scoped X11 video recording with safe FFmpeg lifecycle management."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from triview_workspace.engines.panel_runtime import safe_panel_token


class RecordingEngineError(RuntimeError):
    """Base error raised by panel recording operations."""


@dataclass(frozen=True, slots=True)
class RecordingAvailability:
    available: bool
    reason: str
    backend: str | None = None
    command: str | None = None


@dataclass(frozen=True, slots=True)
class RecordingRequest:
    workspace_id: str
    panel_id: str
    panel_title: str
    x: int
    y: int
    width: int
    height: int
    output_path: Path
    frame_rate: int = 30


@dataclass(slots=True)
class RecordingSession:
    panel_id: str
    request: RecordingRequest
    process: subprocess.Popen[bytes]
    temporary_path: Path
    backend: str
    started_at: str
    paused: bool = False


@dataclass(frozen=True, slots=True)
class RecordingResult:
    workspace_id: str
    panel_id: str
    panel_title: str
    path: str
    started_at: str
    finished_at: str
    backend: str
    width: int
    height: int
    frame_rate: int


class RecordingBackend(Protocol):
    def availability(self) -> RecordingAvailability: ...

    def start(self, request: RecordingRequest) -> RecordingSession: ...

    def stop(self, session: RecordingSession) -> None: ...

    def pause(self, session: RecordingSession) -> None: ...

    def resume(self, session: RecordingSession) -> None: ...


class X11FfmpegRecordingBackend:
    """Record one rectangular X11 region with FFmpeg x11grab."""

    def availability(self) -> RecordingAvailability:
        if not os.environ.get("DISPLAY"):
            return RecordingAvailability(
                False,
                "A gravação exige uma sessão gráfica X11 com DISPLAY disponível.",
            )
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            return RecordingAvailability(
                False,
                "O FFmpeg não foi encontrado. Instale-o para gravar painéis.",
            )
        return RecordingAvailability(True, "FFmpeg x11grab disponível.", "ffmpeg-x11grab", ffmpeg)

    def start(self, request: RecordingRequest) -> RecordingSession:
        report = self.availability()
        if not report.available or not report.command or not report.backend:
            raise RecordingEngineError(report.reason)
        if request.width <= 0 or request.height <= 0:
            raise RecordingEngineError("As dimensões do painel são inválidas para gravação.")
        if not 1 <= request.frame_rate <= 60:
            raise RecordingEngineError("A taxa de quadros precisa ficar entre 1 e 60 FPS.")

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = request.output_path.with_name(
            f".{request.output_path.stem}.partial{request.output_path.suffix}"
        )
        temporary.unlink(missing_ok=True)
        display = os.environ["DISPLAY"]
        source = f"{display}+{request.x},{request.y}"
        command = [
            report.command,
            "-nostdin",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "x11grab",
            "-draw_mouse",
            "1",
            "-framerate",
            str(request.frame_rate),
            "-video_size",
            f"{request.width}x{request.height}",
            "-i",
            source,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(temporary),
        ]
        try:
            process = subprocess.Popen(  # noqa: S603
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            raise RecordingEngineError(f"Não foi possível iniciar o FFmpeg: {exc}.") from exc
        return RecordingSession(
            panel_id=request.panel_id,
            request=request,
            process=process,
            temporary_path=temporary,
            backend=report.backend,
            started_at=datetime.now().astimezone().isoformat(),
        )

    def stop(self, session: RecordingSession) -> None:
        process = session.process
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        stderr = b""
        if process.stderr is not None:
            stderr = process.stderr.read()
        if process.returncode not in (0, 255):
            session.temporary_path.unlink(missing_ok=True)
            detail = stderr.decode("utf-8", errors="replace").strip() or "erro desconhecido"
            raise RecordingEngineError(f"A gravação falhou: {detail}.")
        if not session.temporary_path.is_file() or session.temporary_path.stat().st_size == 0:
            session.temporary_path.unlink(missing_ok=True)
            raise RecordingEngineError("O FFmpeg não produziu um vídeo válido.")
        session.temporary_path.replace(session.request.output_path)

    def pause(self, session: RecordingSession) -> None:
        if session.process.poll() is not None:
            raise RecordingEngineError("A gravação já foi encerrada.")
        os.kill(session.process.pid, signal.SIGSTOP)
        session.paused = True

    def resume(self, session: RecordingSession) -> None:
        if session.process.poll() is not None:
            raise RecordingEngineError("A gravação já foi encerrada.")
        os.kill(session.process.pid, signal.SIGCONT)
        session.paused = False


class RecordingEngine:
    """Manage one recording per panel and keep an auditable JSONL history."""

    def __init__(
        self,
        backend: RecordingBackend | None = None,
        root: str | Path | None = None,
        frame_rate: int = 30,
    ) -> None:
        self.backend = backend or X11FfmpegRecordingBackend()
        configured = os.environ.get("TRIVIEW_RECORDING_DIR")
        self.root = Path(root or configured or (Path.home() / "Videos" / "TriView Workspace" / "Recordings"))
        self.frame_rate = frame_rate
        self._sessions: dict[str, RecordingSession] = {}
        self._lock = threading.RLock()
        self._history_lock = threading.Lock()

    def availability(self) -> RecordingAvailability:
        return self.backend.availability()

    def is_recording(self, panel_id: str) -> bool:
        with self._lock:
            return panel_id in self._sessions

    def session(self, panel_id: str) -> RecordingSession | None:
        with self._lock:
            return self._sessions.get(panel_id)

    def start(
        self,
        workspace_id: str,
        panel_id: str,
        panel_title: str,
        x: int,
        y: int,
        width: int,
        height: int,
        now: datetime | None = None,
    ) -> RecordingSession:
        with self._lock:
            if panel_id in self._sessions:
                raise RecordingEngineError("Este painel já está sendo gravado.")
        timestamp = (now or datetime.now().astimezone()).astimezone()
        output = (
            self.root
            / safe_panel_token(workspace_id)
            / safe_panel_token(panel_id)
            / timestamp.strftime("%Y-%m-%d")
            / (timestamp.strftime("%H%M%S-%f") + ".mp4")
        )
        request = RecordingRequest(
            workspace_id=workspace_id,
            panel_id=panel_id,
            panel_title=panel_title,
            x=int(x),
            y=int(y),
            width=int(width),
            height=int(height),
            output_path=output,
            frame_rate=self.frame_rate,
        )
        session = self.backend.start(request)
        with self._lock:
            self._sessions[panel_id] = session
        return session

    def stop(self, panel_id: str) -> RecordingResult:
        with self._lock:
            session = self._sessions.pop(panel_id, None)
        if session is None:
            raise RecordingEngineError("Este painel não possui uma gravação ativa.")
        try:
            if session.paused:
                self.backend.resume(session)
            self.backend.stop(session)
        except Exception:
            session.temporary_path.unlink(missing_ok=True)
            raise
        result = RecordingResult(
            workspace_id=session.request.workspace_id,
            panel_id=session.panel_id,
            panel_title=session.request.panel_title,
            path=str(session.request.output_path),
            started_at=session.started_at,
            finished_at=datetime.now().astimezone().isoformat(),
            backend=session.backend,
            width=session.request.width,
            height=session.request.height,
            frame_rate=session.request.frame_rate,
        )
        self._append_history(result)
        return result

    def pause(self, panel_id: str) -> None:
        session = self.session(panel_id)
        if session is None:
            raise RecordingEngineError("Este painel não possui uma gravação ativa.")
        self.backend.pause(session)

    def resume(self, panel_id: str) -> None:
        session = self.session(panel_id)
        if session is None:
            raise RecordingEngineError("Este painel não possui uma gravação ativa.")
        self.backend.resume(session)

    def stop_all(self) -> tuple[RecordingResult, ...]:
        with self._lock:
            panel_ids = tuple(self._sessions)
        results: list[RecordingResult] = []
        for panel_id in panel_ids:
            try:
                results.append(self.stop(panel_id))
            except Exception:
                # Best effort during workspace change or application shutdown.
                continue
        return tuple(results)

    @property
    def history_path(self) -> Path:
        return self.root / "recording-history.jsonl"

    def _append_history(self, result: RecordingResult) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(result), ensure_ascii=False, sort_keys=True)
        with self._history_lock:
            with self.history_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
