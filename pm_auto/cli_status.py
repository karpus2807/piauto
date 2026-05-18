#!/usr/bin/env python3
"""Print dashboard Tier-2 stats (hostname, uptime, storage free) as JSON."""

import argparse
import json
import sys

from .dashboard_stats import get_dashboard_snapshot


def main():
    parser = argparse.ArgumentParser(
        description='Show hostname, uptime, and storage free space (for web dashboard dev).',
    )
    parser.add_argument(
        '--pretty', '-p', action='store_true', help='Indented JSON output',
    )
    args = parser.parse_args()
    data = get_dashboard_snapshot()
    indent = 2 if args.pretty else None
    json.dump(data, sys.stdout, indent=indent)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
