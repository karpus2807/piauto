# Changelog

All notable changes to [piauto](https://github.com/karpus2807/piauto) (`pm_auto`).

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [2.0.16] - 2026-09-02

### Fixed
- Refresh (or reload) on OLED / Fans / Update left the dashboard **blank**: stock React restored `tabIndex` `Update`/`index: 99`, which is not a real panel
- Extra tab pages are now hosted outside the React `#root` so a refresh cannot unmount them

## [2.0.15] - 2026-09-02

### Added
- Curl one-command installer: `curl -fsSL https://raw.githubusercontent.com/karpus2807/piauto/main/install.sh | sudo bash`
- systemd service name **`piauto`** (legacy `pironman5.service` is disabled by the installer)

### Changed
- Installer order: OS packages → verify → venv → Python packages → enable `piauto.service`

## [2.0.14] - 2026-09-02

### Fixed
- PWM fan profile, custom curves, and GPIO fan mode ignored after reboot (`FanAddon` kept DEFAULT_CONFIG instead of `config.json`)
- Custom profile id resolved before custom curves were loaded, so it fell back to Balanced on start
- OLED designer layout/enabled reset to stock templates after every restart
- OLED **Services** page (`top_cpu_1`/`2`/`3`) was always blank
- `pironman5.service` could die on boot (I2C/GPIO race) and stay down — now `Restart=always` and enabled on overlay install
- Calibration hold duty no longer sticks across reboot

### Changed
- systemd unit waits for `network-online.target` / filesystems, then auto-restarts every 5s if the process exits

## [2.0.13] - 2026-09-02

### Changed
- Fan page: large **Calibrate PWM max** panel at the top (plus header and PWM-section buttons)

## [2.0.12] - 2026-09-02

### Fixed
- Dashboard Network card showed Type **undefined** because `network_type` was never published in the live history stream

## [2.0.11] - 2026-09-02

### Added
- Dashboard left-nav **Fans** page: PWM profiles, custom step curves, RGB Pironman styles, calibration, live benchmark popup

## [2.0.10] - 2026-09-02

### Added
- Dashboard left-nav **Update** tab: last 3 GitHub Releases, with **Update** or **Downgrade** per tag
- `NOTES.md` how-to for install, Update tab, OLED, and fans
- `/update/` URL (old `/upgrade/` still works)

### Changed
- Installing a release uses `pip --force-reinstall` so older tags can downgrade
- `install.sh` sets `DEBIAN_FRONTEND=noninteractive` via `env` so apt does not treat it as a package name

## [2.0.9] - 2026-08-19

### Added
- Dashboard **Update** left-nav section: last 3 GitHub Releases, switch to any of them
- `GET /api/v1.0/get-upgrades`, `POST /api/v1.0/apply-upgrade`, upgrade status polling

### Changed
- PWM tower fan uses a tighter CPU temp curve and `pwm1` duty cycle (not kernel 0–4 only):
  off below 34°C, 25% at 34–38, 50% at 38–41, 75% at 41–43, 100% above 43°C
- One-time max-RPM calibration at first start, saved in `/opt/pironman5/fan_calibration.json`

## [Unreleased] - vendored Pironman 5 Max stack

### Added
- `vendor/pironman5/` — SunFounder pironman5 **1.3.18** (`1.3.x`) copied into this repo
- `vendor/sf_rpi_status/` — Raspberry Pi status helper, no extra git clone
- `install.sh` — one command full Max setup (`sudo bash install.sh`) without cloning sunfounder/pironman5
- `vendor/python/requirements-max.txt` — pip libraries used by Max (Flask, Pillow, …)

## [OLED Designer Phase 2] - 2026-05-19

### Added
- One-command Pironman 5 installer: `install-oled-designer.sh`
- Web OLED Designer at `/oled-designer`
- Editable built-in pages and custom OLED pages
- **Test on OLED**: render the current unsaved page on the physical OLED for 5 seconds
- **Apply to device**: persist designer layout and carousel order
- Native 14×14 monochrome built-in OLED icon set
- Bootstrap icon mapping to OLED-safe monochrome bitmaps
- Icon animations: `none`, `blink`, `pulse`, `spin`

### Fixed
- Dashboard script init failures that caused blank page lists/canvas/icons
- Designer preview calibration against the 128×64 SSD1306 display
- Repeated **Test on OLED** presses now retrigger the physical preview
- `pm_auto` package metadata now matches `pm_auto.__version__` so pip upgrades correctly
- Built-in and Bootstrap icon sizing to avoid stretched/fat pixels on OLED

## [1.2.24] - 2026-05-18

### Added (Tier 4)
- `CHANGELOG.md` (this file)
- `pm-auto-oled`: `--pages` custom carousel list, `--show`, alert threshold flags
- `pm-auto-oled-preview`: export all OLED pages to PNG without hardware
- Git release tags (`v1.2.x`) for pinned installs

### Changed
- `SSD1306` preview mode for headless layout rendering
- Unknown custom page ids are filtered with a warning log

## [1.2.23] - 2026-05-18

### Added (Dashboard Tier 2 — not on OLED)
- `dashboard_stats.get_dashboard_snapshot()` — hostname, uptime, storage free space
- `pm-auto-status` CLI
- `PMAuto.get_dashboard_status()` and callback publish every 5s

## [1.2.22] - 2026-05-18

### Added (Tier 3)
- Home IP bar shows interface name + address
- Heart page inset margin
- Refined 14×14 storage icons (SD / SSD / USB)
- Disk temperature on storage/temps pages (`smartctl`)
- `PWR!` undervoltage alert

## [1.2.21] - 2026-05-18

### Fixed
- CPU % sampling cached correctly for OLED
- Pi 5 GPU usage via `v3d/gpu_stats`

## [1.2.20] - 2026-05-18

### Added (Tier 2)
- OLED alert / WARNING flash
- Improved GPU % probes
- Fan page: TOWER RPM + SIDE on/off

## [1.2.18] - 2026-05-18

### Added
- OLED profiles (`full`, `minimal`, `server`), network page, tap → home
- `pm-auto-oled` CLI for profile/timing

## [1.2.13] - 2026-05-18

### Added
- Multi-page OLED carousel (home, storage, CPU, GPU, fans, RAM, temps, services, heart)
- Combined disk percent fix, storage mount filtering
