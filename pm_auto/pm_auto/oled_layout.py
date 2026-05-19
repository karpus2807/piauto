"""Render OLED pages from designer JSON layouts (Phase 2)."""

from .oled_icons import STORAGE_ICONS, draw_storage_icon

_DRAW_Z = {
    'rect': 0,
    'bar': 1,
    'gauge': 2,
    'icon': 3,
    'text': 4,
    'metric': 5,
    'heart': 6,
}

_FONT_MAP = {8: 'sm', 10: 'md', 12: 'lg', 14: 'xl'}


def _snap_font(px):
    try:
        n = int(px)
    except (TypeError, ValueError):
        n = 8
    for size in (8, 10, 12, 14):
        if abs(n - size) <= 1:
            return size
    return max(8, min(14, n))


def _draw_bitmap_scaled(oled, bmp, x, y, w, h, fill=1):
    native_w = len(bmp[0])
    native_h = len(bmp)
    w = max(1, int(w))
    h = max(1, int(h))
    for row in range(h):
        for col in range(w):
            sr = int(row * native_h / h)
            sc = int(col * native_w / w)
            if bmp[sr][sc]:
                oled.draw.point((x + col, y + row), fill=fill)


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

    def _text_size(self, el):
        """Match legacy OLED: 8px (sm) unless font px or size=2 explicitly set."""
        if el.get('font') is not None:
            return _FONT_MAP.get(_snap_font(el['font']), 'sm')
        if el.get('size') == 2:
            return 'md'
        return 'sm'

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
            size = self._text_size(el)
            text = el.get('text', '')
            align = el.get('align', 'left')
            self.oled.draw_text(text, x, y, fill=1, align=align, size=size)
        elif t == 'metric':
            size = self._text_size(el)
            text = self._metric_text(el, metrics)
            if not text:
                return
            align = el.get('align', 'left')
            fill = 0 if el.get('invert') else 1
            self.oled.draw_text(text, x, y, fill=fill, align=align, size=size)
        elif t == 'icon':
            pack = el.get('pack', 'builtin')
            icon = el.get('icon', 'disk')
            w = int(el['w']) if 'w' in el else 14
            h = int(el['h']) if 'h' in el else 14
            if pack == 'builtin':
                kind = icon.upper() if icon.upper() in STORAGE_ICONS else 'DISK'
                if icon in ('ssd', 'usb', 'disk'):
                    kind = icon.upper()
                icon_bmp = STORAGE_ICONS.get(kind, STORAGE_ICONS['DISK'])
                if ('w' in el or 'h' in el) and (w != 14 or h != 14):
                    _draw_bitmap_scaled(self.oled, icon_bmp, x, y, w, h, fill=1)
                else:
                    draw_storage_icon(self.oled, kind, x, y, fill=1)
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
