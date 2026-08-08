"""Default editable layouts calibrated to legacy OLED draw positions (128×64)."""

from . import DESIGNER_PAGE_IDS, STOCK_NATIVE_PAGE_IDS, STOCK_NATIVE_SOURCES
OLED_PAGE_IDS = DESIGNER_PAGE_IDS

FULL_CAROUSEL = list(OLED_PAGE_IDS)
STOCK_CAROUSEL = list(STOCK_NATIVE_PAGE_IDS)

# Legacy hardware uses 8px font (ssd1306 size='sm') for all data lines.
_LEGACY_FONT = 1  # designer: 1 = sm/8px, 2 = md/10px


def _txt(x, y, text, **kw):
    return {'type': 'text', 'x': x, 'y': y, 'text': text, 'size': _LEGACY_FONT, **kw}


def _m(x, y, key, **kw):
    return {'type': 'metric', 'x': x, 'y': y, 'key': key, 'size': _LEGACY_FONT, **kw}


def _gauge(x, y, r, key, start, end):
    return {
        'type': 'gauge', 'x': x, 'y': y, 'r': r,
        'key': key, 'start': start, 'end': end,
    }


def _pct(x, y, key):
    """Centered % on top of pieslice (same as legacy draw_* after pieslice_chart)."""
    return {
        'type': 'metric', 'x': x, 'y': y, 'key': key,
        'format': '{:.0f}%', 'align': 'center', 'size': _LEGACY_FONT,
    }


def _stock_stub(page_id, title, blurb):
    """Canvas placeholder — hardware still runs PageMix/etc., not this layout."""
    src = STOCK_NATIVE_SOURCES.get(page_id, '')
    short = src.rsplit('.', 1)[-1] if src else page_id
    return {
        'id': page_id,
        'name': title,
        'duration': 5,
        'builtin': True,
        'native': True,
        'stock': True,
        'source': src,
        'elements': [
            _txt(64, 8, title.upper(), align='center', size=2),
            _txt(64, 28, 'Native stock page', align='center'),
            _txt(64, 42, blurb, align='center'),
            _txt(64, 54, short, align='center'),
        ],
    }


# Element list order = draw order (back to front).

BUILTIN_PAGE_TEMPLATES = {
    'home': {
        'id': 'home',
        'name': 'Home',
        'duration': 15,
        'builtin': True,
        'elements': [
            _txt(18, 0, 'CPU', align='center'),
            _gauge(18, 27, 15, 'cpu_percent', 180, 0),
            _pct(18, 27, 'cpu_percent'),
            _m(18, 37, 'cpu_temp_label', align='center'),
            _gauge(18, 48, 15, 'cpu_temp_gauge', 0, 180),
            {'type': 'rect', 'x': 39, 'y': 0, 'w': 88, 'h': 10, 'fill': True},
            _m(83, 0, 'ip_line', align='center', invert=True),
            _m(39, 17, 'ram_line'),
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'memory_percent', 'max': 100},
            _m(39, 41, 'storage_line'),
            {'type': 'bar', 'x': 39, 'y': 53, 'w': 88, 'h': 10, 'key': 'storage_percent', 'max': 100},
        ],
    },
    'storage': {
        'id': 'storage',
        'name': 'Storage',
        'duration': 5,
        'builtin': True,
        'elements': [
            _txt(2, 0, 'STORAGE'),
            _txt(127, 0, '1/1', align='right'),
            {'type': 'icon', 'x': 2, 'y': 20, 'icon': 'ssd', 'pack': 'builtin', 'w': 14, 'h': 14},
            _gauge(18, 38, 13, 'storage_percent', 180, 0),
            _pct(18, 38, 'storage_percent'),
            _m(39, 17, 'storage_detail'),
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'storage_percent', 'max': 100},
            _m(39, 43, 'storage_temp'),
        ],
    },
    'network': {
        'id': 'network',
        'name': 'Network',
        'duration': 5,
        'builtin': True,
        'elements': [
            _txt(2, 0, 'NETWORK'),
            _txt(127, 0, '1/1', align='right'),
            _m(4, 17, 'net_line_1'),
            _m(4, 29, 'net_line_2'),
            _m(4, 41, 'net_line_3'),
            _m(4, 53, 'net_line_4'),
        ],
    },
    'cpu': {
        'id': 'cpu',
        'name': 'CPU',
        'duration': 5,
        'builtin': True,
        'elements': [
            _txt(2, 0, 'CPU'),
            _txt(18, 10, 'CPU', align='center'),
            _gauge(18, 30, 15, 'cpu_percent', 180, 0),
            _pct(18, 30, 'cpu_percent'),
            _m(18, 40, 'cpu_temp_label', align='center'),
            _gauge(18, 50, 13, 'cpu_temp_gauge', 0, 180),
            _m(39, 17, 'cpu_use_line'),
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'cpu_percent', 'max': 100},
            _m(39, 43, 'cpu_temp_line'),
        ],
    },
    'gpu': {
        'id': 'gpu',
        'name': 'GPU',
        'duration': 5,
        'builtin': True,
        'elements': [
            _txt(2, 0, 'GPU'),
            _gauge(18, 38, 13, 'gpu_percent', 180, 0),
            _pct(18, 38, 'gpu_percent'),
            _m(39, 17, 'gpu_use_line'),
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'gpu_percent', 'max': 100},
            _m(39, 43, 'gpu_temp_line'),
        ],
    },
    'fans': {
        'id': 'fans',
        'name': 'Fans',
        'duration': 5,
        'builtin': True,
        'elements': [
            _txt(2, 0, 'FANS'),
            _m(4, 17, 'tower_rpm_line'),
            _m(4, 29, 'side_fan_line'),
            _m(4, 41, 'fan_mode_line'),
        ],
    },
    'ram': {
        'id': 'ram',
        'name': 'RAM',
        'duration': 5,
        'builtin': True,
        'elements': [
            _txt(2, 0, 'RAM'),
            _gauge(18, 38, 13, 'memory_percent', 180, 0),
            _pct(18, 38, 'memory_percent'),
            _m(39, 17, 'ram_line'),
            {'type': 'bar', 'x': 39, 'y': 29, 'w': 88, 'h': 10, 'key': 'memory_percent', 'max': 100},
        ],
    },
    'temps': {
        'id': 'temps',
        'name': 'Temps',
        'duration': 5,
        'builtin': True,
        'elements': [
            _txt(2, 0, 'TEMPS'),
            _m(39, 17, 'cpu_temp_line'),
            _m(39, 29, 'gpu_temp_line'),
            _m(39, 41, 'disk_temp_line_1'),
            _m(39, 53, 'disk_temp_line_2'),
        ],
    },
    'services': {
        'id': 'services',
        'name': 'Top CPU',
        'duration': 5,
        'builtin': True,
        'elements': [
            _txt(2, 0, 'TOP CPU'),
            _m(39, 17, 'top_cpu_1'),
            _m(39, 29, 'top_cpu_2'),
            _m(39, 41, 'top_cpu_3'),
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

# Stock Pironman Max OLED pages (firmware PageMix / PagePerformance / …).
STOCK_NATIVE_TEMPLATES = {
    'mix': _stock_stub('mix', 'Mix', 'IP + CPU + RAM'),
    'performance': _stock_stub('performance', 'Perf', 'CPU RAM TEMP FAN'),
    'ips': _stock_stub('ips', 'IPs', 'Network addresses'),
    'disk': _stock_stub('disk', 'Disk', 'Storage usage'),
}


def build_default_layout():
    import copy
    pages = {k: copy.deepcopy(v) for k, v in BUILTIN_PAGE_TEMPLATES.items()}
    for pid in STOCK_NATIVE_PAGE_IDS:
        pages[pid] = copy.deepcopy(STOCK_NATIVE_TEMPLATES[pid])
    return {
        'version': 1,
        'display': {'width': 128, 'height': 64, 'aspect': '2:1'},
        'carousel': list(FULL_CAROUSEL),
        'pages': pages,
        'static': False,
        'static_page': '',
        'mode': 'carousel',
    }


def merge_layout_with_templates(saved):
    import copy
    base = build_default_layout()
    if not saved or not isinstance(saved, dict):
        return base
    if saved.get('carousel'):
        base['carousel'] = list(saved['carousel'])
    base['static'] = bool(saved.get('static') or saved.get('mode') == 'static')
    base['static_page'] = str(saved.get('static_page') or '')
    base['mode'] = 'static' if base['static'] else 'carousel'
    if base['static'] and base['static_page']:
        base['carousel'] = [base['static_page']]
    saved_pages = saved.get('pages') or {}
    for pid, page in saved_pages.items():
        if not isinstance(page, dict):
            continue
        # Keep stock native stubs authoritative (hardware Page* classes).
        if pid in STOCK_NATIVE_PAGE_IDS:
            base['pages'][pid] = copy.deepcopy(STOCK_NATIVE_TEMPLATES[pid])
            if page.get('duration') is not None:
                base['pages'][pid]['duration'] = page.get('duration')
            continue
        if page.get('elements'):
            base['pages'][pid] = copy.deepcopy(page)
            base['pages'][pid].setdefault('builtin', pid in BUILTIN_PAGE_TEMPLATES)
            base['pages'][pid].setdefault('duration', 5)
        elif pid.startswith('custom_'):
            base['pages'][pid] = copy.deepcopy(page)
            base['pages'][pid].setdefault('duration', 5)
    return base
