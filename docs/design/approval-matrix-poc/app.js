/* App core: shell, router, action dispatch, drawers/modals, guide, reset */
(function (P) {
  const S = () => P.state;
  const esc = P.esc;
  P.screens = P.screens || {};
  P.actions = P.actions || {};
  P.drawers = P.drawers || {};
  P.modals = P.modals || {};

  const RAIL = [
    { key: 'home', label: 'Home', icon: 'home', screen: 'inbox' },
    { key: 'payrun', label: 'Pay Run', icon: 'zap', screen: 'scheme' },
    { key: 'people', label: 'People', icon: 'users', screen: 'other' },
    { key: 'workforce', label: 'Workforce', icon: 'compass', screen: 'other' },
    { key: 'insights', label: 'Insights', icon: 'trendingUp', screen: 'other' },
    { key: 'compliance', label: 'Compliance', icon: 'shield', screen: 'other' },
    { key: 'learn', label: 'Learn', icon: 'bookOpen', screen: 'other' },
    { key: 'settings', label: 'Settings', icon: 'settings', screen: 'matrix', cog: true },
  ];
  const railFor = { inbox: 'home', mobile: 'home', scheme: 'payrun', matrix: 'settings', builder: 'settings', people: 'settings', history: 'settings', other: '' };

  P.crumbs = {
    matrix: ['Settings', 'Approval Matrix'],
    builder: ['Settings', 'Approval Matrix', 'Pay run approval'],
    people: ['Settings', 'Approval Matrix', 'People & backups'],
    history: ['Settings', 'Approval Matrix', 'History'],
    scheme: ['Pay Run', 'New configuration', 'Connect'],
    inbox: ['Home', 'Approvals'],
    mobile: ['Home', 'Approvals', 'Phone view'],
    other: ['Not part of this POC'],
  };

  P.shell = function () {
    const s = S();
    const on = railFor[s.screen] || '';
    return `
<div class="top">
  <div class="brand"><i>p</i>payobook</div>
  <div class="ctx">${ic('building', 13)} <b>Rize Vietnam</b> · Vietnam company</div>
  <button class="ksearch" data-act="toast" data-arg="The ⌘K launcher would open here: Approvals, Approval Matrix, My approvals.">${ic('search', 14)} Search or jump to… <kbd>⌘K</kbd></button>
  <div class="sp"></div>
  <div class="lang">${ic('globe', 13)} EN ${ic('chevronDown', 12)}</div>
  <div class="avatar" title="You · Payroll administrator">AD</div>
</div>
<div class="low">
  <nav class="rail" aria-label="Main">
    ${RAIL.map(r => `<button class="rb ${on === r.key ? 'on' : ''} ${r.cog ? 'cog' : ''}" data-key="${r.key}" data-act="nav" data-arg="${r.screen}" title="${r.label}">${ic(r.icon, 20)}<span>${r.label}</span></button>`).join('')}
  </nav>
  <div class="canvas">
    <div class="crumb" id="crumb"></div>
    <div class="page"><div class="wrap" id="screen"></div></div>
  </div>
</div>
<div class="scrim" id="scrim" data-act="closeDrawer"></div>
<aside class="drawer" id="drawer" aria-hidden="true"></aside>
<div class="modal" id="modal"></div>
<div class="toast" id="toast"></div>
<button class="guidebtn" data-act="guide">${ic('help', 16)} POC guide</button>`;
  };

  P.render = function () {
    const s = S();
    const root = document.getElementById('app');
    if (!root.dataset.built) { root.innerHTML = P.shell(); root.dataset.built = '1'; }
    // rail highlight
    const on = railFor[s.screen] || '';
    root.querySelectorAll('.rail .rb').forEach(b => b.classList.toggle('on', b.dataset.key === on));
    const crumb = P.crumbs[s.screen] || [];
    document.getElementById('crumb').innerHTML = crumb.map((c, i) => (i ? '<span class="sep">/</span>' : '') + (i === crumb.length - 1 ? `<b>${esc(c)}</b>` : `<span>${esc(c)}</span>`)).join('') +
      `<span class="right"><span class="badge muted sentence">Example data · ${esc(P.TODAY)}</span></span>`;
    const fn = P.screens[s.screen] || P.screens.other;
    document.getElementById('screen').innerHTML = fn(s);
    // drawer
    const d = document.getElementById('drawer'), sc = document.getElementById('scrim');
    if (s.drawer && P.drawers[s.drawer.type]) {
      d.innerHTML = P.drawers[s.drawer.type](s);
      d.classList.add('show'); sc.classList.add('show'); d.setAttribute('aria-hidden', 'false');
    } else { d.classList.remove('show'); sc.classList.remove('show'); d.setAttribute('aria-hidden', 'true'); }
    const m = document.getElementById('modal');
    if (s.modal && P.modals[s.modal.type]) { m.innerHTML = `<div class="box">${P.modals[s.modal.type](s)}</div>`; m.classList.add('show'); }
    else { m.classList.remove('show'); m.innerHTML = ''; }
    if (P.focusId) { const el = document.getElementById(P.focusId); if (el) { el.focus(); try { el.setSelectionRange(el.value.length, el.value.length); } catch (e) { } } P.focusId = null; }
  };

  let toastTimer;
  P.toast = function (msg) {
    const t = document.getElementById('toast');
    t.innerHTML = ic('checkCircle', 16) + '<span>' + esc(msg) + '</span>';
    t.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
  };

  // ---- generic actions ----
  Object.assign(P.actions, {
    nav(arg) { S().screen = arg; S().drawer = null; S().modal = null; window.scrollTo({ top: 0 }); },
    tab(arg) { S().matrixTab = arg; S().screen = arg === 'matrix' ? 'matrix' : arg; },
    guide() { S().drawer = S().drawer && S().drawer.type === 'guide' ? null : { type: 'guide' }; },
    closeDrawer() { S().drawer = null; },
    closeModal() { S().modal = null; },
    toast(arg) { P.toast(arg); return false; },
    reset() { P.state = P.defaultState(); P.toast('POC reset to the sample data.'); },
    go(arg) { S().screen = arg; S().drawer = null; window.scrollTo({ top: 0 }); },
  });

  P.drawers.guide = function (s) {
    return `<div class="dh"><div><h2>POC guide</h2><div class="s">What this page is, and what to click. Nothing here is connected to a real system.</div></div><button class="x" data-act="closeDrawer" aria-label="Close">${ic('x', 18)}</button></div>
<div class="db">
  <div class="note">This is a clickable proof of concept for the <b>Approval Matrix</b>: one place to configure who approves what, across every feature. Names, amounts and dates are example data.</div>
  <div class="glist">${P.guide.map((g, i) => `<div class="grow"><div class="n">${i + 1}</div><div><div class="t">${esc(g.t)}</div><div class="s">${esc(g.s)}</div></div><button class="btn ghost sm" data-act="go" data-arg="${g.screen}">Open</button></div>`).join('')}</div>
</div>
<div class="df"><button class="btn ghost" data-act="reset">${ic('refresh', 14)} Reset POC</button><button class="btn primary" data-act="closeDrawer">Close</button></div>`;
  };

  P.screens.other = function () {
    return `<div class="empty placeholder">${ic('compass', 36)}<h2>Not part of this POC</h2><p>This area of the product is unchanged. The approval work lives under Settings → Approval Matrix and in the Approvals inbox on Home.</p><div style="margin-top:14px"><button class="btn primary" data-act="go" data-arg="matrix">Open the Approval Matrix</button></div></div>`;
  };

  // ---- state binding helpers ----
  function setPath(path, val) {
    const parts = path.split('.'); let o = S();
    for (let i = 0; i < parts.length - 1; i++) o = o[parts[i]];
    o[parts[parts.length - 1]] = val;
  }
  function coerce(el) {
    if (el.type === 'checkbox') return el.checked;
    if (el.dataset.num !== undefined) return Number(String(el.value).replace(/[^0-9.-]/g, '')) || 0;
    return el.value;
  }

  document.addEventListener('click', (ev) => {
    const el = ev.target.closest('[data-act]');
    if (!el) return;
    if (el.tagName === 'SUMMARY') return;
    const fn = P.actions[el.dataset.act];
    if (!fn) return;
    ev.preventDefault();
    const r = fn(el.dataset.arg, el, ev);
    if (r !== false) P.render();
  });
  document.addEventListener('change', (ev) => {
    const el = ev.target.closest('[data-bind]');
    if (!el) return;
    setPath(el.dataset.bind, coerce(el));
    if (el.dataset.after && P.actions[el.dataset.after]) P.actions[el.dataset.after](el.value, el);
    P.render();
  });
  document.addEventListener('input', (ev) => {
    const el = ev.target.closest('[data-bind][data-live]');
    if (!el) return;
    setPath(el.dataset.bind, coerce(el));
    P.focusId = el.id;
    P.render();
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && (S().drawer || S().modal)) { S().drawer = null; S().modal = null; P.render(); }
  });
  window.addEventListener('DOMContentLoaded', () => P.render());
})(window.POC);
