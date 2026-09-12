/* Where it applies: the reconciled "Connect" step (3 of 6) inside New configuration */
(function (P) {
  const S = () => P.state;
  const esc = P.esc;

  function routeText(labels) { return labels.map((l, i) => (i ? ic('arrowRight', 12) : '') + `<span>${esc(l)}</span>`).join(''); }

  P.screens.scheme = function (s) {
    const sc = s.scheme; const b = s.builder;
    const defRoute = P.routeLabels(b);
    const steps = ['Start', 'Pay rules', 'Connect', 'Outputs', 'Test', 'Finish'];
    const exc = sc.exceptions;
    const chosenLabel = { inherit: 'Using the company default', shared: 'Using a shared workflow', custom: 'Custom for this scheme' }[sc.choice];
    return `<div class="hero"><div><div class="eyebrow">${ic('zap', 13)} Pay Run · New configuration</div><h1>Connect what you need.</h1><div class="sub">Retail monthly · Vietnam · step 3 of 6. The same six-step journey; the Approvals card is now real.</div></div><div class="hero-r"><span class="badge muted sentence">Draft configuration</span></div></div>
<div class="bptop">${steps.map((t, i) => `<span class="pstep ${i < 2 ? 'done' : i === 2 ? 'on' : ''}"><i>${i < 2 ? ic('check', 12) : i + 1}</i>${t}</span>${i < 5 ? '<span class="bar"></span>' : ''}`).join('')}</div>
<div class="bpgrid">
  <div class="panel"><div class="panel-h"><div><h2>Your connections</h2></div></div>
    <div class="conn">
      <div class="connrow"><div class="t">Data sources</div><div class="s">Connected · Zoho People</div></div>
      <div class="connrow"><div class="t">Payslip layout</div><div class="s">Ready · Vietnam standard</div></div>
      <div class="connrow on"><div class="t">Approvals</div><div class="s">${esc(chosenLabel)}${exc.length ? ' · ' + exc.length + ' division exception' + (exc.length > 1 ? 's' : '') : ''}</div></div>
    </div>
    <div class="note" style="margin-top:14px">${ic('info', 13)} Finish can save a draft. Activating the scheme and submitting a pay run both need a complete approval route.</div>
  </div>
  <div class="panel">
    <div class="panel-h"><div><h2>Approval workflows</h2><div class="s">Choose the checks for this scheme. Two different decisions, kept apart.</div></div></div>
    <div class="aprow"><div>
      <div class="h"><span class="t">Pay run approval</span><span class="badge ${sc.choice === 'inherit' ? 'info' : sc.choice === 'shared' ? 'blue' : 'teal'} sentence">${sc.choice === 'inherit' ? 'Inherited' : sc.choice === 'shared' ? 'Shared' : 'Custom for this scheme'}</span>${sc.saved ? '<span class="badge ok">Saved</span>' : ''}</div>
      <div class="wf">${sc.choice === 'shared' ? 'Retail payroll sign-off' : sc.choice === 'custom' ? 'Retail monthly · custom route' : esc(b.name)}</div>
      <div class="rt">${sc.choice === 'shared' ? routeText(['HR lead', 'Finance approver']) : sc.choice === 'custom' ? routeText(['HR lead', 'Finance approver + Country director (everyone)']) : routeText(defRoute)}</div>
      <div class="src">Source: ${sc.choice === 'inherit' ? 'Vietnam company default · ' + (b.publishedNow ? 'version 3 from 01 Oct' : 'version 2') : sc.choice === 'shared' ? 'Shared with 2 other schemes' : 'Only this scheme · visible in the Matrix as "Custom for Retail monthly"'}</div>
      ${exc.length ? `<div class="exc" style="margin-top:10px">${exc.map((e, i) => `<div class="excrow"><span class="d">${esc(P.scopes[e.division])}</span><span>${esc(e.workflow)} · ${esc(e.route)}</span><button class="btn quiet xs" data-act="excRemove" data-arg="${i}">Remove</button></div>`).join('')}</div>` : ''}
    </div><div><button class="btn ghost" data-act="schemeChange">${sc.changing ? 'Close' : 'Change'}</button></div></div>
    ${sc.changing ? changePanel(s) : ''}
    <div class="aprow"><div>
      <div class="h"><span class="t">Scheme change approval</span><span class="badge blue sentence">Shared</span></div>
      <div class="wf">Scheme change</div>
      <div class="rt">${routeText(['Scheme owner', 'Payroll manager', 'Country director'])}</div>
      <div class="src">Approves an exact proposal before it is activated, released, rolled back or merged. Editing continues on the next proposal; nothing changes in live pay until approved.</div>
    </div><div><button class="btn ghost" data-act="toast" data-arg="Opens the same chooser for the scheme-change workflow. Editing a scheme never lets you weaken its own approval rule.">Change</button></div></div>
    <div class="aprow"><div>
      <div class="h"><span class="t">Related approvals</span></div>
      <div class="rt" style="margin-top:6px"><span class="chip ok">${ic('checkCircle', 12)} Weekly timesheets · needs 1 manager</span><span class="chip ok">${ic('checkCircle', 12)} Bank file &amp; payment release · Published</span><span class="chip plain">${ic('bell', 12)} Payslip send-out · notify only</span></div>
      <div class="src">Prerequisites shown for information; they are configured once, in the Matrix.</div>
    </div><div><button class="btn ghost" data-act="go" data-arg="matrix">Open Matrix</button></div></div>
  </div>
</div>
<div class="bfoot"><button class="btn ghost">${ic('arrowLeft', 14)} Pay rules</button><span class="small muted">Finish shows real approval coverage, not "already in place".</span><button class="btn primary">Continue to Outputs ${ic('arrowRight', 14)}</button></div>`;
  };

  function changePanel(s) {
    const sc = s.scheme; const b = s.builder;
    const defRoute = P.routeLabels(b);
    const opts = [
      { k: 'inherit', t: 'Use the default for each division', s: 'Recommended. Retail and Operations keep their own people; the route is the company default.', sub: sc.choice === 'inherit' ? `<div class="wwh"><div class="div"><div class="t">Retail</div><div class="r">${routeText(resolvedFor('retail', b))}</div><div class="s">${esc(b.name)} · company default</div></div><div class="div"><div class="t">Operations</div><div class="r">${routeText(resolvedFor('operations', b))}</div><div class="s">${S().resp['hr_lead|operations'] ? esc(b.name) + ' · company default' : 'HR lead for Operations not assigned · cannot submit'}</div></div></div>` : '' },
      { k: 'shared', t: 'Use a shared workflow', s: 'One route structure, with people resolved for each division.', sub: sc.choice === 'shared' ? `<div class="field"><label>Workflow</label><select class="input"><option>Retail payroll sign-off · HR lead → Finance approver · used by 2 schemes</option><option>Officer → HR → Finance · used by 1 scheme</option></select></div>` : '' },
      { k: 'custom', t: 'Customize for this scheme', s: 'Start from the route above, then tailor the steps. Creates a variation only this scheme uses, visible centrally.', sub: sc.choice === 'custom' ? `<div class="note amber">${ic('alert', 13)} Retail monthly currently follows the company default. Customizing starts from that route. Later changes to the default will <b>not</b> reach this scheme; a "Compare with original" is offered.</div><div style="margin-top:8px"><button class="btn outline sm" data-act="go" data-arg="builder">${ic('pencil', 12)} Open the builder for this scheme</button></div>` : '' },
    ];
    return `<div style="padding:6px 0 18px;display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:18px;align-items:start">
  <div style="display:flex;flex-direction:column;gap:14px">
    <div class="choices">${opts.map(o => `<label class="choice ${sc.choice === o.k ? 'on' : ''}" data-act="schemeChoice" data-arg="${o.k}"><i></i><span><div class="t">${esc(o.t)}</div><div class="s">${esc(o.s)}</div>${o.sub ? `<div class="sub">${o.sub}</div>` : ''}</span></label>`).join('')}</div>
    <div class="panel" style="padding:14px 16px"><div class="panel-h" style="margin-bottom:8px"><div><h2>Exceptions for a division</h2><div class="s">A division inside this scheme can follow a different workflow. Most specific wins.</div></div></div>
      <div class="exc">${sc.exceptions.map((e, i) => `<div class="excrow"><span class="d">${esc(P.scopes[e.division])}</span><span>${esc(e.workflow)} · ${esc(e.route)}</span><button class="btn quiet xs" data-act="excRemove" data-arg="${i}">Remove</button></div>`).join('')}
      ${sc.adding ? `<div class="excrow" style="background:var(--soft)"><select class="input" data-bind="scheme.newDiv"><option value="retail">Retail</option><option value="operations">Operations</option></select><select class="input" data-bind="scheme.newWf"><option value="Retail payroll sign-off">Retail payroll sign-off · HR lead → Finance approver</option><option value="Joint sign-off">Joint sign-off · Nithya + Monica (everyone)</option></select><button class="btn primary sm" data-act="excSave">Add</button></div>` : `<button class="btn quiet sm" data-act="excAdd">${ic('plus', 12)} Add a division exception</button>`}</div></div>
  </div>
  <div class="ex"><div class="exh"><h2>What will happen?</h2></div>
    <span class="badge ${sc.choice === 'custom' ? 'teal' : 'info'} sentence">${sc.choice === 'inherit' ? 'Inherited from Vietnam' : sc.choice === 'shared' ? 'Shared with 2 schemes' : 'Custom for Retail monthly'}</span>
    <div class="wwh">${P.schemes.retail.divisions.map(d => { const e = sc.exceptions.find(x => x.division === d); return `<div class="div"><div class="t">${esc(P.scopes[d])}</div><div class="r">${e ? routeText(e.route.split(' → ')) : sc.choice === 'shared' ? routeText(['HR lead · ' + P.scopes[d], 'Finance approver']) : sc.choice === 'custom' ? routeText(['HR lead · ' + P.scopes[d], 'Finance approver + Country director']) : routeText(resolvedFor(d, b))}</div><div class="s">${e ? 'Exception · ' + esc(e.workflow) : sc.choice === 'inherit' ? 'Company default' : sc.choice === 'shared' ? 'Shared workflow' : 'Scheme-wide custom route'}</div></div>`; }).join('')}</div>
    <div class="small muted">Changing this affects new pay runs only. 1 run in progress keeps its route.</div>
    <button class="btn primary" style="width:100%;justify-content:center" data-act="schemeSave">Save selection</button>
  </div></div>`;
  }
  function resolvedFor(d, b) {
    return b.steps.filter(s => s.kind !== 'notify').map(st => {
      if (st.who.mode === 'role') { const seat = P.resolveSeat(st.who.role, st.who.scope === 'division' ? d : null); const nm = seat ? (seat.pool ? 'Any of ' + seat.pool.length : P.pshort(P.coverFor(seat.person) || seat.person) + (P.coverFor(seat.person) ? ' (covering)' : '')) : 'No one · ' + P.roles[st.who.role].name; return nm + (b.tiers && st.min ? ' (' + P.fmtShort(st.min) + '+)' : ''); }
      return P.whoLabel(st.who) + (b.tiers && st.min ? ' (' + P.fmtShort(st.min) + '+)' : '');
    });
  }
  Object.assign(P.actions, {
    schemeChange() { S().scheme.changing = !S().scheme.changing; S().scheme.saved = false; },
    schemeChoice(k) { S().scheme.choice = k; S().scheme.saved = false; },
    excAdd() { S().scheme.adding = true; S().scheme.newDiv = 'retail'; S().scheme.newWf = 'Retail payroll sign-off'; },
    excSave() { const sc = S().scheme; sc.exceptions = sc.exceptions.filter(e => e.division !== sc.newDiv); sc.exceptions.push({ division: sc.newDiv, workflow: sc.newWf, route: sc.newWf === 'Joint sign-off' ? 'Nithya + Monica (everyone)' : 'HR lead → Finance approver' }); sc.adding = false; P.toast('Exception added for ' + P.scopes[sc.newDiv] + '. It wins over the scheme route for that division.'); },
    excRemove(i) { S().scheme.exceptions.splice(Number(i), 1); },
    schemeSave() { S().scheme.saved = true; S().scheme.changing = false; P.toast('Saved. The Connect card and Finish now show this choice; new pay runs for Retail monthly use it.'); },
  });
})(window.POC);
