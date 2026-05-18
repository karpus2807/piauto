from .ssd1306 import SSD1306, Rect
from sf_rpi_status import \
    get_cpu_temperature, \
    get_cpu_percent, \
    get_gpu_temperature, \
    get_memory_info, \
    get_ips

from .utils import format_bytes, format_storage_pair, log_error
from .oled_icons import draw_storage_icon
from .system_stats import (
    get_mounts_usage,
    get_combined_disk,
    get_gpu_usage_percent,
    get_top_processes_cpu,
)
import math
import time

OLED_DEFAULT_CONFIG = {
    'temperature_unit': 'C',
    'oled_enable': True,
    'oled_rotation': 0,
    'oled_disk': 'total',
    'oled_network_interface': 'all',
    'oled_sleep_timeout': 0,
}

HOME_DURATION = 15
PAGE_DURATION = 5
# One mount per storage page — page count grows with drives (SD / SSD / USB).
MOUNTS_PER_STORAGE_SLIDE = 1


class OLED():
    @log_error
    def __init__(self, config, get_logger=None, fan_control=None):
        if get_logger is None:
            import logging
            get_logger = logging.getLogger
        self.log = get_logger(__name__)
        self._is_ready = False
        self.fan_control = fan_control

        self.oled = SSD1306(get_logger=get_logger)
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

        self._page_sequence = []
        self._page_index = 0
        self._page_started_at = time.time()
        self._storage_slide = 0
        self._rebuild_pages()

        self.update_config(config)

    @log_error
    def set_fan_control(self, fan_control):
        self.fan_control = fan_control

    def _rebuild_pages(self):
        mounts = get_mounts_usage()
        if mounts:
            n_storage = math.ceil(len(mounts) / MOUNTS_PER_STORAGE_SLIDE)
        else:
            n_storage = 1
        pages = [{'id': 'home', 'duration': HOME_DURATION}]
        for slide in range(n_storage):
            pages.append({'id': 'storage', 'slide': slide, 'duration': PAGE_DURATION})
        for pid in ('cpu', 'gpu', 'fans', 'ram', 'temps', 'services', 'heart'):
            pages.append({'id': pid, 'duration': PAGE_DURATION})
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

    @log_error
    def set_rotation(self, rotation):
        self.oled.set_rotation(rotation)

    @log_error
    def is_ready(self):
        return self._is_ready

    def _truncate(self, text, max_len):
        text = str(text)
        return text if len(text) <= max_len else text[: max_len - 1] + '~'

    @log_error
    def _get_ip_display(self):
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

        ip_list = []
        if len(ips) > 0:
            if self.ip_interface == 'all':
                ip_list = list(ips.values())
            elif self.ip_interface in ips:
                ip_list = [ips[self.ip_interface]]
                self.ip_index = 0
        if not ip_list:
            return 'DISCONNECTED'
        ip = ip_list[self.ip_index % len(ip_list)]
        if time.time() - self.ip_show_next_timestamp > self.ip_show_next_interval:
            self.ip_show_next_timestamp = time.time()
            self.ip_index = (self.ip_index + 1) % len(ip_list)
        return ip

    @log_error
    def _draw_header(self, title, sub=''):
        self.oled.draw_text(title, 2, 0, fill=1, size='md')
        if sub:
            self.oled.draw_text(sub, 127, 0, fill=1, align='right', size='md')

    @log_error
    def draw_home(self):
        memory_info = get_memory_info()
        mounts = get_mounts_usage()
        combined = get_combined_disk(mounts)

        cpu_temp_c = get_cpu_temperature() or 0
        cpu_temp_f = cpu_temp_c * 9 / 5 + 32
        cpu_usage = get_cpu_percent() or 0

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

        self.oled.draw_text(f'DISK {disk_label}', *disk_info_rect.coord(), size='sm')
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
            self.oled.draw_text('No storage', 8, 28, size='lg')
            return

        m = chunk[0]
        kind = m.get('kind', 'DISK')
        pair, pct = format_storage_pair(m['used'], m['total'])

        draw_storage_icon(self.oled, kind, 6, 16)
        self.oled.draw_text(kind, 50, 16, size='xl')
        self.oled.draw_text(pair, 50, 32, size='lg')
        self.oled.draw_text(f'{pct:.0f}%', 50, 46, size='md')
        self.oled.draw_bar_graph_horizontal(pct, 6, 54, 116, 8)

    @log_error
    def draw_cpu(self):
        cpu_usage = get_cpu_percent() or 0
        cpu_temp_c = get_cpu_temperature() or 0
        cpu_temp_f = cpu_temp_c * 9 / 5 + 32
        temp = cpu_temp_c if self.temperature_unit == 'C' else cpu_temp_f

        self._draw_header('CPU')
        self.oled.draw_text(f'{cpu_usage:.0f}%', 64, 14, size='xl', align='center')
        self.oled.draw_text('CPU USE', 64, 28, size='sm', align='center')
        self.oled.draw_bar_graph_horizontal(cpu_usage, 6, 36, 116, 10)
        self.oled.draw_text(f'{temp:.1f}{self.temperature_unit}', 64, 52, size='lg', align='center')

    @log_error
    def draw_gpu(self):
        gpu_temp = get_gpu_temperature()
        gpu_pct = get_gpu_usage_percent()

        self._draw_header('GPU')
        if gpu_pct is not None:
            self.oled.draw_text(f'{gpu_pct:.0f}%', 64, 14, size='xl', align='center')
        else:
            self.oled.draw_text('N/A', 64, 14, size='xl', align='center')
        self.oled.draw_text('GPU USE', 64, 28, size='sm', align='center')
        if gpu_pct is not None:
            self.oled.draw_bar_graph_horizontal(gpu_pct, 6, 36, 116, 10)
        if gpu_temp is not None:
            t = gpu_temp if self.temperature_unit == 'C' else gpu_temp * 9 / 5 + 32
            self.oled.draw_text(f'{t:.1f}{self.temperature_unit}', 64, 52, size='lg', align='center')
        else:
            self.oled.draw_text('TEMP N/A', 64, 52, size='md', align='center')

    @log_error
    def draw_fans(self):
        self._draw_header('FANS')
        y = 18
        if self.fan_control is None:
            self.oled.draw_text('No fan data', 8, y, size='lg')
            return
        snap = self.fan_control.get_oled_snapshot()
        if snap.get('pwm_rpm') is not None:
            self.oled.draw_text(f'{snap["pwm_rpm"]}', 64, y, size='xl', align='center')
            self.oled.draw_text('RPM', 64, y + 16, size='md', align='center')
            y += 34
        if snap.get('gpio_on') is not None:
            state = 'ON' if snap['gpio_on'] else 'OFF'
            self.oled.draw_text(f'GPIO {state}', 8, y, size='lg')
            y += 16
        self.oled.draw_text(self._truncate(snap.get('mode', '?'), 14), 8, y, size='md')

    @log_error
    def draw_ram(self):
        memory_info = get_memory_info()
        memory_total, memory_unit = format_bytes(memory_info.total, auto_threshold=1024)
        memory_used = format_bytes(memory_info.used, memory_unit)

        self._draw_header('RAM')
        self.oled.draw_text(
            f'{memory_used}/{memory_total} {memory_unit}',
            64, 18, size='lg', align='center',
        )
        self.oled.draw_text(f'{memory_info.percent:.0f}%', 64, 34, size='xl', align='center')
        self.oled.draw_bar_graph_horizontal(memory_info.percent, 6, 48, 116, 12)

    @log_error
    def draw_temps(self):
        cpu_temp_c = get_cpu_temperature()
        gpu_temp = get_gpu_temperature()

        self._draw_header('TEMPS')
        if cpu_temp_c is not None:
            t = cpu_temp_c if self.temperature_unit == 'C' else cpu_temp_c * 9 / 5 + 32
            self.oled.draw_text(f'CPU {t:.1f}{self.temperature_unit}', 8, 20, size='xl')
        if gpu_temp is not None:
            t = gpu_temp if self.temperature_unit == 'C' else gpu_temp * 9 / 5 + 32
            self.oled.draw_text(f'GPU {t:.1f}{self.temperature_unit}', 8, 42, size='xl')

    @log_error
    def draw_services(self):
        self._draw_header('TOP CPU')
        rows = get_top_processes_cpu(3)
        if not rows:
            self.oled.draw_text('idle', 64, 28, size='xl', align='center')
            return
        y = 14
        for row in rows:
            name = self._truncate(row['name'], 10)
            self.oled.draw_text(f'{name} {row["cpu_percent"]:.0f}%', 6, y, size='lg')
            y += 16

    @log_error
    def draw_heart(self):
        self.oled.draw_heart_fullscreen(fill=1)

    @log_error
    def draw_current_page(self):
        page = self._current_page()
        pid = page['id']
        self.oled.clear()

        if pid == 'home':
            self.draw_home()
        elif pid == 'storage':
            self.draw_storage(page.get('slide', 0))
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
        self._advance_page_if_needed()
        self.draw_current_page()

    @log_error
    def close(self):
        if self.oled is not None and self.oled.is_ready():
            self.oled.clear()
            self.oled.display()
            self.oled.off()
            self.log.debug("OLED closed")
