#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p -- "$applications_dir"
cp -- "$project_root/data/crisisconnect.desktop" "$applications_dir/crisisconnect.desktop"
echo "Registered CrisisConnect for GeoClue. Allow location in your desktop privacy settings."
echo "Your Linux desktop also needs the GeoClue service and a location permission agent."
