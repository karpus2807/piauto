"""OLEDPage that renders a designer layout page id on stock SSD1306."""

from __future__ import annotations

import json

from pm_auto.libs.oled_page import OLEDPage

from .layout_renderer import OledLayoutRenderer
from .metrics import collect_metrics_from_data


class PageDesigner(OLEDPage):
    needs_ip = True

    def __init__(self, page_id, layout_holder):
        super().__init__()
        self.page_id = page_id
        self.layout_holder = layout_holder  # OLEDAddon instance-like object

    def main(self, oled, data, config):
        holder = self.layout_holder
        layout = getattr(holder, '_designer_layout', None) or {}
        pages = layout.get('pages') or {}
        page_def = pages.get(self.page_id)
        if not page_def or not page_def.get('elements'):
            oled.clear()
            oled.draw_text(self.page_id, 64, 24, align='center', size=12)
            oled.display()
            return

        def metrics_provider(slide=0, page_id=''):
            return collect_metrics_from_data(data, config, slide=slide)

        oled.clear()
        renderer = OledLayoutRenderer(oled, metrics_provider)
        renderer.render(page_def, slide=0)
        oled.display()


def parse_layout(raw):
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
    return None
