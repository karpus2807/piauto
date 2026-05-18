#!/usr/bin/env python3
"""Render OLED pages to PNG files without hardware (layout dev / CI)."""

import argparse
import sys
from pathlib import Path

from .oled import OLED, OLED_DEFAULT_CONFIG, OLED_PAGE_PROFILES


def main():
    parser = argparse.ArgumentParser(
        description='Export OLED carousel pages as PNG (no I2C / display required)',
    )
    parser.add_argument(
        '-o', '--output-dir',
        default='/tmp',
        help='Directory for PNG files (default: /tmp)',
    )
    parser.add_argument(
        '-op', '--profile',
        choices=tuple(OLED_PAGE_PROFILES.keys()),
        default='full',
        help='Page profile to render',
    )
    parser.add_argument(
        '--pages',
        help='Custom comma-separated page ids (overrides --profile)',
    )
    parser.add_argument(
        '--warn',
        action='store_true',
        help='Also render sample WARNING flash frame',
    )
    args = parser.parse_args()

    config = dict(OLED_DEFAULT_CONFIG)
    config['oled_preview'] = True
    if args.pages:
        config['oled_pages'] = args.pages
        config['oled_pages_profile'] = 'custom'
    else:
        config['oled_pages_profile'] = args.profile

    oled = OLED(config)
    if not oled.is_ready():
        print('Error: failed to init preview OLED', file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    oled._rebuild_pages()
    written = []
    for idx, page in enumerate(oled._page_sequence):
        oled._page_index = idx
        oled.draw_current_page()
        pid = page['id']
        if 'slide' in page:
            name = f'oled_{pid}_{page["slide"]}'
        else:
            name = f'oled_{pid}'
        path = out_dir / f'{name}.png'
        oled.oled.save_frame(str(path))
        written.append(path)

    if args.warn:
        oled.draw_warn(['PWR! LOW V', 'CPU 85C', 'DISK 92%'])
        path = out_dir / 'oled_warn.png'
        oled.oled.save_frame(str(path))
        written.append(path)

    for path in written:
        print(path)
    print(f'Wrote {len(written)} file(s) to {out_dir}')


if __name__ == '__main__':
    main()
