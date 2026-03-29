#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="python3.11"
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "[INFO] Creating virtual environment at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

PY_VER="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$PY_VER" = "3.13" ]; then
  echo "[ERROR] Python 3.13 detected in .venv; pinned sentencepiece/tokenizers wheels are not stable on 3.13."
  echo "[ERROR] Recreate venv with Python 3.11 and rerun:"
  echo "        rm -rf \"$VENV_DIR\" && PYTHON_BIN=python3.11 ./run_evaluation.sh <args>"
  exit 1
fi

python -m pip install --upgrade pip >/dev/null
python -m pip install -U \
  "transformers==4.44.2" \
  "datasets==2.21.0" \
  "evaluate==0.4.2" \
  "sacrebleu==2.4.3" \
  "sentencepiece==0.2.0" \
  "accelerate==0.34.2" \
  "rouge-score==0.1.2"
python -m pip install -r "$SCRIPT_DIR/requirements.txt"

python "$SCRIPT_DIR/evaluate_models.py" "$@"
