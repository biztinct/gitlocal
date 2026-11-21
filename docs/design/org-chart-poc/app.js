/* ---------- state ---------- */
const S = {
  view: 'tree',          // tree | lr | list | teams
  compact: false,
  colorBy: 'dept',       // dept | loc | type | tenure
  zoom: 1, px: 0, py: 0,
  sel: null, hover: null,
  q: '', sugg: -1,
  filters: {dept: null, loc: null, type: null},
  focus: null,           // kpi focus: open | nomgr | dotted | wide | new
  levels: 0,             // 0 = all
  draft: false, changes: [], undone: [], live: [],
  asOf: 0,               // days offset from today (negative = past)
  scenario: 'normal',
  menu: null, dlg: null, side: null, sideTab: 'team', toast: null,
  dragId: null, overId: null,
  protoMin: false,
  base: null,            // snapshot of managerIds before draft
};
try { const v = localStorage.getItem('org-scn'); if (v && SCENARIOS[v]) S.scenario = v; } catch (e) {}

const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const byId = id => DATA.find(p => p.id === id);
let DATA = PEOPLE;

/* ---------- scenario data ---------- */
function applyScenario() {
  DATA = PEOPLE.map(p => Object.assign({}, p));
  if (S.scenario === 'wide') {
    const n = DATA.find(p => p.title === 'Regional Lead · South');
    DATA.filter(p => p.title === 'Field agronomist' && p.managerId !== n.id && !p.open).slice(0, 6).forEach(p => p.managerId = n.id);
  }
  if (S.scenario === 'nomgr') DATA.forEach(p => { if (p.title !== 'Chief Executive Officer') p.managerId = null; p.dotted = null; });
  if (S.scenario === 'big') {
    let id = 5000;
    const leads = DATA.filter(p => /Lead|Head|Manager/.test(p.title) && !p.open);
    for (let k = 0; k < 357; k++) {
      const m = leads[k % leads.length];
      const nm = mkName();
      DATA.push({id: id++, name: nm, ini: nm.split(' ').slice(-1)[0][0] + nm[0], title: 'Field agronomist', dept: m.dept, loc: m.loc, type: 'Full-time', joined: daysAgo(100 + k), managerId: m.id, dotted: null, open: false, status: '', collapsed: false});
    }
    DATA.filter(p => p.managerId === byId(1).id || p.managerId && byId(p.managerId)?.managerId === 1).forEach(p => { if (kids(p.id).length > 4) p.collapsed = true; });
  }
  // Start folded like the best tools do: leadership and leads open, big field teams tucked behind a "+N" badge.
  if (S.scenario !== 'big') DATA.forEach(p => { if (depth(p.id) >= 2 && kids(p.id).length >= 4) p.collapsed = true; });
  S.changes = []; S.undone = []; S.live = []; S.draft = false; S.sel = null; S.focus = null; S.side = null;
}

/* ---------- tree helpers ---------- */
const visibleData = () => DATA.filter(p => {
  if (S.asOf < 0 && p.joined > daysAgo(-S.asOf)) return false;
  return true;
}).concat(S.asOf > 0 ? FUTURE.filter(f => f.joined <= daysAgo(-S.asOf)) : []);
const isVis = id => { const p = byId(id) || FUTURE.find(f => f.id === id); return !!p && !(S.asOf < 0 && p.joined > daysAgo(-S.asOf)) && !(p.future && !(S.asOf > 0 && p.joined <= daysAgo(-S.asOf))); };
// The manager a card hangs from on screen. In the time machine a manager who had not joined yet
// is skipped and the line goes to the next person up — the chart never shows a gap for someone who was not there.
const effMgr = p => { let m = p.managerId; while (m && !isVis(m)) m = (byId(m) || {}).managerId; return m || null; };
const kids = id => visibleData().filter(p => effMgr(p) === id);
const roots = () => visibleData().filter(p => !effMgr(p));
const descendants = id => { const out = []; const walk = i => kids(i).forEach(k => { out.push(k); walk(k.id); }); walk(id); return out; };
const ancestors = id => { const out = []; let p = byId(id); while (p && p.managerId) { p = byId(p.managerId) || FUTURE.find(f => f.id === p.managerId); if (p) out.push(p); } return out; };
const depth = id => ancestors(id).length;
const isDesc = (a, b) => descendants(a).some(p => p.id === b); // b under a
const tenure = p => { const d = Math.round((TODAY - p.joined) / 864e5); return d < 30 ? `${d} days` : d < 365 ? `${Math.round(d/30)} months` : `${(d/365).toFixed(1)} years`; };
const matches = p => {
  if (p.open) return !S.filters.type;
  if (S.filters.dept && p.dept !== S.filters.dept) return false;
  if (S.filters.loc && p.loc !== S.filters.loc) return false;
  if (S.filters.type && p.type !== S.filters.type) return false;
  return true;
};
const anyFilter = () => S.filters.dept || S.filters.loc || S.filters.type || S.q.length > 1 || S.focus;
const emphasised = p => {
  if (S.q.length > 1 && !(p.name + ' ' + p.title + ' ' + p.dept).toLowerCase().includes(S.q.toLowerCase())) return false;
  if (!matches(p)) return false;
  if (S.focus === 'open') return p.open;
  if (S.focus === 'nomgr') return !p.managerId && p.title !== 'Chief Executive Officer';
  if (S.focus === 'dotted') return !!p.dotted || DATA.some(x => x.dotted === p.id);
  if (S.focus === 'wide') return kids(p.id).length >= 10;
  if (S.focus === 'new') return p.status === 'new';
  if (S.focus === 'leave') return p.status === 'leave' || p.status === 'leaving';
  return true;
};
const colorOf = p => {
  if (p.open) return '#B45309';
  if (S.colorBy === 'dept') return DEPTS[p.dept]?.c || '#64748B';
  if (S.colorBy === 'loc') return ['#5A4BB0','#0F7B4F','#2563EB','#B45309','#64748B'][LOCS.indexOf(p.loc)] || '#64748B';
  if (S.colorBy === 'type') return {'Full-time':'#5A4BB0','Part-time':'#0F7C6B','Contractor':'#B45309'}[p.type];
  const d = (TODAY - p.joined) / 864e5; return d < 90 ? '#0F7B4F' : d < 365 ? '#2563EB' : d < 1095 ? '#5A4BB0' : '#241F52';
};
const legendItems = () => {
  if (S.colorBy === 'dept') return Object.entries(DEPTS).map(([k, v]) => [k, v.c]);
  if (S.colorBy === 'loc') return LOCS.map((l, i) => [l, ['#5A4BB0','#0F7B4F','#2563EB','#B45309','#64748B'][i]]);
  if (S.colorBy === 'type') return [['Full-time','#5A4BB0'],['Part-time','#0F7C6B'],['Contractor','#B45309']];
  return [['Under 3 months','#0F7B4F'],['Under a year','#2563EB'],['1–3 years','#5A4BB0'],['3+ years','#241F52']];
};

/* ---------- layout (tidy tree) ---------- */
const NW = () => S.compact ? 180 : 224, NH = () => S.compact ? 52 : 96, GX = 22, GY = 70;
let POS = {}, ORPHANS = [], LANE = null;
function layout() {
  POS = {};
  const W = NW(), H = NH();
  const rs = roots();
  const main = rs.find(p => p.title === 'Chief Executive Officer') || rs[0];
  ORPHANS = rs.filter(p => p !== main);
  const shown = id => { const p = byId(id) || FUTURE.find(f => f.id === id); if (!p || p.collapsed) return []; if (S.levels && depth(id) + 1 >= S.levels) return []; return kids(id); };
  // Slots: a manager's children with no visible team of their own are stacked in ONE column
  // (3 or more of them) — the trick Workday and Lucidchart use so a 13-person field team
  // does not make the whole chart 3 screens wide. Sideways view keeps the plain tree.
  const STACK = S.view === 'tree', IND = 28, SY = 12;
  const wid = {}, hgt = {};
  const slots = id => { const ks = shown(id); const leaves = ks.filter(k => !shown(k.id).length); if (!STACK || leaves.length < 3) return ks.map(k => ({node: k})); const out = []; let put = false; ks.forEach(k => { if (shown(k.id).length) out.push({node: k}); else if (!put) { out.push({stack: leaves}); put = true; } }); return out; };
  const measure = id => { const ss = slots(id); if (!ss.length) { hgt[id] = H; return wid[id] = W; } let w = 0, hh = 0; ss.forEach(s => { if (s.stack) { w += W + IND + GX; hh = Math.max(hh, s.stack.length * (H + SY) - SY + 8); } else { w += measure(s.node.id) + GX; hh = Math.max(hh, hgt[s.node.id]); } }); hgt[id] = H + GY + hh; return wid[id] = Math.max(W, w - GX); };
  const place = (id, x, y) => {
    const ss = slots(id);
    POS[id] = {x: x + (wid[id] - W) / 2, y, w: W, h: H};
    let cx = x;
    ss.forEach(s => {
      if (s.stack) { const tx = cx + IND / 2, ty = y + H + GY - 24; s.stack.forEach((k, i) => POS[k.id] = {x: cx + IND, y: y + H + GY + i * (H + SY), w: W, h: H, stack: {tx, ty}}); cx += W + IND + GX; }
      else { place(s.node.id, cx, y + H + GY); cx += wid[s.node.id] + GX; }
    });
  };
  let ox = 0, oy = 0;
  LANE = null;
  if (ORPHANS.length) {
    // a lane above the chart for people without a manager
    const lw = ORPHANS.length * (W + GX) - GX + 20;
    LANE = {x: 0, y: 0, w: lw, h: H + 44};
    ORPHANS.forEach((p, i) => POS[p.id] = {x: 10 + i * (W + GX), y: 34, w: W, h: H});
    oy = H + 44 + GY;
  }
  if (main) { measure(main.id); place(main.id, ox, oy); if (LANE) { const cw = wid[main.id]; if (cw > LANE.w) { const dx = (cw - LANE.w) / 2; LANE.x = dx; ORPHANS.forEach(p => POS[p.id].x += dx); } else { const dx = (LANE.w - cw) / 2; Object.keys(POS).forEach(k => { if (!ORPHANS.find(o => o.id == k)) POS[k].x += dx; }); } } }
  if (S.view === 'lr') { Object.values(POS).forEach(p => { const x = p.x, y = p.y; p.x = y * 1.0; p.y = x; p.w = W; p.h = H; }); if (LANE) { const t = LANE.x; LANE.x = LANE.y; LANE.y = t; const tw = LANE.w; LANE.w = LANE.h + 40; LANE.h = tw; } }
}
const bounds = () => { const v = Object.values(POS); if (!v.length) return {x:0,y:0,w:400,h:300}; const x0 = Math.min(...v.map(p => p.x)), y0 = Math.min(...v.map(p => p.y)), x1 = Math.max(...v.map(p => p.x + p.w)), y1 = Math.max(...v.map(p => p.y + p.h)); return {x: x0, y: y0, w: x1 - x0, h: y1 - y0}; };

/* ---------- render ---------- */
function render() {
  renderHead(); renderKpis(); renderBar(); renderDraftbar(); renderSide(); renderProto(); renderLayer();
  const cv = $('#canvas');
  cv.querySelectorAll('.float,.empty,.listview,.teams').forEach(e => e.remove());
  if (S.view === 'list') { $('#world').classList.add('hide'); renderList(); return; }
  if (S.view === 'teams') { $('#world').classList.add('hide'); renderTeams(); return; }
  $('#world').classList.remove('hide');
  layout();
  renderNodes(); renderEdges(); renderFloats();
  applyTransform();
}
function renderHead() {
  $('#crumb').innerHTML = `${I('users')} People · Org chart`;
  const n = visibleData().filter(p => !p.open).length, o = visibleData().filter(p => p.open).length;
  const lvl = Math.max(...visibleData().map(p => depth(p.id))) + 1;
  $('#subline').innerHTML = `<strong>${n} people</strong> across <strong>${Object.keys(DEPTS).length} teams</strong>, ${lvl} ${lvl === 1 ? 'level' : 'levels'} deep · ${o} open role${o === 1 ? '' : 's'} · updates itself whenever an employee record changes`;
  $('#headActions').innerHTML = `
    <button class="btn outline" data-act="me">${I('crosshair')} Find me</button>
    <button class="btn outline" data-act="menu:export">${I('download')} Export ${I('chevd')}</button>
    ${S.draft ? `<button class="btn primary" data-act="publish">${I('send')} Publish changes <span class="badge">${S.changes.length}</span></button>`
              : `<button class="btn primary" data-act="draft">${I('pencil')} Plan changes</button>`}
    ${S.menu === 'export' ? `<div class="menu">
      <h6>Export</h6>
      <button data-act="export:png">${I('image')}<span><b>Picture (PNG)</b><small>What you see now, at print quality</small></span></button>
      <button data-act="export:pdf">${I('printer')}<span><b>PDF · one page per team</b><small>Ready to print or attach</small></span></button>
      <button data-act="export:xlsx">${I('sheet')}<span><b>Spreadsheet</b><small>Name, title, team, manager, location</small></span></button>
      <hr>
      <button data-act="export:link">${I('link')}<span><b>Share a read-only link</b><small>Anyone in the company · expires in 30 days</small></span></button>
      <button data-act="print">${I('printer')}<span><b>Print</b><small>Fits the chart to A3 landscape</small></span></button>
    </div>` : ''}`;
}
function renderKpis() {
  const v = visibleData();
  const open = v.filter(p => p.open).length;
  const nomgr = ORPHANS.length || v.filter(p => !p.managerId && p.title !== 'Chief Executive Officer').length;
  const dotted = v.filter(p => p.dotted).length;
  const wide = v.filter(p => kids(p.id).length >= 10).length;
  const nw = v.filter(p => p.status === 'new').length;
  const away = v.filter(p => p.status === 'leave' || p.status === 'leaving').length;
  const spans = v.filter(p => kids(p.id).length).map(p => kids(p.id).length);
  const avg = spans.length ? (spans.reduce((a, b) => a + b, 0) / spans.length).toFixed(1) : '0';
  const k = (key, bd, ic, val, lbl) => `<button class="kpi ${S.focus === key ? 'on' : ''} ${val === 0 ? 'zero' : ''}" data-act="focus:${key}"><span class="bd ${bd}">${I(ic)}</span><span><b class="num">${val}</b><small>${lbl}</small></span></button>`;
  $('#kpis').innerHTML =
    `<div class="kpi" title="Average number of direct reports per manager"><span class="bd p">${I('users')}</span><span><b class="num">${avg}</b><small>per manager</small></span></div>` +
    k('open', 'amber', 'briefcase', open, open === 1 ? 'open role' : 'open roles') +
    k('nomgr', nomgr ? 'rose' : 'slate', 'userx', nomgr, 'no manager yet') +
    k('wide', wide ? 'amber' : 'slate', 'alert', wide, wide === 1 ? 'wide team (10+)' : 'wide teams (10+)') +
    k('dotted', 'blue', 'dotted', dotted, 'dotted lines') +
    k('new', 'green', 'star', nw, 'new this month');
}
function renderBar() {
  const f = S.filters;
  // Menus sit BESIDE their button inside a wrapper — a <button> cannot contain buttons (the parser splits it).
  const chip = (key, ic, label, val) => `<span class="cw"><button class="chip ${val ? 'on' : ''}" data-act="menu:${key}">${I(ic)} ${val ? esc(val) : label} ${val ? `<span class="x" data-act="clear:${key}">${I('x')}</span>` : I('chevd')}</button>
    ${S.menu === key ? `<div class="menu left">${menuFor(key)}</div>` : ''}</span>`;
  const seg = (v, ic, l, title) => `<button class="${S.view === v ? 'on' : ''}" data-act="view:${v}" title="${title}">${I(ic)} ${l}</button>`;
  $('#bar').innerHTML = `
    <div class="search">${I('search')}<input id="q" placeholder="Find a person, title or team…" value="${esc(S.q)}" autocomplete="off"><span class="kbd">/</span>${suggestions()}</div>
    ${chip('dept', 'building', 'Team', f.dept)}${chip('loc', 'mappin', 'Location', f.loc)}${chip('type', 'briefcase', 'Employment', f.type)}
    ${chip('color', 'palette', {dept:'Colour: team', loc:'Colour: location', type:'Colour: employment', tenure:'Colour: tenure'}[S.colorBy], null)}
    ${chip('levels', 'layers', S.levels ? `${S.levels} levels` : 'All levels', null)}
    <span class="grow"></span>
    <div class="seg">${seg('tree', 'tree', 'Top-down', 'Classic chart')}${seg('lr', 'lr', 'Sideways', 'Left to right — good for deep teams')}${seg('teams', 'grid', 'Teams', 'Who is in each team')}${seg('list', 'list', 'List', 'Indented list you can sort and export')}</div>
    <button class="chip ${S.compact ? 'on' : ''}" data-act="compact" title="Smaller cards, more on screen">${I('compact')} Compact</button>`;
}
function toolsHtml() {
  return `<div class="float tools"><div class="zoom"><button data-act="zoom:-" title="Zoom out (−)">${I('zoomout')}</button><span class="pct num" data-act="zoom:1" title="Reset to 100%">${Math.round(S.zoom * 100)}%</span><button data-act="zoom:+" title="Zoom in (+)">${I('zoomin')}</button><button data-act="fit" title="Fit everything on screen (F)">${I('fit')}</button></div>
    <button class="btn outline sm" data-act="expandall" title="Expand all (E)">${I('expand')}</button>
    <button class="btn outline sm" data-act="collapseall" title="Collapse to the top two levels (C)">${I('collapse')}</button>
    <span class="cw"><button class="btn outline sm" data-act="menu:time" title="See the chart as at another date">${I('history')} ${S.asOf ? (S.asOf < 0 ? `${-S.asOf} days ago` : `In ${S.asOf} days`) : 'Today'}</button>
      ${S.menu === 'time' ? `<div class="menu" style="min-width:340px;padding:12px">
        <h6>Time machine</h6>
        <div class="time ${S.asOf < 0 ? 'past' : S.asOf > 0 ? 'future' : ''}"><small>1 yr ago</small><input type="range" min="-365" max="90" value="${S.asOf}" id="asof"><small>+90 d</small><b>${S.asOf ? fmtD(daysAgo(-S.asOf)) : 'Today'}</b></div>
        <small style="display:block;color:var(--muted);margin-top:8px">Drag back to see who reported to whom then. Drag forward to see planned joiners and announced leavers.</small>
        <button data-act="asof:0" style="margin-top:6px">${I('rotate')}<span><b>Back to today</b></span></button>
      </div>` : ''}</span>
    <span class="cw"><button class="btn outline sm" data-act="menu:help" title="Keyboard shortcuts">${I('keyboard')}</button>
      ${S.menu === 'help' ? `<div class="menu" style="min-width:300px"><h6>Keyboard</h6>
        ${[['↑ ↓ ← →','Move between people'],['Enter','Open the side panel'],['Space','Expand or collapse'],['/','Search'],['F','Fit to screen'],['E / C','Expand all / collapse'],['M','Change manager'],['A','Add a team member'],['⌘Z / ⇧⌘Z','Undo / redo a planned change'],['Esc','Close']].map(([k, l]) => `<div class="sw"><span class="kbd" style="min-width:60px;text-align:center">${k}</span><small style="color:var(--ink2)">${l}</small></div>`).join('')}</div>` : ''}</span></div>`;
}
function menuFor(key) {
  const opt = (act, label, on, col) => `<button data-act="${act}">${col ? `<i style="width:12px;height:12px;border-radius:4px;background:${col};margin-top:3px"></i>` : I(on ? 'check' : 'minus')}<span><b>${esc(label)}</b></span>${on ? `<span class="tick">${I('check')}</span>` : ''}</button>`;
  if (key === 'dept') return `<h6>Team</h6>` + Object.entries(DEPTS).map(([k, v]) => opt(`filter:dept:${k}`, `${k} · ${DATA.filter(p => p.dept === k && !p.open).length}`, S.filters.dept === k, v.c)).join('');
  if (key === 'loc') return `<h6>Location</h6>` + LOCS.map(l => opt(`filter:loc:${l}`, `${l} · ${DATA.filter(p => p.loc === l && !p.open).length}`, S.filters.loc === l)).join('');
  if (key === 'type') return `<h6>Employment</h6>` + ['Full-time','Part-time','Contractor'].map(l => opt(`filter:type:${l}`, `${l} · ${DATA.filter(p => p.type === l && !p.open).length}`, S.filters.type === l)).join('');
  if (key === 'color') return `<h6>Colour cards by</h6>` + [['dept','Team'],['loc','Location'],['type','Employment type'],['tenure','Time with us']].map(([k, l]) => opt(`color:${k}`, l, S.colorBy === k)).join('');
  if (key === 'levels') return `<h6>Show</h6>` + [[0,'All levels'],[2,'2 levels · leadership'],[3,'3 levels · leads'],[4,'4 levels']].map(([k, l]) => opt(`levels:${k}`, l, S.levels === k)).join('');
  return '';
}
function suggestions() {
  if (S.q.length < 2) return '';
  const q = S.q.toLowerCase();
  const hits = DATA.filter(p => (p.name + ' ' + p.title + ' ' + p.dept).toLowerCase().includes(q)).slice(0, 8);
  if (!hits.length) return `<div class="sugg"><div style="padding:14px;color:var(--muted);font-size:13px">Nobody called “${esc(S.q)}”. Try a title like “agronomist” or a team like “Finance”.</div></div>`;
  return `<div class="sugg"><h6>Jump to</h6>${hits.map((p, i) => `<button class="${i === S.sugg ? 'hi' : ''}" data-act="jump:${p.id}">${avatar(p, 'av')}<span><b>${p.open ? 'Open role' : esc(p.name)}</b><small>${esc(p.title)} · ${esc(p.dept)}</small></span></button>`).join('')}</div>`;
}
const avatar = (p, cls = 'av') => `<span class="${cls}" style="background:${colorOf(p)}${p.open ? ';background:var(--amber-soft);color:var(--amber);border:1.5px dashed var(--amber-line)' : ''}">${p.open ? I('briefcase') : esc(p.ini)}${p.status ? `<i class="st ${p.status}"></i>` : ''}</span>`;

function renderNodes() {
  const host = $('#nodes');
  const W = NW(), H = NH();
  const sel = S.sel, hl = S.hover || S.sel;
  const pathIds = hl ? new Set([hl, ...ancestors(hl).map(a => a.id)]) : null;
  const changed = new Set(S.changes.map(c => c.id));
  host.innerHTML = Object.keys(POS).map(k => {
    const id = +k, p = byId(id) || FUTURE.find(f => f.id === id), pos = POS[id];
    if (!p) return '';
    const ks = kids(id), n = ks.length, dn = descendants(id).length;
    const dim = anyFilter() && !emphasised(p) && !(pathIds && pathIds.has(id));
    const tags = [];
    if (p.open) tags.push(`<span class="tag amber">${I('briefcase')} ${esc(p.hiring || 'Open role')}</span>`);
    if (p.future) tags.push(`<span class="tag blue">${I('calendar')} Starts ${fmtD(p.joined)}</span>`);
    if (p.status === 'new') tags.push(`<span class="tag green">${I('star')} Joined ${tenure(p)} ago</span>`);
    if (p.status === 'leave') tags.push(`<span class="tag amber">${I('plane')} On leave</span>`);
    if (p.status === 'leaving') tags.push(`<span class="tag rose">${I('userx')} Leaving</span>`);
    if (p.dotted) tags.push(`<span class="tag blue" title="Also reports to ${esc(byId(p.dotted)?.name || '')}">${I('dotted')} Dotted line</span>`);
    if (n >= 10) tags.push(`<span class="tag amber">${I('alert')} ${n} direct reports</span>`);
    if (p.assistant) tags.push(`<span class="tag">${I('user')} Assistant</span>`);
    if (!p.open && n && n < 10) tags.push(`<span class="tag">${I('users')} ${n} direct${dn > n ? ` · ${dn} total` : ''}</span>`);
    return `<div class="node ${S.compact ? 'compact' : ''} ${sel === id ? 'sel' : ''} ${dim ? 'dim' : ''} ${pathIds && pathIds.has(id) && sel !== id ? 'path' : ''} ${p.open ? 'open' : ''} ${p.future ? 'ghost' : ''} ${id === ME ? 'me' : ''} ${changed.has(id) ? 'changed' : ''} ${S.dragId === id ? 'drag' : ''} ${pos.stack ? 'stk' : ''} ${S.overId === id ? (canDrop(S.dragId, id) ? 'over' : 'over bad') : ''}"
        data-id="${id}" style="transform:translate(${pos.x}px,${pos.y}px);width:${W}px;min-height:${H}px" tabindex="-1" role="treeitem" aria-label="${esc(p.open ? 'Open role: ' + p.title : p.name + ', ' + p.title)}">
      <div class="top">${avatar(p)}<div class="who">
        <div class="nm">${p.open ? `Open role` : esc(p.name)}</div>
        <div class="jt">${esc(p.title)}</div>
        <div class="dp"><i style="background:${DEPTS[p.dept]?.c}"></i>${esc(p.dept)} · ${esc(p.loc)}</div>
      </div></div>
      <div class="tags">${tags.join('')}</div>
      ${!p.future ? `<div class="qa">
        ${p.open ? `<button data-act="fill:${id}" title="Fill this role with someone">${I('usercheck')}</button>` : `<button data-act="addmember:${id}" title="Add a team member (A)">${I('userplus')}</button>`}
        <button data-act="changemgr:${id}" title="Change manager (M)">${I('move')}</button>
        <button data-act="ctx:${id}" title="More">${I('more')}</button>
      </div>` : ''}
      ${n ? `<button class="tog" data-act="toggle:${id}" title="${p.collapsed ? 'Expand' : 'Collapse'} team (Space)">${p.collapsed ? `${I('plus')} ${dn}` : I(S.view === 'lr' ? 'chevl' : 'chevu')}</button>` : ''}
    </div>`;
  }).join('') + (LANE ? `<div class="lane" style="transform:translate(${LANE.x}px,${LANE.y}px);width:${LANE.w}px;height:${LANE.h}px"><h5>${I('userx')} No manager yet · drag onto a manager, or press M</h5></div>` : '');
}
function canDrop(a, b) { if (!a || !b || a === b) return false; const t = byId(b); if (!t || t.future) return false; const p = byId(a); if (p.managerId === b) return false; return !isDesc(a, b); }

function renderEdges() {
  const svg = $('#edges'), b = bounds();
  svg.setAttribute('width', b.x + b.w + 400); svg.setAttribute('height', b.y + b.h + 400);
  const hl = S.hover || S.sel; const path = hl ? new Set([hl, ...ancestors(hl).map(a => a.id)]) : null;
  const lr = S.view === 'lr';
  const edge = (a, b, cls) => {
    const A = POS[a], B = POS[b]; if (!A || !B) return '';
    let d;
    if (B.stack && !cls) { const {tx, ty} = B.stack; const x1 = A.x + A.w / 2, y1 = A.y + A.h, my = y1 + (ty - y1) / 2; d = `M${x1},${y1} C${x1},${my} ${tx},${my} ${tx},${ty} V${B.y + B.h / 2} H${B.x}`; }
    else if (lr) { const x1 = A.x + A.w, y1 = A.y + A.h / 2, x2 = B.x, y2 = B.y + B.h / 2, mx = (x1 + x2) / 2; d = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`; }
    else { const x1 = A.x + A.w / 2, y1 = A.y + A.h, x2 = B.x + B.w / 2, y2 = B.y, my = y1 + (y2 - y1) / 2; d = `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`; }
    return `<path d="${d}" class="${cls}"/>`;
  };
  let out = '', hi = '';
  Object.keys(POS).forEach(k => { const id = +k, p = byId(id) || FUTURE.find(f => f.id === id); const m = p && effMgr(p); if (m && POS[m]) { if (path && path.has(id) && path.has(m)) hi += edge(m, id, '').replace('class=""', 'class="hi"'); else out += edge(m, id, ''); } });
  out += hi;
  Object.keys(POS).forEach(k => { const p = byId(+k); if (p && p.dotted && POS[p.dotted]) out += edge(p.dotted, p.id, 'dot'); });
  // ghost edges: where a moved person used to sit
  if (S.draft) S.changes.filter(c => c.kind === 'move' && c.from && POS[c.from] && POS[c.id]).forEach(c => out += edge(c.from, c.id, 'ghost'));
  svg.innerHTML = out;
}
function renderFloats() {
  const cv = $('#canvas');
  const lg = legendItems();
  cv.insertAdjacentHTML('beforeend', `<div class="float legend"><span class="lg key">${I('palette')} Legend</span>${lg.map(([l, c]) => `<span class="lg"><i style="background:${c}"></i>${esc(l)}</span>`).join('')}
    <span class="lg"><i style="background:var(--amber-line);border:1px dashed var(--amber)"></i>Open role</span><span class="lg"><svg width="18" height="8"><path d="M1 4h16" stroke="var(--amber)" stroke-width="2" stroke-dasharray="3 3"/></svg>Dotted line</span></div>`);
  cv.insertAdjacentHTML('beforeend', `<div class="float minimap" id="minimap"></div>`);
  cv.insertAdjacentHTML('beforeend', toolsHtml());
  if (S.focus) cv.insertAdjacentHTML('beforeend', `<div class="float hint amber">${I('filter')} Showing only ${{open:'open roles',nomgr:'people without a manager',dotted:'dotted-line reports',wide:'managers with 10 or more direct reports',new:'people who joined recently',leave:'people on leave or leaving'}[S.focus]} <button class="btn sm" style="color:#fff;height:24px;padding:0 8px;background:rgba(255,255,255,.15)" data-act="focus:${S.focus}">Show everyone</button></div>`);
  if (!Object.keys(POS).length) cv.insertAdjacentHTML('beforeend', `<div class="empty"><div class="box"><div class="bd">${I('orgchart')}</div><h3>Nobody is in the chart yet</h3><p>Nobody has a manager set. Press the magic button and Payobook will suggest a chart from your teams and job titles — you confirm each line.</p><button class="btn primary" data-act="suggest">${I('wand')} Suggest a chart</button></div></div>`);
  else if (S.scenario === 'nomgr' && ORPHANS.length > 10) cv.insertAdjacentHTML('beforeend', `<div class="float hint amber" style="top:auto;bottom:150px">${I('wand')} ${ORPHANS.length} people have no manager yet <button class="btn sm" style="color:#fff;height:24px;padding:0 8px;background:rgba(255,255,255,.15)" data-act="suggest">Suggest a chart</button></div>`);
  drawMinimap();
}
function drawMinimap() {
  const mm = $('#minimap'); if (!mm) return;
  const b = bounds(), cv = $('#canvas').getBoundingClientRect();
  const pad = 40, bw = b.w + pad * 2, bh = b.h + pad * 2;
  const vx = -S.px / S.zoom, vy = -S.py / S.zoom, vw = cv.width / S.zoom, vh = cv.height / S.zoom;
  mm.innerHTML = `<svg viewBox="${b.x - pad} ${b.y - pad} ${bw} ${bh}" preserveAspectRatio="xMidYMid meet">${Object.keys(POS).map(k => { const p = byId(+k) || {}; const q = POS[k]; return `<rect class="n ${p.open ? 'op' : ''}" x="${q.x}" y="${q.y}" width="${q.w}" height="${q.h}" rx="8"/>`; }).join('')}<rect class="vp" x="${vx}" y="${vy}" width="${vw}" height="${vh}" rx="6"/></svg>`;
}

/* ---------- pan / zoom ---------- */
function applyTransform(anim) {
  const w = $('#world'); w.classList.toggle('anim', !!anim);
  w.style.transform = `translate(${S.px}px,${S.py}px) scale(${S.zoom})`;
  $('.zoom .pct') && ($('.zoom .pct').textContent = Math.round(S.zoom * 100) + '%');
  drawMinimap();
}
function fit(anim = true) {
  layout();
  const b = bounds(), cv = $('#canvas').getBoundingClientRect();
  // Never shrink below readable. If it still does not fit, centre on the top of the chart and let people pan.
  const want = Math.min((cv.width - 60) / b.w, (cv.height - 120) / b.h);
  const z = Math.min(1.1, Math.max(.42, want));
  S.zoom = z;
  const rootPos = POS[(roots().find(p => p.title === 'Chief Executive Officer') || roots()[0])?.id];
  if (want < .42 && rootPos) S.px = cv.width / 2 - (rootPos.x + rootPos.w / 2) * z; else S.px = (cv.width - b.w * z) / 2 - b.x * z;
  S.py = 36 - b.y * z;
  applyTransform(anim);
}
function centerOn(id, anim = true) {
  layout(); const p = POS[id]; if (!p) return;
  const cv = $('#canvas').getBoundingClientRect();
  if (S.zoom < .6) S.zoom = .9;
  const off = S.side && innerWidth <= 1500 ? 180 : 0; // the side panel overlays the right edge on smaller screens
  S.px = cv.width / 2 - off - (p.x + p.w / 2) * S.zoom; S.py = cv.height / 2 - (p.y + p.h / 2) * S.zoom - 40;
  applyTransform(anim);
}
function zoomAt(f, cx, cy) {
  const z = Math.min(2.5, Math.max(.12, S.zoom * f));
  const cv = $('#canvas').getBoundingClientRect();
  cx = cx ?? cv.width / 2; cy = cy ?? cv.height / 2;
  S.px = cx - (cx - S.px) * (z / S.zoom); S.py = cy - (cy - S.py) * (z / S.zoom); S.zoom = z;
  applyTransform(false);
}
(function pan() {
  const cv = $('#canvas'); let down = null;
  cv.addEventListener('pointerdown', e => { if (e.target.closest('.node,.float,button')) return; down = {x: e.clientX, y: e.clientY, px: S.px, py: S.py}; cv.classList.add('grabbing'); });
  window.addEventListener('pointermove', e => { if (!down) return; S.px = down.px + e.clientX - down.x; S.py = down.py + e.clientY - down.y; applyTransform(false); });
  window.addEventListener('pointerup', () => { down = null; cv.classList.remove('grabbing'); });
  cv.addEventListener('wheel', e => { if (S.view === 'list' || S.view === 'teams') return; e.preventDefault(); const r = cv.getBoundingClientRect(); if (e.ctrlKey || e.metaKey) zoomAt(e.deltaY < 0 ? 1.1 : .9, e.clientX - r.left, e.clientY - r.top); else { S.px -= e.deltaX; S.py -= e.deltaY; applyTransform(false); } }, {passive: false});
  cv.addEventListener('click', e => { const mm = e.target.closest('.minimap'); if (mm) { const r = mm.getBoundingClientRect(), b = bounds(), pad = 40; const sx = (b.w + pad * 2) / r.width, sy = (b.h + pad * 2) / r.height, s = Math.max(sx, sy); const wx = b.x - pad + (e.clientX - r.left) * s - ((r.width * s) - (b.w + pad * 2)) / 2, wy = b.y - pad + (e.clientY - r.top) * s - ((r.height * s) - (b.h + pad * 2)) / 2; const c = cv.getBoundingClientRect(); S.px = c.width / 2 - wx * S.zoom; S.py = c.height / 2 - wy * S.zoom; applyTransform(true); } });
})();

/* ---------- drag to re-assign ---------- */
/* Pointer-based (works with mouse, trackpad and touch — native HTML5 drag does not on touch).
   A ghost copy of the card follows the pointer; the card under it lights green (can drop) or rose (would make a loop). */
let dragSuppressClick = false;
(function dnd() {
  const host = $('#nodes');
  let start = null, ghost = null, lastOver = null;
  const setOver = id => {
    if (id === lastOver) return;
    if (lastOver != null) host.querySelector(`.node[data-id="${lastOver}"]`)?.classList.remove('over', 'bad');
    lastOver = id; S.overId = id;
    if (id != null) { const el = host.querySelector(`.node[data-id="${id}"]`); if (el) { el.classList.add('over'); if (!canDrop(S.dragId, id)) el.classList.add('bad'); } }
  };
  host.addEventListener('pointerdown', e => {
    const n = e.target.closest('.node'); if (!n || e.button !== 0 || e.target.closest('button')) return;
    const p = byId(+n.dataset.id); if (!p || p.open || p.future) return;
    start = {x: e.clientX, y: e.clientY, id: p.id, el: n};
  });
  window.addEventListener('pointermove', e => {
    if (!start) return;
    if (!S.dragId) { if (Math.hypot(e.clientX - start.x, e.clientY - start.y) < 6) return;
      S.dragId = start.id; dragSuppressClick = true; start.el.classList.add('drag');
      ghost = start.el.cloneNode(true); ghost.classList.remove('drag', 'sel'); ghost.style.cssText += `;position:fixed;left:0;top:0;z-index:300;pointer-events:none;opacity:.95;box-shadow:var(--sh-3);transform:translate(${e.clientX + 12}px,${e.clientY + 12}px) scale(${Math.max(.7, S.zoom)}) rotate(-2deg);transform-origin:0 0;transition:none;min-height:0`; document.body.appendChild(ghost);
      $('#canvas').insertAdjacentHTML('beforeend', `<div class="float hint" id="draghint">${I('move')} Drop on the new manager · ${S.draft ? 'added to your planned changes' : 'takes effect straight away'}</div>`);
    }
    ghost.style.transform = `translate(${e.clientX + 12}px,${e.clientY + 12}px) scale(${Math.max(.7, S.zoom)}) rotate(-2deg)`;
    const under = document.elementFromPoint(e.clientX, e.clientY)?.closest('.node');
    setOver(under && +under.dataset.id !== S.dragId ? +under.dataset.id : null);
  });
  window.addEventListener('pointerup', () => {
    if (!start) return;
    const from = S.dragId, to = S.overId; start = null;
    if (!from) return;
    ghost?.remove(); ghost = null; $('#draghint')?.remove(); setOver(null);
    S.dragId = null; S.overId = null;
    if (to && canDrop(from, to)) openMoveConfirm(from, to);
    else { render(); if (to) toast(`Can't do that — ${short(byId(to))} is inside ${short(byId(from))}'s own team.`, 'alert'); }
    setTimeout(() => dragSuppressClick = false, 0);
  });
})();
