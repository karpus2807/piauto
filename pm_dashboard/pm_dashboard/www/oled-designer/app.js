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
  'bi-arrow-up', 'bi-arrow-down', 'bi-droplet', 'bi-moon-stars-fill',
];

let spec = null;
let layout = null;
let metrics = {};
let pageId = 'custom_1';
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

function metricValue(key) {
  const v = metrics[key];
  if (v == null) return '—';
  if (key === 'gpio_fan_state') return v ? 'ON' : 'OFF';
  if (key === 'uptime_seconds') return `${Math.floor(v / 3600)}h`;
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(1);
  return String(v);
}

function formatMetric(el) {
  const v = metrics[el.key];
  if (v == null) return '—';
  try {
    const fmt = el.format || '{}';
    if (fmt.includes('{')) return fmt.replace(/\{[^}]+\}/, String(v));
    return `${v}${fmt}`;
  } catch (_) {
    return metricValue(el.key);
  }
}

function drawBuiltinIcon(name, x, y, w, h) {
  const bi = BUILTIN_BI[name] || 'bi-square';
  ctx.save();
  ctx.fillStyle = '#fff';
  ctx.font = `${Math.min(w, h)}px bootstrap-icons`;
  ctx.textBaseline = 'top';
  ctx.fillText('\uF4CA', x, y);
  ctx.restore();
  ctx.strokeStyle = '#666';
  ctx.strokeRect(x, y, w, h);
}

function render() {
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, 128, 64);
  ctx.fillStyle = '#fff';
  ctx.strokeStyle = '#fff';

  const els = currentPage().elements;
  els.forEach((el, i) => {
    const selected = i === selIdx;
    if (el.type === 'text') {
      ctx.font = el.size === 2 ? 'bold 12px monospace' : '10px monospace';
      ctx.fillText(el.text || '', el.x, el.y + (el.size === 2 ? 12 : 10));
    } else if (el.type === 'metric') {
      ctx.font = el.size === 2 ? 'bold 12px monospace' : '10px monospace';
      ctx.fillText(formatMetric(el), el.x, el.y + (el.size === 2 ? 12 : 10));
    } else if (el.type === 'icon') {
      if (el.pack === 'bootstrap') {
        ctx.strokeStyle = '#888';
        ctx.strokeRect(el.x, el.y, el.w || 16, el.h || 16);
        ctx.font = '8px monospace';
        ctx.fillStyle = '#aaa';
        ctx.fillText((el.icon || '').replace('bi-', '').slice(0, 4), el.x, el.y + 6);
        ctx.fillStyle = '#fff';
      } else {
        drawBuiltinIcon(el.icon, el.x, el.y, el.w || 16, el.h || 16);
      }
    } else if (el.type === 'rect') {
      if (el.fill) ctx.fillRect(el.x, el.y, el.w, el.h);
      else ctx.strokeRect(el.x, el.y, el.w, el.h);
    } else if (el.type === 'bar') {
      const pct = Math.min(100, Math.max(0, Number(metrics[el.key]) || 0));
      const fill = (el.w * pct) / (el.max || 100);
      ctx.strokeRect(el.x, el.y, el.w, el.h);
      ctx.fillRect(el.x + 1, el.y + 1, Math.max(0, fill - 2), el.h - 2);
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
  const w = el.w || 80;
  const h = el.size === 2 ? 14 : 12;
  return { x: el.x, y: el.y, w, h };
}

function hitTest(mx, my) {
  const els = currentPage().elements;
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

function renderPageList() {
  const ul = document.getElementById('page-list');
  ul.innerHTML = '';
  Object.keys(layout.pages).forEach((id) => {
    const li = document.createElement('button');
    li.type = 'button';
    li.className = 'list-group-item list-group-item-action' + (id === pageId ? ' active' : '');
    li.textContent = layout.pages[id].name || id;
    li.onclick = () => {
      pageId = id;
      selIdx = -1;
      renderPageList();
      renderProps();
      render();
    };
    ul.appendChild(li);
  });
  document.getElementById('carousel').value = (layout.carousel || []).join(',');
}

function renderProps() {
  const box = document.getElementById('props');
  if (selIdx < 0) {
    const p = currentPage();
    box.innerHTML = `
      <p class="small text-secondary">Page settings</p>
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
  html += row('X', `<input type="number" class="form-control form-control-sm" data-k="x" min="0" max="127" value="${el.x}"/>`);
  html += row('Y', `<input type="number" class="form-control form-control-sm" data-k="y" min="0" max="63" value="${el.y}"/>`);
  if (el.type === 'text') {
    html += row('Text', `<input type="text" class="form-control form-control-sm" data-k="text" value="${el.text || ''}"/>`);
    html += row('Size', `<select class="form-select form-select-sm" data-k="size"><option value="1">Small</option><option value="2">Large</option></select>`);
  }
  if (el.type === 'metric') {
    html += row('Metric', `<select class="form-select form-select-sm" data-k="key">${(spec.metrics || []).map((k) =>
      `<option value="${k}"${k === el.key ? ' selected' : ''}>${k}</option>`).join('')}</select>`);
    html += row('Format', `<input type="text" class="form-control form-control-sm" data-k="format" value="${el.format || '{:.1f}'}"/>`);
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
  box.innerHTML = html;
  box.querySelectorAll('[data-k]').forEach((inp) => {
    const k = inp.dataset.k;
    const handler = () => {
      let v = inp.type === 'checkbox' ? inp.checked : inp.value;
      if (['x', 'y', 'w', 'h', 'size', 'max'].includes(k)) v = Number(v);
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
  if (type === 'metric') Object.assign(el, { key: 'cpu_temperature', format: '{:.1f} C', size: 2, w: 80 });
  if (type === 'icon') Object.assign(el, { icon: 'cpu', pack: 'builtin', w: 16, h: 16 });
  if (type === 'rect') Object.assign(el, { w: 40, h: 20, fill: false });
  if (type === 'bar') Object.assign(el, { key: 'cpu_percent', w: 120, h: 8, max: 100 });
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
    if (pack === 'bootstrap') {
      btn.innerHTML = `<i class="bi ${id}"></i>`;
    } else {
      btn.innerHTML = `<i class="bi ${BUILTIN_BI[id] || 'bi-square'}"></i>`;
    }
    btn.onclick = () => {
      if (selIdx < 0 || currentPage().elements[selIdx].type !== 'icon') {
        toast('Select an icon element first', true);
        return;
      }
      const el = currentPage().elements[selIdx];
      el.pack = pack;
      el.icon = pack === 'bootstrap' ? id : id;
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
    drag = { ox: x - currentPage().elements[hit].x, oy: y - currentPage().elements[hit].y };
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

document.getElementById('btn-add-page').onclick = () => {
  let n = 1;
  while (layout.pages[`custom_${n}`]) n++;
  const id = `custom_${n}`;
  layout.pages[id] = { id, name: `Custom ${n}`, duration: 5, elements: [] };
  pageId = id;
  renderPageList();
  render();
};

document.getElementById('btn-apply').onclick = async () => {
  const carousel = document.getElementById('carousel').value
    .split(',').map((s) => s.trim()).filter(Boolean);
  layout.carousel = carousel.length ? carousel : ['home', pageId, 'heart'];
  document.getElementById('save-status').textContent = 'Saving…';
  try {
    await api('/apply-oled-layout', 'POST', { layout });
    document.getElementById('save-status').textContent = 'Applied';
    toast('Layout saved to device config');
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
    pageId = Object.keys(layout.pages)[0] || 'custom_1';
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
