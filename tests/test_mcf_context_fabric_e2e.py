from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from triview_workspace.mcf_binding import McfBindingRepository, McfWorkspaceBinder
from triview_workspace.mcf_bridge import McfRepositoryInspector
from triview_workspace.mcf_cockpit import McfCockpitContext, load_cockpit_model
from triview_workspace.mcf_context_fabric import McfContextFabricRepositoryReader


def _capsule() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project_id": "triview-workspace-linux",
        "purpose": "Workspace for governed agent surfaces",
        "lifecycle": "ACTIVE",
        "snapshot": {
            "current_workstream": "context-fabric-lab-integration",
            "current_status": "LAB_VALIDATION",
            "next_action": "Run the synthetic read-only E2E",
            "blockers": ["Physical X11 acceptance remains pending"],
        },
        "sources": {"current_state": "docs/architecture/context.md"},
        "observed_at": "2026-08-23T03:09:19-03:00",
    }


def _registry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project": {"id": "triview-workspace-linux", "lifecycle": "REGISTERED"},
        "identity": {
            "canonical_repository": "leon337/triview-workspace-linux",
            "aliases": ["TriView"],
        },
        "ownership": {"project_owner": "LEANDRO"},
        "context": {
            "capsule_path": ".mcf/project-capsule.yaml",
            "canonical_entrypoints": ["README.md"],
        },
        "freshness": {
            "operational_state": "LIVE_REQUIRED",
            "project_identity": "DURABLE",
        },
    }


def _receipt() -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_id": "context-recovery-e2e",
        "project_id": "triview-workspace-linux",
        "recovery_state": "PARTIAL_RECOVERY",
        "recovered_at": "2026-08-23T06:09:19Z",
        "read_only": True,
        "material_action": False,
        "sources": [
            {
                "role": "REGISTRY",
                "source_ref": "context/projects/triview-workspace-linux.yaml",
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
                "claim_key": "snapshot.current_status",
                "type": "OPERATIONAL",
                "value": "LAB_VALIDATION",
                "owner": "TRIVIEW_PROJECT_REPOSITORY",
                "source_ref": ".mcf/project-capsule.yaml",
                "freshness": "LIVE_REQUIRED",
                "provenance": [
                    {
                        "source_ref": ".mcf/project-capsule.yaml",
                        "source_revision": "capsule-sha",
                        "observed_at": "2026-08-23T03:09:19-03:00",
                    }
                ],
                "requires_live_verification": True,
            }
        ],
        "warnings": ["LIVE_VERIFICATION_UNAVAILABLE:READ_ONLY_CONTEXT_ONLY"],
        "evidence_only": True,
    }


def _capability_entry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "capability": {
            "id": "cloud.workspace.g2a.read",
            "provider_project_id": "cloud-infrastructure",
            "consumer_project_ids": ["triview-workspace-linux"],
            "mode": "READ_ONLY",
        },
        "contract": {
            "protocol": "MCF_WORKSPACE_CONTROL_V1",
            "allowed_operations": ["workspace.read"],
            "prohibited_operations": ["workspace.write"],
        },
        "scope": {"environments": ["dev"], "resources": ["workspace/dev"]},
        "governance": {
            "authorization_state": "NOT_AUTHORIZED",
            "required_gate": "DEDICATED_FORCED_COMMAND_SSH_READ_TRANSPORT",
            "expiration": None,
        },
        "lifecycle": {
            "implementation_state": "IMPLEMENTED",
            "connection_state": "DISCONNECTED",
            "runtime_state": "UNKNOWN",
            "verification_state": "HISTORICALLY_VERIFIED",
            "last_verified_at": "2026-08-22T15:35:21+02:00",
        },
        "evidence": [
            {
                "source_ref": "repo://leon337/cloud-infrastructure/state/control.yaml",
                "source_revision": "g2a-revision",
                "observed_at": "2026-08-22T15:35:21+02:00",
            }
        ],
        "freshness": "LIVE_REQUIRED",
    }


def _capability_snapshot() -> dict[str, object]:
    return {
        "schema_version": 1,
        "retrieved_at": "2026-08-23T06:50:00Z",
        "project_id": "triview-workspace-linux",
        "read_only": True,
        "evidence_only": True,
        "entries": [_capability_entry()],
        "sources": [
            {
                "source_ref": "context/capabilities/cloud-workspace-g2a-read.yaml",
                "source_revision": "capability-registry-revision",
            }
        ],
    }


def _write_context_sources(
    project_root: Path,
    registry_root: Path,
) -> tuple[Path, Path, Path]:
    capsule_path = project_root / ".mcf/project-capsule.yaml"
    registry_path = registry_root / "context/projects/triview-workspace-linux.yaml"
    capability_path = registry_root / "context/capabilities/cloud-workspace-g2a-read.yaml"
    capsule_path.parent.mkdir(parents=True)
    registry_path.parent.mkdir(parents=True)
    capability_path.parent.mkdir(parents=True)
    capsule_path.write_text(json.dumps(_capsule()), encoding="utf-8")
    registry_path.write_text(json.dumps(_registry()), encoding="utf-8")
    capability_path.write_text(json.dumps(_capability_entry()), encoding="utf-8")
    return capsule_path, registry_path, capability_path


class _ContextHandler(BaseHTTPRequestHandler):
    status = 200
    requests: list[tuple[str, str, str | None, str | None]] = []

    def do_GET(self) -> None:  # noqa: N802
        type(self).requests.append(
            (
                "GET",
                self.path,
                self.headers.get("x-mcf-context-token"),
                self.headers.get("Authorization"),
            )
        )
        path = urlparse(self.path).path
        payload = (
            _capability_snapshot()
            if path == "/v1/mcf/context/capabilities"
            else _receipt()
        )
        body = json.dumps(payload).encode("utf-8")
        self.send_response(type(self).status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _serve(status: int = 200) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    handler = type(
        "SyntheticContextHandler",
        (_ContextHandler,),
        {"status": status, "requests": []},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, thread, f"http://{host}:{port}"


def test_cockpit_consumes_context_receipt_end_to_end_without_repository_writes(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "triview"
    registry_root = tmp_path / "mcf"
    capsule_path, registry_path, capability_path = _write_context_sources(
        project_root, registry_root
    )
    before = (
        capsule_path.read_bytes(),
        registry_path.read_bytes(),
        capability_path.read_bytes(),
    )
    server, thread, runtime_url = _serve()
    try:
        context = McfCockpitContext(
            project_root=project_root,
            registry_root=registry_root,
            runtime_url=runtime_url,
            _context_read_token="ephemeral-e2e-token",
        )

        model = load_cockpit_model(context)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert model.context_fabric["status"] == "VALID"
    assert model.context_fabric["project_id"] == "triview-workspace-linux"
    assert model.context_fabric["operational_freshness"] == "LIVE_REQUIRED"
    assert model.context_receipt == {
        "mode": "MCF_RUNTIME_GET",
        "recovery_state": "PARTIAL_RECOVERY",
        "receipt_id": "context-recovery-e2e",
        "evidence_only": "SIM",
        "freshness": "LIVE_REQUIRED",
        "live_verification_required": "SIM",
        "sources": "2",
        "claims": "1",
        "warning": "LIVE_VERIFICATION_UNAVAILABLE:READ_ONLY_CONTEXT_ONLY",
    }
    assert model.capability_registry["mode"] == "MCF_RUNTIME_GET"
    assert model.capability_registry["status"] == "VALID"
    assert model.capability_registry["state_model"] == (
        "IMPLEMENTED ≠ CONNECTED ≠ AUTHORIZED ≠ VERIFIED"
    )
    assert "CONNECTED=DISCONNECTED" in model.capability_registry["capability_1"]
    assert "AUTHORIZED=NOT_AUTHORIZED" in model.capability_registry["capability_1"]
    assert "DEDICATED_FORCED_COMMAND_SSH_READ_TRANSPORT" in model.capability_registry[
        "required_gates"
    ]
    assert model.mission["status"] == "NÃO CONFIGURADA"
    assert "ephemeral-e2e-token" not in repr(context)
    assert "ephemeral-e2e-token" not in repr(model)
    assert (
        capsule_path.read_bytes(),
        registry_path.read_bytes(),
        capability_path.read_bytes(),
    ) == before

    handler = server.RequestHandlerClass
    assert len(handler.requests) == 2
    assert [urlparse(request[1]).path for request in handler.requests] == [
        "/v1/mcf/context/recovery",
        "/v1/mcf/context/capabilities",
    ]
    for method, _raw_path, context_token, authorization in handler.requests:
        assert method == "GET"
        assert context_token == "ephemeral-e2e-token"
        assert authorization is None
    recovery = urlparse(handler.requests[0][1])
    capabilities = urlparse(handler.requests[1][1])
    assert parse_qs(recovery.query) == {
        "project_hint": ["triview-workspace-linux"],
        "requires_current_operational_state": ["false"],
    }
    assert parse_qs(capabilities.query) == {
        "project_id": ["triview-workspace-linux"]
    }


def test_cockpit_falls_back_explicitly_when_context_endpoint_is_unavailable(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "triview"
    registry_root = tmp_path / "mcf"
    _write_context_sources(project_root, registry_root)
    server, thread, runtime_url = _serve(status=503)
    try:
        model = load_cockpit_model(
            McfCockpitContext(
                project_root=project_root,
                registry_root=registry_root,
                runtime_url=runtime_url,
                _context_read_token="ephemeral-fallback-token",
            )
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert model.context_fabric["status"] == "VALID"
    assert model.context_receipt["mode"] == "REPOSITORY_FALLBACK"
    assert model.context_receipt["recovery_state"] == "N/A"
    assert model.context_receipt["warning"].startswith("CONTEXT_RUNTIME_READ_FAILED:HTTPError")
    assert model.capability_registry["mode"] == "REPOSITORY_FALLBACK"
    assert model.capability_registry["status"] == "VALID"
    assert model.capability_registry["retrieved_at"] == "REPOSITORY_ONLY_NON_LIVE"
    assert model.capability_registry["finding"].startswith(
        "CAPABILITY_RUNTIME_READ_FAILED:HTTPError"
    )
    assert "ephemeral-fallback-token" not in repr(model)


def test_binding_persists_only_reference_after_registry_capsule_validation(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "triview"
    registry_root = tmp_path / "mcf"
    _write_context_sources(project_root, registry_root)
    binding_path = tmp_path / "state/mcf-bindings.json"
    binder = McfWorkspaceBinder(
        repository=McfBindingRepository(binding_path),
        inspector=McfRepositoryInspector(
            context_fabric_reader=McfContextFabricRepositoryReader(
                registry_root=registry_root
            )
        ),
    )

    binding = binder.bind(
        "workspace-a",
        project_root,
        runtime_url="http://127.0.0.1:8787",
    )

    assert binding.project_id == "triview-workspace-linux"
    persisted = json.loads(binding_path.read_text(encoding="utf-8"))
    serialized = json.dumps(persisted).casefold()
    assert persisted["bindings"][0]["project_id"] == "triview-workspace-linux"
    for forbidden in (
        "token",
        "authorization",
        "cookie",
        "receipt",
        "claim",
        "capability",
    ):
        assert forbidden not in serialized
