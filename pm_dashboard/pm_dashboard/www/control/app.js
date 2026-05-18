const API = '/api/v1.0';

let schema = null;
let config = {};
let oledOptions = { disks: ['total'], interfaces: ['all'] };
let saveTimer = null;

async function api(path, method = 'GET', body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  const json = await res.json();
  if (!json.status) throw new Error(json.error || 'Request failed');
  return json.data;
}

function toast(msg, err = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.toggle('err', err);
  el.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add('hidden'), 2800);
}

function setConn(ok) {
  const el = document.getElementById('conn');
  el.textContent = ok ? 'Connected' : 'Offline';
  el.className = 'pill ' + (ok ? 'ok' : 'err');
}

async function patchConfig(patch) {
  document.getElementById('save-status').textContent = 'Saving…';
  try {
    await api('/set-system-config', 'POST', { system: patch });
    Object.assign(config, patch);
    document.getElementById('save-status').textContent = 'Saved';
    toast('Updated');
  } catch (e) {
    document.getElementById('save-status').textContent = '';
    toast(e.message, true);
  }
}

function schedulePatch(patch) {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => patchConfig(patch), 350);
}

function renderLive(data) {
  const h = data.history || {};
  const d = data.dashboard || {};
  const sys = d.system || {};
  const stor = (d.storage || {}).combined || {};
  const items = [
    ['Host', sys.hostname || h.hostname || '—'],
    ['Uptime', sys.uptime || h.uptime || '—'],
    ['CPU', h.cpu_temperature != null ? `${h.cpu_temperature.toFixed(1)}°C` : '—'],
    ['CPU %', h.cpu_percent != null ? `${Math.round(h.cpu_percent)}%` : '—'],
    ['RAM', h.memory_percent != null ? `${Math.round(h.memory_percent)}%` : '—'],
    ['Storage', stor.free_display || h.storage_free_display || '—'],
    ['Tower RPM', h.pwm_fan_speed != null ? h.pwm_fan_speed : '—'],
    ['Side fan', h.gpio_fan_state != null ? (h.gpio_fan_state ? 'ON' : 'OFF') : '—'],
  ];
  document.getElementById('live').innerHTML = items
    .map(([label, value]) => `<div class="stat"><div class="label">${label}</div><div class="value">${value}</div></div>`)
    .join('');
}

function renderPresets() {
  const box = document.getElementById('presets');
  box.innerHTML = '';
  (schema.presets || []).forEach((p) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'preset';
    btn.innerHTML = `<strong>${p.label}</strong><span>${p.description}</span>`;
    btn.onclick = async () => {
      try {
        await api('/apply-preset', 'POST', { preset: p.id });
        await loadAll();
        toast(`Preset: ${p.label}`);
      } catch (e) {
        toast(e.message, true);
      }
    };
    box.appendChild(btn);
  });
}

function makeToggle(key, value) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'toggle' + (value ? ' on' : '');
  btn.onclick = () => {
    const next = !btn.classList.contains('on');
    btn.classList.toggle('on', next);
    schedulePatch({ [key]: next });
  };
  return btn;
}

function makeRange(key, spec, value) {
  const wrap = document.createElement('div');
  const input = document.createElement('input');
  input.type = 'range';
  input.min = spec.min;
  input.max = spec.max;
  input.value = value ?? spec.min;
  const out = document.createElement('span');
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
  box.className = 'chips';
  choices.forEach((c, i) => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip' + (String(c) === String(value) ? ' active' : '');
    chip.textContent = labels ? labels[i] : String(c);
    chip.onclick = () => {
      box.querySelectorAll('.chip').forEach((x) => x.classList.remove('active'));
      chip.classList.add('active');
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
  box.className = 'page-checks';
  const current = (config.oled_pages || '').split(',').filter(Boolean);
  (schema.oled_page_ids || []).forEach((id) => {
    const label = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = current.includes(id);
    cb.onchange = () => {
      const selected = [...box.querySelectorAll('input:checked')].map((x) => x.value);
      patchConfig({ oled_pages: selected.join(','), oled_pages_profile: 'custom' });
    };
    cb.value = id;
    label.appendChild(cb);
    label.appendChild(document.createTextNode(id));
    box.appendChild(label);
  });
  return box;
}

function renderField(field) {
  const row = document.createElement('div');
  row.className = 'field';
  const label = document.createElement('label');
  label.textContent = field.label;
  row.appendChild(label);

  const key = field.key;
  const val = config[key];
  const spec = field;

  if (key === 'gpio_fan_mode') {
    row.appendChild(makeFanModes(val));
  } else if (key === 'oled_pages_profile') {
    row.appendChild(makeChips(key, schema.oled_profiles, val));
  } else if (key === 'oled_pages') {
    row.appendChild(makeOledPages());
    return row;
  } else if (key === 'oled_disk') {
    row.appendChild(makeChips(key, oledOptions.disks, val));
  } else if (key === 'oled_network_interface') {
    row.appendChild(makeChips(key, oledOptions.interfaces, val));
  } else if (spec.type === 'bool') {
    row.appendChild(makeToggle(key, !!val));
  } else if (spec.type === 'int' || spec.type === 'float') {
    row.appendChild(makeRange(key, spec, val));
  } else if (spec.type === 'color') {
    const inp = document.createElement('input');
    inp.type = 'color';
    inp.value = val || '#0a1aff';
    inp.onchange = () => patchConfig({ [key]: inp.value });
    row.appendChild(inp);
  } else if (spec.type === 'choice') {
    row.appendChild(makeChips(key, spec.choices, val));
  } else {
    const span = document.createElement('span');
    span.textContent = String(val ?? '—');
    row.appendChild(span);
  }
  return row;
}

function renderTabs() {
  const tabsEl = document.getElementById('tabs');
  const panelsEl = document.getElementById('panels');
  tabsEl.innerHTML = '';
  panelsEl.innerHTML = '';

  const sections = (schema.sections || []).filter((s) => s.fields && s.fields.length);
  sections.forEach((sec, i) => {
    const tab = document.createElement('button');
    tab.type = 'button';
    tab.className = 'tab' + (i === 0 ? ' active' : '');
    tab.textContent = sec.label;
    tab.onclick = () => {
      tabsEl.querySelectorAll('.tab').forEach((t, j) => {
        t.classList.toggle('active', j === i);
      });
      panelsEl.querySelectorAll('.panel').forEach((p, j) => {
        p.classList.toggle('active', j === i);
      });
    };
    tabsEl.appendChild(tab);

    const panel = document.createElement('section');
    panel.className = 'panel card' + (i === 0 ? ' active' : '');
    sec.fields.forEach((f) => panel.appendChild(renderField(f)));
    panelsEl.appendChild(panel);
  });
}

async function loadAll() {
  schema = await api('/get-control-schema');
  config = { ...schema.config };
  try {
    oledOptions = await api('/get-oled-options');
  } catch (_) { /* optional */ }
  renderPresets();
  renderTabs();
  const live = await api('/get-live-status');
  renderLive(live);
}

async function init() {
  try {
    await api('/test');
    setConn(true);
    await loadAll();
    setInterval(async () => {
      try {
        const live = await api('/get-live-status');
        renderLive(live);
      } catch (_) { /* ignore poll errors */ }
    }, 3000);
  } catch (e) {
    setConn(false);
    toast(e.message, true);
  }
}

init();
