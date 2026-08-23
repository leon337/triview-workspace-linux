from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from triview_workspace.mcf_capability_registry import (
    McfCapabilityRegistryError,
    McfCapabilityRegistryRepositoryReader,
    McfCapabilityRegistrySnapshotParser,
)


def _entry(
    capability_id: str = "cloud.workspace.g2a.read",
    *,
    provider: str = "cloud-infrastructure",
    consumers: list[str] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "capability": {
            "id": capability_id,
            "provider_project_id": provider,
            "consumer_project_ids": consumers or ["triview-workspace-linux"],
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
            "required_gate": "DEDICATED_READ_TRANSPORT",
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
                "source_revision": "3e34044c",
                "observed_at": "2026-08-22T15:35:21+02:00",
            }
        ],
        "freshness": "LIVE_REQUIRED",
    }


def _snapshot(*entries: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "retrieved_at": "2026-08-23T06:50:00Z",
        "project_id": "triview-workspace-linux",
        "read_only": True,
        "evidence_only": True,
        "entries": list(entries or (_entry(),)),
        "sources": [
            {
                "source_ref": "context/capabilities/cloud-workspace-g2a-read.yaml",
                "source_revision": "registry-revision",
            }
        ],
    }


def _write_entry(root: Path, name: str, entry: dict[str, object]) -> Path:
    path = root / f"context/capabilities/{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entry), encoding="utf-8")
    return path


def test_snapshot_parser_keeps_lifecycle_dimensions_independent() -> None:
    projection = McfCapabilityRegistrySnapshotParser().parse(_snapshot(_entry()))

    assert projection.status == "VALID"
    assert projection.read_only is True
    assert projection.evidence_only is True
    assert projection.project_id == "triview-workspace-linux"
    assert projection.retrieved_at == "2026-08-23T06:50:00Z"
    assert len(projection.sources) == 1
    capability = projection.entries[0]
    assert capability.implementation_state == "IMPLEMENTED"
    assert capability.connection_state == "DISCONNECTED"
    assert capability.authorization_state == "NOT_AUTHORIZED"
    assert capability.verification_state == "HISTORICALLY_VERIFIED"
    assert capability.runtime_state == "UNKNOWN"
    assert capability.required_gate == "DEDICATED_READ_TRANSPORT"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("read_only", False, "CAPABILITY_SNAPSHOT_NOT_READ_ONLY"),
        ("evidence_only", False, "CAPABILITY_SNAPSHOT_NOT_EVIDENCE_ONLY"),
        ("retrieved_at", "2026-08-23 06:50:00Z", "CAPABILITY_SNAPSHOT_RETRIEVED_AT_INVALID"),
    ],
)
def test_snapshot_parser_rejects_non_evidence_or_invalid_contracts(
    field: str,
    value: object,
    code: str,
) -> None:
    snapshot = _snapshot()
    snapshot[field] = value

    with pytest.raises(McfCapabilityRegistryError, match=f"^{code}$"):
        McfCapabilityRegistrySnapshotParser().parse(snapshot)


def test_snapshot_parser_rejects_unknown_fields_duplicates_and_wrong_filter() -> None:
    unknown = _snapshot()
    unknown["action"] = "connect"
    with pytest.raises(
        McfCapabilityRegistryError, match="^CAPABILITY_SNAPSHOT_UNKNOWN_FIELDS$"
    ):
        McfCapabilityRegistrySnapshotParser().parse(unknown)

    duplicate = _snapshot(_entry(), copy.deepcopy(_entry()))
    with pytest.raises(McfCapabilityRegistryError, match="^CAPABILITY_ID_DUPLICATED$"):
        McfCapabilityRegistrySnapshotParser().parse(duplicate)

    unrelated = _snapshot(
        _entry(
            "cloud.workspace.internal",
            consumers=["multiagent-collaboration-framework"],
        )
    )
    with pytest.raises(
        McfCapabilityRegistryError,
        match="^CAPABILITY_SNAPSHOT_PROJECT_FILTER_INVALID$",
    ):
        McfCapabilityRegistrySnapshotParser().parse(unrelated)


def test_snapshot_parser_enforces_lifecycle_gate_and_operation_invariants() -> None:
    active_without_authorization = _entry()
    lifecycle = active_without_authorization["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle.update(
        {
            "connection_state": "CONNECTED",
            "runtime_state": "ACTIVE",
            "verification_state": "VERIFIED",
        }
    )
    with pytest.raises(McfCapabilityRegistryError, match="^CAPABILITY_ACTIVE_STATE_INVALID$"):
        McfCapabilityRegistrySnapshotParser().parse(_snapshot(active_without_authorization))

    write_without_gate = _entry()
    capability = write_without_gate["capability"]
    governance = write_without_gate["governance"]
    assert isinstance(capability, dict) and isinstance(governance, dict)
    capability["mode"] = "BOUNDED_WRITE"
    governance["required_gate"] = None
    with pytest.raises(McfCapabilityRegistryError, match="^CAPABILITY_WRITE_GATE_REQUIRED$"):
        McfCapabilityRegistrySnapshotParser().parse(_snapshot(write_without_gate))

    conflicting = _entry()
    contract = conflicting["contract"]
    assert isinstance(contract, dict)
    contract["prohibited_operations"] = ["workspace.read"]
    with pytest.raises(McfCapabilityRegistryError, match="^CAPABILITY_OPERATION_CONFLICT$"):
        McfCapabilityRegistrySnapshotParser().parse(_snapshot(conflicting))


def test_repository_reader_filters_entries_without_modifying_sources(tmp_path: Path) -> None:
    relevant = _write_entry(tmp_path, "relevant", _entry())
    unrelated = _write_entry(
        tmp_path,
        "unrelated",
        _entry(
            "cloud.workspace.internal",
            consumers=["multiagent-collaboration-framework"],
        ),
    )
    before = (relevant.read_bytes(), unrelated.read_bytes())

    projection = McfCapabilityRegistryRepositoryReader(
        registry_root=tmp_path
    ).inspect(project_id="triview-workspace-linux")

    assert projection.status == "VALID"
    assert projection.retrieved_at is None
    assert projection.sources == ()
    assert [entry.capability_id for entry in projection.entries] == [
        "cloud.workspace.g2a.read"
    ]
    assert (relevant.read_bytes(), unrelated.read_bytes()) == before


def test_repository_reader_fails_closed_for_alias_symlink_size_and_file_limits(
    tmp_path: Path,
) -> None:
    alias_root = tmp_path / "alias"
    alias_path = alias_root / "context/capabilities/alias.yaml"
    alias_path.parent.mkdir(parents=True)
    alias_path.write_text("capability: &shared {}\ncopy: *shared\n", encoding="utf-8")
    aliased = McfCapabilityRegistryRepositoryReader(registry_root=alias_root).inspect(
        project_id="triview-workspace-linux"
    )
    assert aliased.status == "INVALID"
    assert aliased.error_codes == ("CAPABILITY_SOURCE_YAML_ALIAS_FORBIDDEN",)

    symlink_root = tmp_path / "symlink"
    target = _write_entry(symlink_root, "target", _entry())
    link = symlink_root / "context/capabilities/link.yaml"
    link.symlink_to(target)
    symlinked = McfCapabilityRegistryRepositoryReader(registry_root=symlink_root).inspect(
        project_id="triview-workspace-linux"
    )
    assert symlinked.status == "INVALID"
    assert symlinked.error_codes == ("CAPABILITY_SOURCE_SYMLINK_FORBIDDEN",)

    size_root = tmp_path / "size"
    _write_entry(size_root, "large", _entry())
    limited = McfCapabilityRegistryRepositoryReader(
        registry_root=size_root,
        max_source_bytes=8,
    ).inspect(project_id="triview-workspace-linux")
    assert limited.status == "INVALID"
    assert limited.error_codes == ("CAPABILITY_SOURCE_TOO_LARGE",)

    count_root = tmp_path / "count"
    _write_entry(count_root, "one", _entry("capability.one"))
    _write_entry(count_root, "two", _entry("capability.two"))
    count_limited = McfCapabilityRegistryRepositoryReader(
        registry_root=count_root,
        max_capability_files=1,
    ).inspect(project_id="triview-workspace-linux")
    assert count_limited.status == "INVALID"
    assert count_limited.error_codes == ("CAPABILITY_SOURCE_LIMIT_EXCEEDED",)
