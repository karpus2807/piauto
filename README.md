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

## Install (standalone)

```bash
sudo apt-get install -y python3-pip python3-dev liblgpio-dev \
  libfreetype6-dev libjpeg-dev libopenjp2-7 i2c-tools
pip3 install git+https://github.com/karpus2807/piauto.git@main
```

## Install (with Pironman 5)

From [pironman5](https://github.com/sunfounder/pironman5) installer — `install.py` pulls this repo automatically:

```bash
sudo python3 install.py
```

## Upgrade on device

```bash
sudo systemctl stop pironman5.service
sudo /opt/pironman5/venv/bin/pip3 uninstall pm_auto -y
sudo /opt/pironman5/venv/bin/pip3 install --upgrade git+https://github.com/karpus2807/piauto.git@main
sudo systemctl start pironman5.service
```

## OLED profile / timing (no new pironman5 CLI required)

After installing piauto, use `pm-auto-oled` (works even if `pironman5 -op` is not available):

```bash
sudo /opt/pironman5/venv/bin/pm-auto-oled -op minimal
sudo /opt/pironman5/venv/bin/pm-auto-oled -ohd 20 -opd 8
sudo /opt/pironman5/venv/bin/pm-auto-oled -op
sudo systemctl restart pironman5.service
```

Profiles: `full`, `minimal`, `server`

## Based on

Forked from [sunfounder/pm_auto](https://github.com/sunfounder/pm_auto) with OLED carousel and storage formatting changes.
