/* ---------- changes (live or planned) ---------- */
const short = p => p ? (p.open ? `the open ${p.title} role` : p.name.split(' ').pop()) : 'nobody';
function applyChange(c) {
  // c: {kind, id, from, to, label, note}
  const p = byId(c.id);
  if (c.kind === 'move') { c.from = p.managerId; p.managerId = c.to; }
  if (c.kind === 'dotted') { c.from = p.dotted; p.dotted = c.to; }
  if (c.kind === 'unassign') { c.from = p.managerId; p.managerId = null; }
  if (c.kind === 'fill') { c.from = null; p.open = false; p.name = c.name; p.ini = c.name.split(' ').slice(-1)[0][0] + c.name[0]; p.status = 'new'; p.joined = TODAY; p.hiring = ''; }
  if (c.kind === 'newrole') { const n = {id: 7000 + S.changes.length + S.undone.length, name: '', ini: '', title: c.title, dept: byId(c.to).dept, loc: byId(c.to).loc, type: 'Full-time', joined: TODAY, managerId: c.to, dotted: null, open: true, hiring: 'Open · just added', status: '', collapsed: false}; DATA.push(n); c.id = n.id; }
  if (c.kind === 'addexisting') { c.from = p.managerId; p.managerId = c.to; }
  if (c.kind === 'swap') { const a = byId(c.id), b = byId(c.to); c.from = a.managerId; const ka = kids(a.id).map(k => k.id), kb = kids(b.id).map(k => k.id); const ma = a.managerId, mb = b.managerId; a.managerId = mb; b.managerId = ma; ka.forEach(k => byId(k).managerId = b.id); kb.forEach(k => byId(k).managerId = a.id); c.ka = ka; c.kb = kb; }
  // Planning mode stacks changes in the plan; live mode applies at once and keeps a short undo trail of its own.
  if (S.draft) { S.changes.push(c); S.undone = []; } else { S.live.push(c); toast(c.label, 'check', () => undo()); }
  if (byId(c.to)) byId(c.to).collapsed = false;
  render();
}
function revert(c) {
  const p = byId(c.id);
  if (c.kind === 'move' || c.kind === 'unassign' || c.kind === 'addexisting') p.managerId = c.from;
  if (c.kind === 'dotted') p.dotted = c.from;
  if (c.kind === 'fill') { p.open = true; p.name = ''; p.ini = ''; p.status = ''; p.hiring = 'Open role'; }
  if (c.kind === 'newrole') DATA.splice(DATA.findIndex(x => x.id === c.id), 1);
  if (c.kind === 'swap') { const a = byId(c.id), b = byId(c.to); const ma = a.managerId, mb = b.managerId; a.managerId = mb; b.managerId = ma; c.ka.forEach(k => byId(k).managerId = a.id); c.kb.forEach(k => byId(k).managerId = b.id); }
}
function undo() { const c = S.draft ? S.changes.pop() : S.live.pop(); if (!c) return; revert(c); if (S.draft) S.undone.push(c); toast(`Undone: ${c.label}`, 'undo'); render(); }
function redo() { if (!S.draft) return; const c = S.undone.pop(); if (!c) return; const keep = S.undone; applyChange(c); S.undone = keep; }

/* ---------- dialogs ---------- */
function openMoveConfirm(from, to) { S.dlg = {kind: 'move', from, to}; render(); }
function dialogHtml() {
  const d = S.dlg; if (!d) return '';
  const wrap = (ic, title, sub, body, foot) => `<div class="scrim" data-act="closedlg"><div class="dlg" data-act="noop"><div class="dh"><span class="bd">${I(ic)}</span><div><h3>${title}</h3><small>${sub}</small></div></div><div class="db">${body}</div><div class="df">${foot}</div></div></div>`;
  const picker = (list, sel, act, q = '') => `<div class="field"><label>Search</label><input id="pick-q" placeholder="Type a name or title…" value="${esc(q)}"></div><div class="picker">${list.filter(p => !q || (p.name + p.title).toLowerCase().includes(q.toLowerCase())).slice(0, 40).map(p => `<div class="rep ${sel === p.id ? 'on' : ''}" data-act="${act}:${p.id}">${avatar(p)}<span><b>${p.open ? 'Open role' : esc(p.name)}</b><small>${esc(p.title)} · ${esc(p.dept)}${kids(p.id).length ? ` · ${kids(p.id).length} reports` : ''}</small></span>${sel === p.id ? `<span class="ic" style="margin-left:auto;color:var(--green)">${I('check')}</span>` : ''}</div>`).join('') || `<div style="padding:14px;color:var(--muted);font-size:13px">No match.</div>`}</div>`;
  const when = S.draft ? `<small style="color:var(--amber);font-weight:600">${I('pencil')} Goes into your planned changes — nothing moves until you publish.</small>` : `<small style="color:var(--muted)">${I('info')} Takes effect straight away. The person, both managers and Payroll are told.</small>`;

  if (d.kind === 'move') {
    const p = byId(d.from), m = byId(d.to), old = byId(p.managerId), team = descendants(p.id).length;
    const body = `<div class="opt ${!d.only ? 'on' : ''}" data-act="dlgopt:team">${I(team ? 'users' : 'user')}<span><b>${team ? `Move ${short(p)} and their whole team (${team} ${team === 1 ? 'person' : 'people'})` : `Move ${short(p)}`}</b><small>${team ? `Everyone who reports to ${short(p)} comes along. The usual choice.` : `Nobody reports to ${short(p)}, so only they move.`}</small></span></div>
      ${team ? `<div class="opt ${d.only ? 'on' : ''}" data-act="dlgopt:only">${I('user')}<span><b>Move only ${short(p)}</b><small>Their ${team} ${team === 1 ? 'report stays' : 'reports stay'} with ${short(old)}.</small></span></div>` : ''}
      <div class="impact"><b>What changes</b><ul><li>${esc(p.name)} will report to <b>${esc(m.name || 'the open ' + m.title + ' role')}</b>${old ? ` instead of ${esc(old.name)}` : ''}.</li>
      ${m.dept !== p.dept ? `<li>Team changes from ${esc(p.dept)} to <b>${esc(m.dept)}</b> — the pay data file and approvals follow the new team.</li>` : ''}
      ${kids(m.id).length + 1 >= 10 ? `<li style="color:var(--amber)">${short(m)} will have ${kids(m.id).length + 1} direct reports — that is a wide span.</li>` : ''}
      ${m.open ? `<li style="color:var(--amber)">${short(m)} is not filled yet — ${short(p)} will have no actual manager until it is.</li>` : ''}
      <li>Leave and expense approvals go to the new manager from the next request.</li></ul></div>
      <div class="field" style="margin-top:12px"><label>Effective from</label><input type="date" value="2026-11-04"></div>${when}`;
    return wrap('move', `Move ${short(p)} under ${short(m)}?`, `${esc(p.title)} → reports to ${esc(m.title)}`, body,
      `<button class="btn outline" data-act="closedlg">Cancel</button><button class="btn primary" data-act="dlgmove">${I('check')} ${S.draft ? 'Add to plan' : 'Move now'}</button>`);
  }
  if (d.kind === 'changemgr') {
    const p = byId(d.id); const list = DATA.filter(x => x.id !== p.id && !isDesc(p.id, x.id) && !x.future);
    return wrap('move', `Who should ${short(p)} report to?`, `${esc(p.title)} · currently ${p.managerId ? 'reports to ' + esc(byId(p.managerId).name) : 'has no manager'}`,
      picker(list, d.sel, 'pick', d.q) + `<div style="margin-top:10px">${when}</div>`,
      `<button class="btn outline" data-act="closedlg">Cancel</button><button class="btn primary" data-act="dlgpickmgr" ${d.sel ? '' : 'disabled style="opacity:.5"'}>${I('check')} Continue</button>`);
  }
  if (d.kind === 'dotted') {
    const p = byId(d.id); const list = DATA.filter(x => x.id !== p.id && x.id !== p.managerId && !x.open && !x.future);
    return wrap('dotted', `Add a dotted-line manager for ${short(p)}`, `A second person they also report to — for projects or a matrix team. The solid line stays with ${esc(byId(p.managerId)?.name || 'nobody')}.`,
      picker(list, d.sel, 'pick', d.q) + `<div style="margin-top:10px">${when}</div>`,
      `<button class="btn outline" data-act="closedlg">Cancel</button><button class="btn primary" data-act="dlgdotted" ${d.sel ? '' : 'disabled style="opacity:.5"'}>${I('check')} Add dotted line</button>`);
  }
  if (d.kind === 'addmember') {
    const m = byId(d.id);
    const body = `<div class="opt ${d.mode === 'existing' ? 'on' : ''}" data-act="dlgmode:existing">${I('users')}<span><b>Someone already here</b><small>Move an existing employee into ${short(m)}'s team.</small></span></div>
      <div class="opt ${d.mode === 'role' ? 'on' : ''}" data-act="dlgmode:role">${I('briefcase')}<span><b>A new open role</b><small>A dashed card appears under ${short(m)} and Hiring gets the job to fill.</small></span></div>
      <div class="opt ${d.mode === 'hire' ? 'on' : ''}" data-act="dlgmode:hire">${I('userplus')}<span><b>A new starter</b><small>Opens the new-employee form with ${short(m)} already set as manager.</small></span></div>
      ${d.mode === 'existing' ? picker(DATA.filter(x => x.id !== m.id && x.managerId !== m.id && !x.open && !x.future && !isDesc(m.id, x.id) && !isDesc(x.id, m.id)), d.sel, 'pick', d.q) : ''}
      ${d.mode === 'role' ? `<div class="field"><label>Job title</label><input id="role-title" placeholder="e.g. Field agronomist" value="${esc(d.title || '')}"></div><div class="field"><label>Why</label><select><option>Growth — new position</option><option>Backfill — someone is leaving</option><option>Replacement — cover for leave</option></select></div>` : ''}
      <div style="margin-top:6px">${when}</div>`;
    const ok = d.mode === 'existing' ? !!d.sel : d.mode === 'role' ? !!(d.title || '').trim() : d.mode === 'hire';
    return wrap('userplus', `Add someone to ${short(m)}'s team`, `${esc(m.title)} · ${kids(m.id).length} direct reports today`, body,
      `<button class="btn outline" data-act="closedlg">Cancel</button><button class="btn primary" data-act="dlgadd" ${ok ? '' : 'disabled style="opacity:.5"'}>${I('check')} ${d.mode === 'hire' ? 'Open the form' : d.mode === 'role' ? 'Add the role' : 'Add to team'}</button>`);
  }
  if (d.kind === 'fill') {
    const r = byId(d.id);
    return wrap('usercheck', `Fill the ${esc(r.title)} role`, `Reports to ${esc(byId(r.managerId)?.name || 'nobody')} · ${esc(r.dept)}`,
      `<div class="opt ${d.mode === 'existing' ? 'on' : ''}" data-act="dlgmode:existing">${I('users')}<span><b>Promote or move someone already here</b></span></div>
       <div class="opt ${d.mode === 'hire' ? 'on' : ''}" data-act="dlgmode:hire">${I('userplus')}<span><b>A new starter</b><small>Opens the new-employee form with the title, team and manager already filled in.</small></span></div>
       ${d.mode === 'existing' ? picker(DATA.filter(x => !x.open && !x.future && x.id !== r.managerId), d.sel, 'pick', d.q) : ''}<div style="margin-top:6px">${when}</div>`,
      `<button class="btn outline" data-act="closedlg">Cancel</button><button class="btn primary" data-act="dlgfill" ${d.mode === 'hire' || d.sel ? '' : 'disabled style="opacity:.5"'}>${I('check')} ${d.mode === 'hire' ? 'Open the form' : 'Fill the role'}</button>`);
  }
  if (d.kind === 'publish') {
    const n = S.changes.length;
    return wrap('send', `Publish ${n} planned ${n === 1 ? 'change' : 'changes'}?`, `Everything below goes live together`,
      `${S.changes.map(c => `<div class="chg"><span class="bd ${c.bd || ''}">${I(c.ic || 'move')}</span><span><b>${esc(c.label)}</b><small>${esc(c.note || '')}</small></span></div>`).join('')}
       <div class="impact"><b>Before it goes live</b><ul><li>Your approver <b>Head of People &amp; Culture</b> gets one request covering all ${n}.</li><li>Each person and both their managers get a note on the day it takes effect.</li><li>Payroll, leave approvals and the pay data file update themselves.</li></ul></div>
       <div class="field" style="margin-top:12px"><label>Effective from</label><input type="date" value="2026-12-01"></div>
       <div class="field"><label>Message to the approver (optional)</label><input placeholder="e.g. Q1 restructure of the Southern field team"></div>`,
      `<button class="btn outline" data-act="closedlg">Keep planning</button><button class="btn primary" data-act="dlgpublish">${I('send')} Send for approval</button>`);
  }
  if (d.kind === 'share') {
    return wrap('link', 'Share a read-only link', 'Anyone in the company can open it. No pay, no personal details — just names, titles and teams.',
      `<div class="field"><label>Link</label><input readonly value="https://demo.payobook.com/org/share/7f3a9c…"></div><div class="field"><label>Expires</label><select><option>In 30 days</option><option>In 7 days</option><option>Never — until I turn it off</option></select></div><div class="field"><label>Who</label><select><option>Anyone signed in to Payobook</option><option>Only people in ${esc(S.filters.dept || 'Leadership')}</option><option>Anyone with the link (no sign-in)</option></select></div>`,
      `<button class="btn outline" data-act="closedlg">Close</button><button class="btn primary" data-act="copylink">${I('link')} Copy link</button>`);
  }
  if (d.kind === 'suggest') {
    return wrap('wand', 'Suggested chart', 'Built from team names and job titles. Nothing is saved until you press Use it.',
      `<div class="impact"><b>How it was worked out</b><ul><li>“Head of …”, “Chief …” and “… Lead” titles become managers of their team.</li><li>Everyone else reports to the lead of their team; teams without a lead report to the CEO.</li><li>${DATA.filter(p => !p.open).length - 1} of ${DATA.filter(p => !p.open).length} people get a manager. 0 left over.</li></ul></div>
       <small style="display:block;margin-top:10px;color:var(--muted)">You can drag anyone afterwards — this is a starting point, not a decision.</small>`,
      `<button class="btn outline" data-act="closedlg">Not now</button><button class="btn primary" data-act="dlgsuggest">${I('check')} Use it</button>`);
  }
  if (d.kind === 'form') {
    return wrap('userplus', d.title, d.sub, `<div class="impact">${I('info')} In the real product this opens the <b>New employee</b> form with the manager, team and title already filled in. The person appears on the chart the moment the form is saved.</div>`, `<button class="btn primary" data-act="closedlg">Got it</button>`);
  }
  return '';
}

/* ---------- side panel ---------- */
function renderSide() {
  const side = $('#side');
  if (!S.side) { side.classList.add('hide'); return; }
  side.classList.remove('hide');
  if (S.side === 'changes') { side.innerHTML = changesPanel(); return; }
  const p = byId(S.side) || FUTURE.find(f => f.id === S.side); if (!p) { S.side = null; side.classList.add('hide'); return; }
  const chain = ancestors(p.id).reverse();
  const reps = kids(p.id), dn = descendants(p.id).length;
  const tab = S.sideTab;
  side.innerHTML = `<div class="sh"><h3>${I(p.open ? 'briefcase' : 'user')} ${p.open ? 'Open role' : 'Person'}</h3><div style="display:flex;gap:4px"><button class="btn icon ghost" data-act="ctx:${p.id}" title="More">${I('more')}</button><button class="btn icon ghost" data-act="closeside" title="Close (Esc)">${I('x')}</button></div></div>
  <div class="sb">
    <div class="prof">${avatar(p, 'av lg')}<div><div class="nm">${p.open ? esc(p.title) : esc(p.name)}</div><div class="jt">${p.open ? esc(p.hiring || 'Open role') : esc(p.title)}</div><div class="dp">${esc(p.dept)} · ${esc(p.loc)}</div></div></div>
    ${p.statusNote ? `<div class="banner-sm" style="margin-top:12px;padding:8px 10px;border-radius:10px;background:var(--amber-soft);color:#7A3A06;font-size:12.5px">${I('info')} ${esc(p.statusNote)}</div>` : ''}
    <div class="chain">${chain.length ? chain.map((a, i) => `${i ? I('chevr') : ''}<button data-act="select:${a.id}" title="${esc(a.title)}">${a.open ? I('briefcase') : esc(a.name.split(' ').pop())}</button>`).join('') + I('chevr') : ''}<span style="font-weight:700;color:var(--ink2)">${p.open ? 'this role' : esc(p.name.split(' ').pop())}</span>${!chain.length && !p.open ? `<span class="tag rose">${I('userx')} No manager</span>` : ''}</div>
    <div class="facts">
      <div class="fact"><small>Reports to</small><b>${p.managerId ? esc(byId(p.managerId)?.name || byId(p.managerId)?.title) : '—'}</b></div>
      <div class="fact"><small>Dotted line to</small><b>${p.dotted ? esc(byId(p.dotted).name) : '—'}</b></div>
      <div class="fact"><small>Team size</small><b>${reps.length} direct · ${dn} total</b></div>
      <div class="fact"><small>Level</small><b>${depth(p.id) + 1} of ${Math.max(...DATA.map(x => depth(x.id))) + 1}</b></div>
      <div class="fact"><small>With us</small><b>${p.open ? '—' : tenure(p)}</b></div>
      <div class="fact"><small>Employment</small><b>${esc(p.type)}</b></div>
      <div class="fact lock"><small>Pay band</small><b>${I('lock')} People managers only</b></div>
      <div class="fact"><small>Employee record</small><b><a href="#" style="color:var(--p)">Open ${I('arrowr', 12)}</a></b></div>
    </div>
    <div class="stabs"><button class="${tab === 'team' ? 'on' : ''}" data-act="stab:team">Team (${reps.length})</button><button class="${tab === 'peers' ? 'on' : ''}" data-act="stab:peers">Peers</button><button class="${tab === 'history' ? 'on' : ''}" data-act="stab:history">History</button></div>
    ${tab === 'team' ? (reps.length ? reps.map(r => `<div class="rep" data-act="select:${r.id}">${avatar(r)}<span><b>${r.open ? 'Open role' : esc(r.name)}</b><small>${esc(r.title)}${kids(r.id).length ? ` · ${kids(r.id).length} reports` : ''}</small></span>${I('chevr')}</div>`).join('') : `<div style="color:var(--muted);font-size:13px;padding:8px 6px">Nobody reports to ${short(p)} yet. <a href="#" data-act="addmember:${p.id}" style="color:var(--p);font-weight:600">Add a team member</a></div>`) : ''}
    ${tab === 'peers' ? (p.managerId ? kids(p.managerId).filter(x => x.id !== p.id).map(r => `<div class="rep" data-act="select:${r.id}">${avatar(r)}<span><b>${r.open ? 'Open role' : esc(r.name)}</b><small>${esc(r.title)}</small></span>${I('chevr')}</div>`).join('') || `<div style="color:var(--muted);font-size:13px;padding:8px 6px">No peers — ${short(p)} is the only one reporting to ${short(byId(p.managerId))}.</div>` : `<div style="color:var(--muted);font-size:13px;padding:8px 6px">Top of the chart — no peers.</div>`) : ''}
    ${tab === 'history' ? ((HISTORY[p.id] || []).concat(S.changes.filter(c => c.id === p.id).map(c => ({when: TODAY, what: c.label + (S.draft ? ' (planned)' : ''), who: 'You'}))).sort((a, b) => b.when - a.when).map(h => `<div class="hist"><span class="dot"></span><span><b>${esc(h.what)}</b><small>${fmtD(h.when)} · by ${esc(h.who)}</small></span></div>`).join('') || `<div class="hist"><span class="dot"></span><span><b>${p.open ? 'Role created' : 'Joined'}</b><small>${fmtD(p.joined)}</small></span></div>`) : ''}
  </div>
  <div class="sf">
    ${p.open ? `<button class="btn primary sm" data-act="fill:${p.id}">${I('usercheck')} Fill this role</button>` : `<button class="btn primary sm" data-act="addmember:${p.id}">${I('userplus')} Add team member</button>`}
    <button class="btn outline sm" data-act="changemgr:${p.id}">${I('move')} Change manager</button>
    ${!p.open ? `<button class="btn outline sm" data-act="dotted:${p.id}">${I('dotted')} Dotted line</button>` : ''}
  </div>`;
}
function changesPanel() {
  const ic = {move: 'move', dotted: 'dotted', unassign: 'userx', fill: 'usercheck', newrole: 'briefcase', addexisting: 'userplus', swap: 'swap'};
  const bd = {fill: 'green', newrole: 'p', unassign: 'rose', addexisting: 'green'};
  return `<div class="sh"><h3>${I('pencil')} Planned changes</h3><button class="btn icon ghost" data-act="closeside">${I('x')}</button></div>
  <div class="sb">${S.changes.length ? S.changes.map((c, i) => `<div class="chg"><span class="bd ${bd[c.kind] || ''}">${I(ic[c.kind])}</span><span><b>${esc(c.label)}</b><small>${esc(c.note || '')}</small></span><button class="rm" data-act="rmchange:${i}" title="Remove this change">${I('trash')}</button></div>`).join('') : `<div style="color:var(--muted);font-size:13px;text-align:center;padding:30px 10px">${I('move', 28)}<br><br>Drag anyone onto a new manager, or use the buttons on a card. Changes stack here; nothing is real until you publish.</div>`}
    ${S.changes.length ? `<div class="impact" style="margin-top:4px"><b>Effect of the plan</b><ul><li>${new Set(S.changes.map(c => c.id)).size} people move or change.</li><li>${S.changes.filter(c => c.kind === 'newrole').length} new open roles for Hiring.</li><li>Managers with 10+ reports after the plan: <b>${DATA.filter(p => kids(p.id).length >= 10).length}</b>.</li></ul></div>` : ''}
  </div>
  <div class="sf"><button class="btn primary sm" data-act="publish" ${S.changes.length ? '' : 'disabled style="opacity:.5"'}>${I('send')} Publish</button><button class="btn outline sm" data-act="undo" ${S.changes.length ? '' : 'disabled style="opacity:.5"'}>${I('undo')} Undo</button><button class="btn outline sm" data-act="redo" ${S.undone.length ? '' : 'disabled style="opacity:.5"'}>${I('redo')}</button><button class="btn ghost sm danger" data-act="discard">Discard plan</button></div>`;
}
function renderDraftbar() {
  const b = $('#draftbar');
  if (!S.draft) { b.classList.add('hide'); return; }
  b.classList.remove('hide');
  b.innerHTML = `${I('pencil')}<span class="grow"><b>Planning mode.</b> Nothing you do here changes the real chart until you publish. ${S.changes.length ? `<b>${S.changes.length}</b> change${S.changes.length === 1 ? '' : 's'} so far — amber outline marks who moved, a dashed red line shows where they came from.` : 'Drag people around, add roles, try things.'}</span>
    <button class="btn outline sm" data-act="side:changes">${I('list')} See changes</button><button class="btn outline sm" data-act="undo" title="⌘Z">${I('undo')}</button><button class="btn outline sm" data-act="redo" title="⇧⌘Z">${I('redo')}</button><button class="btn ghost sm danger" data-act="discard">Discard</button>`;
}

/* ---------- list + teams views ---------- */
function renderList() {
  const rows = [];
  const walk = (id, d) => kids(id).forEach(k => { rows.push([k, d]); if (!k.collapsed) walk(k.id, d + 1); });
  roots().forEach(r => { rows.push([r, 0]); if (!r.collapsed) walk(r.id, 1); });
  $('#canvas').insertAdjacentHTML('beforeend', `<div class="listview"><table class="lt"><thead><tr><th>Person</th><th>Title</th><th>Team</th><th>Reports to</th><th>Location</th><th>Direct</th><th>Total</th><th>With us</th></tr></thead><tbody>
    ${rows.map(([p, d]) => `<tr data-act="select:${p.id}" style="${anyFilter() && !emphasised(p) ? 'opacity:.35' : ''}"><td><div class="nm" style="padding-left:${d * 22}px">${kids(p.id).length ? `<button class="tw" data-act="toggle:${p.id}">${I(p.collapsed ? 'chevr' : 'chevd')}</button>` : '<span class="tw"></span>'}${avatar(p)}${p.open ? '<i style="color:var(--amber)">Open role</i>' : esc(p.name)}</div></td><td>${esc(p.title)}</td><td>${esc(p.dept)}</td><td>${p.managerId ? esc(byId(p.managerId)?.name || byId(p.managerId)?.title) : '<span class="tag rose">None</span>'}</td><td>${esc(p.loc)}</td><td class="num">${kids(p.id).length || ''}</td><td class="num">${descendants(p.id).length || ''}</td><td>${p.open ? '' : tenure(p)}</td></tr>`).join('')}</tbody></table></div>`);
}
function renderTeams() {
  const groups = Object.keys(DEPTS).map(d => [d, visibleData().filter(p => p.dept === d)]).filter(([, l]) => l.length);
  $('#canvas').insertAdjacentHTML('beforeend', `<div class="teams">${groups.map(([d, l]) => { const lead = l.find(p => !l.some(x => x.id === p.managerId)) ; return `<div class="team"><h4><i style="background:${DEPTS[d].c}"></i>${esc(d)}<small>${l.filter(p => !p.open).length} people${l.some(p => p.open) ? ` · ${l.filter(p => p.open).length} open` : ''}</small></h4>
    ${l.sort((a, b) => depth(a.id) - depth(b.id)).map(p => `<div class="rep ${p === lead ? 'lead' : ''}" data-act="select:${p.id}" style="${anyFilter() && !emphasised(p) ? 'opacity:.35' : ''}">${avatar(p)}<span><b>${p.open ? 'Open role' : esc(p.name)}</b><small>${esc(p.title)}${p === lead ? ' · leads the team' : ''}</small></span>${I('chevr')}</div>`).join('')}</div>`; }).join('')}</div>`);
}

/* ---------- layer: dialogs, context menu, toast ---------- */
function renderLayer() {
  let h = dialogHtml();
  if (S.ctx) { const p = byId(S.ctx.id); const m = p.managerId ? byId(p.managerId) : null;
    h += `<div class="menu ctx" style="left:${S.ctx.x}px;top:${S.ctx.y}px"><h6>${esc(p.open ? p.title : p.name)}</h6>
      <button data-act="select:${p.id}">${I('eye')}<span><b>Open side panel</b></span></button>
      ${p.open ? `<button data-act="fill:${p.id}">${I('usercheck')}<span><b>Fill this role</b></span></button>` : `<button data-act="addmember:${p.id}">${I('userplus')}<span><b>Add a team member</b><small>Existing person, open role or new starter</small></span></button>`}
      <button data-act="changemgr:${p.id}">${I('move')}<span><b>Change manager</b></span></button>
      ${!p.open ? `<button data-act="dotted:${p.id}">${I('dotted')}<span><b>${p.dotted ? 'Change' : 'Add'} dotted-line manager</b></span></button>` : ''}
      ${m && !p.open && !m.open && m.title !== 'Chief Executive Officer' ? `<button data-act="promote:${p.id}">${I('arrowup')}<span><b>Swap places with ${short(m)}</b><small>${short(p)} becomes the manager; ${short(m)} reports to them</small></span></button>` : ''}
      ${kids(p.id).length ? `<button data-act="toggle:${p.id}">${I(p.collapsed ? 'expand' : 'collapse')}<span><b>${p.collapsed ? 'Expand' : 'Collapse'} team</b></span></button><button data-act="focusteam:${p.id}">${I('target')}<span><b>Show only this team</b><small>Everyone under ${short(p)}, fitted to the screen</small></span></button>` : ''}
      <hr>
      <button data-act="export:png">${I('image')}<span><b>Export this branch as a picture</b></span></button>
      ${p.managerId && !p.open ? `<button class="danger" data-act="unassign:${p.id}">${I('userx')}<span><b>Remove from ${short(m)}'s team</b><small>Moves to the “no manager yet” lane</small></span></button>` : ''}
      ${p.open ? `<button class="danger" data-act="closerole:${p.id}">${I('trash')}<span><b>Close this open role</b></span></button>` : ''}
    </div>`; }
  if (S.toast) h += `<div class="toast">${I(S.toast.ic || 'check')} ${esc(S.toast.msg)} ${S.toast.undo ? `<button data-act="toastundo">Undo</button>` : ''}</div>`;
  $('#layer').innerHTML = h;
  if (S.dlg && (S.dlg.q !== undefined)) { const i = $('#pick-q'); if (i && document.activeElement !== i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); } }
}
let toastT;
function toast(msg, ic = 'check', undo) { S.toast = {msg, ic, undo}; renderLayer(); clearTimeout(toastT); toastT = setTimeout(() => { S.toast = null; renderLayer(); }, 4500); }

/* ---------- prototype footer ---------- */
function renderProto() {
  $('#proto').innerHTML = S.protoMin ? `<button data-act="proto:min">${I('chevu')} Prototype</button>` :
    `<b>Try:</b>${Object.entries(SCENARIOS).map(([k, v]) => `<button class="${S.scenario === k ? 'on' : ''}" data-act="scn:${k}">${v.label}</button>`).join('')}<button data-act="proto:min" title="Hide">${I('chevd')}</button>`;
}

/* ---------- actions ---------- */
function act(a, el, ev) {
  const [k, v, w] = a.split(':');
  const id = +v;
  const closeMenus = () => { S.menu = null; S.ctx = null; };
  switch (k) {
    case 'view': S.view = v; closeMenus(); render(); if (v === 'tree' || v === 'lr') fit(); break;
    case 'compact': S.compact = !S.compact; render(); fit(); break;
    case 'zoom': if (v === '1') { S.zoom = 1; applyTransform(true); } else zoomAt(v === '+' ? 1.2 : 1 / 1.2); break;
    case 'fit': fit(); break;
    case 'expandall': DATA.forEach(p => p.collapsed = false); S.levels = 0; render(); fit(); break;
    case 'collapseall': DATA.forEach(p => { if (depth(p.id) >= 1) p.collapsed = true; }); render(); fit(); break;
    case 'toggle': { const p = byId(id); p.collapsed = !p.collapsed; S.menu = null; S.ctx = null; render(); break; }
    case 'menu': S.menu = S.menu === v ? null : v; S.ctx = null; render(); if (v === 'time') $('#asof')?.addEventListener('input', e => { S.asOf = +e.target.value; render(); }); break;
    case 'filter': S.filters[v] = S.filters[v] === w ? null : w; S.menu = null; render(); break;
    case 'clear': S.filters[v] = null; S.menu = null; ev.stopPropagation(); render(); break;
    case 'color': S.colorBy = v; S.menu = null; render(); break;
    case 'levels': S.levels = id; S.menu = null; render(); fit(); break;
    case 'focus': S.focus = S.focus === v ? null : v; closeMenus(); if (S.focus === 'nomgr' && S.view !== 'tree' && S.view !== 'lr') S.view = 'tree'; render(); if (S.focus) fit(); break;
    case 'focusteam': { S.ctx = null; S.filters = {dept: null, loc: null, type: null}; DATA.forEach(p => p.collapsed = false); const keep = new Set([id, ...descendants(id).map(d => d.id)]); DATA.forEach(p => { if (!keep.has(p.id) && !ancestors(id).some(a => a.id === p.id)) p.collapsed = true; }); ancestors(id).forEach(a => a.collapsed = false); byId(id).collapsed = false; render(); centerOn(id); toast(`Showing ${short(byId(id))}'s team. Press E to see everyone again.`, 'target'); break; }
    case 'asof': S.asOf = 0; S.menu = null; render(); break;
    case 'jump': S.q = ''; S.sugg = -1; S.sel = id; S.side = id; ancestors(id).forEach(a => a.collapsed = false); if (S.view !== 'tree' && S.view !== 'lr') S.view = 'tree'; render(); centerOn(id); break;
    case 'select': closeMenus(); S.sel = id; S.side = id; S.sideTab = S.sideTab || 'team'; ancestors(id).forEach(a => a.collapsed = false); render(); if (S.view === 'tree' || S.view === 'lr') centerOn(id); break;
    case 'stab': S.sideTab = v; renderSide(); break;
    case 'closeside': S.side = null; S.sel = null; render(); break;
    case 'side': S.side = v; render(); break;
    case 'ctx': { ev.stopPropagation(); const r = el.getBoundingClientRect(); S.ctx = {id, x: Math.min(r.left, innerWidth - 300), y: Math.min(r.bottom + 4, innerHeight - 420)}; S.menu = null; renderLayer(); break; }
    case 'me': S.sel = ME; S.side = ME; ancestors(ME).forEach(a => a.collapsed = false); if (S.view !== 'tree' && S.view !== 'lr') S.view = 'tree'; render(); centerOn(ME); break;
    case 'draft': S.draft = true; S.side = 'changes'; closeMenus(); render(); break;
    case 'discard': while (S.changes.length) revert(S.changes.pop()); S.undone = []; S.draft = false; S.side = null; render(); toast('Plan discarded — the chart is back to how it was.', 'undo'); break;
    case 'undo': undo(); break;
    case 'redo': redo(); break;
    case 'toastundo': S.toast = null; undo(); break;
    case 'rmchange': { const c = S.changes[id]; const after = S.changes.slice(id + 1); S.changes.length = 0; [...after].reverse().forEach(revert); revert(c); after.forEach(x => { S.changes = S.changes; applyChange(x); }); render(); break; }
    case 'publish': S.dlg = {kind: 'publish'}; render(); break;
    case 'dlgpublish': { const n = S.changes.length; S.changes = []; S.undone = []; S.draft = false; S.dlg = null; S.side = null; render(); toast(`${n} ${n === 1 ? 'change' : 'changes'} sent to the Head of People & Culture for approval. You'll be told when they are live.`, 'send'); break; }
    case 'addmember': closeMenus(); S.dlg = {kind: 'addmember', id, mode: 'existing', q: '', sel: null}; render(); break;
    case 'changemgr': closeMenus(); S.dlg = {kind: 'changemgr', id, q: '', sel: null}; render(); break;
    case 'dotted': closeMenus(); S.dlg = {kind: 'dotted', id, q: '', sel: null}; render(); break;
    case 'fill': closeMenus(); S.dlg = {kind: 'fill', id, mode: 'existing', q: '', sel: null}; render(); break;
    case 'dlgmode': S.dlg.mode = v; S.dlg.sel = null; render(); break;
    case 'dlgopt': S.dlg.only = v === 'only'; renderLayer(); break;
    case 'pick': S.dlg.sel = id; renderLayer(); break;
    case 'closedlg': S.dlg = null; renderLayer(); break;
    case 'dlgmove': { const d = S.dlg, p = byId(d.from), m = byId(d.to); S.dlg = null; const oldMgr = p.managerId; const stay = d.only ? kids(p.id).map(k => k.id) : [];
      applyChange({kind: 'move', id: p.id, to: m.id, label: `${short(p)} now reports to ${short(m)}`, note: `${esc(p.title)} · from ${short(byId(oldMgr))}`, ic: 'move'});
      stay.forEach(kid => applyChange({kind: 'move', id: kid, to: oldMgr, label: `${short(byId(kid))} stays with ${short(byId(oldMgr))}`, note: 'Left behind when their manager moved', ic: 'move'}));
      break; }
    case 'dlgpickmgr': { const d = S.dlg; const p = byId(d.id); S.dlg = null; openMoveConfirm(p.id, d.sel); break; }
    case 'dlgdotted': { const d = S.dlg; const p = byId(d.id), m = byId(d.sel); S.dlg = null; applyChange({kind: 'dotted', id: p.id, to: m.id, label: `${short(p)} also reports to ${short(m)} (dotted line)`, note: esc(p.title), ic: 'dotted'}); break; }
    case 'dlgadd': { const d = S.dlg, m = byId(d.id); if (d.mode === 'hire') { S.dlg = {kind: 'form', title: 'New starter', sub: `Manager: ${esc(m.name)} · Team: ${esc(m.dept)}`}; renderLayer(); break; } S.dlg = null; if (d.mode === 'existing') { const p = byId(d.sel); applyChange({kind: 'addexisting', id: p.id, to: m.id, label: `${short(p)} joins ${short(m)}'s team`, note: `${esc(p.title)} · from ${short(byId(p.managerId))}`, ic: 'userplus'}); } else applyChange({kind: 'newrole', to: m.id, title: d.title.trim(), label: `New open role: ${esc(d.title.trim())} under ${short(m)}`, note: 'Hiring will see it as a job to fill', ic: 'briefcase'}); break; }
    case 'dlgfill': { const d = S.dlg, r = byId(d.id); if (d.mode === 'hire') { S.dlg = {kind: 'form', title: `New starter — ${esc(r.title)}`, sub: `Manager: ${esc(byId(r.managerId)?.name || '')} · Team: ${esc(r.dept)}`}; renderLayer(); break; } const p = byId(d.sel); S.dlg = null; applyChange({kind: 'fill', id: r.id, name: p.name, label: `${short(p)} fills the ${r.title} role`, note: `Their old spot under ${short(byId(p.managerId))} becomes free`, ic: 'usercheck'}); applyChange({kind: 'unassign', id: p.id, label: `${short(p)}'s old record is closed`, note: 'Merged into the filled role'}); DATA.splice(DATA.findIndex(x => x.id === p.id), 1); render(); break; }
    case 'unassign': { S.ctx = null; const p = byId(id); applyChange({kind: 'unassign', id, label: `${short(p)} removed from ${short(byId(p.managerId))}'s team`, note: 'Now in the “no manager yet” lane', ic: 'userx'}); break; }
    case 'closerole': { S.ctx = null; DATA.splice(DATA.findIndex(x => x.id === id), 1); S.side = null; S.sel = null; render(); toast('Open role closed. Hiring has been told.', 'trash'); break; }
    case 'promote': { S.ctx = null; const p = byId(id), m = byId(p.managerId); applyChange({kind: 'swap', id, to: m.id, label: `${short(p)} and ${short(m)} swap places`, note: `${short(p)} now leads; ${short(m)} reports to them`, ic: 'swap'}); break; }
    case 'suggest': S.dlg = {kind: 'suggest'}; render(); break;
    case 'dlgsuggest': { S.dlg = null; const ceo = DATA.find(p => p.title === 'Chief Executive Officer'); const heads = DATA.filter(p => /^(Head of|Chief)/.test(p.title) && p !== ceo && !p.open); heads.forEach(h => h.managerId = ceo.id); const leads = DATA.filter(p => /Lead|Manager/.test(p.title) && !heads.includes(p) && p !== ceo); leads.forEach(l => { const h = heads.find(x => x.dept === l.dept); l.managerId = h ? h.id : (l.dept === 'Operations' ? DATA.find(p => p.title === 'Chief Operating Officer') : DATA.find(p => p.title === 'Chief Financial Officer'))?.id || ceo.id; }); DATA.forEach(p => { if (p === ceo || heads.includes(p) || leads.includes(p)) return; const l = leads.find(x => x.dept === p.dept) || heads.find(x => x.dept === p.dept); p.managerId = l ? l.id : ceo.id; }); render(); fit(); toast('Suggested chart in place. Drag anyone to adjust it.', 'wand'); break; }
    case 'export': S.menu = null; S.ctx = null; if (v === 'link') { S.dlg = {kind: 'share'}; render(); break; } render(); toast({png: 'Picture saved as org-chart-2026-11-04.png', pdf: 'PDF ready — 8 pages, one per team', xlsx: 'Spreadsheet saved as org-chart-2026-11-04.xlsx'}[v], 'download'); break;
    case 'copylink': S.dlg = null; render(); toast('Link copied. It stops working in 30 days.', 'link'); break;
    case 'print': S.menu = null; render(); window.print(); break;
    case 'scn': S.scenario = v; try { localStorage.setItem('org-scn', v); } catch (e) {} applyScenario(); render(); fit(); break;
    case 'proto': S.protoMin = !S.protoMin; renderProto(); break;
    case 'hub': toast('This tab is on the live product; the prototype only shows Org chart.', 'info'); break;
  }
}
document.addEventListener('click', e => {
  const t = e.target.closest('[data-act]');
  if (!t) { if (S.menu || S.ctx) { S.menu = null; S.ctx = null; render(); } return; }
  if (t.tagName === 'A') e.preventDefault();
  act(t.dataset.act, t, e);
});
document.addEventListener('contextmenu', e => { const n = e.target.closest('.node'); if (!n) return; e.preventDefault(); S.ctx = {id: +n.dataset.id, x: Math.min(e.clientX, innerWidth - 300), y: Math.min(e.clientY, innerHeight - 420)}; renderLayer(); });
document.addEventListener('input', e => {
  if (e.target.id === 'q') { S.q = e.target.value; S.sugg = -1; const i = e.target; renderBar(); const n = $('#q'); n.focus(); n.setSelectionRange(i.value.length, i.value.length); renderNodes(); renderEdges(); }
  if (e.target.id === 'pick-q') { S.dlg.q = e.target.value; renderLayer(); }
  if (e.target.id === 'role-title') { S.dlg.title = e.target.value; const b = $('[data-act="dlgadd"]'); if (b) { b.disabled = !e.target.value.trim(); b.style.opacity = b.disabled ? .5 : 1; } }
});
$('#nodes').addEventListener('mouseover', e => { const n = e.target.closest('.node'); const id = n ? +n.dataset.id : null; if (id !== S.hover) { S.hover = id; renderEdges(); if (!S.sel) renderNodes(); } });
$('#nodes').addEventListener('mouseleave', () => { S.hover = null; renderEdges(); renderNodes(); });
$('#nodes').addEventListener('click', e => { if (dragSuppressClick || e.target.closest('[data-act]')) return; const n = e.target.closest('.node'); if (n && !n.classList.contains('ghost')) act('select:' + n.dataset.id); });
$('#nodes').addEventListener('dblclick', e => { const n = e.target.closest('.node'); if (n) act('toggle:' + n.dataset.id); });
$('#hub').querySelectorAll('.hb').forEach(b => { b.insertAdjacentHTML('afterbegin', I(b.dataset.ic)); if (!b.classList.contains('on')) b.dataset.act = 'hub'; });
document.querySelectorAll('.rail a').forEach(a => a.insertAdjacentHTML('afterbegin', I(a.dataset.ic)));

/* ---------- keyboard ---------- */
document.addEventListener('keydown', e => {
  const typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName);
  if (e.key === 'Escape') { if (S.dlg) S.dlg = null; else if (S.menu || S.ctx) { S.menu = null; S.ctx = null; } else if (S.q) { S.q = ''; } else { S.side = null; S.sel = null; } document.activeElement.blur(); render(); return; }
  if (typing) {
    if (document.activeElement.id === 'q') { const hits = DATA.filter(p => (p.name + ' ' + p.title + ' ' + p.dept).toLowerCase().includes(S.q.toLowerCase())).slice(0, 8); if (e.key === 'ArrowDown') { S.sugg = Math.min(hits.length - 1, S.sugg + 1); renderBar(); $('#q').focus(); e.preventDefault(); } if (e.key === 'ArrowUp') { S.sugg = Math.max(0, S.sugg - 1); renderBar(); $('#q').focus(); e.preventDefault(); } if (e.key === 'Enter' && hits[Math.max(0, S.sugg)]) { act('jump:' + hits[Math.max(0, S.sugg)].id); } }
    return;
  }
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
  if (e.key === '/') { e.preventDefault(); $('#q').focus(); return; }
  if (e.key === 'f' || e.key === 'F') fit();
  if (e.key === 'e' || e.key === 'E') act('expandall');
  if (e.key === 'c' || e.key === 'C') act('collapseall');
  if (e.key === '+' || e.key === '=') zoomAt(1.2);
  if (e.key === '-') zoomAt(1 / 1.2);
  if (S.dlg) return;
  const cur = S.sel ? byId(S.sel) : null;
  if (e.key === 'Enter' && cur) { S.side = cur.id; render(); }
  if (e.key === ' ' && cur) { e.preventDefault(); act('toggle:' + cur.id); }
  if ((e.key === 'm' || e.key === 'M') && cur) act('changemgr:' + cur.id);
  if ((e.key === 'a' || e.key === 'A') && cur && !cur.open) act('addmember:' + cur.id);
  if (e.key.startsWith('Arrow')) {
    e.preventDefault();
    if (!cur) { const r = roots()[0]; if (r) act('select:' + r.id); return; }
    const lr = S.view === 'lr';
    const up = lr ? 'ArrowLeft' : 'ArrowUp', down = lr ? 'ArrowRight' : 'ArrowDown', prev = lr ? 'ArrowUp' : 'ArrowLeft', next = lr ? 'ArrowDown' : 'ArrowRight';
    let t = null;
    if (e.key === up && cur.managerId) t = cur.managerId;
    if (e.key === down) { cur.collapsed = false; t = kids(cur.id)[0]?.id; }
    if (e.key === prev || e.key === next) { const sib = cur.managerId ? kids(cur.managerId) : roots(); const i = sib.findIndex(s => s.id === cur.id); t = sib[i + (e.key === next ? 1 : -1)]?.id; }
    if (t) { S.sel = t; if (S.side && S.side !== 'changes') S.side = t; render(); centerOn(t); }
  }
});
window.addEventListener('resize', () => drawMinimap());

/* ---------- go ---------- */
applyScenario(); render(); fit(false);
if (S.scenario === 'normal') setTimeout(() => toast('Tip: drag any card onto a new manager, or right-click a card for everything you can do.', 'info'), 800);
