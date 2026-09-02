from . import Module, register

register(Module(
    name="pwm_fan",
    peripherals=[
        'pwm_fan_speed',
    ],
    default_config={
        'pwm_fan_profile': 'balanced',
        'pwm_fan_custom_profiles': [],
        'pwm_fan_hold_percent': None,
        'pwm_fan_benchmarks': {},
    },
))
