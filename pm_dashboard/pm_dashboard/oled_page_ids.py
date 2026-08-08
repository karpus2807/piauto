"""Built-in multi-page OLED designer page ids + stock hardware pages."""

OLED_PAGE_IDS = (
    'home', 'storage', 'network', 'cpu', 'gpu', 'fans',
    'ram', 'temps', 'services', 'heart',
)

# Firmware-native pages from pm_auto.addons.oled.pages.* (not canvas-editable).
STOCK_NATIVE_PAGE_IDS = (
    'mix', 'performance', 'ips', 'disk',
)

STOCK_NATIVE_SOURCES = {
    'mix': 'pm_auto.addons.oled.pages.mix.PageMix',
    'performance': 'pm_auto.addons.oled.pages.performance.PagePerformance',
    'ips': 'pm_auto.addons.oled.pages.ips.PageIPs',
    'disk': 'pm_auto.addons.oled.pages.disks.PageDisks',
}
