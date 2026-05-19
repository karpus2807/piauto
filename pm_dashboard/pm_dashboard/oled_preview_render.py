"""Render OLED page to PNG using the same pm_auto drawing code as the hardware."""

import io
import json

from flask import Response


def render_oled_page_png(page_id, slide=0, layout=None, system_config=None):
    """
    Return Flask Response with image/png, or None if render failed.
    Uses pm_auto preview buffer (identical fonts/layout to physical OLED).
    """
    try:
        from pm_auto.oled import OLED, OLED_DEFAULT_CONFIG
    except ImportError:
        return None

    cfg = dict(OLED_DEFAULT_CONFIG)
    cfg['oled_preview'] = True
    if system_config:
        for key in (
            'temperature_unit', 'oled_disk', 'oled_network_interface',
            'oled_designer_enabled', 'oled_designer_layout',
        ):
            if key in system_config:
                cfg[key] = system_config[key]

    host = OLED(cfg)
    if not host.is_ready():
        return None

    host.oled.clear()

    use_layout = layout
    if use_layout is None and system_config and system_config.get('oled_designer_layout'):
        raw = system_config['oled_designer_layout']
        try:
            use_layout = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            use_layout = None

    rendered = False
    if use_layout:
        host._load_designer_layout(use_layout)
        host._designer_enabled = True
        pdef = (use_layout.get('pages') or {}).get(page_id)
        if pdef and pdef.get('elements'):
            from pm_auto.oled_layout import OledLayoutRenderer
            host._layout_renderer = OledLayoutRenderer(host)
            rendered = host._layout_renderer.render(pdef, slide=slide)

    if not rendered:
        host.draw_legacy_page(page_id, slide)

    host.oled.display()

    buf = io.BytesIO()
    frame = host.oled._last_frame if host.oled._last_frame is not None else host.oled.image
    frame.save(buf, format='PNG')
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')
