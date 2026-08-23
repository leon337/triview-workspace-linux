"""Safe, read-only projections of MCF Context Fabric contracts.

MCF remains authoritative for Registry resolution, recovery semantics and Receipts.
This module only validates bounded repository inputs for an offline projection and
strictly parses evidence-only Receipts returned by an MCF read endpoint.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ContextFabricStatus = Literal["ABSENT", "PARTIAL", "VALID", "INVALID"]

_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_CANONICAL_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_REPOSITORY_PATH = re.compile(
    r"^(?![A-Za-z]:)(?!/)(?!.*\\)(?!.*(?:^|/)\.\.?(?:/|$))"
    r"(?!.*//)(?!.*[\x00-\x1F\x7F])(?=.*\S)[^/]+(?:/[^/]+)*$"
)
_RFC_3339_DATE_TIME = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})"
    r"(?:\.\d+)?(?:[Zz]|([+-])(\d{2}):(\d{2}))$"
)
_REGISTRY_LIFECYCLES = frozenset(
    {"DISCOVERABLE", "CANDIDATE", "REGISTERED", "SUSPENDED", "ARCHIVED"}
)
_RECOVERY_STATES = frozenset(
    {
        "RECOVERED",
        "PARTIAL_RECOVERY",
        "AMBIGUOUS_CONTEXT",
        "SOURCE_UNAVAILABLE",
        "INVALID_CONTEXT",
        "DRIFT_DETECTED",
        "RECONCILIATION_REQUIRED",
    }
)
_SOURCE_ROLES = frozenset({"REGISTRY", "CAPSULE", "LIVE_VERIFICATION"})
_CLAIM_TYPES = frozenset({"IDENTITY", "NORMATIVE", "OPERATIONAL", "DERIVED"})
_FRESHNESS = frozenset({"DURABLE", "SNAPSHOT", "LIVE_REQUIRED", "DERIVED"})
_CAPSULE_PATH = ".mcf/project-capsule.yaml"
_REGISTRY_DIRECTORY = "context/projects"
_DEFAULT_MAX_SOURCE_BYTES = 256 * 1024
_DEFAULT_MAX_REGISTRY_FILES = 256
_MAX_JSON_DEPTH = 32


class McfContextFabricError(ValueError):
    """Raised when an untrusted Context Fabric input fails closed."""


@dataclass(frozen=True, slots=True)
class McfContextFabricProjection:
    """Derived repository view; never an MCF recovery decision or Receipt."""

    status: ContextFabricStatus
    project_id: str | None = None
    canonical_repository: str | None = None
    aliases: tuple[str, ...] = ()
    registry_path: str | None = None
    capsule_path: str | None = None
    registry_lifecycle: str | None = None
    capsule_lifecycle: str | None = None
    purpose: str | None = None
    current_workstream: str | None = None
    current_status: str | None = None
    next_action: str | None = None
    blockers: tuple[str, ...] = ()
    observed_at: str | None = None
    operational_freshness: str | None = None
    project_identity_freshness: str | None = None
    error_codes: tuple[str, ...] = ()
    source: str = "REPOSITORY_CONTEXT_FABRIC_READ_ONLY"


@dataclass(frozen=True, slots=True)
class McfContextSourceProjection:
    role: str
    source_ref: str
    source_revision: str
    observed_at: str | None = None


@dataclass(frozen=True, slots=True)
class McfTruthClaimProjection:
    claim_key: str
    claim_type: str
    owner: str
    source_ref: str
    freshness: str
    observed_at: str | None
    requires_live_verification: bool


@dataclass(frozen=True, slots=True)
class McfContextRecoveryReceiptProjection:
    """Token-free projection of one schema-valid, read-only MCF Receipt."""

    receipt_id: str
    project_id: str | None
    recovery_state: str
    recovered_at: str
    sources: tuple[McfContextSourceProjection, ...]
    claims: tuple[McfTruthClaimProjection, ...]
    warnings: tuple[str, ...]
    freshness: tuple[str, ...]
    requires_live_verification: bool
    read_only: bool = True
    material_action: bool = False
    evidence_only: bool = True
    source: str = "MCF_CONTEXT_RECOVERY_GET_READ_ONLY"


@dataclass(frozen=True, slots=True)
class _RegistryRecord:
    project_id: str
    lifecycle: str
    canonical_repository: str
    aliases: tuple[str, ...]
    project_owner: str
    capsule_path: str
    canonical_entrypoints: tuple[str, ...]
    operational_freshness: str
    project_identity_freshness: str


@dataclass(frozen=True, slots=True)
class _CapsuleRecord:
    project_id: str
    purpose: str
    lifecycle: str
    current_workstream: str
    current_status: str
    next_action: str
    blockers: tuple[str, ...]
    current_state_source: str
    observed_at: str


def _fail(code: str) -> McfContextFabricError:
    return McfContextFabricError(code)


def _mapping(
    value: object,
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    code: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail(f"{code}_NOT_OBJECT")
    keys = {str(key) for key in value}
    if keys != set(value):
        raise _fail(f"{code}_NON_STRING_KEY")
    missing = required - keys
    unknown = keys - required - optional
    if missing:
        raise _fail(f"{code}_MISSING_FIELDS")
    if unknown:
        raise _fail(f"{code}_UNKNOWN_FIELDS")
    return value


def _text(value: object, *, maximum: int, code: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or not value.strip():
        raise _fail(code)
    if pattern is not None and pattern.fullmatch(value) is None:
        raise _fail(code)
    return value


def _date_time(value: object, *, code: str) -> str:
    text = _text(value, maximum=128, code=code)
    match = _RFC_3339_DATE_TIME.fullmatch(text)
    if match is None:
        raise _fail(code)
    year, month, day, hour, minute, second = (
        int(part) for part in match.groups()[:6]
    )
    offset_hour = int(match.group(8) or 0)
    offset_minute = int(match.group(9) or 0)
    leap_year = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days_by_month = (31, 29 if leap_year else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if not (
        1 <= month <= 12
        and 1 <= day <= days_by_month[month - 1]
        and hour <= 23
        and minute <= 59
        and second <= 59
        and offset_hour <= 23
        and offset_minute <= 59
    ):
        raise _fail(code)
    return text


def _string_list(
    value: object,
    *,
    minimum: int,
    maximum: int,
    item_maximum: int,
    code: str,
    pattern: re.Pattern[str] | None = None,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise _fail(code)
    items = tuple(
        _text(item, maximum=item_maximum, code=code, pattern=pattern) for item in value
    )
    if len(set(items)) != len(items):
        raise _fail(f"{code}_DUPLICATE")
    return items


def _has_symlink_component(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _safe_path(root: Path, relative_path: str, *, code: str) -> Path:
    if _REPOSITORY_PATH.fullmatch(relative_path) is None:
        raise _fail(f"{code}_UNSAFE_PATH")
    candidate = root / relative_path
    if _has_symlink_component(root, candidate):
        raise _fail(f"{code}_SYMLINK_FORBIDDEN")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise _fail(f"{code}_UNSAFE_PATH") from exc
    return resolved


def _read_yaml(root: Path, relative_path: str, *, maximum_bytes: int, code: str) -> object:
    path = _safe_path(root, relative_path, code=code)
    if not path.is_file():
        raise _fail(f"{code}_UNAVAILABLE")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise _fail(f"{code}_UNAVAILABLE") from exc
    if size > maximum_bytes:
        raise _fail(f"{code}_TOO_LARGE")
    try:
        import yaml
        from yaml.tokens import AliasToken, AnchorToken
    except ImportError as exc:
        raise _fail("CONTEXT_FABRIC_YAML_RUNTIME_UNAVAILABLE") from exc
    try:
        raw = path.read_text(encoding="utf-8")
        tokens = yaml.scan(raw, Loader=yaml.SafeLoader)
        if any(isinstance(token, (AliasToken, AnchorToken)) for token in tokens):
            raise _fail(f"{code}_YAML_ALIAS_FORBIDDEN")
        return yaml.safe_load(raw)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise _fail(f"{code}_INVALID_YAML") from exc


def _validate_registry(value: object) -> _RegistryRecord:
    root = _mapping(
        value,
        required=frozenset(
            {"schema_version", "project", "identity", "ownership", "context", "freshness"}
        ),
        code="REGISTRY",
    )
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise _fail("REGISTRY_SCHEMA_VERSION_INVALID")
    project = _mapping(
        root["project"], required=frozenset({"id", "lifecycle"}), code="REGISTRY_PROJECT"
    )
    project_id = _text(
        project["id"], maximum=128, code="REGISTRY_PROJECT_ID_INVALID", pattern=_PROJECT_ID
    )
    lifecycle = _text(project["lifecycle"], maximum=32, code="REGISTRY_LIFECYCLE_INVALID")
    if lifecycle not in _REGISTRY_LIFECYCLES:
        raise _fail("REGISTRY_LIFECYCLE_INVALID")

    identity = _mapping(
        root["identity"],
        required=frozenset({"canonical_repository", "aliases"}),
        code="REGISTRY_IDENTITY",
    )
    canonical_repository = _text(
        identity["canonical_repository"],
        maximum=256,
        code="REGISTRY_REPOSITORY_INVALID",
        pattern=_CANONICAL_REPOSITORY,
    )
    aliases = _string_list(
        identity["aliases"],
        minimum=1,
        maximum=64,
        item_maximum=128,
        code="REGISTRY_ALIASES_INVALID",
    )

    ownership = _mapping(
        root["ownership"], required=frozenset({"project_owner"}), code="REGISTRY_OWNERSHIP"
    )
    project_owner = _text(
        ownership["project_owner"], maximum=128, code="REGISTRY_OWNER_INVALID"
    )

    context = _mapping(
        root["context"],
        required=frozenset({"capsule_path", "canonical_entrypoints"}),
        code="REGISTRY_CONTEXT",
    )
    capsule_path = _text(
        context["capsule_path"],
        maximum=512,
        code="REGISTRY_CAPSULE_PATH_INVALID",
        pattern=_REPOSITORY_PATH,
    )
    entrypoints = _string_list(
        context["canonical_entrypoints"],
        minimum=1,
        maximum=64,
        item_maximum=512,
        code="REGISTRY_ENTRYPOINTS_INVALID",
        pattern=_REPOSITORY_PATH,
    )

    freshness = _mapping(
        root["freshness"],
        required=frozenset({"operational_state", "project_identity"}),
        code="REGISTRY_FRESHNESS",
    )
    if freshness["operational_state"] != "LIVE_REQUIRED":
        raise _fail("REGISTRY_OPERATIONAL_FRESHNESS_INVALID")
    if freshness["project_identity"] != "DURABLE":
        raise _fail("REGISTRY_IDENTITY_FRESHNESS_INVALID")
    return _RegistryRecord(
        project_id=project_id,
        lifecycle=lifecycle,
        canonical_repository=canonical_repository,
        aliases=aliases,
        project_owner=project_owner,
        capsule_path=capsule_path,
        canonical_entrypoints=entrypoints,
        operational_freshness="LIVE_REQUIRED",
        project_identity_freshness="DURABLE",
    )


def _validate_capsule(value: object) -> _CapsuleRecord:
    root = _mapping(
        value,
        required=frozenset(
            {
                "schema_version",
                "project_id",
                "purpose",
                "lifecycle",
                "snapshot",
                "sources",
                "observed_at",
            }
        ),
        code="CAPSULE",
    )
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise _fail("CAPSULE_SCHEMA_VERSION_INVALID")
    project_id = _text(
        root["project_id"], maximum=128, code="CAPSULE_PROJECT_ID_INVALID", pattern=_PROJECT_ID
    )
    purpose = _text(root["purpose"], maximum=2048, code="CAPSULE_PURPOSE_INVALID")
    lifecycle = _text(root["lifecycle"], maximum=128, code="CAPSULE_LIFECYCLE_INVALID")
    snapshot = _mapping(
        root["snapshot"],
        required=frozenset({"current_workstream", "current_status", "next_action", "blockers"}),
        code="CAPSULE_SNAPSHOT",
    )
    current_workstream = _text(
        snapshot["current_workstream"], maximum=256, code="CAPSULE_WORKSTREAM_INVALID"
    )
    current_status = _text(
        snapshot["current_status"], maximum=256, code="CAPSULE_STATUS_INVALID"
    )
    next_action = _text(
        snapshot["next_action"], maximum=1024, code="CAPSULE_NEXT_ACTION_INVALID"
    )
    blockers = _string_list(
        snapshot["blockers"],
        minimum=0,
        maximum=64,
        item_maximum=1024,
        code="CAPSULE_BLOCKERS_INVALID",
    )
    sources = _mapping(
        root["sources"], required=frozenset({"current_state"}), code="CAPSULE_SOURCES"
    )
    current_state = _text(
        sources["current_state"],
        maximum=512,
        code="CAPSULE_CURRENT_STATE_INVALID",
        pattern=_REPOSITORY_PATH,
    )
    return _CapsuleRecord(
        project_id=project_id,
        purpose=purpose,
        lifecycle=lifecycle,
        current_workstream=current_workstream,
        current_status=current_status,
        next_action=next_action,
        blockers=blockers,
        current_state_source=current_state,
        observed_at=_date_time(root["observed_at"], code="CAPSULE_OBSERVED_AT_INVALID"),
    )


class McfContextFabricRepositoryReader:
    """Read the project Capsule and its MCF-owned Registry entry without mutation."""

    def __init__(
        self,
        *,
        registry_root: str | Path | None = None,
        max_source_bytes: int = _DEFAULT_MAX_SOURCE_BYTES,
        max_registry_files: int = _DEFAULT_MAX_REGISTRY_FILES,
    ) -> None:
        if max_source_bytes <= 0 or max_registry_files <= 0:
            raise ValueError("Context Fabric read limits must be greater than zero")
        self.registry_root = (
            Path(registry_root).expanduser().resolve() if registry_root is not None else None
        )
        self.max_source_bytes = max_source_bytes
        self.max_registry_files = max_registry_files

    def inspect(
        self,
        project_root: str | Path,
        *,
        registry_root: str | Path | None = None,
    ) -> McfContextFabricProjection:
        root = Path(project_root).expanduser().resolve()
        capsule_candidate = root / _CAPSULE_PATH
        if not capsule_candidate.exists() and not capsule_candidate.is_symlink():
            return McfContextFabricProjection(status="ABSENT")
        try:
            capsule = _validate_capsule(
                _read_yaml(
                    root,
                    _CAPSULE_PATH,
                    maximum_bytes=self.max_source_bytes,
                    code="CAPSULE_SOURCE",
                )
            )
        except McfContextFabricError as exc:
            return McfContextFabricProjection(
                status="INVALID",
                capsule_path=str(capsule_candidate),
                error_codes=(str(exc),),
            )

        selected_registry_root = (
            Path(registry_root).expanduser().resolve()
            if registry_root is not None
            else self.registry_root or root
        )
        registry_directory = selected_registry_root / _REGISTRY_DIRECTORY
        if not registry_directory.is_dir() or _has_symlink_component(
            selected_registry_root, registry_directory
        ):
            return self._capsule_projection(
                capsule,
                status="PARTIAL",
                capsule_path=str(capsule_candidate.resolve()),
                errors=("PROJECT_REGISTRY_UNAVAILABLE",),
            )

        candidates = sorted(registry_directory.glob("*.yaml"))
        if len(candidates) > self.max_registry_files:
            return self._capsule_projection(
                capsule,
                status="INVALID",
                capsule_path=str(capsule_candidate.resolve()),
                errors=("PROJECT_REGISTRY_FILE_LIMIT_EXCEEDED",),
            )

        registries: list[tuple[Path, _RegistryRecord]] = []
        for candidate in candidates:
            try:
                relative = candidate.relative_to(selected_registry_root).as_posix()
                registry = _validate_registry(
                    _read_yaml(
                        selected_registry_root,
                        relative,
                        maximum_bytes=self.max_source_bytes,
                        code="REGISTRY_SOURCE",
                    )
                )
            except ValueError as exc:
                return self._capsule_projection(
                    capsule,
                    status="INVALID",
                    capsule_path=str(capsule_candidate.resolve()),
                    errors=(str(exc),),
                )
            registries.append((candidate.resolve(), registry))

        matches = [
            (path, entry)
            for path, entry in registries
            if entry.project_id == capsule.project_id
        ]
        if not matches:
            return self._capsule_projection(
                capsule,
                status="PARTIAL",
                capsule_path=str(capsule_candidate.resolve()),
                errors=("PROJECT_REGISTRY_ENTRY_UNAVAILABLE",),
            )
        if len(matches) != 1:
            return self._capsule_projection(
                capsule,
                status="INVALID",
                capsule_path=str(capsule_candidate.resolve()),
                errors=("PROJECT_REGISTRY_IDENTITY_AMBIGUOUS",),
            )

        registry_path, registry = matches[0]
        if registry.capsule_path != _CAPSULE_PATH:
            return self._capsule_projection(
                capsule,
                status="INVALID",
                capsule_path=str(capsule_candidate.resolve()),
                registry_path=str(registry_path),
                errors=("REGISTRY_CAPSULE_PATH_MISMATCH",),
            )
        try:
            resolved_capsule = _safe_path(root, registry.capsule_path, code="REGISTRY_CAPSULE")
        except McfContextFabricError as exc:
            return self._capsule_projection(
                capsule,
                status="INVALID",
                capsule_path=str(capsule_candidate.resolve()),
                registry_path=str(registry_path),
                errors=(str(exc),),
            )
        if resolved_capsule != capsule_candidate.resolve():
            return self._capsule_projection(
                capsule,
                status="INVALID",
                capsule_path=str(capsule_candidate.resolve()),
                registry_path=str(registry_path),
                errors=("REGISTRY_CAPSULE_PATH_MISMATCH",),
            )
        return McfContextFabricProjection(
            status="VALID",
            project_id=capsule.project_id,
            canonical_repository=registry.canonical_repository,
            aliases=registry.aliases,
            registry_path=str(registry_path),
            capsule_path=str(resolved_capsule),
            registry_lifecycle=registry.lifecycle,
            capsule_lifecycle=capsule.lifecycle,
            purpose=capsule.purpose,
            current_workstream=capsule.current_workstream,
            current_status=capsule.current_status,
            next_action=capsule.next_action,
            blockers=capsule.blockers,
            observed_at=capsule.observed_at,
            operational_freshness=registry.operational_freshness,
            project_identity_freshness=registry.project_identity_freshness,
        )

    @staticmethod
    def _capsule_projection(
        capsule: _CapsuleRecord,
        *,
        status: ContextFabricStatus,
        capsule_path: str,
        errors: tuple[str, ...],
        registry_path: str | None = None,
    ) -> McfContextFabricProjection:
        return McfContextFabricProjection(
            status=status,
            project_id=capsule.project_id,
            registry_path=registry_path,
            capsule_path=capsule_path,
            capsule_lifecycle=capsule.lifecycle,
            purpose=capsule.purpose,
            current_workstream=capsule.current_workstream,
            current_status=capsule.current_status,
            next_action=capsule.next_action,
            blockers=capsule.blockers,
            observed_at=capsule.observed_at,
            error_codes=errors,
        )


def _validate_json_value(value: object, *, depth: int = 0) -> None:
    if depth > _MAX_JSON_DEPTH:
        raise _fail("RECEIPT_CLAIM_VALUE_TOO_DEEP")
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not math.isfinite(value):
            raise _fail("RECEIPT_CLAIM_VALUE_INVALID_NUMBER")
        return
    if isinstance(value, list):
        if len(value) > 1024:
            raise _fail("RECEIPT_CLAIM_VALUE_LIST_TOO_LARGE")
        for item in value:
            _validate_json_value(item, depth=depth + 1)
        return
    if isinstance(value, Mapping):
        if len(value) > 1024 or any(not isinstance(key, str) for key in value):
            raise _fail("RECEIPT_CLAIM_VALUE_OBJECT_INVALID")
        for item in value.values():
            _validate_json_value(item, depth=depth + 1)
        return
    raise _fail("RECEIPT_CLAIM_VALUE_NOT_JSON")


def _validate_source(value: object) -> McfContextSourceProjection:
    source = _mapping(
        value,
        required=frozenset({"role", "source_ref", "source_revision"}),
        optional=frozenset({"observed_at"}),
        code="RECEIPT_SOURCE",
    )
    role = _text(source["role"], maximum=32, code="RECEIPT_SOURCE_ROLE_INVALID")
    if role not in _SOURCE_ROLES:
        raise _fail("RECEIPT_SOURCE_ROLE_INVALID")
    observed = (
        _date_time(source["observed_at"], code="RECEIPT_SOURCE_OBSERVED_AT_INVALID")
        if "observed_at" in source
        else None
    )
    if role == "LIVE_VERIFICATION" and observed is None:
        raise _fail("RECEIPT_LIVE_SOURCE_OBSERVED_AT_REQUIRED")
    return McfContextSourceProjection(
        role=role,
        source_ref=_text(
            source["source_ref"], maximum=1024, code="RECEIPT_SOURCE_REF_INVALID"
        ),
        source_revision=_text(
            source["source_revision"], maximum=256, code="RECEIPT_SOURCE_REVISION_INVALID"
        ),
        observed_at=observed,
    )


def _validate_claim(value: object) -> McfTruthClaimProjection:
    claim = _mapping(
        value,
        required=frozenset(
            {
                "claim_key",
                "type",
                "value",
                "owner",
                "source_ref",
                "freshness",
                "provenance",
                "requires_live_verification",
            }
        ),
        optional=frozenset({"observed_at"}),
        code="RECEIPT_CLAIM",
    )
    claim_type = _text(claim["type"], maximum=32, code="RECEIPT_CLAIM_TYPE_INVALID")
    freshness = _text(
        claim["freshness"], maximum=32, code="RECEIPT_CLAIM_FRESHNESS_INVALID"
    )
    if claim_type not in _CLAIM_TYPES:
        raise _fail("RECEIPT_CLAIM_TYPE_INVALID")
    if freshness not in _FRESHNESS:
        raise _fail("RECEIPT_CLAIM_FRESHNESS_INVALID")
    requires_live = claim["requires_live_verification"]
    if type(requires_live) is not bool:
        raise _fail("RECEIPT_CLAIM_LIVE_FLAG_INVALID")
    if (freshness == "LIVE_REQUIRED") is not requires_live:
        raise _fail("RECEIPT_CLAIM_LIVE_FLAG_INVALID")
    observed = (
        _date_time(claim["observed_at"], code="RECEIPT_CLAIM_OBSERVED_AT_INVALID")
        if "observed_at" in claim
        else None
    )
    if freshness == "SNAPSHOT" and observed is None:
        raise _fail("RECEIPT_SNAPSHOT_OBSERVED_AT_REQUIRED")
    provenance = claim["provenance"]
    if not isinstance(provenance, list) or not 1 <= len(provenance) <= 256:
        raise _fail("RECEIPT_CLAIM_PROVENANCE_INVALID")
    for item in provenance:
        entry = _mapping(
            item,
            required=frozenset({"source_ref", "source_revision"}),
            optional=frozenset({"observed_at"}),
            code="RECEIPT_PROVENANCE",
        )
        _text(entry["source_ref"], maximum=1024, code="RECEIPT_PROVENANCE_REF_INVALID")
        _text(
            entry["source_revision"],
            maximum=256,
            code="RECEIPT_PROVENANCE_REVISION_INVALID",
        )
        if "observed_at" in entry:
            _date_time(entry["observed_at"], code="RECEIPT_PROVENANCE_OBSERVED_AT_INVALID")
    _validate_json_value(claim["value"])
    return McfTruthClaimProjection(
        claim_key=_text(claim["claim_key"], maximum=256, code="RECEIPT_CLAIM_KEY_INVALID"),
        claim_type=claim_type,
        owner=_text(claim["owner"], maximum=256, code="RECEIPT_CLAIM_OWNER_INVALID"),
        source_ref=_text(
            claim["source_ref"], maximum=1024, code="RECEIPT_CLAIM_SOURCE_REF_INVALID"
        ),
        freshness=freshness,
        observed_at=observed,
        requires_live_verification=requires_live,
    )


class McfContextRecoveryReceiptParser:
    """Fail closed unless a payload is a CF-0/CF-1 evidence-only read Receipt."""

    def parse(self, value: object) -> McfContextRecoveryReceiptProjection:
        receipt = _mapping(
            value,
            required=frozenset(
                {
                    "schema_version",
                    "receipt_id",
                    "project_id",
                    "recovery_state",
                    "recovered_at",
                    "read_only",
                    "material_action",
                    "sources",
                    "claims",
                    "warnings",
                    "evidence_only",
                }
            ),
            code="RECEIPT",
        )
        if type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1:
            raise _fail("RECEIPT_SCHEMA_VERSION_INVALID")
        if receipt["read_only"] is not True or receipt["material_action"] is not False:
            raise _fail("RECEIPT_NOT_READ_ONLY")
        if receipt["evidence_only"] is not True:
            raise _fail("RECEIPT_NOT_EVIDENCE_ONLY")
        project_value = receipt["project_id"]
        project_id = (
            None
            if project_value is None
            else _text(
                project_value,
                maximum=128,
                code="RECEIPT_PROJECT_ID_INVALID",
                pattern=_PROJECT_ID,
            )
        )
        recovery_state = _text(
            receipt["recovery_state"], maximum=64, code="RECEIPT_RECOVERY_STATE_INVALID"
        )
        if recovery_state not in _RECOVERY_STATES:
            raise _fail("RECEIPT_RECOVERY_STATE_INVALID")

        raw_sources = receipt["sources"]
        raw_claims = receipt["claims"]
        raw_warnings = receipt["warnings"]
        if not isinstance(raw_sources, list) or len(raw_sources) > 256:
            raise _fail("RECEIPT_SOURCES_INVALID")
        if not isinstance(raw_claims, list) or len(raw_claims) > 1024:
            raise _fail("RECEIPT_CLAIMS_INVALID")
        sources = tuple(_validate_source(item) for item in raw_sources)
        claims = tuple(_validate_claim(item) for item in raw_claims)
        warnings = _string_list(
            raw_warnings,
            minimum=0,
            maximum=256,
            item_maximum=1024,
            code="RECEIPT_WARNINGS_INVALID",
        )

        roles = {source.role for source in sources}
        if recovery_state == "RECOVERED" and (
            project_id is None
            or len(sources) < 2
            or not {"REGISTRY", "CAPSULE"}.issubset(roles)
            or not claims
        ):
            raise _fail("RECEIPT_RECOVERED_EVIDENCE_INCOMPLETE")
        if recovery_state == "PARTIAL_RECOVERY" and (
            project_id is None or not sources or not claims
        ):
            raise _fail("RECEIPT_PARTIAL_EVIDENCE_INCOMPLETE")
        if recovery_state == "AMBIGUOUS_CONTEXT" and project_id is not None:
            raise _fail("RECEIPT_AMBIGUOUS_PROJECT_MUST_BE_NULL")

        freshness = tuple(sorted({claim.freshness for claim in claims}))
        return McfContextRecoveryReceiptProjection(
            receipt_id=_text(
                receipt["receipt_id"], maximum=256, code="RECEIPT_ID_INVALID"
            ),
            project_id=project_id,
            recovery_state=recovery_state,
            recovered_at=_date_time(receipt["recovered_at"], code="RECEIPT_RECOVERED_AT_INVALID"),
            sources=sources,
            claims=claims,
            warnings=warnings,
            freshness=freshness,
            requires_live_verification=any(
                claim.requires_live_verification for claim in claims
            ),
        )


__all__ = [
    "ContextFabricStatus",
    "McfContextFabricError",
    "McfContextFabricProjection",
    "McfContextFabricRepositoryReader",
    "McfContextRecoveryReceiptParser",
    "McfContextRecoveryReceiptProjection",
    "McfContextSourceProjection",
    "McfTruthClaimProjection",
]
