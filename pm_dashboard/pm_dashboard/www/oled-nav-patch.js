/**
 * Inject a 4th "OLED" item into the stock MUI drawer and show /oled-customize
 * inside the main content area (iframe), without rebuilding the React SPA.
 */
(function () {
  const TAB_KEY = 'pm-dashboard-tabIndex';
  const OLED_TEXT = 'OLED';
  const API = '/api/v1.0';
  let injected = false;
  let iframe = null;
  let oledButton = null;
  let originalMainChildren = null;

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function qsa(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function findNavList() {
    // MUI List inside permanent drawer that contains Dashboard item text.
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

  function clearReactSelection(list) {
    listButtons(list).forEach((btn) => {
      if (btn === oledButton) return;
      setSelected(btn, false);
    });
  }

  function hideOledPanel() {
    const main = findMain();
    if (!main || !iframe) return;
    iframe.style.display = 'none';
    qsa(':scope > *', main).forEach((child) => {
      if (child === iframe) return;
      if (originalMainChildren && originalMainChildren.has(child)) {
        child.style.display = originalMainChildren.get(child);
      } else {
        child.style.removeProperty('display');
      }
    });
  }

  function showOledPanel() {
    const main = findMain();
    if (!main) return;
    if (!iframe) {
      iframe = document.createElement('iframe');
      iframe.id = 'piauto-oled-customize-frame';
      iframe.src = '/oled-designer/';
      iframe.title = 'OLED Designer';
      iframe.style.cssText = 'border:0;width:100%;height:calc(100vh - 56px);min-height:640px;background:#0b0f14;display:block;';
      main.appendChild(iframe);
    }
    if (!originalMainChildren) originalMainChildren = new WeakMap();
    qsa(':scope > *', main).forEach((child) => {
      if (child === iframe) return;
      if (!originalMainChildren.has(child)) {
        originalMainChildren.set(child, child.style.display || '');
      }
      child.style.display = 'none';
    });
    iframe.style.display = 'block';
    try {
      window.localStorage.setItem(TAB_KEY, JSON.stringify({ text: OLED_TEXT, index: 99 }));
    } catch (_) { /* ignore */ }
  }

  function onStockTabClick() {
    hideOledPanel();
    if (oledButton) setSelected(oledButton, false);
  }

  function ensureOledItem(list) {
    if (injected && oledButton && list.contains(oledButton.closest('.MuiListItem-root'))) {
      return;
    }
    const templateBtn = listButtons(list).find((b) => {
      const t = (b.textContent || '').trim();
      return t.startsWith('Dashboard') || t.startsWith('History') || t.startsWith('Log');
    });
    if (!templateBtn) return;

    const templateItem = templateBtn.closest('.MuiListItem-root') || templateBtn.parentElement;
    const item = templateItem.cloneNode(true);
    const btn = qs('.MuiListItemButton-root', item) || item.querySelector('div[role="button"]') || item.firstElementChild;
    const textEl = qs('.MuiListItemText-primary', item);
    if (textEl) textEl.textContent = OLED_TEXT;

    // Simple monitor glyph in the icon slot if present.
    const iconSlot = qs('.MuiListItemIcon-root', item);
    if (iconSlot) {
      iconSlot.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20 3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h3v2h10v-2h3c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 13H4V5h16v11z"/></svg>';
    }

    setSelected(btn, false);
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      clearReactSelection(list);
      setSelected(btn, true);
      showOledPanel();
    });

    // When user returns to stock tabs, hide our panel.
    listButtons(list).forEach((b) => {
      if (b === btn) return;
      b.addEventListener('click', onStockTabClick, true);
    });

    list.appendChild(item);
    oledButton = btn;
    injected = true;

    // Restore OLED tab if it was last selected.
    try {
      const saved = JSON.parse(window.localStorage.getItem(TAB_KEY) || 'null');
      if (saved && saved.text === OLED_TEXT) {
        clearReactSelection(list);
        setSelected(btn, true);
        showOledPanel();
      }
    } catch (_) { /* ignore */ }
  }

  async function hasOledPeripheral() {
    try {
      const res = await fetch(`${API}/get-device-info`);
      const data = await res.json();
      const peripherals = (data && data.data && data.data.peripherals) || [];
      return peripherals.includes('oled');
    } catch (_) {
      return true; // still try to inject; page will error if unsupported
    }
  }

  async function tryInject() {
    if (!(await hasOledPeripheral())) return;
    const list = findNavList();
    if (!list) return;
    ensureOledItem(list);
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
  // SPA paints after first paint; retry a few times.
  let n = 0;
  const timer = setInterval(() => {
    tryInject();
    n += 1;
    if (n > 40 || injected) clearInterval(timer);
  }, 250);
})();
