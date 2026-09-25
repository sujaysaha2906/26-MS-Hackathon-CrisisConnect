#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
bash scripts/linux/setup_venv.sh
venv/bin/python -m pip install -r requirements-demo.txt
for dependency in espeak-ng; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        echo "Install $dependency first. On Debian/Ubuntu: sudo apt install espeak-ng python3-tk libportaudio2" >&2
        exit 1
    fi
done
venv/bin/python -m crisisconnect.setup_demo_model
echo "Demo ready. Run bash scripts/linux/start_demo.sh. No internet is needed after setup."
