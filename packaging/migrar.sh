#!/usr/bin/env bash
set -Eeuo pipefail
PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$PACKAGE_DIR/app/scripts/migrate-legacy.sh" --source "$PACKAGE_DIR/app" --package-dir "$PACKAGE_DIR" "$@"
