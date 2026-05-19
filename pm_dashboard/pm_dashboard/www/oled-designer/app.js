const API = '/api/v1.0';
const BUILTIN_PAGE_IDS = [
  'home', 'storage', 'network', 'cpu', 'gpu', 'fans',
  'ram', 'temps', 'services', 'heart',
];

const BUILTIN_BI = {
  cpu: 'bi-cpu-fill', gpu: 'bi-gpu-card', ram: 'bi-memory',
  disk: 'bi-hdd', ssd: 'bi-device-ssd', usb: 'bi-usb-symbol',
  wifi: 'bi-wifi', ethernet: 'bi-ethernet', fan: 'bi-fan',
  temp: 'bi-thermometer-half', heart: 'bi-heart-fill',
  alert: 'bi-exclamation-triangle-fill', power: 'bi-lightning-charge-fill',
  clock: 'bi-clock', server: 'bi-server', home: 'bi-house-fill',
};

const BOOTSTRAP_PICK = [
  'bi-cpu-fill', 'bi-gpu-card', 'bi-memory', 'bi-hdd-fill', 'bi-device-ssd-fill',
  'bi-wifi', 'bi-ethernet', 'bi-fan', 'bi-thermometer-half', 'bi-thermometer-high',
  'bi-heart-fill', 'bi-lightning-charge-fill', 'bi-battery-half', 'bi-speedometer2',
  'bi-hdd-network-fill', 'bi-cloud', 'bi-router', 'bi-pc-display', 'bi-display',
  'bi-activity', 'bi-bar-chart-fill', 'bi-graph-up', 'bi-clock-history',
  'bi-exclamation-triangle-fill', 'bi-shield-check', 'bi-gear-fill', 'bi-power',
];

let spec = null;
let layout = null;
let metrics = {};
let pageId = 'home';
let selIdx = -1;
let drag = null;
let toastBs = null;
let previewBusy = false;
/** Sharp preview via server PNG (real OLED fonts); no live polling */
let useHardwarePreview = true;
let metricsPollTimer = null;
let renderDebounceTimer = null;

const STATIC_METRICS = {
  cpu_temperature: 52.3,
  gpu_temperature: 48.0,
  cpu_percent: 24,
  memory_percent: 61,
  storage_percent: 72,
  storage_percent_free: 28,
  pwm_fan_speed: 3200,
  gpio_fan_state: true,
  hostname: 'pironman',
  gpu_percent: 12,
  ip_line: '192.168.1.42',
  ram_line: 'RAM 61%',
  storage_line: 'STORE 72%',
  storage_detail: 'SSD 512G',
  storage_temp: '32C',
  cpu_use_line: 'USE 24%',
  cpu_temp_line: 'TEMP 52C',
  cpu_temp_label: '52C',
  cpu_temp_gauge: 52,
  gpu_use_line: 'USE 12%',
  gpu_temp_line: 'TEMP 48C',
  tower_rpm_line: 'TOWER 3200 RPM',
  side_fan_line: 'SIDE  ON',
  fan_mode_line: 'MODE  Auto',
  net_line_1: 'eth0 192.168.1.42',
  net_line_2: 'wlan0 10.0.0.5',
  top_cpu_1: 'python 18%',
  top_cpu_2: 'node 9%',
  top_cpu_3: 'idle 73%',
};

const canvas = document.getElementById('oled');
const ctx = canvas ? canvas.getContext('2d') : null;
if (ctx) {
  ctx.imageSmoothingEnabled = false;
}
const Z_ORDER = { rect: 0, bar: 1, gauge: 2, icon: 3, text: 4, metric: 5, heart: 6 };
const FONT_PX = [8, 10, 12, 14];
const RESIZE_HANDLES = ['nw', 'ne', 'sw', 'se'];
const HANDLE_HIT = 6;

function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}

function snapFont(px) {
  const n = Number(px) || 8;
  return FONT_PX.reduce((best, s) => (Math.abs(s - n) < Math.abs(best - n) ? s : best), 8);
}

function fontPx(el) {
  if (el.font != null) return snapFont(el.font);
  if (el.size === 2) return 10;
  return 8;
}

function fontFromBoxHeight(h) {
  return snapFont(Math.round(Math.max(8, Math.min(14, (h || 12) * 0.75))));
}

function setElementFont(el, px) {
  el.font = snapFont(px);
  el.size = el.font >= 10 ? 2 : 1;
  if (el.type === 'text' || el.type === 'metric') {
    el.h = Math.max(6, el.font + 4);
  }
}

/** Read-only defaults for handles/hit-test — does not change saved layout */
function layoutDims(el) {
  if (!el) return { w: 80, h: 12 };
  if (el.type === 'text' || el.type === 'metric') {
    return {
      w: el.w || 80,
      h: el.h || (el.font ? snapFont(el.font) + 4 : (el.size === 2 ? 14 : 12)),
    };
  }
  if (el.type === 'icon') return { w: el.w || 14, h: el.h || 14 };
  if (el.type === 'bar') return { w: el.w || 120, h: el.h || 8 };
  if (el.type === 'rect') return { w: el.w || 40, h: el.h || 20 };
  if (el.type === 'gauge') {
    const r = el.r || 13;
    return { w: r * 2, h: r * 2 };
  }
  return { w: 80, h: 12 };
}

/** Only for newly added elements (user resize sets fields directly) */
function initNewElementBox(el) {
  if (!el || el.type === 'heart') return;
  if (el.type === 'text' || el.type === 'metric') {
    if (el.font == null) setElementFont(el, 8);
    if (!el.w) el.w = 80;
    if (!el.h) el.h = fontPx(el) + 4;
  } else if (el.type === 'icon') {
    if (!el.w) el.w = 14;
    if (!el.h) el.h = 14;
  } else if (el.type === 'rect' || el.type === 'bar') {
    if (!el.w) el.w = el.type === 'bar' ? 120 : 40;
    if (!el.h) el.h = el.type === 'bar' ? 8 : 20;
  } else if (el.type === 'gauge' && !el.r) {
    el.r = 13;
  }
}

function isResizable(el) {
  return el && el.type !== 'heart';
}

function handlePoint(b, handle) {
  switch (handle) {
    case 'nw': return { x: b.x, y: b.y };
    case 'ne': return { x: b.x + b.w, y: b.y };
    case 'sw': return { x: b.x, y: b.y + b.h };
    default: return { x: b.x + b.w, y: b.y + b.h };
  }
}

function hitResizeHandle(mx, my) {
  if (selIdx < 0) return null;
  const el = currentPage().elements[selIdx];
  if (!isResizable(el)) return null;
  const b = bounds(el);
  for (const h of RESIZE_HANDLES) {
    const p = handlePoint(b, h);
    if (Math.abs(mx - p.x) <= HANDLE_HIT && Math.abs(my - p.y) <= HANDLE_HIT) return h;
  }
  return null;
}

function applyResize(el, handle, mx, my, start) {
  let { x0, y0, x1, y1 } = start;
  if (handle === 'se') { x1 = mx; y1 = my; }
  else if (handle === 'sw') { x0 = mx; y1 = my; }
  else if (handle === 'ne') { x1 = mx; y0 = my; }
  else if (handle === 'nw') { x0 = mx; y0 = my; }

  let lx = Math.min(x0, x1);
  let ly = Math.min(y0, y1);
  let w = Math.max(8, Math.abs(x1 - x0));
  let h = Math.max(6, Math.abs(y1 - y0));
  lx = clamp(lx, 0, 127);
  ly = clamp(ly, 0, 63);
  w = Math.min(w, 128 - lx);
  h = Math.min(h, 64 - ly);

  if (el.type === 'gauge') {
    const cx = Math.round(lx + w / 2);
    const cy = Math.round(ly + h / 2);
    el.x = cx;
    el.y = cy;
    el.r = clamp(Math.round(Math.min(w, h) / 2), 4, 24);
    return;
  }

  el.x = Math.round(lx);
  el.y = Math.round(ly);
  el.w = Math.round(w);
  el.h = Math.round(h);
  if (el.type === 'text' || el.type === 'metric') {
    setElementFont(el, fontFromBoxHeight(el.h));
  }
}

function resizeCursor(handle) {
  if (handle === 'nw' || handle === 'se') return 'nwse-resize';
  if (handle === 'ne' || handle === 'sw') return 'nesw-resize';
  return 'crosshair';
}

async function api(path, method = 'GET', body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  const text = await res.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch (_) {
    throw new Error(`Bad API response (${res.status}): ${text.slice(0, 120)}`);
  }
  if (!json.status) throw new Error(json.error || 'Request failed');
  return json.data;
}

function onClick(id, fn) {
  const el = document.getElementById(id);
  if (el) el.addEventListener('click', fn);
}

function toast(msg, err = false) {
  const el = document.getElementById('toast');
  document.getElementById('toast-body').textContent = msg;
  el.classList.toggle('text-bg-danger', err);
  el.classList.toggle('text-bg-success', !err);
  if (!toastBs) toastBs = bootstrap.Toast.getOrCreateInstance(el, { delay: 4500 });
  toastBs.show();
}

function currentPage() {
  if (!layout.pages[pageId]) {
    layout.pages[pageId] = { id: pageId, name: pageId, duration: 5, elements: [] };
  }
  return layout.pages[pageId];
}

function isBuiltin(id) {
  return BUILTIN_PAGE_IDS.includes(id) || layout.pages[id]?.builtin;
}

function formatMetric(el) {
  const key = el.key;
  const v = metrics[key];
  if (v == null || v === '') return '—';
  if (typeof v === 'string') return v;
  const fmt = el.format || '{}';
  if (fmt.includes('{')) {
    try {
      return fmt.replace(/\{[^}]+\}/, String(v));
    } catch (_) {
      return String(v);
    }
  }
  if (key === 'gpio_fan_state') return v ? 'ON' : 'OFF';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(1);
  return String(v);
}

function drawGauge(cx, cy, r, pct, startDeg, endDeg) {
  const start = (startDeg * Math.PI) / 180;
  const end = (endDeg * Math.PI) / 180;
  const valueEnd = start + ((end - start) * Math.min(100, Math.max(0, pct))) / 100;
  ctx.strokeStyle = '#fff';
  ctx.beginPath();
  ctx.arc(cx, cy, r, start, end);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx, cy, r, start, valueEnd);
  ctx.lineTo(cx, cy);
  ctx.closePath();
  ctx.fillStyle = '#fff';
  ctx.fill();
}

function drawHeartFull() {
  ctx.fillStyle = '#fff';
  for (let y = 8; y < 56; y++) {
    for (let x = 16; x < 112; x++) {
      const dx = x < 64 ? (x - 36) / 28 : (x - 92) / 28;
      const dy = (y - 28) / 24;
      if (dx * dx + dy * dy < 1 && (x + y) % 3 !== 1) ctx.fillRect(x, y, 1, 1);
    }
  }
}

function drawTextOled(text, el, align, fillLight) {
  const px = fontPx(el);
  ctx.font = `${px}px monospace`;
  ctx.textBaseline = 'top';
  ctx.fillStyle = fillLight ? '#000' : '#fff';
  const ty = Math.round(el.y);
  let tx = Math.round(el.x);
  if (align === 'center') tx = Math.round(el.x - ctx.measureText(text).width / 2);
  else if (align === 'right') tx = Math.round(el.x - ctx.measureText(text).width);
  ctx.fillText(text, tx, ty);
  ctx.fillStyle = '#fff';
}

function drawSelectionOverlay() {
  if (selIdx < 0) return;
  const el = currentPage().elements[selIdx];
  if (!isResizable(el)) return;
  const b = bounds(el);
  ctx.strokeStyle = '#3d8bfd';
  ctx.lineWidth = 1;
  ctx.strokeRect(b.x - 1, b.y - 1, b.w + 2, b.h + 2);
  ctx.fillStyle = '#3d8bfd';
  RESIZE_HANDLES.forEach((h) => {
    const p = handlePoint(b, h);
    ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
  });
  ctx.strokeStyle = '#fff';
  ctx.fillStyle = '#fff';
}

async function renderHardwarePreview() {
  if (!ctx || previewBusy) return false;
  previewBusy = true;
  try {
    const res = await fetch(API + '/oled-preview-png', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page: pageId, slide: 0, layout }),
    });
    if (!res.ok || !res.headers.get('content-type')?.includes('image')) {
      return false;
    }
    const blob = await res.blob();
    const bmp = await createImageBitmap(blob);
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, 128, 64);
    ctx.drawImage(bmp, 0, 0, 128, 64);
    drawSelectionOverlay();
    return true;
  } catch (_) {
    return false;
  } finally {
    previewBusy = false;
  }
}

function renderCanvasFallback() {
  if (!ctx) return;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, 128, 64);
  ctx.fillStyle = '#fff';
  ctx.strokeStyle = '#fff';

  const base = currentPage().elements || [];
  const els = base
    .map((el, i) => ({ el, i }))
    .sort((a, b) => (Z_ORDER[a.el.type] ?? 5) - (Z_ORDER[b.el.type] ?? 5));
  els.forEach(({ el, i }) => {
    const selected = i === selIdx;
    if (el.type === 'text') {
      drawTextOled(el.text || '', el, el.align || 'left', false);
    } else if (el.type === 'metric') {
      const t = formatMetric(el);
      drawTextOled(t, el, el.align || 'left', el.invert || el.key === 'ip_line');
    } else if (el.type === 'icon') {
      const iw = el.w || 16;
      const ih = el.h || 16;
      ctx.strokeStyle = '#888';
      ctx.strokeRect(el.x, el.y, iw, ih);
      const labelPx = snapFont(Math.max(6, Math.min(12, Math.round(ih * 0.45))));
      ctx.font = `${labelPx}px monospace`;
      ctx.fillStyle = '#aaa';
      ctx.fillText((el.icon || 'ic').slice(0, 4), el.x + 2, el.y + Math.floor((ih - labelPx) / 2));
      ctx.fillStyle = '#fff';
    } else if (el.type === 'rect') {
      if (el.fill) ctx.fillRect(el.x, el.y, el.w, el.h);
      else ctx.strokeRect(el.x, el.y, el.w, el.h);
    } else if (el.type === 'bar') {
      const pct = Math.min(100, Math.max(0, Number(metrics[el.key]) || 0));
      const fill = (el.w * pct) / (el.max || 100);
      ctx.strokeRect(el.x, el.y, el.w, el.h);
      ctx.fillRect(el.x + 1, el.y + 1, Math.max(0, fill - 2), el.h - 2);
    } else if (el.type === 'gauge') {
      const pct = Number(metrics[el.key]) || 0;
      drawGauge(el.x, el.y, el.r || 13, pct, el.start ?? 180, el.end ?? 0);
      if (el.label_key) {
        const t = formatMetric({ key: el.label_key, format: el.label_format || '{}' });
        const lbl = { type: 'text', x: el.x, y: el.y, font: 8, h: 10, w: 40 };
        drawTextOled(t, lbl, 'center', false);
      }
    } else if (el.type === 'heart') {
      drawHeartFull();
    }
    if (selected) drawSelectionOverlay();
  });
}

async function render() {
  if (useHardwarePreview) {
    const ok = await renderHardwarePreview();
    if (ok) return;
  }
  renderCanvasFallback();
}

function requestRender(immediate = false) {
  if (immediate) {
    if (renderDebounceTimer) clearTimeout(renderDebounceTimer);
    renderDebounceTimer = null;
    return render();
  }
  if (renderDebounceTimer) clearTimeout(renderDebounceTimer);
  renderDebounceTimer = setTimeout(() => {
    renderDebounceTimer = null;
    render();
  }, 400);
}

function renderQuick() {
  renderCanvasFallback();
}

async function previewOnDevice() {
  await requestRender(true);
  toast('Preview updated (real OLED fonts)');
}

function stopLivePreview() {
  if (metricsPollTimer) {
    clearInterval(metricsPollTimer);
    metricsPollTimer = null;
  }
}

function ensureLayout() {
  if (!layout || typeof layout !== 'object') {
    layout = { version: 1, pages: {}, carousel: [...BUILTIN_PAGE_IDS, 'heart'] };
  }
  if (!layout.pages || typeof layout.pages !== 'object') layout.pages = {};
  BUILTIN_PAGE_IDS.forEach((id) => {
    if (!layout.pages[id]) {
      layout.pages[id] = { id, name: id, duration: 5, builtin: true, elements: [] };
    }
  });
  if (!Array.isArray(layout.carousel) || !layout.carousel.length) {
    layout.carousel = [...BUILTIN_PAGE_IDS];
  }
}

function bounds(el) {
  if (el.type === 'heart') return { x: 0, y: 0, w: 128, h: 64 };
  if (el.type === 'gauge') {
    const r = el.r || 13;
    return { x: el.x - r, y: el.y - r, w: r * 2, h: r * 2 };
  }
  const d = layoutDims(el);
  return { x: el.x, y: el.y, w: d.w, h: d.h };
}

function hitTest(mx, my) {
  const els = currentPage().elements || [];
  for (let i = els.length - 1; i >= 0; i--) {
    const b = bounds(els[i]);
    if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) return i;
  }
  return -1;
}

function canvasXY(e) {
  const r = canvas.getBoundingClientRect();
  return {
    x: Math.round(((e.clientX - r.left) / r.width) * 128),
    y: Math.round(((e.clientY - r.top) / r.height) * 64),
  };
}

function makePageBtn(id, listEl) {
  const p = layout.pages[id];
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center' +
    (id === pageId ? ' active' : '');
  btn.innerHTML = `<span>${p.name || id}</span>${isBuiltin(id) ? '<span class="badge text-bg-secondary">built-in</span>' : ''}`;
  btn.onclick = () => {
    pageId = id;
    selIdx = -1;
    renderPageList();
    renderProps();
    requestRender(true);
  };
  listEl.appendChild(btn);
}

function renderPageList() {
  ensureLayout();
  const builtinEl = document.getElementById('page-list-builtin');
  const customEl = document.getElementById('page-list-custom');
  const legacyEl = document.getElementById('page-list');

  if (builtinEl && customEl) {
    builtinEl.innerHTML = '';
    customEl.innerHTML = '';
    BUILTIN_PAGE_IDS.forEach((id) => makePageBtn(id, builtinEl));
    Object.keys(layout.pages)
      .filter((id) => !BUILTIN_PAGE_IDS.includes(id))
      .sort()
      .forEach((id) => makePageBtn(id, customEl));
  } else if (legacyEl) {
    legacyEl.innerHTML = '';
    Object.keys(layout.pages).sort().forEach((id) => makePageBtn(id, legacyEl));
  }

  const carousel = document.getElementById('carousel');
  if (carousel) carousel.value = (layout.carousel || []).join(',');
}

function addCustomPage() {
  let n = 1;
  while (layout.pages[`custom_${n}`]) n++;
  const id = `custom_${n}`;
  layout.pages[id] = { id, name: `Custom ${n}`, duration: 5, builtin: false, elements: [] };
  if (!layout.carousel.includes(id)) layout.carousel.push(id);
  pageId = id;
  renderPageList();
  renderProps();
  requestRender(true);
  toast(`Added ${id}`);
}

async function resetCurrentPage() {
  if (!isBuiltin(pageId)) {
    toast('Only built-in pages can be reset', true);
    return;
  }
  try {
    const data = await api(`/reset-oled-page/${pageId}`);
    layout.pages[pageId] = data.page;
    selIdx = -1;
    renderPageList();
    renderProps();
    requestRender(true);
    toast(`Reset ${pageId}`);
  } catch (e) {
    toast(e.message, true);
  }
}

function renderProps() {
  const box = document.getElementById('props');
  if (selIdx < 0) {
    const p = currentPage();
    box.innerHTML = `
      <p class="small text-secondary">Page: <strong>${pageId}</strong>${isBuiltin(pageId) ? ' (built-in)' : ''}</p>
      <label class="form-label small">Name</label>
      <input type="text" class="form-control form-control-sm mb-2" id="p-name" value="${p.name || ''}"/>
      <label class="form-label small">Duration (s)</label>
      <input type="number" class="form-control form-control-sm" id="p-dur" min="2" max="120" value="${p.duration || 5}"/>`;
    document.getElementById('p-name').oninput = (e) => { p.name = e.target.value; renderPageList(); };
    document.getElementById('p-dur').onchange = (e) => { p.duration = Number(e.target.value); };
    return;
  }
  const el = currentPage().elements[selIdx];
  let html = `<p class="small mb-2"><span class="badge text-bg-primary">${el.type}</span></p>`;
  if (el.type !== 'heart') {
    html += row('X', `<input type="number" class="form-control form-control-sm" data-k="x" min="0" max="127" value="${el.x}"/>`);
    html += row('Y', `<input type="number" class="form-control form-control-sm" data-k="y" min="0" max="63" value="${el.y}"/>`);
  }
  if (el.type === 'text') {
    html += row('Text', `<input type="text" class="form-control form-control-sm" data-k="text" value="${el.text || ''}"/>`);
    html += row('Font (px)', `<input type="number" class="form-control form-control-sm" data-k="font" min="8" max="14" step="2" value="${fontPx(el)}"/>`);
    html += row('Width', `<input type="number" class="form-control form-control-sm" data-k="w" min="8" max="128" value="${el.w ?? layoutDims(el).w}"/>`);
    html += row('Height', `<input type="number" class="form-control form-control-sm" data-k="h" min="6" max="64" value="${el.h ?? layoutDims(el).h}"/>`);
    html += row('Align', `<select class="form-select form-select-sm" data-k="align"><option value="left">left</option><option value="center">center</option><option value="right">right</option></select>`);
  }
  if (el.type === 'metric') {
    html += row('Metric', `<select class="form-select form-select-sm" data-k="key">${(spec.metrics || []).map((k) =>
      `<option value="${k}"${k === el.key ? ' selected' : ''}>${k}</option>`).join('')}</select>`);
    html += row('Format', `<input type="text" class="form-control form-control-sm" data-k="format" value="${el.format || '{}'}"/>`);
    html += row('Font (px)', `<input type="number" class="form-control form-control-sm" data-k="font" min="8" max="14" step="2" value="${fontPx(el)}"/>`);
    html += row('Width', `<input type="number" class="form-control form-control-sm" data-k="w" min="8" max="128" value="${el.w ?? layoutDims(el).w}"/>`);
    html += row('Height', `<input type="number" class="form-control form-control-sm" data-k="h" min="6" max="64" value="${el.h ?? layoutDims(el).h}"/>`);
    html += row('Align', `<select class="form-select form-select-sm" data-k="align"><option value="left">left</option><option value="center">center</option><option value="right">right</option></select>`);
  }
  if (el.type === 'icon') {
    html += row('Pack', `<select class="form-select form-select-sm" data-k="pack"><option value="builtin">builtin</option><option value="bootstrap">bootstrap</option></select>`);
    html += row('Icon', `<input type="text" class="form-control form-control-sm" data-k="icon" value="${el.icon || ''}"/>`);
    html += row('Width', `<input type="number" class="form-control form-control-sm" data-k="w" min="8" max="64" value="${el.w ?? layoutDims(el).w}"/>`);
    html += row('Height', `<input type="number" class="form-control form-control-sm" data-k="h" min="8" max="64" value="${el.h ?? layoutDims(el).h}"/>`);
  }
  if (el.type === 'rect') {
    html += row('W', `<input type="number" class="form-control form-control-sm" data-k="w" value="${el.w}"/>`);
    html += row('H', `<input type="number" class="form-control form-control-sm" data-k="h" value="${el.h}"/>`);
    html += row('Fill', `<input type="checkbox" class="form-check-input" data-k="fill" ${el.fill ? 'checked' : ''}/>`);
  }
  if (el.type === 'bar') {
    html += row('Metric', `<select class="form-select form-select-sm" data-k="key">${(spec.metrics || []).map((k) =>
      `<option value="${k}"${k === el.key ? ' selected' : ''}>${k}</option>`).join('')}</select>`);
    html += row('W', `<input type="number" class="form-control form-control-sm" data-k="w" value="${el.w}"/>`);
    html += row('H', `<input type="number" class="form-control form-control-sm" data-k="h" value="${el.h}"/>`);
    html += row('Max', `<input type="number" class="form-control form-control-sm" data-k="max" value="${el.max || 100}"/>`);
  }
  if (el.type === 'gauge') {
    html += row('Metric', `<select class="form-select form-select-sm" data-k="key">${(spec.metrics || []).map((k) =>
      `<option value="${k}"${k === el.key ? ' selected' : ''}>${k}</option>`).join('')}</select>`);
    html += row('Radius', `<input type="number" class="form-control form-control-sm" data-k="r" min="4" max="24" value="${el.r || 13}"/>`);
    html += row('Start', `<input type="number" class="form-control form-control-sm" data-k="start" value="${el.start ?? 180}"/>`);
    html += row('End', `<input type="number" class="form-control form-control-sm" data-k="end" value="${el.end ?? 0}"/>`);
  }
  if (el.type === 'heart') {
    html += row('Margin', `<input type="number" class="form-control form-control-sm" data-k="margin" min="0" max="20" value="${el.margin ?? 7}"/>`);
  }
  box.innerHTML = html;
  box.querySelectorAll('[data-k]').forEach((inp) => {
    const k = inp.dataset.k;
    const handler = () => {
      let v = inp.type === 'checkbox' ? inp.checked : inp.value;
      if (['x', 'y', 'w', 'h', 'size', 'font', 'max', 'r', 'start', 'end', 'margin'].includes(k)) v = Number(v);
      if (k === 'font') {
        setElementFont(el, v);
      } else {
        el[k] = v;
      }
      if ((k === 'w' || k === 'h') && (el.type === 'text' || el.type === 'metric')) {
        setElementFont(el, fontFromBoxHeight(el.h));
      }
      requestRender();
      if (k === 'font' || k === 'w' || k === 'h') renderProps();
    };
    inp.addEventListener(inp.type === 'checkbox' ? 'change' : 'input', handler);
    if (k === 'align') inp.value = el.align || 'left';
    if (k === 'pack') inp.value = el.pack || 'builtin';
  });
}

function row(label, input) {
  return `<div class="mb-2"><label class="form-label small text-secondary mb-0">${label}</label>${input}</div>`;
}

function addElement(type) {
  const el = { type, x: 4, y: 4 };
  if (type === 'text') Object.assign(el, { text: 'Label', font: 8, size: 1, w: 80, h: 12 });
  if (type === 'metric') Object.assign(el, { key: 'cpu_temperature', format: '{}', font: 8, size: 1, w: 80, h: 12 });
  if (type === 'icon') Object.assign(el, { icon: 'cpu', pack: 'builtin', w: 14, h: 14 });
  if (type === 'rect') Object.assign(el, { w: 40, h: 20, fill: false });
  if (type === 'bar') Object.assign(el, { key: 'cpu_percent', w: 120, h: 8, max: 100 });
  if (type === 'gauge') Object.assign(el, { key: 'cpu_percent', r: 13, start: 180, end: 0 });
  if (type === 'heart') Object.assign(el, { margin: 7 });
  initNewElementBox(el);
  currentPage().elements.push(el);
  selIdx = currentPage().elements.length - 1;
  renderProps();
  requestRender(true);
}

function renderIconGrid() {
  const pack = document.getElementById('icon-pack').value;
  const q = document.getElementById('icon-search').value.toLowerCase();
  const grid = document.getElementById('icon-grid');
  grid.innerHTML = '';
  const list = pack === 'bootstrap' ? BOOTSTRAP_PICK : Object.keys(BUILTIN_BI);
  list.filter((id) => id.toLowerCase().includes(q)).forEach((id) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.title = id;
    btn.innerHTML = pack === 'bootstrap'
      ? `<i class="bi ${id}"></i>`
      : `<i class="bi ${BUILTIN_BI[id] || 'bi-square'}"></i>`;
    btn.onclick = () => {
      if (selIdx < 0 || currentPage().elements[selIdx].type !== 'icon') {
        toast('Select an icon element first', true);
        return;
      }
      const el = currentPage().elements[selIdx];
      el.pack = pack;
      el.icon = id;
      if (pack === 'bootstrap' && (el.w || 16) <= 16 && (el.h || 16) <= 16) {
        el.w = 16;
        el.h = 16;
      } else if (pack === 'builtin' && (el.w || 14) <= 16 && (el.h || 14) <= 16) {
        el.w = 14;
        el.h = 14;
      }
      renderProps();
      requestRender(true);
    };
    grid.appendChild(btn);
  });
}

if (canvas) canvas.addEventListener('mousedown', (e) => {
  const { x, y } = canvasXY(e);
  const rh = hitResizeHandle(x, y);
  if (rh !== null && selIdx >= 0) {
    const el = currentPage().elements[selIdx];
    const b = bounds(el);
    drag = {
      mode: 'resize',
      handle: rh,
      start: { x0: b.x, y0: b.y, x1: b.x + b.w, y1: b.y + b.h },
    };
    requestRender(true);
    return;
  }
  const hit = hitTest(x, y);
  if (hit >= 0) {
    selIdx = hit;
    const el = currentPage().elements[hit];
    if (el.type !== 'heart') {
      drag = { mode: 'move', ox: x - el.x, oy: y - el.y };
    }
    renderProps();
    requestRender(true);
  } else {
    selIdx = -1;
    renderProps();
    requestRender(true);
  }
});

if (canvas) canvas.addEventListener('mousemove', (e) => {
  const { x, y } = canvasXY(e);
  if (!drag || selIdx < 0) {
    const rh = hitResizeHandle(x, y);
    canvas.style.cursor = rh ? resizeCursor(rh) : 'crosshair';
    return;
  }
  const el = currentPage().elements[selIdx];
  if (drag.mode === 'resize') {
    applyResize(el, drag.handle, x, y, drag.start);
    renderProps();
    renderQuick();
    return;
  }
  el.x = clamp(Math.round(x - drag.ox), 0, 127);
  el.y = clamp(Math.round(y - drag.oy), 0, 63);
  renderQuick();
});

function endDrag() {
  const was = drag;
  drag = null;
  if (canvas) canvas.style.cursor = 'crosshair';
  if (was) requestRender(true);
}

if (canvas) canvas.addEventListener('mouseup', endDrag);
if (canvas) canvas.addEventListener('mouseleave', endDrag);

function wireUi() {
  document.querySelectorAll('[data-add]').forEach((btn) => {
    btn.addEventListener('click', () => addElement(btn.dataset.add));
  });

  onClick('btn-del-el', () => {
    if (selIdx < 0) return;
    currentPage().elements.splice(selIdx, 1);
    selIdx = -1;
    renderProps();
    requestRender(true);
  });

  onClick('btn-add-page', addCustomPage);
  onClick('btn-add-page-full', addCustomPage);
  onClick('btn-reset-page', () => { resetCurrentPage(); });
  onClick('btn-device-preview', () => { previewOnDevice(); });

  onClick('btn-test-oled', async () => {
    const btn = document.getElementById('btn-test-oled');
    if (btn?.disabled) return;
    const carouselEl = document.getElementById('carousel');
    const carousel = (carouselEl?.value || '')
      .split(',').map((s) => s.trim()).filter(Boolean);
    layout.carousel = carousel.length ? carousel : Object.keys(layout.pages);
    try {
      if (btn) btn.disabled = true;
      await api('/test-oled-page', 'POST', {
        page: pageId,
        layout,
        duration: 5,
      });
      toast(`OLED showing "${pageId}" for 5 seconds (live edits, not saved)`);
    } catch (e) {
      toast(e.message, true);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  onClick('btn-apply', async () => {
    const carouselEl = document.getElementById('carousel');
    const carousel = (carouselEl?.value || '')
      .split(',').map((s) => s.trim()).filter(Boolean);
    layout.carousel = carousel.length ? carousel : Object.keys(layout.pages);
    const status = document.getElementById('save-status');
    if (status) status.textContent = 'Saving…';
    try {
      await api('/apply-oled-layout', 'POST', { layout });
      if (status) status.textContent = 'Applied';
      toast('Layout applied — OLED will use designer pages');
    } catch (e) {
      if (status) status.textContent = '';
      toast(e.message, true);
    }
  });

  const iconPack = document.getElementById('icon-pack');
  const iconSearch = document.getElementById('icon-search');
  if (iconPack) iconPack.addEventListener('change', renderIconGrid);
  if (iconSearch) iconSearch.addEventListener('input', renderIconGrid);
}

function showInitError(msg) {
  const box = document.getElementById('props');
  if (box) {
    box.innerHTML = `<p class="text-danger small mb-0"><strong>Could not load designer.</strong><br>${msg}<br>Try: restart pironman5, upgrade pm_dashboard 1.5.6+, hard refresh (Ctrl+Shift+R).</p>`;
  }
  toast('Init failed: ' + msg, true);
}

async function init() {
  wireUi();
  try {
    spec = await api('/get-oled-spec');
    layout = JSON.parse(JSON.stringify(spec.layout || {}));
    ensureLayout();
    const badge = document.getElementById('spec-badge');
    if (badge) badge.textContent = `${spec.width}×${spec.height} · ${spec.aspect}`;
    pageId = (layout.carousel && layout.carousel[0]) || 'home';
    if (!layout.pages[pageId]) pageId = 'home';
    metrics = { ...STATIC_METRICS };
    stopLivePreview();
    renderPageList();
    renderIconGrid();
    renderProps();
    await requestRender(true);
  } catch (e) {
    showInitError(e.message);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
