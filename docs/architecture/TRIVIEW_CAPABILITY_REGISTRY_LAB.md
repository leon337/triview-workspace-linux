# TriView × MCF Capability Registry — read-only lab

## Status

`HEADLESS_PASS__REAL_ENDPOINT_E2E_PENDING__PHYSICAL_NOT_RUN`

This isolated TriView branch is based on
`origin/release/1.0.0a4@553cce592a130ff08b9c5f828c2e7e5f37b27435`.
It consumes Capability Registry evidence without becoming a capability provider,
authority service, connection manager, or executor.

## Read boundary

The runtime client exposes exactly this additional operation:

```text
GET /v1/mcf/context/capabilities?project_id=<canonical_project_id>
```

It reuses the dedicated `TRIVIEW_MCF_CONTEXT_READ_TOKEN` process input and sends
it only as `x-mcf-context-token`. It does not reuse the mission bearer token. The
base URL remains `TRIVIEW_MCF_RUNTIME_URL`.

The accepted snapshot must have exactly these root fields:

```text
schema_version = 1
retrieved_at = RFC 3339 date-time
project_id = stable id or null
read_only = true
evidence_only = true
entries = bounded Capability Registry entries
sources = bounded provenance records
```

Unknown fields, invalid enums, conflicting allowed/prohibited operations,
duplicate capability ids, unsafe dates, invalid project filtering, and broken
lifecycle invariants fail closed.

## State model shown by the Cockpit

The Capability Registry card displays this inequality explicitly:

```text
IMPLEMENTED ≠ CONNECTED ≠ AUTHORIZED ≠ VERIFIED
```

| Dimension | What it says | What it does not say |
| --- | --- | --- |
| Implementation | Declared code exists or is implemented | A transport is connected |
| Connection | A transport is connected now | Use is authorized |
| Authorization | Governance allows the capability | Runtime evidence is current |
| Verification | Evidence is current, historical, or absent | The capability may execute |
| Runtime | Unknown, inactive, active, or blocked | TriView may change that state |

For each project-relevant entry, the card shows the four dimensions plus runtime.
It also lists the required gate and derives visible gaps such as `NOT_CONNECTED`,
`NOT_AUTHORIZED`, `NOT_VERIFIED`, or `RUNTIME_BLOCKED`. These gaps are a visual
summary of validated fields, not a new authority decision.

No capability connect, authorize, verify, revoke, execute, or write button is
added. Existing TriView workspace-binding controls remain separate and continue
to persist only non-secret references.

## Repository fallback

When `TRIVIEW_MCF_REGISTRY_ROOT` points at an MCF checkout, TriView may read
`context/capabilities/*.yaml` as a bounded repository-only fallback. It rejects:

- more than 128 entries;
- an entry larger than 256 KiB;
- aliases, anchors, unsafe tags, symlinks, traversal, or malformed YAML;
- unknown or missing schema fields;
- duplicate ids, operation conflicts, and invalid lifecycle/gate combinations.

The three presentation modes are:

- `MCF_RUNTIME_GET`: a strict remote snapshot was accepted;
- `REPOSITORY_ONLY`: only local YAML was requested;
- `REPOSITORY_FALLBACK`: the remote GET or snapshot failed and local YAML remains
  visibly non-live.

Repository fallback has no `retrieved_at` and is labeled
`REPOSITORY_ONLY_NON_LIVE`. Every canonical entry declares
`freshness=LIVE_REQUIRED`, so local YAML alone never proves current connectivity,
authorization, verification, or provider/VPS state.

## Limits and presentation

The HTTP response remains bounded by the existing 1 MiB runtime-client limit.
The parser accepts at most 128 entries and 128 snapshot sources. The Cockpit shows
at most eight entry rows, reports how many were hidden, and bounds aggregated gate
and blocker text. It never copies credentials or an executable operation into an
action control.

## Headless evidence

The complete isolated suite passed with `418 passed, 2 skipped`. Focused tests
prove:

- strict validation of the canonical entry and snapshot contracts;
- independence of implemented, connected, authorized, verified, and runtime
  states;
- `ACTIVE` and bounded-write gate invariants;
- safe repository filtering and byte-preserving reads;
- GET-only URL/query and dedicated-token handling;
- exact project identity matching;
- explicit repository fallback after timeout, HTTP 503, or invalid evidence;
- a synthetic Cockpit E2E with separate recovery and capability GET requests,
  no `Authorization` header, no POST, no persistence, and unchanged Registry,
  Capsule, and Capability YAML inputs.

## Remaining gates

- Run a cross-repository E2E only after the MCF capability endpoint has a committed
  and authorized lab SHA.
- Run the physical Mission Cockpit visual smoke and Linux Mint/X11 matrix through
  the existing R7 procedure. The two physical tests remain skipped and are not
  PASS.
- Do not push, merge, deploy, publish, or promote this branch as part of the
  present implementation task.
