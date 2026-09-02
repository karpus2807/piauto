from pm_auto.libs.ssd1306 import SSD1306

from pm_auto.libs.utils import log_error, constrain
from pm_auto.libs.addon import Addon

from .pages import power_off_page
from .pages import get_pages
from .designer import DESIGNER_PAGE_IDS, STOCK_NATIVE_PAGE_IDS
from .designer.page import parse_layout
from .designer.templates import build_default_layout

import time
import asyncio
import json

def get_available_pages(peripherals):
    available_pages = []
    for item in peripherals:
        if item.startswith("oled_page_"):
            available_pages.append(item.split("oled_page_")[1])
    # Stock firmware pages (mix/performance/ips/disk) + designer ids.
    for pid in (*STOCK_NATIVE_PAGE_IDS, *DESIGNER_PAGE_IDS):
        if pid not in available_pages:
            available_pages.append(pid)
    return available_pages

def _normalize_pages(pages):
    if pages is None:
        return []
    if isinstance(pages, str):
        pages = [p.strip() for p in pages.split(',') if p.strip()]
    return list(pages)

class OLEDAddon(Addon):
    REFRESH_INTERVAL = 1 # seconds, how often to refresh the display
    MIN_SLEEP_TIMEOUT = 0 # 5s, minimum sleep timeout
    MAX_SLEEP_TIMEOUT = 3600 # 3600s, 10min, maximum sleep timeout

    DEFAULT_CONFIG = {
        'oled_enable': True,
        'oled_rotation': 0, # 0, 90, 180, 270 degrees
        'scroll_interval': 3,  # seconds, how often to scroll the content
        'oled_sleep_timeout': 10, # seconds, how long to wait before going to sleep
        'temperature_unit': 'C', # 'C' for Celsius, 'F' for Fahrenheit
        'oled_pages': [
            'mix',
            'performance',
            'ips',
            'disk',
        ],
        'oled_designer_enabled': False,
        'oled_designer_layout': '',
    }

    @log_error
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not hasattr(self, 'rotation'):
            self.rotation = int(self.config.get('oled_rotation') or 0)
        if not hasattr(self, 'enable'):
            self.enable = bool(self.config.get('oled_enable', True))
        if not hasattr(self, 'oled_pages'):
            self.oled_pages = list(self.config.get('oled_pages') or [])

        try:
            self.oled = SSD1306(rotation=self.rotation)
        except Exception as e:
            self.log.error(f"Failed to initialize OLED service: {e}")
            return
        self._is_ready = self.oled.is_ready()

        self.available_pages = get_available_pages(self.peripherals)

        self.wake_flag = True
        self.wake_start_time = 0
        self.is_power_off = False
        self._power_off_start = 0
        self.is_wake_page_next = False
        self.is_page_prev = False
        self.data = {}
        # Keep designer layout/enabled already loaded from config.json in
        # update_config(); do not reset to stock templates after reboot.
        if not hasattr(self, '_designer_enabled'):
            self._designer_enabled = False
        if not hasattr(self, '_designer_layout') or self._designer_layout is None:
            self._designer_layout = build_default_layout()
        if not hasattr(self, '_designer_test'):
            self._designer_test = None
        self._page_shown_at = 0
        self._page_ids = []

        self.event.subscribe("oled_wake_page_next", self.wake_page_next)
        self.event.subscribe("oled_page_prev", self.page_prev)
        self.event.subscribe("shutdown", self.show_shutdown_screen)
        self.event.subscribe("oled_show_shutdown_screen", self.show_shutdown_screen)
        self.event.subscribe("oled_clear_screen", self.clear_screen)
        self.event.subscribe("data_changed", self.handle_data_changed)
        self.event.subscribe('ip_data', self.handle_ip_data)

    @log_error
    def handle_data_changed(self, data, delete_keys: list = []):
        # Delete old data
        for key in delete_keys:
            if key in self.data:
                del self.data[key]

        self.data.update(data)

    @log_error
    def handle_ip_data(self, data):
        self.data.update(data)
        self.last_page_index = -1

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
        for key, value in config.items():
            if key in self.DEFAULT_CONFIG:
                self.config[key] = value
        if "oled_enable" in config:
            _enable = bool(config['oled_enable'])
            self.enable = _enable
            patch['oled_enable'] = _enable
            self.log.debug(f"Update oled_enable to {_enable}")
            if not init:
                if _enable:
                    self.wake()
                else:
                    self.sleep()
        if "oled_rotation" in config:
            _rotation = int(config['oled_rotation'])
            if _rotation not in [0, 90, 180, 270]:
                self.log.error("Invalid rotation value, must be 0, 90, 180, or 270")
            else:
                self.rotation = _rotation
                patch['oled_rotation'] = _rotation
                if not init:
                    self.set_rotation(_rotation)
                self.log.debug(f"Update oled_rotation to {_rotation}")
        if "scroll_interval" in config:
            _interval = int(config['scroll_interval'])
            self.scroll_interval = _interval
            patch['scroll_interval'] = _interval
            self.log.debug(f"Update scroll_interval to {_interval}")
        if "oled_sleep_timeout" in config:
            _timeout = int(config['oled_sleep_timeout'])

            if _timeout < self.MIN_SLEEP_TIMEOUT or _timeout > self.MAX_SLEEP_TIMEOUT:
                self.log.warning(f"Invalid sleep timeout value, must be between {self.MIN_SLEEP_TIMEOUT} and {self.MAX_SLEEP_TIMEOUT}")
                _timeout = constrain(_timeout, self.MIN_SLEEP_TIMEOUT, self.MAX_SLEEP_TIMEOUT)
            self.sleep_timeout = _timeout
            patch['oled_sleep_timeout'] = _timeout
            self.log.debug(f"Update oled_sleep_timeout to {_timeout}")
        if "temperature_unit" in config:
            _unit = config['temperature_unit']
            if _unit not in ['C', 'F']:
                self.log.error("Invalid temperature unit, must be 'C' or 'F'")
            else:
                self.temperature_unit = _unit
                patch['temperature_unit'] = _unit
                self.log.debug(f"Update temperature_unit to {_unit}")
        if "oled_pages" in config:
            raw_pages = _normalize_pages(config['oled_pages'])
            new_pages = []
            for page in raw_pages:
                if not init and page not in self.available_pages and not str(page).startswith('custom_'):
                    self.log.warning(f"Invalid oled page {page}, must be in {self.available_pages}")
                elif page in new_pages:
                    self.log.warning(f"Duplicate oled page {page}")
                else:
                    new_pages.append(page)
            if not init:
                self.update_pages(pages=new_pages)
            self.oled_pages = new_pages
            patch['oled_pages'] = new_pages
            self.log.debug(f"Update oled_pages to {self.oled_pages}")
        if "oled_designer_enabled" in config:
            self._designer_enabled = bool(config['oled_designer_enabled'])
            patch['oled_designer_enabled'] = self._designer_enabled
            self.log.debug(f"Update oled_designer_enabled to {self._designer_enabled}")
        if "oled_designer_layout" in config:
            layout = parse_layout(config['oled_designer_layout'])
            if layout is None:
                layout = build_default_layout()
            self._designer_layout = layout
            # Persist as string for config.json compatibility
            if isinstance(config['oled_designer_layout'], str):
                patch['oled_designer_layout'] = config['oled_designer_layout']
            else:
                patch['oled_designer_layout'] = json.dumps(layout)
            if not init:
                self.update_pages()
            self.log.debug("Update oled_designer_layout")
        if "oled_designer_test" in config:
            self._designer_test = config.get('oled_designer_test')
            self.wake()
            self.last_page_index = -1
            self.log.debug("OLED designer test requested")
        self.config.update(patch)
        return patch

    @log_error
    def set_rotation(self, rotation):
        self.oled.set_rotation(rotation)

    @log_error
    def show_shutdown_screen(self, reason):
        self.log.info(f"Show shutdown screen, reason: {reason}")
        self.is_power_off = True
        self._power_off_start = time.time()

    @log_error
    def clear_screen(self, *args, **kwargs):
        """Clear OLED screen immediately — called before forced power-off."""
        self.log.debug('OLED clear screen (pre-shutdown)')
        self.oled.clear()
        self.oled.display()
        self.wake_flag = False

    @log_error
    def wake(self):
        self.wake_start_time = time.time()
        self.wake_flag = True

    @log_error
    def wake_page_next(self, *args, **kwargs):
        self.log.debug(f'OLED wake or next page')
        # Don't call self.wake() here — let _main() decide whether to
        # just wake (if sleeping) or flip page (if already awake).
        self.is_wake_page_next = True

    @log_error
    def page_prev(self, *args, **kwargs):
        self.log.debug(f'OLED prev page')
        self.is_page_prev = True

    @log_error
    def sleep(self):
        self.log.debug(f'OLED sleep')
        self.wake_flag = False
        self.oled.clear()
        self.oled.display()

    @log_error
    def update_pages(self, pages=None):
        configured = list(pages if pages is not None else (getattr(self, 'oled_pages', None) or []))
        layout = self._designer_layout or {}
        active = configured
        # Static mode: only one page forever (no auto-rotate).
        if layout.get('static') or layout.get('mode') == 'static':
            static_id = str(layout.get('static_page') or '').strip()
            if static_id:
                active = [static_id]
            elif configured:
                active = [configured[0]]
            else:
                active = []
        # When designer is enabled, prefer carousel from layout if oled_pages empty
        elif self._designer_enabled and not active and layout:
            active = list(layout.get('carousel') or [])
        self._page_ids = list(active)
        self.pages = get_pages(active, addon=self)
        self.log.debug(f'Update pages to: {self._page_ids} -> {self.pages}')
        self.page_index = 0
        self.last_page_index = -1
        self._page_shown_at = time.time()
        self.wake()

    def _current_page_id(self):
        ids = getattr(self, '_page_ids', None) or getattr(self, 'oled_pages', None) or []
        if 0 <= self.page_index < len(ids):
            return ids[self.page_index]
        return None

    def _is_static_mode(self):
        layout = self._designer_layout or {}
        if layout.get('static') or layout.get('mode') == 'static':
            return True
        return len(getattr(self, '_page_ids', None) or getattr(self, 'oled_pages', None) or []) <= 1

    def _page_duration_seconds(self, page_id):
        """How long to show a page before auto-advance. None = never."""
        if self._is_static_mode():
            return None
        layout = self._designer_layout or {}
        page = (layout.get('pages') or {}).get(page_id or '') or {}
        try:
            duration = int(page.get('duration', 5))
        except (TypeError, ValueError):
            duration = 5
        return constrain(duration, 2, 120)

    def _render_designer_page(self, page_id, layout=None):
        # Stock firmware pages: run the real PageMix/etc. during Test-on-OLED.
        if page_id in STOCK_NATIVE_PAGE_IDS:
            try:
                pages = get_pages([page_id], addon=self)
                if pages:
                    pages[0].main(self.oled, self.data, self.config)
                    return
            except Exception as e:
                self.log.exception(f"OLED stock test render failed ({page_id}): {e}")
                return
        from .designer.page import PageDesigner
        layout = layout or self._designer_layout or build_default_layout()
        holder = self
        prev = getattr(self, '_designer_layout', None)
        self._designer_layout = layout
        try:
            PageDesigner(page_id, holder).main(self.oled, self.data, self.config)
        except Exception as e:
            self.log.exception(f"OLED designer render failed ({page_id}): {e}")
        finally:
            self._designer_layout = prev if prev is not None else layout

    @log_error
    async def _main(self):
        self.update_pages()
        last_refresh_time = 0

        if self.oled is None or not self.oled.is_ready():
            self.log.error("OLED service not ready")
            return

        self.wake_start_time = time.time()

        while self.running:
            if not self.enable:
                if self.wake_flag:
                    self.log.debug("OLED disabled, going to sleep")
                    self.sleep()
                await asyncio.sleep(1)
                continue
            
            if self.is_power_off == True:
                # Show POWER OFF for 2s, then clear display so next boot
                # doesn't show a misleading "POWER OFF" from stale RAM.
                if time.time() - self._power_off_start < 2:
                    self.log.debug("OLED show power off page")
                    power_off_page.main(self.oled)
                else:
                    self.clear_screen()
                await asyncio.sleep(0.1)
                continue

            # Temporary Test-on-OLED from designer
            test = self._designer_test
            if isinstance(test, dict):
                until = float(test.get('until') or 0)
                if time.time() < until:
                    page_id = str(test.get('page') or 'home')
                    layout = test.get('layout') or self._designer_layout
                    if self.last_page_index != -99 or time.time() - last_refresh_time > self.REFRESH_INTERVAL:
                        self.last_page_index = -99
                        last_refresh_time = time.time()
                        self._render_designer_page(page_id, layout=layout)
                    await asyncio.sleep(0.05)
                    continue
                self._designer_test = None
                self.last_page_index = -1

            if len(self.pages) < 1:
                self.oled.draw_text(f'config error', 64, 20, align='center', size=16)
                self.oled.display()
                await asyncio.sleep(1)
                continue

            if self.is_wake_page_next:
                if not self.wake_flag:
                    self.log.debug("OLED service waking up")
                    self.wake_flag = True
                    self.last_page_index = -1
                else:
                    self.page_index += 1
                    if self.page_index >= len(self.pages):
                        self.page_index = 0
                    self._page_shown_at = time.time()
                self.wake_start_time = time.time()
                self.is_wake_page_next = False
            elif self.is_page_prev:
                if self.wake_flag:
                    self.page_index -= 1
                    if self.page_index < 0:
                        self.page_index = len(self.pages) - 1
                    self._page_shown_at = time.time()
                    self.wake_start_time = time.time()
                self.is_page_prev = False

            # Auto-advance carousel by each page's duration (default 5s).
            # Static mode / single page: never rotate.
            if (
                self.wake_flag
                and not self._is_static_mode()
                and len(self.pages) > 1
                and not self.is_wake_page_next
                and not self.is_page_prev
            ):
                if not self._page_shown_at:
                    self._page_shown_at = time.time()
                duration = self._page_duration_seconds(self._current_page_id())
                if duration and (time.time() - self._page_shown_at) >= duration:
                    self.page_index = (self.page_index + 1) % len(self.pages)
                    self._page_shown_at = time.time()
                    self.wake_start_time = time.time()

            if self.wake_flag and self.last_page_index != self.page_index:
                page = self.pages[self.page_index]
                if hasattr(page, 'needs_ip') and page.needs_ip:
                    self.event.publish('request_ips')
                if self._page_shown_at <= 0:
                    self._page_shown_at = time.time()

            if self.wake_flag:
                if self.last_page_index != self.page_index or time.time() - last_refresh_time > self.REFRESH_INTERVAL:
                    if self.last_page_index != self.page_index:
                        self._page_shown_at = time.time()
                    self.last_page_index = self.page_index
                    last_refresh_time = time.time()
                    page = self.pages[self.page_index]
                    try:
                        page.main(self.oled, self.data, self.config)
                    except Exception as e:
                        # One bad page must not kill the OLED loop (e.g. font OSError).
                        self.log.exception(f"OLED page render failed ({type(page).__name__}): {e}")

                if self.sleep_timeout > 0 and time.time() - self.wake_start_time > self.sleep_timeout:
                    self.log.debug("OLED sleep timeout, sleeping")
                    self.sleep()
                    await asyncio.sleep(1)
                    continue

            await asyncio.sleep(.05)

    @log_error
    async def _stop(self):
        if self.oled is not None and self.oled.is_ready():
            self.oled.clear()
            self.oled.display()
            self.oled.off()

