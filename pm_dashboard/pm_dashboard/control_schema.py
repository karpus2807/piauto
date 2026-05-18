"""Config schema, validation, and one-click presets for the control center."""

OLED_PAGE_IDS = (
    'home', 'storage', 'network', 'cpu', 'gpu', 'fans',
    'ram', 'temps', 'services', 'heart',
)

OLED_PROFILES = ('full', 'minimal', 'server', 'custom')

RGB_STYLES = ('solid', 'breathing', 'flow', 'rainbow')

FAN_MODES = (
    {'value': 0, 'label': 'Always On'},
    {'value': 1, 'label': 'Performance'},
    {'value': 2, 'label': 'Cool'},
    {'value': 3, 'label': 'Balanced'},
    {'value': 4, 'label': 'Quiet'},
)

GPIO_FAN_LED = ('on', 'off', 'follow')

PRESETS = {
    'quiet_desktop': {
        'label': 'Quiet Desktop',
        'description': 'Low fan noise, minimal OLED, soft RGB',
        'config': {
            'gpio_fan_mode': 4,
            'oled_pages_profile': 'minimal',
            'oled_enable': True,
            'rgb_enable': True,
            'rgb_style': 'breathing',
            'rgb_brightness': 25,
            'rgb_speed': 30,
        },
    },
    'performance': {
        'label': 'Performance',
        'description': 'Aggressive cooling, full OLED carousel',
        'config': {
            'gpio_fan_mode': 1,
            'oled_pages_profile': 'full',
            'oled_enable': True,
            'rgb_enable': True,
            'rgb_style': 'flow',
            'rgb_brightness': 60,
            'rgb_speed': 70,
        },
    },
    'server': {
        'label': 'Server',
        'description': 'Network + CPU focus, alerts on',
        'config': {
            'gpio_fan_mode': 3,
            'oled_pages_profile': 'server',
            'oled_enable': True,
            'oled_alert_enable': True,
            'oled_alert_cpu_percent': 90,
            'oled_alert_disk_percent': 90,
            'rgb_enable': False,
        },
    },
    'night': {
        'label': 'Night',
        'description': 'RGB off, quiet fans, home OLED only',
        'config': {
            'gpio_fan_mode': 4,
            'rgb_enable': False,
            'oled_pages_profile': 'minimal',
            'oled_home_duration': 10,
            'oled_page_duration': 4,
        },
    },
    'rgb_rainbow': {
        'label': 'RGB Show',
        'description': 'Rainbow LEDs, balanced cooling',
        'config': {
            'rgb_enable': True,
            'rgb_style': 'rainbow',
            'rgb_brightness': 80,
            'rgb_speed': 60,
            'gpio_fan_mode': 3,
        },
    },
    'oled_off': {
        'label': 'OLED Off',
        'description': 'Disable case display',
        'config': {'oled_enable': False},
    },
}

# Keys the control center may set (subset of full system config).
CONFIG_SPEC = {
    'data_interval': {'type': 'int', 'min': 1, 'max': 60, 'label': 'Metrics interval (s)'},
    'temperature_unit': {'type': 'choice', 'choices': ['C', 'F'], 'label': 'Temperature unit'},
    'rgb_enable': {'type': 'bool', 'label': 'RGB enabled'},
    'rgb_color': {'type': 'color', 'label': 'RGB color'},
    'rgb_brightness': {'type': 'int', 'min': 0, 'max': 100, 'label': 'RGB brightness %'},
    'rgb_style': {'type': 'choice', 'choices': list(RGB_STYLES), 'label': 'RGB style'},
    'rgb_speed': {'type': 'int', 'min': 0, 'max': 100, 'label': 'RGB speed %'},
    'rgb_led_count': {'type': 'int', 'min': 1, 'max': 64, 'label': 'LED count'},
    'gpio_fan_mode': {'type': 'int', 'min': 0, 'max': 4, 'label': 'Side fan mode'},
    'gpio_fan_led': {'type': 'choice', 'choices': list(GPIO_FAN_LED), 'label': 'Fan LED'},
    'oled_enable': {'type': 'bool', 'label': 'OLED enabled'},
    'oled_rotation': {'type': 'choice', 'choices': [0, 180], 'label': 'OLED rotation'},
    'oled_disk': {'type': 'string', 'label': 'OLED disk source'},
    'oled_network_interface': {'type': 'string', 'label': 'OLED network iface'},
    'oled_home_duration': {'type': 'int', 'min': 3, 'max': 120, 'label': 'Home page (s)'},
    'oled_page_duration': {'type': 'int', 'min': 2, 'max': 60, 'label': 'Other pages (s)'},
    'oled_pages_profile': {'type': 'choice', 'choices': list(OLED_PROFILES), 'label': 'OLED profile'},
    'oled_pages': {'type': 'pages', 'label': 'Custom pages (comma list)'},
    'oled_alert_enable': {'type': 'bool', 'label': 'OLED alerts'},
    'oled_alert_duration': {'type': 'int', 'min': 1, 'max': 15, 'label': 'Alert duration (s)'},
    'oled_alert_cooldown': {'type': 'int', 'min': 5, 'max': 300, 'label': 'Alert cooldown (s)'},
    'oled_alert_cpu_temp': {'type': 'float', 'min': 50, 'max': 95, 'label': 'Alert CPU temp'},
    'oled_alert_cpu_percent': {'type': 'float', 'min': 50, 'max': 100, 'label': 'Alert CPU %'},
    'oled_alert_disk_percent': {'type': 'float', 'min': 50, 'max': 100, 'label': 'Alert disk %'},
    'oled_alert_gpu_temp': {'type': 'float', 'min': 50, 'max': 95, 'label': 'Alert GPU temp'},
    'oled_alert_undervoltage': {'type': 'bool', 'label': 'PWR undervoltage alert'},
    'oled_sleep_timeout': {'type': 'int', 'min': 0, 'max': 600, 'label': 'OLED sleep timeout (s)'},
}

UI_SECTIONS = (
    {'id': 'machine', 'label': 'Machine', 'keys': ()},
    {'id': 'rgb', 'label': 'RGB', 'keys': (
        'rgb_enable', 'rgb_style', 'rgb_color', 'rgb_brightness', 'rgb_speed', 'rgb_led_count',
    )},
    {'id': 'fans', 'label': 'Fans', 'keys': ('gpio_fan_mode', 'gpio_fan_led')},
    {'id': 'oled', 'label': 'OLED', 'keys': (
        'oled_enable', 'oled_pages_profile', 'oled_pages', 'oled_home_duration',
        'oled_page_duration', 'oled_rotation', 'oled_disk', 'oled_network_interface',
    )},
    {'id': 'alerts', 'label': 'Alerts', 'keys': (
        'oled_alert_enable', 'oled_alert_cpu_temp', 'oled_alert_cpu_percent',
        'oled_alert_disk_percent', 'oled_alert_gpu_temp', 'oled_alert_undervoltage',
        'oled_alert_duration', 'oled_alert_cooldown',
    )},
    {'id': 'system', 'label': 'System', 'keys': ('temperature_unit', 'data_interval')},
)


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('1', 'true', 'yes', 'on')
    return bool(value)


def validate_key(key, value):
    if key not in CONFIG_SPEC:
        return False, f'Unknown key: {key}'
    spec = CONFIG_SPEC[key]
    kind = spec['type']

    if kind == 'bool':
        return True, _coerce_bool(value)
    if kind == 'int':
        try:
            v = int(value)
        except (TypeError, ValueError):
            return False, f'{key} must be an integer'
        if v < spec['min'] or v > spec['max']:
            return False, f'{key} must be between {spec["min"]} and {spec["max"]}'
        return True, v
    if kind == 'float':
        try:
            v = float(value)
        except (TypeError, ValueError):
            return False, f'{key} must be a number'
        if v < spec['min'] or v > spec['max']:
            return False, f'{key} must be between {spec["min"]} and {spec["max"]}'
        return True, v
    if kind == 'choice':
        if value not in spec['choices']:
            return False, f'{key} invalid choice'
        return True, value
    if kind == 'color':
        text = str(value).strip()
        if not text.startswith('#') or len(text) not in (4, 7):
            return False, f'{key} must be a hex color like #0a1aff'
        return True, text
    if kind == 'pages':
        if isinstance(value, list):
            pages = [str(p).strip() for p in value if str(p).strip()]
        else:
            pages = [p.strip() for p in str(value).split(',') if p.strip()]
        bad = [p for p in pages if p not in OLED_PAGE_IDS]
        if bad:
            return False, f'Unknown pages: {bad}'
        return True, ','.join(pages)
    if kind == 'string':
        return True, str(value)
    return False, f'Unsupported type for {key}'


def validate_system_patch(patch):
    """Validate partial system config; return (ok, cleaned_dict|error_msg)."""
    if not isinstance(patch, dict):
        return False, 'Body must be a JSON object'
    cleaned = {}
    for key, value in patch.items():
        ok, result = validate_key(key, value)
        if not ok:
            return False, result
        cleaned[key] = result
    if 'oled_pages' in cleaned:
        cleaned['oled_pages_profile'] = 'custom'
    return True, cleaned


def build_control_schema(config, peripherals=None):
    system = (config or {}).get('system', {})
    sections = []
    for section in UI_SECTIONS:
        fields = []
        for key in section['keys']:
            if key not in CONFIG_SPEC:
                continue
            spec = dict(CONFIG_SPEC[key])
            spec['key'] = key
            spec['value'] = system.get(key)
            fields.append(spec)
        sections.append({
            'id': section['id'],
            'label': section['label'],
            'fields': fields,
        })

    presets = [
        {
            'id': pid,
            'label': p['label'],
            'description': p['description'],
        }
        for pid, p in PRESETS.items()
    ]

    return {
        'presets': presets,
        'fan_modes': FAN_MODES,
        'oled_profiles': list(OLED_PROFILES),
        'oled_page_ids': list(OLED_PAGE_IDS),
        'sections': sections,
        'config': system,
        'peripherals': peripherals or [],
    }
