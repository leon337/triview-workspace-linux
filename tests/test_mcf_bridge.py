from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from triview_workspace.mcf_bridge import (
    McfBridge,
    McfMissionControlSnapshotReader,
    McfRepositoryInspector,
    McfRuntimeClient,
)
from triview_workspace.mcf_capability_registry import (
    McfCapabilityRegistryRepositoryReader,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_project_artifacts(root: Path) -> None:
    _write_json(
        root / ".mcf" / "intent" / "pip-r1.json",
        {
            "artifactType": "PROJECT_INTENT_PACKAGE",
            "schemaVersion": "1.0",
            "projectId": "triview",
            "revisionId": "r1",
            "createdAt": "2026-08-16T10:00:00+00:00",
            "methodologyPin": {
                "version": "v1.1.0",
                "immutableRef": "5d79f488407c77f7b9f21ecfefb41ddfb3a52aef",
            },
        },
    )
    _write_json(
        root / ".mcf" / "reality" / "prr-r1.json",
        {
            "artifactType": "PROJECT_REALITY_REPORT",
            "schemaVersion": "1.0",
            "projectId": "triview",
            "revisionId": "r1",
            "createdAt": "2026-08-16T10:05:00+00:00",
            "methodologyPin": {
                "version": "v1.1.0",
                "immutableRef": "5d79f488407c77f7b9f21ecfefb41ddfb3a52aef",
            },
        },
    )
    _write_json(
        root / ".mcf" / "receipts" / "intent-alignment-a1.json",
        {
            "artifactType": "INTENT_ALIGNMENT_RECEIPT",
            "schemaVersion": "1.0",
            "receiptId": "a1",
            "projectId": "triview",
            "decision": "PASS",
            "confirmedAt": "2026-08-16T10:10:00+00:00",
        },
    )


def test_inspector_reads_latest_canonical_project_artifacts(tmp_path: Path) -> None:
    _write_project_artifacts(tmp_path)
    _write_json(
        tmp_path / ".mcf" / "intent" / "pip-r0.json",
        {
            "artifactType": "PROJECT_INTENT_PACKAGE",
            "schemaVersion": "1.0",
            "projectId": "triview",
            "revisionId": "r0",
            "createdAt": "2026-08-15T10:00:00+00:00",
            "methodologyPin": {"version": "v1.0.0", "immutableRef": "older"},
        },
    )

    snapshot = McfRepositoryInspector().inspect(tmp_path)

    assert snapshot.is_mcf_project is True
    assert snapshot.project_id == "triview"
    assert snapshot.methodology_version == "v1.1.0"
    assert snapshot.pip.status == "VALID"
    assert snapshot.pip.revision_id == "r1"
    assert snapshot.prr.status == "VALID"
    assert snapshot.prr.revision_id == "r1"
    assert snapshot.alignment.status == "VALID"
    assert snapshot.alignment.decision == "PASS"


def test_inspector_marks_malformed_canonical_artifact_invalid(tmp_path: Path) -> None:
    intent = tmp_path / ".mcf" / "intent"
    intent.mkdir(parents=True)
    (intent / "pip-bad.json").write_text("{", encoding="utf-8")

    snapshot = McfRepositoryInspector().inspect(tmp_path)

    assert snapshot.is_mcf_project is True
    assert snapshot.pip.status == "INVALID"
    assert snapshot.pip.error is not None
    assert snapshot.project_id is None


def test_inspector_reports_plain_directory_as_not_mcf(tmp_path: Path) -> None:
    snapshot = McfRepositoryInspector().inspect(tmp_path)

    assert snapshot.is_mcf_project is False
    assert snapshot.project_id is None
    assert snapshot.methodology_version is None
    assert snapshot.pip.status == "ABSENT"
    assert snapshot.prr.status == "ABSENT"
    assert snapshot.alignment.status == "ABSENT"


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self._body if amount < 0 else self._body[:amount]


def _context_receipt(project_id: str = "triview") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt_id": "context-recovery-001",
        "project_id": project_id,
        "recovery_state": "RECOVERED",
        "recovered_at": "2026-08-23T06:09:19Z",
        "read_only": True,
        "material_action": False,
        "sources": [
            {
                "role": "REGISTRY",
                "source_ref": "context/projects/triview.yaml",
                "source_revision": "registry-sha",
            },
            {
                "role": "CAPSULE",
                "source_ref": ".mcf/project-capsule.yaml",
                "source_revision": "capsule-sha",
                "observed_at": "2026-08-23T03:09:19-03:00",
            },
        ],
        "claims": [
            {
                "claim_key": "project.id",
                "type": "IDENTITY",
                "value": project_id,
                "owner": "MCF_PROJECT_REGISTRY",
                "source_ref": "context/projects/triview.yaml",
                "freshness": "DURABLE",
                "provenance": [
                    {
                        "source_ref": "context/projects/triview.yaml",
                        "source_revision": "registry-sha",
                    }
                ],
                "requires_live_verification": False,
            }
        ],
        "warnings": [],
        "evidence_only": True,
    }


def _capability_entry() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "capability": {
            "id": "mcf.context.recovery.read",
            "provider_project_id": "multiagent-collaboration-framework",
            "consumer_project_ids": ["triview"],
            "mode": "READ_ONLY",
        },
        "contract": {
            "protocol": "MCF_CONTEXT_RECOVERY_HTTP_V1",
            "allowed_operations": ["context.recover"],
            "prohibited_operations": ["mission.execute"],
        },
        "scope": {"environments": ["lab"], "resources": ["context/projects/*.yaml"]},
        "governance": {
            "authorization_state": "AUTHORIZED",
            "required_gate": "DEDICATED_CONTEXT_READ_TOKEN",
            "expiration": None,
        },
        "lifecycle": {
            "implementation_state": "IMPLEMENTED",
            "connection_state": "CONNECTED",
            "runtime_state": "ACTIVE",
            "verification_state": "VERIFIED",
            "last_verified_at": "2026-08-23T06:30:22Z",
        },
        "evidence": [{"source_ref": "controller.ts", "source_revision": "d5bbcfd"}],
        "freshness": "LIVE_REQUIRED",
    }


def _capability_snapshot(project_id: str = "triview") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "retrieved_at": "2026-08-23T06:50:00Z",
        "project_id": project_id,
        "read_only": True,
        "evidence_only": True,
        "entries": [_capability_entry()],
        "sources": [
            {
                "source_ref": "context/capabilities/mcf-context-recovery-read.yaml",
                "source_revision": "d6bdcff",
            }
        ],
    }


def test_runtime_client_uses_get_only_and_transient_headers() -> None:
    captured: list[tuple[object, float]] = []

    def opener(request: object, timeout: float) -> _FakeResponse:
        captured.append((request, timeout))
        return _FakeResponse({"missionId": "mission-1", "state": "PLANEJADO"})

    client = McfRuntimeClient(
        "https://mcf.example.test/",
        headers={"Cookie": "session=ephemeral"},
        timeout=3.5,
        opener=opener,
    )

    payload = client.mission("mission 1")

    assert payload["missionId"] == "mission-1"
    assert len(captured) == 1
    request, timeout = captured[0]
    assert request.get_method() == "GET"  # type: ignore[attr-defined]
    assert request.full_url == "https://mcf.example.test/v1/mcf/missions/mission%201"  # type: ignore[attr-defined]
    assert request.get_header("Cookie") == "session=ephemeral"  # type: ignore[attr-defined]
    assert timeout == 3.5


def test_runtime_client_rejects_non_http_base_url() -> None:
    with pytest.raises(ValueError, match="HTTP"):
        McfRuntimeClient("file:///tmp/mcf")


def test_runtime_client_requests_context_recovery_by_get_only() -> None:
    captured: list[object] = []

    def opener(request: object, _timeout: float) -> _FakeResponse:
        captured.append(request)
        return _FakeResponse(_context_receipt("triview workspace"))

    client = McfRuntimeClient("https://mcf.example.test", opener=opener)

    payload = client.context_recovery("triview workspace")

    assert payload["evidence_only"] is True
    request = captured[0]
    assert request.get_method() == "GET"  # type: ignore[attr-defined]
    assert request.full_url == (  # type: ignore[attr-defined]
        "https://mcf.example.test/v1/mcf/context/recovery?"
        "project_hint=triview+workspace&requires_current_operational_state=false"
    )


def test_runtime_client_bounds_context_response_before_json_parsing() -> None:
    client = McfRuntimeClient(
        "https://mcf.example.test",
        max_response_bytes=32,
        opener=lambda _request, _timeout: _FakeResponse({"payload": "x" * 64}),
    )

    with pytest.raises(ValueError, match="size limit"):
        client.context_recovery("triview")


def test_runtime_client_requests_capability_registry_by_get_only() -> None:
    captured: list[object] = []

    def opener(request: object, _timeout: float) -> _FakeResponse:
        captured.append(request)
        return _FakeResponse(_capability_snapshot())

    client = McfRuntimeClient(
        "https://mcf.example.test/",
        headers={"x-mcf-context-token": "ephemeral-read-token"},
        opener=opener,
    )

    payload = client.capability_registry("triview")

    assert payload["evidence_only"] is True
    request = captured[0]
    assert request.get_method() == "GET"  # type: ignore[attr-defined]
    assert request.full_url == (  # type: ignore[attr-defined]
        "https://mcf.example.test/v1/mcf/context/capabilities?project_id=triview"
    )
    assert (
        request.get_header(  # type: ignore[attr-defined]
            "X-mcf-context-token"
        )
        == "ephemeral-read-token"
    )


def test_runtime_client_rejects_invalid_capability_project_id() -> None:
    client = McfRuntimeClient("https://mcf.example.test")

    with pytest.raises(ValueError, match="stable lowercase"):
        client.capability_registry("TriView")


def test_runtime_client_reads_latest_mission_control_snapshot_by_get_only() -> None:
    captured: list[object] = []
    payload = {
        "mission": {"id": "mission-1"},
        "timeline": {"events": []},
        "observability": {"blocked": False},
    }

    def opener(request: object, _timeout: float) -> _FakeResponse:
        captured.append(request)
        return _FakeResponse(payload)

    client = McfRuntimeClient(
        "https://mcf.example.test/",
        headers={"Authorization": "Bearer transient-mission-control-token"},
        opener=opener,
    )

    assert client.mission_control_latest("Leon337/MCF") == payload
    request = captured[0]
    assert request.get_method() == "GET"  # type: ignore[attr-defined]
    assert request.full_url == (  # type: ignore[attr-defined]
        "https://mcf.example.test/v1/mcf/mission-control/latest?repository=leon337%2Fmcf"
    )
    assert request.get_header("Authorization") == (  # type: ignore[attr-defined]
        "Bearer transient-mission-control-token"
    )


def test_mission_control_snapshot_reader_reuses_one_consistent_snapshot() -> None:
    payload = {
        "mission": {"id": "mission-1", "state": "EXECUTING"},
        "timeline": {"events": [{"eventType": "MISSION_CREATED"}]},
        "observability": {"blocked": False},
    }
    reader = McfMissionControlSnapshotReader(payload)

    assert reader.mission_id == "mission-1"
    assert reader.mission("mission-1")["state"] == "EXECUTING"
    assert reader.timeline("mission-1")["events"]
    assert reader.observability("mission-1")["blocked"] is False
    with pytest.raises(ValueError, match="does not match"):
        reader.mission("another-mission")


def test_bridge_combines_repository_and_runtime_read_only(tmp_path: Path) -> None:
    _write_project_artifacts(tmp_path)

    class FakeRuntime:
        def mission(self, mission_id: str) -> dict[str, Any]:
            assert mission_id == "mission-1"
            return {"missionId": mission_id, "state": "EXECUTANDO", "phase": "R2"}

        def timeline(self, mission_id: str) -> dict[str, Any]:
            return {"missionId": mission_id, "events": [{"type": "PHASE_STARTED"}]}

        def observability(self, mission_id: str) -> dict[str, Any]:
            return {"missionId": mission_id, "blocked": False}

    snapshot = McfBridge(runtime_client=FakeRuntime()).inspect(tmp_path, mission_id="mission-1")

    assert snapshot.project.project_id == "triview"
    assert snapshot.project.methodology_version == "v1.1.0"
    assert snapshot.project.source == "REPOSITORY_CANONICAL"
    assert snapshot.runtime is not None
    assert snapshot.runtime.source == "MCF_RUNTIME_READ_ONLY"
    assert snapshot.runtime.mission["state"] == "EXECUTANDO"
    assert snapshot.runtime.timeline["events"][0]["type"] == "PHASE_STARTED"
    assert snapshot.runtime.observability["blocked"] is False


def test_bridge_without_runtime_keeps_runtime_projection_absent(tmp_path: Path) -> None:
    _write_project_artifacts(tmp_path)

    snapshot = McfBridge().inspect(tmp_path)

    assert snapshot.project.project_id == "triview"
    assert snapshot.runtime is None


def test_bridge_parses_context_receipt_without_creating_runtime_authority(tmp_path: Path) -> None:
    _write_project_artifacts(tmp_path)

    class FakeContext:
        def context_recovery(
            self,
            project_hint: str,
            *,
            requires_current_operational_state: bool = False,
        ) -> dict[str, Any]:
            assert project_hint == "triview"
            assert requires_current_operational_state is False
            return _context_receipt()

    snapshot = McfBridge(context_client=FakeContext()).inspect(
        tmp_path,
        recover_context=True,
    )

    assert snapshot.runtime is None
    assert snapshot.context_mode == "MCF_RUNTIME_GET"
    assert snapshot.context_error is None
    assert snapshot.context_receipt is not None
    assert snapshot.context_receipt.recovery_state == "RECOVERED"
    assert snapshot.context_receipt.evidence_only is True


def test_bridge_labels_context_runtime_failure_as_repository_fallback(tmp_path: Path) -> None:
    _write_project_artifacts(tmp_path)

    class FailingContext:
        def context_recovery(
            self,
            _project_hint: str,
            *,
            requires_current_operational_state: bool = False,
        ) -> dict[str, Any]:
            assert requires_current_operational_state is False
            raise TimeoutError("synthetic timeout")

    snapshot = McfBridge(context_client=FailingContext()).inspect(
        tmp_path,
        recover_context=True,
    )

    assert snapshot.project.project_id == "triview"
    assert snapshot.context_receipt is None
    assert snapshot.context_mode == "REPOSITORY_FALLBACK"
    assert snapshot.context_error == ("CONTEXT_RUNTIME_READ_FAILED:TimeoutError:synthetic timeout")


def test_bridge_prefers_strict_remote_capabilities_over_repository_fallback(
    tmp_path: Path,
) -> None:
    _write_project_artifacts(tmp_path)

    class FakeCapabilities:
        def capability_registry(self, project_id: str | None = None) -> dict[str, Any]:
            assert project_id == "triview"
            return _capability_snapshot()

    snapshot = McfBridge(capability_client=FakeCapabilities()).inspect(
        tmp_path,
        list_capabilities=True,
    )

    assert snapshot.runtime is None
    assert snapshot.capability_mode == "MCF_RUNTIME_GET"
    assert snapshot.capability_error is None
    assert snapshot.capability_registry is not None
    assert snapshot.capability_registry.source == "MCF_CAPABILITY_REGISTRY_GET_READ_ONLY"
    assert snapshot.capability_registry.entries[0].runtime_state == "ACTIVE"


def test_bridge_keeps_repository_capabilities_on_remote_failure(tmp_path: Path) -> None:
    _write_project_artifacts(tmp_path)
    registry_root = tmp_path / "registry"
    capability_path = registry_root / "context/capabilities/recovery.yaml"
    capability_path.parent.mkdir(parents=True)
    capability_path.write_text(json.dumps(_capability_entry()), encoding="utf-8")

    class FailingCapabilities:
        def capability_registry(self, project_id: str | None = None) -> dict[str, Any]:
            assert project_id == "triview"
            raise TimeoutError("synthetic timeout")

    snapshot = McfBridge(
        capability_repository_reader=McfCapabilityRegistryRepositoryReader(
            registry_root=registry_root
        ),
        capability_client=FailingCapabilities(),
    ).inspect(tmp_path, list_capabilities=True)

    assert snapshot.capability_mode == "REPOSITORY_FALLBACK"
    assert snapshot.capability_error == (
        "CAPABILITY_RUNTIME_READ_FAILED:TimeoutError:synthetic timeout"
    )
    assert snapshot.capability_registry is not None
    assert snapshot.capability_registry.status == "VALID"
    assert snapshot.capability_registry.source == ("MCF_CAPABILITY_REGISTRY_REPOSITORY_READ_ONLY")
    assert [entry.capability_id for entry in snapshot.capability_registry.entries] == [
        "mcf.context.recovery.read"
    ]


def test_bridge_rejects_capability_snapshot_for_another_project(tmp_path: Path) -> None:
    _write_project_artifacts(tmp_path)

    class WrongProjectCapabilities:
        def capability_registry(self, project_id: str | None = None) -> dict[str, Any]:
            assert project_id == "triview"
            return _capability_snapshot("multiagent-collaboration-framework")

    snapshot = McfBridge(capability_client=WrongProjectCapabilities()).inspect(
        tmp_path,
        list_capabilities=True,
    )

    assert snapshot.capability_mode == "REPOSITORY_FALLBACK"
    assert snapshot.capability_registry is not None
    assert snapshot.capability_registry.status == "ABSENT"
    assert snapshot.capability_error == (
        "CAPABILITY_RUNTIME_READ_FAILED:ValueError:"
        "Capability snapshot project_id differs from repository identity"
    )
