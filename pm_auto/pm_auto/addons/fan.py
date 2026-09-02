from pm_auto.libs.addon import Addon
from pm_auto.libs.utils import log_error
from pm_auto.addons.fan_profiles import (
    resolve_profile,
    sanitize_custom,
    steps_to_levels,
)

import os
import json
import time
import asyncio

FANS = [
    'pwm_fan', # Deprecated
    'gpio_fan', # Deprecated
    'spc_fan', # Deprecated
    'pwm_fan_speed',
    'gpio_fan_state',
    'gpio_fan_led',
    'spc_fan_power'
]

# 5 levels of fan speed, from high to low
GPIO_FAN_MODES = ['Always On', 'Performance', 'Cool', 'Balanced', 'Quiet']
# PWM duty is percent of calibrated max (pwm1 0-255). ~0.3°C down-hysteresis
# so the tight 34/38/41/43 bands do not chatter.
FAN_LEVELS = steps_to_levels(resolve_profile('balanced')['steps'])
PWM_FAN_CALIBRATION_FILE = '/opt/pironman5/fan_calibration.json'

INTERVAL = 1

class FanAddon(Addon):
    
    DEFAULT_CONFIG = {
        "gpio_fan_pin": 6,
        "gpio_fan_led_pin": 5,
        "gpio_fan_led": 'follow',
        "gpio_fan_mode": 1,
        "pwm_fan_profile": "balanced",
        "pwm_fan_custom_profiles": [],
        "pwm_fan_hold_percent": None,
        "pwm_fan_benchmarks": {},
    }

    @log_error
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fans = self.peripherals

        self.gpio_fan = Fan()
        self.spc_fan = Fan()
        self.pwm_fan = Fan()

        self.temperature_unit = 'C'
        self.interval = 1

        if 'gpio_fan_state' in fans or 'gpio_fan' in fans: # gpio_fan is deprecated, use gpio_fan_state instead
            pin = self.config["gpio_fan_pin"]
            if 'gpio_fan_led' in fans:
                led_pin = self.config["gpio_fan_led_pin"]
                self.log.debug(f"Init GPIO Fan with pin: {pin}, led_pin: {led_pin}")
                self.gpio_fan = GPIOFan(pin, led_pin=led_pin, log=self.log)
                self.gpio_fan.set_led(self.config["gpio_fan_led"])
            else:
                self.log.debug(f"Init GPIO Fan with pin: {pin}")
                self.gpio_fan = GPIOFan(pin, log=self.log)
            if not self.gpio_fan.is_ready():
                self.log.warning("GPIO Fan init failed, disable gpio_fan control")
        if 'spc_fan_power' in fans or 'spc_fan' in fans: # spc_fan is deprecated, use spc_fan_power instead
            self.log.debug("Init SPC Fan")
            self.spc_fan = SPCFan(log=self.log)
            if not self.spc_fan.is_ready():
                self.log.warning("SPC Fan init failed, disable spc_fan control")
        if 'pwm_fan_speed' in fans or 'pwm_fan' in fans: # pwm_fan is deprecated, use pwm_fan_speed instead
            self.log.debug("Init PWM Fan")
            self.pwm_fan = PWMFan(log=self.log)
            if not self.pwm_fan.is_ready():
                self.log.warning("PWM Fan init failed, disable pwm_fan control")

        self.level = 0
        self.initial = True
        self._calib_done = False
        # Re-read after hardware init. self.config already merged saved
        # values in update_config(); never resume a calibration hold across reboot.
        self.gpio_fan_mode = self.config.get('gpio_fan_mode', 1)
        self.hold_percent = None
        self.profile_id = self.config.get('pwm_fan_profile', 'balanced')
        self.custom_profiles = [
            sanitize_custom(item) for item in (self.config.get('pwm_fan_custom_profiles') or [])
            if isinstance(item, dict)
        ]
        self.levels = steps_to_levels(resolve_profile(self.profile_id, self.custom_profiles)['steps'])
        self.log.info(f"PWM fan profile on start: {self.profile_id} ({len(self.custom_profiles)} custom)")
        self._is_ready = True

    @log_error
    def update_config(self, config, init=False):
        '''
        Update config.

        Args:
            config (Dict): New config dict.

        Returns:
            A dict of config patch to update the config file.
        '''
        patch = {}
        config = config or {}
        # Merge saved keys into self.config first. Addon.__init__ copies
        # DEFAULT_CONFIG only, so without this reboot always falls back to
        # Balanced / empty custom profiles / default GPIO mode.
        for key, value in config.items():
            if key not in self.DEFAULT_CONFIG:
                continue
            if init and key == 'pwm_fan_hold_percent':
                self.config[key] = None
                continue
            self.config[key] = value
        if not hasattr(self, 'custom_profiles'):
            self.custom_profiles = [
                sanitize_custom(item)
                for item in (self.config.get('pwm_fan_custom_profiles') or [])
                if isinstance(item, dict)
            ]
        if not hasattr(self, 'profile_id'):
            self.profile_id = self.config.get('pwm_fan_profile', 'balanced')
        if not hasattr(self, 'hold_percent'):
            self.hold_percent = None
        if not hasattr(self, 'levels'):
            self.levels = FAN_LEVELS
        if "gpio_fan_pin" in config:
            _pin = config['gpio_fan_pin']
            if not init and self.gpio_fan.is_ready():
                success = self.gpio_fan.change_pin(config["gpio_fan_pin"])
                if success:
                    patch['gpio_fan_pin'] = _pin
                    self.log.debug(f"Update gpio_fan_pin to {_pin}")
                else:
                    self.log.error(f"Change gpio_fan_pin to {_pin} failed")
            else:
                patch['gpio_fan_pin'] = _pin
        if "gpio_fan_mode" in config:
            _mode = config['gpio_fan_mode']
            if _mode in range(len(GPIO_FAN_MODES)):
                self.log.debug(f"Update gpio_fan_mode to {_mode}")
                self.gpio_fan_mode = _mode
                patch['gpio_fan_mode'] = _mode
            else:
                self.log.error(f"Invalid gpio_fan_mode: {_mode}")
        if "gpio_fan_led" in config:
            _led = config['gpio_fan_led']
            if _led in ['follow', 'on', 'off']:
                if not init and self.gpio_fan.is_ready():
                    success = self.gpio_fan.set_led(_led)
                    if success:
                        self.log.debug(f"Update gpio_fan_led to {_led}")
                        patch['gpio_fan_led'] = _led
                    else:
                        self.log.error(f"Change gpio_fan_led to {_led} failed")
                else:
                    patch['gpio_fan_led'] = _led
            else:
                self.log.error(f"Invalid gpio_fan_led: {_led}")
        if "gpio_fan_led_pin" in config:
            _led_pin = config['gpio_fan_led_pin']
            if not init and self.gpio_fan.is_ready():
                success = self.gpio_fan.change_led_pin(_led_pin)
                if success:
                    self.log.debug(f"Update gpio_fan_led_pin to {_led_pin}")
                    patch['gpio_fan_led_pin'] = _led_pin
                else:
                    self.log.error(f"Change gpio_fan_led_pin to {_led_pin} failed")
            else:
                patch['gpio_fan_led_pin'] = _led_pin
        # Load custom curves before the active profile id so a saved custom_*
        # id can resolve instead of falling back to Balanced.
        if "pwm_fan_custom_profiles" in config:
            customs = config.get('pwm_fan_custom_profiles') or []
            if isinstance(customs, list):
                self.custom_profiles = [
                    sanitize_custom(item) for item in customs if isinstance(item, dict)
                ]
                patch['pwm_fan_custom_profiles'] = self.custom_profiles
                self.levels = steps_to_levels(
                    resolve_profile(self.profile_id, self.custom_profiles)['steps']
                )
                self.log.debug(f"Update pwm_fan_custom_profiles ({len(self.custom_profiles)})")
        if "pwm_fan_profile" in config:
            _profile = str(config.get('pwm_fan_profile') or 'balanced')
            self.profile_id = _profile
            self.levels = steps_to_levels(resolve_profile(_profile, self.custom_profiles)['steps'])
            self.level = 0
            patch['pwm_fan_profile'] = _profile
            self.log.debug(f"Update pwm_fan_profile to {_profile}")
        if init:
            self.hold_percent = None
            if config.get('pwm_fan_hold_percent') not in (None, ''):
                patch['pwm_fan_hold_percent'] = None
        elif "pwm_fan_hold_percent" in config:
            hold = config.get('pwm_fan_hold_percent')
            if hold is None or hold == '':
                self.hold_percent = None
                patch['pwm_fan_hold_percent'] = None
            else:
                try:
                    self.hold_percent = max(0, min(100, int(hold)))
                    patch['pwm_fan_hold_percent'] = self.hold_percent
                except (TypeError, ValueError):
                    self.log.error(f"Invalid pwm_fan_hold_percent: {hold}")
        if "pwm_fan_max_speed" in config and getattr(self, 'pwm_fan', None) and self.pwm_fan.is_ready():
            try:
                self.pwm_fan.max_rpm = int(config.get('pwm_fan_max_speed') or 0)
            except (TypeError, ValueError):
                pass
        if "pwm_fan_benchmarks" in config:
            benches = config.get('pwm_fan_benchmarks')
            if isinstance(benches, dict):
                patch['pwm_fan_benchmarks'] = benches
        return patch

    @log_error
    def get_cpu_temperature(self):
        file = '/sys/class/thermal/thermal_zone0/temp'
        try:
            with open(file, 'r') as f:
                temp = int(f.read())
            return round(temp/1000, 2)
        except Exception as e:
            self.log.error(f'get_cpu_temperature error: {e}')
            return 0.0

    @log_error
    def run(self):
        data = {}
        if self.pwm_fan.is_ready() and not self._calib_done:
            self._calib_done = True
            calib = self.pwm_fan.calibrate_max_speed()
            if calib:
                data['pwm_fan_max_speed'] = calib.get('max_rpm', 0)

        temperature = self.get_cpu_temperature()
        self.log.debug(f"cpu temperature: {temperature} \'C")
        levels = self.levels or FAN_LEVELS
        if self.hold_percent is not None:
            power = self.hold_percent
            data['pwm_fan_profile'] = self.profile_id
            data['pwm_fan_hold'] = True
            if self.gpio_fan.is_ready():
                gpio_fan_state = True if self.gpio_fan_mode == 0 else power >= 50
                data['gpio_fan_state'] = gpio_fan_state
                self.gpio_fan.set(gpio_fan_state)
            if self.spc_fan.is_ready():
                self.spc_fan.set_power(power)
                data['spc_fan_power'] = power
            if self.pwm_fan.is_ready():
                self.pwm_fan.set_percent(power)
                data['pwm_fan_speed'] = self.pwm_fan.get_speed()
                if getattr(self.pwm_fan, 'max_rpm', 0):
                    data['pwm_fan_max_speed'] = self.pwm_fan.max_rpm
            data['pwm_fan_power'] = power
            self.event.publish('data_changed', data)
            return

        changed = False
        direction = ""
        if temperature < levels[self.level]["low"]:
            self.level -= 1
            changed = True
            direction = "low"
        elif temperature >= levels[self.level]["high"]:
            self.level += 1
            changed = True
            direction = "high"

        self.level = max(0, min(self.level, len(levels) - 1))
        power = levels[self.level]['percent']

        if self.gpio_fan.is_ready():
            gpio_fan_state = self.level >= self.gpio_fan_mode
            data['gpio_fan_state'] = gpio_fan_state
            self.gpio_fan.set(gpio_fan_state)
        if self.spc_fan.is_ready():
            self.spc_fan.set_power(power)
            data['spc_fan_power'] = power
        if self.pwm_fan.is_ready():
            self.pwm_fan.set_percent(power)
            data['pwm_fan_speed'] = self.pwm_fan.get_speed()
            if getattr(self.pwm_fan, 'max_rpm', 0):
                data['pwm_fan_max_speed'] = self.pwm_fan.max_rpm

        data['pwm_fan_profile'] = self.profile_id
        data['pwm_fan_power'] = power
        data['pwm_fan_hold'] = False

        if changed:
            self.log.info(f"set fan level: {levels[self.level]['name']}")
            self.log.info(f"set fan power: {power}")
            self.log.info(
                f"cpu temperature: {temperature} \'C, {direction}er than {levels[self.level][direction]}")
        elif self.initial:
            self.log.info(f"cpu temperature: {temperature} \'C")
            self.initial = False

        self.event.publish('data_changed', data)
        
    @log_error
    async def _main(self):
        while self.running:
            self.run()
            await asyncio.sleep(self.interval)

    @log_error
    def off(self):
        if self.gpio_fan.is_ready():
            self.gpio_fan.off()
        if self.spc_fan.is_ready():
            self.spc_fan.off()
        if self.pwm_fan.is_ready():
            self.pwm_fan.off()

    @log_error
    def close(self):
        if self.gpio_fan.is_ready():
            self.gpio_fan.close()
        if self.spc_fan.is_ready():
            self.spc_fan.close()
        if self.pwm_fan.is_ready():
            self.pwm_fan.close()
        self.log.debug("FanService closed")

    @log_error
    async def _stop(self):
        self.off()
        self.close()

def check_ready(func):
    def wrapper(self, *args, **kwargs):
        if not self.is_ready():
            self.log.warning(f"{self.__class__.__name__} is not ready")
            return
        return func(self, *args, **kwargs)
    return wrapper

class Fan():
    def __init__(self, log=None):
        self.log = log
        self._is_ready = False

    def is_ready(self):
        return self._is_ready
    
    # Decorator to check if the fan is ready
class GPIOFan(Fan):
    def __init__(self, pin, *args, led_pin=None, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            from pm_auto.libs.pin import Pin, PinMode

            # Init fan
            self.pin = pin
            self.fan = Pin(pin, PinMode.OUT)
            self.fan.off()

            # Init LED if exist
            self.led = None
            self.led_follow = False
            if led_pin is not None:
                self.led = Pin(led_pin, PinMode.OUT)
                self.led.off()
            self._is_ready = True
        except Exception as e:
            self.log.error(f"GPIO Fan init error: {e}")
            self._is_ready = False

    def change_pin(self, pin):
        self.fan.close()
        self.pin = pin
        try:
            from pm_auto.libs.pin import Pin, PinMode
            self.fan = Pin(pin, PinMode.OUT)
            self.fan.off()

            self._is_ready = True
            return True
        except Exception as e:
            self.log.error(f"Change pin error: {e}")
            self._is_ready = False
            return False
            
    def change_led_pin(self, led_pin):
        self.led.close()
        self.led_pin = led_pin
        try:
            from pm_auto.libs.pin import Pin, PinMode
            self.led = Pin(led_pin, PinMode.OUT)
            self.led.off()
            self._is_ready = True
            return True
        except Exception as e:
            self.log.error(f"Change led pin error: {e}")
            self._is_ready = False
            return False

    @log_error
    @check_ready
    def set(self, value: bool):
        self.fan.set_value(value)
        if self.led_follow:
            self.led.set_value(value)

    @log_error
    @check_ready
    def set_led(self, value: str):
        self.log.debug(f"Set led to {value}")
        if value == 'follow':
            self.led_follow = True
        else:
            self.led_follow = False
            if value == 'on':
                self.led.on()
            elif value == 'off':
                self.led.off()
            else:
                self.log.warning(f"Invalid led value: {value}")
                return False
        return True

    @log_error
    @check_ready
    def on(self):
        self.set(True)

    @log_error
    @check_ready
    def off(self):
        self.set(False)

    @log_error
    @check_ready
    def close(self):
        self.off()
        self._is_ready = False
        self.fan.close()
        self.log.debug("GPIO Fan closed")

class SPCFan(Fan):
    I2C_ADDRESS = 0x5A
    GET_FAN_SPEED = 0x21
    SET_FAN_SPEED = 0x00

    def __init__(self, *args, **kwargs):
        from spc.spc import SPC
        super().__init__(*args, **kwargs)
        self.spc = SPC()
        if 'fan' in self.spc.device.peripherals:
            self._is_ready = self.spc.is_ready()

    @log_error
    @check_ready
    def on(self):
        self.set_power(self.power)

    @log_error
    @check_ready
    def off(self):
        self.set_power(0)

    @log_error
    @check_ready
    def set_power(self, power: int):
        '''
        power: 0 ~ 100
        '''
        if not isinstance(power, int):
            raise ValueError("Invalid power")
        
        power = max(0, min(100, power))
        self.spc.set_fan_power(power)
        return power

    @log_error
    @check_ready
    def get_power(self):
        return self.spc.get_fan_power()

    @log_error
    @check_ready
    def close(self):
        self.off()
        self._is_ready = False
        self.log.debug("SPC Fan closed")

class PWMFan(Fan):
    # Always drive pwm1 ourselves (custom temp curve). Kernel thermal
    # governor is not used as the speed source.
    TEMP_CONTROL_INTERVENE_OS = [
        'ubuntu',
    ]
    HWMON_DIR = '/sys/devices/platform/cooling_fan/hwmon'
    COOLING_STATE = '/sys/class/thermal/cooling_device0/cur_state'
    COOLING_MAX = '/sys/class/thermal/cooling_device0/max_state'

    @log_error
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_rpm = 0
        if not PWMFan.pwm_fan_supported():
            self.log.warning("PWM Fan is not supported")
            self._is_ready = False
            return
        self.enable_control = True
        self._is_ready = True

    @staticmethod
    def pwm_fan_supported():
        from os import path
        return path.exists('/sys/class/thermal/cooling_device0/cur_state') and path.exists('/sys/devices/platform/cooling_fan')

    def _hwmon_file(self, name):
        if not os.path.isdir(self.HWMON_DIR):
            return None
        for entry in os.listdir(self.HWMON_DIR):
            path = os.path.join(self.HWMON_DIR, entry, name)
            if os.path.exists(path):
                return path
        return None

    def _write_sysfs(self, path, value):
        with open(path, 'w') as f:
            f.write(str(int(value)))

    @log_error
    @check_ready
    def is_supported(self):
        # False: FanAddon applies the software temperature curve.
        return False

    @log_error
    @check_ready
    def get_state(self):
        try:
            with open(self.COOLING_STATE, 'r') as f:
                return int(f.read())
        except Exception as e:
            self.log.error(f'read pwm fan state error: {e}')
            return 0

    @log_error
    @check_ready
    def get_max_state(self):
        try:
            with open(self.COOLING_MAX, 'r') as f:
                return int(f.read())
        except Exception:
            return 4

    @log_error
    @check_ready
    def set_state(self, level: int):
        if not isinstance(level, int):
            return
        max_state = self.get_max_state()
        if max_state is None:
            max_state = 4
        level = max(0, min(level, max_state))
        try:
            self._write_sysfs(self.COOLING_STATE, level)
        except Exception as e:
            self.log.error(f'write pwm fan state error: {e}')

    @log_error
    @check_ready
    def set_percent(self, percent):
        '''Set duty cycle as percent of max PWM (0-100).'''
        percent = max(0, min(100, int(percent)))
        enable_path = self._hwmon_file('pwm1_enable')
        pwm_path = self._hwmon_file('pwm1')
        if enable_path:
            try:
                self._write_sysfs(enable_path, 1)
            except Exception as e:
                self.log.debug(f'pwm1_enable write skipped: {e}')
        if pwm_path:
            duty = int(round(percent * 255 / 100.0))
            try:
                self._write_sysfs(pwm_path, duty)
                return duty
            except Exception as e:
                self.log.error(f'write pwm1 error: {e}')
        max_state = self.get_max_state() or 4
        self.set_state(int(round(percent * max_state / 100.0)))
        return percent

    @log_error
    @check_ready
    def get_speed(self):
        path = self._hwmon_file('fan1_input')
        if not path:
            return 0
        try:
            with open(path, 'r') as f:
                return int(f.read())
        except Exception as e:
            self.log.error(f'read fan1 speed error: {e}')
            return 0

    def load_calibration(self):
        path = PWM_FAN_CALIBRATION_FILE
        if not os.path.isfile(path):
            return None
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            if isinstance(data, dict) and int(data.get('max_rpm', 0)) > 0:
                return data
        except Exception as e:
            self.log.warning(f'load fan calibration failed: {e}')
        return None

    def save_calibration(self, data):
        path = PWM_FAN_CALIBRATION_FILE
        try:
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(data, f)
            os.chmod(path, 0o644)
        except Exception as e:
            self.log.warning(f'save fan calibration failed: {e}')

    @log_error
    @check_ready
    def calibrate_max_speed(self, settle_seconds=8, force=False, on_sample=None):
        existing = self.load_calibration()
        if existing and not force:
            self.max_rpm = int(existing.get('max_rpm', 0))
            self.log.info(f"PWM fan using saved max speed: {self.max_rpm} RPM")
            return existing

        self.log.info("PWM fan calibration: 100% duty to measure max RPM")
        self.set_percent(100)
        samples = []
        total = max(3, int(settle_seconds))
        for i in range(total):
            time.sleep(1)
            rpm = self.get_speed() or 0
            samples.append(rpm)
            self.log.info(f"calibration sample {i + 1}/{total}: {rpm} RPM")
            if callable(on_sample):
                on_sample(i + 1, total, rpm)
        max_rpm = max(samples) if samples else 0
        self.max_rpm = max_rpm
        if max_rpm <= 0:
            self.log.warning("PWM fan calibration read 0 RPM; will retry on next start")
            return {'max_rpm': 0}
        data = {
            'max_rpm': max_rpm,
            'pwm_max': 255,
            'samples': samples,
        }
        self.save_calibration(data)
        self.log.info(f"PWM fan max speed calibrated: {max_rpm} RPM")
        return data

    @log_error
    @check_ready
    def off(self):
        self.set_percent(0)

    @log_error
    @check_ready
    def close(self):
        self.off()
        self._is_ready = False
        self.log.debug("PWM Fan closed")