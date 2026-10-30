#!/bin/sh
#
# Stages the SambaAD module the way the PowerShell Gallery ships it, with its
# backend inside it, since Install-Module copies one folder and nothing else:
#
#   sh tools/build_gallery_module.sh [destination]
#
# The destination's last component must stay SambaAD: PowerShell finds a module
# by its folder name. Files are written readable by everyone whatever the umask.

set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST=${1:-$ROOT/dist/gallery/SambaAD}

rm -rf "$DEST"
mkdir -p "$DEST/backend"
cp "$ROOT/powershell/SambaAD/SambaAD.psd1" "$ROOT/powershell/SambaAD/SambaAD.psm1" \
    "$ROOT/powershell/SambaAD/SambaAD.Format.ps1xml" "$ROOT/LICENSE" "$DEST/"
cp "$ROOT/tools/gallery/samba_ad_backend.py" "$DEST/backend/"
cp -r "$ROOT/src/samba_powershell" "$DEST/backend/"
find "$DEST" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$DEST" -type d -exec chmod 0755 {} +
find "$DEST" -type f -exec chmod 0644 {} +
echo "$DEST"
