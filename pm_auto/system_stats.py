"""Helpers for OLED multi-page stats (mounts, GPU, top processes)."""

import os
import time

_top_proc_cache = {'at': 0.0, 'rows': []}
_TOP_PROC_TTL = 5.0


def get_mounts_usage():
    """All mounted partitions with usage. Includes SD, NVMe, USB when mounted."""
    from psutil import disk_partitions, disk_usage

    mounts = []
    seen = set()
    for part in disk_partitions(all=False):
        mp = part.mountpoint
        if not mp or mp in seen:
            continue
        if part.fstype in ('squashfs', 'tmpfs', 'devtmpfs', 'overlay'):
            continue
        try:
            usage = disk_usage(mp)
        except (PermissionError, OSError):
            continue
        seen.add(mp)
        dev = part.device or ''
        short_dev = dev.replace('/dev/', '')[:12]
        mounts.append({
            'mountpoint': mp,
            'device': dev,
            'short_dev': short_dev,
            'total': usage.total,
            'used': usage.used,
            'free': usage.free,
            'percent': usage.percent,
        })
    mounts.sort(key=lambda m: m['mountpoint'])
    return mounts


def get_combined_disk(mounts=None):
    """Sum of used/total across mounts; percent from bytes, not sum of percents."""
    if mounts is None:
        mounts = get_mounts_usage()
    total = sum(m['total'] for m in mounts)
    used = sum(m['used'] for m in mounts)
    if total <= 0:
        return {'total': 0, 'used': 0, 'percent': 0.0, 'mounted': False}
    return {
        'total': total,
        'used': used,
        'percent': round(used / total * 100, 1),
        'mounted': True,
    }


def get_gpu_usage_percent():
    """Best-effort GPU busy % on Raspberry Pi. None if unavailable."""
    from .utils import run_command

    # Legacy VideoCore (some Pi OS images)
    status, out = run_command('vcgencmd measure_busy 2>/dev/null')
    if status == 0 and out.strip():
        try:
            if 'busy=' in out:
                return float(out.split('=')[1].strip().rstrip('%'))
            return float(out.strip().rstrip('%'))
        except ValueError:
            pass

    sysfs_candidates = [
        '/sys/class/drm/card1/device/gpu_busy_percent',
        '/sys/class/drm/card0/device/gpu_busy_percent',
        '/sys/kernel/debug/dri/0/gt0_busy_percent',
    ]
    for path in sysfs_candidates:
        if os.path.isfile(path):
            try:
                with open(path, 'r') as f:
                    val = float(f.read().strip())
                if 0 <= val <= 100:
                    return round(val, 1)
            except (ValueError, OSError):
                continue

    return None


def get_top_processes_cpu(count=3):
    """Top N processes by CPU %. Cached for _TOP_PROC_TTL seconds."""
    global _top_proc_cache
    now = time.time()
    if now - _top_proc_cache['at'] < _TOP_PROC_TTL and _top_proc_cache['rows']:
        return _top_proc_cache['rows'][:count]

    import psutil
    psutil.cpu_percent(interval=0.1)
    rows = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            info = proc.info
            cpu = info.get('cpu_percent') or 0.0
            if cpu <= 0:
                continue
            name = (info.get('name') or '?')[:14]
            rows.append({'name': name, 'cpu_percent': round(cpu, 1)})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    rows.sort(key=lambda r: r['cpu_percent'], reverse=True)
    _top_proc_cache = {'at': now, 'rows': rows}
    return rows[:count]
