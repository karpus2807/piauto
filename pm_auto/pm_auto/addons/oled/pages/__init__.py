
from .power_off import PagePowerOff

power_off_page = PagePowerOff()

DESIGNER_FALLBACK_IDS = {
    'home', 'storage', 'network', 'cpu', 'gpu', 'fans',
    'ram', 'temps', 'services', 'heart',
}


def get_pages(page_names, addon=None):
    pages = []
    for name in page_names:
        if 'battery' == name:
            from .battery import PageBattery
            pages.append(PageBattery())
        elif 'disk' == name:
            from .disks import PageDisks
            pages.append(PageDisks())
        elif 'input' == name:
            from .input import PageInput
            pages.append(PageInput())
        elif 'ips' == name:
            from .ips import PageIPs
            pages.append(PageIPs())
        elif 'mix' == name:
            from .mix import PageMix
            pages.append(PageMix())
        elif 'rpi_power' == name:
            from .rpi_power import PageRPiPower
            pages.append(PageRPiPower())
        elif 'performance' == name:
            from .performance import PagePerformance
            pages.append(PagePerformance())
        elif name in DESIGNER_FALLBACK_IDS or str(name).startswith('custom_'):
            from ..designer.page import PageDesigner
            pages.append(PageDesigner(name, addon))
        else:
            raise ValueError(f"Unknown page name: {name}")

    return pages
