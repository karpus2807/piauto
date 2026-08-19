/**
 * Inject extra left-nav items (OLED, Upgrade) into the stock MUI drawer
 * and show their pages in the main content area (iframe).
 */
(function () {
  const TAB_KEY = 'pm-dashboard-tabIndex';
  const API = '/api/v1.0';

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
      id: 'upgrade',
      text: 'Upgrade',
      src: '/upgrade/',
      title: 'Upgrade',
      needOled: false,
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M5 20h14v-2H5v2zm7-2l5-5h-3V6h-4v7H7l5 5z"/></svg>',
    },
  ];

  const state = {
    oledOk: null,
    buttons: {},
    iframes: {},
    originalMainChildren: null,
    restored: false,
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

  function findMain() {
    return qs('main.main') || qs('main') || qs('[class*="Main"]');
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

  function clearReactSelection(list) {
    listButtons(list).forEach((btn) => {
      if (isExtraButton(btn)) return;
      setSelected(btn, false);
    });
  }

  function hideExtraPanels() {
    const main = findMain();
    if (!main) return;
    Object.values(state.iframes).forEach((frame) => {
      frame.style.display = 'none';
    });
    qsa(':scope > *', main).forEach((child) => {
      if (child.dataset && child.dataset.piautoFrame) return;
      if (state.originalMainChildren && state.originalMainChildren.has(child)) {
        child.style.display = state.originalMainChildren.get(child);
      } else {
        child.style.removeProperty('display');
      }
    });
  }

  function showTab(tab) {
    const main = findMain();
    if (!main) return;
    if (!state.iframes[tab.id]) {
      const iframe = document.createElement('iframe');
      iframe.id = 'piauto-frame-' + tab.id;
      iframe.dataset.piautoFrame = tab.id;
      iframe.src = tab.src;
      iframe.title = tab.title;
      iframe.style.cssText = 'border:0;width:100%;height:calc(100vh - 56px);min-height:640px;background:#0b0f14;display:block;';
      main.appendChild(iframe);
      state.iframes[tab.id] = iframe;
    }
    if (!state.originalMainChildren) state.originalMainChildren = new WeakMap();
    qsa(':scope > *', main).forEach((child) => {
      if (child.dataset && child.dataset.piautoFrame) return;
      if (!state.originalMainChildren.has(child)) {
        state.originalMainChildren.set(child, child.style.display || '');
      }
      child.style.display = 'none';
    });
    Object.entries(state.iframes).forEach(([id, frame]) => {
      frame.style.display = id === tab.id ? 'block' : 'none';
    });
    try {
      window.localStorage.setItem(TAB_KEY, JSON.stringify({ text: tab.text, index: 99, id: tab.id }));
    } catch (_) { /* ignore */ }
  }

  function onStockTabClick() {
    hideExtraPanels();
    extraButtons().forEach((btn) => setSelected(btn, false));
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

    listButtons(list).forEach((b) => {
      if (isExtraButton(b)) return;
      b.addEventListener('click', onStockTabClick, true);
    });
  }

  function restoreSelection(list) {
    if (state.restored) return;
    state.restored = true;
    try {
      const saved = JSON.parse(window.localStorage.getItem(TAB_KEY) || 'null');
      if (!saved) return;
      const tab = EXTRA_TABS.find((t) => t.text === saved.text || t.id === saved.id);
      if (!tab || !state.buttons[tab.id]) {
        state.restored = false;
        return;
      }
      clearReactSelection(list);
      extraButtons().forEach((b) => setSelected(b, false));
      setSelected(state.buttons[tab.id], true);
      showTab(tab);
    } catch (_) { /* ignore */ }
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
    const list = findNavList();
    if (!list) return;
    const oledOk = await hasOledPeripheral();
    EXTRA_TABS.forEach((tab) => {
      if (tab.needOled && !oledOk) return;
      ensureItem(list, tab);
    });
    restoreSelection(list);
  }

  const obs = new MutationObserver(() => {
    tryInject();
  });
  obs.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => tryInject());
  } else {
    tryInject();
  }
  let n = 0;
  const timer = setInterval(() => {
    tryInject();
    n += 1;
    if (n > 40) clearInterval(timer);
  }, 250);
})();
