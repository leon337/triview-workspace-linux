# TriView × Context Fabric — lab boundary

## Status

`IMPLEMENTATION_IN_PROGRESS`

This branch is an isolated lab integration based on
`origin/release/1.0.0a4@4089eed90a4672f8f68e396f9861e70552b1b115`.
It does not promote or replace the immutable `1.0.0a4` physical candidate and it
does not change `main`.

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

It may not:

- write under `.mcf` at runtime;
- create or execute a mission, continuity route or material action;
- approve a HUMAN_GATE or mutate standing authorization;
- persist tokens, Authorization headers, cookies or Receipt claims as authority;
- turn repository-only fallback into a claim of live verification;
- publish, deploy or promote the release candidate.

## Qualification boundary

Headless unit and synthetic end-to-end tests prove only the software contract.
The physical Linux Mint/X11 matrix, Mission Cockpit visual smoke, stable update
and rollback gates remain `NOT_RUN` until executed through the renewed R7
runbook on an explicitly qualified product SHA.
