"""Flask routes for the OLED visual designer."""

import json
import traceback

from flask import request, send_from_directory
from flask_cors import cross_origin

from .control_schema import OLED_PAGE_IDS
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
from .oled_page_templates import BUILTIN_PAGE_TEMPLATES


def register_oled_designer_routes(app, api_prefix, static_folder, getters):
    get_config = getters['get_config']
    on_config_changed = getters['on_config_changed']
    get_history = getters['get_history']

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
                'builtin_templates': list(BUILTIN_PAGE_TEMPLATES.keys()),
                'layout': layout,
                'designer_enabled': bool(system.get('oled_designer_enabled')),
                'bootstrap_cdn': 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
            },
        }

    @app.route(f'{api_prefix}/get-oled-metrics')
    @cross_origin()
    def get_oled_metrics():
        try:
            from pm_auto.oled import OLED, OLED_DEFAULT_CONFIG
            cfg = dict(OLED_DEFAULT_CONFIG)
            cfg['oled_preview'] = True
            host = OLED(cfg)
            if host.is_ready():
                return {'status': True, 'data': host.collect_layout_metrics(slide=0)}
        except Exception:
            pass
        latest = get_history(1)
        if not isinstance(latest, dict):
            latest = {}
        return {
            'status': True,
            'data': {
                'cpu_temperature': latest.get('cpu_temperature'),
                'gpu_temperature': latest.get('gpu_temperature'),
                'cpu_percent': latest.get('cpu_percent'),
                'memory_percent': latest.get('memory_percent'),
                'storage_percent': 100 - (latest.get('storage_percent_free') or 0),
                'storage_percent_free': latest.get('storage_percent_free'),
                'pwm_fan_speed': latest.get('pwm_fan_speed'),
                'gpio_fan_state': latest.get('gpio_fan_state'),
            },
        }

    @app.route(f'{api_prefix}/reset-oled-page/<page_id>')
    @cross_origin()
    def reset_oled_page(page_id):
        if page_id not in BUILTIN_PAGE_TEMPLATES:
            return {'status': False, 'error': f'Unknown built-in page: {page_id}'}
        import copy
        return {
            'status': True,
            'data': {'page': copy.deepcopy(BUILTIN_PAGE_TEMPLATES[page_id])},
        }

    @app.route(f'{api_prefix}/apply-oled-layout', methods=['POST'])
    @cross_origin()
    def apply_oled_layout():
        body = request.get_json(silent=True) or {}
        layout = body.get('layout', body)
        ok, result = validate_layout(layout)
        if not ok:
            return {'status': False, 'error': result}
        patch = {
            'oled_designer_layout': layout_to_config_string(result),
            'oled_designer_enabled': True,
        }
        carousel = result.get('carousel') or []
        if carousel:
            patch['oled_pages'] = ','.join(carousel)
            patch['oled_pages_profile'] = 'custom'
        on_config_changed({'system': patch})
        return {'status': True, 'data': {'layout': result, 'config_patch': patch}}
