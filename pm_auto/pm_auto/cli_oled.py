#!/usr/bin/env python3
"""Update OLED carousel settings in pironman5 config.json (works without new pironman5 CLI)."""

import argparse
import json
import sys
from pathlib import Path

from .oled import OLED_PAGE_IDS, OLED_PAGE_PROFILES

PROFILES = tuple(OLED_PAGE_PROFILES.keys())


def find_config_path(explicit=None):
    if explicit:
        return Path(explicit)
    candidates = []
    try:
        from importlib.resources import files as resource_files
        candidates.append(Path(str(resource_files('pironman5').joinpath('config.json'))))
    except Exception:
        pass
    candidates.extend([
        Path('/opt/pironman5/venv/lib/python3.13/site-packages/pironman5/config.json'),
        Path('/opt/pironman5/venv/lib/python3.12/site-packages/pironman5/config.json'),
        Path('/opt/pironman5/venv/lib/python3.11/site-packages/pironman5/config.json'),
    ])
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_config(path):
    text = path.read_text()
    if not text.strip():
        return {'system': {}}
    return json.loads(text)


def save_config(path, data):
    path.write_text(json.dumps(data, indent=4) + '\n')


def _parse_pages(value):
    pages = [p.strip() for p in value.split(',') if p.strip()]
    valid = set(OLED_PAGE_IDS)
    bad = [p for p in pages if p not in valid]
    if bad:
        print(f'Error: unknown page id(s): {", ".join(bad)}', file=sys.stderr)
        print(f'Valid: {", ".join(OLED_PAGE_IDS)}', file=sys.stderr)
        sys.exit(1)
    if not pages:
        print('Error: empty page list', file=sys.stderr)
        sys.exit(1)
    return pages


def _show_all(sys_cfg):
    print(f"oled_pages_profile: {sys_cfg.get('oled_pages_profile', 'full')}")
    pages = sys_cfg.get('oled_pages')
    if pages:
        print(f"oled_pages: {pages if isinstance(pages, str) else ','.join(pages)}")
    print(f"oled_home_duration: {sys_cfg.get('oled_home_duration', 15)}")
    print(f"oled_page_duration: {sys_cfg.get('oled_page_duration', 5)}")
    print(f"oled_alert_enable: {sys_cfg.get('oled_alert_enable', True)}")
    print(f"oled_alert_duration: {sys_cfg.get('oled_alert_duration', 3)}")
    print(f"oled_alert_cooldown: {sys_cfg.get('oled_alert_cooldown', 45)}")
    print(f"oled_alert_cpu_temp: {sys_cfg.get('oled_alert_cpu_temp', 80)}")
    print(f"oled_alert_cpu_percent: {sys_cfg.get('oled_alert_cpu_percent', 90)}")
    print(f"oled_alert_disk_percent: {sys_cfg.get('oled_alert_disk_percent', 90)}")
    print(f"oled_alert_gpu_temp: {sys_cfg.get('oled_alert_gpu_temp', 80)}")
    print(f"oled_alert_undervoltage: {sys_cfg.get('oled_alert_undervoltage', True)}")


def main():
    parser = argparse.ArgumentParser(
        description='Set Pironman5 OLED profile, custom pages, timings, and alerts in config.json',
    )
    parser.add_argument('-c', '--config-path', help='Path to pironman5 config.json')
    parser.add_argument(
        '--show', action='store_true',
        help='Print all OLED-related config values',
    )
    parser.add_argument(
        '-op', '--oled-pages-profile',
        nargs='?',
        choices=PROFILES,
        const='',
        help=f'Profile: {", ".join(PROFILES)} (no value = show current)',
    )
    parser.add_argument(
        '--pages', '--oled-pages',
        dest='oled_pages',
        metavar='IDS',
        help=f'Custom page list, comma-separated (sets profile custom). '
             f'Ids: {", ".join(OLED_PAGE_IDS)}',
    )
    parser.add_argument(
        '-ohd', '--oled-home-duration',
        nargs='?', type=int, const=-1,
        help='Home page seconds (no value = show current)',
    )
    parser.add_argument(
        '-opd', '--oled-page-duration',
        nargs='?', type=int, const=-1,
        help='Other pages seconds (no value = show current)',
    )
    parser.add_argument(
        '--alert-enable', dest='alert_enable', action='store_const', const=True,
        help='Enable OLED warning flashes',
    )
    parser.add_argument(
        '--no-alert-enable', dest='alert_enable', action='store_const', const=False,
        help='Disable OLED warning flashes',
    )
    parser.add_argument('--alert-cpu-temp', type=float, metavar='C')
    parser.add_argument('--alert-cpu-percent', type=float, metavar='PCT')
    parser.add_argument('--alert-disk-percent', type=float, metavar='PCT')
    parser.add_argument('--alert-gpu-temp', type=float, metavar='C')
    parser.add_argument('--alert-duration', type=int, metavar='SEC')
    parser.add_argument('--alert-cooldown', type=int, metavar='SEC')
    parser.add_argument(
        '--alert-undervoltage', dest='alert_undervoltage',
        action='store_const', const=True,
    )
    parser.add_argument(
        '--no-alert-undervoltage', dest='alert_undervoltage',
        action='store_const', const=False,
    )
    args = parser.parse_args()

    path = find_config_path(args.config_path)
    if path is None:
        print('Error: config.json not found. Use -c /path/to/config.json', file=sys.stderr)
        sys.exit(1)

    cfg = load_config(path)
    sys_cfg = cfg.setdefault('system', {})
    changed = False

    if args.show:
        print(f'Config file: {path}')
        _show_all(sys_cfg)
        return

    if args.oled_pages_profile is not None:
        if args.oled_pages_profile == '':
            print(f"oled_pages_profile: {sys_cfg.get('oled_pages_profile', 'full')}")
        else:
            sys_cfg['oled_pages_profile'] = args.oled_pages_profile
            if args.oled_pages_profile != 'custom':
                sys_cfg.pop('oled_pages', None)
            print(f"Set oled_pages_profile: {args.oled_pages_profile}")
            changed = True

    if args.oled_pages is not None:
        pages = _parse_pages(args.oled_pages)
        sys_cfg['oled_pages'] = ','.join(pages)
        sys_cfg['oled_pages_profile'] = 'custom'
        print(f"Set oled_pages: {','.join(pages)}")
        changed = True

    if args.oled_home_duration is not None:
        if args.oled_home_duration == -1:
            print(f"oled_home_duration: {sys_cfg.get('oled_home_duration', 15)}")
        else:
            sys_cfg['oled_home_duration'] = max(3, args.oled_home_duration)
            print(f"Set oled_home_duration: {sys_cfg['oled_home_duration']}")
            changed = True

    if args.oled_page_duration is not None:
        if args.oled_page_duration == -1:
            print(f"oled_page_duration: {sys_cfg.get('oled_page_duration', 5)}")
        else:
            sys_cfg['oled_page_duration'] = max(2, args.oled_page_duration)
            print(f"Set oled_page_duration: {sys_cfg['oled_page_duration']}")
            changed = True

    alert_map = (
        ('alert_enable', 'oled_alert_enable'),
        ('alert_cpu_temp', 'oled_alert_cpu_temp'),
        ('alert_cpu_percent', 'oled_alert_cpu_percent'),
        ('alert_disk_percent', 'oled_alert_disk_percent'),
        ('alert_gpu_temp', 'oled_alert_gpu_temp'),
        ('alert_duration', 'oled_alert_duration'),
        ('alert_cooldown', 'oled_alert_cooldown'),
        ('alert_undervoltage', 'oled_alert_undervoltage'),
    )
    for arg_name, cfg_key in alert_map:
        value = getattr(args, arg_name)
        if value is not None:
            sys_cfg[cfg_key] = value
            print(f'Set {cfg_key}: {value}')
            changed = True

    if not changed:
        parser.print_help()
        print(f'\nConfig file: {path}')
        _show_all(sys_cfg)
        return

    save_config(path, cfg)
    print(f'Saved: {path}')
    print('Restart service: sudo systemctl restart pironman5.service')


if __name__ == '__main__':
    main()
