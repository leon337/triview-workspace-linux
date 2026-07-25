#!/usr/bin/env bash
set -Eeuo pipefail
PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$PACKAGE_DIR/app/scripts/restore-latest.sh" "$@"
