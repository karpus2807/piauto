"""Render OLED pages from designer JSON layouts (Phase 2)."""

import math

from .oled_icons import draw_storage_icon, STORAGE_ICONS

_DRAW_Z = {
    'rect': 0,
    'bar': 1,
    'gauge': 2,
    'icon': 3,
    'text': 4,
    'metric': 5,
    'heart': 6,
}


class OledLayoutRenderer:
    """Draw a page from layout elements using live metrics from the OLED host."""

    def __init__(self, host):
        self.host = host
        self.oled = host.oled

    def render(self, page_def, slide=0):
        elements = page_def.get('elements') or []
        if not elements:
            return False
        pid = page_def.get('id', '')
        metrics = self.host.collect_layout_metrics(slide=slide, page_id=pid)
        ordered = sorted(
            enumerate(elements),
            key=lambda item: _DRAW_Z.get(item[1].get('type'), 5),
        )
        for _, el in ordered:
            self._draw_element(el, metrics)
        return True

    def _metric_text(self, el, metrics):
        key = el.get('key', '')
        raw = metrics.get(key)
        if raw is None:
            return '—'
        fmt = el.get('format', '{}')
        if fmt and '{' in fmt:
            try:
                return fmt.format(raw)
            except (TypeError, ValueError):
                return str(raw)
        return str(raw)

    def _metric_number(self, key, metrics, default=0):
        v = metrics.get(key)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def _draw_element(self, el, metrics):
        t = el.get('type')
        x = int(el.get('x', 0))
        y = int(el.get('y', 0))

        if t == 'text':
            size = 'md' if el.get('size') == 2 else 'sm'
            text = el.get('text', '')
            align = el.get('align', 'left')
            self.oled.draw_text(text, x, y, fill=1, align=align, size=size)
        elif t == 'metric':
            size = 'md' if el.get('size') == 2 else 'sm'
            text = self._metric_text(el, metrics)
            if not text:
                return
            align = el.get('align', 'left')
            fill = 0 if el.get('invert') else 1
            self.oled.draw_text(text, x, y, fill=fill, align=align, size=size)
        elif t == 'icon':
            pack = el.get('pack', 'builtin')
            icon = el.get('icon', 'disk')
            w = int(el.get('w', 14))
            h = int(el.get('h', 14))
            if pack == 'builtin':
                kind = icon.upper() if icon.upper() in STORAGE_ICONS else 'DISK'
                if icon in ('ssd', 'usb', 'disk'):
                    kind = icon.upper()
                draw_storage_icon(self.oled, kind, x, y, fill=1)
            else:
                self.oled.draw.rectangle((x, y, x + w, y + h), outline=1)
        elif t == 'rect':
            w = int(el.get('w', 10))
            h = int(el.get('h', 10))
            if el.get('fill'):
                self.oled.draw.rectangle((x, y, x + w, y + h), fill=1, outline=1)
                if el.get('invert_text'):
                    pass
            else:
                self.oled.draw.rectangle((x, y, x + w, y + h), outline=1)
        elif t == 'bar':
            w = int(el.get('w', 88))
            h = int(el.get('h', 10))
            pct = self._metric_number(el.get('key'), metrics, 0)
            mx = float(el.get('max', 100) or 100)
            pct = min(100, max(0, pct / mx * 100 if mx else pct))
            self.oled.draw_bar_graph_horizontal(pct, x, y, w, h)
        elif t == 'gauge':
            r = int(el.get('r', 13))
            pct = self._metric_number(el.get('key'), metrics, 0)
            start = int(el.get('start', 180))
            end = int(el.get('end', 0))
            self.oled.draw_pieslice_chart(pct, x, y, r, start, end)
            label_key = el.get('label_key')
            if label_key:
                label_el = {
                    'key': label_key,
                    'format': el.get('label_format', '{}'),
                }
                label = self._metric_text(label_el, metrics)
                if label and label != '—':
                    self.oled.draw_text(label, x, y, fill=1, align='center', size='sm')
        elif t == 'heart':
            margin = int(el.get('margin', 7))
            self.oled.draw_heart_fullscreen(fill=1, margin=margin)
