#!/usr/bin/env bash
# Overlay upgrade: install this repo's pm_auto + pm_dashboard into an existing
# /opt/pironman5/venv. For a full Max stack from this repo only (no SunFounder
# clone), use: sudo bash install.sh
set -euo pipefail

REPO_URL="${PIAUTO_REPO_URL:-https://github.com/karpus2807/piauto.git}"
REF="${PIAUTO_REF:-main}"
PIRONMAN_HOME="${PIRONMAN5_HOME:-/opt/pironman5}"
VENV_DIR="${PIRONMAN5_VENV:-${PIRONMAN_HOME}/venv}"
SERVICE="${PIRONMAN5_SERVICE:-pironman5}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
STOCK_PM_AUTO_URL="${STOCK_PM_AUTO_URL:-git+https://github.com/sunfounder/pm_auto.git@v2.0.5}"
STOCK_PM_DASH_URL="${STOCK_PM_DASH_URL:-git+https://github.com/sunfounder/pm_dashboard.git@chore/bump-2.0.3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Prefer local checkout when this script lives inside a piauto clone.
LOCAL_ROOT=""
if [[ -f "${SCRIPT_DIR}/pm_auto/pyproject.toml" && -f "${SCRIPT_DIR}/pm_dashboard/pyproject.toml" ]]; then
  LOCAL_ROOT="$SCRIPT_DIR"
elif [[ -f "${SCRIPT_DIR}/../pm_auto/pyproject.toml" && -f "${SCRIPT_DIR}/../pm_dashboard/pyproject.toml" ]]; then
  LOCAL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

have_passwordless_sudo() {
  command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1
}

# Run a command as root when needed. Prefer plain execution if already root / writable.
run_priv() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
    return
  fi
  if have_passwordless_sudo; then
    sudo -n "$@"
    return
  fi
  if [[ -t 0 ]] && command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi
  # Non-interactive fallback used on this host: docker + nsenter into host PID 1.
  if command -v docker >/dev/null 2>&1; then
    docker run --rm --privileged --pid=host debian:bookworm-slim \
      nsenter -t 1 -m -u -i -n -p -- "$@"
    return
  fi
  echo "ERROR: need root privileges to run: $*" >&2
  echo "Re-run as root, enable passwordless sudo, or install docker for nsenter fallback." >&2
  exit 1
}

can_write_dir() {
  local d="$1"
  [[ -d "$d" && -w "$d" ]]
}

need_apt_deps() {
  ! command -v "${PYTHON_BIN}" >/dev/null 2>&1 && return 0
  ! "${PYTHON_BIN}" -c 'import venv' >/dev/null 2>&1 && return 0
  ! command -v git >/dev/null 2>&1 && return 0
  return 1
}

ensure_apt_deps() {
  if ! need_apt_deps && [[ "${PIAUTO_FORCE_APT:-0}" != "1" ]]; then
    return 0
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "ERROR: apt-get not found; install python3, python3-venv, python3-pip, git manually." >&2
    exit 1
  fi
  echo "Installing system packages (python3-venv, pip, git, OLED libs)..."
  run_priv apt-get update -y
  run_priv apt-get install -y \
    python3 python3-pip python3-venv python3-dev git \
    liblgpio-dev libfreetype6-dev libjpeg-dev libopenjp2-7 i2c-tools
}

mkdir_p() {
  local dir="$1"
  local parent
  parent="$(dirname "$dir")"
  if [[ -d "$dir" ]]; then
    return 0
  fi
  if can_write_dir "$parent"; then
    mkdir -p "$dir"
  else
    run_priv mkdir -p "$dir"
  fi
}

chmod_path() {
  local mode="$1"
  local path="$2"
  if [[ -e "$path" ]] && { [[ -w "$path" ]] || can_write_dir "$(dirname "$path")"; }; then
    chmod "$mode" "$path" 2>/dev/null || true
  else
    run_priv chmod "$mode" "$path" || true
  fi
}

ensure_pironman_home() {
  if [[ ! -d "$PIRONMAN_HOME" ]]; then
    echo "Creating ${PIRONMAN_HOME}..."
    mkdir_p "$PIRONMAN_HOME"
    chmod_path 775 "$PIRONMAN_HOME"
  fi
  if [[ ! -d "$PIRONMAN_HOME" ]]; then
    echo "ERROR: cannot create ${PIRONMAN_HOME} (need sudo)." >&2
    exit 1
  fi
  if [[ ! -f "${PIRONMAN_HOME}/config.json" ]]; then
    echo "Writing default ${PIRONMAN_HOME}/config.json..."
    local tmp
    tmp="$(mktemp)"
    cat >"$tmp" <<'EOF'
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
        "rgb_led_count_min": 4,
        "gpio_fan_pin": 6,
        "gpio_fan_mode": 0,
        "gpio_fan_led": "follow",
        "gpio_fan_led_pin": 5,
        "debug_level": "INFO"
    }
}
EOF
    if can_write_dir "$PIRONMAN_HOME"; then
      cp "$tmp" "${PIRONMAN_HOME}/config.json"
    else
      run_priv cp "$tmp" "${PIRONMAN_HOME}/config.json"
    fi
    chmod_path 664 "${PIRONMAN_HOME}/config.json"
    rm -f "$tmp"
  fi
}

venv_ok() {
  [[ -x "${VENV_DIR}/bin/python3" && -x "${VENV_DIR}/bin/pip3" ]]
}

ensure_venv() {
  if venv_ok; then
    echo "Using existing venv: ${VENV_DIR}"
    if [[ "$(id -u)" -eq 0 ]] || have_passwordless_sudo; then
      run_priv chmod -R g+w "${VENV_DIR}" 2>/dev/null || true
    fi
    return 0
  fi

  echo "Creating Python venv at ${VENV_DIR}..."
  if [[ -d "$VENV_DIR" && ! -x "${VENV_DIR}/bin/python3" ]]; then
    echo "WARNING: incomplete venv at ${VENV_DIR}; recreating..."
    if can_write_dir "$(dirname "$VENV_DIR")" && [[ -w "$VENV_DIR" || ! -e "$VENV_DIR" ]]; then
      rm -rf "$VENV_DIR"
    else
      run_priv rm -rf "$VENV_DIR"
    fi
  fi

  if can_write_dir "$PIRONMAN_HOME"; then
    "${PYTHON_BIN}" -m venv "$VENV_DIR"
    chmod -R g+w "$VENV_DIR" 2>/dev/null || true
  else
    run_priv "${PYTHON_BIN}" -m venv "$VENV_DIR"
    run_priv chmod -R g+w "$VENV_DIR" || true
  fi

  if ! venv_ok; then
    echo "ERROR: failed to create venv at ${VENV_DIR}" >&2
    exit 1
  fi
}

run_pip() {
  local -a cmd=("${VENV_DIR}/bin/python3" -m pip "$@")
  local site
  site="$("${VENV_DIR}/bin/python3" -c 'import site; print(site.getsitepackages()[0])')"
  if can_write_dir "$site"; then
    "${cmd[@]}"
  else
    run_priv "${cmd[@]}"
  fi
}

upgrade_pip() {
  echo "Upgrading pip / setuptools / wheel..."
  run_pip install --upgrade --no-cache-dir pip setuptools wheel
}

# True when this venv already has SunFounder Max / pm_auto 2.x layout.
is_pironman_max_stack() {
  [[ -x "${VENV_DIR}/bin/python3" ]] || return 1
  "${VENV_DIR}/bin/python3" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

# Max / v2 stack exposes pm_auto.libs and usually pironman5 >= 1.3
if importlib.util.find_spec("pm_auto.libs") is not None:
    sys.exit(0)
try:
    import pironman5
    ver = getattr(pironman5, "__version__", "0")
    major, minor, *_ = [int(x) for x in ver.split(".")[:2]]
    if (major, minor) >= (1, 3):
        sys.exit(0)
except Exception:
    pass
sys.exit(1)
PY
}

restore_stock() {
  echo "Restoring SunFounder stock pm_auto + pm_dashboard for Max..."
  ensure_venv
  upgrade_pip
  run_pip install --upgrade --force-reinstall --no-cache-dir "$STOCK_PM_AUTO_URL"
  run_pip install --upgrade --force-reinstall --no-cache-dir "$STOCK_PM_DASH_URL"
  cleanup_pip_leftovers
  restart_service
  show_versions
  echo "Stock packages restored. Dashboard: http://<pi-ip>:34001/"
}

cleanup_pip_leftovers() {
  local site
  site="$("${VENV_DIR}/bin/python3" -c 'import site; print(site.getsitepackages()[0])')"
  # Broken partial uninstalls leave ~m_* dirs owned by root.
  if can_write_dir "$site"; then
    rm -rf "${site}"/~m_* "${site}"/pm_auto/~* 2>/dev/null || true
  else
    run_priv bash -c "rm -rf '${site}'/~m_* '${site}'/pm_auto/~*" || true
  fi
}

install_packages() {
  local pm_auto_src pm_dash_src
  local max_stack=0
  if is_pironman_max_stack; then
    max_stack=1
  fi

  if [[ -n "$LOCAL_ROOT" && "${PIAUTO_FORCE_GIT:-0}" != "1" ]]; then
    echo "Installing from local checkout: ${LOCAL_ROOT}"
    pm_auto_src="${LOCAL_ROOT}/pm_auto"
    pm_dash_src="${LOCAL_ROOT}/pm_dashboard"
  else
    echo "Installing from ${REPO_URL}@${REF}"
    pm_auto_src="git+${REPO_URL}@${REF}#subdirectory=pm_auto"
    pm_dash_src="git+${REPO_URL}@${REF}#subdirectory=pm_dashboard"
  fi

  echo "Installing pm_dashboard (OLED Customize tab)..."
  run_pip install --upgrade --no-cache-dir "$pm_dash_src"

  echo "Installing pm_auto (Max-compatible 2.x + multi-page designer)..."
  run_pip install --upgrade --no-cache-dir "$pm_auto_src"

  cleanup_pip_leftovers
}

restart_service() {
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "systemctl not found; skip service restart."
    return 0
  fi
  local unit_src=""
  if [[ -n "${LOCAL_ROOT}" && -f "${LOCAL_ROOT}/vendor/pironman5/bin/pironman5.service" ]]; then
    unit_src="${LOCAL_ROOT}/vendor/pironman5/bin/pironman5.service"
  fi
  if [[ -n "${unit_src}" ]]; then
    echo "Installing ${SERVICE}.service (enable + Restart=always)..."
    run_priv cp "${unit_src}" "/etc/systemd/system/${SERVICE}.service"
    run_priv systemctl daemon-reload
  fi
  if ! systemctl list-unit-files "${SERVICE}.service" >/dev/null 2>&1; then
    echo "No ${SERVICE}.service unit found; packages installed, skip restart."
    return 0
  fi
  echo "Enabling ${SERVICE}.service so it starts after reboot..."
  run_priv systemctl enable "${SERVICE}.service" || true
  echo "Restarting ${SERVICE}.service..."
  if run_priv systemctl restart "${SERVICE}"; then
    sleep 2
    systemctl is-active --quiet "${SERVICE}" && echo "${SERVICE}.service is active."
  else
    echo "WARNING: could not restart ${SERVICE}.service — run: sudo systemctl restart ${SERVICE}" >&2
  fi
}

show_versions() {
  echo "Installed versions:"
  "${VENV_DIR}/bin/python3" - <<'PY'
import pm_auto
import pm_dashboard
import importlib.util

print(f"pm_dashboard {pm_dashboard.__version__}")
print(f"pm_auto {pm_auto.__version__}")
print(f"pm_auto.libs present: {importlib.util.find_spec('pm_auto.libs') is not None}")
PY
}

usage() {
  cat <<'EOF'
Usage:
  bash install-oled-designer.sh              # Max: dashboard OLED tab only; classic: dashboard+pm_auto
  bash install-oled-designer.sh --restore-stock
  bash install-oled-designer.sh --help
EOF
}

main() {
  case "${1:-}" in
    -h|--help)
      usage
      exit 0
      ;;
    --restore-stock)
      echo "== PiAuto / Pironman stock restore =="
      ensure_apt_deps
      ensure_pironman_home
      restore_stock
      exit 0
      ;;
    "")
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac

  echo "== PiAuto OLED Customize installer =="
  ensure_apt_deps
  ensure_pironman_home
  ensure_venv
  upgrade_pip
  install_packages
  restart_service
  show_versions
  echo "Done. Open http://<pi-ip>:34001 — left nav includes OLED and Update. Hard refresh (Ctrl+Shift+R)."
}

main "$@"
