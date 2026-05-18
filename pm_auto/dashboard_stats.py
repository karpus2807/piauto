"""
Dashboard-ready system info (Tier 2).

Not used by the OLED UI — intended for pm_dashboard / custom web frontends.
"""

import socket
import time

from .system_stats import get_combined_disk, get_storage_mounts_usage
from .utils import (
    format_storage_bytes,
    format_storage_free_display,
    format_storage_pair,
)


def get_hostname():
    try:
        return socket.gethostname()
    except OSError:
        return None


def get_uptime_seconds():
    try:
        import psutil
        return max(0, int(time.time() - psutil.boot_time()))
    except Exception:
        pass
    try:
        with open('/proc/uptime', 'r') as f:
            return int(float(f.read().split()[0]))
    except OSError:
        return None


def format_uptime(seconds):
    if seconds is None:
        return None
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f'{days}d')
    if hours:
        parts.append(f'{hours}h')
    if minutes or not parts:
        parts.append(f'{minutes}m')
    return ' '.join(parts)


def get_uptime_info():
    seconds = get_uptime_seconds()
    return {
        'uptime_seconds': seconds,
        'uptime': format_uptime(seconds),
    }


def _mount_dashboard_row(mount):
    used = mount['used']
    total = mount['total']
    free = mount.get('free', max(0, total - used))
    pair, percent_used = format_storage_pair(used, total)
    free_label, percent_free = format_storage_free_display(free, total)
    used_val, _ = format_storage_bytes(used)
    total_val, unit = format_storage_bytes(total)
    free_val, _ = format_storage_bytes(free)

    return {
        'mountpoint': mount['mountpoint'],
        'device': mount['device'],
        'short_dev': mount.get('short_dev', ''),
        'kind': mount.get('kind', 'DISK'),
        'total_bytes': total,
        'used_bytes': used,
        'free_bytes': free,
        'percent_used': percent_used,
        'percent_free': percent_free,
        'used_total_display': pair,
        'free_display': free_label,
        'used_display': f'{used_val} {unit}',
        'total_display': f'{total_val} {unit}',
        'free_value_display': f'{free_val} {unit}',
    }


def get_storage_dashboard():
    mounts = get_storage_mounts_usage()
    combined = get_combined_disk(mounts)
    combined_free = max(0, combined['total'] - combined['used'])
    pair, pct_used = format_storage_pair(combined['used'], combined['total'])
    free_label, pct_free = format_storage_free_display(combined_free, combined['total'])

    return {
        'combined': {
            'total_bytes': combined['total'],
            'used_bytes': combined['used'],
            'free_bytes': combined_free,
            'percent_used': pct_used,
            'percent_free': pct_free,
            'mounted': combined['mounted'],
            'used_total_display': pair,
            'free_display': free_label,
        },
        'mounts': [_mount_dashboard_row(m) for m in mounts],
    }


def get_system_info():
    """Hostname + uptime for dashboard header widgets."""
    uptime = get_uptime_info()
    return {
        'hostname': get_hostname(),
        **uptime,
    }


def get_dashboard_snapshot():
    """
    Full Tier-2 payload for web dashboard / status callbacks.

    Example::

        from pm_auto.dashboard_stats import get_dashboard_snapshot
        data = get_dashboard_snapshot()
        print(data['system']['hostname'], data['system']['uptime'])
        for m in data['storage']['mounts']:
            print(m['kind'], m['free_display'])
    """
    return {
        'system': get_system_info(),
        'storage': get_storage_dashboard(),
    }
