/* Screens: Approval Matrix (catalogue), People & backups, History */
(function (P) {
  const S = () => P.state;
  const esc = P.esc;

  function tabs(s) {
    const needs = P.catalogue.filter(c => c.status === 'needs').length;
    return `<div class="tabs">
      <button class="tab ${s.screen === 'matrix' ? 'on' : ''}" data-act="tab" data-arg="matrix">${ic('workflow', 15)} Matrix</button>
      <button class="tab ${s.screen === 'people' ? 'on' : ''}" data-act="tab" data-arg="people">${ic('users', 15)} People &amp; backups ${needs ? `<span class="cnt">${needs}</span>` : ''}</button>
      <button class="tab ${s.screen === 'history' ? 'on' : ''}" data-act="tab" data-arg="history">${ic('history', 15)} History</button>
    </div>`;
  }
  function hero(s, extra) {
    return `<div class="hero">
      <div><div class="eyebrow">${ic('stamp', 13)} Settings</div><h1>Approval Matrix</h1><div class="sub">Every check, in one place. Decide who signs off what, for each division and pay scheme, in plain words.</div></div>
      <div class="hero-r">${extra || ''}</div>
    </div>`;
  }
  P.matrixChrome = { tabs, hero };

  const routeHtml = (route) => route.map((r, i) => (i ? '<span class="ar">' + ic('arrowRight', 12) + '</span>' : '') + `<span>${esc(r)}</span>`).join('');

  P.screens.matrix = function (s) {
    const f = s.filter;
    const q = f.q.trim().toLowerCase();
    const rows = P.catalogue.filter(c => (f.area === 'all' || c.area === f.area) && (f.status === 'all' || c.status === f.status) && (!q || (c.name + ' ' + c.route.join(' ') + ' ' + c.applies + ' ' + c.sub).toLowerCase().includes(q)));
    const needs = P.catalogue.filter(c => c.status === 'needs');
    const counts = {}; P.catalogue.forEach(c => { counts[c.status] = (counts[c.status] || 0) + 1; });
    const areaRows = P.areas.map(a => {
      const rs = rows.filter(r => r.area === a.key);
      if (!rs.length) return '';
      return `<tr class="area"><td colspan="5"><span>${ic(a.icon, 14)} ${esc(a.name)} <span class="muted" style="font-weight:600;letter-spacing:0;text-transform:none">· ${rs.length}</span></span></td></tr>` +
        rs.map(r => {
          const m = P.statusMeta[r.status];
          const ver = r.id === 'payrun' && s.builder.publishedNow ? 'v3' : r.ver;
          const route = (r.id === 'payrun' && s.builder.publishedNow && P.routeLabels) ? P.routeLabels(s.builder) : r.route;
          return `<tr class="row" data-act="openProcess" data-arg="${r.id}">
            <td><div class="pn">${esc(r.name)}${r.fast ? `<span class="fl">${ic('zap', 10)} fast lane</span>` : ''}${r.money ? `<span class="fl" style="background:var(--slate-soft);color:var(--muted)" title="Recommended, not required">${ic('users', 10)} 2 people recommended</span>` : ''}</div><div class="route">${routeHtml(route)}</div></td>
            <td><div class="applies">${esc(r.applies)}<div class="s">${esc(r.sub)}</div></div></td>
            <td><span class="badge ${m.cls}"><span class="d"></span>${m.label}</span></td>
            <td class="tnum muted small">${esc(ver)}</td>
            <td class="chev">${ic('chevronRight', 16)}</td></tr>`;
        }).join('');
    }).join('');
    return `${hero(s, `<button class="btn ghost" data-act="toast" data-arg="Reads the Approval Matrix tab of your setup workbook and creates drafts for Rize Vietnam only. People stay proposals until an account is chosen.">${ic('fileSpreadsheet', 15)} Import from spreadsheet</button><button class="btn primary" data-act="presets">${ic('plus', 15)} Create workflow</button>`)}
${tabs(s)}
${s.presetsOpen ? `<div class="panel"><div class="panel-h"><div><h2>Start with a flow you already know</h2><div class="s">Presets stay drafts until you finish them. Nothing is published by choosing one.</div></div><button class="btn quiet" data-act="presets">${ic('x', 15)} Close</button></div>
  <div class="presets">${P.presets.map(p => `<button class="preset" data-act="usePreset" data-arg="${p.key}"><div class="t">${esc(p.t)}</div><div class="s">${esc(p.s)}</div><div class="r">${p.r.map((r, i) => (i ? ic('arrowRight', 11) : '') + `<span>${esc(r)}</span>`).join('')}</div></button>`).join('')}</div></div>` : ''}
${needs.length ? `<div class="attn">${ic('alert', 18)} <span>${needs.length} processes need people before they can be used.</span><span class="sp"></span><button class="btn ghost sm" data-act="filterStatus" data-arg="needs">Review setup</button></div>` : ''}
<div class="filters">
  <label class="search">${ic('search', 15)}<input id="mx-q" type="search" placeholder="Search processes, roles or people" value="${esc(f.q)}" data-bind="filter.q" data-live></label>
  <div class="fchips">
    <button class="fchip ${f.area === 'all' ? 'on' : ''}" data-act="filterArea" data-arg="all">All areas</button>
    ${P.areas.map(a => `<button class="fchip ${f.area === a.key ? 'on' : ''}" data-act="filterArea" data-arg="${a.key}">${esc(a.name)}</button>`).join('')}
  </div>
  <div class="fchips">
    <button class="fchip ${f.status === 'all' ? 'on' : ''}" data-act="filterStatus" data-arg="all">Any status</button>
    ${Object.keys(P.statusMeta).map(k => `<button class="fchip ${f.status === k ? 'on' : ''}" data-act="filterStatus" data-arg="${k}">${P.statusMeta[k].label}<span class="c">${counts[k] || 0}</span></button>`).join('')}
  </div>
</div>
<div class="tblwrap"><div class="tblx"><table class="tbl">
  <thead><tr><th style="width:44%">Process / approval route</th><th>Applies to</th><th>Status</th><th>Version</th><th></th></tr></thead>
  <tbody>${areaRows || `<tr><td colspan="5"><div class="empty">${ic('search', 24)}<div class="t">Nothing matches</div><div class="s">Try another word or clear the filters.</div></div></td></tr>`}</tbody>
</table></div></div>
<div class="note">A row is <b>Published</b> only when its workflow is published <i>and</i> the feature is connected to the engine. <b>Not connected yet</b> rows can be drafted but never published, so nothing pretends to be protected. Any process can be set to <b>No approval needed</b>; the row says so in words, and every use is logged. Recommendations such as "2 people" are advice you confirm at publish, never a lock.</div>`;
  };

  Object.assign(P.actions, {
    filterArea(a) { S().filter.area = a; },
    filterStatus(a) { S().filter.status = a; },
    presets() { S().presetsOpen = !S().presetsOpen; },
    usePreset(k) {
      const b = S().builder; const p = P.presets.find(x => x.key === k);
      S().presetsOpen = false;
      if (k === 'blank') { b.steps = [{ id: 'n1', kind: 'notify', title: 'Tell the payroll preparer', who: { mode: 'preparer' }, min: 0, cond: '' }]; b.tiers = false; }
      else if (k === 'officer') { b.steps = [{ id: 's1', kind: 'review', title: 'Officer review', who: { mode: 'role', role: 'payroll_mgr', scope: 'company' }, min: 0, cond: '' }, { id: 's2', kind: 'review', title: 'HR review', who: { mode: 'role', role: 'hr_lead', scope: 'division' }, min: 0, cond: '' }, { id: 's3', kind: 'approve', title: 'Finance approval', who: { mode: 'role', role: 'finance', scope: 'company' }, min: 0, cond: '' }]; b.tiers = false; }
      else if (k === 'mgr_hr') { b.steps = [{ id: 's1', kind: 'review', title: 'Manager review', who: { mode: 'manager' }, min: 0, cond: '' }, { id: 's2', kind: 'approve', title: 'HR approval', who: { mode: 'role', role: 'hr_lead', scope: 'division' }, min: 0, cond: '' }]; b.tiers = false; }
      else if (k === 'joint') { b.steps = [{ id: 's1', kind: 'joint', title: 'Joint sign-off', who: { mode: 'people', people: ['nithya', 'monica', 'thao'], all: true }, min: 0, cond: '' }]; b.tiers = false; }
      else if (k === 'four') { b.steps = [{ id: 's1', kind: 'review', title: 'Independent review', who: { mode: 'team', team: 'Vietnam payroll desk' }, min: 0, cond: '' }, { id: 's2', kind: 'approve', title: 'Owner approval', who: { mode: 'role', role: 'scheme_owner', scope: 'company' }, min: 0, cond: '' }]; b.tiers = false; }
      else { S().builder = P.defaultBuilder(); }
      S().builder.name = k === 'tiers' ? 'Pay run approval' : (p ? p.t : 'New workflow');
      S().builder.step = 1; S().builder.coverage = null; S().screen = 'builder';
      P.toast('Draft created from "' + (p ? p.t : 'Start blank') + '". Nothing is published yet.');
    },
    openProcess(id) {
      const c = P.catalogue.find(x => x.id === id);
      if (!c) return;
      if (c.status === 'soon') { P.toast(c.name + ' is not connected to the engine yet. You can draft it, but Publish stays unavailable.'); return false; }
      if (c.open === 'scheme') { S().screen = 'scheme'; return; }
      if (c.id !== 'payrun' && c.id !== 'timesheet') { P.toast('In the POC only "Pay run" opens the full builder. ' + c.name + ' would open the same builder with its own steps.'); return false; }
      S().builder.step = 2; S().screen = 'builder'; window.scrollTo({ top: 0 });
    },
  });

  // ---------- People & backups ----------
  P.resolveSeat = function (role, division) {
    const r = S().resp;
    const exact = division && r[role + '|' + division];
    if (exact) return { ...exact, via: P.scopes[division] };
    const co = r[role + '|company'];
    const def = P.roles[role];
    if (co && (def.fallback || !division)) return { ...co, via: 'Vietnam company' + (division ? ' (fallback)' : '') };
    return null;
  };
  P.coverFor = function (pk) {
    const d = S().delegations.find(x => x.active && x.from === pk);
    return d ? d.to : null;
  };

  P.screens.people = function (s) {
    const cols = ['company', 'retail', 'operations'];
    const rolesOrder = ['hr_lead', 'finance', 'payroll_mgr', 'director', 'scheme_owner', 'budget', 'signatory', 'access'];
    const gaps = rolesOrder.filter(r => !P.roles[r].fallback).flatMap(r => P.divisions.filter(d => !s.resp[r + '|' + d]).map(d => ({ r, d })));
    const rows = rolesOrder.map(r => {
      const def = P.roles[r];
      return `<tr><td class="role">${esc(def.name)}<div class="s">${esc(def.desc)} · ${def.fallback ? 'company person covers a division with no one assigned' : 'each division needs its own person'}</div></td>` +
        cols.map(c => {
          const v = s.resp[r + '|' + c];
          if (v) {
            const cover = P.coverFor(v.person);
            return `<td><div class="cell">${v.pool ? `<div class="person"><span class="av sm">${v.pool.length}</span><div><div class="n">Any of ${v.pool.map(P.pshort).join(', ')}</div><div class="t">Pool · mandate on file</div></div></div>` : `<div class="person"><span class="av sm">${P.people[v.person].ini}</span><div><div class="n">${esc(P.pname(v.person))}${cover ? ` <span class="badge warn sentence">${ic('plane', 10)} ${esc(P.pshort(cover))} covering</span>` : ''}</div><div class="t">${esc(P.people[v.person].title)} · since ${esc(v.from)}</div></div></div>`}${v.backup ? `<div class="bk">${ic('repeat', 11)} Backup: ${esc(P.pshort(v.backup))}</div>` : (v.pool ? '' : `<div class="bk muted">${ic('repeat', 11)} No backup <button class="btn quiet xs" data-act="toast" data-arg="Choose a backup for this seat.">Choose</button></div>`)}</div></td>`;
          }
          if (c === 'company') return `<td><div class="cell"><span class="inh">Not set at company level</span></div></td>`;
          if (def.fallback) { const co = s.resp[r + '|company']; return `<td><div class="cell"><span class="inh">${co ? 'Inherits ' + esc(P.pshort(co.person)) + ' from company' : 'No one'}</span></div></td>`; }
          return `<td><div class="cell gap"><span class="badge err sentence">${ic('userX', 11)} Needs a person</span><button class="btn outline sm" data-act="assignOpen" data-arg="${r}|${c}">Assign</button></div></td>`;
        }).join('') + '</tr>';
    }).join('');
    return `${hero(s, `<button class="btn primary" data-act="handoverOpen">${ic('plane', 15)} I'm away · set a hand-over</button>`)}
${tabs(s)}
${gaps.length ? `<div class="attn">${ic('alert', 18)} <span>${gaps.length} seat${gaps.length > 1 ? 's' : ''} ${gaps.length > 1 ? 'have' : 'has'} no one assigned: ${gaps.map(g => P.roles[g.r].name + ' for ' + P.scopes[g.d]).join(', ')}. Requests for that scope cannot be submitted.</span><span class="sp"></span><button class="btn ghost sm" data-act="assignOpen" data-arg="${gaps[0].r}|${gaps[0].d}">Assign now</button></div>` : `<div class="attn green">${ic('checkCircle', 18)} <span>Every seat has a person. Changing a person here changes new requests only; requests already in progress keep their people.</span></div>`}
<div class="panel"><div class="panel-h"><div><h2>Who fills each role, where</h2><div class="s">A role is a responsibility, not a permission. Assigning someone here never gives them access; the picker tells you when a person still needs a role.</div></div></div>
<div class="respwrap"><div class="tblx"><table class="resp"><thead><tr><th style="width:30%">Role</th>${cols.map(c => `<th>${esc(P.scopes[c])}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div></div></div>
<div class="panel"><div class="panel-h"><div><h2>Hand-overs</h2><div class="s">Time-boxed cover for a seat. Every card shows "covering for", and the decision is recorded under both names.</div></div><button class="btn ghost sm" data-act="handoverOpen">${ic('plus', 13)} Add a hand-over</button></div>
<div class="deleg">${s.delegations.map(d => `<div class="delrow"><span class="av lg">${P.people[d.to].ini}</span><div><div class="t">${esc(P.pshort(d.to))} covers for ${esc(P.pshort(d.from))} · ${esc(d.seat)}</div><div class="s">${esc(d.start)} to ${esc(d.end)} · ${esc(d.reason)} · set by ${esc(P.pshort(d.from))}</div></div><label class="switch ${d.active ? 'on' : 'off'}" data-act="toggleDeleg" data-arg="${d.id}"><i></i>${d.active ? 'Active now (preview)' : 'Starts ' + esc(d.start) + ' · switch on to preview'}</label></div>`).join('')}</div></div>`;
  };

  P.drawers.assign = function (s) {
    const [r, d] = s.people.assignDrawer.split('|');
    const cands = ['duc', 'nithya', 'thaominh', 'monica'];
    const pick = s.people.assignPick || '';
    return `<div class="dh"><div><h2>Choose the ${esc(P.roles[r].name)} for ${esc(P.scopes[d])}</h2><div class="s">Only people with an account and the right role are listed. Choosing someone here changes new requests only.</div></div><button class="x" data-act="closeDrawer" aria-label="Close">${ic('x', 18)}</button></div>
<div class="db">
  <div class="plist">${cands.map(k => { const ok = k !== 'thaominh'; return `<div class="prow ${pick === k ? 'on' : ''}" data-act="assignPick" data-arg="${k}"><span class="av">${P.people[k].ini}</span><div><div class="n" style="font-weight:700">${esc(P.pname(k))}</div><div class="t small muted">${esc(P.people[k].title)} · ${ok ? 'Has the role' : 'Needs the "Payroll manager" role first'}</div></div>${ok ? '' : `<span class="badge warn sentence">Needs permission</span>`}<span class="cb">${pick === k ? ic('check', 12) : ''}</span></div>`; }).join('')}</div>
  <div class="note">${ic('info', 13)} Nithya already holds this role for Retail. One person may cover several divisions, but a single person cannot be the only reviewer <i>and</i> the only approver on the same request.</div>
</div>
<div class="df"><button class="btn ghost" data-act="closeDrawer">Cancel</button><button class="btn primary" data-act="assignSave" ${pick ? '' : 'disabled'}>Assign ${pick ? esc(P.pshort(pick)) : ''}</button></div>`;
  };
  P.drawers.handover = function (s) {
    return `<div class="dh"><div><h2>Set a hand-over</h2><div class="s">Someone covers your seats for a while. It shows on every card, and it ends by itself.</div></div><button class="x" data-act="closeDrawer" aria-label="Close">${ic('x', 18)}</button></div>
<div class="db">
  <div class="field"><label>Who is away</label><select class="input"><option>Nithya · HR lead, Payroll manager</option><option>Monica · Finance approver</option></select></div>
  <div class="field"><label>Who covers</label><select class="input"><option>Monica · Finance Manager</option><option>Duc Pham · Operations manager</option></select></div>
  <div class="ex"><div class="grid2"><div class="field"><label>From</label><input class="input" type="date" value="2026-09-21"></div><div class="field"><label>To</label><input class="input" type="date" value="2026-09-25"></div></div></div>
  <div class="field"><label>Which seats</label><div class="checkrow on"><span class="cb">${ic('check', 12)}</span>HR lead · Vietnam / Retail</div><div class="checkrow on"><span class="cb">${ic('check', 12)}</span>Payroll manager · Vietnam</div></div>
  <div class="field"><label>Reason (recorded)</label><input class="input" placeholder="Annual leave"></div>
  <div class="note amber">${ic('alert', 13)} Monica is also the backup for HR lead. During this hand-over she would hold both seats on a pay run, so the run's Finance step will go to her backup, Thao, instead.</div>
</div>
<div class="df"><button class="btn ghost" data-act="closeDrawer">Cancel</button><button class="btn primary" data-act="handoverSave">Save hand-over</button></div>`;
  };
  Object.assign(P.actions, {
    assignOpen(arg) { S().people.assignDrawer = arg; S().people.assignPick = ''; S().drawer = { type: 'assign' }; },
    assignPick(k) { S().people.assignPick = k; },
    assignSave() {
      const s = S(); const [r, d] = s.people.assignDrawer.split('|');
      s.resp[r + '|' + d] = { person: s.people.assignPick, backup: null, from: '12 Sep 2026' };
      s.drawer = null;
      const t = P.catalogue.find(c => c.id === 'timesheet'); if (t && r === 'hr_lead') { /* timesheet gap is a manager gap, unrelated */ }
      P.toast(P.pshort(s.people.assignPick) + ' is now ' + P.roles[r].name + ' for ' + P.scopes[d] + '. New requests use this; nothing in progress changes.');
      if (s.builder.coverage) P.actions.coverage && P.actions.coverage();
    },
    handoverOpen() { S().drawer = { type: 'handover' }; },
    handoverSave() { S().delegations.push({ id: 'd' + Date.now(), from: 'nithya', to: 'monica', seat: 'HR lead · Vietnam / Retail, Payroll manager · Vietnam', start: '21 Sep 2026', end: '25 Sep 2026', reason: 'Annual leave', active: true }); S().drawer = null; P.toast('Hand-over saved. Monica covers from 21 to 25 Sep.'); },
    toggleDeleg(id) { const d = S().delegations.find(x => x.id === id); d.active = !d.active; P.toast(d.active ? P.pshort(d.to) + ' now covers ' + P.pshort(d.from) + '. Check the builder example and the inbox.' : 'Hand-over off. ' + P.pshort(d.from) + ' keeps her seat on new requests.'); },
  });

  // ---------- History ----------
  P.screens.history = function (s) {
    return `${hero(s)}${tabs(s)}
<div class="panel"><div class="panel-h"><div><h2>What changed, and who did it</h2><div class="s">Publishes, decisions, exceptions, hand-overs and reassignments. The same events feed the Audit console.</div></div><div class="fchips"><button class="fchip on">All</button><button class="fchip">Publishes</button><button class="fchip">Decisions</button><button class="fchip">Exceptions</button><button class="fchip">Hand-overs</button></div></div>
<div class="hist">${(s.builder.publishedNow ? [{ when: 'Sat 12 Sep, now', who: 'admin', t: 'Published Pay run approval · v3', s: 'Added Country director sign-off from ₫600,000,000 · Finance approval from ₫300,000,000 · starts 01 Oct 2026, 09:00' }] : []).concat(P.history).map(h => `<div class="hrow"><div class="when">${esc(h.when)}</div><span class="av sm" title="${esc(P.pname(h.who))}">${P.people[h.who].ini}</span><div><div class="t">${esc(h.t)}</div><div class="s">${esc(h.s)}</div></div></div>`).join('')}</div></div>`;
  };
})(window.POC);
