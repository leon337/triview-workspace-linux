#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE_ID="${1:?CANDIDATE_ID ausente}"
APP_ROOT="${2:?APP_ROOT ausente}"
DATA_ROOT="${3:?DATA_ROOT ausente}"
STATE_ROOT="${4:?STATE_ROOT ausente}"
MODULE="${5:?MODULE ausente}"
UPDATE_REF="${6:?UPDATE_REF ausente}"
REPO="${7:?REPO ausente}"
CURRENT="$APP_ROOT/current"
APP_STATE="$STATE_ROOT/triview-workspace"

mkdir -p "$APP_STATE/updates"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$APP_STATE/updates/update-$STAMP.log"
LIFECYCLE_LOCK="$APP_STATE/lifecycle.lock"

if ! command -v flock >/dev/null 2>&1; then
  printf 'ERRO: flock não está disponível para serializar o ciclo de vida.\n' \
    | tee "$LOG" >&2
  exit 1
fi

exec 8>"$LIFECYCLE_LOCK"
if ! flock -n 8; then
  printf 'ERRO: outra operação de instalação, atualização ou rollback já está em execução.\n' \
    | tee "$LOG" >&2
  exit 2
fi

CURRENT_TARGET="$(readlink -f "$CURRENT" 2>/dev/null || true)"
if [[ -z "$CURRENT_TARGET" || ! -d "$CURRENT_TARGET" ]]; then
  printf 'ERRO: candidato ativo ausente ou inválido: %s\n' "$CURRENT" | tee "$LOG" >&2
  exit 1
fi

RUNNING_PIDS="$(python3 - "$APP_ROOT" "$MODULE" <<'PY'
from __future__ import annotations

import pathlib
import sys

app_root = pathlib.Path(sys.argv[1]).expanduser().resolve()
expected_module = sys.argv[2]
releases = app_root / "releases"
for environ_path in pathlib.Path("/proc").glob("[0-9]*/environ"):
    try:
        raw = environ_path.read_bytes()
    except (OSError, PermissionError):
        continue
    entries = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        entries[key.decode(errors="replace")] = value.decode(errors="replace")
    if entries.get("TRIVIEW_RUNTIME_MODULE") != expected_module:
        continue
    runtime_root = entries.get("TRIVIEW_RUNTIME_ROOT")
    if not runtime_root:
        continue
    try:
        pathlib.Path(runtime_root).expanduser().resolve().relative_to(releases)
    except (OSError, ValueError):
        continue
    print(environ_path.parent.name)
PY
)"

if [[ -n "$RUNNING_PIDS" ]]; then
  message="Feche o TriView Workspace antes de atualizar. Instância ativa: $RUNNING_PIDS"
  printf 'ERRO: %s\n' "$message" | tee "$LOG" >&2
  if command -v zenity >/dev/null 2>&1; then
    zenity --error --title='TriView ainda está aberto' --text="$message" || true
  fi
  printf '\nPressione ENTER para fechar.\n'
  read -r _ || true
  exit 2
fi

INSTALLER="$CURRENT_TARGET/scripts/install-module-candidate.sh"
if [[ ! -f "$INSTALLER" ]]; then
  printf 'ERRO: instalador não encontrado: %s\n' "$INSTALLER" | tee "$LOG" >&2
  exit 1
fi

{
  printf 'TriView Workspace — Atualização controlada\n'
  printf 'Candidato: %s\n' "$CANDIDATE_ID"
  printf 'Repositório: %s\n' "$REPO"
  printf 'Referência de atualização: %s\n' "$UPDATE_REF"
  printf 'Runtime atual: %s\n' "$CURRENT_TARGET"
  printf 'Bloqueio de ciclo de vida: %s\n' "$LIFECYCLE_LOCK"
  printf 'Início: %s\n\n' "$(date --iso-8601=seconds)"
} | tee "$LOG"

set +e
TRIVIEW_REPO="$REPO" \
TRIVIEW_LIFECYCLE_LOCK_HELD=1 \
bash "$INSTALLER" \
  "$CANDIDATE_ID" "$UPDATE_REF" "$MODULE" "$UPDATE_REF" 2>&1 | tee -a "$LOG"
status="${PIPESTATUS[0]}"
set -e

printf '\nFim: %s\nStatus: %s\nLog: %s\n' \
  "$(date --iso-8601=seconds)" "$status" "$LOG" | tee -a "$LOG"

if command -v zenity >/dev/null 2>&1; then
  if [[ "$status" -eq 0 ]]; then
    zenity --info --title='TriView atualizado' \
      --text="Atualização concluída.\n\nLog: $LOG" || true
  else
    zenity --error --title='Falha na atualização do TriView' \
      --text="A atualização falhou com código $status.\n\nLog: $LOG" || true
  fi
fi

printf '\nPressione ENTER para fechar.\n'
read -r _ || true
exit "$status"
