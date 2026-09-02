"""PWM and RGB fan profile definitions used by FanAddon and the dashboard."""

BUILTIN_PWM_PROFILES = [
    {
        'id': 'silent',
        'name': 'Silent',
        'summary': 'Off until warm, then a slow ramp. Quietest stock curve.',
        'steps': [
            {'name': 'OFF', 'until_c': 48, 'percent': 0},
            {'name': 'LOW', 'until_c': 58, 'percent': 18},
            {'name': 'MID', 'until_c': 68, 'percent': 40},
            {'name': 'HIGH', 'until_c': 78, 'percent': 70},
            {'name': 'FULL', 'until_c': 200, 'percent': 100},
        ],
    },
    {
        'id': 'quiet',
        'name': 'Quiet',
        'summary': 'Low duty until the mid-50s. Good for overnight.',
        'steps': [
            {'name': 'OFF', 'until_c': 42, 'percent': 0},
            {'name': 'LOW', 'until_c': 50, 'percent': 22},
            {'name': 'MID', 'until_c': 58, 'percent': 45},
            {'name': 'HIGH', 'until_c': 66, 'percent': 70},
            {'name': 'FULL', 'until_c': 200, 'percent': 100},
        ],
    },
    {
        'id': 'balanced',
        'name': 'Balanced',
        'summary': 'Default PiAuto curve — tight 34–43 °C bands.',
        'steps': [
            {'name': 'OFF', 'until_c': 34, 'percent': 0},
            {'name': 'LOW', 'until_c': 38, 'percent': 25},
            {'name': 'MEDIUM', 'until_c': 41, 'percent': 50},
            {'name': 'HIGH', 'until_c': 43, 'percent': 75},
            {'name': 'FULL', 'until_c': 200, 'percent': 100},
        ],
    },
    {
        'id': 'cool',
        'name': 'Cool',
        'summary': 'Spins earlier and harder to keep CPU in the low 40s.',
        'steps': [
            {'name': 'OFF', 'until_c': 32, 'percent': 0},
            {'name': 'LOW', 'until_c': 36, 'percent': 35},
            {'name': 'MID', 'until_c': 40, 'percent': 60},
            {'name': 'HIGH', 'until_c': 44, 'percent': 85},
            {'name': 'FULL', 'until_c': 200, 'percent': 100},
        ],
    },
    {
        'id': 'performance',
        'name': 'Performance',
        'summary': 'Aggressive cooling for compiles, transcode, stress.',
        'steps': [
            {'name': 'LOW', 'until_c': 30, 'percent': 30},
            {'name': 'MID', 'until_c': 36, 'percent': 55},
            {'name': 'HIGH', 'until_c': 40, 'percent': 80},
            {'name': 'FULL', 'until_c': 200, 'percent': 100},
        ],
    },
    {
        'id': 'full',
        'name': 'Full blast',
        'summary': 'Always 100% duty. Loudest, maximum dissipation.',
        'steps': [
            {'name': 'FULL', 'until_c': 200, 'percent': 100},
        ],
    },
    {
        'id': 'night',
        'name': 'Night',
        'summary': 'Cap at 40% until it really heats, then step up.',
        'steps': [
            {'name': 'HUSH', 'until_c': 50, 'percent': 15},
            {'name': 'SOFT', 'until_c': 62, 'percent': 40},
            {'name': 'WARM', 'until_c': 72, 'percent': 70},
            {'name': 'FULL', 'until_c': 200, 'percent': 100},
        ],
    },
]

RGB_STYLE_META = [
    {'id': 'solid', 'name': 'Solid', 'summary': 'Single color, no motion.'},
    {'id': 'breathing', 'name': 'Breathing', 'summary': 'Fade in and out on one color.'},
    {'id': 'flow', 'name': 'Flow', 'summary': 'Color travels along the strip.'},
    {'id': 'flow_reverse', 'name': 'Flow reverse', 'summary': 'Flow in the opposite direction.'},
    {'id': 'rainbow', 'name': 'Rainbow', 'summary': 'Full spectrum cycle.'},
    {'id': 'rainbow_reverse', 'name': 'Rainbow reverse', 'summary': 'Rainbow the other way.'},
    {'id': 'hue_cycle', 'name': 'Hue cycle', 'summary': 'Whole strip shifts hue together.'},
]

DEFAULT_CUSTOM_STEPS = [
    {'name': 'Idle', 'until_c': 40, 'percent': 15},
    {'name': 'Warm', 'until_c': 55, 'percent': 50},
    {'name': 'Hot', 'until_c': 200, 'percent': 100},
]


def steps_to_levels(steps):
    cleaned = []
    for i, raw in enumerate(steps or []):
        try:
            until = float(raw.get('until_c', 40 + i * 10))
        except (TypeError, ValueError):
            until = 40.0 + i * 10
        try:
            percent = int(raw.get('percent', 0))
        except (TypeError, ValueError):
            percent = 0
        percent = max(0, min(100, percent))
        name = str(raw.get('name') or f'Step {i + 1}')[:24]
        cleaned.append({'until_c': until, 'percent': percent, 'name': name})
    cleaned.sort(key=lambda item: item['until_c'])
    if not cleaned:
        cleaned = [{'until_c': 34, 'percent': 0, 'name': 'OFF'}, {'until_c': 200, 'percent': 100, 'name': 'FULL'}]
    if cleaned[-1]['until_c'] < 200:
        cleaned[-1]['until_c'] = 200
    levels = []
    prev_high = -200
    for i, item in enumerate(cleaned):
        high = item['until_c']
        low = prev_high if i == 0 else prev_high - 0.3
        levels.append({
            'name': item['name'],
            'low': low,
            'high': high,
            'percent': item['percent'],
        })
        prev_high = high
    return levels


def builtin_by_id(profile_id):
    for item in BUILTIN_PWM_PROFILES:
        if item['id'] == profile_id:
            return item
    return None


def resolve_profile(profile_id, custom_profiles=None):
    found = builtin_by_id(profile_id)
    if found:
        return found
    for item in custom_profiles or []:
        if item.get('id') == profile_id:
            return item
    return builtin_by_id('balanced')


def sanitize_custom(raw, fallback_id=None):
    data = raw if isinstance(raw, dict) else {}
    pid = str(data.get('id') or fallback_id or 'custom')
    name = str(data.get('name') or 'Custom')[:40]
    steps_in = data.get('steps') or []
    steps = []
    for i, step in enumerate(steps_in[:12]):
        if not isinstance(step, dict):
            continue
        try:
            until_c = float(step.get('until_c', 40 + i * 10))
        except (TypeError, ValueError):
            until_c = 40.0 + i * 10
        try:
            percent = int(step.get('percent', 0))
        except (TypeError, ValueError):
            percent = 0
        steps.append({
            'name': str(step.get('name') or f'Step {i + 1}')[:24],
            'until_c': max(0, min(200, until_c)),
            'percent': max(0, min(100, percent)),
        })
    if not steps:
        steps = [dict(s) for s in DEFAULT_CUSTOM_STEPS]
    return {'id': pid, 'name': name, 'kind': 'custom', 'steps': steps}
