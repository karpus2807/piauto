"""Flask routes for the multi-page OLED visual designer (Max-compatible)."""

import copy
import io
import json
import time
import traceback

from flask import Response, request, send_from_directory
from flask_cors import cross_origin
from PIL import Image, ImageDraw

from .oled_designer_schema import (
    BUILTIN_ICONS,
    DEFAULT_LAYOUT,
    ICON_PACKS,
    METRIC_KEYS,
    OLED_ASPECT,
    OLED_HEIGHT,
    OLED_PHYSICAL,
    OLED_WIDTH,
    layout_to_config_string,
    merge_layout_with_templates,
    validate_layout,
)
from .oled_page_ids import OLED_PAGE_IDS, STOCK_NATIVE_PAGE_IDS, STOCK_NATIVE_SOURCES
from .oled_page_templates import BUILTIN_PAGE_TEMPLATES, STOCK_NATIVE_TEMPLATES, build_default_layout


class _PreviewOled:
    """Minimal SSD1306-like surface for PNG preview (no hardware)."""

    def __init__(self, width=128, height=64):
        self.width = width
        self.height = height
        self.image = Image.new('1', (width, height), 0)
        self.draw = ImageDraw.Draw(self.image)

    def clear(self):
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)

    def display(self):
        return None

    def draw_text(self, text, x, y, fill=1, align='left', size=8, font_path=None):
        text = str(text)
        # Approximate width for alignment without shipping fonts dependency failures
        approx = max(1, int(len(text) * size * 0.55))
        if align == 'center':
            x -= approx / 2
        elif align == 'right':
            x -= approx
        try:
            from PIL import ImageFont
            font = ImageFont.load_default()
        except Exception:
            font = None
        self.draw.text((x, y), text=text, fill=fill, font=font)

    def draw_bar_graph_horizontal(self, percent, x, y, width, height):
        self.draw.rectangle((x, y, x + width, y + height), outline=1, fill=0)
        self.draw.rectangle((x, y, x + int(width * percent / 100.0), y + height), outline=1, fill=1)

    def draw_pieslice_chart(self, percent, x, y, r, start, end):
        direction = 1 if start < end else -1
        value_end = int(start + (end - start) * percent / 100) * direction
        self.draw.pieslice((x - r, y - r, x + r, y + r), start=start, end=end, fill=0, outline=1)
        self.draw.pieslice((x - r, y - r, x + r, y + r), start=start, end=value_end, fill=1, outline=1)


def _render_preview_png(page_id, slide, layout, metrics):
    from pm_auto.addons.oled.designer.layout_renderer import OledLayoutRenderer

    pages = (layout or {}).get('pages') or {}
    page_def = pages.get(page_id) or {}
    oled = _PreviewOled(OLED_WIDTH, OLED_HEIGHT)
    oled.clear()

    def provider(slide=0, page_id=''):
        return metrics

    rendered = OledLayoutRenderer(oled, provider).render(page_def, slide=slide)
    if not rendered:
        oled.draw_text(page_id or 'page', 64, 28, align='center', size=12)
    buf = io.BytesIO()
    oled.image.save(buf, format='PNG')
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')


def register_oled_designer_routes(app, api_prefix, static_folder, getters):
    get_config = getters['get_config']
    on_config_changed = getters['on_config_changed']
    pm_auto_runtime_update = getters.get('pm_auto_runtime_update')
    apply_system_runtime = getters.get('apply_system_runtime', on_config_changed)
    get_history = getters['get_history']
    get_device_info = getters.get('get_device_info', lambda: {})

    @app.route('/oled-designer')
    @app.route('/oled-designer/')
    @cross_origin()
    def oled_designer_index():
        return send_from_directory(f'{static_folder}/oled-designer', 'index.html')

    @app.route('/oled-designer/<path:filename>')
    @cross_origin()
    def oled_designer_assets(filename):
        return send_from_directory(f'{static_folder}/oled-designer', filename)

    @app.route(f'{api_prefix}/get-oled-spec')
    @cross_origin()
    def get_oled_spec():
        cfg = get_config() or {}
        system = cfg.get('system', {})
        raw = system.get('oled_designer_layout')
        layout = None
        if raw:
            ok, result = validate_layout(raw)
            if ok:
                layout = merge_layout_with_templates(result)
        if layout is None:
            layout = DEFAULT_LAYOUT
        if not isinstance(layout.get('pages'), dict) or len(layout['pages']) < len(BUILTIN_PAGE_TEMPLATES):
            merged = build_default_layout()
            merged['carousel'] = layout.get('carousel') or merged['carousel']
            for pid, page in (layout.get('pages') or {}).items():
                if isinstance(page, dict) and page.get('elements'):
                    merged['pages'][pid] = copy.deepcopy(page)
                elif isinstance(page, dict) and str(pid).startswith('custom_'):
                    merged['pages'][pid] = copy.deepcopy(page)
            layout = merged
        return {
            'status': True,
            'data': {
                'width': OLED_WIDTH,
                'height': OLED_HEIGHT,
                'aspect': OLED_ASPECT,
                'physical': OLED_PHYSICAL,
                'builtin_icons': list(BUILTIN_ICONS),
                'icon_packs': list(ICON_PACKS),
                'metrics': list(METRIC_KEYS),
                'builtin_page_ids': list(OLED_PAGE_IDS),
                'stock_page_ids': list(STOCK_NATIVE_PAGE_IDS),
                'stock_page_sources': dict(STOCK_NATIVE_SOURCES),
                'builtin_templates': list(BUILTIN_PAGE_TEMPLATES.keys()) + list(STOCK_NATIVE_TEMPLATES.keys()),
                'layout': layout,
                'designer_enabled': bool(system.get('oled_designer_enabled')),
                'current_oled_pages': list(system.get('oled_pages') or []),
                'bootstrap_cdn': 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
                'device': get_device_info(),
            },
        }

    @app.route(f'{api_prefix}/get-oled-metrics')
    @cross_origin()
    def get_oled_metrics():
        latest = get_history(1)
        if not isinstance(latest, dict):
            latest = {}
        # Enrich with designer-friendly aliases from history flat keys
        try:
            from pm_auto.addons.oled.designer.metrics import collect_metrics_from_data
            metrics = collect_metrics_from_data(latest, (get_config() or {}).get('system') or {})
        except Exception:
            metrics = {
                'cpu_temperature': latest.get('cpu_temperature'),
                'gpu_temperature': latest.get('gpu_temperature'),
                'cpu_percent': latest.get('cpu_percent'),
                'memory_percent': latest.get('memory_percent'),
                'pwm_fan_speed': latest.get('pwm_fan_speed'),
                'gpio_fan_state': latest.get('gpio_fan_state'),
            }
        return {'status': True, 'data': metrics}

    @app.route(f'{api_prefix}/oled-preview-png', methods=['GET', 'POST'])
    @cross_origin()
    def oled_preview_png():
        try:
            if request.method == 'POST':
                body = request.get_json(silent=True) or {}
                page_id = body.get('page', 'home')
                slide = int(body.get('slide', 0))
                layout = body.get('layout')
            else:
                page_id = request.args.get('page', 'home')
                slide = int(request.args.get('slide', 0))
                layout = None
            if layout is None:
                raw = ((get_config() or {}).get('system') or {}).get('oled_designer_layout')
                ok, result = validate_layout(raw) if raw else (False, None)
                layout = result if ok else build_default_layout()
            elif isinstance(layout, str):
                ok, result = validate_layout(layout)
                layout = result if ok else build_default_layout()
            metrics_resp = get_oled_metrics()
            metrics = (metrics_resp.get('data') if isinstance(metrics_resp, dict) else {}) or {}
            return _render_preview_png(page_id, slide, layout, metrics)
        except Exception as e:
            return {'status': False, 'error': str(e), 'trace': traceback.format_exc()[-400:]}

    @app.route(f'{api_prefix}/reset-oled-page/<page_id>')
    @cross_origin()
    def reset_oled_page(page_id):
        if page_id in STOCK_NATIVE_TEMPLATES:
            return {
                'status': True,
                'data': {'page': copy.deepcopy(STOCK_NATIVE_TEMPLATES[page_id])},
            }
        if page_id not in BUILTIN_PAGE_TEMPLATES:
            return {'status': False, 'error': f'Unknown built-in page: {page_id}'}
        return {
            'status': True,
            'data': {'page': copy.deepcopy(BUILTIN_PAGE_TEMPLATES[page_id])},
        }

    @app.route(f'{api_prefix}/test-oled-page', methods=['POST'])
    @cross_origin()
    def test_oled_page():
        body = request.get_json(silent=True) or {}
        layout = body.get('layout', body)
        page_id = str(body.get('page', 'home'))[:32]
        try:
            duration = int(body.get('duration', 5))
        except (TypeError, ValueError):
            duration = 5
        duration = max(1, min(30, duration))
        ok, result = validate_layout(layout)
        if not ok:
            return {'status': False, 'error': result}
        if page_id not in (result.get('pages') or {}):
            return {'status': False, 'error': f'Unknown page: {page_id}'}
        test_patch = {
            'oled_designer_test': {
                'until': time.time() + duration,
                'token': str(time.time_ns()),
                'page': page_id,
                'layout': result,
            },
        }
        try:
            handled_runtime = False
            if pm_auto_runtime_update:
                handled_runtime = bool(pm_auto_runtime_update(test_patch))
            if not handled_runtime:
                # Push into system config path so OLEDAddon.update_config sees it.
                apply_system_runtime({'system': test_patch} if 'system' not in test_patch else test_patch)
                # Also try flat system merge used by pironman5
                on_config_changed({'system': test_patch})
        except Exception as e:
            return {'status': False, 'error': str(e), 'trace': traceback.format_exc()[-300:]}
        return {
            'status': True,
            'data': {
                'page': page_id,
                'duration': duration,
                'runtime': handled_runtime,
            },
        }

    @app.route(f'{api_prefix}/apply-oled-layout', methods=['POST'])
    @cross_origin()
    def apply_oled_layout():
        body = request.get_json(silent=True) or {}
        layout = body.get('layout', body)
        ok, result = validate_layout(layout)
        if not ok:
            return {'status': False, 'error': result}
        carousel = list(result.get('carousel') or [])
        if result.get('static') and result.get('static_page'):
            carousel = [result['static_page']]
            result['carousel'] = carousel
        patch = {
            'oled_designer_layout': layout_to_config_string(result),
            'oled_designer_enabled': True,
            'oled_pages': carousel,
            'oled_pages_profile': 'custom',
        }
        on_config_changed({'system': patch})
        return {
            'status': True,
            'data': {
                'layout': result,
                'config_patch': patch,
                'oled_pages': carousel,
                'static': bool(result.get('static')),
            },
        }
