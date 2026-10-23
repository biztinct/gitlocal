/* One Approvals inbox for every process, the request drawer, decisions, and the phone view */
(function (P) {
  const S = () => P.state;
  const esc = P.esc;
  const I = () => S().inbox;

  function actorOf(r) { return r.steps[r.cur_step]; }
  function assignees(step) { return (step.who || []).map(k => ({ key: k, cover: P.coverFor(k) })); }
  function isMine(r, me) {
    if (r.state !== 'pending') return false;
    const st = actorOf(r); if (!st) return false;
    return assignees(st).some(a => (a.cover || a.key) === me && !(st.done || []).includes(a.key));
  }
  function nextWho(r) {
    const st = actorOf(r); if (!st) return '';
    if (r.state === 'blocked') return 'Blocked · ' + (st.issue || '');
    const left = assignees(st).filter(a => !(st.done || []).includes(a.key));
    return left.map(a => a.cover ? P.pshort(a.cover) + ' (covering for ' + P.pshort(a.key) + ')' : P.pshort(a.key)).join(st.mode === 'all' ? ' and ' : ' or ');
  }
  function stepBadge(st, r) {
    if (st.mode === 'all') { const d = (st.done || []).length; return `<span class="badge info sentence">${d} of ${st.who.length} approvals received</span>`; }
    return '';
  }
  P.reqCard = function (r, me, phone) {
    const mine = isMine(r, me);
    const st = actorOf(r);
    const dots = r.steps.map((s, i) => { const cls = s.status === 'done' ? 'done' : s.status === 'current' ? 'cur' : s.status === 'blocked' || s.status === 'returned' ? 'bad' : ''; return (i ? '<span class="rline"></span>' : '') + `<span class="rdot ${cls}"><i></i>${esc(s.title)}</span>`; }).join('');
    const stateBadge = r.state === 'returned' ? '<span class="badge warn">Returned</span>' : r.state === 'blocked' ? '<span class="badge err">Blocked</span>' : r.state === 'done' ? '<span class="badge ok">Approved</span>' : r.state === 'applied' ? `<span class="badge teal sentence">${ic('zap', 10)} Applied immediately</span>` : r.state === 'rejected' ? '<span class="badge err">Rejected</span>' : mine ? '<span class="badge info">Your turn</span>' : '';
    const exc = st && st.conflict && st.who.includes(me) && r.state === 'pending' ? `<span class="badge warn sentence">${ic('alert', 10)} You prepared this · exception available</span>` : '';
    const excUsed = r.steps.some(s => s.exceptionUsed) ? `<span class="badge warn sentence">${ic('flag', 10)} Exception used</span>` : '';
    return `<div class="req ${mine ? 'mine' : ''} ${r.state === 'applied' || r.state === 'done' ? 'dim' : ''}" data-act="reqOpen" data-arg="${r.id}">
  <span class="icsq ${r.state === 'blocked' ? 'rose' : r.state === 'returned' ? 'amber' : ''}">${ic(r.icon, 17)}</span>
  <div><div class="t">${esc(r.title)} ${stateBadge} ${exc} ${excUsed}</div><div class="s">${esc(r.sub)} · submitted by ${esc(P.pshort(r.submittedBy))}, ${esc(r.submittedAt)}</div>
    <div class="facts"><span class="f">${ic('layers', 12)} <b>${esc(r.count)}</b></span><span class="f">${ic('workflow', 12)} ${esc(r.wf)}</span>${r.state === 'pending' ? `<span class="f">${ic('user', 12)} Waiting for <b>${esc(nextWho(r))}</b></span>` : r.state === 'blocked' ? `<span class="f" style="color:var(--rose)">${ic('userX', 12)} ${esc(st.issue)}</span>` : r.state === 'returned' ? `<span class="f">${ic('undo', 12)} "${esc(r.returnNote)}"</span>` : ''}</div>
    <div class="rt">${dots}</div></div>
  <div class="right">${r.amount != null ? `<div class="amt tnum">${P.fmtVND(r.amount)}</div><div class="small muted">${esc(r.cur)}</div>` : `<div class="amt">${esc(r.count)}</div>`}${r.due ? `<div class="due ${r.state === 'returned' ? 'late' : ''}">${ic('clock', 11)} Due ${esc(r.due)}</div>` : ''}</div>
</div>`;
  };

  P.screens.inbox = function (s) {
    const ib = s.inbox; const me = ib.viewAs;
    const all = ib.requests;
    const mine = all.filter(r => isMine(r, me));
    const lists = { mine, all: all.filter(r => r.state === 'pending' || r.state === 'blocked'), returned: all.filter(r => r.state === 'returned'), done: all.filter(r => ['done', 'applied', 'rejected'].includes(r.state)) };
    const list = lists[ib.tab] || [];
    const sumByCur = {}; mine.forEach(r => { if (r.amount != null) sumByCur[r.cur] = (sumByCur[r.cur] || 0) + r.amount; });
    return `<div class="hero"><div><div class="eyebrow">${ic('inbox', 13)} Home</div><h1>Approvals</h1><div class="sub">Everything waiting for a decision, from every part of the product. One place, whoever you are.</div></div>
  <div class="hero-r"><span class="small muted">View as</span><span class="seg">${['nithya', 'monica', 'linh'].map(k => `<button class="${me === k ? 'on' : ''}" data-act="viewAs" data-arg="${k}">${esc(P.pshort(k))}</button>`).join('')}</span><button class="btn ghost" data-act="go" data-arg="matrix">${ic('settings', 14)} Workflows</button></div></div>
${P.coverFor(me) ? `<div class="attn">${ic('plane', 18)} <span>${esc(P.pshort(P.coverFor(me)))} is covering your Finance approver seat until 20 Sep. Requests still show here; ${esc(P.pshort(P.coverFor(me)))} can decide them and both names are recorded.</span></div>` : ''}
${S().delegations.some(d => d.active && d.to === me) ? `<div class="attn" style="background:var(--soft);color:var(--p)">${ic('plane', 18)} <span>You are covering for Monica (Finance approver) until 20 Sep. Her requests show as your turn, marked "covering for Monica".</span></div>` : ''}
${me === 'monica' && !P.coverFor(me) ? `<div class="attn" style="background:var(--soft);color:var(--p)">${ic('plane', 18)} <span>Your hand-over to Thao starts Mon 14 Sep. Until then these are yours. <button class="btn quiet xs" data-act="go" data-arg="people">See hand-overs</button></span></div>` : ''}
<div class="tabs"><button class="tab ${ib.tab === 'mine' ? 'on' : ''}" data-act="inboxTab" data-arg="mine">My turn <span class="cnt">${mine.length}</span></button><button class="tab ${ib.tab === 'all' ? 'on' : ''}" data-act="inboxTab" data-arg="all">All I can see <span class="cnt">${lists.all.length}</span></button><button class="tab ${ib.tab === 'returned' ? 'on' : ''}" data-act="inboxTab" data-arg="returned">Returned <span class="cnt">${lists.returned.length}</span></button><button class="tab ${ib.tab === 'done' ? 'on' : ''}" data-act="inboxTab" data-arg="done">Done <span class="cnt">${lists.done.length}</span></button></div>
${ib.tab === 'mine' && mine.length ? `<div class="filters"><span class="small muted">${mine.length} waiting for ${esc(P.pshort(me))} · ${Object.keys(sumByCur).map(c => P.fmtVND(sumByCur[c]) + ' ' + c).join(' · ') || 'no money at stake'} · amounts are never added across currencies</span></div>` : ''}
<div class="filters"><div class="fchips"><button class="fchip on">All processes</button><button class="fchip">Pay</button><button class="fchip">Money out</button><button class="fchip">People</button><button class="fchip">Time</button><button class="fchip">Setup</button><button class="fchip">Platform</button></div><div class="fchips"><button class="fchip on">Any division</button><button class="fchip">Retail</button><button class="fchip">Operations</button></div><div class="fchips"><button class="fchip">Due today</button><button class="fchip">Overdue</button></div></div>
<div class="reqs">${list.length ? list.map(r => P.reqCard(r, me)).join('') : `<div class="empty">${ic('checkCircle', 28)}<div class="t">Nothing waiting for you</div><div class="s">When a request reaches your step it lands here, with the facts and evidence attached.</div></div>`}</div>`;
  };

  // ---------- request drawer ----------
  P.drawers.request = function (s) {
    const ib = s.inbox; const me = ib.viewAs; const r = ib.requests.find(x => x.id === ib.open);
    if (!r) return '';
    const st = actorOf(r); const mine = isMine(r, me);
    const conflict = st && st.conflict && st.who.includes(me) && r.state === 'pending';
    const tl = r.steps.map((s2, i) => {
      const cls = s2.status === 'done' ? 'done' : s2.status === 'current' ? 'cur' : (s2.status === 'blocked' || s2.status === 'returned') ? 'bad' : '';
      const who = s2.mode === 'fast' ? '' : assignees(s2).map(a => `<span class="person"><span class="av sm">${P.people[a.cover || a.key].ini}</span><span>${esc(P.pshort(a.cover || a.key))}${a.cover ? ` <span class="badge warn sentence">${ic('plane', 10)} covering for ${esc(P.pshort(a.key))}</span>` : ''}${(s2.done || []).includes(a.key) ? ` <span class="badge ok">approved</span>` : ''}</span></span>`).join('');
      return `<div class="tlrow ${cls}"><div class="dot">${s2.status === 'done' ? ic('check', 13) : s2.status === 'current' ? ic('circleDot', 13) : s2.status === 'blocked' || s2.status === 'returned' ? ic('x', 13) : (i + 1)}</div><div><div class="t">${esc(s2.title)} ${stepBadge(s2, r)} ${s2.exceptionUsed ? `<span class="badge warn sentence">${ic('flag', 10)} Exception used</span>` : ''}</div>
        ${s2.why ? `<div class="s">${esc(s2.why)}</div>` : ''}
        ${s2.issue ? `<div class="s" style="color:var(--rose)">${esc(s2.issue)}</div><div style="display:flex;gap:6px;margin-top:6px"><button class="btn primary sm" data-act="reqFixManager">Set Minh Tran's manager</button><button class="btn ghost sm" data-act="toast" data-arg="Reassigns this step to a scoped backup with a written reason.">Choose scoped backup</button></div>` : ''}
        <div class="by">${who}</div>
        ${s2.by ? `<div class="by">${s2.status === 'returned' ? 'Sent back' : 'Decided'} by ${esc(P.pshort(s2.by))}, ${esc(s2.at)}${s2.note ? ' · ' + esc(s2.note) : ''}${s2.reason ? ' · "' + esc(s2.reason) + '"' : ''}</div>` : ''}
      </div></div>`;
    }).join('');
    const canAct = mine && r.state === 'pending';
    const footer = r.state === 'pending' ? (canAct ? `<button class="btn danger" data-act="modal" data-arg="reject">Reject</button><button class="btn ghost" data-act="modal" data-arg="sendback">${ic('undo', 14)} Send back</button>${conflict ? `<button class="btn primary" data-act="modal" data-arg="exception">${ic('flag', 14)} Approve with exception</button>` : `<button class="btn primary" data-act="approve">${ic('check', 14)} Approve</button>`}` : `<span class="small muted" style="margin-right:auto">Waiting for ${esc(nextWho(r))}. You can read everything; the decision is theirs.</span><button class="btn ghost" data-act="closeDrawer">Close</button>`)
      : r.state === 'returned' ? `<span class="small muted" style="margin-right:auto">Returned to ${esc(P.pshort(r.submittedBy))} for changes. Resubmitting starts a new attempt; this history stays.</span><button class="btn ghost" data-act="closeDrawer">Close</button>`
        : `<button class="btn ghost" data-act="closeDrawer">Close</button>`;
    return `<div class="dh"><span class="icsq">${ic(r.icon, 17)}</span><div><h2>${esc(r.title)}</h2><div class="s">${esc(r.sub)} · ${esc(r.wf)}</div></div><button class="x" data-act="closeDrawer" aria-label="Close">${ic('x', 18)}</button></div>
<div class="db">
  ${conflict ? `<div class="note amber"><b>You prepared this.</b> The "${esc(st.exception)}" policy lets you approve with a written reason. It will be marked "Exception used" and the workflow owner is told.</div>` : ''}
  ${r.state === 'blocked' ? `<div class="note rose"><b>This request cannot move.</b> ${esc(st.issue)} Fix the record and the route resumes; nothing needs resubmitting.</div>` : ''}
  ${r.state === 'returned' ? `<div class="note amber"><b>Sent back:</b> "${esc(r.returnNote)}"</div>` : ''}
  <div><div class="small muted" style="font-weight:800;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Submitted facts · frozen at submission</div><div class="factgrid">${r.facts.map(f => `<div class="fact"><div class="k">${esc(f[0])}</div><div class="v ${f[1].length > 14 ? 'sm' : ''} tnum">${esc(f[1])}</div></div>`).join('')}</div></div>
  ${r.evidence.length ? `<div><div class="small muted" style="font-weight:800;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Evidence</div><div class="evid">${r.evidence.map(e => `<div class="evrow">${ic(e.na ? 'minus' : 'paperclip', 14)}<div><div class="n">${esc(e.n)}</div><div class="s">${esc(e.s)}</div></div><span class="r">${e.warn ? `<span class="badge warn sentence">${esc(e.warn)}</span>` : e.na ? '<span class="badge muted sentence">Not required</span>' : `<button class="btn quiet xs" data-act="toast" data-arg="Opens the locked report. Its checksum is recorded with the request.">Open</button>`}</span></div>`).join('')}</div></div>` : ''}
  <div><div class="small muted" style="font-weight:800;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Route · ${esc(r.wf)}</div><div class="tl">${tl}</div></div>
  <div class="small muted">Submitted by ${esc(P.pshort(r.submittedBy))}, ${esc(r.submittedAt)}${r.due ? ' · due ' + esc(r.due) : ''}. Approving records your name, the time, and the exact version of the facts above.</div>
</div>
<div class="df">${footer}</div>`;
  };

  P.modals.exception = function (s) {
    const m = s.modal; const r = I().requests.find(x => x.id === I().open); const st = actorOf(r);
    return `<h2>Approve with exception</h2><div class="note amber"><b>You prepared this payroll.</b> Your scoped exception allows you to approve with a reason.</div>
<div class="field"><label>Why are you using this exception?</label><textarea class="input" id="exc-reason" placeholder="Say what makes this run safe to approve yourself, for example who else checked it." data-bind="modal.reason" data-live>${esc(m.reason || '')}</textarea></div>
<div class="small muted">Policy: ${esc(st.exception)} · Step: ${esc(st.title)} · Your name, the reason and the policy are recorded in the audit trail and the workflow owner is told.</div>
<div class="mf"><button class="btn ghost" data-act="closeModal">Cancel</button><button class="btn primary" data-act="approveException" ${(m.reason || '').trim().length < 12 ? 'disabled' : ''}>Confirm approval</button></div>`;
  };
  P.modals.sendback = function (s) {
    const m = s.modal; const r = I().requests.find(x => x.id === I().open);
    return `<h2>Send back to ${esc(P.pshort(r.submittedBy))}</h2><p class="muted">The request returns to the preparer for changes. Completed approvals stay in the history; resubmitting starts a fresh attempt.</p>
<div class="field"><label>What should change?</label><textarea class="input" id="sb-reason" placeholder="Be specific: the person reading this fixes it." data-bind="modal.reason" data-live>${esc(m.reason || '')}</textarea></div>
<div class="mf"><button class="btn ghost" data-act="closeModal">Cancel</button><button class="btn primary" data-act="sendBack" ${(m.reason || '').trim().length < 6 ? 'disabled' : ''}>Send back</button></div>`;
  };
  P.modals.reject = function (s) {
    const m = s.modal; const r = I().requests.find(x => x.id === I().open);
    return `<h2>Reject this request</h2><div class="note rose"><b>This ends the request.</b> ${r.process === 'payrun' ? 'All ' + esc(r.count) + ' go back to draft; nothing is paid. ' : ''}The preparer must start again. Prefer "Send back" when a correction is enough.</div>
<div class="field"><label>Reason (required)</label><textarea class="input" id="rj-reason" data-bind="modal.reason" data-live>${esc(m.reason || '')}</textarea></div>
<div class="mf"><button class="btn ghost" data-act="closeModal">Cancel</button><button class="btn danger" data-act="reject" ${(m.reason || '').trim().length < 6 ? 'disabled' : ''}>Reject request</button></div>`;
  };

  function advance(r, me, note, exception) {
    const st = actorOf(r);
    st.done = st.done || [];
    const a = assignees(st).find(x => (x.cover || x.key) === me);
    if (a) st.done.push(a.key);
    if (exception) { st.exceptionUsed = true; st.reason = note; }
    st.coverNote = a && a.cover ? P.pshort(a.cover) + ' covering for ' + P.pshort(a.key) : '';
    if (st.mode === 'all' && st.done.length < st.who.length) return 'Recorded. ' + (st.who.length - st.done.length) + ' more approval' + (st.who.length - st.done.length > 1 ? 's' : '') + ' needed from ' + nextWho(r) + '.';
    st.status = 'done'; st.by = me; st.at = 'Sat 12 Sep, now'; if (st.coverNote) st.note = st.coverNote;
    if (r.cur_step + 1 < r.steps.length) { r.cur_step++; r.steps[r.cur_step].status = 'current'; return 'Approved. Next: ' + r.steps[r.cur_step].title + ' (' + nextWho(r) + ').'; }
    r.state = 'done'; return r.title + ' is fully approved. ' + (r.process === 'payrun' ? 'Payment still needs the bank file and release approvals.' : '');
  }
  Object.assign(P.actions, {
    viewAs(k) { I().viewAs = k; I().open = null; S().drawer = null; },
    inboxTab(t) { I().tab = t; },
    reqOpen(id) { I().open = id; S().drawer = { type: 'request' }; },
    modal(t) { S().modal = { type: t, reason: '' }; },
    approve() { const r = I().requests.find(x => x.id === I().open); const msg = advance(r, I().viewAs); P.toast(msg); if (r.state === 'done') S().drawer = null; },
    approveException() { const r = I().requests.find(x => x.id === I().open); const msg = advance(r, I().viewAs, S().modal.reason, true); S().modal = null; P.toast('Approved with exception. ' + msg); },
    sendBack() { const r = I().requests.find(x => x.id === I().open); const st = actorOf(r); st.status = 'returned'; st.by = I().viewAs; st.at = 'Sat 12 Sep, now'; r.state = 'returned'; r.returnNote = S().modal.reason; S().modal = null; S().drawer = null; I().tab = 'returned'; P.toast('Sent back to ' + P.pshort(r.submittedBy) + '. They see your note and can resubmit.'); },
    reject() { const r = I().requests.find(x => x.id === I().open); const st = actorOf(r); st.status = 'returned'; st.by = I().viewAs; st.at = 'Sat 12 Sep, now'; r.state = 'rejected'; r.returnNote = S().modal.reason; S().modal = null; S().drawer = null; I().tab = 'done'; P.toast('Rejected. The preparer is told, with your reason.'); },
    reqFixManager() { const r = I().requests.find(x => x.id === I().open); const st = r.steps[0]; st.who = ['thaominh']; st.status = 'current'; delete st.issue; r.state = 'pending'; P.toast('Thao Minh set as manager on the employee record. The timesheet resumes at Manager review; no resubmission needed.'); },
  });

  // ---------- phone view ----------
  P.screens.mobile = function (s) {
    const me = 'nithya'; const r = s.inbox.requests.find(x => x.id === 'r1'); const r6 = s.inbox.requests.find(x => x.id === 'r6');
    return `<div class="hero"><div><div class="eyebrow">${ic('smartphone', 13)} Phone view · 390 px</div><h1>The same decision, on a phone.</h1><div class="sub">Identity and the current action come first. Evidence and history fold away. The footer never covers content.</div></div></div>
<div class="phonewrap">
  <div class="phone"><div class="ptop">${ic('inbox', 16)} Approvals <span class="badge info" style="margin-left:auto;background:rgba(255,255,255,.14);color:#fff">Your turn · 3</span></div>
    <div class="pbody">
      ${P.reqCard(r, me, true)}
      <div class="panel"><div class="small muted" style="font-weight:800;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">Submitted facts</div><div class="factgrid">${r.facts.slice(0, 4).map(f => `<div class="fact"><div class="k">${esc(f[0])}</div><div class="v sm tnum">${esc(f[1])}</div></div>`).join('')}</div></div>
      <details><summary>Evidence · 2 items</summary><div class="evid" style="margin-top:8px">${r.evidence.map(e => `<div class="evrow">${ic('paperclip', 14)}<div><div class="n">${esc(e.n)}</div><div class="s">${esc(e.s)}</div></div></div>`).join('')}</div></details>
      <details><summary>Route · step 1 of 3</summary><div class="rt" style="margin-top:8px;display:flex;flex-direction:column;gap:6px">${r.steps.map((s2, i) => `<span class="rdot ${s2.status === 'done' ? 'done' : s2.status === 'current' ? 'cur' : ''}"><i></i>${i + 1}. ${esc(s2.title)} · ${assignees(s2).map(a => P.pshort(a.cover || a.key)).join(', ')}</span>`).join('')}</div></details>
      ${P.reqCard(r6, me, true)}
    </div>
    <div class="pfoot"><button class="btn primary" style="justify-content:center;padding:13px">${ic('check', 15)} Approve HR lead review</button><div style="display:flex;gap:8px"><button class="btn ghost" style="flex:1;justify-content:center">${ic('undo', 14)} Send back</button><button class="btn quiet" style="flex:1;justify-content:center;color:var(--rose)">Reject</button></div></div>
  </div>
  <div class="ex" style="max-width:380px"><div class="exh"><h2>What holds on a phone</h2></div>
    <div class="kv" style="grid-template-columns:1fr"><dd>${ic('check', 13)} Long names wrap; nothing is cut with "…".</dd><dd>${ic('check', 13)} One primary action, full width, above the keyboard.</dd><dd>${ic('check', 13)} Joint steps say "1 of 3 received · waiting for Nithya and Monica".</dd><dd>${ic('check', 13)} "Approve with exception" replaces Approve when you prepared the run.</dd><dd>${ic('check', 13)} Loss of permission or a stale request disables the button with the reason inline.</dd></div>
    <button class="btn ghost" data-act="go" data-arg="inbox">${ic('arrowLeft', 14)} Back to the desktop inbox</button></div>
</div>`;
  };
})(window.POC);
