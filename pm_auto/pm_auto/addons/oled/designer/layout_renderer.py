"""Render OLED designer JSON layouts on stock SSD1306 (Max / pm_auto 2.x)."""

import time

from .icons import draw_builtin_icon

_DRAW_Z = {
    'rect': 0,
    'bar': 1,
    'gauge': 2,
    'icon': 3,
    'text': 4,
    'metric': 5,
    'heart': 6,
}

_FONT_MAP = {'sm': 8, 'md': 10, 'lg': 12, 'xl': 14, 1: 8, 2: 10}


def _font_px(el):
    if el.get('font') is not None:
        try:
            return max(8, min(14, int(el['font'])))
        except (TypeError, ValueError):
            return 8
    size = el.get('size', 1)
    if size in _FONT_MAP:
        return _FONT_MAP[size]
    try:
        return max(8, min(14, int(size)))
    except (TypeError, ValueError):
        return 8


def _draw_heart(oled, margin=7, fill=1):
    """Simple heart using polygons on the ImageDraw surface."""
    w, h = 128, 64
    # Normalized heart points scaled into OLED bounds with margin.
    pts = [
        (0.50, 0.18), (0.72, 0.05), (0.92, 0.22), (0.92, 0.42),
        (0.50, 0.88), (0.08, 0.42), (0.08, 0.22), (0.28, 0.05),
    ]
    box = []
    for px, py in pts:
        x = int(margin + px * (w - 2 * margin))
        y = int(margin + py * (h - 2 * margin))
        box.append((x, y))
    oled.draw.polygon(box, fill=fill)


class OledLayoutRenderer:
    def __init__(self, oled, metrics_provider):
        self.oled = oled
        self.metrics_provider = metrics_provider

    def render(self, page_def, slide=0):
        elements = page_def.get('elements') or []
        if not elements:
            return False
        metrics = self.metrics_provider(slide=slide, page_id=page_def.get('id', ''))
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
        size = _font_px(el)

        if t == 'text':
            self.oled.draw_text(el.get('text', ''), x, y, fill=1, align=el.get('align', 'left'), size=size)
        elif t == 'metric':
            text = self._metric_text(el, metrics)
            if not text:
                return
            fill = 0 if el.get('invert') else 1
            self.oled.draw_text(text, x, y, fill=fill, align=el.get('align', 'left'), size=size)
        elif t == 'icon':
            pack = el.get('pack', 'builtin')
            icon = el.get('icon', 'disk')
            w = int(el['w']) if 'w' in el else 14
            h = int(el['h']) if 'h' in el else 14
            animation = el.get('animation', 'none')
            frame = int(time.time() * 2)
            if animation == 'blink' and frame % 2:
                return
            if animation == 'pulse' and frame % 2 == 0:
                grow = 2
                x -= grow // 2
                y -= grow // 2
                w += grow
                h += grow
            if animation == 'spin' and frame % 2:
                x += 1
            if pack in ('builtin', 'bootstrap'):
                draw_builtin_icon(self.oled, icon, x, y, w, h, fill=1)
            else:
                self.oled.draw.rectangle((x, y, x + w, y + h), outline=1)
        elif t == 'rect':
            w = int(el.get('w', 10))
            h = int(el.get('h', 10))
            if el.get('fill'):
                self.oled.draw.rectangle((x, y, x + w, y + h), fill=1, outline=1)
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
        elif t == 'heart':
            _draw_heart(self.oled, margin=int(el.get('margin', 7)), fill=1)
