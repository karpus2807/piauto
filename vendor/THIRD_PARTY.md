# Third-party sources vendored in this tree

PiAuto is a Pironman 5 Max upgrade. These upstream GPL-2.0 packages are
copied into `vendor/` so a fresh Pi does **not** need to `git clone`
SunFounder `pironman5` / `sf_rpi_status`.

| Path | Upstream | Branch / version |
|------|----------|------------------|
| `vendor/pironman5/` | https://github.com/sunfounder/pironman5 | `1.3.x` (`1.3.18`) |
| `vendor/sf_rpi_status/` | https://github.com/sunfounder/sf_rpi_status | `main` |

Our OLED/dashboard forks stay at the repo root:

| Path | Role |
|------|------|
| `pm_auto/` | Max-compatible automation + OLED designer renderer |
| `pm_dashboard/` | Dashboard + OLED designer UI |

Python *libraries* (Flask, Pillow, …) are listed in
`vendor/python/requirements-max.txt`. If `vendor/python/wheels/` exists,
`install.sh` installs from those wheels first (offline-friendly).
Otherwise pip uses PyPI — still **no** SunFounder git clone.

OS packages (apt): Python, JPEG/Freetype, i2c-tools, optional InfluxDB.
Those cannot live in git as full .deb files; `install.sh` installs them
from the Pi’s apt repos.
