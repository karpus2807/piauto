# pm_dashboard (Pironman 5 fork)

Flask dashboard on port **34001** with an advanced **Control Center** at `/control`.

## Control Center (v1.3.0+)

- **URL:** `http://<pi-ip>:34001/control`
- One-click **presets** (Quiet, Performance, Server, Night, RGB, OLED off)
- Tabs: RGB, Fans, OLED, Alerts, System
- Sliders / toggles / chips — auto-save to `config.json`
- Live bar: hostname, uptime, CPU, storage free (via `pm_auto` Tier 2)

### API (extensions)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1.0/get-control-schema` | Fields, presets, current config |
| GET | `/api/v1.0/get-live-status` | History + dashboard snapshot |
| GET | `/api/v1.0/get-oled-options` | Disk + network lists |
| POST | `/api/v1.0/apply-preset` | `{"preset": "quiet_desktop"}` |
| POST | `/api/v1.0/set-system-config` | `{"system": { ...partial }}` |

Requires **pm_auto** with `dashboard_stats` (piauto v1.2.23+).

## Install

With pironman5 `install.py` (uses `./pm_dashboard` from this monorepo), or:

```bash
pip install ./pm_dashboard
```

## Based on

[sunfounder/pm_dashboard](https://github.com/sunfounder/pm_dashboard) @ 1.2.10 + control center.
