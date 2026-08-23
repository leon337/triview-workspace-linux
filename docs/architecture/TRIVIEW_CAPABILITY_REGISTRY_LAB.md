# TriView × MCF Capability Registry — read-only lab

## Status

`HEADLESS_PASS__FOCUSED_MINT_X11_PASS__REAL_MCF_E2E_PASS`

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

The complete isolated suite passed with `419 passed, 2 skipped`. Focused tests
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

## Focused Linux Mint/X11 evidence

The Capability Registry Cockpit smoke ran locally on the exact source content in
`c86ee97666bb57ff03f7a3e8b3eaa63c2e668ab5`, on Linux Mint 22.3 Zena with the
real XFCE X11 session (`DISPLAY=:0.0`). This is focused evidence for the new
read-only panel; it is not a claim that the full product-candidate R7 matrix ran.

The first physical attempt exposed a real layout defect: the seventh card was
below the 980×720 viewport and the body did not scroll. The fix puts Capability
Registry beside Project in the first row and makes the complete body vertically
scrollable. The repeated gate proved:

- a normal, viewable 980×720 X11 window rendered the Capability Registry card;
- `IMPLEMENTED ≠ CONNECTED ≠ AUTHORIZED ≠ VERIFIED`, individual entries,
  required gates, blockers, and `EVIDENCE_ONLY_NO_ACTIONS` were visible;
- real wheel input scrolled to Context Receipt and Timeline;
- `Atualizar` performed another repository-only read without a runtime URL or
  either MCF token in the process environment;
- the aggregate TriView `.mcf` digest stayed
  `c2ebe435f154fcf0081f804e0ae2f38dff23471bb98bdc889173aa6b38d4eb54`;
- the aggregate MCF Capability YAML digest stayed
  `6afce8a4b5066c841e0fdd45f7dc16ae7f17d7ea410e110bcce06c9c4db32022`;
- activating `Fechar` removed the X11 window and the driver exited with status 0.

Local screenshot evidence was captured without credentials, fingerprinted, and
then removed as temporary data before branch publication:

- `/tmp/triview-capability-physical.VbNKCH/capability-cockpit-after-refresh-settled.png`
  (`sha256:b75b3ee2236b733b5d91ed10f69ea2c2e984cfc718c72590038cc8f0fa35eb80`);
- `/tmp/triview-capability-physical.VbNKCH/capability-cockpit-scrolled.png`
  (`sha256:e3d66fb544c1493d079613e5f426c63acc22a9477aaceef876e950c4f026a155`).

## Real MCF endpoint evidence

The real local cross-repository E2E was repeated from TriView checkpoint
`4758ba52b6ecdcec753edbadaa1d8bafd0a3a8cf` against remote MCF checkpoint
`c7455fcfdb51cd1d36883dda900c5ecbf2835ae4`, which contains the functional
public-projection fix in
`d03f1b3a8f4612414decc18238b437f103c28c7d`. A disposable test-mode server bound
only to `127.0.0.1:3112`, used an allowlisted Registry configuration and a
dedicated synthetic context-read token. Its global rate-limit guard used a
migrated disposable PostgreSQL container bound only to `127.0.0.1:65432`.
Both processes and ports were removed immediately afterward.

The first run against the preceding MCF SHA failed closed because its public
`sources` objects leaked the non-contract field `resolved_path`. TriView rejected
that response as `CAPABILITY_SNAPSHOT_SOURCE_UNKNOWN_FIELDS` and visibly retained
`REPOSITORY_FALLBACK`. MCF then corrected its public projection and added an
anti-`resolved_path` regression test; TriView's strict parser did not need to be
weakened.

On the corrected checkpoint, the real `load_cockpit_model` path proved:

- the final traced invocation contained exactly one recovery GET and one
  capability GET, both HTTP 200, and no mutating request;
- Capability Registry mode was `MCF_RUNTIME_GET`, status was `VALID`, and finding
  was `EVIDENCE_ONLY_NO_ACTIONS`;
- the server-side `project_id=triview-workspace-linux` filter returned exactly
  `cloud.workspace.g2a.read`, `mcf.capability.registry.read`, and
  `mcf.context.recovery.read`; the G2-B write entry was absent;
- the four lifecycle dimensions, gates, and the honest G2-A blockers reached the
  Cockpit model;
- neither the synthetic token nor an authorization credential reached the model,
  representation, repository, or evidence output;
- the aggregate MCF Registry/Capability/schema digest remained
  `4391619883270f068cf65d5d51e1e5037d8ab878084a057418f79552f1472a5c`;
- the aggregate TriView `.mcf` digest at the tested checkpoint remained
  `fa0a8a7f40df919925d5d84837841bad93b201f044b444d2741d33c81c7ebd8f`;
- both worktrees remained clean at their tested checkpoints, ports 3112 and
  65432 were closed, and the disposable database container was absent.

The complete headless suite was then repeated with an explicit UTC test timezone
and no display variables: `419 passed, 2 skipped`. Compile and shell syntax gates
also passed. The two skips remain the separately gated X11 integration cases.

## Remaining gates

- The focused Capability Registry smoke is PASS. The broader product-candidate R7
  matrix remains a separate release gate and is not claimed by this lab evidence.
- The two dedicated X11 integration tests remain skipped in the normal headless
  suite; this focused physical observation does not relabel them.
- Publishing this lab branch does not authorize merge, deploy, release, or
  promotion.
