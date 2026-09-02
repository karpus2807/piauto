(function () {
  const API = '/api/v1.0';
  const listEl = document.getElementById('release-list');
  const repoBadge = document.getElementById('repo-badge');
  const currentBadge = document.getElementById('current-badge');
  const errorBanner = document.getElementById('error-banner');
  const jobBanner = document.getElementById('job-banner');
  const refreshBtn = document.getElementById('btn-refresh');

  let pollTimer = null;

  function showError(msg) {
    if (!msg) {
      errorBanner.classList.add('hidden');
      errorBanner.textContent = '';
      return;
    }
    errorBanner.classList.remove('hidden');
    errorBanner.textContent = msg;
  }

  function showJob(job) {
    if (!job || !job.state || job.state === 'idle') {
      jobBanner.classList.add('hidden');
      return;
    }
    jobBanner.classList.remove('hidden', 'error', 'ok');
    if (job.state === 'error') jobBanner.classList.add('error');
    if (job.state === 'success') jobBanner.classList.add('ok');
    const tag = job.tag ? ` (${job.tag})` : '';
    jobBanner.textContent = `${job.state}${tag}: ${job.message || ''}`;
  }

  function fmtDate(value) {
    if (!value) return '';
    try {
      return new Date(value).toLocaleString();
    } catch (_) {
      return value;
    }
  }

  function excerpt(body) {
    const text = (body || '').trim();
    if (!text) return 'No release notes.';
    return text.length > 600 ? text.slice(0, 600) + '…' : text;
  }

  function actionFor(rel) {
    const direction = rel.direction || (rel.current ? 'current' : 'switch');
    if (direction === 'current') {
      return { label: 'Running this version', kind: 'current', disabled: true };
    }
    if (direction === 'update') {
      return { label: 'Update to this version', kind: 'update', disabled: false };
    }
    if (direction === 'downgrade') {
      return { label: 'Downgrade to this version', kind: 'downgrade', disabled: false };
    }
    return { label: 'Install this version', kind: 'switch', disabled: false };
  }

  function render(data) {
    const current = (data && data.current) || {};
    const releases = (data && data.releases) || [];
    repoBadge.textContent = data.repo || 'github';
    const tag = current.release_tag || current.pm_auto || 'unknown';
    currentBadge.textContent = `current ${tag}  ·  pm_auto ${current.pm_auto || '—'}  ·  dashboard ${current.pm_dashboard || '—'}`;

    if (!releases.length) {
      listEl.innerHTML = '<p class="muted">No GitHub Releases yet. Publish a Release on the repo, then tap Refresh. Until then, tags are shown if available.</p>';
      return;
    }

    listEl.innerHTML = '';
    releases.forEach((rel, index) => {
      const card = document.createElement('article');
      const action = actionFor(rel);
      card.className = 'card' + (rel.current ? ' current' : '') + (action.kind === 'downgrade' ? ' older' : '');
      const when = fmtDate(rel.published_at);
      const badges = [];
      if (index === 0) badges.push('<span class="badge">latest</span>');
      if (rel.current) badges.push('<span class="badge ok">running</span>');
      if (rel.prerelease) badges.push('<span class="badge warn">pre-release</span>');
      if (action.kind === 'update') badges.push('<span class="badge">update</span>');
      if (action.kind === 'downgrade') badges.push('<span class="badge warn">older</span>');
      const btnClass = action.kind === 'downgrade' ? 'btn downgrade' : 'btn';
      card.innerHTML = `
        <div class="card-top">
          <h2>${escapeHtml(rel.name || rel.tag)}</h2>
          <div>${badges.join(' ')}</div>
        </div>
        <p class="meta">${escapeHtml(rel.tag)}${when ? ' · ' + escapeHtml(when) : ''}</p>
        <pre class="body">${escapeHtml(excerpt(rel.body))}</pre>
        <button type="button" class="${btnClass}" data-tag="${escapeAttr(rel.tag)}" ${action.disabled ? 'disabled' : ''}>${action.label}</button>
      `;
      const btn = card.querySelector('button');
      btn.addEventListener('click', () => applyTag(rel.tag, rel.name, action.kind));
      listEl.appendChild(card);
    });
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escapeAttr(value) {
    return escapeHtml(value).replace(/'/g, '&#39;');
  }

  async function load(refresh) {
    showError('');
    if (refreshBtn) refreshBtn.disabled = true;
    try {
      const url = `${API}/get-upgrades${refresh ? '?refresh=1' : ''}`;
      const res = await fetch(url);
      const json = await res.json();
      if (json.error) showError(json.error);
      render((json && json.data) || {});
      showJob(json && json.data && json.data.job);
      const job = json && json.data && json.data.job;
      if (job && job.state === 'running') startPoll();
      return json;
    } catch (err) {
      showError(String(err && err.message ? err.message : err));
      if (listEl && !listEl.children.length) {
        listEl.innerHTML = '<p class="muted">Could not load releases. Try Refresh again.</p>';
      }
      return null;
    } finally {
      if (refreshBtn) refreshBtn.disabled = false;
    }
  }

  async function poll() {
    try {
      const res = await fetch(`${API}/upgrade-status`);
      const json = await res.json();
      const job = json && json.data;
      showJob(job);
      if (!job || job.state !== 'running') {
        stopPoll();
        await load(true);
        if (job && job.state === 'success') {
          setTimeout(() => {
            try { window.top.location.reload(); } catch (_) { window.location.reload(); }
          }, 2500);
        }
      }
    } catch (_) {
      jobBanner.classList.remove('hidden');
      jobBanner.textContent = 'Dashboard restarting… waiting to come back.';
    }
  }

  function startPoll() {
    if (pollTimer) return;
    pollTimer = setInterval(poll, 2000);
  }

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function applyTag(tag, name, kind) {
    const label = name || tag;
    const verb = kind === 'downgrade' ? 'Downgrade to' : (kind === 'update' ? 'Update to' : 'Install');
    const extra = kind === 'downgrade' ? '\nThis installs an older version.' : '';
    const ok = window.confirm(`${verb} ${label}?${extra}\nThe Pironman service will restart. This can take a minute.`);
    if (!ok) return;
    showError('');
    const res = await fetch(`${API}/apply-upgrade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag }),
    });
    const json = await res.json();
    if (!json.status) {
      showError(json.error || 'Update failed to start');
      return;
    }
    showJob(json.data);
    startPoll();
  }

  refreshBtn.addEventListener('click', () => {
    load(true).catch((err) => showError(String(err)));
  });
  load(false).catch((err) => {
    showError(String(err));
    listEl.innerHTML = '<p class="muted">Could not load releases.</p>';
  });
})();
