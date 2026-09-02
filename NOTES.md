# PiAuto notes — how to use

Practical guide for the Pironman 5 Max stack in this repo: OLED carousel, dashboard designer, PWM/GPIO fans, and the dashboard **Update** tab.

Repo: [github.com/karpus2807/piauto](https://github.com/karpus2807/piauto)

Dashboard: `http://<pi-ip>:34001` or `https://piauto.krserver.cloud`

---

## Install on a device

**One command** (fresh Pi or existing Pironman 5 — no SunFounder installer first):

```bash
curl -fsSL https://raw.githubusercontent.com/karpus2807/piauto/main/install.sh | sudo bash
```

Pinned tag (installer from **main**, packages from that tag):

```bash
curl -fsSL https://raw.githubusercontent.com/karpus2807/piauto/main/install.sh | sudo bash -s -- --ref v2.0.15
```

The installer, in order:

1. Installs OS packages (`python3`, `git`, `i2c-tools`, build libs, …) and **verifies** them
2. Clones this repo if you used curl (or uses the local checkout)
3. Creates `/opt/pironman5/venv` if needed
4. Installs vendored `pironman5` + `sf_rpi_status` + this repo’s `pm_auto` / `pm_dashboard`
5. Enables systemd **`piauto.service`** (`Restart=always`) and starts it

If an old `pironman5.service` is running, it is disabled so only **piauto** owns the fans/OLED.

```bash
sudo systemctl status piauto
sudo journalctl -u piauto -f
sudo piauto
```

Local checkout (same script, no curl):

```bash
git clone https://github.com/karpus2807/piauto.git
cd piauto
sudo bash install.sh
```

Existing Max venv overlay only (keeps `/opt/pironman5/config.json`):

```bash
cd /path/to/piauto
bash install-oled-designer.sh
```

Then hard-refresh the browser (`Ctrl+Shift+R`).

---

## Dashboard left menu

Stock tabs (Dashboard, History, Log, …) plus two injected items:

| Menu | Opens | What it does |
|------|--------|----------------|
| **OLED** | `/oled-designer/` | Edit 128×64 pages, Test on OLED, Apply to device |
| **Update** | `/update/` | Last **3 GitHub Releases** — update or downgrade |

The injector is `pm_dashboard/www/oled-nav-patch.js`. Direct URLs still work if the left nav is missing.

---

## Update / downgrade (left-nav **Update**)

1. Open the dashboard → click **Update**.
2. The page lists the last 3 GitHub Releases of `karpus2807/piauto`.
3. Each card shows notes, whether it is **latest** / **running** / **older**.
4. Click:
   - **Update to this version** — newer than what is running
   - **Downgrade to this version** — older than what is running
5. Confirm. `pm_auto` + `pm_dashboard` install from that tag, then **`piauto`** restarts (~1 minute).

Refresh reloads the GitHub list (2-minute cache). Until a GitHub **Release** exists, the API falls back to git **tags**.

### APIs

| Method | Path | Role |
|--------|------|------|
| GET | `/api/v1.0/get-upgrades` | Last 3 releases + current versions (`?refresh=1` bypasses cache) |
| GET | `/api/v1.0/upgrade-status` | Background job: idle / running / success / error |
| POST | `/api/v1.0/apply-upgrade` | Body `{"tag":"v2.0.10"}` — only tags in that last-3 list |

Status files: `/opt/pironman5/upgrade-status.json`, `/opt/pironman5/installed-release.json`, log `/var/log/pironman5/upgrade.log`.

### Publish a release so the panel can see it

```bash
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file CHANGELOG.md
```

Bump `pm_auto/pm_auto/version.py` and `pm_dashboard/pm_dashboard/version.py` together.

---

## OLED

Designer: `http://<pi-ip>:34001/oled-designer`

- Edit built-in pages (`home`, `storage`, `network`, `cpu`, `gpu`, `fans`, `ram`, `temps`, `services`, `heart`) or add custom pages.
- **Test on OLED** — 5 second preview, not saved.
- **Apply to device** — writes `oled_pages` / `oled_designer_layout` in `/opt/pironman5/config.json`.

CLI:

```bash
sudo /opt/pironman5/venv/bin/pm-auto-oled --show
sudo /opt/pironman5/venv/bin/pm-auto-oled --pages home,storage,network,heart
sudo systemctl restart pironman5
```

---

## Fans

`pm_auto/addons/fan.py` runs every 1s from CPU temp (`thermal_zone0`).

| Fan | Hardware | UI |
|-----|----------|-----|
| PWM **tower** | Pi 5 `pwm1` (0–255 duty) | OLED `TOWER nnnn RPM` |
| GPIO **side** | GPIO 6 on/off | OLED `SIDE ON/OFF` |

PWM curve comes from the **Fans** page profile (Silent / Quiet / Balanced / custom steps). Saved in `/opt/pironman5/config.json` and restored after reboot. First start calibrates max RPM to `/opt/pironman5/fan_calibration.json`.

Dashboard fan-mode / LED APIs change the **side** GPIO fan only, not the PWM curve.

`piauto.service` is enabled on install and uses `Restart=always` so fans/OLED/dashboard come back after reboot. (Older boxes may still have `pironman5.service`; the new installer replaces it with `piauto`.)

---

## Layout of the code

```
piauto/
  install.sh                 # curl-pipe full install (deps → venv → piauto.service)
  deploy/piauto.service      # systemd unit (service name: piauto)
  install-oled-designer.sh   # overlay into existing /opt/pironman5/venv
  NOTES.md                   # this file
  pm_auto/                   # automation: fans, OLED, RGB, power
  pm_dashboard/              # Flask UI on :34001
    pm_dashboard/upgrade_routes.py
    pm_dashboard/www/upgrade/          # Update tab page
    pm_dashboard/www/oled-nav-patch.js
    pm_dashboard/www/oled-designer/
  vendor/pironman5/          # SunFounder 1.3.18, not cloned at install time
  vendor/sf_rpi_status/
```

Runtime: systemd `piauto.service` → `/usr/local/bin/piauto start` → `PMAuto` + `PMDashboard`. Config stays at `/opt/pironman5/config.json` (hardware paths are unchanged).

---

## Restore SunFounder stock packages

```bash
bash install-oled-designer.sh --restore-stock
```
