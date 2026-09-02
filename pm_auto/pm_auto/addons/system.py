from pm_auto.libs.addon import Addon
from pm_auto.libs.utils import log_error
from pm_auto.libs.task_scheduler import TaskScheduler

from sf_rpi_status import \
    get_cpu_temperature, \
    get_gpu_temperature, \
    get_cpu_percent, \
    get_cpu_freq, \
    get_cpu_count, \
    get_memory_info, \
    get_disks, \
    get_disk_info, \
    get_disks_info, \
    get_boot_time, \
    get_ips, \
    get_macs, \
    get_network_connection_type, \
    get_network_speed

import time
import socket
import asyncio


def _detect_network_types():
    from os import listdir
    from os.path import exists, isdir
    types = []
    try:
        names = listdir('/sys/class/net/')
    except Exception:
        names = []
    stats = {}
    try:
        from psutil import net_if_stats
        stats = net_if_stats()
    except Exception:
        stats = {}
    for name in names:
        if name == 'lo':
            continue
        isup = False
        if name in stats:
            isup = bool(stats[name].isup)
        else:
            try:
                with open(f'/sys/class/net/{name}/operstate', 'r') as f:
                    isup = f.read().strip() in ('up', 'unknown')
            except Exception:
                continue
        if not isup:
            continue
        wireless = isdir(f'/sys/class/net/{name}/wireless') or name.startswith(('wlan', 'wlp', 'wls', 'wlx'))
        virtual = exists(f'/sys/devices/virtual/net/{name}')
        wired = name.startswith(('eth', 'enp', 'ens', 'eno', 'end', 'enx'))
        vpn = name.startswith(('zt', 'wg', 'tun', 'tap', 'tailscale'))
        if wireless:
            label = 'Wireless'
        elif vpn or (virtual and not wired):
            label = 'VPN'
        else:
            label = 'Wired'
        if label not in types:
            types.append(label)
    if types:
        return types
    try:
        return list(get_network_connection_type() or [])
    except Exception:
        return []


def _format_network_type(types):
    seen = []
    for item in types or []:
        if item and item not in seen:
            seen.append(item)
    return '&'.join(seen) if seen else 'None'


def _top_cpu_lines(addon):
    """Best-effort top-3 process names for the OLED Services page."""
    try:
        import psutil
    except ImportError:
        return ['', '', '']
    try:
        if not getattr(addon, '_proc_cpu_primed', False):
            for proc in psutil.process_iter(['pid']):
                try:
                    proc.cpu_percent(None)
                except Exception:
                    continue
            addon._proc_cpu_primed = True
            return ['measuring...', '', '']
        rows = []
        for proc in psutil.process_iter(['name']):
            try:
                rows.append((float(proc.cpu_percent(None) or 0), proc.info.get('name') or '?'))
            except Exception:
                continue
        rows.sort(key=lambda item: item[0], reverse=True)
        lines = []
        for pct, name in rows[:3]:
            short = str(name)[:12]
            lines.append(f'{short} {pct:.0f}%')
        while len(lines) < 3:
            lines.append('')
        return lines
    except Exception:
        return ['', '', '']


class SystemAddon(Addon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event.subscribe('shutdown', self._on_shutdown)
        self.event.subscribe('request_ips', self._on_request_ips)
        self.tasks = TaskScheduler()
        self._is_ready = True

        # A list of last disk keys, for knowing which disk is gone,
        # and need to be removed from data
        self.disk_keys = []
        self._proc_cpu_primed = False

    @log_error
    def fetch_ip_data(self):
        ips = get_ips()
        result = {'ips': ips}
        for name in ips:
            result[f'ip_{name}'] = ips[name]
        macs = get_macs()
        for name in macs:
            result[f'mac_{name}'] = macs[name]
        result['network_type'] = _format_network_type(_detect_network_types())
        return result

    @log_error
    def _on_request_ips(self, *args):
        data = self.fetch_ip_data()
        self.event.publish('ip_data', data)

    @log_error
    def _on_shutdown(self, *args):
        if len(args) == 0:
            reason = 'None'
        else:
            reason = args[0]
        if reason != 'None' or reason != None or reason != 0:
            self.log.info(f"Shutdown reason: {reason}")
            self.event.publish('before_shutdown', reason)
            time.sleep(2)

            try:
                from sf_rpi_status import shutdown
                shutdown()
            except Exception as e:
                self.log.error(f"Failed to shutdown: {e}")
                from os import system
                system("shutdown -h now")

    @log_error
    def task_once(self):
        data = {}
        data['cpu_count'] = int(get_cpu_count())
        self.event.publish('data_changed', data)

    @log_error
    def task_1s(self):
        data = {}
        boot = float(get_boot_time())
        data['boot_time'] = boot
        data['uptime_seconds'] = max(0, int(time.time() - boot)) if boot else 0
        try:
            data['hostname'] = socket.gethostname()
        except Exception:
            data['hostname'] = ''

        data['cpu_temperature'] = float(get_cpu_temperature()) if get_cpu_temperature() is not None else None
        data['gpu_temperature'] = float(get_gpu_temperature()) if get_gpu_temperature() is not None else None
        cpu_percent = get_cpu_percent()
        data['cpu_percent'] = float(cpu_percent)
        cpu_percents = get_cpu_percent(percpu=True)
        for i, percent in enumerate(cpu_percents):
            data[f'cpu_{i}_percent'] = float(percent)

        cpu_freq = get_cpu_freq()
        data['cpu_freq'] = float(cpu_freq.current)
        data['cpu_freq_min'] = float(cpu_freq.min)
        data['cpu_freq_max'] = float(cpu_freq.max)

        memory = get_memory_info()
        data['memory_total'] = int(memory.total)
        data['memory_available'] = int(memory.available)
        data['memory_percent'] = float(memory.percent)
        data['memory_used'] = int(memory.used)
    
        network_speed = get_network_speed()
        data['network_upload_speed'] = int(network_speed.upload)
        data['network_download_speed'] = int(network_speed.download)
        data['network_type'] = _format_network_type(_detect_network_types())
    
        self.event.publish('data_changed', data)

    @log_error
    def task_3s(self):
        data = {}
        self.event.publish('data_changed', data)

    @log_error
    def task_5s(self):
        data = {}
        data['disk_list'] = get_disks()
        disks = get_disks_info(temperature=True)
        data['disks'] = disks
        for disk_name in disks:
            disk = disks[disk_name]
            data[f'disk_{disk_name}_mounted'] = int(disk.mounted)
            data[f'disk_{disk_name}_total'] = int(disk.total)
            data[f'disk_{disk_name}_used'] = int(disk.used)
            data[f'disk_{disk_name}_free'] = int(disk.free)
            data[f'disk_{disk_name}_percent'] = float(disk.percent)
            if (disk.temperature is not None):
                data[f'disk_{disk_name}_temperature'] = float(disk.temperature)
                
        # Get current disk keys
        keys = list(data.keys())
        # Find disk keys that is gone
        delete_keys = []
        for key in self.disk_keys:
            if key not in keys:
                delete_keys.append(key)
        # Update disk keys
        self.disk_keys = keys
        top = _top_cpu_lines(self)
        data['top_cpu_1'] = top[0]
        data['top_cpu_2'] = top[1]
        data['top_cpu_3'] = top[2]
        
        self.event.publish('data_changed', data, delete_keys=delete_keys)

    @log_error
    async def _main(self):
        self.log.debug("SystemAddon main loop started")
        await self.tasks.run_once(self.task_once, 1)
        await self.tasks.run_periodically(self.task_1s, 1)
        await self.tasks.run_periodically(self.task_5s, 5)
        while self.running:
            await asyncio.sleep(1)

    @log_error
    async def _stop(self):
        await self.tasks.stop()
