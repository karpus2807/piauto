(function () {
  const API = '/api/v1.0';
  const state = {
    data: null,
    editorId: '',
    pollTimer: null,
    modal: null,
  };

  const $ = (id) => document.getElementById(id);

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function fmt(value, unit) {
    if (value == null || value === '' || Number.isNaN(value)) return '—';
    const n = typeof value === 'number' ? value : Number(value);
    if (Number.isNaN(n)) return String(value);
    const shown = Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1);
    return unit ? `${shown} ${unit}` : shown;
  }

  async function api(path, opts) {
    const res = await fetch(`${API}${path}`, opts);
    const json = await res.json();
    if (!json.status && json.error) throw new Error(json.error);
    return json;
  }

  function liveTiles(live, extra) {
    const peak = extra && extra.peak_rpm;
    const rows = [
      ['CPU load', fmt(live.cpu_load, '%')],
      ['GPU load', live.gpu_load == null ? 'N/A' : fmt(live.gpu_load, '%')],
      ['GPU temp', fmt(live.gpu_temp, '°C')],
      ['CPU temp', fmt(live.cpu_temp, '°C')],
      ['Fan RPM', fmt(live.fan_rpm, 'RPM')],
      ['Max speed', fmt(live.max_speed, 'RPM')],
      ['Heat gen', fmt(live.heat_generation, '°C/s')],
      ['Heat dissip.', fmt(live.heat_dissipation, '°C/s')],
    ];
    if (peak != null) rows.push(['Peak RPM', fmt(peak, 'RPM')]);
    $('live-tiles').innerHTML = rows.map(([k, v]) => `
      <div class="col-6 col-md-3">
        <div class="live-tile"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>
      </div>`).join('');
  }

  function benchSummary(bench) {
    if (!bench) return '<p class="text-secondary small mb-0">No benchmark yet.</p>';
    return `<div class="bench-line">Score <strong>${esc(bench.score)}</strong>
      · peak ${esc(fmt(bench.peak_cpu_temp, '°C'))}
      · avg ${esc(fmt(bench.avg_rpm, 'RPM'))}
      · gen ${esc(fmt(bench.heat_generation, '°C/s'))}
      · dissip ${esc(fmt(bench.heat_dissipation, '°C/s'))}</div>`;
  }

  function stepChips(steps) {
    return (steps || []).map((s) =>
      `<span class="step-chip">${esc(s.name)} ≤${esc(s.until_c)}° ${esc(s.percent)}%</span>`
    ).join('');
  }

  function profileCard(profile, kind) {
    const pwm = state.data.pwm;
    const active = pwm.active === profile.id;
    const bench = (pwm.benchmarks || {})[profile.id];
    return `
      <div class="col-12 col-md-6">
        <article class="profile-card p-3 ${active ? 'active' : ''}" data-id="${esc(profile.id)}">
          <div class="d-flex justify-content-between align-items-start gap-2">
            <div>
              <h3 class="h6 mb-1">${esc(profile.name)}</h3>
              <p class="small text-secondary mb-2">${esc(profile.summary || 'Custom temperature curve')}</p>
            </div>
            ${active ? '<span class="badge text-bg-primary">active</span>' : ''}
          </div>
          <div class="mb-2">${stepChips(profile.steps)}</div>
          ${benchSummary(bench)}
          <div class="d-flex flex-wrap gap-2 mt-3">
            <button type="button" class="btn btn-sm btn-success btn-apply" data-id="${esc(profile.id)}">Apply</button>
            <button type="button" class="btn btn-sm btn-outline-warning btn-bench" data-id="${esc(profile.id)}">
              <i class="bi bi-activity"></i> Benchmark
            </button>
            ${kind === 'custom' ? `<button type="button" class="btn btn-sm btn-outline-light btn-edit" data-id="${esc(profile.id)}">Edit</button>
            <button type="button" class="btn btn-sm btn-outline-danger btn-del" data-id="${esc(profile.id)}">Delete</button>` : ''}
          </div>
        </article>
      </div>`;
  }

  function rgbCard(style, active) {
    return `
      <div class="col-12 col-md-6">
        <article class="profile-card rgb-card p-3 ${active ? 'active' : ''}">
          <div class="d-flex justify-content-between">
            <h3 class="h6 mb-1">${esc(style.name)}</h3>
            ${active ? '<span class="badge text-bg-info">on</span>' : ''}
          </div>
          <p class="small text-secondary mb-3">${esc(style.summary)}</p>
          <button type="button" class="btn btn-sm btn-outline-info btn-rgb" data-id="${esc(style.id)}">Enable profile</button>
        </article>
      </div>`;
  }

  function renderSteps(steps) {
    $('step-rows').innerHTML = (steps || []).map((s, i) => `
      <tr>
        <td><input class="form-control form-control-sm step-name" data-i="${i}" value="${esc(s.name)}"/></td>
        <td><input type="number" min="0" max="200" class="form-control form-control-sm step-until" data-i="${i}" value="${esc(s.until_c)}"/></td>
        <td><input type="number" min="0" max="100" class="form-control form-control-sm step-pct" data-i="${i}" value="${esc(s.percent)}"/></td>
        <td><button type="button" class="btn btn-sm btn-outline-danger btn-del-step" data-i="${i}">×</button></td>
      </tr>`).join('');
  }

  function readSteps() {
    const names = [...document.querySelectorAll('.step-name')];
    return names.map((el, i) => ({
      name: el.value || `Step ${i + 1}`,
      until_c: Number(document.querySelector(`.step-until[data-i="${i}"]`).value),
      percent: Number(document.querySelector(`.step-pct[data-i="${i}"]`).value),
    }));
  }

  function loadEditor(profile) {
    state.editorId = profile.id;
    $('editor-id').textContent = profile.id;
    $('custom-name').value = profile.name || '';
    renderSteps(profile.steps && profile.steps.length ? profile.steps : [
      { name: 'Idle', until_c: 40, percent: 15 },
      { name: 'Warm', until_c: 55, percent: 50 },
      { name: 'Hot', until_c: 200, percent: 100 },
    ]);
  }

  function render(data) {
    state.data = data;
    const live = data.live || {};
    $('rpm-badge').textContent = `RPM ${fmt(live.fan_rpm)}`;
    $('temp-badge').textContent = `CPU ${fmt(live.cpu_temp, '°C')}`;
    $('max-badge').textContent = `Max ${fmt((data.pwm.calibration || {}).max_rpm || live.max_speed, 'RPM')}`;
    const calibMax = (data.pwm.calibration || {}).max_rpm || live.max_speed;
    const calibAt = (data.pwm.calibration || {}).calibrated_at || '';
    const calibLabel = $('calib-max-label');
    if (calibLabel) {
      calibLabel.textContent = calibMax ? `${fmt(calibMax, 'RPM')}${calibAt ? ' · ' + calibAt : ''}` : 'not calibrated yet';
    }
    const job = data.job || {};
    const jobBadge = $('job-badge');
    if (job.state === 'running') {
      jobBadge.classList.remove('d-none');
      jobBadge.textContent = job.kind || 'job';
    } else {
      jobBadge.classList.add('d-none');
    }

    $('pwm-builtin').innerHTML = (data.pwm.builtin || []).map((p) => profileCard(p, 'builtin')).join('');
    const customs = data.pwm.custom || [];
    $('pwm-custom').innerHTML = customs.map((p) => profileCard(p, 'custom')).join('');
    $('custom-empty').classList.toggle('d-none', customs.length > 0);

    const rgb = data.rgb || {};
    $('rgb-enable').checked = !!rgb.enable;
    $('rgb-color').value = rgb.color || '#0a1aff';
    $('rgb-count').value = rgb.led_count || 4;
    $('rgb-brightness').value = rgb.brightness || 0;
    $('rgb-speed').value = rgb.speed || 0;
    $('rgb-bright-val').textContent = `${rgb.brightness}%`;
    $('rgb-speed-val').textContent = `${rgb.speed}%`;
    $('rgb-styles').innerHTML = (rgb.styles || []).map((s) => rgbCard(s, s.id === rgb.style)).join('');

    if (!state.editorId && customs[0]) loadEditor(customs[0]);
  }

  function showJob(title) {
    $('job-title').textContent = title;
    $('job-result').classList.add('d-none');
    state.modal = bootstrap.Modal.getOrCreateInstance($('job-modal'));
    state.modal.show();
  }

  function updateJobUI(job) {
    if (!job) return;
    $('job-msg').textContent = job.message || job.state || '';
    const prog = job.progress || {};
    const pct = prog.total ? Math.round((prog.step / prog.total) * 100) : (job.state === 'success' ? 100 : 15);
    $('job-progress').style.width = `${pct}%`;
    liveTiles(job.live || {}, { peak_rpm: (job.live || {}).peak_rpm });
    if (job.result && job.state !== 'running') {
      const r = job.result;
      $('job-result').classList.remove('d-none');
      $('job-result').innerHTML = job.kind === 'calibrate'
        ? `<div class="alert alert-success py-2">Calibrated max <strong>${esc(r.max_rpm)} RPM</strong></div>`
        : `<div class="alert alert-info py-2">${benchSummary(r)}</div>`;
    }
  }

  async function refresh() {
    const json = await api('/get-fan-controls');
    render(json.data);
    updateJobUI(json.data.job);
    return json.data;
  }

  async function pollJob() {
    const json = await api('/fan-live');
    const live = json.data.live || {};
    $('rpm-badge').textContent = `RPM ${fmt(live.fan_rpm)}`;
    $('temp-badge').textContent = `CPU ${fmt(live.cpu_temp, '°C')}`;
    updateJobUI(json.data.job);
    const job = json.data.job || {};
    if (job.state && job.state !== 'running') {
      stopPoll();
      await refresh();
    }
  }

  function startPoll() {
    if (state.pollTimer) return;
    state.pollTimer = setInterval(() => {
      pollJob().catch(() => {});
    }, 800);
  }

  function stopPoll() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  async function applyProfile(id) {
    await api('/apply-pwm-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    });
    await refresh();
  }

  async function startBench(id) {
    showJob(`Benchmark — ${id}`);
    await api('/start-fan-benchmark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id }),
    });
    startPoll();
  }

  async function saveCustom(apply) {
    const profile = {
      id: state.editorId || undefined,
      name: $('custom-name').value || 'Custom',
      steps: readSteps(),
      apply: !!apply,
    };
    const json = await api('/save-custom-fan-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    });
    state.editorId = json.data.profile.id;
    await refresh();
    loadEditor(json.data.profile);
  }

  document.addEventListener('click', async (e) => {
    const apply = e.target.closest('.btn-apply');
    const bench = e.target.closest('.btn-bench');
    const edit = e.target.closest('.btn-edit');
    const del = e.target.closest('.btn-del');
    const rgb = e.target.closest('.btn-rgb');
    const delStep = e.target.closest('.btn-del-step');
    try {
      if (apply) await applyProfile(apply.dataset.id);
      if (bench) await startBench(bench.dataset.id);
      if (edit) {
        const found = (state.data.pwm.custom || []).find((p) => p.id === edit.dataset.id);
        if (found) loadEditor(found);
      }
      if (del && !del.classList.contains('btn-del-step')) {
        if (!window.confirm('Delete this custom profile?')) return;
        await api('/delete-custom-fan-profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: del.dataset.id }),
        });
        state.editorId = '';
        await refresh();
      }
      if (rgb) {
        await api('/set-rgb-fan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ style: rgb.dataset.id, enable: true }),
        });
        await refresh();
      }
      if (delStep) {
        const steps = readSteps();
        steps.splice(Number(delStep.dataset.i), 1);
        renderSteps(steps);
      }
    } catch (err) {
      window.alert(err.message || String(err));
    }
  });

  $('btn-add-step').addEventListener('click', () => {
    const steps = readSteps();
    steps.push({ name: `Step ${steps.length + 1}`, until_c: 70, percent: 80 });
    renderSteps(steps);
  });

  $('btn-clear-custom').addEventListener('click', () => {
    $('custom-name').value = 'Custom';
    renderSteps([
      { name: 'Idle', until_c: 40, percent: 15 },
      { name: 'Warm', until_c: 55, percent: 50 },
      { name: 'Hot', until_c: 200, percent: 100 },
    ]);
  });

  $('btn-add-custom').addEventListener('click', async () => {
    const json = await api('/save-custom-fan-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: `Custom ${Date.now() % 1000}`, steps: [
        { name: 'Idle', until_c: 40, percent: 15 },
        { name: 'Warm', until_c: 55, percent: 50 },
        { name: 'Hot', until_c: 200, percent: 100 },
      ] }),
    });
    loadEditor(json.data.profile);
    await refresh();
  });

  $('btn-apply-custom').addEventListener('click', () => saveCustom(true).catch((e) => window.alert(e.message)));
  $('btn-save-custom').addEventListener('click', () => saveCustom(false).catch((e) => window.alert(e.message)));
  $('btn-bench-editor').addEventListener('click', async () => {
    await saveCustom(false);
    await startBench(state.editorId);
  });
  $('btn-delete-custom').addEventListener('click', async () => {
    if (!state.editorId) return;
    if (!window.confirm('Delete this custom profile?')) return;
    await api('/delete-custom-fan-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: state.editorId }),
    });
    state.editorId = '';
    await refresh();
  });

  async function startCalibrate() {
    if (!window.confirm('Spin the PWM fan at 100% for ~10s to measure max RPM? Live CPU temperature will be shown.')) return;
    showJob('PWM calibration');
    await api('/start-fan-calibration', { method: 'POST' });
    startPoll();
  }

  document.querySelectorAll('.js-calibrate').forEach((btn) => {
    btn.addEventListener('click', () => startCalibrate().catch((e) => window.alert(e.message)));
  });

  async function pushRgb(extra) {
    const body = Object.assign({
      enable: $('rgb-enable').checked,
      color: $('rgb-color').value,
      brightness: Number($('rgb-brightness').value),
      speed: Number($('rgb-speed').value),
      led_count: Number($('rgb-count').value),
    }, extra || {});
    await api('/set-rgb-fan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  ['rgb-enable', 'rgb-color', 'rgb-count'].forEach((id) => {
    $(id).addEventListener('change', () => pushRgb().then(refresh).catch((e) => window.alert(e.message)));
  });
  ['rgb-brightness', 'rgb-speed'].forEach((id) => {
    $(id).addEventListener('input', () => {
      $('rgb-bright-val').textContent = `${$('rgb-brightness').value}%`;
      $('rgb-speed-val').textContent = `${$('rgb-speed').value}%`;
    });
    $(id).addEventListener('change', () => pushRgb().then(refresh).catch((e) => window.alert(e.message)));
  });

  refresh().catch((err) => {
    document.body.insertAdjacentHTML('beforeend',
      `<div class="alert alert-danger m-3">${esc(err.message)}</div>`);
  });
  setInterval(() => {
    api('/fan-live').then((json) => {
      const live = json.data.live || {};
      $('rpm-badge').textContent = `RPM ${fmt(live.fan_rpm)}`;
      $('temp-badge').textContent = `CPU ${fmt(live.cpu_temp, '°C')}`;
      $('max-badge').textContent = `Max ${fmt(live.max_speed, 'RPM')}`;
    }).catch(() => {});
  }, 1500);
})();
