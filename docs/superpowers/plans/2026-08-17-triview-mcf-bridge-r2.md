# TriView MCF Read-Only Bridge R2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only MCF v1.1 integration bridge that inspects canonical `.mcf` project artifacts and, when configured, reads mission/timeline/observability projections without creating a second authority inside TriView.

**Architecture:** Keep the existing `WorkspaceSpec`/layout/panel domain unchanged. Add one focused `mcf_bridge.py` module that produces derived snapshots from canonical repository artifacts and authenticated read-only runtime GET endpoints; callers may provide transient HTTP headers in memory, but the bridge never persists credentials or writes MCF artifacts.

**Tech Stack:** Python 3.11 standard library (`dataclasses`, `json`, `pathlib`, `urllib`), pytest 8, existing TriView package conventions.

## Global Constraints

- Compatibility baseline: MCF `v1.1.0` / SHA `5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`.
- TriView implementation baseline: `train/road-to-1.0` / SHA `17f1b11a36e09463d6ad9b3fdb0be0fc337c2f99`.
- Read-only only: no writes below `.mcf`, no mission execution, no gate approval, no GitHub mutation.
- MCF remains the source of truth; TriView stores only derived/transient projections in R2.
- No new third-party runtime dependency.
- No credential persistence; authentication headers are caller-supplied transient values only.
- Invalid canonical JSON must fail closed as `INVALID`, never be treated as valid MCF authority.

---

### Task 1: Canonical repository inspection

**Files:**
- Create: `src/triview_workspace/mcf_bridge.py`
- Test: `tests/test_mcf_bridge.py`

**Interfaces:**
- Produces: `McfArtifactProjection`, `McfRepositorySnapshot`, `McfRepositoryInspector.inspect(root: Path) -> McfRepositorySnapshot`.
- `McfRepositorySnapshot` exposes `root`, `is_mcf_project`, `project_id`, `methodology_version`, and projections for `pip`, `prr`, and `alignment`.

- [ ] **Step 1: Write failing repository inspection tests**

```python
from pathlib import Path
import json

from triview_workspace.mcf_bridge import McfRepositoryInspector


def test_inspector_reads_latest_canonical_project_artifacts(tmp_path: Path) -> None:
    intent = tmp_path / ".mcf" / "intent"
    reality = tmp_path / ".mcf" / "reality"
    receipts = tmp_path / ".mcf" / "receipts"
    intent.mkdir(parents=True)
    reality.mkdir(parents=True)
    receipts.mkdir(parents=True)
    (intent / "pip-r1.json").write_text(json.dumps({
        "artifactType": "PROJECT_INTENT_PACKAGE",
        "schemaVersion": "1.0",
        "projectId": "triview",
        "revisionId": "r1",
        "createdAt": "2026-08-16T10:00:00+00:00",
        "methodologyPin": {"version": "v1.1.0", "immutableRef": "5d79f488"},
    }), encoding="utf-8")
    (reality / "prr-r1.json").write_text(json.dumps({
        "artifactType": "PROJECT_REALITY_REPORT",
        "schemaVersion": "1.0",
        "projectId": "triview",
        "revisionId": "r1",
        "createdAt": "2026-08-16T10:05:00+00:00",
        "methodologyPin": {"version": "v1.1.0", "immutableRef": "5d79f488"},
    }), encoding="utf-8")
    (receipts / "intent-alignment-a1.json").write_text(json.dumps({
        "artifactType": "INTENT_ALIGNMENT_RECEIPT",
        "schemaVersion": "1.0",
        "receiptId": "a1",
        "projectId": "triview",
        "decision": "PASS",
        "confirmedAt": "2026-08-16T10:10:00+00:00",
    }), encoding="utf-8")

    snapshot = McfRepositoryInspector().inspect(tmp_path)

    assert snapshot.is_mcf_project is True
    assert snapshot.project_id == "triview"
    assert snapshot.methodology_version == "v1.1.0"
    assert snapshot.pip.status == "VALID"
    assert snapshot.prr.status == "VALID"
    assert snapshot.alignment.status == "VALID"
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `pytest -q tests/test_mcf_bridge.py::test_inspector_reads_latest_canonical_project_artifacts`
Expected: FAIL because `triview_workspace.mcf_bridge` does not exist.

- [ ] **Step 3: Implement minimal read-only artifact discovery**

Implement dataclasses and an inspector that reads only `.mcf/intent/pip-*.json`, `.mcf/reality/prr-*.json`, and `.mcf/receipts/intent-alignment-*.json`; validate expected artifact type/schema/project identity and choose the newest candidate by canonical timestamp field, falling back to deterministic path order only when no valid timestamp exists.

- [ ] **Step 4: Add invalid/non-MCF behavior tests**

```python
def test_inspector_marks_malformed_canonical_artifact_invalid(tmp_path: Path) -> None:
    intent = tmp_path / ".mcf" / "intent"
    intent.mkdir(parents=True)
    (intent / "pip-bad.json").write_text("{", encoding="utf-8")
    snapshot = McfRepositoryInspector().inspect(tmp_path)
    assert snapshot.is_mcf_project is True
    assert snapshot.pip.status == "INVALID"
    assert snapshot.project_id is None


def test_inspector_reports_plain_repository_as_not_mcf(tmp_path: Path) -> None:
    snapshot = McfRepositoryInspector().inspect(tmp_path)
    assert snapshot.is_mcf_project is False
    assert snapshot.pip.status == "ABSENT"
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `pytest -q tests/test_mcf_bridge.py`
Expected: PASS.

### Task 2: Read-only Mission Runtime client

**Files:**
- Modify: `src/triview_workspace/mcf_bridge.py`
- Modify: `tests/test_mcf_bridge.py`

**Interfaces:**
- Produces: `McfRuntimeClient(base_url: str, headers: Mapping[str, str] | None = None, timeout: float = 5.0)`.
- Methods: `mission(mission_id)`, `timeline(mission_id)`, `observability(mission_id)`, all HTTP GET only.

- [ ] **Step 1: Write failing runtime client test**

Use an injected opener callable to capture `urllib.request.Request` and return JSON bytes. Assert the request method is `GET`, the URL is `/v1/mcf/missions/<quoted-id>`, and transient headers are attached but never written to disk.

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_mcf_bridge.py::test_runtime_client_uses_get_only`
Expected: FAIL because `McfRuntimeClient` is absent.

- [ ] **Step 3: Implement minimal GET-only client**

Use `urllib.request.Request(method="GET")`, `urllib.request.urlopen`, JSON decoding, URL quoting and explicit validation that base URL is HTTP(S). Do not expose POST/PUT/PATCH/DELETE methods.

- [ ] **Step 4: Verify GREEN**

Run: `pytest -q tests/test_mcf_bridge.py`
Expected: PASS.

### Task 3: Derived bridge snapshot

**Files:**
- Modify: `src/triview_workspace/mcf_bridge.py`
- Modify: `tests/test_mcf_bridge.py`

**Interfaces:**
- Produces: `McfBridgeSnapshot` and `McfBridge.inspect(root: Path, mission_id: str | None = None) -> McfBridgeSnapshot`.
- The bridge combines repository facts with optional runtime projections without copying or redefining MCF authority rules.

- [ ] **Step 1: Write failing bridge composition test**

Create canonical PIP/PRR fixtures plus a fake runtime client returning a mission, timeline and observability payload. Assert the returned snapshot carries the canonical `project_id`, methodology version, mission payload and source labels `REPOSITORY_CANONICAL` / `MCF_RUNTIME_READ_ONLY`.

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_mcf_bridge.py::test_bridge_combines_repository_and_runtime_read_only`
Expected: FAIL because `McfBridge` is absent.

- [ ] **Step 3: Implement minimal composition**

The bridge must not infer a new mission authority state. It only projects canonical repository artifact identities and copies runtime response payloads when a mission id and runtime client are supplied.

- [ ] **Step 4: Verify GREEN and full regression**

Run: `pytest -q tests/test_mcf_bridge.py`
Expected: PASS.

Run: `python -m compileall -q src tests && pytest -q`
Expected: all repository tests PASS.

### Task 4: Documentation and boundary check

**Files:**
- Create: `docs/architecture/MCF_INTEGRATION_R2.md`

**Interfaces:**
- Documents the read-only trust boundary and future R3/R4 extension points.

- [ ] **Step 1: Document source-of-truth boundary**

Document that `.mcf` artifacts and MCF runtime remain authoritative, TriView projections are derived, credentials are transient, and R2 contains no execution/gate/write gateway.

- [ ] **Step 2: Run documentation/full validation**

Run: `python -m compileall -q src tests && pytest -q`
Expected: PASS.

- [ ] **Step 3: Review branch diff**

Confirm changed paths are limited to the plan, bridge module, focused tests and R2 architecture document. No existing workspace persistence schema or GUI behavior should be modified in R2.
