#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
SOURCE_REF="${TRIVIEW_CANDIDATE_REF:-}"

if [[ -z "$SOURCE_REF" ]] && command -v git >/dev/null 2>&1; then
  if git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    SOURCE_REF="$(git -C "$REPO_ROOT" rev-parse HEAD)"
  fi
fi

if [[ ! "$SOURCE_REF" =~ ^[0-9a-fA-F]{40}$ ]]; then
  printf '%s\n' \
    'Não foi possível fixar o candidato em um commit imutável.' \
    'Execute este script dentro do clone Git ou informe:' \
    'TRIVIEW_CANDIDATE_REF=<SHA completo> bash scripts/install-train-candidate.sh' >&2
  exit 2
fi

exec bash "$SCRIPT_DIR/install-module-candidate.sh" \
  "RC4-1.0.0A1" \
  "$SOURCE_REF" \
  "triview_workspace.gui"
