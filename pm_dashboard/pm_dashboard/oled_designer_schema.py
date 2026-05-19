"""OLED display spec and layout JSON validation for the web designer."""

import json

OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_ASPECT = '2:1'
OLED_PHYSICAL = '0.96"'

ELEMENT_TYPES = ('text', 'metric', 'icon', 'rect', 'bar')
ICON_PACKS = ('builtin', 'bootstrap')

BUILTIN_ICONS = (
    'cpu', 'gpu', 'ram', 'disk', 'ssd', 'usb', 'wifi', 'ethernet',
    'fan', 'temp', 'heart', 'alert', 'power', 'clock', 'server', 'home',
)

METRIC_KEYS = (
    'cpu_temperature', 'gpu_temperature', 'cpu_percent', 'memory_percent',
    'storage_percent_free', 'pwm_fan_speed', 'gpio_fan_state',
    'hostname', 'uptime_seconds',
)

DEFAULT_LAYOUT = {
    'version': 1,
    'display': {'width': OLED_WIDTH, 'height': OLED_HEIGHT, 'aspect': OLED_ASPECT},
    'carousel': ['home', 'storage', 'heart'],
    'pages': {
        'custom_1': {
            'id': 'custom_1',
            'name': 'Custom',
            'duration': 5,
            'elements': [
                {'type': 'text', 'x': 0, 'y': 0, 'w': 128, 'text': 'Pironman', 'size': 1},
                {
                    'type': 'metric', 'x': 0, 'y': 16, 'w': 80,
                    'key': 'cpu_temperature', 'format': '{:.1f} C', 'size': 2,
                },
                {'type': 'icon', 'x': 108, 'y': 14, 'w': 16, 'h': 16, 'icon': 'cpu', 'pack': 'builtin'},
                {
                    'type': 'bar', 'x': 0, 'y': 52, 'w': 128, 'h': 8,
                    'key': 'cpu_percent', 'max': 100,
                },
            ],
        },
    },
}


def _clamp_int(value, lo, hi, default=0):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _validate_element(el, errors, path):
    if not isinstance(el, dict):
        errors.append(f'{path}: element must be object')
        return
    t = el.get('type')
    if t not in ELEMENT_TYPES:
        errors.append(f'{path}: invalid type {t!r}')
        return
    x = _clamp_int(el.get('x', 0), 0, OLED_WIDTH - 1)
    y = _clamp_int(el.get('y', 0), 0, OLED_HEIGHT - 1)
    el['x'], el['y'] = x, y
    if t == 'text':
        el['text'] = str(el.get('text', ''))[:40]
        el['size'] = _clamp_int(el.get('size', 1), 1, 2, 1)
    elif t == 'metric':
        key = el.get('key', 'cpu_temperature')
        if key not in METRIC_KEYS:
            errors.append(f'{path}: unknown metric {key!r}')
        el['key'] = key
        el['format'] = str(el.get('format', '{}'))[:24]
        el['size'] = _clamp_int(el.get('size', 1), 1, 2, 1)
    elif t == 'icon':
        pack = el.get('pack', 'builtin')
        if pack not in ICON_PACKS:
            pack = 'builtin'
        el['pack'] = pack
        icon = str(el.get('icon', 'cpu'))[:48]
        el['icon'] = icon
        el['w'] = _clamp_int(el.get('w', 16), 8, 32, 16)
        el['h'] = _clamp_int(el.get('h', 16), 8, 32, 16)
    elif t == 'rect':
        el['w'] = _clamp_int(el.get('w', 32), 1, OLED_WIDTH, 32)
        el['h'] = _clamp_int(el.get('h', 12), 1, OLED_HEIGHT, 12)
        el['fill'] = bool(el.get('fill', False))
    elif t == 'bar':
        key = el.get('key', 'cpu_percent')
        if key not in METRIC_KEYS:
            errors.append(f'{path}: unknown metric {key!r}')
        el['key'] = key
        el['w'] = _clamp_int(el.get('w', 128), 4, OLED_WIDTH, 128)
        el['h'] = _clamp_int(el.get('h', 8), 2, 16, 8)
        el['max'] = _clamp_int(el.get('max', 100), 1, 1000, 100)


def validate_layout(data):
    """Return (ok, layout_dict|error_message)."""
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            return False, f'Invalid JSON: {e}'
    if not isinstance(data, dict):
        return False, 'Layout must be a JSON object'
    errors = []
    version = data.get('version', 1)
    if version != 1:
        errors.append('Only layout version 1 is supported')
    pages = data.get('pages')
    if not isinstance(pages, dict):
        return False, 'pages must be an object'
    carousel = data.get('carousel', [])
    if not isinstance(carousel, list):
        errors.append('carousel must be a list')
        carousel = []
    cleaned_pages = {}
    for pid, page in pages.items():
        if not isinstance(page, dict):
            errors.append(f'page {pid}: must be object')
            continue
        pid_s = str(pid)[:32]
        elements = page.get('elements', [])
        if not isinstance(elements, list):
            errors.append(f'page {pid_s}: elements must be list')
            elements = []
        clean_els = []
        for i, el in enumerate(elements[:40]):
            _validate_element(el, errors, f'pages.{pid_s}.elements[{i}]')
            clean_els.append(el)
        cleaned_pages[pid_s] = {
            'id': pid_s,
            'name': str(page.get('name', pid_s))[:32],
            'duration': _clamp_int(page.get('duration', 5), 2, 120, 5),
            'elements': clean_els,
        }
    clean_carousel = [str(p)[:32] for p in carousel[:20]]
    if errors:
        return False, '; '.join(errors[:8])
    return True, {
        'version': 1,
        'display': {
            'width': OLED_WIDTH,
            'height': OLED_HEIGHT,
            'aspect': OLED_ASPECT,
            'physical': OLED_PHYSICAL,
        },
        'carousel': clean_carousel,
        'pages': cleaned_pages,
    }


def layout_to_config_string(layout):
    return json.dumps(layout, separators=(',', ':'))
