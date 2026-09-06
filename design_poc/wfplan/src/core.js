/* ===================================================================
   WFPLAN proof-of-concept core — shared by option A/B/C.
   Money is held internally in ₫ millions (M). 1,000 M = ₫1 B.
   Everything here is deliberately plain: a CEO can read the outputs,
   an engineer can read the model. VN statutory numbers are the real
   2026 ones, simplified to averages per role.
   =================================================================== */
window.WF = (() => {
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const MONTHS_LONG = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  // ---- The company (mirrors the Payobook Vietnam demo: 4,502 people) ----
  const DIVS = [
    {key:'mfg', name:'Manufacturing', color:'#2a78d6', revenue:true, roles:[
      {key:'op',  name:'Operators',          n:760, pay:10.8, ot:24, night:0.35},
      {key:'tl',  name:'Team leads',         n:140, pay:15.5, ot:16, night:0.35},
      {key:'qc',  name:'Quality inspectors', n:60,  pay:14.2, ot:12, night:0.20},
      {key:'sup', name:'Supervisors',        n:40,  pay:22.0, ot:0,  night:0.20}]},
    {key:'ret', name:'Retail', color:'#eb6834', revenue:true, roles:[
      {key:'ss',  name:'Store staff',        n:640, pay:12.6, ot:14, night:0},
      {key:'ca',  name:'Cashiers',           n:120, pay:9.4,  ot:10, night:0},
      {key:'sm',  name:'Store managers',     n:82,  pay:24.0, ot:0,  night:0},
      {key:'me',  name:'Merchandisers',      n:60,  pay:16.0, ot:6,  night:0}]},
    {key:'con', name:'Construction', color:'#1baf7a', revenue:true, roles:[
      {key:'sw',  name:'Site workers',       n:560, pay:12.4, ot:30, night:0.15},
      {key:'fm',  name:'Foremen',            n:120, pay:18.0, ot:20, night:0.15},
      {key:'en',  name:'Site engineers',     n:80,  pay:22.0, ot:10, night:0},
      {key:'sa',  name:'Safety officers',    n:40,  pay:16.0, ot:8,  night:0}]},
    {key:'log', name:'Logistics', color:'#eda100', revenue:true, roles:[
      {key:'dr',  name:'Drivers',            n:400, pay:13.5, ot:28, night:0.40},
      {key:'wh',  name:'Warehouse staff',    n:220, pay:10.5, ot:20, night:0.30},
      {key:'di',  name:'Dispatchers',        n:50,  pay:15.0, ot:12, night:0.30},
      {key:'fs',  name:'Fleet supervisors',  n:30,  pay:21.0, ot:0,  night:0}]},
    {key:'it',  name:'IT', color:'#e87ba4', revenue:false, roles:[
      {key:'eng', name:'Engineers',          n:380, pay:28.0, ot:4,  night:0},
      {key:'sen', name:'Senior engineers',   n:120, pay:42.0, ot:2,  night:0},
      {key:'pm',  name:'Project managers',   n:60,  pay:38.0, ot:0,  night:0},
      {key:'sp',  name:'Support staff',      n:40,  pay:16.0, ot:8,  night:0}]},
    {key:'cor', name:'Corporate', color:'#008300', revenue:false, roles:[
      {key:'ad',  name:'Admin',              n:180, pay:14.0, ot:2,  night:0},
      {key:'fh',  name:'Finance & HR',       n:160, pay:26.0, ot:2,  night:0},
      {key:'sa',  name:'Sales',              n:100, pay:30.0, ot:0,  night:0},
      {key:'mg',  name:'Managers',           n:60,  pay:48.0, ot:0,  night:0}]},
  ];
  const DIV = Object.fromEntries(DIVS.map(d => [d.key, d]));

  // ---- Vietnam statutory (2026), simplified ----
  const K = {
    allowance: 0.12,      // meal / transport / phone, share of base
    insCap: 46.8,         // ₫46.8M cap for SI/HI (20 × base salary)
    erRate: 0.235,        // employer: SI 17.5 + HI 3 + UI 1 + union 2
    eeRate: 0.105,        // employee: SI 8 + HI 1.5 + UI 1
    otMult: 1.5,          // weekday overtime multiplier
    nightPrem: 0.30,      // night-shift premium on the base hour
    personalDed: 11,      // ₫11M personal deduction / month
    depDed: 4.4 * 0.9,    // ₫4.4M per dependent × 0.9 avg dependents
  };
  const PIT = [[5,0.05],[10,0.10],[18,0.15],[32,0.20],[52,0.25],[80,0.30],[Infinity,0.35]];
  function pitOn(taxable) {
    if (taxable <= 0) return 0;
    let tax = 0, prev = 0;
    for (const [cap, rate] of PIT) {
      const slice = Math.min(taxable, cap) - prev;
      if (slice <= 0) break;
      tax += slice * rate; prev = cap;
    }
    return tax;
  }

  // ---- The knobs (state) ----
  function defaultState() {
    return {
      divs: Object.fromEntries(DIVS.map(d => [d.key, {
        delta: 0,                 // people added (+) or removed (−)
        month: 3,                 // month (1-12) the change lands
        raise: null,              // % override, null = follow company raise
        roles: Object.fromEntries(d.roles.map(r => [r.key, 0])),  // per-role delta
      }])),
      raise: 0,          // company-wide raise, %
      raiseMonth: 4,     // month raise starts
      otFactor: 1,       // overtime vs today (1 = same)
      nightFactor: 1,    // night work vs today
      workDays: 24,      // paid working days / month
      bonusMonths: 1,    // Tet 13th-month
      attrition: 12,     // % of people who leave per year
      backfill: true,    // replace leavers?
      recruitCost: 1,    // months of pay per hire (agency, onboarding)
      severance: 1.5,    // months of pay per person let go
      revenue: 2200000,  // ₫M / year  (₫2,200 B)
      otherCosts: 260000,// ₫M / year non-people costs
      revenueFollows: false, // does revenue grow with revenue-earning staff?
    };
  }

  // ---- The engine ----
  function compute(s) {
    const months = [];
    const byDiv = {};
    let revHeadsBase = 0, revHeads = new Array(12).fill(0);
    const totals = { hires:0, cuts:0, leavers:0 };
    for (const d of DIVS) {
      byDiv[d.key] = { name:d.name, color:d.color, heads:new Array(12).fill(0), cost:new Array(12).fill(0), baseCost:0, headsToday:0 };
    }
    for (let m = 0; m < 12; m++) {
      const row = { m, heads:0, base:0, allow:0, ot:0, night:0, erc:0, bonus:0, oneOff:0, eeIns:0, pit:0, takeHome:0, total:0 };
      for (const d of DIVS) {
        const ds = s.divs[d.key];
        const raisePct = (ds.raise == null ? s.raise : ds.raise);
        for (const r of d.roles) {
          // two kinds of change: a division-wide delta (spread across roles) landing at ds.month,
          // and a per-role delta (number, or {n, month}) landing at its own month
          // a role delta may be a number (lands at ds.month), {n, month}, or an array of {n, month} (option D)
          const rd = ds.roles[r.key];
          const rdl = Array.isArray(rd) ? rd : [typeof rd === 'object' && rd ? rd : { n: rd || 0, month: ds.month }];
          const divShare = ds.delta * (r.n / d.roles.reduce((a, x) => a + x.n, 0));
          let n = r.n + ((m + 1) >= ds.month ? divShare : 0) + rdl.reduce((a, x) => a + ((m + 1) >= x.month ? x.n : 0), 0);
          const aRate = s.attrition / 100 / 12;
          const leaversThisMonth = r.n * aRate;
          if (!s.backfill) n -= r.n * (1 - Math.pow(1 - aRate, m + 1));
          n = Math.max(0, n);
          const pay = r.pay * (1 + ((m + 1) >= s.raiseMonth ? raisePct / 100 : 0));
          const base = n * pay;
          const allow = base * K.allowance;
          const hourly = pay / (s.workDays * 8);
          const ot = n * hourly * K.otMult * r.ot * s.otFactor;
          const night = base * K.nightPrem * r.night * s.nightFactor;
          const erc = n * Math.min(pay, K.insCap) * K.erRate;
          const bonus = m === 0 ? base * s.bonusMonths : 0;
          let oneOff = 0;
          const land = (delta, month) => {
            if ((m + 1) !== month || !delta) return;
            if (delta > 0) { oneOff += delta * pay * s.recruitCost; totals.hires += delta; }
            else { oneOff += -delta * pay * s.severance; totals.cuts += -delta; }
          };
          land(divShare, ds.month); rdl.forEach(x => land(x.n, x.month));
          if (s.backfill) { oneOff += leaversThisMonth * pay * s.recruitCost; }
          totals.leavers += leaversThisMonth;
          const eeInsPP = Math.min(pay, K.insCap) * K.eeRate;
          const grossPP = pay + allow / Math.max(n,1e-9) + (n ? ot / n : 0) + (n ? night / n : 0);
          const pitPP = pitOn(grossPP - eeInsPP - K.personalDed - K.depDed);
          const eeIns = n * eeInsPP, pit = n * pitPP;
          const gross = base + allow + ot + night;
          const total = gross + erc + bonus + oneOff;
          row.heads += n; row.base += base; row.allow += allow; row.ot += ot; row.night += night;
          row.erc += erc; row.bonus += bonus; row.oneOff += oneOff; row.eeIns += eeIns; row.pit += pit;
          row.takeHome += gross - eeIns - pit; row.total += total;
          byDiv[d.key].heads[m] += n; byDiv[d.key].cost[m] += total;
          if (m === 0) byDiv[d.key].headsToday += r.n;
          if (d.revenue) { revHeads[m] += n; if (m === 0) revHeadsBase += r.n; }
        }
      }
      row.gross = row.base + row.allow + row.ot + row.night;
      months.push(row);
    }
    // revenue + profit
    const seasonal = [0.86,0.78,0.95,1.0,1.02,1.04,1.02,1.03,1.05,1.08,1.1,1.07]; // mild VN seasonality, sums to 12
    for (let m = 0; m < 12; m++) {
      const row = months[m];
      let rev = s.revenue / 12 * seasonal[m];
      if (s.revenueFollows) rev *= revHeads[m] / revHeadsBase;
      row.revenue = rev;
      row.other = s.otherCosts / 12;
      row.profit = rev - row.total - row.other;
      row.margin = rev ? row.profit / rev : 0;
    }
    const sum = k => months.reduce((a, r) => a + r[k], 0);
    const year = {
      cost: sum('total'), gross: sum('gross'), base: sum('base'), allow: sum('allow'), ot: sum('ot'), night: sum('night'),
      erc: sum('erc'), bonus: sum('bonus'), oneOff: sum('oneOff'), eeIns: sum('eeIns'), pit: sum('pit'), takeHome: sum('takeHome'),
      revenue: sum('revenue'), other: sum('other'), profit: sum('profit'),
      headsEnd: months[11].heads, headsAvg: sum('heads') / 12,
      peakMonth: months.reduce((b, r) => r.total > months[b].total ? r.m : b, 0),
    };
    year.margin = year.revenue ? year.profit / year.revenue : 0;
    year.costPerHead = year.cost / 12 / year.headsAvg;
    year.peopleShare = year.revenue ? year.cost / year.revenue : 0;
    for (const d of DIVS) byDiv[d.key].year = byDiv[d.key].cost.reduce((a, b) => a + b, 0);
    return { months, year, byDiv, totals };
  }

  let _base = null;
  const baseline = () => _base || (_base = compute(defaultState()));

  // ---- Goal seek: how far can one knob go before margin drops below target? ----
  function maxHeadsForMargin(s, divKey, targetMargin) {
    let lo = 0, hi = 4000;
    const test = n => { const t = clone(s); t.divs[divKey].delta = n; return compute(t).year.margin >= targetMargin; };
    if (!test(0)) return 0;
    while (lo < hi) { const mid = Math.ceil((lo + hi) / 2); if (test(mid)) lo = mid; else hi = mid - 1; }
    return lo;
  }
  function maxRaiseForMargin(s, targetMargin) {
    let lo = 0, hi = 60;
    const test = p => { const t = clone(s); t.raise = p; return compute(t).year.margin >= targetMargin; };
    if (!test(0)) return 0;
    while (hi - lo > 0.1) { const mid = (lo + hi) / 2; if (test(mid)) lo = mid; else hi = mid; }
    return Math.floor(lo * 2) / 2;
  }
  const clone = o => JSON.parse(JSON.stringify(o));
  const roleSum = ds => Object.values(ds.roles).reduce((a, v) => a + (Array.isArray(v) ? v.reduce((b, x) => b + x.n, 0) : (typeof v === 'object' && v ? v.n : v)), 0);

  // ---- Formatting (₫, plain) ----
  const fmt = {
    money(v, opts = {}) {
      const sign = v < 0 ? '−' : (opts.plus && v > 0 ? '+' : '');
      const a = Math.abs(v);
      if (a >= 1000) return `${sign}₫${(a / 1000).toLocaleString('en', { maximumFractionDigits: a >= 100000 ? 0 : 1 })} B`;
      if (a >= 1) return `${sign}₫${a.toLocaleString('en', { maximumFractionDigits: a >= 100 ? 0 : 1 })} M`;
      return `${sign}₫${(a * 1000).toLocaleString('en', { maximumFractionDigits: 0 })} K`;
    },
    int(v, opts = {}) { const sign = v < 0 ? '−' : (opts.plus && v > 0 ? '+' : ''); return sign + Math.round(Math.abs(v)).toLocaleString('en'); },
    pct(v, opts = {}) { const p = v * 100; const sign = p < 0 ? '−' : (opts.plus && p > 0 ? '+' : ''); return `${sign}${Math.abs(p).toFixed(opts.d ?? 1)}%`; },
    pts(v) { const p = v * 100; return `${p < 0 ? '−' : '+'}${Math.abs(p).toFixed(1)} pt`; },
    month: i => MONTHS_LONG[i - 1],
  };

  // ---- Number animation ----
  function animateNumber(el, to, format, ms = 420) {
    const from = el._v ?? to;
    el._v = to;
    if (from === to) { el.textContent = format(to); return; }
    const t0 = performance.now();
    const tick = t => {
      const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
      el.textContent = format(from + (to - from) * e);
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  // ---- Lucide icons (stroke only, no emoji) ----
  const ICONS = {
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    'user-plus': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
    'user-minus': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="22" x2="16" y1="11" y2="11"/>',
    wallet: '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    'trending-up': '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    'trending-down': '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    minus: '<path d="M5 12h14"/>',
    sparkles: '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>',
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11"/>',
    redo: '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5A5.5 5.5 0 0 0 4 14.5A5.5 5.5 0 0 0 9.5 20H13"/>',
    save: '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
    columns: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M12 3v18"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    'eye-off': '<path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/><path d="m2 2 20 20"/>',
    zap: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    layers: '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"/><path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"/><path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"/>',
    'arrow-right': '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    percent: '<line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    calendar: '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13"/><path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7"/><path d="M7.5 8a2.5 2.5 0 0 1 0-5A4.8 8 0 0 1 12 8a4.8 8 0 0 1 4.5-5 2.5 2.5 0 0 1 0 5"/>',
    reset: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    bulb: '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    building: '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    landmark: '<line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/>',
    chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    scale: '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    grip: '<circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    play: '<polygon points="6 3 20 12 6 21 6 3"/>',
    home: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    'chevron-right': '<path d="m9 18 6-6-6-6"/>',
    flag: '<path d="M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.333 2q2 0 3.067-.8A1 1 0 0 1 20 4v10a1 1 0 0 1-.4.8A6 6 0 0 1 16 16c-3 0-5-2-8-2a6 6 0 0 0-4 1.528"/>',
    hand: '<path d="M11 14h2a2 2 0 1 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 16"/><path d="m7 20 1.6-1.4c.3-.4.8-.6 1.4-.6h4c1.1 0 2.1-.4 2.8-1.2l4.6-4.4a2 2 0 0 0-2.75-2.91l-4.2 3.9"/><path d="m2 15 6 6"/><path d="M19.5 8.5c.7-.7 1.5-1.6 1.5-2.7A2.73 2.73 0 0 0 16 4a2.78 2.78 0 0 0-5 1.8c0 1.2.8 2 1.5 2.8L16 12Z"/>',
  };
  const icon = (name, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`;

  // ---- The plain-language summary sentence ----
  function describe(s, r, b) {
    const parts = [];
    let hires = 0, cuts = 0;
    const hireBits = [], cutBits = [];
    for (const d of DIVS) {
      const ds = s.divs[d.key];
      const tot = ds.delta + roleSum(ds);
      if (tot > 0) { hires += tot; hireBits.push(`${fmt.int(tot)} in ${d.name}`); }
      if (tot < 0) { cuts += -tot; cutBits.push(`${fmt.int(-tot)} in ${d.name}`); }
    }
    if (hires) parts.push(`hiring ${hireBits.join(', ')}`);
    if (cuts) parts.push(`letting go ${cutBits.join(', ')}`);
    if (s.raise) parts.push(`a ${s.raise}% raise from ${fmt.month(s.raiseMonth)}`);
    if (s.otFactor !== 1) parts.push(`${s.otFactor > 1 ? 'more' : 'less'} overtime (${fmt.pct(s.otFactor - 1, { plus: true, d: 0 })})`);
    if (s.nightFactor !== 1) parts.push(`${s.nightFactor > 1 ? 'more' : 'fewer'} night shifts (${fmt.pct(s.nightFactor - 1, { plus: true, d: 0 })})`);
    if (s.bonusMonths !== 1) parts.push(`${s.bonusMonths === 0 ? 'no Tet bonus' : s.bonusMonths + ' months of Tet bonus'}`);
    if (!s.backfill) parts.push('not replacing leavers');
    if (s.attrition !== 12) parts.push(`${s.attrition}% of people leaving a year`);
    const dCost = r.year.cost - b.year.cost, dProfit = r.year.profit - b.year.profit;
    if (!parts.length) return { lead: 'This is your company today.', tail: `${fmt.int(b.year.headsEnd)} people cost ${fmt.money(b.year.cost)} a year and you keep ${fmt.money(b.year.profit)} profit — a ${fmt.pct(b.year.margin)} margin.` };
    const lead = 'With ' + (parts.length > 1 ? parts.slice(0, -1).join(', ') + ' and ' + parts.slice(-1) : parts[0]) + ',';
    const tail = `your yearly people cost ${dCost >= 0 ? 'rises' : 'falls'} by ${fmt.money(Math.abs(dCost))} to ${fmt.money(r.year.cost)}, and profit ${dProfit >= 0 ? 'goes up' : 'goes down'} ${fmt.money(Math.abs(dProfit))} — margin ${fmt.pct(b.year.margin)} → ${fmt.pct(r.year.margin)}.`;
    return { lead, tail };
  }

  // ---- Watch-outs (what could bite) ----
  function warnings(s, r, b) {
    const w = [];
    if (r.year.margin < 0.10) w.push({ level: 'crit', text: `Margin falls to ${fmt.pct(r.year.margin)} — below the 10% floor. Cut ${fmt.money(0.10 * r.year.revenue - r.year.profit)} of cost or add revenue.` });
    else if (r.year.margin < 0.15) w.push({ level: 'warn', text: `Margin at ${fmt.pct(r.year.margin)} is thin. Anything under 15% leaves little room for a slow quarter.` });
    const worst = r.months.reduce((a, m) => m.profit < a.profit ? m : a, r.months[0]);
    if (worst.profit < 0) {
      const hiresThen = r.months[worst.m].oneOff > r.months[worst.m].base * 0.02;
      const why = worst.m === 0 ? (hiresThen ? 'the Tet bonus and new hires land in the same month. Move the hires later and it recovers.' : 'the Tet bonus is paid this month. It is normal; make sure the cash is there.') : (hiresThen ? 'hiring and severance costs land together this month. Spread them out.' : 'costs outrun revenue this month.');
      w.push({ level: 'crit', text: `${fmt.month(worst.m + 1)} loses money (${fmt.money(worst.profit)}) — ${why}` });
    }
    const hireMonths = DIVS.filter(d => (s.divs[d.key].delta + roleSum(s.divs[d.key])) > 0).map(d => s.divs[d.key].month);
    if (hireMonths.length && r.totals.hires > 150) w.push({ level: 'warn', text: `${fmt.int(r.totals.hires)} new hires is a lot to recruit at once — roughly ${Math.ceil(r.totals.hires / 25)} recruiter-months of work. Spread them over two or three months.` });
    if (s.raise >= 12) w.push({ level: 'warn', text: `A ${s.raise}% raise is well above the market average of 7–9%. Great for keeping people; check the ${fmt.money(r.year.cost - b.year.cost)} yearly bill.` });
    if (s.attrition >= 20) w.push({ level: 'warn', text: `${s.attrition}% leaving a year means re-hiring ${fmt.int(r.totals.leavers)} people — ${fmt.money(r.totals.leavers * 15 * s.recruitCost)} in recruiting cost alone.` });
    if (s.otFactor >= 1.5) w.push({ level: 'warn', text: `Overtime at ${fmt.pct(s.otFactor - 1, { plus: true, d: 0 })} vs today brushes the 40 h/month legal cap for factory roles. Hiring may be cheaper.` });
    if (!w.length) w.push({ level: 'ok', text: 'Nothing to worry about. Margin, cash and hiring pace all look healthy.' });
    return w;
  }

  // ---- Tiny SVG chart kit ----
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  const nice = max => { const p = Math.pow(10, Math.floor(Math.log10(max))); const n = max / p; const s = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10; return s * p; };

  function tooltip(container) {
    let t = container.querySelector('.wf-tip');
    if (!t) { t = document.createElement('div'); t.className = 'wf-tip'; container.appendChild(t); }
    return t;
  }

  // Line/area chart: series = [{name, values[12], color, dash, area}]
  function lines(container, { series, fmtY = fmt.money, x = MONTHS, band, baseline0 = true, h = 220, endLabels = false }) {
    container.innerHTML = ''; container.classList.add('wf-chart');
    const W = container.clientWidth || 600, H = h, P = { l: 56, r: endLabels ? 78 : 24, t: 18, b: 28 };
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', height: H }, container);
    const all = series.flatMap(s => s.values).concat(band ? [band.lo, band.hi] : []);
    let max = Math.max(...all), min = Math.min(0, ...all);
    if (!baseline0) min = Math.min(...all);
    const span = nice((max - min) * 1.15 || 1); max = min + span;
    const X = i => P.l + (W - P.l - P.r) * i / (x.length - 1);
    const Y = v => P.t + (H - P.t - P.b) * (1 - (v - min) / (max - min));
    for (let i = 0; i <= 4; i++) {
      const v = min + (max - min) * i / 4, y = Y(v);
      el('line', { x1: P.l, x2: W - P.r, y1: y, y2: y, class: 'wf-grid' }, svg);
      el('text', { x: P.l - 8, y: y + 4, class: 'wf-ax', 'text-anchor': 'end' }, svg).textContent = fmtY(v);
    }
    if (min < 0) el('line', { x1: P.l, x2: W - P.r, y1: Y(0), y2: Y(0), class: 'wf-zero' }, svg);
    x.forEach((m, i) => { el('text', { x: X(i), y: H - 8, class: 'wf-ax', 'text-anchor': 'middle' }, svg).textContent = m; });
    if (band) el('rect', { x: P.l, y: Y(band.hi), width: W - P.l - P.r, height: Y(band.lo) - Y(band.hi), class: 'wf-band' }, svg);
    series.forEach(s => {
      const pts = s.values.map((v, i) => `${X(i)},${Y(v)}`);
      if (s.area) el('path', { d: `M${X(0)},${Y(Math.max(min,0))} L${pts.join(' L')} L${X(x.length - 1)},${Y(Math.max(min,0))} Z`, fill: s.color, opacity: 0.10 }, svg);
      el('path', { d: 'M' + pts.join(' L'), fill: 'none', stroke: s.color, 'stroke-width': s.dash ? 2 : 2.5, 'stroke-dasharray': s.dash ? '5 5' : '', 'stroke-linejoin': 'round', class: 'wf-line' }, svg);
      const last = s.values.length - 1;
      el('circle', { cx: X(last), cy: Y(s.values[last]), r: 4, fill: s.color, stroke: '#fff', 'stroke-width': 2 }, svg);
    });
    if (endLabels) { // value at the end of each line, nudged apart so they never sit on top of each other
      const used = [];
      series.filter(s => s.endLabel !== false).map(s => ({ s, y: Y(s.values[s.values.length - 1]) })).sort((a, b) => a.y - b.y).forEach(o => {
        let y = o.y; for (const u of used) if (Math.abs(y - u) < 13) y = u + 13; used.push(y);
        const t = el('text', { x: X(x.length - 1) + 9, y: y + 4, class: 'wf-end', fill: o.s.color }, svg); t.textContent = fmtY(o.s.values[o.s.values.length - 1]);
      });
    }
    // hover
    const cross = el('line', { y1: P.t, y2: H - P.b, class: 'wf-cross', opacity: 0 }, svg);
    const dots = series.map(s => el('circle', { r: 5, fill: s.color, stroke: '#fff', 'stroke-width': 2, opacity: 0 }, svg));
    const tip = tooltip(container);
    const hit = el('rect', { x: P.l, y: P.t, width: W - P.l - P.r, height: H - P.t - P.b, fill: 'transparent' }, svg);
    hit.addEventListener('mousemove', ev => {
      const r = svg.getBoundingClientRect(); const px = (ev.clientX - r.left) * W / r.width;
      const i = Math.max(0, Math.min(x.length - 1, Math.round((px - P.l) / (W - P.l - P.r) * (x.length - 1))));
      cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('opacity', 1);
      series.forEach((s, k) => { dots[k].setAttribute('cx', X(i)); dots[k].setAttribute('cy', Y(s.values[i])); dots[k].setAttribute('opacity', 1); });
      tip.innerHTML = `<b>${x[i]}</b>` + series.map(s => `<div><i style="background:${s.color}"></i>${s.name} <span>${fmtY(s.values[i])}</span></div>`).join('');
      tip.style.opacity = 1; tip.style.left = Math.min(r.width - 170, X(i) * r.width / W + 12) + 'px'; tip.style.top = (ev.clientY - r.top - 10) + 'px';
    });
    hit.addEventListener('mouseleave', () => { cross.setAttribute('opacity', 0); dots.forEach(d => d.setAttribute('opacity', 0)); tip.style.opacity = 0; });
  }

  // Grouped bars: cats[], series=[{name, values, color}]
  function bars(container, { cats, series, fmtY = fmt.money, h = 220, colors }) {
    container.innerHTML = ''; container.classList.add('wf-chart');
    const W = container.clientWidth || 600, H = h, P = { l: 56, r: 12, t: 18, b: 36 };
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', height: H }, container);
    const max = nice(Math.max(...series.flatMap(s => s.values)) * 1.15 || 1);
    const Y = v => P.t + (H - P.t - P.b) * (1 - v / max);
    for (let i = 0; i <= 4; i++) { const v = max * i / 4, y = Y(v); el('line', { x1: P.l, x2: W - P.r, y1: y, y2: y, class: 'wf-grid' }, svg); el('text', { x: P.l - 8, y: y + 4, class: 'wf-ax', 'text-anchor': 'end' }, svg).textContent = fmtY(v); }
    const gw = (W - P.l - P.r) / cats.length, bw = Math.min(28, (gw * 0.7) / series.length);
    const tip = tooltip(container);
    cats.forEach((c, i) => {
      const cx = P.l + gw * i + gw / 2;
      // category label, wrapped onto two lines when it will not fit the slot
      const words = String(c).split(' '); const fits = String(c).length * 6.2 < gw - 6;
      if (fits || words.length === 1) { const t = el('text', { x: cx, y: H - 10, class: 'wf-ax', 'text-anchor': 'middle' }, svg); t.textContent = fits ? c : (String(c).length > Math.floor(gw / 6.2) ? String(c).slice(0, Math.max(3, Math.floor(gw / 6.2) - 1)) + '…' : c); }
      else { const mid = Math.ceil(words.length / 2); el('text', { x: cx, y: H - 18, class: 'wf-ax', 'text-anchor': 'middle' }, svg).textContent = words.slice(0, mid).join(' '); el('text', { x: cx, y: H - 6, class: 'wf-ax', 'text-anchor': 'middle' }, svg).textContent = words.slice(mid).join(' '); }
      series.forEach((s, k) => {
        const x = cx - (series.length * bw + (series.length - 1) * 2) / 2 + k * (bw + 2);
        const v = s.values[i], y = Y(v);
        const rect = el('rect', { x, y, width: bw, height: Math.max(0, Y(0) - y), rx: 4, fill: colors ? colors[i] : s.color, opacity: s.ghost ? 0.35 : 1, class: 'wf-bar' }, svg);
        rect.addEventListener('mousemove', ev => { const r = svg.getBoundingClientRect(); tip.innerHTML = `<b>${c}</b><div><i style="background:${colors ? colors[i] : s.color}"></i>${s.name} <span>${fmtY(v)}</span></div>`; tip.style.opacity = 1; tip.style.left = Math.min(r.width - 170, ev.clientX - r.left + 12) + 'px'; tip.style.top = (ev.clientY - r.top - 10) + 'px'; });
        rect.addEventListener('mouseleave', () => tip.style.opacity = 0);
      });
    });
  }

  // Waterfall: start {label,value}, steps [{label,value}], end label
  function waterfall(container, { start, steps, endLabel, fmtY = fmt.money, h = 240, upColor = '#DC2668', downColor = '#2E7D4F', totalColor = '#5A4BB0' }) {
    container.innerHTML = ''; container.classList.add('wf-chart');
    const W = container.clientWidth || 600, H = h, P = { l: 56, r: 12, t: 18, b: 40 };
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', height: H }, container);
    const items = [{ label: start.label, value: start.value, total: true }];
    let run = start.value;
    steps.forEach(s => { items.push({ label: s.label, value: s.value, from: run }); run += s.value; });
    items.push({ label: endLabel, value: run, total: true });
    const vals = items.flatMap(i => i.total ? [i.value] : [i.from, i.from + i.value]);
    const lo = Math.min(0, ...vals), hiV = Math.max(...vals);
    const min = lo, max = min + nice((hiV - lo) * 1.1 || 1);
    const Y = v => P.t + (H - P.t - P.b) * (1 - (v - min) / (max - min));
    for (let i = 0; i <= 4; i++) { const v = min + (max - min) * i / 4, y = Y(v); el('line', { x1: P.l, x2: W - P.r, y1: y, y2: y, class: 'wf-grid' }, svg); el('text', { x: P.l - 8, y: y + 4, class: 'wf-ax', 'text-anchor': 'end' }, svg).textContent = fmtY(v); }
    const gw = (W - P.l - P.r) / items.length, bw = Math.min(56, gw * 0.62);
    const tip = tooltip(container);
    items.forEach((it, i) => {
      const cx = P.l + gw * i + gw / 2;
      const a = it.total ? 0 : it.from, b = it.total ? it.value : it.from + it.value;
      const y1 = Y(Math.max(a, b)), y2 = Y(Math.min(a, b));
      const color = it.total ? totalColor : (it.value >= 0 ? upColor : downColor);
      const r = el('rect', { x: cx - bw / 2, y: y1, width: bw, height: Math.max(2, y2 - y1), rx: 4, fill: color, class: 'wf-bar' }, svg);
      if (!it.total && i < items.length - 1) el('line', { x1: cx + bw / 2, x2: cx + gw - bw / 2, y1: Y(b), y2: Y(b), class: 'wf-connector' }, svg);
      if (it.total && i === 0) el('line', { x1: cx + bw / 2, x2: cx + gw - bw / 2, y1: Y(b), y2: Y(b), class: 'wf-connector' }, svg);
      const words = String(it.label).split(' '), fits = String(it.label).length * 6.2 < gw - 4;
      if (fits || words.length === 1) { const lbl = el('text', { x: cx, y: H - 22, class: 'wf-ax', 'text-anchor': 'middle' }, svg); lbl.textContent = fits ? it.label : String(it.label).slice(0, Math.max(3, Math.floor(gw / 6.2) - 1)) + '…'; }
      else { const mid = Math.ceil(words.length / 2); el('text', { x: cx, y: H - 26, class: 'wf-ax', 'text-anchor': 'middle' }, svg).textContent = words.slice(0, mid).join(' '); el('text', { x: cx, y: H - 14, class: 'wf-ax', 'text-anchor': 'middle' }, svg).textContent = words.slice(mid).join(' '); }
      const val = el('text', { x: cx, y: y1 - 6, class: 'wf-val', 'text-anchor': 'middle' }, svg); val.textContent = it.total ? fmtY(it.value) : fmtY(it.value, { plus: true });
      r.addEventListener('mousemove', ev => { const rr = svg.getBoundingClientRect(); tip.innerHTML = `<b>${it.label}</b><div><i style="background:${color}"></i>${it.total ? '' : 'Change '}<span>${fmtY(it.value, { plus: !it.total })}</span></div>`; tip.style.opacity = 1; tip.style.left = Math.min(rr.width - 170, ev.clientX - rr.left + 12) + 'px'; tip.style.top = (ev.clientY - rr.top - 10) + 'px'; });
      r.addEventListener('mouseleave', () => tip.style.opacity = 0);
    });
  }

  // 100% horizontal stack (plain HTML)
  function stack(container, layers, total) {
    container.innerHTML = '';
    container.classList.add('wf-stack');
    const bar = document.createElement('div'); bar.className = 'wf-stack-bar';
    const leg = document.createElement('div'); leg.className = 'wf-stack-legend';
    layers.forEach(l => {
      const seg = document.createElement('div'); seg.style.width = (l.value / total * 100) + '%'; seg.style.background = l.color; seg.title = `${l.name}: ${fmt.money(l.value)}`; bar.appendChild(seg);
      const li = document.createElement('div'); li.innerHTML = `<i style="background:${l.color}"></i><span>${l.name}</span><b>${fmt.money(l.value)}</b><small>${fmt.pct(l.value / total, { d: 0 })}</small>`; leg.appendChild(li);
    });
    container.appendChild(bar); container.appendChild(leg);
  }

  const CHART_CSS = `
    .wf-chart{position:relative;width:100%}
    .wf-chart svg{display:block;overflow:visible;font-family:inherit}
    .wf-grid{stroke:#E8EAF2;stroke-width:1}
    .wf-zero{stroke:#94A3B8;stroke-width:1.5}
    .wf-cross{stroke:#94A3B8;stroke-width:1;stroke-dasharray:3 3}
    .wf-connector{stroke:#CBD5E1;stroke-width:1;stroke-dasharray:3 3}
    .wf-ax{font-size:11px;fill:#64748B}
    .wf-val{font-size:11px;fill:#1E1B2E;font-weight:600}
    .wf-end{font-size:11px;font-weight:800;font-variant-numeric:tabular-nums;paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}
    .wf-band{fill:#2E7D4F;opacity:.07}
    .wf-line{transition:d .35s ease}
    .wf-bar{transition:y .35s ease,height .35s ease}
    .wf-tip{position:absolute;pointer-events:none;opacity:0;transition:opacity .15s;background:#1E1B2E;color:#fff;font-size:12px;border-radius:8px;padding:8px 10px;min-width:150px;z-index:5;box-shadow:0 8px 24px rgba(30,27,46,.25)}
    .wf-tip b{display:block;margin-bottom:4px;font-weight:600}
    .wf-tip div{display:flex;align-items:center;gap:6px;white-space:nowrap}
    .wf-tip div span{margin-left:auto;font-variant-numeric:tabular-nums}
    .wf-tip i{width:8px;height:8px;border-radius:2px;display:inline-block}
    .wf-stack-bar{display:flex;height:22px;border-radius:6px;overflow:hidden;gap:2px;background:#fff}
    .wf-stack-bar div{transition:width .35s ease;min-width:2px}
    .wf-stack-legend{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px 18px;margin-top:12px;font-size:12px}
    .wf-stack-legend div{display:flex;align-items:center;gap:6px}
    .wf-stack-legend i{width:10px;height:10px;border-radius:3px;flex:none}
    .wf-stack-legend b{margin-left:auto;font-weight:600;font-variant-numeric:tabular-nums}
    .wf-stack-legend small{color:#64748B;width:32px;text-align:right}
    .ic{width:18px;height:18px;flex:none}
  `;
  const injectCss = () => { const s = document.createElement('style'); s.textContent = CHART_CSS; document.head.appendChild(s); };

  return { MONTHS, MONTHS_LONG, DIVS, DIV, K, defaultState, compute, baseline, clone, roleSum, fmt, animateNumber, icon, describe, warnings,
    maxHeadsForMargin, maxRaiseForMargin, chart: { lines, bars, waterfall, stack }, injectCss };
})();
