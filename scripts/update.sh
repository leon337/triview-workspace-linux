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
WRAPPER_SNAPSHOT=""

cleanup() {
  [[ -n "$WRAPPER_SNAPSHOT" ]] && rm -f "$WRAPPER_SNAPSHOT"
}
trap cleanup EXIT

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

# O núcleo legado instala a si próprio em updater/update.sh. Quando o
# controlador já está nesse caminho, o arquivo pode ser sobrescrito durante
# a execução. O snapshot preserva os bytes autorizados antes de chamar o núcleo.
if ((dry_run == 0)); then
  WRAPPER_SNAPSHOT="$(mktemp)"
  cp -a "$SCRIPT_PATH" "$WRAPPER_SNAPSHOT"
fi

set +e
bash "$CORE_SCRIPT" "${forwarded_args[@]}"
status=$?
set -e

((status == 0)) || exit "$status"
((dry_run == 0)) || exit 0

mkdir -p "$UPDATER_ROOT"
if [[ "$CORE_SCRIPT" != "$TARGET_CORE" ]] && ! cmp -s "$CORE_SCRIPT" "$TARGET_CORE"; then
  cp -a "$CORE_SCRIPT" "$TARGET_CORE"
fi
if ! cmp -s "$WRAPPER_SNAPSHOT" "$TARGET_WRAPPER"; then
  cp -a "$WRAPPER_SNAPSHOT" "$TARGET_WRAPPER"
fi
chmod +x "$TARGET_WRAPPER" "$TARGET_CORE"
