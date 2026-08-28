# MCF Integration R2 — Read-Only Bridge

## Status

`IMPLEMENTED_ON_FEATURE_BRANCH`

TriView baseline: `train/road-to-1.0@17f1b11a36e09463d6ad9b3fdb0be0fc337c2f99`  
MCF compatibility baseline: `v1.1.0@5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`

## Purpose

R2 introduces the first native integration boundary between TriView Workspace and the current MCF without turning TriView into a second MCF runtime.

The integration is intentionally read-only. It provides derived projections that future UI layers can consume while canonical MCF artifacts and runtime services remain authoritative.

## Source-of-truth rule

```text
MCF repository / .mcf artifacts / MCF runtime
                   │
                   │ authoritative
                   ▼
          TriView mcf_bridge.py
                   │
                   │ derived read-only projection
                   ▼
          future Mission Cockpit UI
```

TriView MUST NOT treat an `McfRepositorySnapshot`, `McfRuntimeProjection`, or `McfBridgeSnapshot` as independent authority.

## R2 components

### `McfRepositoryInspector`

Reads only the canonical artifact families currently needed by the cockpit bootstrap:

- `.mcf/intent/pip-*.json`;
- `.mcf/reality/prr-*.json`;
- `.mcf/receipts/intent-alignment-*.json`.

It produces small projections containing artifact identity, project identity, methodology pin and alignment decision. It does not edit files, calculate new MCF authority, create artifacts, or perform migrations.

Recognition status is deliberately limited to the bridge boundary:

- `ABSENT`: no candidate file was found;
- `VALID`: the candidate is readable and carries the expected R2 identity fields;
- `INVALID`: the candidate cannot safely be projected.

`VALID` in this module does not replace canonical MCF schema/digest/runtime validation.

If readable canonical artifacts disagree about `projectId` or methodology version, the aggregate project identity/version fails closed to `None` and exposes a consistency error.

### `McfRuntimeClient`

Exposes only these authenticated read paths from the MCF v1.1 runtime:

```text
GET /v1/mcf/missions/:missionId
GET /v1/mcf/missions/:missionId/timeline
GET /v1/mcf/observability/missions/:missionId
```

There is no POST, PUT, PATCH or DELETE method in the R2 client.

Authentication headers are supplied by the caller and live only in memory. R2 does not write cookies, tokens or credentials to TriView workspace JSON, runtime state, logs or plugin manifests.

### `McfBridge`

Combines the repository projection with optional runtime GET responses. It does not derive a new mission state machine and does not decide MCF authority. The returned runtime payload remains labeled `MCF_RUNTIME_READ_ONLY`.

## Explicitly out of scope

R2 does not:

- execute a mission phase or skill;
- create a mission;
- approve, reject or consume a HUMAN_GATE;
- create or mutate Standing Authorization;
- write PIP, PRR, receipts or checkpoints;
- reconcile canonical Git state by itself;
- write to GitHub;
- change `WorkspaceSpec`, `LayoutSpec`, `PanelSpec` or workspace persistence schema;
- persist MCF credentials;
- add Mission Cockpit UI.

## Failure behavior

The bridge fails closed at the projection boundary:

- malformed canonical JSON is `INVALID`;
- unrecognized schema versions are `INVALID`;
- conflicting project identities suppress aggregate `project_id`;
- conflicting methodology versions suppress aggregate `methodology_version`;
- runtime URLs must be HTTP(S);
- an empty mission id is rejected;
- a mission id cannot be resolved without an explicitly configured runtime reader;
- non-object runtime responses are rejected.

## Security and privacy boundary

R2 performs no automatic discovery of browser session cookies and no credential harvesting. A caller that later integrates authenticated runtime access must inject transient headers through a trusted boundary.

Repository inspection is limited to known `.mcf` canonical path families beneath the selected project root. The bridge never writes below `.mcf`.

## Extension points

### R3 — Mission Cockpit

R3 may render `McfBridgeSnapshot` as project, mission, authority and continuity UI. The UI must continue to label derived state and must not add hidden write actions.

### R4 — Workspace binding

R4 may introduce a TriView-owned binding that links a local workspace to a project/mission reference. Such binding is navigation metadata only and must not duplicate PIP, PRR, Mission Contract or checkpoint authority.

### Later governed actions

Any write/action layer must call existing MCF-governed interfaces rather than write canonical artifacts directly. HUMAN_GATE, permissions, standing authorizations and evidence rules remain MCF responsibilities.

## Qualification evidence

TDD RED evidence for the contract commit `d05c885f41eac1a8027bc3b577472c594cde399c`:

```text
ModuleNotFoundError: No module named 'triview_workspace.mcf_bridge'
```

Initial GREEN implementation commit: `b5ffdf0ff50c91072c7baf02021df4f1c76327fc`.

GitHub Actions CI run `32004517751` passed:

- install: PASS;
- compile: PASS;
- shell validation: PASS;
- pytest suite: PASS;
- X11 wheel integration: PASS;
- XTEST device integration: PASS;
- Xephyr containment integration: PASS.
