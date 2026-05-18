#!/usr/bin/env python3
"""Update OLED carousel settings in pironman5 config.json (works without new pironman5 CLI)."""

import argparse
import json
import sys
from pathlib import Path

PROFILES = ('full', 'minimal', 'server')


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


def main():
    parser = argparse.ArgumentParser(
        description='Set Pironman5 OLED page profile and timings in config.json',
    )
    parser.add_argument('-c', '--config-path', help='Path to pironman5 config.json')
    parser.add_argument(
        '-op', '--oled-pages-profile',
        nargs='?',
        choices=PROFILES,
        const='',
        help='Page set: full, minimal, server (no value = show current)',
    )
    parser.add_argument(
        '-ohd', '--oled-home-duration',
        nargs='?',
        type=int,
        const=-1,
        help='Home page seconds (no value = show current)',
    )
    parser.add_argument(
        '-opd', '--oled-page-duration',
        nargs='?',
        type=int,
        const=-1,
        help='Other pages seconds (no value = show current)',
    )
    args = parser.parse_args()

    path = find_config_path(args.config_path)
    if path is None:
        print('Error: config.json not found. Use -c /path/to/config.json', file=sys.stderr)
        sys.exit(1)

    cfg = load_config(path)
    sys_cfg = cfg.setdefault('system', {})
    changed = False

    if args.oled_pages_profile is not None:
        if args.oled_pages_profile == '':
            print(f"oled_pages_profile: {sys_cfg.get('oled_pages_profile', 'full')}")
        else:
            sys_cfg['oled_pages_profile'] = args.oled_pages_profile
            print(f"Set oled_pages_profile: {args.oled_pages_profile}")
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

    if not any([
        args.oled_pages_profile is not None,
        args.oled_home_duration is not None,
        args.oled_page_duration is not None,
    ]):
        parser.print_help()
        print(f'\nConfig file: {path}')
        print(f"oled_pages_profile: {sys_cfg.get('oled_pages_profile', 'full')}")
        print(f"oled_home_duration: {sys_cfg.get('oled_home_duration', 15)}")
        print(f"oled_page_duration: {sys_cfg.get('oled_page_duration', 5)}")
        return

    if changed:
        save_config(path, cfg)
        print(f'Saved: {path}')
        print('Restart service: sudo systemctl restart pironman5.service')


if __name__ == '__main__':
    main()
