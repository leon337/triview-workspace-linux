# MCF Workspace Binding — R4

## Purpose

R4 gives TriView a persistent association between a TriView workspace and an MCF project context without moving MCF authority into the TriView domain model.

The binding is a **TriView-owned reference**. MCF remains the source of truth for project intent, reality, missions, authority, checkpoints, evidence, events, and continuation state.

## Storage ownership

Bindings are stored separately from the universal workspace catalog:

- workspace catalog: `workspaces.json`
- MCF binding catalog: `mcf-bindings.json`

The default binding path uses the same XDG data root as TriView workspace persistence, under `triview-workspace/mcf-bindings.json`.

R4 does **not** change:

- `WorkspaceSpec`
- `LayoutSpec`
- `WorkspaceCatalog`
- the `workspaces.json` schema version

This separation keeps a normal TriView workspace valid even when no MCF integration is configured.

## Persisted contract

`mcf-bindings.json` uses schema version `1`.

Each binding contains exactly these fields:

```json
{
  "workspace_id": "workspace-a",
  "project_root": "/absolute/path/to/project",
  "project_id": "canonical-mcf-project-id",
  "mission_id": "optional-mission-id",
  "runtime_url": "https://optional-runtime.example"
}
```

`mission_id` and `runtime_url` may be null. No additional binding fields are accepted.

The file never stores:

- session tokens or `Authorization` headers;
- PIP or PRR contents;
- intent-alignment contents;
- mission state or phase state;
- HUMAN_GATE state;
- standing authorization data;
- checkpoint payloads;
- evidence receipts or runtime events.

`TRIVIEW_MCF_SESSION_TOKEN` remains process-only input. It may be used transiently to authenticate read-only runtime queries, but it is not part of `McfWorkspaceBinding` and is never serialized into `mcf-bindings.json`.

## Validation and drift handling

Creating a binding is not a blind path assignment.

`McfWorkspaceBinder.bind()` uses the existing MCF repository inspector to verify that `project_root` is an MCF project and to obtain its canonical `project_id`. TriView persists that observed identity with the reference.

`McfWorkspaceBinder.resolve()` re-inspects the project root each time a persisted binding is resolved. If the root is no longer an MCF project, or if its observed canonical `project_id` differs from the persisted value, resolution fails explicitly with `McfBindingError`.

TriView never silently rewrites a binding to match drifted canonical state.

Malformed binding JSON is quarantined by the TriView binding repository and replaced by an empty binding catalog. This recovery affects only TriView-owned reference metadata; it does not touch the referenced MCF project.

## Mission Cockpit resolution

For a workspace with a persisted binding, the Mission Cockpit uses the binding's:

- project root;
- optional mission id;
- optional runtime URL.

Those non-secret persisted values take precedence over their `TRIVIEW_MCF_*` environment fallbacks for that workspace.

The session token is the exception: it is always read only from current process input and is never supplied by the persisted binding.

For an unbound workspace, the R3 environment/current-directory fallback remains available.

The `MCF` header action resolves `window.workspace.id` at click time, so switching workspaces does not freeze the binding context captured when the application header was created.

## Bind / unbind controls

The Cockpit exposes `Vincular workspace` and `Desvincular workspace` only as operations over the TriView binding catalog.

`Vincular workspace` persists the current non-secret context references after canonical MCF project validation.

`Desvincular workspace` removes only that TriView reference.

Neither operation:

- deletes or changes files under `.mcf`;
- creates, executes, cancels, or mutates an MCF mission;
- approves or rejects a HUMAN_GATE;
- grants or revokes a standing authorization;
- modifies MCF checkpoints, evidence, or event ledgers.

Deleting a binding therefore never deletes or modifies the MCF project it referenced.

## Workspace deletion and orphan bindings

The binding store is intentionally independent from the universal workspace catalog. If a workspace is removed without a binding-cleanup action, its binding can remain as inert TriView metadata.

Such an orphan has no authority and cannot affect the MCF project. Detecting or cleaning orphan bindings is TriView housekeeping and must not be interpreted as canonical MCF reconciliation.

## Atomicity and recovery

Binding writes use the same durability pattern expected from TriView persistence:

1. serialize a complete replacement payload;
2. write to a temporary file in the target directory;
3. flush and `fsync` the temporary file;
4. replace the destination atomically with `os.replace`.

The binding store maintains one current binding per `workspace_id`.

## Boundary to R5

R4 establishes persistent identity and context linkage only.

It does not derive or persist the continuation decision:

- `FAST_RESUME`
- `RECONCILE`
- `RECOVER_MCF_PROJECT`

R5 owns the visual continuity/reconciliation projection and must derive that route from canonical MCF/repository evidence rather than from a value invented or cached by the R4 binding store.
