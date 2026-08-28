"""Strict read-only projections of the MCF Capability Registry.

The MCF Registry remains authoritative.  TriView validates bounded snapshots or
repository YAML and renders lifecycle evidence; it never connects, authorizes,
verifies, or executes a capability.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from triview_workspace.mcf_context_fabric import (
    McfContextFabricError,
    _date_time,
    _has_symlink_component,
    _mapping,
    _read_yaml,
    _string_list,
    _text,
)

CapabilityRegistryStatus = Literal["ABSENT", "VALID", "INVALID"]
McfCapabilityRegistryError = McfContextFabricError

_STABLE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_OPERATION = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_CAPABILITY_DIRECTORY = "context/capabilities"
_DEFAULT_MAX_SOURCE_BYTES = 256 * 1024
_DEFAULT_MAX_CAPABILITY_FILES = 128
_MODES = frozenset({"READ_ONLY", "BOUNDED_WRITE"})
_ENVIRONMENTS = frozenset({"dev", "lab", "staging"})
_AUTHORIZATION_STATES = frozenset({"NOT_AUTHORIZED", "AUTHORIZED"})
_IMPLEMENTATION_STATES = frozenset({"DECLARED", "IMPLEMENTED"})
_CONNECTION_STATES = frozenset({"DISCONNECTED", "CONNECTED"})
_RUNTIME_STATES = frozenset({"UNKNOWN", "INACTIVE", "ACTIVE", "BLOCKED"})
_VERIFICATION_STATES = frozenset(
    {"NOT_VERIFIED", "HISTORICALLY_VERIFIED", "VERIFIED"}
)


@dataclass(frozen=True, slots=True)
class McfCapabilityEvidenceProjection:
    source_ref: str
    source_revision: str
    observed_at: str | None = None


@dataclass(frozen=True, slots=True)
class McfCapabilityEntryProjection:
    capability_id: str
    provider_project_id: str
    consumer_project_ids: tuple[str, ...]
    mode: str
    protocol: str
    allowed_operations: tuple[str, ...]
    prohibited_operations: tuple[str, ...]
    environments: tuple[str, ...]
    resources: tuple[str, ...]
    authorization_state: str
    required_gate: str | None
    expiration: str | None
    implementation_state: str
    connection_state: str
    runtime_state: str
    verification_state: str
    last_verified_at: str | None
    evidence: tuple[McfCapabilityEvidenceProjection, ...]
    freshness: str

    def involves(self, project_id: str) -> bool:
        return (
            self.provider_project_id == project_id
            or project_id in self.consumer_project_ids
        )


@dataclass(frozen=True, slots=True)
class McfCapabilityRegistryProjection:
    status: CapabilityRegistryStatus
    project_id: str | None = None
    retrieved_at: str | None = None
    entries: tuple[McfCapabilityEntryProjection, ...] = ()
    sources: tuple[McfCapabilityEvidenceProjection, ...] = ()
    error_codes: tuple[str, ...] = ()
    read_only: bool = True
    evidence_only: bool = True
    source: str = "MCF_CAPABILITY_REGISTRY_REPOSITORY_READ_ONLY"


def _enum(value: object, *, allowed: frozenset[str], code: str) -> str:
    selected = _text(value, maximum=64, code=code)
    if selected not in allowed:
        raise McfCapabilityRegistryError(code)
    return selected


def _optional_text(value: object, *, maximum: int, code: str) -> str | None:
    if value is None:
        return None
    return _text(value, maximum=maximum, code=code)


def _optional_date_time(value: object, *, code: str) -> str | None:
    if value is None:
        return None
    return _date_time(value, code=code)


def _validate_evidence(value: object, *, code: str) -> McfCapabilityEvidenceProjection:
    evidence = _mapping(
        value,
        required=frozenset({"source_ref", "source_revision"}),
        optional=frozenset({"observed_at"}),
        code=code,
    )
    return McfCapabilityEvidenceProjection(
        source_ref=_text(
            evidence["source_ref"], maximum=1024, code=f"{code}_SOURCE_REF_INVALID"
        ),
        source_revision=_text(
            evidence["source_revision"],
            maximum=256,
            code=f"{code}_SOURCE_REVISION_INVALID",
        ),
        observed_at=(
            _date_time(evidence["observed_at"], code=f"{code}_OBSERVED_AT_INVALID")
            if "observed_at" in evidence
            else None
        ),
    )


def _validate_entry(value: object) -> McfCapabilityEntryProjection:
    root = _mapping(
        value,
        required=frozenset(
            {
                "schema_version",
                "capability",
                "contract",
                "scope",
                "governance",
                "lifecycle",
                "evidence",
                "freshness",
            }
        ),
        code="CAPABILITY_ENTRY",
    )
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise McfCapabilityRegistryError("CAPABILITY_SCHEMA_VERSION_INVALID")

    capability = _mapping(
        root["capability"],
        required=frozenset(
            {"id", "provider_project_id", "consumer_project_ids", "mode"}
        ),
        code="CAPABILITY_IDENTITY",
    )
    capability_id = _text(
        capability["id"],
        maximum=128,
        code="CAPABILITY_ID_INVALID",
        pattern=_STABLE_ID,
    )
    provider_project_id = _text(
        capability["provider_project_id"],
        maximum=128,
        code="CAPABILITY_PROVIDER_INVALID",
        pattern=_STABLE_ID,
    )
    consumer_project_ids = _string_list(
        capability["consumer_project_ids"],
        minimum=1,
        maximum=64,
        item_maximum=128,
        code="CAPABILITY_CONSUMERS_INVALID",
        pattern=_STABLE_ID,
    )
    mode = _enum(capability["mode"], allowed=_MODES, code="CAPABILITY_MODE_INVALID")

    contract = _mapping(
        root["contract"],
        required=frozenset(
            {"protocol", "allowed_operations", "prohibited_operations"}
        ),
        code="CAPABILITY_CONTRACT",
    )
    protocol = _text(
        contract["protocol"], maximum=1024, code="CAPABILITY_PROTOCOL_INVALID"
    )
    allowed_operations = _string_list(
        contract["allowed_operations"],
        minimum=1,
        maximum=128,
        item_maximum=128,
        code="CAPABILITY_ALLOWED_OPERATIONS_INVALID",
        pattern=_OPERATION,
    )
    prohibited_operations = _string_list(
        contract["prohibited_operations"],
        minimum=1,
        maximum=128,
        item_maximum=128,
        code="CAPABILITY_PROHIBITED_OPERATIONS_INVALID",
        pattern=_OPERATION,
    )
    if set(allowed_operations).intersection(prohibited_operations):
        raise McfCapabilityRegistryError("CAPABILITY_OPERATION_CONFLICT")

    scope = _mapping(
        root["scope"],
        required=frozenset({"environments", "resources"}),
        code="CAPABILITY_SCOPE",
    )
    environments = _string_list(
        scope["environments"],
        minimum=1,
        maximum=3,
        item_maximum=16,
        code="CAPABILITY_ENVIRONMENTS_INVALID",
    )
    if any(environment not in _ENVIRONMENTS for environment in environments):
        raise McfCapabilityRegistryError("CAPABILITY_ENVIRONMENTS_INVALID")
    resources = _string_list(
        scope["resources"],
        minimum=1,
        maximum=128,
        item_maximum=1024,
        code="CAPABILITY_RESOURCES_INVALID",
    )

    governance = _mapping(
        root["governance"],
        required=frozenset({"authorization_state", "required_gate", "expiration"}),
        code="CAPABILITY_GOVERNANCE",
    )
    authorization_state = _enum(
        governance["authorization_state"],
        allowed=_AUTHORIZATION_STATES,
        code="CAPABILITY_AUTHORIZATION_INVALID",
    )
    required_gate = _optional_text(
        governance["required_gate"],
        maximum=1024,
        code="CAPABILITY_GATE_INVALID",
    )
    expiration = _optional_date_time(
        governance["expiration"], code="CAPABILITY_EXPIRATION_INVALID"
    )

    lifecycle = _mapping(
        root["lifecycle"],
        required=frozenset(
            {
                "implementation_state",
                "connection_state",
                "runtime_state",
                "verification_state",
                "last_verified_at",
            }
        ),
        code="CAPABILITY_LIFECYCLE",
    )
    implementation_state = _enum(
        lifecycle["implementation_state"],
        allowed=_IMPLEMENTATION_STATES,
        code="CAPABILITY_IMPLEMENTATION_INVALID",
    )
    connection_state = _enum(
        lifecycle["connection_state"],
        allowed=_CONNECTION_STATES,
        code="CAPABILITY_CONNECTION_INVALID",
    )
    runtime_state = _enum(
        lifecycle["runtime_state"],
        allowed=_RUNTIME_STATES,
        code="CAPABILITY_RUNTIME_INVALID",
    )
    verification_state = _enum(
        lifecycle["verification_state"],
        allowed=_VERIFICATION_STATES,
        code="CAPABILITY_VERIFICATION_INVALID",
    )
    last_verified_at = _optional_date_time(
        lifecycle["last_verified_at"],
        code="CAPABILITY_LAST_VERIFIED_INVALID",
    )

    if mode == "BOUNDED_WRITE" and required_gate is None:
        raise McfCapabilityRegistryError("CAPABILITY_WRITE_GATE_REQUIRED")
    if verification_state == "NOT_VERIFIED" and last_verified_at is not None:
        raise McfCapabilityRegistryError("CAPABILITY_VERIFICATION_TIME_INVALID")
    if verification_state != "NOT_VERIFIED" and last_verified_at is None:
        raise McfCapabilityRegistryError("CAPABILITY_VERIFICATION_TIME_INVALID")
    if runtime_state == "ACTIVE" and (
        authorization_state != "AUTHORIZED"
        or implementation_state != "IMPLEMENTED"
        or connection_state != "CONNECTED"
        or verification_state != "VERIFIED"
        or last_verified_at is None
    ):
        raise McfCapabilityRegistryError("CAPABILITY_ACTIVE_STATE_INVALID")

    raw_evidence = root["evidence"]
    if not isinstance(raw_evidence, list) or not 1 <= len(raw_evidence) <= 128:
        raise McfCapabilityRegistryError("CAPABILITY_EVIDENCE_INVALID")
    evidence = tuple(
        _validate_evidence(item, code="CAPABILITY_EVIDENCE")
        for item in raw_evidence
    )
    if root["freshness"] != "LIVE_REQUIRED":
        raise McfCapabilityRegistryError("CAPABILITY_FRESHNESS_INVALID")

    return McfCapabilityEntryProjection(
        capability_id=capability_id,
        provider_project_id=provider_project_id,
        consumer_project_ids=consumer_project_ids,
        mode=mode,
        protocol=protocol,
        allowed_operations=allowed_operations,
        prohibited_operations=prohibited_operations,
        environments=environments,
        resources=resources,
        authorization_state=authorization_state,
        required_gate=required_gate,
        expiration=expiration,
        implementation_state=implementation_state,
        connection_state=connection_state,
        runtime_state=runtime_state,
        verification_state=verification_state,
        last_verified_at=last_verified_at,
        evidence=evidence,
        freshness="LIVE_REQUIRED",
    )


def _validate_entries(value: object) -> tuple[McfCapabilityEntryProjection, ...]:
    if not isinstance(value, list) or len(value) > _DEFAULT_MAX_CAPABILITY_FILES:
        raise McfCapabilityRegistryError("CAPABILITY_ENTRIES_INVALID")
    entries = tuple(_validate_entry(item) for item in value)
    ids = [entry.capability_id for entry in entries]
    if len(set(ids)) != len(ids):
        raise McfCapabilityRegistryError("CAPABILITY_ID_DUPLICATED")
    return entries


class McfCapabilityRegistrySnapshotParser:
    """Accept only bounded evidence-only snapshots from the MCF GET endpoint."""

    def parse(self, value: object) -> McfCapabilityRegistryProjection:
        root = _mapping(
            value,
            required=frozenset(
                {
                    "schema_version",
                    "retrieved_at",
                    "project_id",
                    "read_only",
                    "evidence_only",
                    "entries",
                    "sources",
                }
            ),
            code="CAPABILITY_SNAPSHOT",
        )
        if type(root["schema_version"]) is not int or root["schema_version"] != 1:
            raise McfCapabilityRegistryError("CAPABILITY_SNAPSHOT_SCHEMA_VERSION_INVALID")
        if root["read_only"] is not True:
            raise McfCapabilityRegistryError("CAPABILITY_SNAPSHOT_NOT_READ_ONLY")
        if root["evidence_only"] is not True:
            raise McfCapabilityRegistryError("CAPABILITY_SNAPSHOT_NOT_EVIDENCE_ONLY")
        project_value = root["project_id"]
        project_id = (
            None
            if project_value is None
            else _text(
                project_value,
                maximum=128,
                code="CAPABILITY_SNAPSHOT_PROJECT_ID_INVALID",
                pattern=_STABLE_ID,
            )
        )
        entries = _validate_entries(root["entries"])
        if project_id is not None and any(
            not entry.involves(project_id) for entry in entries
        ):
            raise McfCapabilityRegistryError("CAPABILITY_SNAPSHOT_PROJECT_FILTER_INVALID")
        raw_sources = root["sources"]
        if not isinstance(raw_sources, list) or len(raw_sources) > 128:
            raise McfCapabilityRegistryError("CAPABILITY_SNAPSHOT_SOURCES_INVALID")
        sources = tuple(
            _validate_evidence(item, code="CAPABILITY_SNAPSHOT_SOURCE")
            for item in raw_sources
        )
        return McfCapabilityRegistryProjection(
            status="VALID",
            project_id=project_id,
            retrieved_at=_date_time(
                root["retrieved_at"], code="CAPABILITY_SNAPSHOT_RETRIEVED_AT_INVALID"
            ),
            entries=entries,
            sources=sources,
            source="MCF_CAPABILITY_REGISTRY_GET_READ_ONLY",
        )


class McfCapabilityRegistryRepositoryReader:
    """Read repository capability entries as an explicit non-live fallback."""

    def __init__(
        self,
        *,
        registry_root: str | Path | None = None,
        max_source_bytes: int = _DEFAULT_MAX_SOURCE_BYTES,
        max_capability_files: int = _DEFAULT_MAX_CAPABILITY_FILES,
    ) -> None:
        if max_source_bytes <= 0 or max_capability_files <= 0:
            raise ValueError("Capability Registry read limits must be greater than zero")
        self.registry_root = (
            Path(registry_root).expanduser().resolve()
            if registry_root is not None
            else None
        )
        self.max_source_bytes = max_source_bytes
        self.max_capability_files = max_capability_files

    def inspect(
        self,
        *,
        project_id: str | None,
        registry_root: str | Path | None = None,
    ) -> McfCapabilityRegistryProjection:
        selected_root = (
            Path(registry_root).expanduser().resolve()
            if registry_root is not None
            else self.registry_root
        )
        if selected_root is None:
            return McfCapabilityRegistryProjection(status="ABSENT", project_id=project_id)
        if project_id is not None:
            try:
                project_id = _text(
                    project_id,
                    maximum=128,
                    code="CAPABILITY_PROJECT_ID_INVALID",
                    pattern=_STABLE_ID,
                )
            except McfCapabilityRegistryError as exc:
                return McfCapabilityRegistryProjection(
                    status="INVALID",
                    error_codes=(str(exc),),
                )

        directory = selected_root / _CAPABILITY_DIRECTORY
        if not directory.exists() and not directory.is_symlink():
            return McfCapabilityRegistryProjection(status="ABSENT", project_id=project_id)
        if not directory.is_dir() or _has_symlink_component(selected_root, directory):
            return McfCapabilityRegistryProjection(
                status="INVALID",
                project_id=project_id,
                error_codes=("CAPABILITY_REGISTRY_DIRECTORY_INVALID",),
            )
        candidates = sorted(directory.glob("*.yaml"))
        if len(candidates) > self.max_capability_files:
            return McfCapabilityRegistryProjection(
                status="INVALID",
                project_id=project_id,
                error_codes=("CAPABILITY_SOURCE_LIMIT_EXCEEDED",),
            )

        try:
            entries = _validate_entries(
                [
                    _read_yaml(
                        selected_root,
                        candidate.relative_to(selected_root).as_posix(),
                        maximum_bytes=self.max_source_bytes,
                        code="CAPABILITY_SOURCE",
                    )
                    for candidate in candidates
                ]
            )
        except (McfCapabilityRegistryError, ValueError) as exc:
            return McfCapabilityRegistryProjection(
                status="INVALID",
                project_id=project_id,
                error_codes=(str(exc),),
            )
        filtered = (
            entries
            if project_id is None
            else tuple(entry for entry in entries if entry.involves(project_id))
        )
        return McfCapabilityRegistryProjection(
            status="VALID",
            project_id=project_id,
            entries=filtered,
        )


__all__ = [
    "CapabilityRegistryStatus",
    "McfCapabilityEntryProjection",
    "McfCapabilityEvidenceProjection",
    "McfCapabilityRegistryError",
    "McfCapabilityRegistryProjection",
    "McfCapabilityRegistryRepositoryReader",
    "McfCapabilityRegistrySnapshotParser",
]
