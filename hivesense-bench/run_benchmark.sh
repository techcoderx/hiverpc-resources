#!/usr/bin/env bash
# Run the HiveSense embedding benchmark with uv-managed dependencies.
#
# Usage: ./run_benchmark.sh [benchmark.py options]
# Pass --help for the full option list.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "$0")" >/dev/null 2>&1 || exit 1; pwd -P)"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required (https://docs.astral.sh/uv/)" >&2
  exit 1
fi

exec uv run --project "$SCRIPT_DIR" python "$SCRIPT_DIR/benchmark.py" "$@"
