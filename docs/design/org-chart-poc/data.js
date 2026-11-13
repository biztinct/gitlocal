/* Example company — invented people, no real staff. 63 people, 8 teams, 4 levels. */
const DEPTS = {
  'Leadership':      {c:'#5A4BB0'},
  'Agronomy':        {c:'#0F7B4F'},
  'Operations':      {c:'#2563EB'},
  'Finance & Partnerships': {c:'#B45309'},
  'Carbon & Innovation': {c:'#0F7C6B'},
  'People & Culture':{c:'#DC2655'},
  'Product & Technology': {c:'#7C3AED'},
  'Legal':           {c:'#64748B'},
};
const LOCS = ['Hà Nội', 'Hồ Chí Minh', 'Cần Thơ', 'Đà Lạt', 'Remote'];
const FAM = ['Nguyễn','Trần','Lê','Phạm','Hoàng','Võ','Đặng','Bùi','Đỗ','Huỳnh','Phan','Trương','Ngô','Dương','Lý'];
const MID = ['Văn','Thị','Minh','Thanh','Ngọc','Quốc','Hữu','Đức','Thu','Gia','Bảo','Kim'];
const GIV = ['An','Bình','Châu','Dũng','Giang','Hà','Hải','Hạnh','Hiếu','Hùng','Khánh','Khoa','Lan','Linh','Long','Mai','Nam','Ngân','Nhi','Phát','Phong','Phúc','Quang','Quyên','Sơn','Tâm','Thảo','Thắng','Thư','Tiến','Trâm','Trí','Trung','Tú','Tuấn','Uyên','Vân','Việt','Vinh','Vy','Xuân','Yến','Đạt','Hậu','Kiên','Lộc','Mỹ','Nghĩa','Oanh','Phương','Quân','Sang','Tài','Thịnh','Toàn','Trang','Tùng','Vũ','Hằng','Duy','Hoà','Nhân','Thuỷ'];
let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
let gi = 0;
const mkName = () => `${FAM[Math.floor(rnd()*FAM.length)]} ${MID[Math.floor(rnd()*MID.length)]} ${GIV[gi++ % GIV.length]}`;
const TODAY = new Date('2026-11-04');
const daysAgo = n => { const d = new Date(TODAY); d.setDate(d.getDate() - n); return d; };
const fmtD = d => d.toLocaleDateString('en-GB', {day:'numeric', month:'short', year:'numeric'});

/* Build the tree. Each spec: [title, dept, [children...]] ; strings prefixed '+' are open roles. */
let nextId = 1;
const PEOPLE = [];
function mk(title, dept, opts = {}) {
  const p = {
    id: nextId++, name: opts.open ? '' : mkName(), title, dept,
    loc: opts.loc || LOCS[Math.floor(rnd()*LOCS.length)],
    type: opts.type || (rnd() < .12 ? 'Contractor' : rnd() < .1 ? 'Part-time' : 'Full-time'),
    joined: opts.joined || daysAgo(Math.floor(60 + rnd() * 1800)),
    managerId: null, dotted: null, open: !!opts.open, status: opts.status || '',
    collapsed: false, assistant: !!opts.assistant, hiring: opts.hiring || '',
  };
  PEOPLE.push(p);
  return p;
}
function under(mgr, list) { list.forEach(c => c.managerId = mgr.id); return mgr; }
function many(n, title, dept, mgr, opts) { for (let k = 0; k < n; k++) mk(title, dept, opts).managerId = mgr.id; }

const ceo = mk('Chief Executive Officer', 'Leadership', {loc:'Hà Nội', type:'Full-time', joined:daysAgo(2400)});
const ea  = mk('Executive Assistant', 'Leadership', {loc:'Hà Nội', assistant:true}); ea.managerId = ceo.id;
const coo = mk('Chief Operating Officer', 'Leadership', {loc:'Hà Nội'});
const cfo = mk('Chief Financial Officer', 'Leadership', {loc:'Hà Nội'});
const cao = mk('Head of Agronomy', 'Agronomy', {loc:'Cần Thơ'});
const cpo = mk('Head of People & Culture', 'People & Culture', {loc:'Hồ Chí Minh'});
const cto = mk('Head of Product & Technology', 'Product & Technology', {open:true, hiring:'Interviewing · 3 candidates', loc:'Hồ Chí Minh'});
under(ceo, [coo, cfo, cao, cpo, cto]);

/* Agronomy: 31 — 3 regional leads */
const agN = mk('Regional Lead · North', 'Agronomy', {loc:'Hà Nội'});
const agS = mk('Regional Lead · South', 'Agronomy', {loc:'Cần Thơ'});
const agH = mk('Regional Lead · Highlands', 'Agronomy', {loc:'Đà Lạt'});
under(cao, [agN, agS, agH]);
many(9, 'Field agronomist', 'Agronomy', agN, {loc:'Hà Nội'});
many(12, 'Field agronomist', 'Agronomy', agS, {loc:'Cần Thơ'});
many(4, 'Field agronomist', 'Agronomy', agH, {loc:'Đà Lạt'});
const sen = mk('Senior agronomist', 'Agronomy', {loc:'Cần Thơ'}); sen.managerId = agS.id;
mk('Field agronomist', 'Agronomy', {open:true, hiring:'Open · posted 9 days ago', loc:'Đà Lạt'}).managerId = agH.id;

/* Operations: 15 */
const opsL = mk('Logistics Lead', 'Operations', {loc:'Hồ Chí Minh'});
const opsQ = mk('Quality Lead', 'Operations', {loc:'Cần Thơ'});
under(coo, [opsL, opsQ]);
many(6, 'Operations officer', 'Operations', opsL);
many(4, 'Quality officer', 'Operations', opsQ);
const proc = mk('Process analyst', 'Operations', {loc:'Remote'}); proc.managerId = coo.id;
const proc2 = mk('Process analyst', 'Operations', {loc:'Remote'}); proc2.managerId = coo.id;

/* Finance & Partnerships: 7 */
const finL = mk('Finance Lead', 'Finance & Partnerships', {loc:'Hà Nội'}); finL.managerId = cfo.id;
many(3, 'Accountant', 'Finance & Partnerships', finL, {loc:'Hà Nội'});
const partM = mk('Partnerships Manager', 'Finance & Partnerships', {loc:'Hồ Chí Minh'}); partM.managerId = cfo.id;
many(2, 'Partnerships associate', 'Finance & Partnerships', partM);

/* Carbon & Innovation: 4 — programme lead reports to COO, dotted to CEO */
const carb = mk('Programme Lead · Carbon', 'Carbon & Innovation', {loc:'Hà Nội'}); carb.managerId = coo.id; carb.dotted = ceo.id;
many(3, 'Carbon analyst', 'Carbon & Innovation', carb);

/* People & Culture: 2 */
const hr1 = mk('People Partner', 'People & Culture', {loc:'Hồ Chí Minh'}); hr1.managerId = cpo.id;
const hr2 = mk('Payroll Specialist', 'People & Culture', {loc:'Hà Nội'}); hr2.managerId = cpo.id; hr2.dotted = cfo.id;

/* Product & Technology: 2 — manager is an open role */
const pm = mk('Product Manager', 'Product & Technology', {loc:'Hồ Chí Minh'}); pm.managerId = cto.id;
const dev = mk('Software Engineer', 'Product & Technology', {loc:'Remote'}); dev.managerId = cto.id;

/* Legal: 1 — reports to CFO */
const legal = mk('Legal Counsel', 'Legal', {loc:'Hà Nội'}); legal.managerId = cfo.id;

/* Status colour: new joiner / on leave / leaving */
PEOPLE.filter(p => !p.open).slice(20, 23).forEach(p => { p.joined = daysAgo(8 + Math.floor(rnd()*20)); p.status = 'new'; });
PEOPLE[14].status = 'leave'; PEOPLE[14].statusNote = 'Annual leave until 12 Nov';
PEOPLE[33].status = 'leave'; PEOPLE[33].statusNote = 'Parental leave until Feb 2027';
PEOPLE[41].status = 'leaving'; PEOPLE[41].statusNote = 'Last day 28 Nov';
PEOPLE.forEach(p => { p.ini = p.open ? '' : p.name.split(' ').slice(-1)[0][0] + p.name.split(' ')[0][0]; });

/* Two people who nobody has set a manager for yet (new starters imported from the pay data file). */
const orphan1 = mk('Field agronomist', 'Agronomy', {loc:'Cần Thơ', joined:daysAgo(3), status:'new'});
const orphan2 = mk('Operations officer', 'Operations', {loc:'Hồ Chí Minh', joined:daysAgo(5), status:'new'});
[orphan1, orphan2].forEach(p => { p.ini = p.name.split(' ').slice(-1)[0][0] + p.name.split(' ')[0][0]; });

/* "You" — the signed-in person, a People Partner */
const ME = hr1.id;

/* Manager-change history, newest first (what the History tab shows) */
const HISTORY = {
  [carb.id]: [{when:daysAgo(40), what:'Dotted line to the CEO added', who:'Head of People & Culture'}, {when:daysAgo(300), what:'Moved from Head of Agronomy to COO', who:'CEO'}],
  [proc.id]: [{when:daysAgo(120), what:'Moved from Logistics Lead to COO', who:'COO'}],
};

/* Future: a planned joiner (shows in the time machine when scrubbing forward) */
const FUTURE = [
  {id: 9001, name:'(Planned) Data Analyst', title:'Data Analyst', dept:'Product & Technology', loc:'Remote', type:'Full-time', joined:new Date('2026-12-01'), managerId: pm.id, future:true},
];

/* Scenario presets for the prototype footer */
const SCENARIOS = {
  normal: {label:'Everyday · 63 people'},
  wide:   {label:'Wide team · a manager with 18 reports'},
  nomgr:  {label:'Nothing set up yet'},
  big:    {label:'Large company · 420 people'},
};
