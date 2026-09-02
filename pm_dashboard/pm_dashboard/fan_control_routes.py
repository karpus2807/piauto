"""Dashboard FAN controls: PWM profiles, RGB styles, calibration, benchmarks."""

import json
import os
import threading
import time
import traceback
from datetime import datetime, timezone
from multiprocessing import Process, cpu_count

from flask import request, send_from_directory
from flask_cors import cross_origin

from pm_auto.addons.fan_profiles import (
    BUILTIN_PWM_PROFILES,
    DEFAULT_CUSTOM_STEPS,
    RGB_STYLE_META,
    sanitize_custom,
)

STATUS_PATH = os.environ.get('PIAUTO_FAN_JOB', '/opt/pironman5/fan-job-status.json')
CALIB_PATH = os.environ.get('PIAUTO_FAN_CALIBRATION', '/opt/pironman5/fan_calibration.json')

_lock = threading.Lock()
_job_thread = None


def _now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _read_json(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, data):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def _job():
    return _read_json(STATUS_PATH, {
        'state': 'idle',
        'kind': '',
        'profile_id': '',
        'message': '',
        'started_at': '',
        'finished_at': '',
        'live': {},
        'result': None,
    }) or {}


def _set_job(**kwargs):
    data = _job()
    data.update(kwargs)
    _write_json(STATUS_PATH, data)
    return data


def _system(getters):
    cfg = getters['get_config']() or {}
    return cfg.get('system') or {}


def _live(getters):
    data = getters['get_history']() or {}
    cpu_temp = data.get('cpu_temperature')
    prev = _job().get('live') or {}
    prev_temp = prev.get('cpu_temp')
    prev_at = prev.get('at') or 0
    now = time.time()
    dt_rate = None
    if cpu_temp is not None and prev_temp is not None and now - prev_at >= 0.4:
        dt_rate = (float(cpu_temp) - float(prev_temp)) / max(0.4, now - prev_at)
    gen = max(0.0, dt_rate) if dt_rate is not None else 0.0
    diss = max(0.0, -dt_rate) if dt_rate is not None else 0.0
    gpu_load = data.get('gpu_percent')
    live = {
        'at': now,
        'cpu_load': data.get('cpu_percent'),
        'gpu_load': gpu_load,
        'gpu_temp': data.get('gpu_temperature'),
        'cpu_temp': cpu_temp,
        'fan_rpm': data.get('pwm_fan_speed'),
        'fan_power': data.get('pwm_fan_power'),
        'max_speed': data.get('pwm_fan_max_speed') or (_read_json(CALIB_PATH, {}) or {}).get('max_rpm') or 0,
        'heat_generation': round(gen, 3),
        'heat_dissipation': round(diss, 3),
        'gpio_fan_state': data.get('gpio_fan_state'),
        'profile': data.get('pwm_fan_profile'),
        'hold': bool(data.get('pwm_fan_hold')),
    }
    return live


def _burn():
    x = 1
    while True:
        x = (x * x + 13) % 1000003


def _start_stress():
    workers = []
    n = max(1, cpu_count())
    for _ in range(n):
        proc = Process(target=_burn, daemon=True)
        proc.start()
        workers.append(proc)
    return workers


def _stop_stress(workers):
    for proc in workers:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.join(timeout=1)
        except Exception:
            pass


def _apply_system(getters, patch):
    getters['on_config_changed']({'system': patch})


def _custom_list(system):
    items = []
    for raw in system.get('pwm_fan_custom_profiles') or []:
        if isinstance(raw, dict):
            items.append(sanitize_custom(raw))
    return items


def _run_calibration(getters):
    try:
        _set_job(state='running', kind='calibrate', profile_id='', message='Holding PWM at 100%…',
                 started_at=_now_iso(), finished_at='', result=None, live=_live(getters))
        _apply_system(getters, {'pwm_fan_hold_percent': 100})
        samples = []
        total = 10
        for i in range(total):
            time.sleep(1)
            live = _live(getters)
            rpm = int(live.get('fan_rpm') or 0)
            samples.append(rpm)
            _set_job(
                message=f'Calibration {i + 1}/{total} — {rpm} RPM, CPU {live.get("cpu_temp")} °C',
                live=live,
                progress={'step': i + 1, 'total': total, 'rpm': rpm, 'cpu_temp': live.get('cpu_temp')},
            )
        max_rpm = max(samples) if samples else 0
        payload = {
            'max_rpm': max_rpm,
            'pwm_max': 255,
            'samples': samples,
            'calibrated_at': _now_iso(),
        }
        if max_rpm > 0:
            _write_json(CALIB_PATH, payload)
        _apply_system(getters, {
            'pwm_fan_hold_percent': None,
            'pwm_fan_max_speed': max_rpm,
        })
        _set_job(
            state='success' if max_rpm > 0 else 'error',
            kind='calibrate',
            message=f'Max speed {max_rpm} RPM' if max_rpm else 'Calibration read 0 RPM',
            finished_at=_now_iso(),
            live=_live(getters),
            result=payload,
        )
    except Exception as exc:
        _apply_system(getters, {'pwm_fan_hold_percent': None})
        _set_job(state='error', kind='calibrate', message=str(exc), finished_at=_now_iso())


def _run_benchmark(getters, profile_id):
    previous = None
    workers = []
    try:
        system = _system(getters)
        previous = system.get('pwm_fan_profile') or 'balanced'
        _set_job(
            state='running', kind='benchmark', profile_id=profile_id,
            message=f'Applying {profile_id}…', started_at=_now_iso(), finished_at='',
            result=None, live=_live(getters), phase='idle',
        )
        _apply_system(getters, {'pwm_fan_profile': profile_id, 'pwm_fan_hold_percent': None})
        samples = []

        def collect(phase, seconds):
            for i in range(seconds):
                time.sleep(1)
                live = _live(getters)
                row = dict(live)
                row['phase'] = phase
                samples.append(row)
                peak = max((int(s.get('fan_rpm') or 0) for s in samples), default=0)
                live['peak_rpm'] = peak
                _set_job(
                    message=f'{phase} {i + 1}/{seconds}',
                    live=live,
                    phase=phase,
                    progress={'step': i + 1, 'total': seconds, 'phase': phase},
                )

        collect('idle', 6)
        _set_job(message='CPU stress…', phase='stress')
        workers = _start_stress()
        collect('stress', 12)
        _stop_stress(workers)
        workers = []
        _set_job(message='Cooling down…', phase='recover')
        collect('recover', 8)

        def avg(key, phase=None):
            rows = [s for s in samples if phase is None or s.get('phase') == phase]
            vals = [float(s[key]) for s in rows if s.get(key) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        def mx(key, phase=None):
            rows = [s for s in samples if phase is None or s.get('phase') == phase]
            vals = [float(s[key]) for s in rows if s.get(key) is not None]
            return round(max(vals), 2) if vals else None

        idle_temps = [float(s['cpu_temp']) for s in samples if s.get('phase') == 'idle' and s.get('cpu_temp') is not None]
        stress_temps = [float(s['cpu_temp']) for s in samples if s.get('phase') == 'stress' and s.get('cpu_temp') is not None]
        recover_temps = [float(s['cpu_temp']) for s in samples if s.get('phase') == 'recover' and s.get('cpu_temp') is not None]
        gen = 0.0
        diss = 0.0
        if len(idle_temps) and len(stress_temps):
            gen = max(0.0, (stress_temps[-1] - idle_temps[0]) / max(1, len(stress_temps)))
        if len(stress_temps) and len(recover_temps) >= 2:
            diss = max(0.0, (stress_temps[-1] - recover_temps[-1]) / max(1, len(recover_temps)))
        peak_temp = mx('cpu_temp') or 0
        avg_rpm = avg('fan_rpm') or 0
        peak_rpm = mx('fan_rpm') or 0
        score = round((diss * 40) + (80 - peak_temp) - (avg_rpm / 80.0), 1)
        result = {
            'profile_id': profile_id,
            'at': _now_iso(),
            'avg_cpu_load': avg('cpu_load'),
            'peak_cpu_load': mx('cpu_load'),
            'avg_gpu_temp': avg('gpu_temp'),
            'peak_cpu_temp': peak_temp,
            'avg_rpm': avg_rpm,
            'peak_rpm': peak_rpm,
            'max_speed': samples[-1].get('max_speed') if samples else 0,
            'heat_generation': round(gen, 3),
            'heat_dissipation': round(diss, 3),
            'score': score,
        }
        benches = dict(system.get('pwm_fan_benchmarks') or {})
        benches[profile_id] = result
        restore = previous if previous != profile_id else profile_id
        _apply_system(getters, {
            'pwm_fan_profile': restore,
            'pwm_fan_benchmarks': benches,
        })
        _set_job(
            state='success', kind='benchmark', profile_id=profile_id,
            message=f'Benchmark done — score {score}',
            finished_at=_now_iso(), live=_live(getters), result=result, phase='done',
        )
    except Exception as exc:
        _stop_stress(workers)
        if previous:
            try:
                _apply_system(getters, {'pwm_fan_profile': previous, 'pwm_fan_hold_percent': None})
            except Exception:
                pass
        _set_job(state='error', kind='benchmark', profile_id=profile_id, message=str(exc),
                 finished_at=_now_iso(), traceback=traceback.format_exc())


def register_fan_control_routes(app, api_prefix, static_folder, getters):
    @app.route('/fan-controls')
    @app.route('/fan-controls/')
    @cross_origin()
    def fan_controls_index():
        return send_from_directory(f'{static_folder}/fan-controls', 'index.html')

    @app.route('/fan-controls/<path:filename>')
    @cross_origin()
    def fan_controls_assets(filename):
        return send_from_directory(f'{static_folder}/fan-controls', filename)

    @app.route(f'{api_prefix}/get-fan-controls')
    @cross_origin()
    def get_fan_controls():
        system = _system(getters)
        customs = _custom_list(system)
        calib = _read_json(CALIB_PATH, {}) or {}
        return {
            'status': True,
            'data': {
                'pwm': {
                    'active': system.get('pwm_fan_profile') or 'balanced',
                    'builtin': BUILTIN_PWM_PROFILES,
                    'custom': customs,
                    'benchmarks': system.get('pwm_fan_benchmarks') or {},
                    'gpio_fan_mode': system.get('gpio_fan_mode', 1),
                    'gpio_fan_led': system.get('gpio_fan_led', 'follow'),
                    'hold_percent': system.get('pwm_fan_hold_percent'),
                    'calibration': {
                        'max_rpm': calib.get('max_rpm') or 0,
                        'calibrated_at': calib.get('calibrated_at') or '',
                        'samples': calib.get('samples') or [],
                    },
                },
                'rgb': {
                    'enable': bool(system.get('rgb_enable', True)),
                    'style': system.get('rgb_style') or 'breathing',
                    'color': system.get('rgb_color') or '#0a1aff',
                    'brightness': int(system.get('rgb_brightness') or 100),
                    'speed': int(system.get('rgb_speed') or 50),
                    'led_count': int(system.get('rgb_led_count') or 4),
                    'styles': RGB_STYLE_META,
                },
                'live': _live(getters),
                'job': _job(),
            },
        }

    @app.route(f'{api_prefix}/fan-live')
    @cross_origin()
    def fan_live():
        return {'status': True, 'data': {'live': _live(getters), 'job': _job()}}

    @app.route(f'{api_prefix}/apply-pwm-profile', methods=['POST'])
    @cross_origin()
    def apply_pwm_profile():
        body = request.get_json(silent=True) or {}
        profile_id = str(body.get('id') or '').strip()
        if not profile_id:
            return {'status': False, 'error': 'Missing profile id'}, 400
        system = _system(getters)
        known = {p['id'] for p in BUILTIN_PWM_PROFILES}
        known.update(p['id'] for p in _custom_list(system))
        if profile_id not in known:
            return {'status': False, 'error': f'Unknown profile {profile_id}'}, 400
        _apply_system(getters, {'pwm_fan_profile': profile_id, 'pwm_fan_hold_percent': None})
        return {'status': True, 'data': {'active': profile_id}}

    @app.route(f'{api_prefix}/save-custom-fan-profile', methods=['POST'])
    @cross_origin()
    def save_custom_fan_profile():
        body = request.get_json(silent=True) or {}
        system = _system(getters)
        customs = _custom_list(system)
        pid = str(body.get('id') or '').strip() or f'custom_{int(time.time())}'
        saved = sanitize_custom({
            'id': pid,
            'name': body.get('name') or 'Custom',
            'steps': body.get('steps') or DEFAULT_CUSTOM_STEPS,
        }, fallback_id=pid)
        replaced = False
        next_list = []
        for item in customs:
            if item['id'] == saved['id']:
                next_list.append(saved)
                replaced = True
            else:
                next_list.append(item)
        if not replaced:
            if len(next_list) >= 12:
                return {'status': False, 'error': 'Maximum 12 custom profiles'}, 400
            next_list.append(saved)
        patch = {'pwm_fan_custom_profiles': next_list}
        if body.get('apply'):
            patch['pwm_fan_profile'] = saved['id']
            patch['pwm_fan_hold_percent'] = None
        _apply_system(getters, patch)
        return {'status': True, 'data': {'profile': saved, 'custom': next_list}}

    @app.route(f'{api_prefix}/delete-custom-fan-profile', methods=['POST'])
    @cross_origin()
    def delete_custom_fan_profile():
        body = request.get_json(silent=True) or {}
        pid = str(body.get('id') or '').strip()
        system = _system(getters)
        customs = [p for p in _custom_list(system) if p['id'] != pid]
        patch = {'pwm_fan_custom_profiles': customs}
        if (system.get('pwm_fan_profile') or '') == pid:
            patch['pwm_fan_profile'] = 'balanced'
        _apply_system(getters, patch)
        return {'status': True, 'data': {'custom': customs}}

    @app.route(f'{api_prefix}/set-rgb-fan', methods=['POST'])
    @cross_origin()
    def set_rgb_fan():
        body = request.get_json(silent=True) or {}
        patch = {}
        if 'enable' in body:
            patch['rgb_enable'] = bool(body['enable'])
        if 'style' in body:
            style = str(body['style'])
            allowed = {item['id'] for item in RGB_STYLE_META}
            if style not in allowed:
                return {'status': False, 'error': f'Unknown RGB style {style}'}, 400
            patch['rgb_style'] = style
        if 'color' in body:
            patch['rgb_color'] = str(body['color'])
        if 'brightness' in body:
            patch['rgb_brightness'] = max(0, min(100, int(body['brightness'])))
        if 'speed' in body:
            patch['rgb_speed'] = max(0, min(100, int(body['speed'])))
        if 'led_count' in body:
            patch['rgb_led_count'] = max(1, min(16, int(body['led_count'])))
        if not patch:
            return {'status': False, 'error': 'No RGB settings'}, 400
        _apply_system(getters, patch)
        return {'status': True, 'data': patch}

    @app.route(f'{api_prefix}/start-fan-calibration', methods=['POST'])
    @cross_origin()
    def start_fan_calibration():
        global _job_thread
        with _lock:
            current = _job()
            if current.get('state') == 'running' and _job_thread and _job_thread.is_alive():
                return {'status': False, 'error': 'A fan job is already running', 'data': current}, 409
            _set_job(state='running', kind='calibrate', message='Starting calibration…',
                     started_at=_now_iso(), finished_at='', result=None)
            _job_thread = threading.Thread(target=_run_calibration, args=(getters,), daemon=True)
            _job_thread.start()
        return {'status': True, 'data': _job()}

    @app.route(f'{api_prefix}/start-fan-benchmark', methods=['POST'])
    @cross_origin()
    def start_fan_benchmark():
        global _job_thread
        body = request.get_json(silent=True) or {}
        profile_id = str(body.get('id') or '').strip()
        if not profile_id:
            return {'status': False, 'error': 'Missing profile id'}, 400
        with _lock:
            current = _job()
            if current.get('state') == 'running' and _job_thread and _job_thread.is_alive():
                return {'status': False, 'error': 'A fan job is already running', 'data': current}, 409
            _set_job(state='running', kind='benchmark', profile_id=profile_id,
                     message=f'Starting benchmark for {profile_id}…',
                     started_at=_now_iso(), finished_at='', result=None)
            _job_thread = threading.Thread(target=_run_benchmark, args=(getters, profile_id), daemon=True)
            _job_thread.start()
        return {'status': True, 'data': _job()}
