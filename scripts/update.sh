#!/usr/bin/env bash
set -Eeuo pipefail

EXECUTING_PATH="$(readlink -f "${BASH_SOURCE[0]}")"

# Bash pode ler este arquivo progressivamente. O núcleo legado substitui
# updater/update.sh durante a atualização; por isso o controlador precisa
# continuar a partir de uma cópia imutável antes de chamar o núcleo.
if [[ "${TRIVIEW_UPDATER_CONTROLLER_SNAPSHOT:-0}" != "1" ]]; then
  snapshot="$(mktemp)"
  cp -a "$EXECUTING_PATH" "$snapshot"
  chmod +x "$snapshot"
  export TRIVIEW_UPDATER_CONTROLLER_SNAPSHOT=1
  export TRIVIEW_UPDATER_ORIGINAL_WRAPPER="$EXECUTING_PATH"
  exec bash "$snapshot" "$@"
fi

CONTROLLER_SOURCE="$EXECUTING_PATH"
ORIGINAL_WRAPPER="$(readlink -f "${TRIVIEW_UPDATER_ORIGINAL_WRAPPER:?caminho original ausente}")"
SCRIPT_DIR="$(dirname "$ORIGINAL_WRAPPER")"
CORE_SCRIPT="$SCRIPT_DIR/update-core.sh"
APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
CHANNEL_FILE="$APP_ROOT/UPDATE_CHANNEL"
UPDATER_ROOT="$APP_ROOT/updater"
TARGET_WRAPPER="$UPDATER_ROOT/update.sh"
TARGET_CORE="$UPDATER_ROOT/update-core.sh"

cleanup() {
  rm -f "$CONTROLLER_SOURCE" || true
  return 0
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

set +e
bash "$CORE_SCRIPT" "${forwarded_args[@]}"
status=$?
set -e

((status == 0)) || exit "$status"
((dry_run == 0)) || exit 0

# O núcleo instala a si próprio em updater/update.sh. Restauramos o
# controlador a partir da cópia imutável e mantemos o núcleo ao lado dele.
mkdir -p "$UPDATER_ROOT"
if [[ "$CORE_SCRIPT" != "$TARGET_CORE" ]] && ! cmp -s "$CORE_SCRIPT" "$TARGET_CORE"; then
  cp -a "$CORE_SCRIPT" "$TARGET_CORE"
fi
if ! cmp -s "$CONTROLLER_SOURCE" "$TARGET_WRAPPER"; then
  cp -a "$CONTROLLER_SOURCE" "$TARGET_WRAPPER"
fi
chmod +x "$TARGET_WRAPPER" "$TARGET_CORE"
