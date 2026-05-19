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

const canvas = document.getElementById('oled');
const ctx = canvas.getContext('2d');

async function api(path, method = 'GET', body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  const json = await res.json();
  if (!json.status) throw new Error(json.error || 'Request failed');
  return json.data;
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

function render() {
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, 128, 64);
  ctx.fillStyle = '#fff';
  ctx.strokeStyle = '#fff';

  const els = currentPage().elements || [];
  els.forEach((el, i) => {
    const selected = i === selIdx;
    if (el.type === 'text') {
      ctx.font = el.size === 2 ? 'bold 12px monospace' : '10px monospace';
      ctx.fillText(el.text || '', el.x, el.y + (el.size === 2 ? 12 : 10));
    } else if (el.type === 'metric') {
      ctx.font = el.size === 2 ? 'bold 12px monospace' : '10px monospace';
      const t = formatMetric(el);
      if (el.key === 'ip_line') {
        ctx.fillStyle = '#000';
        ctx.fillText(t, el.x, el.y + 8);
        ctx.fillStyle = '#fff';
      } else {
        ctx.fillText(t, el.x, el.y + (el.size === 2 ? 12 : 10));
      }
    } else if (el.type === 'icon') {
      ctx.strokeStyle = '#888';
      ctx.strokeRect(el.x, el.y, el.w || 16, el.h || 16);
      ctx.font = '8px monospace';
      ctx.fillStyle = '#aaa';
      ctx.fillText((el.icon || 'ic').slice(0, 4), el.x + 2, el.y + 8);
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
    } else if (el.type === 'heart') {
      drawHeartFull();
    }
    if (selected) {
      ctx.strokeStyle = '#3d8bfd';
      const b = bounds(el);
      ctx.strokeRect(b.x - 1, b.y - 1, b.w + 2, b.h + 2);
      ctx.strokeStyle = '#fff';
    }
  });
}

function bounds(el) {
  if (el.type === 'bar') return { x: el.x, y: el.y, w: el.w, h: el.h };
  if (el.type === 'rect') return { x: el.x, y: el.y, w: el.w, h: el.h };
  if (el.type === 'icon') return { x: el.x, y: el.y, w: el.w || 16, h: el.h || 16 };
  if (el.type === 'gauge') {
    const r = el.r || 13;
    return { x: el.x - r, y: el.y - r, w: r * 2, h: r * 2 };
  }
  if (el.type === 'heart') return { x: 0, y: 0, w: 128, h: 64 };
  const w = el.w || 80;
  const h = el.size === 2 ? 14 : 12;
  return { x: el.x, y: el.y, w, h };
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
    render();
  };
  listEl.appendChild(btn);
}

function renderPageList() {
  const builtinEl = document.getElementById('page-list-builtin');
  const customEl = document.getElementById('page-list-custom');
  const legacyEl = document.getElementById('page-list');
  if (legacyEl) legacyEl.innerHTML = '';
  if (!builtinEl) return;
  builtinEl.innerHTML = '';
  customEl.innerHTML = '';
  BUILTIN_PAGE_IDS.forEach((id) => {
    if (layout.pages[id]) makePageBtn(id, builtinEl);
  });
  Object.keys(layout.pages)
    .filter((id) => !BUILTIN_PAGE_IDS.includes(id))
    .sort()
    .forEach((id) => makePageBtn(id, customEl));
  document.getElementById('carousel').value = (layout.carousel || []).join(',');
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
  render();
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
    render();
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
    html += row('Size', `<select class="form-select form-select-sm" data-k="size"><option value="1">Small</option><option value="2">Large</option></select>`);
  }
  if (el.type === 'metric') {
    html += row('Metric', `<select class="form-select form-select-sm" data-k="key">${(spec.metrics || []).map((k) =>
      `<option value="${k}"${k === el.key ? ' selected' : ''}>${k}</option>`).join('')}</select>`);
    html += row('Format', `<input type="text" class="form-control form-control-sm" data-k="format" value="${el.format || '{}'}"/>`);
    html += row('Size', `<select class="form-select form-select-sm" data-k="size"><option value="1">Small</option><option value="2">Large</option></select>`);
  }
  if (el.type === 'icon') {
    html += row('Pack', `<select class="form-select form-select-sm" data-k="pack"><option value="builtin">builtin</option><option value="bootstrap">bootstrap</option></select>`);
    html += row('Icon', `<input type="text" class="form-control form-control-sm" data-k="icon" value="${el.icon || ''}"/>`);
    html += row('W', `<input type="number" class="form-control form-control-sm" data-k="w" min="8" max="32" value="${el.w || 16}"/>`);
    html += row('H', `<input type="number" class="form-control form-control-sm" data-k="h" min="8" max="32" value="${el.h || 16}"/>`);
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
      if (['x', 'y', 'w', 'h', 'size', 'max', 'r', 'start', 'end', 'margin'].includes(k)) v = Number(v);
      el[k] = v;
      render();
    };
    inp.addEventListener(inp.type === 'checkbox' ? 'change' : 'input', handler);
    if (k === 'size' && el.size) inp.value = String(el.size);
    if (k === 'pack') inp.value = el.pack || 'builtin';
  });
}

function row(label, input) {
  return `<div class="mb-2"><label class="form-label small text-secondary mb-0">${label}</label>${input}</div>`;
}

function addElement(type) {
  const el = { type, x: 4, y: 4 };
  if (type === 'text') Object.assign(el, { text: 'Label', size: 1, w: 80 });
  if (type === 'metric') Object.assign(el, { key: 'cpu_temperature', format: '{}', size: 1, w: 80 });
  if (type === 'icon') Object.assign(el, { icon: 'cpu', pack: 'builtin', w: 16, h: 16 });
  if (type === 'rect') Object.assign(el, { w: 40, h: 20, fill: false });
  if (type === 'bar') Object.assign(el, { key: 'cpu_percent', w: 120, h: 8, max: 100 });
  if (type === 'gauge') Object.assign(el, { key: 'cpu_percent', r: 13, start: 180, end: 0 });
  if (type === 'heart') Object.assign(el, { margin: 7 });
  currentPage().elements.push(el);
  selIdx = currentPage().elements.length - 1;
  renderProps();
  render();
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
      renderProps();
      render();
    };
    grid.appendChild(btn);
  });
}

canvas.addEventListener('mousedown', (e) => {
  const { x, y } = canvasXY(e);
  const hit = hitTest(x, y);
  if (hit >= 0) {
    selIdx = hit;
    const el = currentPage().elements[hit];
    if (el.type !== 'heart') {
      drag = { ox: x - el.x, oy: y - el.y };
    }
    renderProps();
    render();
  } else {
    selIdx = -1;
    renderProps();
    render();
  }
});

canvas.addEventListener('mousemove', (e) => {
  if (!drag || selIdx < 0) return;
  const { x, y } = canvasXY(e);
  const el = currentPage().elements[selIdx];
  el.x = Math.max(0, Math.min(127, x - drag.ox));
  el.y = Math.max(0, Math.min(63, y - drag.oy));
  render();
});

canvas.addEventListener('mouseup', () => { drag = null; });
canvas.addEventListener('mouseleave', () => { drag = null; });

document.querySelectorAll('[data-add]').forEach((btn) => {
  btn.onclick = () => addElement(btn.dataset.add);
});

document.getElementById('btn-del-el').onclick = () => {
  if (selIdx < 0) return;
  currentPage().elements.splice(selIdx, 1);
  selIdx = -1;
  renderProps();
  render();
};

document.getElementById('btn-add-page').onclick = addCustomPage;
document.getElementById('btn-add-page-full').onclick = addCustomPage;
document.getElementById('btn-reset-page').onclick = resetCurrentPage;

document.getElementById('btn-apply').onclick = async () => {
  const carousel = document.getElementById('carousel').value
    .split(',').map((s) => s.trim()).filter(Boolean);
  layout.carousel = carousel.length ? carousel : Object.keys(layout.pages);
  document.getElementById('save-status').textContent = 'Saving…';
  try {
    await api('/apply-oled-layout', 'POST', { layout });
    document.getElementById('save-status').textContent = 'Applied';
    toast('Layout applied — OLED will use designer pages');
  } catch (e) {
    document.getElementById('save-status').textContent = '';
    toast(e.message, true);
  }
};

document.getElementById('icon-pack').onchange = renderIconGrid;
document.getElementById('icon-search').oninput = renderIconGrid;

async function init() {
  try {
    spec = await api('/get-oled-spec');
    layout = JSON.parse(JSON.stringify(spec.layout));
    document.getElementById('spec-badge').textContent =
      `${spec.width}×${spec.height} · ${spec.aspect}`;
    pageId = (layout.carousel && layout.carousel[0]) || 'home';
    renderPageList();
    renderIconGrid();
    renderProps();
    render();
    const poll = async () => {
      try {
        metrics = await api('/get-oled-metrics');
        render();
      } catch (_) { /* ignore */ }
    };
    poll();
    setInterval(poll, 3000);
  } catch (e) {
    toast('Init failed: ' + e.message, true);
  }
}

init();
