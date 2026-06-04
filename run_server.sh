#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$PROJECT_ROOT/app"
VENV_DIR="$APP_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Virtual environment not found: $VENV_DIR"
  echo "Create it first:"
  echo "  cd \"$APP_DIR\""
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

cd "$APP_DIR"
source "$VENV_DIR/bin/activate"

export INGEST_ENABLED="${INGEST_ENABLED:-1}"
export INGEST_INTERVAL_SECONDS="${INGEST_INTERVAL_SECONDS:-900}"

python app.py
