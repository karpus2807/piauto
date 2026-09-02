#!/usr/bin/env bash
# PiAuto installer — curl-pipe safe, phased: deps → verify → venv → packages → piauto.service
#
# One command (no prior SunFounder install):
#   curl -fsSL https://raw.githubusercontent.com/karpus2807/piauto/main/install.sh | sudo bash
#
# Local checkout:
#   sudo bash install.sh
#   sudo bash install.sh --offline
#   sudo bash install.sh --variant max
#
set -euo pipefail

REPO_URL="${PIAUTO_REPO_URL:-https://github.com/karpus2807/piauto.git}"
REF="${PIAUTO_REF:-main}"
APP_HOME="${PIRONMAN5_HOME:-/opt/pironman5}"
VENV_DIR="${PIRONMAN5_VENV:-${APP_HOME}/venv}"
SERVICE="${PIAUTO_SERVICE:-piauto}"
LEGACY_SERVICE="pironman5"
VARIANT="${PIAUTO_VARIANT:-max}"
SRC_KEEP="${PIAUTO_SRC:-/opt/piauto/src}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OFFLINE=0
SKIP_CLONE=0

usage() {
  cat <<'EOF'
Usage:
  sudo bash install.sh                 # deps, verify, venv, packages, piauto.service
  sudo bash install.sh --offline       # wheels-only (needs vendor/python/wheels)
  sudo bash install.sh --variant max   # max | base | mini  (default: max)
  sudo bash install.sh --ref v2.0.14   # git tag/branch when curl-bootstrapping

Env:
  PIAUTO_REPO_URL  PIAUTO_REF  PIAUTO_VARIANT  PIAUTO_SERVICE
  PIRONMAN5_HOME   PIRONMAN5_VENV  PYTHON_BIN
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --offline) OFFLINE=1; shift ;;
    --local) SKIP_CLONE=1; shift ;;
    --variant) VARIANT="${2:-max}"; shift 2 ;;
    --variant=*) VARIANT="${1#*=}"; shift ;;
    --ref) REF="${2:-main}"; shift 2 ;;
    --ref=*) REF="${1#*=}"; shift ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

case "$VARIANT" in
  max|base|mini|pro_max|pro-max) [[ "$VARIANT" == "pro-max" ]] && VARIANT="pro_max" ;;
  *) echo "ERROR: invalid --variant ${VARIANT} (max|base|mini)" >&2; exit 1 ;;
esac

die() { echo "ERROR: $*" >&2; exit 1; }
ok()  { echo "  [ok] $*"; }
step() { echo; echo "== $* =="; }

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

need_cmd() {
  local name="$1"
  command -v "$name" >/dev/null 2>&1
}

resolve_self_dir() {
  local src="${BASH_SOURCE[0]:-}"
  if [[ -n "$src" && -f "$src" ]]; then
    cd "$(dirname "$src")" && pwd
  else
    echo ""
  fi
}

TREE=""
SELF_DIR="$(resolve_self_dir)"
if [[ "$SKIP_CLONE" == "1" && -n "$SELF_DIR" && -f "${SELF_DIR}/vendor/pironman5/pyproject.toml" ]]; then
  TREE="$SELF_DIR"
elif [[ -n "$SELF_DIR" && -f "${SELF_DIR}/vendor/pironman5/pyproject.toml" ]]; then
  TREE="$SELF_DIR"
fi

# --- Phase 1: OS packages (before clone, so curl | bash can fetch git) ---
step "1/6  Install required OS packages"
if command -v apt-get >/dev/null 2>&1; then
  run_priv apt-get update -y
  run_priv env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates curl git \
    python3 python3-pip python3-venv python3-dev \
    libjpeg-dev libfreetype6-dev libopenjp2-7 \
    kmod i2c-tools build-essential gcc g++ \
    python3-gpiozero pkg-config
  run_priv env DEBIAN_FRONTEND=noninteractive apt-get install -y influxdb || \
    echo "  [warn] influxdb package not available (history optional)"
else
  echo "  [warn] apt-get not found; OS packages must already be present"
fi

# --- Phase 2: Verify OS requirements ---
step "2/6  Verify required commands"
MISSING=0
for cmd in "$PYTHON_BIN" git curl gcc; do
  if need_cmd "$cmd"; then
    ok "$cmd $(command -v "$cmd")"
  else
    echo "  [MISSING] $cmd"
    MISSING=1
  fi
done
if ! "$PYTHON_BIN" -c 'import venv, ensurepip' >/dev/null 2>&1; then
  if ! "$PYTHON_BIN" -c 'import venv' >/dev/null 2>&1; then
    echo "  [MISSING] python3 venv module"
    MISSING=1
  else
    ok "python3 venv module"
  fi
else
  ok "python3 venv module"
fi
if need_cmd i2cdetect; then
  ok "i2c-tools"
else
  echo "  [warn] i2cdetect not found (OLED/I2C tools missing)"
fi
[[ "$MISSING" == "0" ]] || die "required packages missing; fix the [MISSING] items and re-run"

# --- Bootstrap clone when this file was piped via curl | bash ---
if [[ -z "$TREE" ]]; then
  [[ "$OFFLINE" == "1" ]] && die "--offline needs a local checkout with vendor/"
  step "Fetch PiAuto source (${REF})"
  run_priv mkdir -p "$(dirname "$SRC_KEEP")"
  if [[ -d "${SRC_KEEP}/.git" ]]; then
    echo "  updating ${SRC_KEEP}"
    run_priv git -C "$SRC_KEEP" fetch --depth 1 origin "$REF" || \
      run_priv git -C "$SRC_KEEP" fetch origin "$REF"
    run_priv git -C "$SRC_KEEP" checkout -f FETCH_HEAD 2>/dev/null || \
      run_priv git -C "$SRC_KEEP" checkout -f "$REF"
  else
    run_priv rm -rf "$SRC_KEEP"
    run_priv git clone --depth 1 --branch "$REF" "$REPO_URL" "$SRC_KEEP" || \
      run_priv git clone --depth 1 "$REPO_URL" "$SRC_KEEP"
    if [[ "$REF" != "main" && "$REF" != "master" ]]; then
      run_priv git -C "$SRC_KEEP" fetch --depth 1 origin "$REF" || true
      run_priv git -C "$SRC_KEEP" checkout -f "$REF" || true
    fi
  fi
  TREE="$SRC_KEEP"
  echo "  source: $TREE"
fi

[[ -n "$TREE" ]] || die "no source tree (checkout this repo or drop --local)"

VENDOR_PM5="${TREE}/vendor/pironman5"
VENDOR_STATUS="${TREE}/vendor/sf_rpi_status"
REQ_FILE="${TREE}/vendor/python/requirements-max.txt"
WHEELS="${TREE}/vendor/python/wheels"
PM_AUTO="${TREE}/pm_auto"
PM_DASH="${TREE}/pm_dashboard"
UNIT_SRC="${TREE}/deploy/piauto.service"

[[ -f "${VENDOR_PM5}/pyproject.toml" ]] || die "missing ${VENDOR_PM5}"
[[ -f "${PM_AUTO}/pyproject.toml" ]] || die "missing ${PM_AUTO}"
[[ -f "${PM_DASH}/pyproject.toml" ]] || die "missing ${PM_DASH}"
[[ -f "$REQ_FILE" ]] || die "missing ${REQ_FILE}"

if [[ -x "${VENDOR_PM5}/scripts/install_lgpio.sh" ]]; then
  echo "  lgpio helper..."
  run_priv bash "${VENDOR_PM5}/scripts/install_lgpio.sh" || \
    echo "  [warn] lgpio helper failed (rpi.lgpio pip package may still work)"
fi
if [[ -x "${VENDOR_PM5}/scripts/install_influxdb.sh" ]]; then
  echo "  influxdb helper..."
  run_priv bash "${VENDOR_PM5}/scripts/install_influxdb.sh" || true
fi

# Kernel modules + device tree (hardware access)
step "Kernel / I2C / overlays"
run_priv mkdir -p /etc/modules-load.d
if ! grep -qs '^i2c-dev$' /etc/modules-load.d/i2c-dev.conf /etc/modules-load.d/modules.conf 2>/dev/null; then
  echo i2c-dev | run_priv tee /etc/modules-load.d/i2c-dev.conf >/dev/null
fi
run_priv modprobe i2c-dev 2>/dev/null || echo "  [warn] could not modprobe i2c-dev now (ok until reboot)"

overlay_file="sunfounder-pironman5.dtbo"
case "$VARIANT" in
  mini) overlay_file="sunfounder-pironman5mini.dtbo" ;;
  pro_max) overlay_file="sunfounder-pironman5promax.dtbo" ;;
esac
overlay_src="${VENDOR_PM5}/overlays/${overlay_file}"
if [[ -f "$overlay_src" ]]; then
  run_priv mkdir -p /usr/local/share/sunfounder/overlays
  run_priv cp "$overlay_src" /usr/local/share/sunfounder/overlays/
  for dest in /boot/firmware/overlays /boot/overlays; do
    if [[ -d "$dest" ]]; then
      run_priv cp "$overlay_src" "${dest}/"
      ok "copied ${overlay_file} → ${dest}"
    fi
  done
  overlay_stem="${overlay_file%.dtbo}"
  for cfg in /boot/firmware/config.txt /boot/config.txt; do
    [[ -f "$cfg" ]] || continue
    if ! grep -qs "^dtoverlay=${overlay_stem}$" "$cfg"; then
      echo "dtoverlay=${overlay_stem}" | run_priv tee -a "$cfg" >/dev/null
      ok "enabled dtoverlay=${overlay_stem} in ${cfg}"
    else
      ok "dtoverlay=${overlay_stem} already in ${cfg}"
    fi
    if ! grep -qsE '^dtparam=i2c_arm=on' "$cfg"; then
      echo "dtparam=i2c_arm=on" | run_priv tee -a "$cfg" >/dev/null
    fi
    if ! grep -qsE '^dtparam=spi=on' "$cfg"; then
      echo "dtparam=spi=on" | run_priv tee -a "$cfg" >/dev/null
    fi
    break
  done
else
  echo "  [warn] overlay not in tree: ${overlay_src}"
fi

# --- Phase 3: dirs, config, venv ---
step "3/6  Create /opt/pironman5 and Python venv"
run_priv mkdir -p "$APP_HOME" /var/log/pironman5
if command -v groupadd >/dev/null 2>&1; then
  run_priv getent group pironman5 >/dev/null || run_priv groupadd -r pironman5 || true
  run_priv getent passwd pironman5 >/dev/null || \
    run_priv useradd -r -g pironman5 -s /sbin/nologin -d "$APP_HOME" -m pironman5 || true
  for g in video influxdb spi gpio i2c input; do
    run_priv getent group "$g" >/dev/null 2>&1 || run_priv groupadd -r "$g" || true
    run_priv usermod -aG "$g" pironman5 2>/dev/null || true
  done
fi
echo -n "$VARIANT" | run_priv tee "${APP_HOME}/.variant" >/dev/null
if [[ ! -f "${APP_HOME}/config.json" ]]; then
  run_priv tee "${APP_HOME}/config.json" >/dev/null <<'EOF'
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
  ok "wrote default ${APP_HOME}/config.json"
else
  ok "kept existing ${APP_HOME}/config.json"
fi
run_priv touch /var/log/pironman5/pironman5.log || true

if [[ ! -x "${VENV_DIR}/bin/python3" ]]; then
  echo "  creating venv ${VENV_DIR}"
  run_priv "$PYTHON_BIN" -m venv "$VENV_DIR" --system-site-packages
fi
[[ -x "${VENV_DIR}/bin/python3" ]] || die "venv python missing at ${VENV_DIR}/bin/python3"
ok "venv ${VENV_DIR}"

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

# --- Phase 4: Python libraries then this project ---
step "4/6  Install Python libraries, then PiAuto packages"
echo "  pip requirements..."
pip_local_or_pypi -r "$REQ_FILE"
echo "  vendored pironman5 + sf_rpi_status..."
pip_local_or_pypi --upgrade --no-cache-dir "$VENDOR_PM5"
if [[ -f "${VENDOR_STATUS}/pyproject.toml" ]]; then
  pip_local_or_pypi --upgrade --no-cache-dir "$VENDOR_STATUS"
fi
echo "  pm_dashboard + pm_auto..."
pip_local_or_pypi --upgrade --no-cache-dir "$PM_DASH"
pip_local_or_pypi --upgrade --no-cache-dir "$PM_AUTO"

step "Verify Python packages in venv"
"${VENV_DIR}/bin/python3" - <<'PY'
import importlib
import sys
needed = [
    'pironman5', 'pm_auto', 'pm_dashboard', 'sf_rpi_status',
    'flask', 'PIL', 'psutil', 'smbus2',
]
missing = []
for name in needed:
    try:
        importlib.import_module(name)
        print(f'  [ok] {name}')
    except Exception as exc:
        missing.append(f'{name}: {exc}')
        print(f'  [MISSING] {name}: {exc}')
if missing:
    sys.exit(1)
import pm_auto, pm_dashboard
from pironman5.version import __version__ as pm5
print(f'  pironman5 {pm5}')
print(f'  pm_auto {pm_auto.__version__}')
print(f'  pm_dashboard {pm_dashboard.__version__}')
PY

run_priv ln -sfn "${VENV_DIR}/bin/pironman5" /usr/local/bin/pironman5
run_priv ln -sfn "${VENV_DIR}/bin/pironman5" /usr/local/bin/piauto
ok "CLI /usr/local/bin/piauto  (also pironman5)"

# --- Phase 5: systemd service named piauto ---
step "5/6  Install and enable ${SERVICE}.service"
if ! command -v systemctl >/dev/null 2>&1; then
  echo "  [warn] systemctl not found; skip service"
else
  if [[ -f "$UNIT_SRC" ]]; then
    run_priv cp "$UNIT_SRC" "/etc/systemd/system/${SERVICE}.service"
  else
    run_priv tee "/etc/systemd/system/${SERVICE}.service" >/dev/null <<EOF
[Unit]
Description=PiAuto service
After=network-online.target local-fs.target systemd-modules-load.service
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=${APP_HOME}
ExecStart=/usr/local/bin/piauto start
Restart=always
RestartSec=5
StartLimitIntervalSec=0

[Install]
WantedBy=multi-user.target
EOF
  fi
  run_priv systemctl daemon-reload
  if systemctl list-unit-files "${LEGACY_SERVICE}.service" >/dev/null 2>&1; then
    if systemctl is-enabled --quiet "${LEGACY_SERVICE}.service" 2>/dev/null || \
       systemctl is-active --quiet "${LEGACY_SERVICE}.service" 2>/dev/null; then
      echo "  stopping legacy ${LEGACY_SERVICE}.service (replaced by ${SERVICE})"
      run_priv systemctl disable --now "${LEGACY_SERVICE}.service" || true
    fi
  fi
  run_priv systemctl enable "${SERVICE}.service"
  run_priv systemctl restart "${SERVICE}.service"
  sleep 2
  if systemctl is-active --quiet "${SERVICE}"; then
    ok "${SERVICE}.service is active and enabled"
  else
    echo "  [warn] ${SERVICE}.service did not stay active — journalctl -u ${SERVICE} -e"
    systemctl --no-pager --full status "${SERVICE}" || true
  fi
fi

step "6/6  Done"
echo "Dashboard:     http://<pi-ip>:34001   (hard refresh Ctrl+Shift+R)"
echo "OLED designer: http://<pi-ip>:34001/oled-designer"
echo "Fans:          http://<pi-ip>:34001/fan-controls"
echo "Update:        http://<pi-ip>:34001/update/"
echo
echo "Service:  sudo systemctl status ${SERVICE}"
echo "Logs:     sudo journalctl -u ${SERVICE} -f"
echo "CLI:      sudo piauto"
echo "Config:   ${APP_HOME}/config.json"
echo "If I2C/SPI overlays were newly added, reboot once: sudo reboot"
