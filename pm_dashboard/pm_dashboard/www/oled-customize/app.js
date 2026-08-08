(() => {
  const API = '/api/v1.0';
  const PAGE_HELP = {
    mix: 'Overview mix page',
    performance: 'CPU / GPU / memory / fan',
    ips: 'Network addresses',
    disk: 'Storage usage',
    battery: 'Battery / UPS',
    input: 'Power input',
    rpi_power: 'Pi power status',
  };

  const el = {
    status: document.getElementById('status'),
    enable: document.getElementById('oled-enable'),
    rotation: document.getElementById('oled-rotation'),
    sleep: document.getElementById('oled-sleep'),
    list: document.getElementById('page-list'),
    apply: document.getElementById('btn-apply'),
    reload: document.getElementById('btn-reload'),
    foot: document.getElementById('foot'),
  };

  let available = [];
  let dragId = null;

  async function api(path, opts) {
    const res = await fetch(`${API}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(opts && opts.headers) },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === false) {
      throw new Error((data && data.error) || `Request failed: ${path}`);
    }
    return data;
  }

  function setStatus(msg, kind) {
    el.status.textContent = msg;
    el.status.className = `status${kind ? ` ${kind}` : ''}`;
  }

  function orderedPages(enabledPages) {
    const enabled = Array.isArray(enabledPages) ? enabledPages.filter((p) => available.includes(p)) : [];
    const rest = available.filter((p) => !enabled.includes(p));
    return [...enabled, ...rest];
  }

  function renderPages(enabledPages) {
    const order = orderedPages(enabledPages);
    const enabledSet = new Set(Array.isArray(enabledPages) ? enabledPages : []);
    el.list.innerHTML = '';
    order.forEach((page) => {
      const li = document.createElement('li');
      li.className = 'page-item';
      li.draggable = true;
      li.dataset.page = page;

      const handle = document.createElement('span');
      handle.className = 'handle';
      handle.textContent = '⋮⋮';

      const name = document.createElement('div');
      name.className = 'name';
      name.innerHTML = `${page}<small>${PAGE_HELP[page] || 'OLED page'}</small>`;

      const toggle = document.createElement('input');
      toggle.type = 'checkbox';
      toggle.checked = enabledSet.has(page);
      toggle.title = 'Include in carousel';
      toggle.addEventListener('click', (e) => e.stopPropagation());

      li.append(handle, name, toggle);
      bindDrag(li);
      el.list.appendChild(li);
    });
  }

  function bindDrag(li) {
    li.addEventListener('dragstart', () => {
      dragId = li.dataset.page;
      li.classList.add('dragging');
    });
    li.addEventListener('dragend', () => {
      dragId = null;
      li.classList.remove('dragging');
    });
    li.addEventListener('dragover', (e) => {
      e.preventDefault();
      const target = e.currentTarget;
      if (!dragId || target.dataset.page === dragId) return;
      const dragging = el.list.querySelector(`[data-page="${dragId}"]`);
      if (!dragging) return;
      const items = [...el.list.children];
      const from = items.indexOf(dragging);
      const to = items.indexOf(target);
      if (from < to) target.after(dragging);
      else target.before(dragging);
    });
  }

  function collectEnabledPages() {
    return [...el.list.children]
      .filter((li) => li.querySelector('input[type="checkbox"]').checked)
      .map((li) => li.dataset.page);
  }

  async function load() {
    setStatus('Loading…');
    el.apply.disabled = true;
    const [dev, cfg] = await Promise.all([
      api('/get-device-info'),
      api('/get-config'),
    ]);
    const peripherals = (dev.data && dev.data.peripherals) || [];
    available = peripherals
      .filter((p) => typeof p === 'string' && p.startsWith('oled_page_'))
      .map((p) => p.slice('oled_page_'.length));

    const system = (cfg.data && cfg.data.system) || {};
    el.enable.checked = system.oled_enable !== false;
    el.rotation.value = String(system.oled_rotation === 180 ? 180 : 0);
    el.sleep.value = String(Number(system.oled_sleep_timeout ?? 0));
    renderPages(system.oled_pages || available.slice());

    const name = (dev.data && (dev.data.name || dev.data.id)) || 'device';
    el.foot.textContent = `${name} · available pages: ${available.join(', ') || 'none'}`;
    setStatus('Ready — change settings and click Apply.', 'ok');
    el.apply.disabled = false;
  }

  async function apply() {
    const pages = collectEnabledPages();
    if (!pages.length) {
      setStatus('Enable at least one OLED page before applying.', 'err');
      return;
    }
    el.apply.disabled = true;
    setStatus('Applying…');
    try {
      const sleep = Number(el.sleep.value);
      if (!Number.isFinite(sleep) || sleep < 0) {
        throw new Error('Sleep timeout must be a number ≥ 0');
      }
      await api('/set-oled-enable', {
        method: 'POST',
        body: JSON.stringify({ enable: !!el.enable.checked }),
      });
      await api('/set-oled-rotation', {
        method: 'POST',
        body: JSON.stringify({ rotation: Number(el.rotation.value) }),
      });
      await api('/set-oled-sleep-timeout', {
        method: 'POST',
        body: JSON.stringify({ timeout: sleep }),
      });
      await api('/set-oled-pages', {
        method: 'POST',
        body: JSON.stringify({ pages }),
      });
      setStatus('Applied. OLED carousel updated.', 'ok');
    } catch (err) {
      setStatus(err.message || String(err), 'err');
    } finally {
      el.apply.disabled = false;
    }
  }

  el.apply.addEventListener('click', () => {
    apply().catch((err) => setStatus(err.message || String(err), 'err'));
  });
  el.reload.addEventListener('click', () => {
    load().catch((err) => setStatus(err.message || String(err), 'err'));
  });

  load().catch((err) => setStatus(err.message || String(err), 'err'));
})();
