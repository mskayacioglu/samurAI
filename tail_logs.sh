#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$PROJECT_ROOT/app"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/db_operations.log"
LINES="${1:-200}"

mkdir -p "$LOG_DIR"
touch "$LOG_FILE"

echo "Following log file: $LOG_FILE"
echo "Showing last $LINES lines. Press Ctrl+C to stop."
echo

tail -n "$LINES" -F "$LOG_FILE"
