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
    validate_layout,
)


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
                layout = result
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
                'layout': layout,
                'bootstrap_cdn': 'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
            },
        }

    @app.route(f'{api_prefix}/get-oled-metrics')
    @cross_origin()
    def get_oled_metrics():
        latest = get_history(1)
        if not isinstance(latest, dict):
            latest = {}
        try:
            from pm_auto.dashboard_stats import get_dashboard_snapshot
            dash = get_dashboard_snapshot() or {}
        except Exception:
            dash = {}
        sys = (dash.get('system') or {}) if isinstance(dash, dict) else {}
        return {
            'status': True,
            'data': {
                'cpu_temperature': latest.get('cpu_temperature'),
                'gpu_temperature': latest.get('gpu_temperature'),
                'cpu_percent': latest.get('cpu_percent'),
                'memory_percent': latest.get('memory_percent'),
                'storage_percent_free': latest.get('storage_percent_free'),
                'pwm_fan_speed': latest.get('pwm_fan_speed'),
                'gpio_fan_state': latest.get('gpio_fan_state'),
                'hostname': sys.get('hostname') or latest.get('hostname'),
                'uptime_seconds': latest.get('uptime_seconds'),
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
        patch = {'oled_designer_layout': layout_to_config_string(result)}
        carousel = result.get('carousel') or []
        builtin = [p for p in carousel if p in OLED_PAGE_IDS]
        if builtin:
            patch['oled_pages'] = ','.join(builtin)
            patch['oled_pages_profile'] = 'custom'
        on_config_changed({'system': patch})
        return {'status': True, 'data': {'layout': result, 'config_patch': patch}}
