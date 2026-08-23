# TriView × MCF Context Fabric — cross-repository lab evidence

## Result

`PASS__LAB_ONLY__PHYSICAL_NOT_RUN`

Observed at `2026-08-23T03:36:43-03:00` on loopback only. No push,
deployment, production configuration, paid API, or external AI provider was used.

## Tested baselines

- TriView consumer/product SHA:
  `9796ac98655dc545a48f1609fba6f8c09a10f318`;
- MCF endpoint SHA: `d5bbcfd79e41e5604071013a8c9ec6aa1b861591`;
- MCF endpoint: `GET /v1/mcf/context/recovery`;
- query: `project_hint=triview-workspace-linux` and
  `requires_current_operational_state=false`;
- transport: `127.0.0.1:3110` with a synthetic, process-only Context Fabric
  read token;
- MCF database dependency: local laboratory PostgreSQL supplied by the
  authorized test environment.

The MCF worktree also contained unrelated capability-contract work owned by a
parallel team. It was not edited by this run. This is therefore integration
evidence for the committed endpoint baseline, not a clean-tree release
qualification.

## Observed request boundary

The real `load_cockpit_model()` path was executed while wrapping Python's URL
opener in memory. The wrapper observed exactly one outbound request:

```text
method = GET
path = /v1/mcf/context/recovery
project_hint = triview-workspace-linux
requires_current_operational_state = false
credential header = x-mcf-context-token
Authorization header present = false
request count = 1
```

The MCF server independently recorded:

```text
method = GET
route = /v1/mcf/context/recovery
statusCode = 200
outcome = SUCCESS
correlationId = a806de6d-fb8f-4549-b009-ace9e78e487e
```

No mission id or mission bearer token was supplied. TriView reported
`mission_runtime_enabled=false`, `mission_status=NÃO CONFIGURADA`, and
`context_runtime_enabled=true`. Consequently, no mission, gate, authorization,
callback, or other material endpoint was requested.

## Receipt projection

The strict TriView parser accepted the real MCF response with these sanitized
facts:

```text
context_fabric_status = VALID
context_mode = MCF_RUNTIME_GET
recovery_state = RECOVERED
receipt_id = context-recovery-0c7b3e16-0f54-4c5e-acc7-a897ca26acc0
freshness = DURABLE, SNAPSHOT
live_verification_required = NÃO
sources = 2
claims = 17
warning = N/A
```

Claim values were validated but were not copied into the Cockpit model. Current
operational verification was intentionally not requested, so this result does
not assert fresh VPS/provider state.

## Non-mutation and secret boundary

The Registry and Capsule were read before and after the request and remained
byte-for-byte identical:

```text
Capsule SHA-256 = 833de214ddaa7c7ba9fc493f900202488841338a4129fe8a8f9ba019d0e33a29
Registry SHA-256 = 3a42fc56b3dfd661de5e2a3977efb31c74f7b5f0ed346418bfd886f4a32897a8
```

The synthetic read token appeared in neither `McfCockpitContext.__repr__()` nor
the returned Cockpit model. Its value is deliberately absent from this evidence.
Workspace bindings continued to persist only non-secret repository, project,
mission-reference, and runtime-URL fields.

## Remaining gate

This E2E proves the repository/HTTP/parser/Cockpit contract in a local lab. The
physical Mission Cockpit layout and Linux Mint/X11 acceptance matrix remain
`NOT_RUN`; the two dedicated X11 tests remain skipped and must not be reported as
PASS.
