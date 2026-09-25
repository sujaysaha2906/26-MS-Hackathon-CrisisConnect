#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
if [[ ! -x venv/bin/python ]]; then
    echo "Run bash scripts/linux/setup_demo.sh first." >&2
    exit 1
fi
exec venv/bin/python main.py --demo "$@"
