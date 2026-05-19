"""Default editable layouts mirroring built-in OLED pages (128×64 wireframes)."""

from .control_schema import OLED_PAGE_IDS

# Shared carousel for full profile
FULL_CAROUSEL = list(OLED_PAGE_IDS)

BUILTIN_PAGE_TEMPLATES = {
    'home': {
        'id': 'home',
        'name': 'Home',
        'duration': 15,
        'builtin': True,
        'elements': [
            {'type': 'text', 'x': 18, 'y': 0, 'text': 'CPU', 'size': 1},
            {'type': 'gauge', 'x': 18, 'y': 27, 'r': 15, 'key': 'cpu_percent', 'start': 180, 'end': 0},
            {'type': 'metric', 'x': 18, 'y': 20, 'key': 'cpu_percent', 'format': '{:.0f}%', 'size': 1},
            {'type': 'metric', 'x': 18, 'y': 32, 'key': 'cpu_temperature', 'format': '{:.1f}', 'size': 1},
            {'type': 'gauge', 'x': 18, 'y': 48, 'r': 15, 'key': 'cpu_temp_gauge', 'start': 0, 'end': 180},
            {'type': 'rect', 'x': 39, 'y': 0, 'w': 88, 'h': 10, 'fill': True},
            {'type': 'metric', 'x': 64, 'y': 0, 'key': 'ip_line', 'format': '{}', 'size': 1, 'align': 'center'},
            {'type': 'metric', 'x': 39, 'y': 17, 'key': 'ram_line', 'format': '{}', 'size': 1},
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'memory_percent', 'max': 100},
            {'type': 'metric', 'x': 39, 'y': 41, 'key': 'storage_line', 'format': '{}', 'size': 1},
            {'type': 'bar', 'x': 39, 'y': 53, 'w': 88, 'h': 10, 'key': 'storage_percent', 'max': 100},
        ],
    },
    'storage': {
        'id': 'storage',
        'name': 'Storage',
        'duration': 5,
        'builtin': True,
        'elements': [
            {'type': 'text', 'x': 2, 'y': 0, 'text': 'STORAGE', 'size': 1},
            {'type': 'text', 'x': 100, 'y': 0, 'text': '1/1', 'size': 1},
            {'type': 'icon', 'x': 2, 'y': 20, 'icon': 'ssd', 'pack': 'builtin', 'w': 14, 'h': 14},
            {'type': 'gauge', 'x': 18, 'y': 38, 'r': 13, 'key': 'storage_percent', 'start': 180, 'end': 0},
            {'type': 'metric', 'x': 18, 'y': 32, 'key': 'storage_percent', 'format': '{:.0f}%', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 17, 'key': 'storage_detail', 'format': '{}', 'size': 1},
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'storage_percent', 'max': 100},
            {'type': 'metric', 'x': 39, 'y': 43, 'key': 'storage_temp', 'format': '{}', 'size': 1},
        ],
    },
    'network': {
        'id': 'network',
        'name': 'Network',
        'duration': 5,
        'builtin': True,
        'elements': [
            {'type': 'text', 'x': 2, 'y': 0, 'text': 'NETWORK', 'size': 1},
            {'type': 'text', 'x': 100, 'y': 0, 'text': '1/1', 'size': 1},
            {'type': 'metric', 'x': 4, 'y': 17, 'key': 'net_line_1', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 4, 'y': 29, 'key': 'net_line_2', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 4, 'y': 41, 'key': 'net_line_3', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 4, 'y': 53, 'key': 'net_line_4', 'format': '{}', 'size': 1},
        ],
    },
    'cpu': {
        'id': 'cpu',
        'name': 'CPU',
        'duration': 5,
        'builtin': True,
        'elements': [
            {'type': 'text', 'x': 2, 'y': 0, 'text': 'CPU', 'size': 1},
            {'type': 'text', 'x': 18, 'y': 10, 'text': 'CPU', 'size': 1},
            {'type': 'gauge', 'x': 18, 'y': 30, 'r': 15, 'key': 'cpu_percent', 'start': 180, 'end': 0},
            {'type': 'metric', 'x': 18, 'y': 24, 'key': 'cpu_percent', 'format': '{:.0f}%', 'size': 1},
            {'type': 'metric', 'x': 18, 'y': 36, 'key': 'cpu_temperature', 'format': '{:.1f}', 'size': 1},
            {'type': 'gauge', 'x': 18, 'y': 50, 'r': 13, 'key': 'cpu_temp_gauge', 'start': 0, 'end': 180},
            {'type': 'metric', 'x': 39, 'y': 17, 'key': 'cpu_use_line', 'format': '{}', 'size': 1},
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'cpu_percent', 'max': 100},
            {'type': 'metric', 'x': 39, 'y': 43, 'key': 'cpu_temp_line', 'format': '{}', 'size': 1},
        ],
    },
    'gpu': {
        'id': 'gpu',
        'name': 'GPU',
        'duration': 5,
        'builtin': True,
        'elements': [
            {'type': 'text', 'x': 2, 'y': 0, 'text': 'GPU', 'size': 1},
            {'type': 'gauge', 'x': 18, 'y': 38, 'r': 13, 'key': 'gpu_percent', 'start': 180, 'end': 0},
            {'type': 'metric', 'x': 18, 'y': 32, 'key': 'gpu_percent', 'format': '{:.0f}%', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 17, 'key': 'gpu_use_line', 'format': '{}', 'size': 1},
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'gpu_percent', 'max': 100},
            {'type': 'metric', 'x': 39, 'y': 43, 'key': 'gpu_temp_line', 'format': '{}', 'size': 1},
        ],
    },
    'fans': {
        'id': 'fans',
        'name': 'Fans',
        'duration': 5,
        'builtin': True,
        'elements': [
            {'type': 'text', 'x': 2, 'y': 0, 'text': 'FANS', 'size': 1},
            {'type': 'metric', 'x': 4, 'y': 17, 'key': 'tower_rpm_line', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 4, 'y': 29, 'key': 'side_fan_line', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 4, 'y': 41, 'key': 'fan_mode_line', 'format': '{}', 'size': 1},
        ],
    },
    'ram': {
        'id': 'ram',
        'name': 'RAM',
        'duration': 5,
        'builtin': True,
        'elements': [
            {'type': 'text', 'x': 2, 'y': 0, 'text': 'RAM', 'size': 1},
            {'type': 'gauge', 'x': 18, 'y': 38, 'r': 13, 'key': 'memory_percent', 'start': 180, 'end': 0},
            {'type': 'metric', 'x': 18, 'y': 32, 'key': 'memory_percent', 'format': '{:.0f}%', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 17, 'key': 'ram_line', 'format': '{}', 'size': 1},
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'memory_percent', 'max': 100},
        ],
    },
    'temps': {
        'id': 'temps',
        'name': 'Temps',
        'duration': 5,
        'builtin': True,
        'elements': [
            {'type': 'text', 'x': 2, 'y': 0, 'text': 'TEMPS', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 17, 'key': 'cpu_temp_line', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 29, 'key': 'gpu_temp_line', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 41, 'key': 'disk_temp_line_1', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 53, 'key': 'disk_temp_line_2', 'format': '{}', 'size': 1},
        ],
    },
    'services': {
        'id': 'services',
        'name': 'Top CPU',
        'duration': 5,
        'builtin': True,
        'elements': [
            {'type': 'text', 'x': 2, 'y': 0, 'text': 'TOP CPU', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 17, 'key': 'top_cpu_1', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 29, 'key': 'top_cpu_2', 'format': '{}', 'size': 1},
            {'type': 'metric', 'x': 39, 'y': 41, 'key': 'top_cpu_3', 'format': '{}', 'size': 1},
        ],
    },
    'heart': {
        'id': 'heart',
        'name': 'Heart',
        'duration': 5,
        'builtin': True,
        'elements': [
            {'type': 'heart', 'margin': 7},
        ],
    },
}


def build_default_layout():
    import copy
    pages = copy.deepcopy(BUILTIN_PAGE_TEMPLATES)
    return {
        'version': 1,
        'display': {'width': 128, 'height': 64, 'aspect': '2:1'},
        'carousel': list(FULL_CAROUSEL),
        'pages': pages,
    }


def merge_layout_with_templates(saved):
    """Merge saved user layout over built-in templates."""
    import copy
    base = build_default_layout()
    if not saved or not isinstance(saved, dict):
        return base
    if saved.get('carousel'):
        base['carousel'] = list(saved['carousel'])
    saved_pages = saved.get('pages') or {}
    for pid, page in saved_pages.items():
        if pid in base['pages'] and isinstance(page, dict) and page.get('elements'):
            base['pages'][pid] = copy.deepcopy(page)
            base['pages'][pid].setdefault('builtin', pid in BUILTIN_PAGE_TEMPLATES)
        elif pid.startswith('custom_') and isinstance(page, dict):
            base['pages'][pid] = copy.deepcopy(page)
    return base
