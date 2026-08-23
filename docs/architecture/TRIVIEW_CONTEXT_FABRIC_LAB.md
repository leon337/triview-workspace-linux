# TriView × Context Fabric — lab boundary

## Status

`HEADLESS_PASS__PHYSICAL_NOT_RUN`

This branch is an isolated lab integration based on
`origin/release/1.0.0a4@4089eed90a4672f8f68e396f9861e70552b1b115`.
It does not promote or replace the immutable `1.0.0a4` physical candidate and it
does not change `main`.

The TriView consumer is implemented on this isolated branch. Integration against
the real MCF Registry and recovery endpoint remains a separate cross-repository
lab gate.

## Ownership

- MCF owns Project Registry identity, Context Fabric recovery semantics and
  Context Recovery Receipts.
- TriView owns this repository's Project Capsule and a derived, read-only visual
  projection.
- Live operational truth stays with its owning repository or provider.
- A Receipt is evidence only and is never a new source of truth.

## Lab scope

The lab integration may:

- read a bounded MCF Registry entry and this repository's Capsule;
- validate their CF-0/CF-1 shapes and matching `project_id`;
- request an evidence-only Receipt through an explicit MCF GET-only endpoint;
- show recovery state, freshness, provenance and warnings in Mission Cockpit;
- preserve only non-secret TriView binding references.

## Implemented consumer

`McfContextFabricRepositoryReader` safely reads bounded CF-0/CF-1 YAML without
following symlinks, accepting aliases, or tolerating unknown contract fields. It
fails closed and only projects validated Registry/Capsule identity and snapshot
metadata.

`McfRuntimeClient` exposes one new operation:

```text
GET /v1/mcf/context/recovery?project_hint=<project_id>&requires_current_operational_state=false
```

The base URL and bearer token are process inputs. The response parser accepts
only a strict `ContextRecoveryReceipt` with `read_only=true`,
`material_action=false`, and `evidence_only=true`. Claim values are not copied to
the presentation model.

The Mission Cockpit shows the repository projection, Receipt state, freshness,
warnings, and one explicit source mode:

- `MCF_RUNTIME_GET`: a strict Receipt was accepted;
- `REPOSITORY_ONLY`: no runtime recovery was requested;
- `REPOSITORY_FALLBACK`: the GET, project resolution, or Receipt validation failed.

`TRIVIEW_MCF_REGISTRY_ROOT` injects the MCF checkout/root used for Registry
lookup. `TRIVIEW_MCF_RUNTIME_URL` and `TRIVIEW_MCF_SESSION_TOKEN` inject the
read-only runtime connection. The token remains excluded from repr, UI models,
and persisted workspace bindings.

It may not:

- write under `.mcf` at runtime;
- create or execute a mission, continuity route or material action;
- approve a HUMAN_GATE or mutate standing authorization;
- persist tokens, Authorization headers, cookies or Receipt claims as authority;
- turn repository-only fallback into a claim of live verification;
- publish, deploy or promote the release candidate.

## Qualification boundary

The isolated headless suite passed with `403 passed, 2 skipped`. A synthetic local
HTTP server proved the exact GET query, strict Receipt projection, explicit 503
fallback, credential non-persistence, and byte-for-byte preservation of the
Registry and Capsule inputs. The two skips are the dedicated physical X11 cases;
they are not counted as PASS.

These tests prove only the software contract. The physical Linux Mint/X11 matrix,
Mission Cockpit visual smoke, stable update and rollback gates remain `NOT_RUN`
until executed through the renewed R7 runbook on an explicitly qualified product
SHA. No push, deployment, release promotion, or production change is part of this
lab evidence.
