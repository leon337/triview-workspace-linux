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
CURRENT_TARGET="$(readlink -f "$CURRENT" 2>/dev/null || true)"

mkdir -p "$STATE_ROOT/triview-workspace/updates"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$STATE_ROOT/triview-workspace/updates/update-$STAMP.log"

if [[ -z "$CURRENT_TARGET" || ! -d "$CURRENT_TARGET" ]]; then
  printf 'ERRO: candidato ativo ausente ou inválido: %s\n' "$CURRENT" | tee "$LOG" >&2
  exit 1
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
  printf 'Início: %s\n\n' "$(date --iso-8601=seconds)"
} | tee "$LOG"

set +e
TRIVIEW_REPO="$REPO" bash "$INSTALLER" \
  "$CANDIDATE_ID" \
  "$UPDATE_REF" \
  "$MODULE" \
  "$UPDATE_REF" 2>&1 | tee -a "$LOG"
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
