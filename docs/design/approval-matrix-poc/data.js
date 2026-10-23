/* Sample data + state for the Approval Matrix POC. Everything here is example data. */
window.POC = window.POC || {};
(function (P) {
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  P.esc = esc;
  P.fmtVND = (n) => '₫' + Math.round(n).toLocaleString('en-US');
  P.fmtShort = (n) => (n >= 1e9 ? '₫' + (n / 1e9).toLocaleString('en-US', { maximumFractionDigits: 2 }) + 'bn' : n >= 1e6 ? '₫' + Math.round(n / 1e6).toLocaleString('en-US') + 'm' : P.fmtVND(n));
  P.TODAY = 'Sat 12 Sep 2026';

  P.people = {
    nithya: { name: 'Nithya', title: 'HR Manager', ini: 'NI' },
    monica: { name: 'Monica', title: 'Finance Manager', ini: 'MO' },
    thao: { name: 'Nguyen Thi Phuong Thao', short: 'Thao', title: 'Country Director', ini: 'PT' },
    linh: { name: 'Linh Nguyen', title: 'Payroll preparer', ini: 'LN' },
    thaominh: { name: 'Thao Minh', title: 'Retail store manager', ini: 'TM' },
    duc: { name: 'Duc Pham', title: 'Operations manager', ini: 'DP' },
    minh: { name: 'Minh Tran', title: 'Sales associate · Retail', ini: 'MT' },
    an: { name: 'An Le', title: 'Warehouse associate · Operations', ini: 'AL' },
    admin: { name: 'You', title: 'Payroll administrator', ini: 'AD' },
  };
  P.pname = (k) => (P.people[k] ? P.people[k].name : k);
  P.pshort = (k) => (P.people[k] ? (P.people[k].short || P.people[k].name) : k);

  P.roles = {
    hr_lead: { name: 'HR lead', fallback: false, desc: 'Checks people and amounts for a division' },
    finance: { name: 'Finance approver', fallback: true, desc: 'Releases money' },
    payroll_mgr: { name: 'Payroll manager', fallback: true, desc: 'Owns the payroll process' },
    director: { name: 'Country director', fallback: true, desc: 'Final authority in the company' },
    scheme_owner: { name: 'Scheme owner', fallback: true, desc: 'Owns a pay scheme' },
    budget: { name: 'Budget holder', fallback: false, desc: 'Owns a division budget' },
    signatory: { name: 'Bank signatory', fallback: true, desc: 'Authorised on the bank mandate', pool: true },
    access: { name: 'Access team', fallback: true, desc: 'Grants and reviews roles' },
  };
  P.scopes = { company: 'Vietnam company', retail: 'Retail', operations: 'Operations' };
  P.divisions = ['retail', 'operations'];
  P.schemes = {
    retail: { name: 'Retail monthly', divisions: ['retail', 'operations'], binding: 'follow' },
    operations: { name: 'Operations monthly', divisions: ['operations'], binding: 'follow' },
    contractor: { name: 'Contractor monthly', divisions: ['retail'], binding: 'custom' },
  };

  // Responsibilities: role|scope -> {person, backup, from}
  P.defaultResp = () => ({
    'hr_lead|company': { person: 'nithya', backup: 'monica', from: '01 Jan 2026' },
    'hr_lead|retail': { person: 'nithya', backup: 'monica', from: '01 Jan 2026' },
    'hr_lead|operations': null,
    'finance|company': { person: 'monica', backup: 'thao', from: '01 Jan 2026' },
    'payroll_mgr|company': { person: 'nithya', backup: null, from: '01 Jan 2026' },
    'director|company': { person: 'thao', backup: null, from: '01 Jan 2026' },
    'scheme_owner|company': { person: 'linh', backup: 'nithya', from: '01 Mar 2026' },
    'budget|retail': { person: 'duc', backup: null, from: '01 Jul 2026' },
    'budget|operations': { person: 'duc', backup: null, from: '01 Jul 2026' },
    'signatory|company': { person: 'nithya', pool: ['nithya', 'monica', 'thao'], from: '01 Jan 2026' },
    'access|company': { person: 'admin', backup: null, from: '01 Jan 2026' },
  });
  P.defaultDelegations = () => ([
    { id: 'd1', from: 'monica', to: 'thao', seat: 'Finance approver · Vietnam', start: '14 Sep 2026', end: '20 Sep 2026', reason: 'Annual leave', active: false },
  ]);

  // Catalogue: every process that can need approval
  P.areas = [
    { key: 'pay', name: 'Pay', icon: 'zap' },
    { key: 'money', name: 'Money out', icon: 'banknote' },
    { key: 'data', name: 'Pay data', icon: 'database' },
    { key: 'people', name: 'People', icon: 'users' },
    { key: 'time', name: 'Time', icon: 'clock' },
    { key: 'setup', name: 'Setup & rules', icon: 'sliders' },
    { key: 'platform', name: 'Platform', icon: 'server' },
  ];
  // status: live | draft | needs | soon ; fast = fast lane allowed
  P.catalogue = [
    { id: 'payrun', area: 'pay', name: 'Pay run', route: ['HR lead', 'Finance approver', 'Country director (₫600m+)'], applies: 'Vietnam company default', sub: 'Followed by 2 schemes · 1 custom', status: 'live', ver: 'v2', open: 'builder' },
    { id: 'reopen', area: 'pay', name: 'Reopen an approved run', route: ['HR lead + Finance approver', 'Country director'], applies: 'Vietnam company default', sub: 'Joint review, then sign-off', status: 'live', ver: 'v1' },
    { id: 'retro', area: 'pay', name: 'Retro adjustments & carry-overs', route: ['Payroll manager', 'Finance approver'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'fnf', area: 'pay', name: 'Full & final settlement', route: ['HR lead', 'Finance approver'], applies: 'Vietnam company default', sub: 'Draft · needs people', status: 'draft', ver: 'draft' },
    { id: 'month', area: 'pay', name: 'Close or reopen a payroll month', route: ['Payroll manager'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'bankfile', area: 'money', name: 'Bank file creation', route: ['Nithya + Monica + Thao (everyone)'], applies: 'Vietnam company default', sub: 'Joint · file hash and control total pinned', status: 'live', ver: 'v1', money: true },
    { id: 'release', area: 'money', name: 'Payment release', route: ['Any 2 bank signatories'], applies: 'Vietnam company default', sub: 'Per bank mandate · confirm mandate', status: 'needs', ver: 'draft', money: true },
    { id: 'journal', area: 'money', name: 'Payroll journal & funding', route: ['Finance approver', 'Finance controller'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1', money: true },
    { id: 'payslips', area: 'money', name: 'Payslip send-out', route: ['Notify HR lead'], applies: 'Vietnam company default', sub: 'Notify only · no approval', status: 'live', ver: 'v1' },
    { id: 'filing', area: 'money', name: 'Government filings', route: ['Payroll manager'], applies: 'Vietnam company default', sub: '', status: 'soon', ver: '' },
    { id: 'records', area: 'data', name: 'Records Desk bulk changes', route: ['HR lead', 'Finance approver (bank or salary fields)'], applies: 'Vietnam company default', sub: 'Stricter route when bank or salary fields change', status: 'live', ver: 'v1' },
    { id: 'runonly', area: 'data', name: '"This run only" pay data', route: ['Payroll manager'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'loads', area: 'data', name: 'Past pay data loads', route: ['Payroll manager'], applies: 'Vietnam company default', sub: '', status: 'draft', ver: 'draft' },
    { id: 'arrivals', area: 'data', name: 'Arrivals from the connected HR system', route: ['HR lead'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'paychange', area: 'people', name: 'Pay change', route: ['Their manager', 'HR lead', 'Finance approver (above guidance)'], applies: 'Vietnam company default', sub: 'Finance only when the raise is above guidance', status: 'live', ver: 'v3' },
    { id: 'contract', area: 'people', name: 'Salary & contract changes', route: ['HR lead', 'HR lead + Finance approver (everyone)'], applies: 'Vietnam company default', sub: 'Approved letter required', status: 'live', ver: 'v1' },
    { id: 'master', area: 'people', name: 'Employee master changes', route: ['HR lead'], applies: 'Vietnam company default', sub: 'Phone or address: applied immediately, logged', status: 'live', ver: 'v2', fast: true },
    { id: 'trip', area: 'people', name: 'Business trips', route: ['Their manager', 'Finance approver'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'assets', area: 'people', name: 'Asset requests', route: ['Their manager', 'Equipment team'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'awards', area: 'people', name: 'Awards & recognition', route: ['Their manager', 'HR lead + Finance approver (₫20m+)'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'resign', area: 'people', name: 'Resignations & contract extensions', route: ['Their manager', 'HR lead'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'verdict', area: 'people', name: 'Probation & growth-plan verdicts', route: ['Their manager', 'HR lead (fail or terminate)'], applies: 'Vietnam company default', sub: 'Second person only for fail or terminate', status: 'live', ver: 'v1' },
    { id: 'newhire', area: 'people', name: 'New hire & first contract', route: ['HR lead'], applies: 'Vietnam company default', sub: '', status: 'draft', ver: 'draft' },
    { id: 'timesheet', area: 'time', name: 'Weekly timesheet', route: ['Their manager', 'HR lead'], applies: 'Vietnam / Retail', sub: '1 employee has no manager', status: 'needs', ver: 'v1', open: 'builder' },
    { id: 'overtime', area: 'time', name: 'Overtime', route: ['Their manager', 'HR lead (over 200 h/yr)'], applies: 'Vietnam company default', sub: 'Yearly cap as a condition', status: 'live', ver: 'v1' },
    { id: 'leave', area: 'time', name: 'Leave', route: ['Their manager', 'HR lead'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'correction', area: 'time', name: 'Attendance corrections', route: ['Their manager'], applies: 'Vietnam company default', sub: 'Under 15 minutes: applied immediately, logged', status: 'live', ver: 'v2', fast: true },
    { id: 'unlock', area: 'time', name: 'Unlock a locked day', route: ['Payroll manager'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'scheme', area: 'setup', name: 'Scheme change', route: ['Scheme owner', 'Payroll manager', 'Country director'], applies: 'Vietnam company default', sub: 'Exact proposal · activate, release, rollback, merge', status: 'live', ver: 'v1', open: 'scheme' },
    { id: 'statutory', area: 'setup', name: 'Statutory rates & tax tables', route: ['Payroll manager', 'Country director'], applies: 'Vietnam company default', sub: 'Four-eyes', status: 'live', ver: 'v1' },
    { id: 'bands', area: 'setup', name: 'Pay bands & guidance', route: ['Head of pay'], applies: 'Vietnam company default', sub: '', status: 'draft', ver: 'draft' },
    { id: 'fx', area: 'setup', name: 'Exchange rates & budgets', route: ['Finance approver', 'Finance controller'], applies: 'Vietnam company default', sub: 'Includes uploads', status: 'live', ver: 'v1' },
    { id: 'schememap', area: 'setup', name: 'Who is paid by which scheme', route: ['Payroll manager'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'mappings', area: 'setup', name: 'Connected-system mappings & sync schedule', route: ['Payroll manager'], applies: 'Vietnam company default', sub: '', status: 'soon', ver: '' },
    { id: 'roles', area: 'platform', name: 'Role grants & access hand-overs', route: ['Access team', 'Tenant administrator'], applies: 'Vietnam company default', sub: 'Highest risk', status: 'live', ver: 'v1' },
    { id: 'support', area: 'platform', name: 'Support access (break-glass)', route: ['Tenant administrator'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
    { id: 'tenant', area: 'platform', name: 'Suspend, delete or change plan', route: ['Platform owner'], applies: 'All tenants', sub: 'Managed by Payobook', status: 'soon', ver: '' },
    { id: 'demo', area: 'platform', name: 'Demo data on a real tenant', route: ['Tenant administrator'], applies: 'Vietnam company default', sub: '', status: 'live', ver: 'v1' },
  ];
  P.statusMeta = {
    live: { label: 'Published', cls: 'ok' },
    draft: { label: 'Draft', cls: 'muted' },
    needs: { label: 'Needs people', cls: 'warn' },
    soon: { label: 'Not connected yet', cls: 'blue' },
  };

  P.presets = [
    { key: 'officer', t: 'Officer → HR → Finance', s: 'The classic payroll chain. One person at each step.', r: ['Payroll officer', 'HR lead', 'Finance approver'] },
    { key: 'mgr_hr', t: 'Manager, then HR', s: 'For requests about one person: their manager first, then HR.', r: ['Their manager', 'HR lead'] },
    { key: 'joint', t: 'Joint sign-off', s: 'Two or three named people must all approve. For bank and money out.', r: ['Nithya + Monica + Thao'] },
    { key: 'tiers', t: 'Route by amount', s: 'Small amounts stay light; big amounts bring in more people.', r: ['HR lead', '+ Finance (₫300m+)', '+ Director (₫600m+)'] },
    { key: 'four', t: 'Four-eyes for setup changes', s: 'The person who made a change never approves it.', r: ['Independent reviewer', 'Owner'] },
    { key: 'blank', t: 'Start blank', s: 'Build the route step by step.', r: [] },
  ];

  P.conditions = {
    overtime: 'overtime is included',
    variance: 'the net total moved more than 5% from last month',
    offcycle: 'the run is off-cycle',
    headcount: 'more than 50 employees are affected',
    bank: 'the change touches bank details',
  };

  P.defaultBuilder = () => ({
    step: 2,
    name: 'Pay run approval',
    process: 'payrun',
    scope: { division: '', scheme: '', runKind: 'any' },
    tiers: true,
    steps: [
      { id: 's1', kind: 'review', title: 'HR lead review', who: { mode: 'role', role: 'hr_lead', scope: 'division' }, min: 0, cond: '' },
      { id: 's2', kind: 'approve', title: 'Finance approval', who: { mode: 'role', role: 'finance', scope: 'company' }, min: 300000000, cond: '' },
      { id: 's3', kind: 'approve', title: 'Country director sign-off', who: { mode: 'people', people: ['thao'], all: true }, min: 600000000, cond: '' },
      { id: 'n1', kind: 'notify', title: 'Tell the payroll preparer', who: { mode: 'preparer' }, min: 0, cond: '' },
    ],
    seq: 4,
    published: { ver: 2, steps: [{ title: 'HR lead review', min: 0 }, { title: 'Finance approval', min: 0 }] },
    safeguards: {
      independent: true,
      selfException: true,
      selfScope: 'Retail · off-cycle runs · HR lead review',
      selfEligible: 'Retail payroll lead',
      repeated: 'different',
      evidence: [{ n: 'Payroll control report', when: 'Before final approval', on: true }, { n: 'Variance explanation', when: 'When the net total moved more than 5%', on: true }, { n: 'Bank control total', when: 'Before Finance approval', on: false }],
      due: '1wd', calendar: 'Vietnam company working calendar',
      remind: 1, escalate: 2, reassign: false,
    },
    example: { scheme: 'retail', division: 'retail', runKind: 'end', amount: 620000000, preparedBy: 'linh', variance: 3.2, overtime: true },
    coverage: null,
    addMenu: false,
    picker: null,
    fix: null,
    publishAt: '2026-10-01T09:00',
    publishedNow: false,
    saved: 'Saved just now',
  });

  P.defaultRequests = () => ([
    { id: 'r1', process: 'payrun', icon: 'zap', title: 'Pay run · September 2026', sub: 'Retail monthly · Retail · end of cycle', amount: 620000000, cur: 'VND', count: '412 payslips', submittedBy: 'linh', submittedAt: 'Sat 12 Sep, 10:14', due: 'Mon 14 Sep, 17:00', state: 'pending', cur_step: 0, wf: 'Pay run approval · v2',
      facts: [['Net total', '₫620,000,000'], ['Payslips', '412'], ['Change vs August', '+3.2%'], ['Overtime included', 'Yes · 1,240 h']],
      evidence: [{ n: 'Payroll control report', s: 'Generated 12 Sep, 10:12 · locked', ok: true }, { n: 'Variance explanation', s: 'Not required (under 5%)', ok: true, na: true }],
      steps: [
        { title: 'HR lead review', who: ['nithya'], mode: 'one', status: 'current' },
        { title: 'Finance approval', who: ['monica'], mode: 'one', status: 'next', cover: { for: 'monica', by: 'thao' } },
        { title: 'Country director sign-off', who: ['thao'], mode: 'one', status: 'next', why: 'Net total is ₫600m or more' },
      ] },
    { id: 'r2', process: 'bankfile', icon: 'banknote', title: 'Bank file · September 2026', sub: 'Retail · 394 transfers · control total pinned', amount: 610450000, cur: 'VND', count: '394 transfers', submittedBy: 'linh', submittedAt: 'Sat 12 Sep, 11:02', due: 'Mon 28 Sep, 12:00', state: 'pending', cur_step: 0, wf: 'Bank file creation · v1',
      facts: [['Control total', '₫610,450,000'], ['Transfers', '394'], ['File hash', 'a91f…c47e'], ['Bank account', 'VCB ····2210']],
      evidence: [{ n: 'Bank control total', s: 'Matches approved run', ok: true }, { n: 'Approved pay run', s: 'Pay run · September 2026 (pending)', ok: false, warn: 'Pay run not yet approved' }],
      steps: [
        { title: 'Joint authorisation', who: ['nithya', 'monica', 'thao'], mode: 'all', status: 'current', done: ['thao'] },
      ] },
    { id: 'r3', process: 'paychange', icon: 'trendingUp', title: 'Pay change · An Le', sub: 'Operations · ₫18,000,000 → ₫21,000,000 (+16.7%)', amount: 3000000, cur: 'VND', count: '+16.7%', submittedBy: 'duc', submittedAt: 'Fri 11 Sep, 16:40', due: 'Tue 15 Sep, 17:00', state: 'pending', cur_step: 1, wf: 'Pay change · v3',
      facts: [['Current wage', '₫18,000,000'], ['New wage', '₫21,000,000'], ['Raise', '+16.7%'], ['Guidance', '10% · above guidance']],
      evidence: [{ n: 'Manager justification', s: 'Attached by Duc Pham', ok: true }],
      steps: [
        { title: 'Manager review', who: ['duc'], mode: 'one', status: 'done', by: 'duc', at: 'Fri 11 Sep, 16:40' },
        { title: 'HR lead approval', who: ['nithya'], mode: 'one', status: 'current' },
        { title: 'Finance approval', who: ['monica'], mode: 'one', status: 'next', why: 'Raise is above the 10% guidance', cover: { for: 'monica', by: 'thao' } },
      ] },
    { id: 'r4', process: 'timesheet', icon: 'clock', title: 'Weekly timesheet · Minh Tran', sub: 'Retail · week 37 · 44.5 h incl. 4.5 h overtime', amount: null, count: '44.5 h', submittedBy: 'minh', submittedAt: 'Fri 11 Sep, 18:05', due: 'Tue 15 Sep, 17:00', state: 'blocked', cur_step: 0, wf: 'Weekly timesheet · v1',
      facts: [['Hours', '44.5 h'], ['Overtime', '4.5 h'], ['Source', 'Attendance grid'], ['Cut-off', 'Day 15']],
      evidence: [],
      steps: [
        { title: 'Manager review', who: [], mode: 'one', status: 'blocked', issue: 'Minh Tran has no manager on the employee record.' },
        { title: 'HR lead approval', who: ['nithya'], mode: 'one', status: 'next' },
      ] },
    { id: 'r5', process: 'scheme', icon: 'gitBranch', title: 'Scheme change · Retail monthly', sub: 'Proposal 14 · "PIT bands 2026" · 6 rules changed', amount: null, count: '6 rules', submittedBy: 'linh', submittedAt: 'Thu 10 Sep, 09:30', due: 'Mon 14 Sep, 17:00', state: 'pending', cur_step: 1, wf: 'Scheme change · v1',
      facts: [['Rules changed', '6'], ['Test runs', '3 passed'], ['Affects', '412 payslips / month'], ['Candidate', 'Proposal 14 (sealed)']],
      evidence: [{ n: 'Shadow run comparison', s: '0 differences outside PIT', ok: true }, { n: 'Client review', s: 'Signed on the review link · acknowledgement only', ok: true }],
      steps: [
        { title: 'Scheme owner check', who: ['linh'], mode: 'one', status: 'done', by: 'linh', at: 'Thu 10 Sep, 09:32', note: 'Self-check by owner: allowed for this step' },
        { title: 'Payroll manager review', who: ['nithya'], mode: 'one', status: 'current' },
        { title: 'Country director sign-off', who: ['thao'], mode: 'one', status: 'next' },
      ] },
    { id: 'r6', process: 'payrun', icon: 'zap', title: 'Off-cycle pay run · Retail corrections', sub: 'Retail monthly · Retail · off-cycle', amount: 48200000, cur: 'VND', count: '18 payslips', submittedBy: 'nithya', submittedAt: 'Sat 12 Sep, 09:50', due: 'Mon 14 Sep, 17:00', state: 'pending', cur_step: 0, wf: 'Pay run approval · v2',
      facts: [['Net total', '₫48,200,000'], ['Payslips', '18'], ['Kind', 'Off-cycle'], ['Prepared by', 'Nithya']],
      evidence: [{ n: 'Payroll control report', s: 'Generated 12 Sep, 09:48 · locked', ok: true }],
      steps: [
        { title: 'HR lead review', who: ['nithya'], mode: 'one', status: 'current', conflict: 'You prepared this run.', exception: 'Retail off-cycle cover · v2' },
      ] },
    { id: 'r7', process: 'roles', icon: 'key', title: 'Role grant · "Payroll approver — final" to Duc Pham', sub: 'Requested by the Access team', amount: null, count: '1 role', submittedBy: 'admin', submittedAt: 'Wed 9 Sep, 14:12', due: 'Fri 11 Sep, 17:00', state: 'returned', cur_step: 0, wf: 'Role grants · v1', returnNote: 'Duc already prepares Operations runs. Choose someone who does not.',
      facts: [['Role', 'Payroll approver — final'], ['Person', 'Duc Pham'], ['Reason', 'Cover for Thao in October']],
      evidence: [],
      steps: [
        { title: 'Tenant administrator', who: ['thao'], mode: 'one', status: 'returned', by: 'thao', at: 'Thu 10 Sep, 08:15' },
      ] },
    { id: 'r8', process: 'correction', icon: 'clock', title: 'Attendance correction · An Le', sub: 'Operations · Tue 8 Sep · clock-out +10 min', amount: null, count: '10 min', submittedBy: 'an', submittedAt: 'Tue 8 Sep, 18:20', due: '', state: 'applied', cur_step: 0, wf: 'Attendance corrections · v2',
      facts: [['Change', 'Clock-out 17:50 → 18:00'], ['Difference', '10 min'], ['Lane', 'Applied immediately · logged']],
      evidence: [],
      steps: [{ title: 'Applied immediately', who: [], mode: 'fast', status: 'done', by: 'an', at: 'Tue 8 Sep, 18:20', note: 'Under 15 minutes · no approval needed · logged in the audit console' }] },
  ]);

  P.history = [
    { when: 'Sat 12 Sep, 11:02', who: 'linh', t: 'Bank file · September 2026 submitted', s: 'Joint authorisation opened for Nithya, Monica and Thao' },
    { when: 'Sat 12 Sep, 10:40', who: 'thao', t: 'Approved 1 of 3 seats on Bank file · September 2026', s: 'Waiting for Nithya and Monica' },
    { when: 'Fri 11 Sep, 16:40', who: 'duc', t: 'Approved Manager review on Pay change · An Le', s: 'Next: HR lead approval (Nithya)' },
    { when: 'Thu 10 Sep, 08:15', who: 'thao', t: 'Sent back Role grant · Duc Pham', s: '"Duc already prepares Operations runs. Choose someone who does not."' },
    { when: 'Wed 9 Sep, 17:30', who: 'monica', t: 'Hand-over set: Thao covers Finance approver', s: '10 to 20 Sep 2026 · Annual leave' },
    { when: 'Tue 8 Sep, 18:20', who: 'an', t: 'Attendance correction applied immediately', s: 'Under 15 minutes · logged, no approval needed' },
    { when: 'Mon 7 Sep, 09:05', who: 'admin', t: 'Published Pay change · v3', s: 'Added Finance approval when the raise is above guidance · 2 schemes follow' },
    { when: 'Mon 31 Aug, 15:00', who: 'admin', t: 'Published Pay run approval · v2', s: 'HR lead review, then Finance approval · Vietnam company default' },
  ];

  P.guide = [
    { screen: 'matrix', t: 'Approval Matrix', s: 'Every process that can need a sign-off, grouped the way you see the product. Click a row to open its workflow. Try the filters and the "3 processes need people" bar.' },
    { screen: 'builder', t: 'Workflow builder · Pay run approval', s: 'Read the sentence, then edit the route: click a purple "who" chip to change who approves, add a step, switch "Route by amount" off and on, change the example on the right (try Operations, or "Prepared by: Nithya"). Try "Add a step → No approval needed" to see a one-person company setup, and how Review & publish asks you to confirm rather than stopping you. Then Continue → Safeguards → Review & publish.' },
    { screen: 'scheme', t: 'Where it applies · inside New configuration', s: 'The Connect step (3 of 6) now shows real approvals for the scheme. Press Change to pick Inherit / Shared / Custom and add a division exception.' },
    { screen: 'inbox', t: 'Approvals inbox', s: 'One inbox for every process. Switch "View as" to Nithya, Monica or Linh. Open a card, approve, send back, or use "Approve with exception" on the off-cycle run.' },
    { screen: 'people', t: 'People & backups', s: 'Who fills each role, where. The red cell is the gap that blocks Operations: assign a person, then re-run the builder\'s coverage check. Switch Monica\'s hand-over on to see "covering for" appear in the example and on inbox cards, and watch the repeated-person rule react.' },
    { screen: 'history', t: 'History', s: 'Every publish, decision, hand-over and exception, in plain words.' },
    { screen: 'mobile', t: 'Phone view', s: 'The same inbox card and decision on a 390 px screen.' },
  ];

  P.defaultState = () => ({
    screen: 'matrix', matrixTab: 'matrix',
    filter: { q: '', area: 'all', status: 'all' },
    presetsOpen: false,
    resp: P.defaultResp(),
    delegations: P.defaultDelegations(),
    builder: P.defaultBuilder(),
    scheme: { choice: 'inherit', changing: false, exceptions: [], adding: false, saved: false },
    inbox: { viewAs: 'nithya', tab: 'mine', open: null, modal: null, requests: P.defaultRequests() },
    people: { assignDrawer: null, handover: false },
    guide: false,
    toast: '',
  });
  P.state = P.defaultState();
})(window.POC);
