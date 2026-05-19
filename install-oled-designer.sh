#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${PIAUTO_REPO_URL:-https://github.com/karpus2807/piauto.git}"
REF="${PIAUTO_REF:-main}"
VENV_PIP="${PIRONMAN5_VENV_PIP:-/opt/pironman5/venv/bin/pip3}"
VENV_PY="${PIRONMAN5_VENV_PY:-/opt/pironman5/venv/bin/python3}"
SERVICE="${PIRONMAN5_SERVICE:-pironman5}"

if [[ ! -x "$VENV_PIP" ]]; then
  echo "ERROR: pip not found at $VENV_PIP" >&2
  echo "Set PIRONMAN5_VENV_PIP=/path/to/pip3 if your venv is elsewhere." >&2
  exit 1
fi

echo "Installing pm_dashboard from ${REPO_URL}@${REF}..."
"$VENV_PIP" install --upgrade --no-cache-dir \
  "git+${REPO_URL}@${REF}#subdirectory=pm_dashboard"

echo "Installing pm_auto from ${REPO_URL}@${REF}..."
"$VENV_PIP" install --upgrade --no-cache-dir \
  "git+${REPO_URL}@${REF}#subdirectory=pm_auto"

echo "Restarting ${SERVICE}.service..."
if command -v sudo >/dev/null 2>&1; then
  sudo systemctl restart "${SERVICE}"
else
  systemctl restart "${SERVICE}"
fi

echo "Installed versions:"
"$VENV_PY" - <<'PY'
import pm_auto
import pm_dashboard

print(f"pm_dashboard {pm_dashboard.__version__}")
print(f"pm_auto {pm_auto.__version__}")
PY

echo "Done. Hard refresh the browser (Ctrl+Shift+R) on /oled-designer."
