"""Build designer metric dict from OLEDAddon live data."""

from __future__ import annotations


def _fmt_bytes(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return 'NA'
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024.0
        i += 1
    if i == 0:
        return f'{int(n)}{units[i]}'
    return f'{n:.1f}{units[i]}'


def collect_metrics_from_data(data, config=None, slide=0):
    """Map stock SystemAddon flat keys into designer metric keys."""
    data = data or {}
    config = config or {}
    unit = config.get('temperature_unit', 'C')

    cpu_temp_c = float(data.get('cpu_temperature') or 0)
    cpu_temp = cpu_temp_c if unit == 'C' else cpu_temp_c * 9 / 5 + 32
    cpu_pct = float(data.get('cpu_percent') or 0)
    mem_pct = float(data.get('memory_percent') or 0)
    mem_used = data.get('memory_used')
    mem_total = data.get('memory_total')

    # Prefer combined-looking disk: largest mounted disk percent if present
    storage_pct = 0.0
    storage_detail = 'No storage'
    for key, val in data.items():
        if key.startswith('disk_') and key.endswith('_percent'):
            try:
                storage_pct = max(storage_pct, float(val or 0))
            except (TypeError, ValueError):
                pass
    # Pick first disk_*_used / total pair for detail line
    for key in sorted(data.keys()):
        if key.startswith('disk_') and key.endswith('_used'):
            base = key[:-5]
            used = data.get(key)
            total = data.get(base + 'total')
            if used is not None and total is not None:
                storage_detail = f'DISK: {_fmt_bytes(used)}/{_fmt_bytes(total)}'
                try:
                    storage_pct = float(data.get(base + 'percent') or storage_pct)
                except (TypeError, ValueError):
                    pass
            break

    ips = data.get('ips') or []
    if isinstance(ips, dict):
        ip_items = list(ips.items())
    elif isinstance(ips, list):
        # stock may provide list of strings or dicts
        ip_items = []
        for item in ips:
            if isinstance(item, dict):
                ip_items.append((item.get('interface') or item.get('name') or 'net', item.get('ip') or item.get('address') or ''))
            else:
                ip_items.append(('net', str(item)))
    else:
        ip_items = []

    ip_line = 'NO IP'
    if ip_items:
        iface, ip = ip_items[0]
        ip_line = f'{iface} {ip}'.strip()[:20]

    gpu_temp = data.get('gpu_temperature')
    gpio_fan = data.get('gpio_fan_state')
    pwm = data.get('pwm_fan_speed')
    disk_temps = []
    for key, val in data.items():
        if not (isinstance(key, str) and key.startswith('disk_') and key.endswith('_temperature')):
            continue
        name = key[5:-12]
        try:
            disk_temps.append(f'{name} {float(val):.0f}{unit}')
        except (TypeError, ValueError):
            continue

    m = {
        'cpu_temperature': cpu_temp,
        'cpu_temp_label': f'{cpu_temp:.1f}{unit}',
        'cpu_percent': cpu_pct,
        'cpu_temp_gauge': min(cpu_temp_c, 100),
        'memory_percent': mem_pct,
        'ram_line': f'RAM {_fmt_bytes(mem_used)}/{_fmt_bytes(mem_total)}' if mem_used is not None else f'RAM {mem_pct:.0f}%',
        'storage_percent': storage_pct,
        'storage_percent_free': max(0, 100 - storage_pct),
        'storage_line': f'STORE {storage_pct:.0f}%',
        'storage_detail': storage_detail,
        'storage_temp': disk_temps[0] if disk_temps else '',
        'ip_line': ip_line,
        'gpu_percent': 0,
        'gpu_temperature': gpu_temp,
        'gpu_use_line': 'USE N/A',
        'gpu_temp_line': f'TEMP {gpu_temp}{unit}' if gpu_temp is not None else 'TEMP N/A',
        'cpu_use_line': f'USE {cpu_pct:.0f}%',
        'cpu_temp_line': f'TEMP {cpu_temp:.1f}{unit}',
        'tower_rpm_line': f'TOWER {pwm} RPM' if pwm not in (None, '') else '',
        'side_fan_line': f'SIDE  {"ON" if gpio_fan else "OFF"}' if gpio_fan is not None else '',
        'fan_mode_line': 'MODE  auto',
        'pwm_fan_speed': pwm,
        'gpio_fan_state': gpio_fan,
        'hostname': data.get('hostname') or '',
        'uptime_seconds': data.get('uptime_seconds') or 0,
        'top_cpu_1': data.get('top_cpu_1') or '',
        'top_cpu_2': data.get('top_cpu_2') or '',
        'top_cpu_3': data.get('top_cpu_3') or '',
        'disk_temp_line_1': disk_temps[0] if disk_temps else '',
        'disk_temp_line_2': disk_temps[1] if len(disk_temps) > 1 else '',
    }
    for i in range(4):
        if i < len(ip_items):
            iface, ip = ip_items[i]
            line = f'{iface} {ip}'.strip()
            m[f'net_line_{i + 1}'] = line[:20]
        else:
            m[f'net_line_{i + 1}'] = ''
    return m
