#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."

if [[ -x venv/bin/python ]]; then
    echo "Virtual environment already exists in venv."
elif [[ -e venv ]]; then
    echo "ERROR: venv exists but is not a Linux virtual environment. Rename it before retrying." >&2
    exit 1
elif ! python3 -m venv venv; then
    echo "ERROR: Could not create venv. Install Python 3.11+ and its venv package (python3-venv on Debian/Ubuntu)." >&2
    exit 1
fi
echo "To activate from the project root: source venv/bin/activate"
