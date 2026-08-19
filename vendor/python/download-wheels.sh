#!/usr/bin/env bash
# Run once on a Raspberry Pi (aarch64) to snapshot PyPI wheels into git:
#   bash vendor/python/download-wheels.sh
# Then commit vendor/python/wheels/ and use: sudo bash install.sh --offline
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${ROOT}/vendor/python/wheels"
REQ="${ROOT}/vendor/python/requirements-max.txt"
mkdir -p "$DEST"
python3 -m pip download -d "$DEST" -r "$REQ"
echo "Saved wheels in $DEST ($(ls "$DEST" | wc -l) files)"
