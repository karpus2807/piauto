"""Flask routes for the advanced control center."""

import json

from flask import request, send_from_directory

from .control_schema import (
    PRESETS,
    build_control_schema,
    validate_system_patch,
)


def register_control_routes(app, api_prefix, static_folder, getters):
    """Register /control UI and extended API routes."""

    get_config = getters['get_config']
    get_device_info = getters['get_device_info']
    on_config_changed = getters['on_config_changed']
    get_history = getters['get_history']
    get_disks = getters.get('get_disks')
    get_ips = getters.get('get_ips')

    @app.route('/control')
    @app.route('/control/')
    def control_index():
        return send_from_directory(f'{static_folder}/control', 'index.html')

    @app.route('/control/<path:filename>')
    def control_assets(filename):
        return send_from_directory(f'{static_folder}/control', filename)

    @app.route(f'{api_prefix}/get-control-schema')
    def get_control_schema():
        cfg = get_config()
        dev = get_device_info()
        peripherals = (dev or {}).get('peripherals', [])
        return {
            'status': True,
            'data': build_control_schema(cfg, peripherals),
        }

    @app.route(f'{api_prefix}/get-live-status')
    def get_live_status():
        latest = get_history(1)
        if not isinstance(latest, dict):
            latest = {}
        live = {'history': latest}
        try:
            from pm_auto.dashboard_stats import get_dashboard_snapshot
            live['dashboard'] = get_dashboard_snapshot()
        except Exception:
            live['dashboard'] = None
        cfg = get_config()
        live['config'] = (cfg or {}).get('system', {})
        return {'status': True, 'data': live}

    @app.route(f'{api_prefix}/get-oled-options')
    def get_oled_options():
        disks = ['total']
        if get_disks:
            try:
                disks.extend(get_disks() or [])
            except Exception:
                pass
        interfaces = ['all']
        if get_ips:
            try:
                interfaces.extend(list((get_ips() or {}).keys()))
            except Exception:
                pass
        return {'status': True, 'data': {'disks': disks, 'interfaces': interfaces}}

    @app.route(f'{api_prefix}/apply-preset', methods=['POST'])
    def apply_preset():
        body = request.get_json(silent=True) or {}
        preset_id = body.get('preset')
        if preset_id not in PRESETS:
            return {
                'status': False,
                'error': f'Unknown preset. Choose: {", ".join(PRESETS.keys())}',
            }
        patch = dict(PRESETS[preset_id]['config'])
        on_config_changed({'system': patch})
        return {'status': True, 'data': {'applied': preset_id, 'config': patch}}

    @app.route(f'{api_prefix}/set-system-config', methods=['POST'])
    def set_system_config():
        body = request.get_json(silent=True) or {}
        patch = body.get('system', body)
        ok, result = validate_system_patch(patch)
        if not ok:
            return {'status': False, 'error': result}
        on_config_changed({'system': result})
        return {'status': True, 'data': result}

    @app.route(f'{api_prefix}/set-config', methods=['POST'])
    def set_config_bulk():
        """Alias: { "data": { "system": { ... } } } or { "system": { ... } }."""
        body = request.get_json(silent=True) or {}
        if 'data' in body and isinstance(body['data'], dict):
            system = body['data'].get('system', body['data'])
        else:
            system = body.get('system', body)
        ok, result = validate_system_patch(system)
        if not ok:
            return {'status': False, 'error': result}
        on_config_changed({'system': result})
        return {'status': True, 'data': result}
