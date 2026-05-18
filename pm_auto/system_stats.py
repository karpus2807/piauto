"""Helpers for OLED multi-page stats (mounts, GPU, top processes)."""

import os
import time

_top_proc_cache = {'at': 0.0, 'rows': []}
_TOP_PROC_TTL = 5.0

_EXCLUDED_FSTYPES = frozenset({
    'squashfs', 'tmpfs', 'devtmpfs', 'overlay', 'autofs',
    'cgroup2', 'proc', 'sysfs', 'efivarfs', 'bpf',
})

_EXCLUDED_MOUNT_EXACT = frozenset({
    '/boot', '/boot/firmware', '/boot/efi', '/efi', '/recovery',
    '/var/lib/nfs/rpc_pipefs',
})

_EXCLUDED_MOUNT_PREFIXES = (
    '/boot/',
    '/snap/',
    '/run/',
    '/sys/',
    '/proc/',
    '/dev/',
)


def _storage_kind(device, mountpoint):
    """Human label: SD, SSD, USB, or ROOT."""
    dev = (device or '').lower()
    mp = mountpoint or ''
    if dev.startswith('nvme') or 'nvme' in dev:
        return 'SSD'
    if 'mmcblk' in dev or dev.startswith('/dev/mmc'):
        if mp == '/':
            return 'SD'
        return 'SD'
    if dev.startswith('sd') and 'mmc' not in dev:
        return 'USB'
    if mp.startswith('/media/') or mp.startswith('/mnt/'):
        return 'USB' if 'mmc' not in dev and 'nvme' not in dev else 'DATA'
    if mp == '/':
        return 'SD'
    return 'DISK'


def is_user_storage_mount(part, total_bytes):
    """True for SD root, NVMe SSD, and USB data volumes — not boot/firmware."""
    mp = part.mountpoint
    fstype = (part.fstype or '').lower()
    dev = part.device or ''

    if not mp or fstype in _EXCLUDED_FSTYPES:
        return False
    if mp in _EXCLUDED_MOUNT_EXACT:
        return False
    for prefix in _EXCLUDED_MOUNT_PREFIXES:
        if mp.startswith(prefix):
            return False

    # Main OS root filesystem
    if mp == '/':
        return True

    # USB / external / custom mounts
    if mp.startswith('/media/') or mp.startswith('/mnt/'):
        return True

    # Block device data partitions (mmc, nvme, usb sdX)
    base = dev.replace('/dev/', '')
    if any(tag in base for tag in ('nvme', 'mmcblk', 'sd')):
        # Skip typical small boot partition unless it's the only root
        if base.endswith('p1') and total_bytes < 768 * 1024 * 1024 and mp != '/':
            if not mp.startswith('/media') and not mp.startswith('/mnt'):
                return False
        return True

    return False


def get_storage_mounts_usage():
    """Mounted user storage only: SD (/) , SSD (nvme), USB (/media, /mnt)."""
    from psutil import disk_partitions, disk_usage

    mounts = []
    seen = set()
    for part in disk_partitions(all=False):
        mp = part.mountpoint
        if not mp or mp in seen:
            continue
        try:
            usage = disk_usage(mp)
        except (PermissionError, OSError):
            continue
        if not is_user_storage_mount(part, usage.total):
            continue
        seen.add(mp)
        dev = part.device or ''
        short_dev = dev.replace('/dev/', '')[:12]
        mounts.append({
            'mountpoint': mp,
            'device': dev,
            'short_dev': short_dev,
            'kind': _storage_kind(dev, mp),
            'total': usage.total,
            'used': usage.used,
            'free': usage.free,
            'percent': usage.percent,
        })

    order = {'SD': 0, 'SSD': 1, 'USB': 2, 'DATA': 3, 'DISK': 4}
    mounts.sort(key=lambda m: (order.get(m['kind'], 9), m['mountpoint']))
    return mounts


def get_mounts_usage():
    """Alias: user storage mounts only (no /boot, /boot/firmware)."""
    return get_storage_mounts_usage()


def get_combined_disk(mounts=None):
    """Sum of used/total across user storage mounts; percent from bytes."""
    if mounts is None:
        mounts = get_storage_mounts_usage()
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
