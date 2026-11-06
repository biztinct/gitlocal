/* Workflow builder: Purpose → People → Safeguards → Review & publish, with Try an example + coverage */
(function (P) {
  const S = () => P.state;
  const esc = P.esc, fmt = P.fmtVND, fsh = P.fmtShort;
  const B = () => S().builder;

  const KIND = { review: 'Review', approve: 'Final approval', joint: 'Joint approval · everyone must approve', any: 'Any one of', notify: 'Notify only · outside the sequence', fast: 'No approval needed · applied immediately, logged' };
  const decisionSteps = (b) => b.steps.filter(s => s.kind !== 'notify');

  // ---------- labels ----------
  P.whoLabel = function (w) {
    if (!w) return '';
    if (w.mode === 'role') return P.roles[w.role].name + (w.scope === 'division' ? ' in this division' : ' · whole company');
    if (w.mode === 'manager') return 'Their manager';
    if (w.mode === 'skip') return "Manager's manager";
    if (w.mode === 'people') return w.people.map(P.pshort).join(' + ') + (w.people.length > 1 ? (w.all ? ' · everyone' : ' · any one') : '');
    if (w.mode === 'team') return 'Any one of ' + w.team;
    if (w.mode === 'preparer') return 'The payroll preparer';
    return '';
  };
  function whoPhrase(w) {
    if (w.mode === 'role') return 'the <b>' + esc(P.roles[w.role].name) + '</b>' + (w.scope === 'division' ? ' for its division' : '');
    if (w.mode === 'manager') return "the employee's <b>manager</b>";
    if (w.mode === 'skip') return "the <b>manager's manager</b>";
    if (w.mode === 'people') return (w.people.length > 1 && !w.all ? 'any one of ' : '') + w.people.map(k => '<b>' + esc(P.pshort(k)) + '</b>').join(w.all ? ' and ' : ', ');
    if (w.mode === 'team') return 'any member of the <b>' + esc(w.team) + '</b>';
    return '';
  }
  P.sentence = function (b) {
    const ds = decisionSteps(b);
    if (!ds.length) return 'Nothing is checked yet. Add a step below.';
    const parts = ds.map((st, i) => {
      const last = i === ds.length - 1;
      let verb;
      if (st.kind === 'fast') return 'it is <b>applied immediately</b> and logged';
      if (st.who.mode === 'people' && st.who.people.length > 1 && st.who.all) verb = 'must all approve';
      else if (st.kind === 'review') verb = 'reviews it';
      else verb = last ? 'gives final approval' : 'approves';
      let q = '';
      if (b.tiers && st.min > 0) q += ' when the net total is <b>' + fmt(st.min) + '</b> or more';
      if (st.cond) q += ', only when ' + esc(P.conditions[st.cond]);
      return whoPhrase(st.who) + ' ' + verb + q;
    });
    let out = 'After a pay run is submitted, ' + parts[0] + '.';
    for (let i = 1; i < parts.length; i++) out += ' Then ' + parts[i] + '.';
    if (b.steps.some(s => s.kind === 'notify')) out += ' The payroll preparer is told at every step.';
    return out;
  };
  P.routeLabels = function (b) {
    return decisionSteps(b).map(st => {
      if (st.kind === 'fast') return 'No approval needed';
      let l = st.who.mode === 'role' ? P.roles[st.who.role].name : P.whoLabel(st.who).replace(' · everyone', ' (everyone)').replace(' · any one', ' (any one)');
      if (b.tiers && st.min > 0) l += ' (' + fsh(st.min) + '+)';
      return l;
    });
  };

  // ---------- route evaluation (the same logic the example, coverage and inbox would share) ----------
  const DUE = { '1wd': ['Mon 14 Sep, 17:00', 'Tue 15 Sep, 17:00', 'Wed 16 Sep, 17:00', 'Thu 17 Sep, 17:00'], day15: ['Tue 15 Sep, 17:00', 'Tue 15 Sep, 17:00', 'Tue 15 Sep, 17:00', 'Tue 15 Sep, 17:00'], none: [], request: [] };
  function condTrue(c, ex) {
    if (c === 'overtime') return !!ex.overtime;
    if (c === 'variance') return Math.abs(ex.variance) > 5;
    if (c === 'offcycle') return ex.runKind === 'off';
    if (c === 'headcount') return ex.runKind !== 'off';
    if (c === 'bank') return false;
    return true;
  }
  P.evalRoute = function (b, ex) {
    const out = { steps: [], issues: [], level: 'ready', via: [] };
    const sg = b.safeguards;
    const dueArr = DUE[sg.due] || [];
    let n = 0, prevPeople = [];
    const override = ex.override || {};
    b.steps.forEach((st) => {
      const r = { st, included: true, reason: '', people: [], issue: null, due: '' };
      if (st.kind === 'notify') { r.people = [{ key: ex.preparedBy, via: 'Prepared this run' }]; out.steps.push(r); return; }
      if (st.kind === 'fast') { r.reason = 'Applied immediately when submitted · logged in History and the Audit console'; out.steps.push(r); return; }
      if (b.tiers && st.min > 0) {
        if (ex.amount < st.min) { r.included = false; r.reason = 'Skipped: net total is under ' + fmt(st.min); }
        else r.reason = 'Included: net total is ' + fmt(st.min) + ' or more';
      }
      if (st.cond && r.included) {
        if (!condTrue(st.cond, ex)) { r.included = false; r.reason = 'Skipped: not the case that ' + P.conditions[st.cond]; }
        else r.reason = (r.reason ? r.reason + ' · ' : '') + 'Included: ' + P.conditions[st.cond];
      }
      if (!r.included) { out.steps.push(r); return; }
      n++;
      const w = st.who;
      const div = ex.division;
      if (w.mode === 'role') {
        const seat = P.resolveSeat(w.role, w.scope === 'division' ? div : null);
        if (!seat) {
          r.issue = { level: 'block', code: 'person_missing', msg: 'No ' + P.roles[w.role].name + ' is assigned for ' + P.scopes[div] + '.', fixes: [{ label: 'Assign a person', act: 'assignOpen', arg: w.role + '|' + div }, { label: 'Open People & backups', act: 'go', arg: 'people' }] };
        } else if (seat.pool) {
          r.people = seat.pool.map(k => ({ key: k, via: 'Bank mandate · Vietnam' }));
        } else {
          r.people = [{ key: override[st.id] || seat.person, via: P.roles[w.role].name + ' for ' + seat.via, backup: seat.backup, cover: P.coverFor(override[st.id] || seat.person) }];
        }
      } else if (w.mode === 'manager' || w.mode === 'skip') {
        r.people = [{ key: w.mode === 'manager' ? 'thaominh' : 'duc', via: w.mode === 'manager' ? 'Manager of each employee (3 managers in this run)' : "Manager's manager (2 in this run)" }];
        r.issue = { level: 'warn', code: 'split', msg: 'A pay run has many employees, so this step would split the run into 3 review groups, one per manager. Use a role for batches; keep "Their manager" for one-person requests.', fixes: [] };
      } else if (w.mode === 'people') {
        r.people = w.people.map(k => ({ key: k, via: 'Named in this workflow', cover: P.coverFor(k) }));
      } else if (w.mode === 'team') {
        r.people = [{ key: 'linh', via: 'Any of 4 members of the ' + w.team }];
      }
      // independence
      if (sg.independent && !r.issue) {
        const hit = r.people.find(p => p.key === ex.preparedBy);
        if (hit) {
          const excOk = sg.selfException && ex.division === 'retail' && ex.runKind === 'off' && st.kind === 'review';
          if (excOk) r.issue = { level: 'warn', code: 'self_exception', msg: P.pshort(hit.key) + ' prepared this run. Under the "' + sg.selfScope + '" exception she can approve with a written reason. The decision is marked in the audit trail.', fixes: [] };
          else r.issue = { level: 'block', code: 'self', msg: P.pshort(hit.key) + ' prepared this run and cannot also decide this step while the independence rule is on.', fixes: (hit.backup ? [{ label: 'Route to backup · ' + P.pshort(hit.backup), act: 'exUseBackup', arg: st.id + '|' + hit.backup }] : [{ label: 'Choose a different person', act: 'pickerOpen', arg: st.id }]).concat([{ label: 'Turn the independence rule off', act: 'sgIndependentOff', arg: '' }]) };
        }
      }
      // repeated person
      if (!r.issue && sg.repeated === 'different') {
        const rep = r.people.find(p => prevPeople.includes(p.cover || p.key));
        if (rep && r.people.length === 1) {
          const alt = rep.backup && !prevPeople.includes(rep.backup) ? rep.backup : null;
          r.issue = { level: alt ? 'warn' : 'block', code: 'repeat', msg: P.pshort(rep.cover || rep.key) + ' already decides an earlier step. The repeated-person rule sends this step to ' + (alt ? 'the backup, ' + P.pshort(alt) + '.' : 'a different person, but no backup is set.'), fixes: alt ? [] : [{ label: 'Set a backup', act: 'go', arg: 'people' }] };
          if (alt) r.people = [{ key: alt, via: 'Backup for ' + P.pshort(rep.key) + ' (repeated-person rule)' }];
        }
      }
      prevPeople = prevPeople.concat(r.people.map(p => p.cover || p.key));
      r.due = sg.due === 'none' ? 'No target' : sg.due === 'request' ? 'Chosen on each request' : (dueArr[n - 1] || dueArr[dueArr.length - 1]) + ' · Asia/Ho_Chi_Minh';
      out.steps.push(r);
      if (r.issue) out.issues.push({ ...r.issue, step: st.title });
    });
    // evidence
    sg.evidence.filter(e => e.on).forEach(e => {
      if (e.n === 'Variance explanation' && Math.abs(ex.variance) > 5) out.issues.push({ level: 'warn', code: 'evidence', msg: 'A variance explanation is required: the net total moved ' + ex.variance + '% from last month. The preparer attaches it before submitting.', fixes: [], step: 'Evidence' });
    });
    const fast = b.steps.find(s => s.kind === 'fast');
    if (fast) out.issues.push({ level: 'warn', code: 'fast', msg: 'Nobody checks this pay run before it is applied. That is your choice; it is shown on the Matrix and every request is logged.', fixes: [], step: 'No approval needed' });
    else if (!decisionSteps(b).some((st) => out.steps.find(r => r.st === st && r.included))) out.issues.push({ level: 'warn', code: 'empty', msg: 'No step applies to this example (all are skipped by amount or condition), so it would be applied immediately and logged.', fixes: [], step: 'Route' });
    out.level = out.issues.some(i => i.level === 'block') ? 'block' : out.issues.some(i => i.level === 'warn') ? 'warn' : 'ready';
    // why this route
    const sch = P.schemes[ex.scheme];
    out.via = [
      { rank: 1, label: sch.name + ' + ' + P.scopes[ex.division], has: false, win: false },
      { rank: 2, label: sch.name + ' (any division)', has: sch.binding === 'custom', win: sch.binding === 'custom', note: sch.binding === 'custom' ? 'Custom workflow for this scheme wins' : 'Follows the company default' },
      { rank: 3, label: P.scopes[ex.division] + ' division (any scheme)', has: false, win: false },
      { rank: 4, label: 'Vietnam company default · this workflow', has: true, win: sch.binding !== 'custom' },
    ];
    if (ex.runKind === 'off') out.via.push({ rank: 5, label: 'Run kind: Off-cycle · no exact-kind binding, "Any kind" applies', has: true, win: false });
    return out;
  };

  // ---------- rendering helpers ----------
  function personChip(p, small) {
    const per = P.people[p.key];
    const cover = p.cover ? P.people[p.cover] : null;
    return `<span class="person"><span class="av ${small ? 'sm' : ''}">${cover ? cover.ini : per.ini}</span><span><span class="n">${cover ? esc(P.pshort(p.cover)) : esc(P.pshort(p.key))}${cover ? ` <span class="badge warn sentence">${ic('plane', 10)} covering for ${esc(P.pshort(p.key))}</span>` : ''}</span>${p.via ? `<span class="t" style="display:block">${esc(p.via)}${p.backup ? ' · backup ' + esc(P.pshort(p.backup)) : ''}</span>` : ''}</span></span>`;
  }
  function stepCard(st, i, b) {
    const ds = decisionSteps(b); const idx = ds.indexOf(st);
    const isNotify = st.kind === 'notify';
    if (st.kind === 'fast') return `<div class="stepw"><div class="num fast">${ic('zap', 14)}</div><div class="step" style="border-color:var(--teal);background:#FBFEFD"><div class="sh"><div><div class="t">No approval needed</div><div class="kind">Applied immediately when submitted · logged in History and the Audit console</div></div><div class="acts"><button title="Remove" data-act="stepRemoveFast" data-arg="${st.id}">${ic('trash', 15)}</button></div></div><div class="note">${ic('info', 13)} Your choice. The Matrix row will say "No approval needed" so nobody has to open this workflow to know. Add a step to bring a check back.</div></div></div>`;
    const ex = P.evalRoute(b, b.example).steps.find(r => r.st === st);
    const resolved = ex && ex.people.length ? ex.people.map(p => `<span>${ic('arrowRight', 12)} ${personChip(p, true)}</span>`).join('') : (ex && ex.issue && ex.issue.code === 'person_missing' ? `<span class="badge err sentence">${ic('userX', 11)} ${esc(ex.issue.msg)}</span>` : '');
    const seats = st.who.mode === 'people' && st.who.people.length > 1 ? `<div class="seats">${st.who.people.map(k => `<span class="seat"><span class="av sm">${P.people[k].ini}</span>${esc(P.pshort(k))}</span>`).join('')}<span class="seg"><button class="${st.who.all ? 'on' : ''}" data-act="stepAll" data-arg="${st.id}|1">Everyone must approve</button><button class="${!st.who.all ? 'on' : ''}" data-act="stepAll" data-arg="${st.id}|0">Any one</button></span></div>` : '';
    return `<div class="stepw"><div class="num ${isNotify ? 'n' : ''}">${isNotify ? ic('bell', 14) : idx + 1}</div>
<div class="step ${isNotify ? 'notify' : ''}">
  <div class="sh"><div><div class="t" contenteditable="true" spellcheck="false" data-title="${st.id}">${esc(st.title)}</div><div class="kind">${KIND[st.kind] || ''}${isNotify ? ' · never counted as an approval' : ''}</div></div>
    <div class="acts"><button title="Move up" data-act="stepMove" data-arg="${i}|-1" ${i === 0 ? 'disabled' : ''}>${ic('chevronUp', 16)}</button><button title="Move down" data-act="stepMove" data-arg="${i}|1" ${i === b.steps.length - 1 ? 'disabled' : ''}>${ic('chevronDown', 16)}</button><button title="Remove" data-act="stepRemove" data-arg="${st.id}">${ic('trash', 15)}</button></div></div>
  <div class="who"><span class="small muted" style="font-weight:700">${isNotify ? 'Who is told' : 'Who decides'}</span>${isNotify ? `<span class="chip plain">${esc(P.whoLabel(st.who))}</span>` : `<button class="chip" data-act="pickerOpen" data-arg="${st.id}" title="Change who approves">${esc(P.whoLabel(st.who))} ${ic('pencil', 12)}</button>`}<span class="resolved">${resolved}</span></div>
  ${seats}
  ${isNotify ? '' : `<div class="cond">${ic('filter', 13)}<span>Include this step</span>
    ${b.tiers ? `<span class="amt"><select class="input" data-bind="builder.steps.${i}.min" data-num><option value="0" ${st.min === 0 ? 'selected' : ''}>for any amount</option><option value="100000000" ${st.min === 100000000 ? 'selected' : ''}>from ₫100,000,000</option><option value="300000000" ${st.min === 300000000 ? 'selected' : ''}>from ₫300,000,000</option><option value="600000000" ${st.min === 600000000 ? 'selected' : ''}>from ₫600,000,000</option><option value="1000000000" ${st.min === 1000000000 ? 'selected' : ''}>from ₫1,000,000,000</option></select></span>` : ''}
    <select class="input" data-bind="builder.steps.${i}.cond"><option value="">${b.tiers ? 'and no other condition' : 'always'}</option>${Object.keys(P.conditions).map(k => `<option value="${k}" ${st.cond === k ? 'selected' : ''}>only when ${esc(P.conditions[k])}</option>`).join('')}</select></div>`}
</div></div>`;
  }
  function tiersPanel(b) {
    if (b.steps.some(s => s.kind === 'fast')) return '';
    const ds = decisionSteps(b);
    const ths = Array.from(new Set(ds.map(s => s.min))).sort((a, b2) => a - b2);
    const bands = ths.map((t, i) => ({ from: t, to: ths[i + 1], steps: ds.filter(s => s.min <= t) }));
    const amt = b.example.amount;
    return `<div class="tiers"><div class="th"><label class="switch ${b.tiers ? 'on' : 'off'}" data-act="tiersToggle"><i></i><span class="t">Route by amount</span></label><span class="s">${b.tiers ? 'Small runs stay light; big runs bring in more people. Set the amount on each step.' : 'Off · every step applies to every run, whatever the amount.'}</span>${b.tiers ? `<span style="margin-left:auto" class="small muted">Amount fact:</span><select class="input" style="width:auto;padding:5px 30px 5px 10px;font-size:12.5px"><option>Net total (VND)</option><option>Gross total (VND)</option><option>Change vs last month (%)</option><option>Employees affected</option><option>Overtime hours</option></select>` : ''}</div>
    ${b.tiers ? `<div class="ladder">${bands.map((bd, i) => `<div class="band b${Math.min(i + 1, 3)} ${amt >= bd.from && (bd.to == null || amt < bd.to) ? 'hit' : ''}"><div class="amt">${bd.from === 0 ? (bd.to ? 'Under ' + fsh(bd.to) : 'Any amount') : (bd.to ? fsh(bd.from) + ' to ' + fsh(bd.to) : fsh(bd.from) + ' and above')}</div><div class="r">${bd.steps.map((s, j) => (j ? '<span class="ar">' + ic('arrowRight', 11) + '</span>' : '') + esc(s.who.mode === 'role' ? P.roles[s.who.role].name : P.whoLabel(s.who))).join('')}</div></div>`).join('')}</div><div class="small muted">Amounts are compared in the run's own currency. Runs in different currencies are never added together.</div>` : ''}</div>`;
  }
  function addRow(b) {
    const items = [
      { k: 'review', t: 'Review', s: 'Someone checks and passes it on', i: 'eye' },
      { k: 'approve', t: 'Final approval', s: 'Someone signs it off', i: 'stamp' },
      { k: 'joint', t: 'Joint approval', s: 'Named people must all approve', i: 'users' },
      { k: 'any', t: 'Any one of a team', s: 'First eligible person decides', i: 'userCheck' },
      { k: 'cond', t: 'Only when…', s: 'A step that applies in some cases', i: 'filter' },
      { k: 'notify', t: 'Notify only', s: 'Tell someone; not an approval', i: 'bell' },
      { k: 'fast', t: 'No approval needed', s: 'Applied immediately and logged. Replaces the steps; you confirm at publish.', i: 'zap' },
    ];
    return `<div class="addrow"><button class="btn outline" data-act="addMenu">${ic('plus', 15)} Add a step</button><span class="small muted">Steps run in order. Drag is optional; the arrows always work.</span>
    ${b.addMenu ? `<div class="addmenu">${items.map(it => `<button data-act="stepAdd" data-arg="${it.k}" ${it.dis ? 'disabled' : ''}><span class="icsq ${it.dis ? 'slate' : ''}" style="width:30px;height:30px">${ic(it.i, 15)}</span><span><div class="t">${esc(it.t)}</div><div class="s">${esc(it.s)}</div></span></button>`).join('')}</div>` : ''}</div>`;
  }
  function examplePanel(b) {
    const ex = b.example; const r = P.evalRoute(b, ex);
    const lvl = { ready: ['ok', 'Ready for this example', 'checkCircle'], warn: ['warn', 'Needs attention', 'alert'], block: ['err', 'Cannot submit', 'xCircle'] }[r.level];
    let n = 0;
    return `<div class="ex">
  <div class="exh"><h2>Try an example</h2><span class="badge muted sentence">No actions sent</span></div>
  <div class="grid2">
    <div class="field"><label>Scheme</label><select class="input" data-bind="builder.example.scheme">${Object.keys(P.schemes).map(k => `<option value="${k}" ${ex.scheme === k ? 'selected' : ''}>${esc(P.schemes[k].name)}</option>`).join('')}</select></div>
    <div class="field"><label>Division</label><select class="input" data-bind="builder.example.division">${P.divisions.map(k => `<option value="${k}" ${ex.division === k ? 'selected' : ''}>${esc(P.scopes[k])}</option>`).join('')}</select></div>
    <div class="field"><label>Run kind</label><select class="input" data-bind="builder.example.runKind"><option value="end" ${ex.runKind === 'end' ? 'selected' : ''}>End of cycle</option><option value="off" ${ex.runKind === 'off' ? 'selected' : ''}>Off-cycle</option><option value="fnf" ${ex.runKind === 'fnf' ? 'selected' : ''}>Full &amp; final</option></select></div>
    <div class="field"><label>Prepared by</label><select class="input" data-bind="builder.example.preparedBy" data-after="exClearOverride"><option value="linh" ${ex.preparedBy === 'linh' ? 'selected' : ''}>Linh Nguyen</option><option value="nithya" ${ex.preparedBy === 'nithya' ? 'selected' : ''}>Nithya</option><option value="monica" ${ex.preparedBy === 'monica' ? 'selected' : ''}>Monica</option></select></div>
    <div class="field"><label>Net total (VND)</label><select class="input" data-bind="builder.example.amount" data-num>${[48200000, 180000000, 420000000, 620000000, 1250000000].map(v => `<option value="${v}" ${ex.amount === v ? 'selected' : ''}>${fmt(v)}</option>`).join('')}</select></div>
    <div class="field"><label>Change vs last month</label><select class="input" data-bind="builder.example.variance" data-num><option value="3.2" ${ex.variance === 3.2 ? 'selected' : ''}>+3.2%</option><option value="7.8" ${ex.variance === 7.8 ? 'selected' : ''}>+7.8%</option><option value="-2.1" ${ex.variance === -2.1 ? 'selected' : ''}>−2.1%</option></select></div>
  </div>
  <label class="checkrow ${ex.overtime ? 'on' : ''}" data-act="exOvertime"><span class="cb">${ex.overtime ? ic('check', 12) : ''}</span>Overtime included</label>
  <div class="res"><span class="badge ${lvl[0]} sentence" style="font-size:12px;padding:6px 12px">${ic(lvl[2], 13)} ${lvl[1]}</span></div>
  <div class="via">${ic('route', 13)} <b>${esc(P.schemes[ex.scheme].name)}</b> ${ic('arrowRight', 11)} ${P.schemes[ex.scheme].binding === 'custom' ? '<b>custom workflow for this scheme</b>' : 'follows the default'} ${ic('arrowRight', 11)} <b>${esc(b.name)} · ${b.publishedNow ? 'v3' : 'draft v3'}</b></div>
  <div class="exsteps">${r.steps.map(s => {
      if (s.st.kind === 'notify') return `<div class="exstep"><div class="n">${ic('bell', 11)}</div><div><div class="t">${esc(s.st.title)}</div><div class="p">${s.people.map(p => personChip(p, true)).join('')}</div><div class="why">Told at every step · not an approval</div></div></div>`;
      if (!s.included) return `<div class="exstep skip"><div class="n">–</div><div><div class="t">${esc(s.st.title)}</div><div class="why">${esc(s.reason)}</div></div></div>`;
      n++;
      const cls = s.issue ? (s.issue.level === 'block' ? 'bad' : 'warn') : '';
      return `<div class="exstep ${cls}"><div class="n">${n}</div><div><div class="t">${esc(s.st.title)}${s.st.who.mode === 'people' && s.st.who.people.length > 1 ? ` <span class="badge info sentence">${s.st.who.all ? 'everyone must approve' : 'any one'}</span>` : ''}</div>
        <div class="p">${s.people.map(p => personChip(p, true)).join('') || ''}</div>
        ${s.reason ? `<div class="why">${esc(s.reason)}</div>` : ''}
        ${s.due ? `<div class="due">${ic('clock', 11)} Due ${esc(s.due)}</div>` : ''}</div></div>`;
    }).join('')}</div>
  ${r.issues.map(i => `<div class="issue ${i.level === 'block' ? 'err' : 'warn'}"><div class="t">${ic(i.level === 'block' ? 'xCircle' : 'alert', 14)} ${esc(i.step)}</div><div class="s">${esc(i.msg)}</div>${i.fixes.length ? `<div class="a">${i.fixes.map(f => `<button class="btn ${i.level === 'block' ? 'primary' : 'ghost'} sm" data-act="${f.act}" data-arg="${esc(f.arg)}">${esc(f.label)}</button>`).join('')}</div>` : ''}</div>`).join('')}
  <details class="why"><summary>${ic('chevronRight', 14)} Why this route?</summary><ol>${r.via.map(v => `<li class="${v.win ? 'win' : ''}"><b>${v.rank}.</b> ${esc(v.label)} — ${v.win ? 'applies' : v.has ? esc(v.note || 'not used') : 'no binding'}${v.note && !v.win ? ' · ' + esc(v.note) : ''}</li>`).join('')}</ol><div class="small muted" style="margin-top:8px">Most specific wins. Two bindings at the same level are refused when publishing, so a run can never see two routes.</div></details>
  <button class="btn ghost" data-act="coverage">${ic('gauge', 14)} Check whole coverage</button>
</div>`;
  }

  // ---------- coverage ----------
  P.runCoverage = function (b) {
    const rows = [];
    Object.keys(P.schemes).forEach(sk => {
      const sch = P.schemes[sk]; if (sch.binding === 'custom') return;
      sch.divisions.forEach(d => {
        const issues = [];
        decisionSteps(b).forEach(st => {
          if (st.who.mode === 'role' && st.who.scope === 'division' && !P.resolveSeat(st.who.role, d)) issues.push({ msg: 'No ' + P.roles[st.who.role].name + ' for ' + P.scopes[d], fix: { act: 'assignOpen', arg: st.who.role + '|' + d }, step: st.title });
        });
        rows.push({ scheme: sch.name, division: P.scopes[d], issues, employees: d === 'retail' ? 412 : 168 });
      });
    });
    return rows;
  };
  function coveragePanel(b) {
    if (!b.coverage) return `<div class="panel"><div class="panel-h"><div><h2>Whole coverage</h2><div class="s">One good example is not proof. This checks every scheme and division this workflow would apply to.</div></div><button class="btn primary" data-act="coverage">${ic('gauge', 14)} Check whole coverage</button></div></div>`;
    const bad = b.coverage.filter(r => r.issues.length);
    return `<div class="panel"><div class="panel-h"><div><h2>Whole coverage</h2><div class="s">Checked ${b.coverage.length} scheme and division combinations, ${b.coverage.reduce((a, r) => a + r.employees, 0).toLocaleString('en-US')} employees.</div></div><button class="btn ghost sm" data-act="coverage">${ic('refresh', 13)} Re-check</button></div>
    ${bad.length ? `<div class="attn rose" style="margin-bottom:12px">${ic('xCircle', 18)} <span>${bad.length} combination${bad.length > 1 ? 's' : ''} cannot be submitted yet.</span></div>` : `<div class="attn green" style="margin-bottom:12px">${ic('checkCircle', 18)} <span>Every combination has a full route. You can publish.</span></div>`}
    <div class="cov">${b.coverage.map(r => `<div class="covrow"><div><div class="t">${esc(r.scheme)} · ${esc(r.division)}</div><div class="s">${r.employees} employees · ${r.issues.length ? r.issues.map(i => i.step + ': ' + i.msg).join('; ') : 'Full route resolves'}</div></div><div>${r.issues.length ? `<button class="btn primary sm" data-act="${r.issues[0].fix.act}" data-arg="${r.issues[0].fix.arg}">Assign a person</button>` : `<span class="badge ok">Ready</span>`}</div></div>`).join('')}</div></div>`;
  }

  // ---------- screens per builder step ----------
  function progress(b) {
    const labels = ['Purpose', 'People', 'Safeguards', 'Review & publish'];
    return `<div class="progress">${labels.map((l, i) => `<button class="pstep ${b.step === i + 1 ? 'on' : b.step > i + 1 ? 'done' : ''}" data-act="bstep" data-arg="${i + 1}"><i>${b.step > i + 1 ? ic('check', 12) : i + 1}</i>${l}</button>${i < 3 ? '<span class="bar"></span>' : ''}`).join('')}</div>`;
  }
  function head(b) {
    return `<div class="bhead"><button class="btn quiet" data-act="go" data-arg="matrix" title="Back to the Matrix">${ic('arrowLeft', 16)}</button><h1 contenteditable="true" spellcheck="false" data-name="1">${esc(b.name)}</h1>${b.publishedNow ? '<span class="badge ok sentence">Published · v3</span>' : '<span class="badge muted sentence">Draft · v3</span><span class="badge info sentence">Published: v2</span>'}<span class="badge info sentence">${ic('building', 11)} Vietnam company default${b.scope.division ? ' · ' + esc(P.scopes[b.scope.division]) : ''}${b.scope.scheme ? ' · ' + esc(P.schemes[b.scope.scheme].name) : ''}${b.scope.runKind !== 'any' ? ' · ' + esc({ end: 'end of cycle', off: 'off-cycle', fnf: 'full & final' }[b.scope.runKind]) : ''}</span><span class="saved">${ic('check', 13)} ${esc(b.saved)}</span></div>`;
  }
  function purpose(b) {
    const overlap = !b.scope.division && !b.scope.scheme && b.scope.runKind === 'any';
    return `<div class="bgrid"><div style="display:flex;flex-direction:column;gap:16px">
<div class="panel"><div class="panel-h"><div><h2>What needs approval, and where?</h2><div class="s">Answer in your own words. Everything can change later.</div></div></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
    <div class="field" style="grid-column:1/-1"><label>Name</label><input class="input" value="${esc(b.name)}" data-bind="builder.name"></div>
    <div class="field"><label>Process</label><select class="input" data-bind="builder.process">${P.catalogue.filter(c => c.status !== 'soon').map(c => `<option value="${c.id}" ${b.process === c.id ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></div>
    <div class="field"><label>Company</label><input class="input" value="Rize Vietnam" disabled></div>
    <div class="field"><label>Division</label><select class="input" data-bind="builder.scope.division"><option value="">Any division (company default)</option>${P.divisions.map(d => `<option value="${d}" ${b.scope.division === d ? 'selected' : ''}>${esc(P.scopes[d])}</option>`).join('')}</select></div>
    <div class="field"><label>Scheme</label><select class="input" data-bind="builder.scope.scheme"><option value="">Any scheme</option>${Object.keys(P.schemes).map(k => `<option value="${k}" ${b.scope.scheme === k ? 'selected' : ''}>${esc(P.schemes[k].name)} · ${P.schemes[k].divisions.map(d => P.scopes[d]).join(', ')}</option>`).join('')}</select></div>
    <div class="field"><label>Run kind</label><select class="input" data-bind="builder.scope.runKind"><option value="any" ${b.scope.runKind === 'any' ? 'selected' : ''}>Any kind</option><option value="end" ${b.scope.runKind === 'end' ? 'selected' : ''}>End of cycle</option><option value="off" ${b.scope.runKind === 'off' ? 'selected' : ''}>Off-cycle</option><option value="fnf" ${b.scope.runKind === 'fnf' ? 'selected' : ''}>Full &amp; final</option></select></div>
  </div></div>
${overlap ? `<div class="note">${ic('info', 13)} This is the <b>company default</b> for pay runs. Every scheme and division follows it unless one has its own workflow or an exception.</div>` : `<div class="panel" style="border-color:var(--p)"><div class="panel-h"><div><h2>Use an existing workflow instead?</h2><div class="s">"Pay run approval" (Vietnam company default, v2) already covers this scope. A narrower workflow here would win over it for ${b.scope.scheme ? esc(P.schemes[b.scope.scheme].name) : ''}${b.scope.division ? (b.scope.scheme ? ' in ' : '') + esc(P.scopes[b.scope.division]) : ''}${b.scope.runKind !== 'any' ? ' · ' + esc({ end: 'end-of-cycle', off: 'off-cycle', fnf: 'full & final' }[b.scope.runKind]) + ' runs' : ''}.</div></div></div><div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn ghost sm" data-act="scopeReset">Edit the default instead</button><button class="btn outline sm" data-act="bstep" data-arg="2">Keep going · this is an exception</button></div></div>`}
<div class="bfoot"><span></span><button class="btn primary" data-act="bstep" data-arg="2">Continue ${ic('arrowRight', 14)}</button></div>
</div>
<div class="ex"><div class="exh"><h2>How scope works</h2></div><div class="ladder2"><div class="l"><span class="k">1 · wins</span><span>Scheme + division</span></div><div class="l"><span class="k">2</span><span>Scheme, any division</span></div><div class="l"><span class="k">3</span><span>Division, any scheme</span></div><div class="l"><span class="k">4</span><span>Company default</span></div></div><div class="small muted">Within a level, an exact run kind beats "Any kind". Two workflows at the same level for the same scope are refused when publishing.</div>
<div class="note">${ic('users', 13)} People are separate from the route. "HR lead" is resolved per division from <a data-act="go" data-arg="people" href="#">People &amp; backups</a>, so one shared route gives Retail and Operations their own approvers.</div></div></div>`;
  }
  function people(b) {
    return `<div class="bgrid"><div style="display:flex;flex-direction:column;gap:14px">
  <div class="rsent">${P.sentence(b)}</div>
  <div class="subm"><span class="k">Submitted by</span><span class="chip plain">${ic('user', 12)} Payroll preparer or anyone who can prepare a run</span><span class="small muted">Not part of the approval sequence</span></div>
  <div class="steps">${b.steps.map((st, i) => stepCard(st, i, b)).join('')}</div>
  ${addRow(b)}
  ${tiersPanel(b)}
  <div class="bfoot"><button class="btn ghost" data-act="bstep" data-arg="1">${ic('arrowLeft', 14)} Back</button><button class="btn primary" data-act="bstep" data-arg="3">Continue to safeguards ${ic('arrowRight', 14)}</button></div>
</div>${examplePanel(b)}</div>`;
  }
  function safeguards(b) {
    const sg = b.safeguards;
    return `<div class="bgrid"><div style="display:flex;flex-direction:column;gap:14px">
<div class="sggrid">
  <div class="sg"><h3>${ic('shieldCheck', 18)} Who may not approve?</h3>
    <div class="opt"><label class="radio ${sg.independent ? 'on' : ''}" data-act="sgSet" data-arg="independent|1"><i></i><span><div class="t">Require an independent person</div><div class="s">The preparer and submitter never decide their own run. Recommended.</div></span></label>
    <label class="radio ${!sg.independent ? 'on' : ''}" data-act="sgSet" data-arg="independent|0"><i></i><span><div class="t">No independence rule</div><div class="s">Anyone eligible may decide, even their own work. Not recommended for pay.</div></span></label></div>
    <div class="row"><label class="switch ${sg.selfException ? 'on' : 'off'}" data-act="sgToggle" data-arg="selfException"><i></i>Allow selected self-approval exceptions</label>${sg.selfException ? '<span class="badge warn sentence">Configured</span>' : ''}</div>
    ${sg.selfException ? `<div class="note amber"><b>Allow selected preparers to approve</b><br>Scope: ${esc(sg.selfScope)}<br>Eligible: ${esc(sg.selfEligible)}<br>A written reason is required every time. The decision is marked "Exception used" in the request and the audit console. It never lets one person fill two seats of a joint approval.</div>` : ''}
    <div class="field"><label>If the same person appears at two steps</label><select class="input" data-bind="builder.safeguards.repeated"><option value="different" ${sg.repeated === 'different' ? 'selected' : ''}>Send the later step to a different eligible person</option><option value="reason" ${sg.repeated === 'reason' ? 'selected' : ''}>Allow it, with a written reason each time</option></select></div>
  </div>
  <div class="sg"><h3>${ic('paperclip', 18)} What must be attached?</h3>
    <div>${sg.evidence.map((e, i) => `<label class="checkrow ${e.on ? 'on' : ''}" data-act="sgEvidence" data-arg="${i}"><span class="cb">${e.on ? ic('check', 12) : ''}</span><span>${esc(e.n)}</span><span class="s">${esc(e.when)}</span></label>`).join('')}</div>
    <div class="small muted">Generated reports are locked to the run. Replacing a report after submission restarts the approvals.</div>
    <button class="btn ghost sm" data-act="toast" data-arg="Add a named document, when it is required, and what kind of file is acceptable.">${ic('plus', 12)} Add a requirement</button>
  </div>
  <div class="sg"><h3>${ic('clock', 18)} When is this due?</h3>
    <div class="field"><label>Target</label><select class="input" data-bind="builder.safeguards.due"><option value="1wd" ${sg.due === '1wd' ? 'selected' : ''}>Within 1 working day of each step</option><option value="day15" ${sg.due === 'day15' ? 'selected' : ''}>By the payroll cut-off (day 15, 17:00)</option><option value="request" ${sg.due === 'request' ? 'selected' : ''}>Chosen on each request</option><option value="none" ${sg.due === 'none' ? 'selected' : ''}>No target</option></select></div>
    <div class="field"><label>Calendar</label><select class="input"><option>Vietnam company working calendar · Mon–Fri · public holidays</option></select></div>
    <div class="note">${ic('calendar', 13)} The example on the right shows the exact local date and time each step is due. "Day 15" only works once the calendar, cut-off hour and weekend rule are set.</div>
  </div>
  <div class="sg"><h3>${ic('bell', 18)} If it is late?</h3>
    <div class="ladder2"><div class="l"><span class="k">After 1 day</span><span>Remind the approver</span></div><div class="l"><span class="k">After 2 days</span><span>Tell the workflow owner (you)</span></div><div class="l"><span class="k">Reassign</span><label class="switch ${sg.reassign ? 'on' : 'off'}" data-act="sgToggle" data-arg="reassign"><i></i>${sg.reassign ? 'To the backup, logged' : 'Off · ask before moving it'}</label></div></div>
    <div class="note rose">${ic('ban', 13)} A late request is never approved automatically. Nothing in this system approves on its own.</div>
  </div>
</div>
<div class="bfoot"><button class="btn ghost" data-act="bstep" data-arg="2">${ic('arrowLeft', 14)} Back</button><button class="btn primary" data-act="bstep" data-arg="4">Review &amp; publish ${ic('arrowRight', 14)}</button></div>
</div>${examplePanel(b)}</div>`;
  }
  function review(b) {
    const cur = decisionSteps(b), pub = b.published.steps;
    const diff = [];
    cur.forEach(st => { const p = pub.find(x => x.title === st.title); if (!p) diff.push(['Added', st.title, st.kind === 'fast' ? 'Pay runs are applied immediately and logged. No one decides.' : (b.tiers && st.min ? 'Only when the net total is ' + fmt(st.min) + ' or more. ' : '') + 'Decided by ' + P.whoLabel(st.who) + '.']); else if (b.tiers && p.min !== st.min) diff.push(['Changed', st.title, st.min ? 'Now only when the net total is ' + fmt(st.min) + ' or more. Before: always.' : 'Now applies to every run. Before: from ' + fmt(p.min) + '.']); });
    pub.forEach(p => { if (!cur.find(x => x.title === p.title)) diff.push(['Removed', p.title, 'This check no longer happens.']); });
    const acks = b.acks || {};
    const warns = [];
    const fast = b.steps.some(s => s.kind === 'fast');
    if (fast) warns.push(['fast', 'Nobody checks pay runs before they are applied. Every run is still logged.']);
    const distinct = new Set(); cur.forEach(st => { if (st.who.mode === 'people') st.who.people.forEach(p => distinct.add(p)); else if (st.who.mode !== 'none') distinct.add(st.who.mode + ':' + (st.who.role || st.who.team || '')); });
    if (!fast && distinct.size < 2) warns.push(['one', 'Only one person signs off pay. Two people are recommended when money leaves the company.']);
    if (!b.safeguards.independent) warns.push(['indep', 'The independence rule is off: the same person may prepare and approve a run.']);
    if (!b.coverage) warns.push(['nocov', 'Whole coverage has not been checked. One good example is not proof that every division has people.']);
    else b.coverage.filter(r => r.issues.length).forEach(r => warns.push(['cov:' + r.scheme + r.division, r.scheme + ' · ' + r.division + ': ' + r.issues.map(i => i.msg).join('; ') + '. Runs from there will be blocked at submission until someone is assigned.']));
    const blocked = warns.some(w => !acks[w[0]]);
    if (b.publishedNow) return `<div class="rvgrid"><div class="success"><h2>${ic('checkCircle', 20)} Workflow published · version 3</h2><p>New pay runs submitted from <b>01 Oct 2026, 09:00 (Asia/Ho_Chi_Minh)</b> follow this route. The 2 requests already in progress keep the people and steps they were given.</p><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px"><button class="btn primary" data-act="go" data-arg="matrix">Back to the Matrix</button><button class="btn ghost" data-act="go" data-arg="inbox">Open the inbox</button><button class="btn ghost" data-act="go" data-arg="scheme">Return to the scheme</button></div></div>
    <div class="ex"><div class="exh"><h2>What was recorded</h2></div><div class="kv"><dt>Version</dt><dd>3 (replaces 2)</dd><dt>Published by</dt><dd>You · Payroll administrator</dd><dt>Reason</dt><dd>Add director sign-off for large runs</dd><dt>Starts</dt><dd>01 Oct 2026, 09:00</dd><dt>Coverage</dt><dd>4 combinations checked, all ready</dd></div></div></div>`;
    return `<div class="rvgrid"><div style="display:flex;flex-direction:column;gap:14px">
<div class="panel"><div class="panel-h"><div><h2>What changes</h2><div class="s">Compared with version 2, published 31 Aug 2026.</div></div></div>
  <div class="diff">${diff.length ? diff.map(d => `<div class="diffrow"><span class="badge ${d[0] === 'Added' ? 'ok' : d[0] === 'Removed' ? 'err' : 'warn'}">${d[0]}</span><div><div class="t">${esc(d[1])}</div><div class="s">${esc(d[2])}</div></div></div>`).join('') : `<div class="note">No difference from version 2. Nothing to publish.</div>`}</div></div>
<div class="panel"><div class="panel-h"><div><h2>Who is affected</h2><div class="s">Schemes that follow the company default change with it. Custom ones do not.</div></div></div>
  <div class="aff">${Object.keys(P.schemes).map(k => { const s = P.schemes[k]; return `<div class="affrow"><span>${esc(s.name)} <span class="small muted">· ${s.divisions.map(d => P.scopes[d]).join(', ')}</span></span>${s.binding === 'custom' ? '<span class="badge muted sentence">Custom · not affected</span>' : '<span class="badge info sentence">Follows the default</span>'}</div>`; }).join('')}</div></div>
${coveragePanel(b)}
<div class="bfoot"><button class="btn ghost" data-act="bstep" data-arg="3">${ic('arrowLeft', 14)} Back</button><span></span></div>
</div>
<div class="ex">
  <div class="res">${blocked ? `<span class="badge warn sentence" style="font-size:12px;padding:6px 12px">${ic('alert', 13)} ${warns.length} thing${warns.length > 1 ? 's' : ''} to confirm</span>` : `<span class="badge ok sentence" style="font-size:12px;padding:6px 12px">${ic('checkCircle', 13)} Ready to publish</span>`}</div>
  ${warns.length ? `<div style="display:flex;flex-direction:column;gap:6px">${warns.map(w => `<label class="checkrow ${acks[w[0]] ? 'on' : ''}" data-act="ackToggle" data-arg="${esc(w[0])}" style="align-items:flex-start"><span class="cb" style="margin-top:2px">${acks[w[0]] ? ic('check', 12) : ''}</span><span style="font-size:12.5px">${esc(w[1])}</span></label>`).join('')}<div class="small muted">Tick each one to confirm. Your confirmations are recorded with the publish. Nothing here stops you; the business knows best.</div></div>` : ''}
  <div class="field"><label>New submissions from</label><input class="input" type="datetime-local" value="${esc(b.publishAt)}" data-bind="builder.publishAt"><span class="small muted">Asia/Ho_Chi_Minh</span></div>
  <div class="field"><label>Reason (recorded in History)</label><input class="input" value="Add director sign-off for large runs"></div>
  <div class="kv"><dt>In progress</dt><dd>2 requests keep version 2</dd><dt>Publishing</dt><dd>You · Payroll administrator</dd><dt>Approval power</dt><dd>Publishing does not make you an approver</dd></div>
  ${blocked ? '' : `<div class="note green">${ic('checkCircle', 13)} ${warns.length ? 'Confirmed. ' : 'Coverage passed. '}Warnings on individual requests still show at submission.</div>`}
  <button class="btn primary" style="width:100%;justify-content:center;padding:12px" data-act="publish" ${blocked || !diff.length ? 'disabled' : ''}>${ic('stamp', 15)} Publish version 3</button>
</div></div>`;
  }

  P.screens.builder = function (s) {
    const b = s.builder;
    const body = b.step === 1 ? purpose(b) : b.step === 2 ? people(b) : b.step === 3 ? safeguards(b) : review(b);
    return head(b) + progress(b) + body;
  };

  // ---------- picker drawer ----------
  P.drawers.picker = function (s) {
    const pk = s.builder.picker; const b = s.builder;
    const cards = [
      { m: 'manager', t: 'Their manager', s: 'Best for requests about one person', i: 'user' },
      { m: 'skip', t: "Manager's manager", s: 'For bigger asks', i: 'users' },
      { m: 'role', t: 'A role in this scope', s: 'Best for payroll and HR batches', i: 'briefcase' },
      { m: 'people', t: 'Specific people', s: 'Fixed signatories', i: 'userCheck' },
      { m: 'team', t: 'One of a team', s: 'First eligible member decides', i: 'inbox' },
    ];
    const tmp = { ...b, steps: b.steps.map(st => st.id === pk.stepId ? { ...st, who: pk.who } : st) };
    const r = P.evalRoute(tmp, b.example).steps.find(x => x.st.id === pk.stepId);
    const w = pk.who;
    let form = '';
    if (w.mode === 'role') form = `<div class="ex"><div class="grid2"><div class="field"><label>Role</label><select class="input" data-bind="builder.picker.who.role">${Object.keys(P.roles).map(k => `<option value="${k}" ${w.role === k ? 'selected' : ''}>${esc(P.roles[k].name)}</option>`).join('')}</select></div><div class="field"><label>Scope</label><select class="input" data-bind="builder.picker.who.scope"><option value="division" ${w.scope === 'division' ? 'selected' : ''}>The run's division</option><option value="company" ${w.scope === 'company' ? 'selected' : ''}>Whole company</option></select></div></div>
      <div><div class="small muted" style="font-weight:800;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">Currently assigned</div>${['company', 'retail', 'operations'].map(sc => { const v = s.resp[w.role + '|' + sc]; return `<div class="checkrow"><span style="min-width:130px;color:var(--muted)">${esc(P.scopes[sc])}</span>${v ? (v.pool ? 'Any of ' + v.pool.map(P.pshort).join(', ') : `<span class="person"><span class="av sm">${P.people[v.person].ini}</span><b>${esc(P.pshort(v.person))}</b><span class="badge ok">Eligible</span></span>`) : (P.roles[w.role].fallback ? '<span class="muted">Inherits company</span>' : `<span class="badge err sentence">Needs a person</span> <button class="btn quiet xs" data-act="assignOpen" data-arg="${w.role}|${sc}">Assign</button>`)}</div>`; }).join('')}</div>
      <div class="note">${ic('info', 13)} ${esc(P.roles[w.role].desc)}. ${P.roles[w.role].fallback ? 'If a division has no one, the company person covers it (shown as "fallback").' : 'Each division needs its own person; there is no silent fallback to "all HR users".'}</div></div>`;
    else if (w.mode === 'people') form = `<div class="ex"><div class="plist">${['nithya', 'monica', 'thao', 'linh', 'duc'].map(k => `<div class="prow ${w.people.includes(k) ? 'on' : ''}" data-act="pickPerson" data-arg="${k}"><span class="av">${P.people[k].ini}</span><div><div style="font-weight:700">${esc(P.pname(k))}</div><div class="small muted">${esc(P.people[k].title)}${k === 'linh' ? ' · Needs the "Payroll approver" role' : ''}</div></div>${k === 'linh' ? '<span class="badge warn sentence">Needs permission</span>' : ''}<span class="cb">${w.people.includes(k) ? ic('check', 12) : ''}</span></div>`).join('')}</div>
      ${w.people.length > 1 ? `<div class="seg"><button class="${w.all ? 'on' : ''}" data-act="pickAll" data-arg="1">Everyone must approve</button><button class="${!w.all ? 'on' : ''}" data-act="pickAll" data-arg="0">Any one of them</button></div>` : ''}
      <div class="note">${ic('info', 13)} Choosing a name never grants access or creates an account. Named people are fixed until you publish a new version.</div></div>`;
    else if (w.mode === 'team') form = `<div class="ex"><div class="field"><label>Team</label><select class="input" data-bind="builder.picker.who.team"><option ${w.team === 'Vietnam payroll desk' ? 'selected' : ''}>Vietnam payroll desk</option><option ${w.team === 'Finance shared services' ? 'selected' : ''}>Finance shared services</option></select></div><div class="note">4 eligible members. The first to decide closes the step. Members who prepared the run are excluded by the independence rule.</div></div>`;
    else form = `<div class="ex"><div class="note amber">${ic('alert', 13)} A pay run covers many employees, so "${w.mode === 'manager' ? 'Their manager' : "Manager's manager"}" would split the run into one review group per manager. This choice is best for one-person requests such as timesheets, leave and pay changes.</div></div>`;
    return `<div class="dh"><div><h2>Who should decide this step?</h2><div class="s">Choose how the step finds the right person. The example shows who that is right now.</div></div><button class="x" data-act="closeDrawer" aria-label="Close">${ic('x', 18)}</button></div>
<div class="db">
  <div class="pickcards">${cards.map(c => `<button class="pick ${w.mode === c.m ? 'on' : ''}" data-act="pickMode" data-arg="${c.m}"><span class="h"><i>${w.mode === c.m ? ic('check', 11) : ''}</i>${ic(c.i, 15)} ${esc(c.t)}</span><span class="s">${esc(c.s)}</span></button>`).join('')}</div>
  ${form}
  <div class="goesto"><div class="t">This step will go to · for the example (${esc(P.scopes[b.example.division])})</div>${r && r.people.length ? r.people.map(p => personChip(p)).join('') : `<span class="badge err sentence">${ic('userX', 11)} ${r && r.issue ? esc(r.issue.msg) : 'No one yet'}</span>`}${r && r.issue && r.issue.level === 'warn' ? `<div class="small" style="color:var(--amber)">${esc(r.issue.msg)}</div>` : ''}<div class="small muted">For new requests, a change of role holder updates the route automatically. Requests in progress keep their people.</div></div>
</div>
<div class="df"><button class="btn ghost" data-act="closeDrawer">Cancel</button><button class="btn primary" data-act="pickerSave" ${w.mode === 'people' && !w.people.length ? 'disabled' : ''}>Use this</button></div>`;
  };

  // ---------- actions ----------
  const clone = (o) => JSON.parse(JSON.stringify(o));
  Object.assign(P.actions, {
    bstep(n) { B().step = Number(n); B().addMenu = false; window.scrollTo({ top: 0 }); },
    scopeReset() { B().scope = { division: '', scheme: '', runKind: 'any' }; },
    tiersToggle() { B().tiers = !B().tiers; B().saved = 'Saved just now'; },
    addMenu() { B().addMenu = !B().addMenu; },
    stepAdd(k) {
      const b = B(); b.addMenu = false; const id = 's' + (++b.seq);
      if (k === 'fast') { b.steps = [{ id, kind: 'fast', title: 'No approval needed', who: { mode: 'none' }, min: 0, cond: '' }].concat(b.steps.filter(s => s.kind === 'notify')); b.tiers = false; b.coverage = null; P.toast('Pay runs will be applied immediately and logged. You will confirm this when publishing.'); return; }
      const st = k === 'joint' ? { id, kind: 'joint', title: 'Joint sign-off', who: { mode: 'people', people: ['nithya', 'monica'], all: true }, min: 0, cond: '' }
        : k === 'any' ? { id, kind: 'any', title: 'Payroll desk check', who: { mode: 'team', team: 'Vietnam payroll desk' }, min: 0, cond: '' }
          : k === 'notify' ? { id, kind: 'notify', title: 'Tell the HR lead', who: { mode: 'preparer' }, min: 0, cond: '' }
            : k === 'cond' ? { id, kind: 'approve', title: 'Payroll manager check', who: { mode: 'role', role: 'payroll_mgr', scope: 'company' }, min: 0, cond: 'overtime' }
              : k === 'review' ? { id, kind: 'review', title: 'Payroll manager review', who: { mode: 'role', role: 'payroll_mgr', scope: 'company' }, min: 0, cond: '' }
                : { id, kind: 'approve', title: 'Final approval', who: { mode: 'role', role: 'director', scope: 'company' }, min: 0, cond: '' };
      b.steps = b.steps.filter(s => s.kind !== 'fast');
      const notifyIdx = b.steps.findIndex(s => s.kind === 'notify');
      if (st.kind !== 'notify' && notifyIdx >= 0) b.steps.splice(notifyIdx, 0, st); else b.steps.push(st);
      b.saved = 'Saving…'; setTimeout(() => { b.saved = 'Saved just now'; P.render(); }, 600);
      if (st.kind !== 'notify') { b.picker = { stepId: id, who: clone(st.who) }; S().drawer = { type: 'picker' }; }
    },
    stepRemove(id) { const b = B(); b.steps = b.steps.filter(s => s.id !== id); b.coverage = null; if (!b.steps.some(s => s.kind !== 'notify')) { b.steps.unshift({ id: 's' + (++b.seq), kind: 'fast', title: 'No approval needed', who: { mode: 'none' }, min: 0, cond: '' }); b.tiers = false; P.toast('No steps left, so pay runs would be applied immediately and logged. Add a step to bring a check back.'); } },
    stepRemoveFast(id) { const b = B(); b.steps = b.steps.filter(s => s.id !== id); b.addMenu = true; P.toast('Choose the first step for this process.'); },
    ackToggle(k) { const b = B(); b.acks = b.acks || {}; b.acks[k] = !b.acks[k]; },
    sgIndependentOff() { B().safeguards.independent = false; P.toast('Independence rule off for this workflow. The same person may prepare and approve. This is recorded with the publish.'); },
    stepMove(arg) { const [i, d] = arg.split('|').map(Number); const b = B(); const j = i + d; if (j < 0 || j >= b.steps.length) return false; const t = b.steps[i]; b.steps[i] = b.steps[j]; b.steps[j] = t; },
    stepAll(arg) { const [id, v] = arg.split('|'); const st = B().steps.find(s => s.id === id); st.who.all = v === '1'; st.kind = st.who.all ? 'joint' : 'any'; },
    pickerOpen(id) { const st = B().steps.find(s => s.id === id); B().picker = { stepId: id, who: clone(st.who) }; S().drawer = { type: 'picker' }; },
    pickMode(m) { const w = B().picker.who; w.mode = m; if (m === 'role' && !w.role) { w.role = 'hr_lead'; w.scope = 'division'; } if (m === 'people' && !w.people) { w.people = ['nithya']; w.all = true; } if (m === 'team' && !w.team) w.team = 'Vietnam payroll desk'; },
    pickPerson(k) { const w = B().picker.who; w.people = w.people.includes(k) ? w.people.filter(x => x !== k) : w.people.concat(k); },
    pickAll(v) { B().picker.who.all = v === '1'; },
    pickerSave() { const b = B(); const st = b.steps.find(s => s.id === b.picker.stepId); st.who = clone(b.picker.who); if (st.who.mode === 'people' && st.who.people.length > 1) st.kind = st.who.all ? 'joint' : 'any'; else if (st.kind === 'joint' || st.kind === 'any') st.kind = 'approve'; b.picker = null; S().drawer = null; b.coverage = null; P.toast('Step updated. The sentence and the example reflect it.'); },
    exOvertime() { B().example.overtime = !B().example.overtime; },
    exClearOverride() { B().example.override = {}; },
    exUseBackup(arg) { const [id, k] = arg.split('|'); const ex = B().example; ex.override = ex.override || {}; ex.override[id] = k; P.toast('For this example, the step goes to ' + P.pshort(k) + '. On a real request this is a logged reassignment.'); },
    sgSet(arg) { const [k, v] = arg.split('|'); B().safeguards[k] = v === '1'; },
    sgToggle(k) { B().safeguards[k] = !B().safeguards[k]; },
    sgEvidence(i) { const e = B().safeguards.evidence[Number(i)]; e.on = !e.on; },
    coverage() { const b = B(); b.coverage = P.runCoverage(b); const bad = b.coverage.filter(r => r.issues.length).length; P.toast(bad ? bad + ' combination(s) need a person before this can be published.' : 'Coverage passed for every scheme and division.'); },
    publish() {
      const b = B(); b.publishedNow = true; b.published = { ver: 3, steps: decisionSteps(b).map(s => ({ title: s.title, min: s.min })) };
      const c = P.catalogue.find(x => x.id === 'payrun'); c.sub = 'Followed by 2 schemes · 1 custom · v3 from 01 Oct';
      S().inbox.requests.forEach(r => { if (r.process === 'payrun') r.wf = 'Pay run approval · v2 (kept)'; });
      P.toast('Published. Future pay runs use version 3 from 01 Oct 2026, 09:00.');
    },
  });
  // inline title / name editing
  document.addEventListener('blur', (ev) => {
    const el = ev.target;
    if (el.dataset && el.dataset.title) { const st = B().steps.find(s => s.id === el.dataset.title); if (st) { st.title = el.textContent.trim() || st.title; B().saved = 'Saved just now'; P.render(); } }
    if (el.dataset && el.dataset.name) { B().name = el.textContent.trim() || B().name; P.render(); }
  }, true);
})(window.POC);
