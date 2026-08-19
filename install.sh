#!/usr/bin/env bash
# One-command PiAuto Max setup: vendored pironman5 + our pm_auto/pm_dashboard.
# Does NOT git clone sunfounder/pironman5.
#
#   sudo bash install.sh
#   sudo bash install.sh --offline   # wheels-only (needs vendor/python/wheels)
#
set -euo pipefail

PIRONMAN_HOME="${PIRONMAN5_HOME:-/opt/pironman5}"
VENV_DIR="${PIRONMAN5_VENV:-${PIRONMAN_HOME}/venv}"
SERVICE="${PIRONMAN5_SERVICE:-pironman5}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OFFLINE=0
if [[ "${1:-}" == "--offline" ]]; then
  OFFLINE=1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR_PM5="${SCRIPT_DIR}/vendor/pironman5"
VENDOR_STATUS="${SCRIPT_DIR}/vendor/sf_rpi_status"
REQ_FILE="${SCRIPT_DIR}/vendor/python/requirements-max.txt"
WHEELS="${SCRIPT_DIR}/vendor/python/wheels"
PM_AUTO="${SCRIPT_DIR}/pm_auto"
PM_DASH="${SCRIPT_DIR}/pm_dashboard"

die() { echo "ERROR: $*" >&2; exit 1; }

[[ -f "${VENDOR_PM5}/pyproject.toml" ]] || die "missing ${VENDOR_PM5} (vendor pironman5)"
[[ -f "${PM_AUTO}/pyproject.toml" ]] || die "missing ${PM_AUTO}"
[[ -f "${PM_DASH}/pyproject.toml" ]] || die "missing ${PM_DASH}"

run_priv() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi
  if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo -n "$@"
    return
  fi
  if [[ -t 0 ]] && command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi
  die "need root for: $*"
}

echo "== PiAuto Max installer (vendored pironman5, no SunFounder clone) =="

echo "-- apt packages --"
if command -v apt-get >/dev/null 2>&1; then
  run_priv apt-get update -y
  run_priv DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip python3-venv python3-dev \
    libjpeg-dev libfreetype6-dev libopenjp2-7 \
    kmod i2c-tools build-essential gcc g++ \
    python3-gpiozero
  # InfluxDB is optional history; ignore failure on distros without the package.
  run_priv DEBIAN_FRONTEND=noninteractive apt-get install -y influxdb || true
else
  echo "WARNING: apt-get not found; install system libs yourself."
fi

if [[ -x "${VENDOR_PM5}/scripts/install_lgpio.sh" ]]; then
  echo "-- lgpio --"
  run_priv bash "${VENDOR_PM5}/scripts/install_lgpio.sh" || true
fi
if [[ -x "${VENDOR_PM5}/scripts/install_influxdb.sh" ]]; then
  echo "-- influxdb helper --"
  run_priv bash "${VENDOR_PM5}/scripts/install_influxdb.sh" || true
fi

echo "-- user / dirs --"
run_priv mkdir -p "${PIRONMAN_HOME}" /var/log/pironman5
if command -v groupadd >/dev/null 2>&1; then
  run_priv getent group pironman5 >/dev/null || run_priv groupadd -r pironman5 || true
  run_priv getent passwd pironman5 >/dev/null || \
    run_priv useradd -r -g pironman5 -s /sbin/nologin -d "${PIRONMAN_HOME}" -m pironman5 || true
  for g in video influxdb spi gpio i2c input; do
    run_priv getent group "$g" >/dev/null 2>&1 || run_priv groupadd -r "$g" || true
    run_priv usermod -aG "$g" pironman5 2>/dev/null || true
  done
fi
if [[ ! -f "${PIRONMAN_HOME}/config.json" ]]; then
  run_priv tee "${PIRONMAN_HOME}/config.json" >/dev/null <<'EOF'
{
  "system": {
    "data_interval": 1,
    "database_retention_days": "30",
    "temperature_unit": "C",
    "enable_history": true,
    "oled_enable": true,
    "oled_rotation": 0,
    "oled_sleep_timeout": 0,
    "oled_pages": ["mix", "performance", "ips", "disk"],
    "rgb_enable": true,
    "rgb_color": "#0a1aff",
    "rgb_brightness": 100,
    "rgb_style": "breathing",
    "rgb_speed": 50,
    "rgb_led_count": 4,
    "gpio_fan_pin": 6,
    "gpio_fan_mode": 0,
    "gpio_fan_led": "follow",
    "gpio_fan_led_pin": 5,
    "debug_level": "INFO"
  }
}
EOF
fi
run_priv touch /var/log/pironman5/pironman5.log || true
run_priv chown -R pironman5:pironman5 "${PIRONMAN_HOME}" /var/log/pironman5 2>/dev/null || true

echo "-- venv --"
if [[ ! -x "${VENV_DIR}/bin/python3" ]]; then
  run_priv "${PYTHON_BIN}" -m venv "${VENV_DIR}" --system-site-packages
fi
PIP=("${VENV_DIR}/bin/python3" -m pip)
run_priv "${PIP[@]}" install --upgrade pip setuptools wheel

pip_local_or_pypi() {
  local extra=()
  if [[ -d "${WHEELS}" ]] && ls "${WHEELS}"/*.whl >/dev/null 2>&1; then
    extra+=(--find-links "${WHEELS}")
    if [[ "${OFFLINE}" == "1" ]]; then
      extra+=(--no-index)
    fi
  elif [[ "${OFFLINE}" == "1" ]]; then
    die "--offline requested but ${WHEELS} has no wheels"
  fi
  run_priv "${PIP[@]}" install "${extra[@]}" "$@"
}

echo "-- python libraries --"
pip_local_or_pypi -r "${REQ_FILE}"

echo "-- vendored pironman5 + sf_rpi_status --"
pip_local_or_pypi --upgrade --no-cache-dir "${VENDOR_PM5}"
if [[ -f "${VENDOR_STATUS}/pyproject.toml" ]]; then
  pip_local_or_pypi --upgrade --no-cache-dir "${VENDOR_STATUS}"
fi

echo "-- PiAuto pm_auto + pm_dashboard --"
pip_local_or_pypi --upgrade --no-cache-dir "${PM_DASH}"
pip_local_or_pypi --upgrade --no-cache-dir "${PM_AUTO}"

echo "-- CLI symlink --"
run_priv ln -sfn "${VENV_DIR}/bin/pironman5" /usr/local/bin/pironman5

echo "-- systemd --"
if [[ -f "${VENDOR_PM5}/bin/pironman5.service" ]] && command -v systemctl >/dev/null 2>&1; then
  run_priv cp "${VENDOR_PM5}/bin/pironman5.service" /etc/systemd/system/pironman5.service
  run_priv systemctl daemon-reload
  run_priv systemctl enable pironman5.service || true
  run_priv systemctl restart pironman5.service || \
    echo "WARNING: could not restart ${SERVICE} — run: sudo systemctl restart ${SERVICE}"
fi

if [[ -f /etc/modules-load.d/modules.conf ]] || [[ -d /etc/modules-load.d ]]; then
  if ! grep -q '^i2c-dev$' /etc/modules-load.d/modules.conf 2>/dev/null; then
    echo i2c-dev | run_priv tee -a /etc/modules-load.d/i2c-dev.conf >/dev/null || true
  fi
fi

echo "-- versions --"
"${VENV_DIR}/bin/python3" - <<'PY'
import importlib.util
import pironman5
import pm_auto
import pm_dashboard
print(f"pironman5 {getattr(pironman5, '__version__', '?')}")
try:
    from pironman5.version import __version__ as v
    print(f"pironman5 {v}")
except Exception:
    pass
print(f"pm_auto {pm_auto.__version__}")
print(f"pm_dashboard {pm_dashboard.__version__}")
print(f"pm_auto.libs: {importlib.util.find_spec('pm_auto.libs') is not None}")
print(f"sf_rpi_status: {importlib.util.find_spec('sf_rpi_status') is not None}")
PY

echo "Done. Dashboard: http://<pi-ip>:34001  (hard refresh Ctrl+Shift+R)"
echo "OLED designer: http://<pi-ip>:34001/oled-designer"
echo "Upgrade:       http://<pi-ip>:34001/upgrade/"
