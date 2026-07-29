#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
CORE_SCRIPT="$SCRIPT_DIR/update-core.sh"
APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
CHANNEL_FILE="$APP_ROOT/UPDATE_CHANNEL"
UPDATER_ROOT="$APP_ROOT/updater"
TARGET_WRAPPER="$UPDATER_ROOT/update.sh"
TARGET_CORE="$UPDATER_ROOT/update-core.sh"

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
# preservem a seleção segura de canal. Comparações de caminho e conteúdo
# tornam a operação idempotente quando já estamos no diretório persistente.
mkdir -p "$UPDATER_ROOT"
if [[ "$CORE_SCRIPT" != "$TARGET_CORE" ]] && ! cmp -s "$CORE_SCRIPT" "$TARGET_CORE"; then
  cp -a "$CORE_SCRIPT" "$TARGET_CORE"
fi
if [[ "$SCRIPT_PATH" != "$TARGET_WRAPPER" ]] && ! cmp -s "$SCRIPT_PATH" "$TARGET_WRAPPER"; then
  cp -a "$SCRIPT_PATH" "$TARGET_WRAPPER"
fi
chmod +x "$TARGET_WRAPPER" "$TARGET_CORE"
