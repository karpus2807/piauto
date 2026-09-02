/**
 * Inject extra left-nav items (OLED, Fans, Update) into the stock MUI drawer.
 * Extra pages live in a host *outside* #root so React re-renders / refresh
 * cannot unmount them or blank the whole dashboard.
 */
(function () {
  const STOCK_TAB_KEY = 'pm-dashboard-tabIndex';
  const EXTRA_TAB_KEY = 'piauto-extra-tab';
  const API = '/api/v1.0';
  const STOCK_TABS = ['Dashboard', 'History', 'Log'];

  const EXTRA_TABS = [
    {
      id: 'oled',
      text: 'OLED',
      src: '/oled-designer/',
      title: 'OLED Designer',
      needOled: true,
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20 3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h3v2h10v-2h3c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 13H4V5h16v11z"/></svg>',
    },
    {
      id: 'fans',
      text: 'Fans',
      src: '/fan-controls/',
      title: 'Fan controls',
      needOled: false,
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a3 3 0 0 1 1 5.83V9.1A4.5 4.5 0 0 1 16.9 13h1.27A3 3 0 1 1 18 19h-.1A4.5 4.5 0 0 1 13.9 16.9v-.01A4.48 4.48 0 0 1 12 17a4.48 4.48 0 0 1-1.9-.11v.01A4.5 4.5 0 0 1 6.1 19H6a3 3 0 1 1-.17-6h1.27A4.5 4.5 0 0 1 11 9.1V7.83A3 3 0 0 1 12 2zm0 2a1 1 0 1 0 0 2 1 1 0 0 0 0-2zm7 12a1 1 0 1 0 0 2 1 1 0 0 0 0-2zM5 16a1 1 0 1 0 0 2 1 1 0 0 0 0-2zm7-5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"/></svg>',
    },
    {
      id: 'upgrade',
      text: 'Update',
      src: '/update/',
      title: 'Update',
      needOled: false,
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21 10.12h-6.78l2.74-2.82c-2.73-2.7-7.15-2.8-9.88-.1-2.73 2.71-2.73 7.08 0 9.79s7.15 2.71 9.88 0C18.32 15.65 19 14.08 19 12.1h2c0 1.98-.88 4.55-2.64 6.29-3.51 3.48-9.21 3.48-12.72 0-3.5-3.47-3.53-9.11-.02-12.58s9.14-3.47 12.65 0L21 3v7.12zM12.5 8v4.25l3.5 2.08-.72 1.21L11 13V8h1.5z"/></svg>',
    },
  ];

  const state = {
    oledOk: null,
    buttons: {},
    iframes: {},
    host: null,
    activeId: null,
    stockBound: false,
  };

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function qsa(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function findNavList() {
    const texts = qsa('nav .MuiListItemText-primary, .MuiDrawer-root .MuiListItemText-primary, .MuiListItemText-primary');
    const dash = texts.find((el) => (el.textContent || '').trim() === 'Dashboard');
    if (!dash) return null;
    return dash.closest('.MuiList-root') || dash.closest('ul');
  }

  function listButtons(list) {
    return qsa('.MuiListItemButton-root', list);
  }

  function setSelected(btn, on) {
    if (!btn) return;
    btn.classList.toggle('Mui-selected', !!on);
    btn.setAttribute('aria-selected', on ? 'true' : 'false');
  }

  function extraButtons() {
    return Object.values(state.buttons);
  }

  function isExtraButton(btn) {
    return extraButtons().includes(btn);
  }

  function readJson(key) {
    try {
      return JSON.parse(window.localStorage.getItem(key) || 'null');
    } catch (_) {
      return null;
    }
  }

  function writeJson(key, value) {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (_) { /* ignore */ }
  }

  function sanitizeStockTab() {
    const saved = readJson(STOCK_TAB_KEY);
    if (!saved || typeof saved !== 'object') {
      writeJson(STOCK_TAB_KEY, { text: 'Dashboard', index: 0 });
      return;
    }
    const extra = EXTRA_TABS.find((t) => (
      t.text === saved.text || t.id === saved.id || (saved.text === 'Upgrade' && t.id === 'upgrade')
    ));
    if (extra) {
      if (!readJson(EXTRA_TAB_KEY)) writeJson(EXTRA_TAB_KEY, { id: extra.id, text: extra.text });
      writeJson(STOCK_TAB_KEY, { text: 'Dashboard', index: 0 });
      return;
    }
    const idx = Number(saved.index);
    if (!STOCK_TABS.includes(saved.text) || !Number.isFinite(idx) || idx < 0 || idx > 20) {
      writeJson(STOCK_TAB_KEY, { text: 'Dashboard', index: 0 });
    }
  }

  function extraHost() {
    if (state.host && document.body.contains(state.host)) return state.host;
    let host = document.getElementById('piauto-extra-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'piauto-extra-host';
      host.setAttribute('aria-live', 'polite');
      document.body.appendChild(host);
    }
    host.style.cssText = [
      'position:fixed',
      'top:48px',
      'left:0',
      'right:0',
      'bottom:0',
      'z-index:1050',
      'display:none',
      'background:#0b0f14',
    ].join(';');
    state.host = host;
    return host;
  }

  function layoutHost() {
    const host = extraHost();
    const appbar = qs('.MuiAppBar-root');
    const drawer = qs('.MuiDrawer-paper');
    let top = 48;
    let left = 0;
    if (appbar) {
      const r = appbar.getBoundingClientRect();
      if (r.height) top = Math.round(r.bottom);
    }
    if (drawer) {
      const r = drawer.getBoundingClientRect();
      if (r.width > 64 && r.left < 8 && r.bottom > 80) left = Math.round(r.right);
    }
    host.style.top = top + 'px';
    host.style.left = left + 'px';
  }

  function hideExtraPanels() {
    state.activeId = null;
    try { window.localStorage.removeItem(EXTRA_TAB_KEY); } catch (_) { /* ignore */ }
    extraButtons().forEach((btn) => setSelected(btn, false));
    if (state.host) state.host.style.display = 'none';
    Object.values(state.iframes).forEach((frame) => {
      frame.style.display = 'none';
    });
  }

  function showTab(tab) {
    const host = extraHost();
    layoutHost();
    if (!state.iframes[tab.id]) {
      const iframe = document.createElement('iframe');
      iframe.id = 'piauto-frame-' + tab.id;
      iframe.dataset.piautoFrame = tab.id;
      iframe.src = tab.src;
      iframe.title = tab.title;
      iframe.style.cssText = 'border:0;width:100%;height:100%;background:#0b0f14;display:block;';
      host.appendChild(iframe);
      state.iframes[tab.id] = iframe;
    }
    Object.entries(state.iframes).forEach(([id, frame]) => {
      if (!host.contains(frame)) host.appendChild(frame);
      frame.style.display = id === tab.id ? 'block' : 'none';
    });
    host.style.display = 'block';
    state.activeId = tab.id;
    writeJson(EXTRA_TAB_KEY, { id: tab.id, text: tab.text });
    // Keep React on a real stock tab so it never renders an empty main view.
    writeJson(STOCK_TAB_KEY, { text: 'Dashboard', index: 0 });
  }

  function clearReactSelection(list) {
    listButtons(list).forEach((btn) => {
      if (isExtraButton(btn)) return;
      setSelected(btn, false);
    });
  }

  function onStockTabClick() {
    hideExtraPanels();
  }

  function bindStockClicks(list) {
    listButtons(list).forEach((b) => {
      if (isExtraButton(b)) return;
      b.addEventListener('click', onStockTabClick, true);
    });
    state.stockBound = true;
  }

  function ensureItem(list, tab) {
    const existing = qs(`[data-piauto-tab="${tab.id}"]`, list);
    if (existing && state.buttons[tab.id]) return;

    const templateBtn = listButtons(list).find((b) => {
      const t = (b.textContent || '').trim();
      return t.startsWith('Dashboard') || t.startsWith('History') || t.startsWith('Log');
    });
    if (!templateBtn) return;

    const templateItem = templateBtn.closest('.MuiListItem-root') || templateBtn.parentElement;
    const item = templateItem.cloneNode(true);
    item.setAttribute('data-piauto-tab', tab.id);
    const btn = qs('.MuiListItemButton-root', item) || item.querySelector('div[role="button"]') || item.firstElementChild;
    const textEl = qs('.MuiListItemText-primary', item);
    if (textEl) textEl.textContent = tab.text;
    const iconSlot = qs('.MuiListItemIcon-root', item);
    if (iconSlot) iconSlot.innerHTML = tab.icon;
    setSelected(btn, false);
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      clearReactSelection(list);
      extraButtons().forEach((b) => setSelected(b, false));
      setSelected(btn, true);
      showTab(tab);
    });
    list.appendChild(item);
    state.buttons[tab.id] = btn;
    bindStockClicks(list);
  }

  function restoreSelection(list) {
    sanitizeStockTab();
    const saved = readJson(EXTRA_TAB_KEY);
    if (!saved) return;
    const tab = EXTRA_TABS.find((t) => (
      t.text === saved.text || t.id === saved.id || (saved.text === 'Upgrade' && t.id === 'upgrade')
    ));
    if (!tab || !state.buttons[tab.id]) return;
    extraButtons().forEach((b) => setSelected(b, false));
    setSelected(state.buttons[tab.id], true);
    showTab(tab);
  }

  async function hasOledPeripheral() {
    if (state.oledOk !== null) return state.oledOk;
    try {
      const res = await fetch(`${API}/get-device-info`);
      const data = await res.json();
      const peripherals = (data && data.data && data.data.peripherals) || [];
      state.oledOk = peripherals.includes('oled');
    } catch (_) {
      state.oledOk = true;
    }
    return state.oledOk;
  }

  async function tryInject() {
    sanitizeStockTab();
    const list = findNavList();
    if (!list) return;
    const oledOk = await hasOledPeripheral();
    EXTRA_TABS.forEach((tab) => {
      if (tab.needOled && !oledOk) return;
      ensureItem(list, tab);
    });
    restoreSelection(list);
    if (state.activeId) layoutHost();
  }

  sanitizeStockTab();

  const obs = new MutationObserver((records) => {
    const onlyHost = records.every((rec) => {
      const node = rec.target;
      if (!node) return false;
      if (node.id === 'piauto-extra-host') return true;
      return !!(node.closest && node.closest('#piauto-extra-host'));
    });
    if (onlyHost) return;
    tryInject();
  });
  function watch() {
    const root = document.getElementById('root');
    obs.observe(root || document.documentElement, { childList: true, subtree: true });
  }
  window.addEventListener('resize', layoutHost);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      watch();
      tryInject();
    });
  } else {
    watch();
    tryInject();
  }
  let n = 0;
  const timer = setInterval(() => {
    tryInject();
    n += 1;
    if (n > 80) clearInterval(timer);
  }, 250);
})();
