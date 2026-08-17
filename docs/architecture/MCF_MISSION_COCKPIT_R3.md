# MCF Mission Cockpit — R3

## Status

R3 adds a read-only visual projection of MCF state to TriView. It depends on the R2 bridge and does not change the MCF source-of-truth model.

Baseline:

- TriView parent: `feat/triview-mcf-bridge-r2@f8e7a4fa99e833f3779830f5537ac4fcfb152483`
- MCF contract/runtime: stable `v1.1.0@5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`

## User entry point

The effective `triview_workspace.gui.WorkspaceWindow` installs one header action:

```text
MCF
```

Opening it creates `McfCockpitDialog`. The dialog exposes only `Atualizar` and `Fechar`; it has no execute, approve, reject, edit or persist controls.

## Sections

### PROJECT

Derived from the R2 repository inspector:

- repository root;
- whether `.mcf` is present;
- `projectId`;
- pinned methodology version;
- PIP status/revision;
- PRR status/revision;
- intent-alignment status/decision;
- repository consistency findings.

### MISSION

Shown only when complete runtime context is configured:

- mission id and title;
- mission state;
- current phase;
- current agent;
- risk class;
- MCF project entry mode.

The fields come from the documented MCF v1.1 mission response and observability projection. Missing fields are rendered as `N/A`, not inferred.

### AUTHORITY

R3 presents, but does not exercise, authority:

- count of `ACTIVE` standing authorizations already present in the mission contract;
- latest `GATE_REQUIRED`, `GATE_APPROVED` or `GATE_REJECTED` timeline event;
- runtime blocked flag.

No button in R3 can grant authorization or resolve a HUMAN_GATE.

### CONTINUITY

R3 shows only the canonical `continuityCheckpointRef` already supplied by the mission contract:

- checkpoint path;
- checkpoint commit SHA.

`resumeRoute` is intentionally displayed as `NÃO PROJETADA NO R3`. Route derivation and reconcile/recover visualization belong to R5.

### TIMELINE

The dialog renders at most the 12 newest runtime events, newest first. It presents event type, timestamp, agent, phase and a small summary based only on known payload fields.

## Ephemeral configuration contract

R3 intentionally does not create a persistent project↔workspace binding. That responsibility belongs to R4.

The process may supply:

```text
TRIVIEW_MCF_PROJECT_ROOT
TRIVIEW_MCF_MISSION_ID
TRIVIEW_MCF_RUNTIME_URL
TRIVIEW_MCF_SESSION_TOKEN
```

Rules:

1. `TRIVIEW_MCF_PROJECT_ROOT` defaults to the process current working directory when absent.
2. Runtime projection is enabled only when mission id, runtime URL and session token are all present.
3. Incomplete runtime configuration falls back to repository-only projection instead of issuing an unauthenticated request.
4. `TRIVIEW_MCF_SESSION_TOKEN` is held only in the ephemeral `McfCockpitContext` with `repr=False`.
5. The token is used only to build an in-memory `Authorization: Bearer ...` header for the existing R2 GET-only runtime client.
6. The token is never copied to `McfCockpitModel`, Tk labels, runtime observability, workspace JSON, Hub documents or architecture artifacts.
7. Error text is redacted against the in-memory token before it can be rendered.

## Authority boundary

MCF remains authoritative for:

- PIP and PRR;
- mission state;
- phases and agents;
- HUMAN_GATE events;
- standing authorizations;
- checkpoint references;
- runtime events and observability.

TriView R3 owns only:

- layout of the read-only projection;
- ephemeral selection of the process-provided MCF context;
- refresh of the projection;
- rendering of missing/invalid data without inventing facts.

## Explicit non-goals

R3 does not:

- write any file under `.mcf`;
- execute a skill or phase;
- create or mutate missions;
- approve or reject a gate;
- grant or revoke standing authorization;
- persist session credentials;
- modify `WorkspaceSpec`, `LayoutSpec` or Workspace Hub schema;
- bind a project permanently to a TriView workspace (R4);
- calculate `FAST_RESUME`, `RECONCILE` or `RECOVER_MCF_PROJECT` (R5).
