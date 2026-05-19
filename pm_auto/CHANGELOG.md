# Changelog

All notable changes to [piauto](https://github.com/karpus2807/piauto) (`pm_auto`).

Format based on [Keep a Changelog](https://keepachangelog.com/).

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
