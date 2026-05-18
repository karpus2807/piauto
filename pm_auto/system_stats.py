"""Helpers for OLED multi-page stats (mounts, GPU, top processes)."""

import os
import time

_top_proc_cache = {'at': 0.0, 'rows': []}
_TOP_PROC_TTL = 5.0

_cpu_pct_cache = {'value': 0.0, 'updated_at': 0.0, 'primed': False}
_CPU_PCT_REFRESH = 0.85

_gpu_v3d_state = {'last_at': 0.0, 'last_runtime': None, 'percent': None}

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


_gpu_usage_reader = None


def get_system_cpu_percent():
    """System CPU 0–100%, sampled once per OLED tick (avoids bogus interval=None spam)."""
    import psutil

    now = time.time()
    if not _cpu_pct_cache['primed']:
        _cpu_pct_cache['value'] = round(psutil.cpu_percent(interval=0.05), 1)
        _cpu_pct_cache['primed'] = True
        _cpu_pct_cache['updated_at'] = now
        return _cpu_pct_cache['value']

    if now - _cpu_pct_cache['updated_at'] >= _CPU_PCT_REFRESH:
        _cpu_pct_cache['value'] = round(psutil.cpu_percent(interval=None), 1)
        _cpu_pct_cache['updated_at'] = now

    return max(0.0, min(100.0, _cpu_pct_cache['value']))


def _parse_percent_value(raw):
    if raw is None:
        return None
    text = str(raw).strip().lower()
    for token in ('busy_percent=', 'busy=', 'load=', 'utilization='):
        if token in text:
            text = text.split(token, 1)[1]
    text = text.strip().rstrip('%').split()[0]
    try:
        val = float(text)
    except ValueError:
        return None
    if 0 <= val <= 100:
        return round(val, 1)
    return None


def _gpu_from_vcgencmd_busy():
    from .utils import run_command
    for cmd in (
        'vcgencmd measure_busy',
        'vcgencmd measure_busy_core',
    ):
        status, out = run_command(f'{cmd} 2>/dev/null')
        if status == 0:
            val = _parse_percent_value(out)
            if val is not None:
                return val
    return None


def _v3d_gpu_stats_paths():
    import glob
    paths = []
    for pattern in (
        '/sys/devices/platform/axi/1002000000.v3d/gpu_stats',
        '/sys/devices/platform/v3dbus/*/gpu_stats',
        '/sys/devices/platform/*/*v3d*/gpu_stats',
    ):
        paths.extend(glob.glob(pattern))
    return paths


def _sum_v3d_runtime_ns(path):
    total = 0
    with open(path, 'r') as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            val = _parse_percent_value(stripped)
            if val is not None and 'busy' in stripped.lower():
                return val
            parts = stripped.split()
            if len(parts) < 4:
                continue
            try:
                total += int(parts[3])
            except ValueError:
                continue
    return total


def _gpu_from_v3d_gpu_stats():
    """Pi 5 / kernel 6.8+: busy % from cumulative V3D queue runtime (nanoseconds)."""
    paths = _v3d_gpu_stats_paths()
    if not paths:
        return None
    try:
        runtime_sum = _sum_v3d_runtime_ns(paths[0])
    except OSError:
        return None

    now = time.time()
    last_rt = _gpu_v3d_state['last_runtime']
    last_at = _gpu_v3d_state['last_at']
    _gpu_v3d_state['last_runtime'] = runtime_sum
    _gpu_v3d_state['last_at'] = now

    if last_rt is None or now - last_at < 0.25:
        return _gpu_v3d_state.get('percent')

    delta_ns = max(0, runtime_sum - last_rt)
    delta_t = now - last_at
    if delta_t <= 0:
        return _gpu_v3d_state.get('percent')

    pct = round((delta_ns / 1e9) / delta_t * 100, 1)
    pct = max(0.0, min(100.0, pct))
    _gpu_v3d_state['percent'] = pct
    return pct


def _gpu_from_debugfs_usage():
    import glob
    for path in glob.glob('/sys/kernel/debug/dri/*/gpu_usage'):
        try:
            with open(path, 'r') as f:
                val = _parse_percent_value(f.read())
            if val is not None:
                return val
        except OSError:
            continue
    return None


def _gpu_from_sysfs_paths():
    import glob
    patterns = [
        '/sys/class/drm/card*/device/gpu_busy_percent',
        '/sys/class/drm/card*/device/load',
        '/sys/class/misc/v3d/device/gpu_busy',
        '/sys/kernel/debug/dri/*/gt*/busy_percent',
        '/sys/kernel/debug/dri/*/gt*/gt0_busy_percent',
    ]
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                with open(path, 'r') as f:
                    val = _parse_percent_value(f.read())
                if val is not None:
                    return val
            except OSError:
                continue
    return None


def _gpu_from_vcgencmd_oom_frac():
    """Approximate load from allocated GPU mem vs total when reported."""
    from .utils import run_command
    status, out = run_command('vcgencmd get_mem gpu 2>/dev/null')
    if status != 0 or 'gpu=' not in out:
        return None
    try:
        part = out.split('gpu=')[1].split()[0].lower()
        if part.endswith('m'):
            used_m = float(part[:-1])
        else:
            return None
    except ValueError:
        return None
    status, arm = run_command('vcgencmd get_mem arm 2>/dev/null')
    if status != 0:
        return None
    # Heuristic only when GPU mem is non-trivial; not true utilization.
    if used_m < 16:
        return 0.0
    if used_m > 480:
        return 100.0
    return round(min(100.0, used_m / 5.0), 1)


def get_gpu_usage_percent():
    """Best-effort GPU busy % on Raspberry Pi. Caches first working method."""
    global _gpu_usage_reader
    if _gpu_usage_reader is not None:
        return _gpu_usage_reader()

    readers = (
        _gpu_from_v3d_gpu_stats,
        _gpu_from_debugfs_usage,
        _gpu_from_sysfs_paths,
        _gpu_from_vcgencmd_busy,
    )
    for reader in readers:
        val = reader()
        if val is not None:
            if reader is not _gpu_from_v3d_gpu_stats:
                _gpu_usage_reader = reader
            return val
    return _gpu_v3d_state.get('percent')


def get_max_storage_percent(mounts=None):
    if mounts is None:
        mounts = get_storage_mounts_usage()
    if not mounts:
        return 0.0
    return max(m['percent'] for m in mounts)


def collect_oled_alerts(
    cpu_temp_c=None,
    cpu_percent=None,
    gpu_temp_c=None,
    disk_percent=None,
    alert_cpu_temp=80,
    alert_cpu_percent=90,
    alert_disk_percent=90,
    alert_gpu_temp=80,
    temperature_unit='C',
):
    """Return short warning lines for OLED alert screen."""
    alerts = []
    unit = temperature_unit

    if cpu_temp_c is not None and cpu_temp_c >= alert_cpu_temp:
        t = cpu_temp_c if unit == 'C' else cpu_temp_c * 9 / 5 + 32
        alerts.append(f'CPU {t:.0f}{unit}')

    if cpu_percent is not None and cpu_percent >= alert_cpu_percent:
        alerts.append(f'CPU {cpu_percent:.0f}%')

    if gpu_temp_c is not None and gpu_temp_c >= alert_gpu_temp:
        t = gpu_temp_c if unit == 'C' else gpu_temp_c * 9 / 5 + 32
        alerts.append(f'GPU {t:.0f}{unit}')

    if disk_percent is not None and disk_percent >= alert_disk_percent:
        alerts.append(f'DISK {disk_percent:.0f}%')

    return alerts[:3]


def get_top_processes_cpu(count=3):
    """Top N processes by CPU %. Cached for _TOP_PROC_TTL seconds."""
    global _top_proc_cache
    now = time.time()
    if now - _top_proc_cache['at'] < _TOP_PROC_TTL and _top_proc_cache['rows']:
        return _top_proc_cache['rows'][:count]

    import psutil

    tracked = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            proc.cpu_percent(interval=None)
            tracked.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    time.sleep(0.12)

    rows = []
    for proc in tracked:
        try:
            info = proc.as_dict(attrs=['pid', 'name'])
            cpu = proc.cpu_percent(interval=None) or 0.0
            if cpu <= 0:
                continue
            name = (info.get('name') or '?')[:14]
            rows.append({'name': name, 'cpu_percent': round(min(cpu, 999), 1)})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    rows.sort(key=lambda r: r['cpu_percent'], reverse=True)
    _top_proc_cache = {'at': now, 'rows': rows}
    return rows[:count]
