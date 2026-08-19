# PiAuto (pm_auto)

Custom **Pironman 5** automation package — multi-page OLED UI, storage fixes, fan/GPU/CPU stats.

Installs as Python package **`pm_auto`** (same import name as SunFounder upstream for `pironman5` compatibility).

- Repo: [github.com/karpus2807/piauto](https://github.com/karpus2807/piauto)
- Version: see `pm_auto/version.py`

## OLED pages

| Page | Duration |
|------|----------|
| Home (classic layout) | 15 s |
| Storage (all mounts, paginated) | 5 s per slide |
| CPU, GPU, Fans, RAM, Temps, Top processes, Heart | 5 s each |

Sleep timeout disabled in firmware loop — carousel runs continuously.

## One-command install (Pironman 5 Max upgrade)

**SunFounder `pironman5` is vendored** in `vendor/pironman5/` (v1.3.18). You do **not** run their installer or clone their repo.

```bash
git clone https://github.com/karpus2807/piauto.git
cd piauto
sudo bash install.sh
```

This installs:

- vendored `pironman5` + `sf_rpi_status`
- this repo’s `pm_auto` + `pm_dashboard` (OLED designer)
- systemd `pironman5.service`
- apt libs (JPEG/Freetype/i2c) and Python packages (Flask, Pillow, …)

Python wheels can be pre-downloaded into `vendor/python/wheels/` then:

```bash
sudo bash install.sh --offline
```

See `vendor/THIRD_PARTY.md`. Overlay-only upgrade on an existing Max install:

```bash
bash install-oled-designer.sh
```

### Pironman 5 Max (recommended path)

Max keeps a **pm_auto 2.x** stack (`pm_auto.libs` intact) plus a multi-page **OLED Designer**:

- Left nav **OLED** tab → full designer (`home` / `storage` / `network` / `cpu` / `gpu` / `fans` / `ram` / `temps` / `services` / `heart`, custom pages, canvas edit, Apply / Test on OLED)
- Direct: `http://<pi-ip>:34001/oled-designer`

To restore pure SunFounder packages:

```bash
bash install-oled-designer.sh --restore-stock
```

### Classic (non-Max) Pironman 5

Installer also installs classic `pm_auto` from this repo (carousel / designer stack). Do **not** force that onto Max unless you know it will break `pm_auto.libs`.

After install, hard refresh the browser (`Ctrl+Shift+R`).

Optional overrides:

```bash
PIRONMAN5_HOME=/opt/pironman5 \
PIRONMAN5_VENV=/opt/pironman5/venv \
PIRONMAN5_SERVICE=pironman5 \
PIAUTO_FORCE_GIT=1 \
PIAUTO_REF=main \
bash install-oled-designer.sh
```

## Upgrade on device

```bash
sudo systemctl stop pironman5.service
sudo /opt/pironman5/venv/bin/pip3 uninstall pm_auto -y
sudo /opt/pironman5/venv/bin/pip3 install --upgrade git+https://github.com/karpus2807/piauto.git@main
sudo systemctl start pironman5.service
```

Pinned release (recommended for production):

```bash
sudo /opt/pironman5/venv/bin/pip3 install --upgrade \
  "git+https://github.com/karpus2807/piauto.git@v1.2.24"
```

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## OLED profile / timing (no new pironman5 CLI required)

After installing piauto, use `pm-auto-oled` (works even if `pironman5 -op` is not available):

```bash
sudo /opt/pironman5/venv/bin/pm-auto-oled -op minimal
sudo /opt/pironman5/venv/bin/pm-auto-oled -ohd 20 -opd 8
sudo /opt/pironman5/venv/bin/pm-auto-oled --pages home,storage,network,heart
sudo /opt/pironman5/venv/bin/pm-auto-oled --alert-cpu-temp 75 --alert-disk-percent 85
sudo /opt/pironman5/venv/bin/pm-auto-oled --show
sudo systemctl restart pironman5.service
```

Profiles: `full`, `minimal`, `server`

### OLED layout preview (no hardware)

```bash
pm-auto-oled-preview -o /tmp/oled-preview --profile full
pm-auto-oled-preview --pages home,cpu,gpu --warn
```

Writes `oled_home.png`, `oled_storage_0.png`, … and optional `oled_warn.png`.

## Tier 4 tooling (v1.2.24+)

| Tool | Purpose |
|------|---------|
| `CHANGELOG.md` | Release history |
| `git tag v1.2.x` | Pinned `pip install …@v1.2.24` |
| `pm-auto-oled --pages` | Custom carousel in `config.json` |
| `pm-auto-oled --alert-*` | Thresholds without editing JSON |
| `pm-auto-oled-preview` | PNG export for layout dev |

## Alerts (v1.2.20+)

When CPU/GPU temp, CPU %, or disk % cross thresholds, OLED shows a flashing **WARNING** screen for 3s (45s cooldown).

Defaults: CPU temp 80°C, CPU 90%, disk 90%, GPU temp 80°C. Set in `config.json` under `system`:

- `oled_alert_enable`, `oled_alert_duration`, `oled_alert_cooldown`
- `oled_alert_cpu_temp`, `oled_alert_cpu_percent`, `oled_alert_disk_percent`, `oled_alert_gpu_temp`

Fan page shows **TOWER** RPM (PWM) and **SIDE** on/off (GPIO) separately.

## Dashboard Tier 2 (v1.2.23+, not on OLED)

Hostname, uptime, and per-mount **free space** for web dashboard integration only.

```python
from pm_auto.dashboard_stats import get_dashboard_snapshot

data = get_dashboard_snapshot()
# data['system']['hostname']  -> "node2"
# data['system']['uptime']    -> "3d 4h 12m"
# data['storage']['mounts'][0]['free_display'] -> "Free 109.1 GB"
```

CLI (no hardware required):

```bash
pm-auto-status --pretty
```

`PMAuto` also publishes flat keys every 5s on `set_on_state_changed` callback:
`hostname`, `uptime`, `uptime_seconds`, `storage_combined`, `storage_mounts`.

## Tier 3 polish (v1.2.22+)

- **Home IP bar:** `wlan0 192.168.1.5` (interface + address, rotates when multiple)
- **Heart page:** inset margin so the shape is not clipped by the case window
- **Storage icons:** refined 14×14 SD (notch), SSD, USB plug
- **Storage / Temps:** disk temperature via `smartctl` when available (NVMe/SSD/USB)
- **PWR! alert:** undervoltage from `vcgencmd get_throttled` → flashing warning (`oled_alert_undervoltage`)

## Web dashboard (pm_dashboard v1.3.0+)

Advanced **Control Center**: `http://<pi-ip>:34001/control`

- Full `config.json` `system` keys via UI (RGB, fans, OLED, alerts)
- Presets: Quiet Desktop, Performance, Server, Night, etc.
- Uses `dashboard_stats` for hostname / uptime / free storage on live bar

## Upgrade (dashboard)

Left nav **Upgrade** lists the last **3 GitHub Releases** of [karpus2807/piauto](https://github.com/karpus2807/piauto). Switch to any of those tags; `pm_auto` + `pm_dashboard` are installed from that release and `pironman5` restarts.

Direct URL: `http://<pi-ip>:34001/upgrade/`

Publish a GitHub **Release** (not only a git tag) so the panel shows notes. Until the first Release exists, the last 3 tags are shown.

## OLED Designer

Open: `http://<pi-ip>:34001/oled-designer`

- Edit all built-in OLED pages and custom pages in a 128×64 canvas.
- Static/sharp preview uses the same OLED render path as hardware.
- **Test on OLED** shows the current unsaved page on the physical OLED for 5 seconds.
- **Apply to device** saves the layout and carousel order permanently.
- Built-in icons render as native 14×14 monochrome OLED bitmaps.
- Bootstrap icon picks are mapped to OLED-safe monochrome bitmaps.
- Icon animations: `none`, `blink`, `pulse`, `spin`.

Install from this repo’s `pm_dashboard/` folder (see root `install.py`).

## Based on

Forked from [sunfounder/pm_auto](https://github.com/sunfounder/pm_auto) with OLED carousel and storage formatting changes.
