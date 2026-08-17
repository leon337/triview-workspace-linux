"""Read-only projections from canonical MCF project state and runtime endpoints.

This module deliberately does not persist MCF authority, credentials or runtime
state. Canonical ``.mcf`` artifacts and the MCF runtime remain the source of truth.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import quote, urlparse

ArtifactStatus = Literal["ABSENT", "VALID", "INVALID"]


@dataclass(frozen=True, slots=True)
class McfArtifactProjection:
    """Small derived view of one canonical MCF artifact family."""

    status: ArtifactStatus
    artifact_type: str
    path: str | None = None
    project_id: str | None = None
    revision_id: str | None = None
    schema_version: str | None = None
    created_at: str | None = None
    methodology_version: str | None = None
    methodology_ref: str | None = None
    decision: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class McfRepositorySnapshot:
    """Read-only repository projection; never a replacement for MCF authority."""

    root: Path
    is_mcf_project: bool
    project_id: str | None
    methodology_version: str | None
    pip: McfArtifactProjection
    prr: McfArtifactProjection
    alignment: McfArtifactProjection
    source: str = "REPOSITORY_CANONICAL"
    consistency_errors: tuple[str, ...] = ()


class McfRepositoryInspector:
    """Inspect canonical MCF project artifacts without writing to the repository."""

    def inspect(self, root: str | Path) -> McfRepositorySnapshot:
        project_root = Path(root).expanduser().resolve()
        mcf_root = project_root / ".mcf"
        is_mcf_project = mcf_root.is_dir()

        pip = self._artifact_projection(
            mcf_root / "intent",
            "pip-*.json",
            artifact_type="PROJECT_INTENT_PACKAGE",
            identity_field="revisionId",
            timestamp_field="createdAt",
            methodology_required=True,
        )
        prr = self._artifact_projection(
            mcf_root / "reality",
            "prr-*.json",
            artifact_type="PROJECT_REALITY_REPORT",
            identity_field="revisionId",
            timestamp_field="createdAt",
            methodology_required=True,
        )
        alignment = self._artifact_projection(
            mcf_root / "receipts",
            "intent-alignment-*.json",
            artifact_type="INTENT_ALIGNMENT_RECEIPT",
            identity_field="receiptId",
            timestamp_field="confirmedAt",
            methodology_required=False,
        )

        valid_project_ids = {
            projection.project_id
            for projection in (pip, prr, alignment)
            if projection.status == "VALID" and projection.project_id is not None
        }
        consistency_errors: list[str] = []
        if len(valid_project_ids) > 1:
            consistency_errors.append("CANONICAL_PROJECT_ID_MISMATCH")
            project_id = None
        else:
            project_id = next(iter(valid_project_ids), None)

        methodology_versions = {
            projection.methodology_version
            for projection in (pip, prr)
            if projection.status == "VALID" and projection.methodology_version is not None
        }
        if len(methodology_versions) > 1:
            consistency_errors.append("METHODOLOGY_VERSION_MISMATCH")
            methodology_version = None
        else:
            methodology_version = next(iter(methodology_versions), None)

        return McfRepositorySnapshot(
            root=project_root,
            is_mcf_project=is_mcf_project,
            project_id=project_id,
            methodology_version=methodology_version,
            pip=pip,
            prr=prr,
            alignment=alignment,
            consistency_errors=tuple(consistency_errors),
        )

    def _artifact_projection(
        self,
        directory: Path,
        pattern: str,
        *,
        artifact_type: str,
        identity_field: str,
        timestamp_field: str,
        methodology_required: bool,
    ) -> McfArtifactProjection:
        candidates = sorted(directory.glob(pattern)) if directory.is_dir() else []
        if not candidates:
            return McfArtifactProjection(status="ABSENT", artifact_type=artifact_type)

        valid: list[tuple[tuple[float, str], McfArtifactProjection]] = []
        invalid: list[McfArtifactProjection] = []
        for path in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                projection = self._validate_projection(
                    path,
                    payload,
                    artifact_type=artifact_type,
                    identity_field=identity_field,
                    timestamp_field=timestamp_field,
                    methodology_required=methodology_required,
                )
            except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
                invalid.append(
                    McfArtifactProjection(
                        status="INVALID",
                        artifact_type=artifact_type,
                        path=str(path),
                        error=str(exc),
                    )
                )
                continue
            valid.append((self._selection_key(projection.created_at, path.name), projection))

        if valid:
            return max(valid, key=lambda item: item[0])[1]
        return invalid[-1]

    @staticmethod
    def _validate_projection(
        path: Path,
        payload: object,
        *,
        artifact_type: str,
        identity_field: str,
        timestamp_field: str,
        methodology_required: bool,
    ) -> McfArtifactProjection:
        if not isinstance(payload, Mapping):
            raise ValueError("canonical MCF artifact root must be an object")
        if payload.get("artifactType") != artifact_type:
            raise ValueError(f"unexpected artifactType for {path.name}")
        schema_version = str(payload.get("schemaVersion", "")).strip()
        if schema_version != "1.0":
            raise ValueError(f"unsupported schemaVersion for {path.name}")
        project_id = str(payload.get("projectId", "")).strip()
        if not project_id:
            raise ValueError(f"projectId missing from {path.name}")
        revision_id = str(payload.get(identity_field, "")).strip()
        if not revision_id:
            raise ValueError(f"{identity_field} missing from {path.name}")
        created_at = str(payload.get(timestamp_field, "")).strip() or None

        methodology_version: str | None = None
        methodology_ref: str | None = None
        if methodology_required:
            methodology = payload.get("methodologyPin")
            if not isinstance(methodology, Mapping):
                raise ValueError(f"methodologyPin missing from {path.name}")
            methodology_version = str(methodology.get("version", "")).strip()
            methodology_ref = str(methodology.get("immutableRef", "")).strip()
            if not methodology_version or not methodology_ref:
                raise ValueError(f"methodologyPin incomplete in {path.name}")

        decision: str | None = None
        if artifact_type == "INTENT_ALIGNMENT_RECEIPT":
            decision = str(payload.get("decision", "")).strip()
            if not decision:
                raise ValueError(f"decision missing from {path.name}")

        return McfArtifactProjection(
            status="VALID",
            artifact_type=artifact_type,
            path=str(path),
            project_id=project_id,
            revision_id=revision_id,
            schema_version=schema_version,
            created_at=created_at,
            methodology_version=methodology_version,
            methodology_ref=methodology_ref,
            decision=decision,
        )

    @staticmethod
    def _selection_key(value: str | None, filename: str) -> tuple[float, str]:
        if not value:
            return (float("-inf"), filename)
        normalized = value.replace("Z", "+00:00")
        try:
            return (datetime.fromisoformat(normalized).timestamp(), filename)
        except ValueError:
            return (float("-inf"), filename)


class _ReadableResponse(Protocol):
    def __enter__(self) -> _ReadableResponse: ...

    def __exit__(self, *args: object) -> object: ...

    def read(self) -> bytes: ...


RuntimeOpener = Callable[[urllib.request.Request, float], _ReadableResponse]


class McfRuntimeClient:
    """Minimal MCF runtime client that intentionally exposes GET operations only."""

    def __init__(
        self,
        base_url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 5.0,
        opener: RuntimeOpener | None = None,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("MCF runtime base URL must use HTTP or HTTPS")
        if timeout <= 0:
            raise ValueError("MCF runtime timeout must be greater than zero")
        self.base_url = base_url.rstrip("/")
        self.headers = dict(headers or {})
        self.timeout = timeout
        self._opener = opener or self._default_opener

    @staticmethod
    def _default_opener(request: urllib.request.Request, timeout: float) -> _ReadableResponse:
        return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310

    def mission(self, mission_id: str) -> dict[str, Any]:
        return self._get(f"/v1/mcf/missions/{self._mission_id(mission_id)}")

    def timeline(self, mission_id: str) -> dict[str, Any]:
        return self._get(f"/v1/mcf/missions/{self._mission_id(mission_id)}/timeline")

    def observability(self, mission_id: str) -> dict[str, Any]:
        return self._get(f"/v1/mcf/observability/missions/{self._mission_id(mission_id)}")

    def _get(self, path: str) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers=self.headers,
            method="GET",
        )
        with self._opener(request, self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("MCF runtime response must be a JSON object")
        return payload

    @staticmethod
    def _mission_id(mission_id: str) -> str:
        cleaned = mission_id.strip()
        if not cleaned:
            raise ValueError("mission_id cannot be empty")
        return quote(cleaned, safe="")


class McfRuntimeReader(Protocol):
    def mission(self, mission_id: str) -> dict[str, Any]: ...

    def timeline(self, mission_id: str) -> dict[str, Any]: ...

    def observability(self, mission_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class McfRuntimeProjection:
    mission: dict[str, Any]
    timeline: dict[str, Any]
    observability: dict[str, Any]
    source: str = "MCF_RUNTIME_READ_ONLY"


@dataclass(frozen=True, slots=True)
class McfBridgeSnapshot:
    project: McfRepositorySnapshot
    runtime: McfRuntimeProjection | None


class McfBridge:
    """Compose repository and runtime facts without creating new MCF authority."""

    def __init__(
        self,
        *,
        repository_inspector: McfRepositoryInspector | None = None,
        runtime_client: McfRuntimeReader | None = None,
    ) -> None:
        self.repository_inspector = repository_inspector or McfRepositoryInspector()
        self.runtime_client = runtime_client

    def inspect(self, root: str | Path, *, mission_id: str | None = None) -> McfBridgeSnapshot:
        project = self.repository_inspector.inspect(root)
        runtime: McfRuntimeProjection | None = None
        if mission_id is not None:
            if self.runtime_client is None:
                raise ValueError("mission_id requires a configured read-only MCF runtime client")
            runtime = McfRuntimeProjection(
                mission=self.runtime_client.mission(mission_id),
                timeline=self.runtime_client.timeline(mission_id),
                observability=self.runtime_client.observability(mission_id),
            )
        return McfBridgeSnapshot(project=project, runtime=runtime)
