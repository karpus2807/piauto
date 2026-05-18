const API = '/api/v1.0';

let schema = null;
let config = {};
let oledOptions = { disks: ['total'], interfaces: ['all'] };
let saveTimer = null;
let toastBs = null;

const LIVE_ICONS = {
  Host: 'bi-pc-display',
  Uptime: 'bi-clock-history',
  CPU: 'bi-thermometer-half',
  'CPU %': 'bi-cpu',
  RAM: 'bi-memory',
  Storage: 'bi-hdd',
  'Tower RPM': 'bi-fan',
  'Side fan': 'bi-wind',
};

async function api(path, method = 'GET', body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  let res;
  try {
    res = await fetch(API + path, opts);
  } catch (e) {
    throw new Error('Network error — use http://<pi-ip>:34001/control (not a file link)');
  }
  const text = await res.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch (_) {
    throw new Error(`Bad response (${res.status}): ${text.slice(0, 120)}`);
  }
  if (!json.status) throw new Error(json.error || 'Request failed');
  return json.data;
}

function toast(msg, err = false) {
  const el = document.getElementById('toast');
  const body = document.getElementById('toast-body');
  if (!el || !body) return;
  body.textContent = msg;
  el.classList.remove('text-bg-success', 'text-bg-danger');
  el.classList.add(err ? 'text-bg-danger' : 'text-bg-success');
  if (!toastBs) toastBs = bootstrap.Toast.getOrCreateInstance(el, { delay: 4000 });
  toastBs.show();
}

function setConn(state) {
  const el = document.getElementById('conn');
  if (!el) return;
  el.className = 'badge rounded-pill';
  if (state === 'ok') {
    el.textContent = 'Connected';
    el.classList.add('text-bg-success');
  } else if (state === 'err') {
    el.textContent = 'Offline';
    el.classList.add('text-bg-danger');
  } else {
    el.textContent = 'Connecting…';
    el.classList.add('text-bg-secondary');
  }
}

async function patchConfig(patch) {
  const status = document.getElementById('save-status');
  if (status) status.textContent = 'Saving…';
  try {
    await api('/set-system-config', 'POST', { system: patch });
    Object.assign(config, patch);
    if (status) status.textContent = 'Saved';
    toast('Updated');
  } catch (e) {
    if (status) status.textContent = '';
    toast(e.message, true);
  }
}

function schedulePatch(patch) {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => patchConfig(patch), 350);
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderLive(data) {
  const h = data.history || {};
  const d = data.dashboard || {};
  const sys = d.system || {};
  const stor = (d.storage || {}).combined || {};
  const items = [
    ['Host', sys.hostname || h.hostname || '—'],
    ['Uptime', sys.uptime || (h.uptime_seconds != null ? `${Math.floor(h.uptime_seconds / 3600)}h` : '—')],
    ['CPU', h.cpu_temperature != null ? `${Number(h.cpu_temperature).toFixed(1)}°C` : '—'],
    ['CPU %', h.cpu_percent != null ? `${Math.round(h.cpu_percent)}%` : '—'],
    ['RAM', h.memory_percent != null ? `${Math.round(h.memory_percent)}%` : '—'],
    ['Storage', stor.free_display || (h.storage_percent_free != null ? `${h.storage_percent_free}% free` : '—')],
    ['Tower RPM', h.pwm_fan_speed != null ? h.pwm_fan_speed : '—'],
    ['Side fan', h.gpio_fan_state != null ? (h.gpio_fan_state ? 'ON' : 'OFF') : '—'],
  ];
  const live = document.getElementById('live');
  if (!live) return;
  live.innerHTML = items
    .map(([label, value]) => {
      const icon = LIVE_ICONS[label] || 'bi-dot';
      return `
        <div class="col-6 col-md-4 col-lg-3">
          <div class="card border-secondary h-100 pm-stat-card shadow-sm">
            <div class="card-body py-3 d-flex align-items-start gap-2">
              <span class="pm-stat-icon rounded-2 d-flex align-items-center justify-content-center flex-shrink-0">
                <i class="bi ${icon}"></i>
              </span>
              <div class="min-w-0">
                <div class="text-secondary text-uppercase small lh-sm mb-1">${esc(label)}</div>
                <div class="fs-5 fw-semibold text-truncate">${esc(String(value))}</div>
              </div>
            </div>
          </div>
        </div>`;
    })
    .join('');
}

function renderPresets() {
  const box = document.getElementById('presets');
  if (!box) return;
  box.innerHTML = '';
  if (!schema?.presets?.length) {
    box.innerHTML = '<div class="col-12"><p class="text-secondary small mb-0">No presets loaded — check API connection.</p></div>';
    return;
  }
  schema.presets.forEach((p) => {
    const col = document.createElement('div');
    col.className = 'col-6 col-md-4 col-lg-3';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline-light w-100 h-100 text-start pm-preset py-3';
    btn.innerHTML = `
      <span class="d-block fw-semibold mb-1">${esc(p.label)}</span>
      <span class="d-block small text-secondary lh-sm">${esc(p.description)}</span>`;
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        await api('/apply-preset', 'POST', { preset: p.id });
        await loadAll();
        toast(`Preset: ${p.label}`);
      } catch (e) {
        toast(e.message, true);
      } finally {
        btn.disabled = false;
      }
    };
    col.appendChild(btn);
    box.appendChild(col);
  });
}

function makeToggle(key, value) {
  const wrap = document.createElement('div');
  wrap.className = 'form-check form-switch mb-0';
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.className = 'form-check-input';
  input.role = 'switch';
  input.checked = !!value;
  input.onchange = () => schedulePatch({ [key]: input.checked });
  wrap.appendChild(input);
  return wrap;
}

function makeRange(key, spec, value) {
  const wrap = document.createElement('div');
  wrap.className = 'd-flex align-items-center gap-3 flex-wrap';
  const input = document.createElement('input');
  input.type = 'range';
  input.className = 'form-range flex-grow-1 pm-range';
  input.min = spec.min;
  input.max = spec.max;
  input.value = value ?? spec.min;
  const out = document.createElement('span');
  out.className = 'badge text-bg-primary pm-range-val';
  out.textContent = input.value;
  input.oninput = () => {
    out.textContent = input.value;
    schedulePatch({ [key]: Number(input.value) });
  };
  wrap.appendChild(input);
  wrap.appendChild(out);
  return wrap;
}

function makeChips(key, choices, value, labels) {
  const box = document.createElement('div');
  box.className = 'btn-group flex-wrap pm-chips';
  box.setAttribute('role', 'group');
  choices.forEach((c, i) => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className =
      'btn btn-sm ' +
      (String(c) === String(value) ? 'btn-primary' : 'btn-outline-secondary');
    chip.textContent = labels ? labels[i] : String(c);
    chip.onclick = () => {
      box.querySelectorAll('button').forEach((x) => {
        x.classList.remove('btn-primary');
        x.classList.add('btn-outline-secondary');
      });
      chip.classList.remove('btn-outline-secondary');
      chip.classList.add('btn-primary');
      schedulePatch({ [key]: c });
    };
    box.appendChild(chip);
  });
  return box;
}

function makeFanModes(value) {
  const modes = schema.fan_modes || [];
  return makeChips(
    'gpio_fan_mode',
    modes.map((m) => m.value),
    value,
    modes.map((m) => m.label),
  );
}

function makeOledPages() {
  const box = document.createElement('div');
  box.className = 'row g-2 mt-1';
  const current = (config.oled_pages || '').split(',').filter(Boolean);
  (schema.oled_page_ids || []).forEach((id) => {
    const col = document.createElement('div');
    col.className = 'col-6 col-md-4 col-lg-3';
    const label = document.createElement('label');
    label.className = 'form-check pm-page-check border border-secondary rounded-3 px-3 py-2 mb-0 w-100';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'form-check-input';
    cb.checked = current.includes(id);
    cb.value = id;
    cb.onchange = () => {
      const selected = [...box.querySelectorAll('input:checked')].map((x) => x.value);
      patchConfig({ oled_pages: selected.join(','), oled_pages_profile: 'custom' });
    };
    const span = document.createElement('span');
    span.className = 'form-check-label small';
    span.textContent = id;
    label.appendChild(cb);
    label.appendChild(span);
    col.appendChild(label);
    box.appendChild(col);
  });
  return box;
}

function renderField(field) {
  const row = document.createElement('div');
  row.className = 'row align-items-center py-3 border-bottom border-secondary-subtle pm-field';

  const labelCol = document.createElement('div');
  labelCol.className = 'col-12 col-md-5 mb-2 mb-md-0';
  const label = document.createElement('label');
  label.className = 'form-label fw-medium mb-0';
  label.textContent = field.label;
  labelCol.appendChild(label);

  const ctrlCol = document.createElement('div');
  ctrlCol.className = 'col-12 col-md-7';

  const key = field.key;
  const val = config[key];
  const spec = field;

  if (key === 'gpio_fan_mode') {
    ctrlCol.appendChild(makeFanModes(val));
  } else if (key === 'oled_pages_profile') {
    ctrlCol.appendChild(makeChips(key, schema.oled_profiles, val));
  } else if (key === 'oled_pages') {
    row.className = 'py-3 border-bottom border-secondary-subtle pm-field';
    row.appendChild(labelCol);
    const full = document.createElement('div');
    full.className = 'col-12';
    full.appendChild(makeOledPages());
    row.appendChild(full);
    return row;
  } else if (key === 'oled_disk') {
    ctrlCol.appendChild(makeChips(key, oledOptions.disks, val));
  } else if (key === 'oled_network_interface') {
    ctrlCol.appendChild(makeChips(key, oledOptions.interfaces, val));
  } else if (spec.type === 'bool') {
    ctrlCol.appendChild(makeToggle(key, !!val));
  } else if (spec.type === 'int' || spec.type === 'float') {
    ctrlCol.appendChild(makeRange(key, spec, val));
  } else if (spec.type === 'color') {
    const inp = document.createElement('input');
    inp.type = 'color';
    inp.className = 'form-control form-control-color pm-color';
    inp.value = val || '#0a1aff';
    inp.onchange = () => patchConfig({ [key]: inp.value });
    ctrlCol.appendChild(inp);
  } else if (spec.type === 'choice') {
    ctrlCol.appendChild(makeChips(key, spec.choices, val));
  } else {
    const span = document.createElement('span');
    span.className = 'text-secondary';
    span.textContent = String(val ?? '—');
    ctrlCol.appendChild(span);
  }

  row.appendChild(labelCol);
  row.appendChild(ctrlCol);
  return row;
}

function renderTabs() {
  const tabsEl = document.getElementById('tabs');
  const panelsEl = document.getElementById('panels');
  if (!tabsEl || !panelsEl) return;
  tabsEl.innerHTML = '';
  panelsEl.innerHTML = '';

  const sections = (schema.sections || []).filter((s) => s.fields?.length);
  if (!sections.length) {
    panelsEl.innerHTML =
      '<p class="text-secondary small mb-0">No controls for this device — check pironman5 config.</p>';
    return;
  }

  sections.forEach((sec, i) => {
    const paneId = `panel-${i}`;
    const li = document.createElement('li');
    li.className = 'nav-item';
    li.setAttribute('role', 'presentation');
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.className = 'nav-link' + (i === 0 ? ' active' : '');
    tab.id = `tab-${i}`;
    tab.setAttribute('data-bs-toggle', 'pill');
    tab.setAttribute('data-bs-target', `#${paneId}`);
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-controls', paneId);
    tab.setAttribute('aria-selected', i === 0 ? 'true' : 'false');
    tab.textContent = sec.label;
    li.appendChild(tab);
    tabsEl.appendChild(li);

    const panel = document.createElement('div');
    panel.className = 'tab-pane fade' + (i === 0 ? ' show active' : '');
    panel.id = paneId;
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-labelledby', `tab-${i}`);
    sec.fields.forEach((f) => panel.appendChild(renderField(f)));
    panelsEl.appendChild(panel);
  });
}

async function loadAll() {
  schema = await api('/get-control-schema');
  config = { ...(schema.config || {}) };
  try {
    oledOptions = await api('/get-oled-options');
  } catch (_) {
    oledOptions = { disks: ['total'], interfaces: ['all'] };
  }
  renderPresets();
  renderTabs();
  try {
    const live = await api('/get-live-status');
    renderLive(live);
  } catch (_) {
    const live = document.getElementById('live');
    if (live) {
      live.innerHTML =
        '<div class="col-12"><p class="text-secondary small mb-0">Live stats unavailable</p></div>';
    }
  }
}

async function init() {
  setConn('wait');
  try {
    await api('/test');
  } catch (e) {
    setConn('err');
    toast(e.message, true);
    return;
  }
  setConn('ok');
  try {
    await loadAll();
  } catch (e) {
    toast('Load failed: ' + e.message, true);
  }
  setInterval(async () => {
    try {
      const live = await api('/get-live-status');
      renderLive(live);
    } catch (_) {
      /* ignore */
    }
  }, 3000);
}

init();
