#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
CORE_SCRIPT="$SCRIPT_DIR/update-core.sh"
APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
CHANNEL_FILE="$APP_ROOT/UPDATE_CHANNEL"
UPDATER_ROOT="$APP_ROOT/updater"

[[ -f "$CORE_SCRIPT" ]] || {
  printf '[TriView Updater] ERRO: núcleo do atualizador ausente: %s\n' "$CORE_SCRIPT" >&2
  exit 1
}

explicit_cli_channel=0
dry_run=0
for argument in "$@"; do
  case "$argument" in
    --stable|--testing) explicit_cli_channel=1 ;;
    --dry-run) dry_run=1 ;;
  esac
done

forwarded_args=("$@")
if ((explicit_cli_channel == 0)) \
  && [[ -z "${TRIVIEW_UPDATE_CHANNEL:-}" ]] \
  && [[ ! -f "$CHANNEL_FILE" ]]; then
  forwarded_args=(--stable "${forwarded_args[@]}")
fi

set +e
bash "$CORE_SCRIPT" "${forwarded_args[@]}"
status=$?
set -e

((status == 0)) || exit "$status"
((dry_run == 0)) || exit 0

# O núcleo legado instala a si próprio como update.sh. Reaplicamos o
# controlador e mantemos o núcleo ao lado dele para que execuções futuras
# preservem a seleção segura de canal.
mkdir -p "$UPDATER_ROOT"
cp -a "$CORE_SCRIPT" "$UPDATER_ROOT/update-core.sh"
cp -a "$SCRIPT_PATH" "$UPDATER_ROOT/update.sh"
chmod +x "$UPDATER_ROOT/update.sh" "$UPDATER_ROOT/update-core.sh"
