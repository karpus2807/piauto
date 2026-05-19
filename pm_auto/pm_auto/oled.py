from .ssd1306 import SSD1306, Rect
from sf_rpi_status import \
    get_cpu_temperature, \
    get_gpu_temperature, \
    get_memory_info, \
    get_ips

from .utils import format_bytes, format_storage_pair, log_error
from .oled_icons import draw_storage_icon
from .system_stats import (
    get_mounts_usage,
    get_combined_disk,
    get_system_cpu_percent,
    get_gpu_usage_percent,
    get_top_processes_cpu,
    get_max_storage_percent,
    get_mount_disk_temperature,
    get_storage_disk_temperatures,
    is_undervoltage_now,
    collect_oled_alerts,
)
import json
import math
import time

from .oled_layout import OledLayoutRenderer

OLED_DEFAULT_CONFIG = {
    'temperature_unit': 'C',
    'oled_enable': True,
    'oled_rotation': 0,
    'oled_disk': 'total',
    'oled_network_interface': 'all',
    'oled_sleep_timeout': 0,
    'oled_home_duration': 15,
    'oled_page_duration': 5,
    'oled_pages_profile': 'full',
    'oled_alert_enable': True,
    'oled_alert_duration': 3,
    'oled_alert_cooldown': 45,
    'oled_alert_cpu_temp': 80,
    'oled_alert_cpu_percent': 90,
    'oled_alert_disk_percent': 90,
    'oled_alert_gpu_temp': 80,
    'oled_alert_undervoltage': True,
}

WARN_DURATION_DEFAULT = 3
WARN_COOLDOWN_DEFAULT = 45

# One mount / up to 4 network lines per page.
MOUNTS_PER_STORAGE_SLIDE = 1
NETWORK_LINES_PER_PAGE = 4

OLED_PAGE_IDS = (
    'home', 'storage', 'network', 'cpu', 'gpu', 'fans',
    'ram', 'temps', 'services', 'heart',
)

OLED_PAGE_PROFILES = {
    'full': OLED_PAGE_IDS,
    'minimal': ('home', 'storage', 'heart'),
    'server': ('home', 'storage', 'network', 'cpu', 'ram', 'services', 'heart'),
}


class OLED():
    @log_error
    def __init__(self, config, get_logger=None, fan_control=None):
        if get_logger is None:
            import logging
            get_logger = logging.getLogger
        self.log = get_logger(__name__)
        self._is_ready = False
        self.fan_control = fan_control

        preview = bool(config.get('oled_preview', False))
        self.oled = SSD1306(get_logger=get_logger, preview=preview)
        if not self.oled.is_ready():
            self.log.error("Failed to initialize OLED")
            return
        self._is_ready = self.oled.is_ready()

        self.temperature_unit = OLED_DEFAULT_CONFIG['temperature_unit']
        self.disk_mode = OLED_DEFAULT_CONFIG['oled_disk']
        self.ip_interface = OLED_DEFAULT_CONFIG['oled_network_interface']
        self.enable = OLED_DEFAULT_CONFIG['oled_enable']
        self.ip_index = 0
        self.ip_show_next_timestamp = 0
        self.ip_show_next_interval = 3
        self.wake_flag = True
        self.last_ips = {}
        self.home_duration = OLED_DEFAULT_CONFIG['oled_home_duration']
        self.page_duration = OLED_DEFAULT_CONFIG['oled_page_duration']
        self.pages_profile = OLED_DEFAULT_CONFIG['oled_pages_profile']
        self.enabled_pages = []
        self.alert_enable = OLED_DEFAULT_CONFIG['oled_alert_enable']
        self.alert_duration = OLED_DEFAULT_CONFIG['oled_alert_duration']
        self.alert_cooldown = OLED_DEFAULT_CONFIG['oled_alert_cooldown']
        self.alert_cpu_temp = OLED_DEFAULT_CONFIG['oled_alert_cpu_temp']
        self.alert_cpu_percent = OLED_DEFAULT_CONFIG['oled_alert_cpu_percent']
        self.alert_disk_percent = OLED_DEFAULT_CONFIG['oled_alert_disk_percent']
        self.alert_gpu_temp = OLED_DEFAULT_CONFIG['oled_alert_gpu_temp']
        self.alert_undervoltage = OLED_DEFAULT_CONFIG['oled_alert_undervoltage']
        self._alert_until = 0.0
        self._alert_last_shown = 0.0
        self._alert_messages = []

        self._designer_layout = None
        self._designer_enabled = False
        self._layout_renderer = None
        self._designer_test_until = 0.0
        self._designer_test_page = None
        self._designer_test_layout = None

        self._page_sequence = []
        self._page_index = 0
        self._page_started_at = time.time()
        self._storage_slide = 0
        self._rebuild_pages()

        self.update_config(config)

    @log_error
    def set_fan_control(self, fan_control):
        self.fan_control = fan_control

    def _custom_page_ids(self):
        if not self._designer_layout:
            return set()
        return {
            k for k in (self._designer_layout.get('pages') or {})
            if str(k).startswith('custom_')
        }

    def _resolve_enabled_pages(self):
        if self._designer_enabled and self._designer_layout:
            carousel = self._designer_layout.get('carousel') or []
            if carousel:
                return list(carousel)
        if self.pages_profile == 'custom':
            valid = set(OLED_PAGE_IDS) | self._custom_page_ids()
            pages = [p for p in self.enabled_pages if p in valid]
            unknown = [p for p in self.enabled_pages if p not in valid]
            if unknown:
                self.log.warning(f'Unknown OLED pages ignored: {unknown}')
            return pages
        profile = self.pages_profile
        if profile in OLED_PAGE_PROFILES:
            return list(OLED_PAGE_PROFILES[profile])
        if isinstance(profile, (list, tuple)):
            return list(profile)
        return list(OLED_PAGE_PROFILES['full'])

    def _page_duration(self, pid):
        if self._designer_layout:
            pdef = (self._designer_layout.get('pages') or {}).get(pid)
            if isinstance(pdef, dict) and pdef.get('duration'):
                try:
                    d = int(pdef['duration'])
                    return max(3, d) if pid == 'home' else max(2, d)
                except (TypeError, ValueError):
                    pass
        return self.home_duration if pid == 'home' else self.page_duration

    def _rebuild_pages(self):
        enabled = self._resolve_enabled_pages()
        mounts = get_mounts_usage()
        ips = get_ips()

        pages = []
        for pid in enabled:
            if pid.startswith('custom_'):
                pages.append({'id': pid, 'duration': self._page_duration(pid)})
            elif pid == 'home':
                pages.append({'id': 'home', 'duration': self._page_duration('home')})
            elif pid == 'storage':
                n_storage = max(1, math.ceil(len(mounts) / MOUNTS_PER_STORAGE_SLIDE)) if mounts else 1
                for slide in range(n_storage):
                    pages.append({
                        'id': 'storage',
                        'slide': slide,
                        'duration': self._page_duration('storage'),
                    })
            elif pid == 'network':
                n_net = max(1, math.ceil(len(ips) / NETWORK_LINES_PER_PAGE)) if ips else 1
                for slide in range(n_net):
                    pages.append({
                        'id': 'network',
                        'slide': slide,
                        'duration': self._page_duration('network'),
                    })
            else:
                pages.append({'id': pid, 'duration': self._page_duration(pid)})

        if not pages:
            pages = [{'id': 'home', 'duration': self.home_duration}]
        self._page_sequence = pages
        if self._page_index >= len(self._page_sequence):
            self._page_index = 0

    @log_error
    def _advance_page_if_needed(self):
        if not self._page_sequence:
            self._rebuild_pages()
        page = self._page_sequence[self._page_index]
        if time.time() - self._page_started_at >= page['duration']:
            self._page_index = (self._page_index + 1) % len(self._page_sequence)
            self._page_started_at = time.time()
            if self._page_sequence[self._page_index]['id'] == 'storage':
                self._storage_slide = self._page_sequence[self._page_index].get('slide', 0)
            if self._page_index == 0:
                self._rebuild_pages()

    def _current_page(self):
        if not self._page_sequence:
            self._rebuild_pages()
        return self._page_sequence[self._page_index]

    @log_error
    def set_debug_level(self, level):
        self.log.setLevel(level)

    @log_error
    def update_config(self, config):
        if "temperature_unit" in config:
            if config['temperature_unit'] not in ['C', 'F']:
                self.log.error("Invalid temperature unit")
                return
            self.temperature_unit = config['temperature_unit']
        if "oled_rotation" in config:
            self.set_rotation(config['oled_rotation'])
        if "oled_disk" in config:
            self.disk_mode = config['oled_disk']
        if "oled_network_interface" in config:
            self.ip_interface = config['oled_network_interface']
        if "oled_enable" in config:
            self.enable = config['oled_enable']
            if self.enable:
                self.wake()
            else:
                self.sleep()
        if 'oled_home_duration' in config:
            try:
                self.home_duration = max(3, int(config['oled_home_duration']))
            except (TypeError, ValueError):
                self.log.error('Invalid oled_home_duration')
        if 'oled_page_duration' in config:
            try:
                self.page_duration = max(2, int(config['oled_page_duration']))
            except (TypeError, ValueError):
                self.log.error('Invalid oled_page_duration')
        if 'oled_pages_profile' in config:
            self.pages_profile = config['oled_pages_profile']
        if 'oled_pages' in config:
            pages = config['oled_pages']
            if isinstance(pages, str):
                self.enabled_pages = [p.strip() for p in pages.split(',') if p.strip()]
            elif isinstance(pages, (list, tuple)):
                self.enabled_pages = list(pages)
            self.pages_profile = 'custom'
        if 'oled_alert_enable' in config:
            self.alert_enable = bool(config['oled_alert_enable'])
        if 'oled_alert_undervoltage' in config:
            self.alert_undervoltage = bool(config['oled_alert_undervoltage'])
        for key, attr in (
            ('oled_alert_duration', 'alert_duration'),
            ('oled_alert_cooldown', 'alert_cooldown'),
            ('oled_alert_cpu_temp', 'alert_cpu_temp'),
            ('oled_alert_cpu_percent', 'alert_cpu_percent'),
            ('oled_alert_disk_percent', 'alert_disk_percent'),
            ('oled_alert_gpu_temp', 'alert_gpu_temp'),
        ):
            if key in config:
                try:
                    if 'duration' in key or 'cooldown' in key:
                        setattr(self, attr, int(config[key]))
                    else:
                        setattr(self, attr, float(config[key]))
                except (TypeError, ValueError):
                    self.log.error(f'Invalid {key}')
        if 'oled_designer_layout' in config:
            self._load_designer_layout(config.get('oled_designer_layout'))
        if 'oled_designer_enabled' in config:
            self._designer_enabled = bool(config['oled_designer_enabled'])
        if 'oled_designer_test' in config:
            self._apply_designer_test(config.get('oled_designer_test'))
        self._rebuild_pages()

    def _clear_designer_test(self):
        self._designer_test_until = 0.0
        self._designer_test_page = None
        self._designer_test_layout = None
        self._layout_renderer = None

    def _apply_designer_test(self, payload):
        if not payload:
            self._clear_designer_test()
            return
        if not isinstance(payload, dict):
            return
        until = float(payload.get('until', 0))
        if until <= time.time():
            self._clear_designer_test()
            return
        self._designer_test_until = until
        self._designer_test_page = str(payload.get('page', 'home'))[:32]
        layout = payload.get('layout')
        if isinstance(layout, str):
            try:
                layout = json.loads(layout)
            except (json.JSONDecodeError, TypeError):
                layout = None
        self._designer_test_layout = layout if isinstance(layout, dict) else None
        self._layout_renderer = None
        self.wake_flag = True
        if self.oled is not None and self.oled.is_ready() and self.enable:
            self._draw_designer_test_page()

    def _designer_test_active(self):
        if self._designer_test_until <= 0:
            return False
        if time.time() >= self._designer_test_until:
            self._clear_designer_test()
            return False
        return True

    def _draw_designer_test_page(self):
        pid = self._designer_test_page or 'home'
        self.oled.clear()
        pdef = None
        if self._designer_test_layout:
            pdef = (self._designer_test_layout.get('pages') or {}).get(pid)
        if not pdef:
            pdef = self._layout_page_def(pid)
        rendered = False
        if pdef and pdef.get('elements'):
            self._layout_renderer = OledLayoutRenderer(self)
            rendered = self._layout_renderer.render(pdef, slide=0)
        if not rendered:
            self.draw_legacy_page(pid, 0)
        self.oled.display()

    def _load_designer_layout(self, raw):
        if not raw:
            self._designer_layout = None
            return
        try:
            if isinstance(raw, str):
                self._designer_layout = json.loads(raw)
            elif isinstance(raw, dict):
                self._designer_layout = raw
            else:
                self._designer_layout = None
        except (json.JSONDecodeError, TypeError) as e:
            self.log.error(f'Invalid oled_designer_layout: {e}')
            self._designer_layout = None

    def _layout_page_def(self, pid):
        if not self._designer_layout:
            return None
        return (self._designer_layout.get('pages') or {}).get(pid)

    def _should_render_layout(self, pid):
        if not self._designer_enabled:
            return False
        pdef = self._layout_page_def(pid)
        return bool(pdef and pdef.get('elements'))

    @log_error
    def collect_layout_metrics(self, slide=0, page_id=''):
        """Metrics for designer layouts (web preview + hardware render)."""
        cpu_temp_c = get_cpu_temperature() or 0
        cpu_temp_f = cpu_temp_c * 9 / 5 + 32
        cpu_pct = get_system_cpu_percent()
        temp = cpu_temp_c if self.temperature_unit == 'C' else cpu_temp_f
        unit = self.temperature_unit

        memory_info = get_memory_info()
        memory_total, memory_unit = format_bytes(memory_info.total, auto_threshold=1024)
        memory_used = format_bytes(memory_info.used, memory_unit)
        mounts = get_mounts_usage()
        combined = get_combined_disk(mounts)
        if combined['mounted']:
            storage_line = f'STORE {format_storage_pair(combined["used"], combined["total"])[0]}'
            storage_pct = format_storage_pair(combined['used'], combined['total'])[1]
        else:
            storage_line = 'STORE NA'
            storage_pct = 0

        gpu_temp = get_gpu_temperature()
        gpu_pct = get_gpu_usage_percent()

        m = {
            'cpu_temperature': temp,
            'cpu_temp_label': f'{temp:.1f}{unit}',
            'cpu_percent': cpu_pct,
            'cpu_temp_gauge': min(cpu_temp_c, 100),
            'memory_percent': memory_info.percent,
            'ram_line': f'RAM {memory_used}/{memory_total}{memory_unit}',
            'storage_percent': storage_pct,
            'storage_percent_free': max(0, 100 - storage_pct),
            'storage_line': storage_line,
            'ip_line': self._get_ip_display(),
            'gpu_percent': gpu_pct if gpu_pct is not None else 0,
            'gpu_temperature': gpu_temp,
            'gpu_use_line': f'USE {gpu_pct:.0f}%' if gpu_pct is not None else 'USE N/A',
            'gpu_temp_line': (
                f'TEMP {gpu_temp:.1f}{unit}' if gpu_temp is not None else 'TEMP N/A'
            ),
            'cpu_use_line': f'USE {cpu_pct:.0f}%',
            'cpu_temp_line': f'TEMP {temp:.1f}{unit}',
        }

        if gpu_temp is not None:
            gt = gpu_temp if self.temperature_unit == 'C' else gpu_temp * 9 / 5 + 32
            m['gpu_temp_line'] = f'TEMP {gt:.1f}{unit}'

        # Storage slide
        total_storage = max(1, math.ceil(len(mounts) / MOUNTS_PER_STORAGE_SLIDE)) if mounts else 1
        slide = min(slide, total_storage - 1)
        start = slide * MOUNTS_PER_STORAGE_SLIDE
        chunk = mounts[start: start + MOUNTS_PER_STORAGE_SLIDE]
        if chunk:
            mount = chunk[0]
            pair, pct = format_storage_pair(mount['used'], mount['total'])
            kind = mount.get('kind', 'DISK')
            m['storage_detail'] = f'{kind}: {pair}'
            m['storage_percent'] = pct
            dt = get_mount_disk_temperature(mount.get('device'))
            if dt is not None:
                if unit == 'F':
                    dt = dt * 9 / 5 + 32
                m['storage_temp'] = f'TEMP {dt:.0f}{unit}'
            else:
                m['storage_temp'] = ''
        else:
            m['storage_detail'] = 'No storage'
            m['storage_temp'] = ''

        # Network slide
        ips = sorted(get_ips().items())
        total_net = max(1, math.ceil(len(ips) / NETWORK_LINES_PER_PAGE)) if ips else 1
        nslide = min(slide, total_net - 1)
        nstart = nslide * NETWORK_LINES_PER_PAGE
        nchunk = ips[nstart: nstart + NETWORK_LINES_PER_PAGE]
        for i in range(4):
            if i < len(nchunk):
                iface, ip = nchunk[i]
                m[f'net_line_{i + 1}'] = self._truncate(f'{iface} {ip}', 20)
            else:
                m[f'net_line_{i + 1}'] = ''

        # Fans
        if self.fan_control is not None:
            snap = self.fan_control.get_oled_snapshot()
            if snap.get('tower_rpm') is not None:
                m['tower_rpm_line'] = f'TOWER {snap["tower_rpm"]} RPM'
            else:
                m['tower_rpm_line'] = ''
            if snap.get('side_on') is not None:
                m['side_fan_line'] = f'SIDE  {"ON" if snap["side_on"] else "OFF"}'
            else:
                m['side_fan_line'] = ''
            m['fan_mode_line'] = f'MODE  {self._truncate(snap.get("mode", "?"), 12)}'
            m['pwm_fan_speed'] = snap.get('tower_rpm')
            m['gpio_fan_state'] = snap.get('side_on')
        else:
            m['tower_rpm_line'] = ''
            m['side_fan_line'] = ''
            m['fan_mode_line'] = ''

        # Temps page disk lines
        disk_temps = get_storage_disk_temperatures()[:2]
        for i in range(2):
            if i < len(disk_temps):
                label, dt = disk_temps[i]
                t = dt if unit == 'C' else dt * 9 / 5 + 32
                m[f'disk_temp_line_{i + 1}'] = f'{label} {t:.0f}{unit}'
            else:
                m[f'disk_temp_line_{i + 1}'] = ''

        m['cpu_temp_line'] = f'CPU {temp:.1f}{unit}'

        rows = get_top_processes_cpu(3)
        for i in range(3):
            if i < len(rows):
                row = rows[i]
                m[f'top_cpu_{i + 1}'] = f'{self._truncate(row["name"], 9)} {row["cpu_percent"]:.0f}%'
            else:
                m[f'top_cpu_{i + 1}'] = ''

        return m

    @log_error
    def _collect_alerts(self):
        cpu_temp = get_cpu_temperature()
        cpu_pct = get_system_cpu_percent()
        gpu_temp = get_gpu_temperature()
        disk_pct = get_max_storage_percent()
        return collect_oled_alerts(
            cpu_temp_c=cpu_temp,
            cpu_percent=cpu_pct,
            gpu_temp_c=gpu_temp,
            disk_percent=disk_pct,
            undervoltage=self.alert_undervoltage and is_undervoltage_now(),
            alert_cpu_temp=self.alert_cpu_temp,
            alert_cpu_percent=self.alert_cpu_percent,
            alert_disk_percent=self.alert_disk_percent,
            alert_gpu_temp=self.alert_gpu_temp,
            temperature_unit=self.temperature_unit,
        )

    @log_error
    def _handle_alerts(self):
        if not self.alert_enable:
            return False
        now = time.time()
        if now < self._alert_until:
            self.draw_warn(self._alert_messages)
            return True
        messages = self._collect_alerts()
        if not messages:
            return False
        if now - self._alert_last_shown < self.alert_cooldown:
            return False
        self._alert_messages = messages
        self._alert_until = now + self.alert_duration
        self._alert_last_shown = now
        self.log.warning(f'OLED alert: {", ".join(messages)}')
        self.draw_warn(messages)
        return True

    @log_error
    def draw_warn(self, messages):
        self.oled.clear()
        flash_on = int(time.time() * 2) % 2 == 1
        if flash_on:
            self.oled.draw.rectangle((0, 0, 127, 63), fill=1)
            ink = 0
        else:
            ink = 1
        self.oled.draw_text('! WARNING !', 64, 6, align='center', fill=ink, size='md')
        y = 20
        for msg in messages[:4]:
            self.oled.draw_text(msg, 64, y, align='center', fill=ink, size='sm')
            y += 11
        self.oled.display()

    @log_error
    def go_home(self):
        """Jump to home page and reset its display timer (e.g. on vibration tap)."""
        if not self._is_ready:
            return
        self._rebuild_pages()
        self._page_index = 0
        for i, page in enumerate(self._page_sequence):
            if page['id'] == 'home':
                self._page_index = i
                break
        self._page_started_at = time.time()
        self.wake_flag = True
        self.draw_current_page()

    @log_error
    def set_rotation(self, rotation):
        self.oled.set_rotation(rotation)

    @log_error
    def is_ready(self):
        return self._is_ready

    def _truncate(self, text, max_len):
        text = str(text)
        return text if len(text) <= max_len else text[: max_len - 1] + '~'

    def _get_ip_entries(self):
        ips = get_ips()
        for interface, ip in ips.items():
            if interface not in self.last_ips:
                self.log.info(f"Connected to {interface}: {ip}")
            elif self.last_ips[interface] != ip:
                self.log.info(f"IP changed for {interface}: {ip}")
            self.last_ips[interface] = ip
        for interface in list(self.last_ips.keys()):
            if interface not in ips:
                self.log.info(f"Disconnected from {interface}")
                del self.last_ips[interface]

        if not ips:
            return []
        if self.ip_interface == 'all':
            return sorted(ips.items())
        if self.ip_interface in ips:
            return [(self.ip_interface, ips[self.ip_interface])]
        return []

    @log_error
    def _get_ip_display(self):
        entries = self._get_ip_entries()
        if not entries:
            return 'DISCONNECTED'
        iface, ip = entries[self.ip_index % len(entries)]
        if time.time() - self.ip_show_next_timestamp > self.ip_show_next_interval:
            self.ip_show_next_timestamp = time.time()
            self.ip_index = (self.ip_index + 1) % len(entries)
        return self._truncate(f'{iface} {ip}', 16)

    @log_error
    def _draw_header(self, title, sub=''):
        self.oled.draw_text(title, 2, 0, fill=1, size='sm')
        if sub:
            self.oled.draw_text(sub, 127, 0, fill=1, align='right', size='sm')

    @log_error
    def draw_home(self):
        memory_info = get_memory_info()
        mounts = get_mounts_usage()
        combined = get_combined_disk(mounts)

        cpu_temp_c = get_cpu_temperature() or 0
        cpu_temp_f = cpu_temp_c * 9 / 5 + 32
        cpu_usage = get_system_cpu_percent()

        memory_total, memory_unit = format_bytes(memory_info.total, auto_threshold=1024)
        memory_used = format_bytes(memory_info.used, memory_unit)
        memory_percent = memory_info.percent

        if combined['mounted']:
            disk_label, disk_percent = format_storage_pair(combined['used'], combined['total'])
        else:
            disk_label, disk_percent = 'NA', 0

        ip = self._get_ip_display()

        ip_rect = Rect(39, 0, 88, 10)
        memory_info_rect = Rect(39, 17, 88, 10)
        memory_rect = Rect(39, 29, 88, 10)
        disk_info_rect = Rect(39, 41, 88, 10)
        disk_rect = Rect(39, 53, 88, 10)
        LEFT_AREA_X = 18

        self.oled.draw_text('CPU', LEFT_AREA_X, 0, align='center')
        self.oled.draw_pieslice_chart(cpu_usage, LEFT_AREA_X, 27, 15, 180, 0)
        self.oled.draw_text(f'{cpu_usage:.0f}%', LEFT_AREA_X, 27, align='center')
        temp = cpu_temp_c if self.temperature_unit == 'C' else cpu_temp_f
        self.oled.draw_text(f'{temp:.1f}{self.temperature_unit}', LEFT_AREA_X, 37, align='center')
        self.oled.draw_pieslice_chart(min(cpu_temp_c, 100), LEFT_AREA_X, 48, 15, 0, 180)

        self.oled.draw_text(
            f'RAM {memory_used}/{memory_total}{memory_unit}',
            *memory_info_rect.coord(),
            size='sm',
        )
        self.oled.draw_bar_graph_horizontal(memory_percent, *memory_rect.coord(), *memory_rect.size())

        self.oled.draw_text(f'STORE {disk_label}', *disk_info_rect.coord(), size='sm')
        self.oled.draw_bar_graph_horizontal(disk_percent, *disk_rect.coord(), *disk_rect.size())

        self.oled.draw.rectangle(
            (ip_rect.x, ip_rect.y, ip_rect.x + ip_rect.width, ip_rect.y + ip_rect.height),
            outline=1,
            fill=1,
        )
        self.oled.draw_text(ip, *ip_rect.topcenter(), fill=0, align='center')

    @log_error
    def draw_storage(self, slide=0):
        mounts = get_mounts_usage()
        total_slides = max(1, math.ceil(len(mounts) / MOUNTS_PER_STORAGE_SLIDE))
        slide = min(slide, total_slides - 1)
        start = slide * MOUNTS_PER_STORAGE_SLIDE
        chunk = mounts[start : start + MOUNTS_PER_STORAGE_SLIDE]

        self._draw_header('STORAGE', f'{slide + 1}/{total_slides}')
        if not chunk:
            self.oled.draw_text('No storage', 39, 28, size='sm')
            return

        m = chunk[0]
        kind = m.get('kind', 'DISK')
        pair, pct = format_storage_pair(m['used'], m['total'])

        # Same layout language as home: icon + gauge left, text + bar right
        draw_storage_icon(self.oled, kind, 2, 20)
        self.oled.draw_pieslice_chart(pct, 18, 38, 13, 180, 0)
        self.oled.draw_text(f'{pct:.0f}%', 18, 38, align='center', size='sm')

        info_rect = Rect(39, 17, 88, 10)
        bar_rect = Rect(39, 29, 88, 10)
        self.oled.draw_text(f'{kind}: {pair}', *info_rect.coord(), size='sm')
        self.oled.draw_bar_graph_horizontal(pct, *bar_rect.coord(), *bar_rect.size())

        disk_temp = get_mount_disk_temperature(m.get('device'))
        if disk_temp is not None:
            unit = self.temperature_unit
            if unit == 'F':
                disk_temp = disk_temp * 9 / 5 + 32
            self.oled.draw_text(
                f'TEMP {disk_temp:.0f}{unit}',
                39, 43, size='sm',
            )

    @log_error
    def draw_cpu(self):
        cpu_usage = get_system_cpu_percent()
        cpu_temp_c = get_cpu_temperature() or 0
        cpu_temp_f = cpu_temp_c * 9 / 5 + 32
        temp = cpu_temp_c if self.temperature_unit == 'C' else cpu_temp_f
        LEFT = 18

        self._draw_header('CPU')
        self.oled.draw_text('CPU', LEFT, 10, align='center', size='sm')
        self.oled.draw_pieslice_chart(cpu_usage, LEFT, 30, 15, 180, 0)
        self.oled.draw_text(f'{cpu_usage:.0f}%', LEFT, 30, align='center', size='sm')
        self.oled.draw_text(f'{temp:.1f}{self.temperature_unit}', LEFT, 40, align='center', size='sm')
        self.oled.draw_pieslice_chart(min(cpu_temp_c, 100), LEFT, 50, 13, 0, 180)

        self.oled.draw_text(f'USE {cpu_usage:.0f}%', 39, 17, size='sm')
        self.oled.draw_bar_graph_horizontal(cpu_usage, 39, 29, 88, 10)
        self.oled.draw_text(f'TEMP {temp:.1f}{self.temperature_unit}', 39, 43, size='sm')

    @log_error
    def draw_gpu(self):
        gpu_temp = get_gpu_temperature()
        gpu_pct = get_gpu_usage_percent()
        pct = gpu_pct if gpu_pct is not None else 0

        self._draw_header('GPU')
        self.oled.draw_pieslice_chart(pct, 18, 38, 13, 180, 0)
        if gpu_pct is not None:
            self.oled.draw_text(f'{gpu_pct:.0f}%', 18, 38, align='center', size='sm')
            self.oled.draw_text(f'USE {gpu_pct:.0f}%', 39, 17, size='sm')
            self.oled.draw_bar_graph_horizontal(gpu_pct, 39, 29, 88, 10)
        else:
            self.oled.draw_text('N/A', 18, 38, align='center', size='sm')
            self.oled.draw_text('USE N/A', 39, 17, size='sm')

        if gpu_temp is not None:
            t = gpu_temp if self.temperature_unit == 'C' else gpu_temp * 9 / 5 + 32
            self.oled.draw_text(f'TEMP {t:.1f}{self.temperature_unit}', 39, 43, size='sm')
        else:
            self.oled.draw_text('TEMP N/A', 39, 43, size='sm')

    @log_error
    def draw_fans(self):
        self._draw_header('FANS')
        y = 17
        if self.fan_control is None:
            self.oled.draw_text('No fan data', 39, y, size='sm')
            return
        snap = self.fan_control.get_oled_snapshot()
        if snap.get('tower_rpm') is not None:
            self.oled.draw_text(f'TOWER {snap["tower_rpm"]} RPM', 4, y, size='sm')
            y += 12
        if snap.get('side_on') is not None:
            state = 'ON' if snap['side_on'] else 'OFF'
            self.oled.draw_text(f'SIDE  {state}', 4, y, size='sm')
            y += 12
        mode = self._truncate(snap.get('mode', '?'), 12)
        self.oled.draw_text(f'MODE  {mode}', 4, y, size='sm')

    @log_error
    def draw_ram(self):
        memory_info = get_memory_info()
        memory_total, memory_unit = format_bytes(memory_info.total, auto_threshold=1024)
        memory_used = format_bytes(memory_info.used, memory_unit)
        pct = memory_info.percent

        self._draw_header('RAM')
        self.oled.draw_pieslice_chart(pct, 18, 38, 13, 180, 0)
        self.oled.draw_text(f'{pct:.0f}%', 18, 38, align='center', size='sm')

        info_rect = Rect(39, 17, 88, 10)
        bar_rect = Rect(39, 29, 88, 10)
        self.oled.draw_text(
            f'RAM {memory_used}/{memory_total}{memory_unit}',
            *info_rect.coord(),
            size='sm',
        )
        self.oled.draw_bar_graph_horizontal(pct, *bar_rect.coord(), *bar_rect.size())

    @log_error
    def draw_temps(self):
        cpu_temp_c = get_cpu_temperature()
        gpu_temp = get_gpu_temperature()

        self._draw_header('TEMPS')
        y = 17
        if cpu_temp_c is not None:
            t = cpu_temp_c if self.temperature_unit == 'C' else cpu_temp_c * 9 / 5 + 32
            self.oled.draw_text(f'CPU {t:.1f}{self.temperature_unit}', 39, y, size='sm')
            y += 12
        if gpu_temp is not None:
            t = gpu_temp if self.temperature_unit == 'C' else gpu_temp * 9 / 5 + 32
            self.oled.draw_text(f'GPU {t:.1f}{self.temperature_unit}', 39, y, size='sm')
            y += 12
        for label, disk_temp in get_storage_disk_temperatures()[:2]:
            if y > 52:
                break
            t = disk_temp if self.temperature_unit == 'C' else disk_temp * 9 / 5 + 32
            self.oled.draw_text(
                f'{label} {t:.0f}{self.temperature_unit}',
                39, y, size='sm',
            )
            y += 12

    @log_error
    def draw_network(self, slide=0):
        ips = get_ips()
        items = sorted(ips.items())
        total_slides = max(1, math.ceil(len(items) / NETWORK_LINES_PER_PAGE)) if items else 1
        slide = min(slide, total_slides - 1)
        start = slide * NETWORK_LINES_PER_PAGE
        chunk = items[start : start + NETWORK_LINES_PER_PAGE]

        self._draw_header('NETWORK', f'{slide + 1}/{total_slides}')
        if not chunk:
            self.oled.draw_text('No link', 39, 28, size='sm')
            return

        y = 17
        for iface, ip in chunk:
            line = f'{self._truncate(iface, 5)} {ip}'
            self.oled.draw_text(self._truncate(line, 20), 4, y, size='sm')
            y += 12

    @log_error
    def draw_services(self):
        self._draw_header('TOP CPU')
        rows = get_top_processes_cpu(3)
        if not rows:
            self.oled.draw_text('(idle)', 39, 28, size='sm')
            return
        y = 17
        for row in rows:
            name = self._truncate(row['name'], 9)
            self.oled.draw_text(f'{name} {row["cpu_percent"]:.0f}%', 39, y, size='sm')
            y += 12

    @log_error
    def draw_heart(self):
        self.oled.draw_heart_fullscreen(fill=1, margin=7)

    @log_error
    def draw_legacy_page(self, page_id, slide=0):
        """Draw a single built-in page (preview / designer PNG export)."""
        if page_id == 'home':
            self.draw_home()
        elif page_id == 'storage':
            self.draw_storage(slide)
        elif page_id == 'network':
            self.draw_network(slide)
        elif page_id == 'cpu':
            self.draw_cpu()
        elif page_id == 'gpu':
            self.draw_gpu()
        elif page_id == 'fans':
            self.draw_fans()
        elif page_id == 'ram':
            self.draw_ram()
        elif page_id == 'temps':
            self.draw_temps()
        elif page_id == 'services':
            self.draw_services()
        elif page_id == 'heart':
            self.draw_heart()
        else:
            self.oled.draw_text(str(page_id)[:12], 2, 28, size='sm')

    @log_error
    def draw_current_page(self):
        page = self._current_page()
        pid = page['id']
        slide = page.get('slide', 0)
        self.oled.clear()

        if self._should_render_layout(pid):
            pdef = self._layout_page_def(pid)
            if pdef:
                if self._layout_renderer is None:
                    self._layout_renderer = OledLayoutRenderer(self)
                if self._layout_renderer.render(pdef, slide=slide):
                    self.oled.display()
                    return

        if pid == 'home':
            self.draw_home()
        elif pid == 'storage':
            self.draw_storage(page.get('slide', 0))
        elif pid == 'network':
            self.draw_network(page.get('slide', 0))
        elif pid == 'cpu':
            self.draw_cpu()
        elif pid == 'gpu':
            self.draw_gpu()
        elif pid == 'fans':
            self.draw_fans()
        elif pid == 'ram':
            self.draw_ram()
        elif pid == 'temps':
            self.draw_temps()
        elif pid == 'services':
            self.draw_services()
        elif pid == 'heart':
            self.draw_heart()

        self.oled.display()

    @log_error
    def wake(self):
        if self.oled is None or not self.oled.is_ready() or not self.enable:
            return
        self.wake_flag = True
        self.draw_current_page()

    @log_error
    def sleep(self):
        self.wake_flag = False
        self.oled.clear()
        self.oled.display()

    @log_error
    def run(self):
        if self.oled is None or not self.oled.is_ready() or not self.wake_flag or not self.enable:
            return
        if self._designer_test_active():
            self._draw_designer_test_page()
            return
        if self._handle_alerts():
            return
        self._advance_page_if_needed()
        self.draw_current_page()

    @log_error
    def close(self):
        if self.oled is not None and self.oled.is_ready():
            self.oled.clear()
            self.oled.display()
            self.oled.off()
            self.log.debug("OLED closed")
