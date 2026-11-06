/* ============================================================
   Payobook POC — shared dataset + shell renderer
   Grounded in the live Payobook instance:
   - April 2026 batch, Vietnam Standard Payroll, company "Payobook"
   - Real employees, real formula configs (VEC/VMC), real analytics shape
   Exposes a global `PB` used by option-a/b/c.
   ============================================================ */
const PB = (function () {

  /* ---------------- Roles ---------------- */
  const ROLES = {
    officer:  { id:"officer",  name:"Mai Pham",        title:"Payroll Officer",      initial:"MP", color:"#6D28D9" },
    approver: { id:"approver", name:"Linh Tran",       title:"HR / Approver Manager",initial:"LT", color:"#0EA5E9" },
    gm:       { id:"gm",       name:"David Nguyen",    title:"General Manager",      initial:"DN", color:"#059669" },
    admin:    { id:"admin",    name:"System Admin",    title:"System Administrator", initial:"SA", color:"#DB2777" },
  };

  /* ---------------- Sidebar IA (role-aware) ----------------
     wf = which of the 4 POC workflows the item opens
     (home | run | formula | analytics) or a stub (people|config|admin)  */
  const NAV = [
    { section:null, items:[
      { label:"Dashboard", icon:"home", wf:"home", roles:["officer","approver","gm","admin"] },
      { label:"Approvals", icon:"clipboard-check", wf:"analytics", roles:["approver","gm","admin"], badge:"3" },
    ]},
    { section:"Pay Run", items:[
      { label:"Run Payroll", icon:"zap", wf:"run", roles:["officer","admin"] },
      { label:"Pay Runs", icon:"calendar", wf:"run", roles:["officer","approver","gm","admin"] },
      { label:"Payslips", icon:"receipt", wf:"run", roles:["officer","approver","gm","admin"] },
      { label:"Import Data", icon:"download", wf:"formula", roles:["officer","admin"] },
    ]},
    { section:"People", items:[
      { label:"Employees", icon:"users", wf:"people", roles:["officer","approver","admin"] },
      { label:"Contracts", icon:"file", wf:"people", roles:["officer","approver","admin"] },
    ]},
    { section:"Insights", items:[
      { label:"Analytics", icon:"trending-up", wf:"analytics", roles:["approver","gm","admin"] },
      { label:"Reports", icon:"file-text", wf:"analytics", roles:["approver","gm","admin"] },
    ]},
    { section:"Setup", items:[
      { label:"Formula Engine", icon:"calculator", wf:"formula", roles:["officer","admin"] },
      { label:"Salary Structures", icon:"layers", wf:"config", roles:["admin"] },
      { label:"Statutory (Insurance & Tax)", icon:"shield", wf:"config", roles:["admin"] },
      { label:"Integrations", icon:"database", wf:"config", roles:["admin"] },
    ]},
    { section:"Admin", items:[
      { label:"Roles & Access", icon:"lock", wf:"admin", roles:["admin"] },
      { label:"Companies", icon:"building", wf:"admin", roles:["admin"] },
      { label:"Menu & Sidebar", icon:"compass", wf:"admin", roles:["admin"] },
    ]},
  ];

  /* ---------------- Dataset ---------------- */
  const PALETTE = ["#6D28D9","#0EA5E9","#059669","#DB2777","#F59E0B","#4F46E5","#EF4444"];
  const payslips = [
    { id:28, emp:"Nguyễn Hồng Nhung",      dept:"Finance",     title:"Senior Accountant", gross:32500000, si:3412500, pit:1150000, net:27937500, state:"done"  },
    { id:29, emp:"Nguyễn Ngọc Thùy Tiên",  dept:"HR",          title:"HR Specialist",     gross:28000000, si:2940000, pit:720000,  net:24340000, state:"done"  },
    { id:30, emp:"Võ Thị Tú Trinh",        dept:"Sales",       title:"Sales Executive",   gross:41200000, si:4326000, pit:2480000, net:34394000, state:"level2", flag:"+18% vs March (commission)" },
    { id:31, emp:"Trương Thị Thu Hiền",    dept:"Operations",  title:"Ops Coordinator",   gross:24500000, si:2572500, pit:410000,  net:21517500, state:"done"  },
    { id:32, emp:"Nguyễn Hữu Thọ",         dept:"Warehouse",   title:"Warehouse Lead",    gross:19800000, si:2079000, pit:165000,  net:17556000, state:"done"  },
    { id:33, emp:"Nguyễn Thành An",        dept:"Logistics",   title:"Driver",            gross:17500000, si:1837500, pit:95000,   net:15567500, state:"level1", flag:"Missing overtime input" },
    { id:34, emp:"Tô Thanh Liêm",          dept:"Maintenance", title:"Technician",        gross:22300000, si:2341500, pit:300000,  net:19658500, state:"done"  },
  ].map((p,i)=>({ ...p, color: PALETTE[i % PALETTE.length] }));

  const run = {
    name:"April 2026", period:"Apr 1 – Apr 30, 2026", structure:"Vietnam Standard Payroll",
    company:"Payobook", state:"level2", headcount:7,
    totalGross: payslips.reduce((s,p)=>s+p.gross,0),
    totalSI:    payslips.reduce((s,p)=>s+p.si,0),
    totalPIT:   payslips.reduce((s,p)=>s+p.pit,0),
    totalNet:   payslips.reduce((s,p)=>s+p.net,0),
    computed: 7, exceptions: payslips.filter(p=>p.flag).length,
  };

  const batches = [
    { name:"October 2025", count:14, state:"done" },
    { name:"February 2026", count:7,  state:"done" },
    { name:"April 2026",   count:7,  state:"level2" },
  ];

  const formulaConfigs = [
    { code:"VEC", name:"VPTQ End Cycle", country:"Vietnam", structure:"Vietnam Standard Payroll", rules:86, formulas:32, tests:5, validation:"PENDING VALIDATION", state:"active", cycle:"End-Cycle", currency:"VND" },
    { code:"VMC", name:"VPTQ Mid Cycle", country:"Vietnam", structure:"Vietnam Standard Payroll", rules:85, formulas:30, tests:4, validation:"PENDING VALIDATION", state:"active", cycle:"Mid-Cycle", currency:"VND" },
  ];
  const formulaRules = [
    { col:"A",  name:"TT (số thứ tự)",                code:"TT",       type:"input" },
    { col:"B",  name:"Mã số nhân viên",               code:"MSNV",     type:"input" },
    { col:"C",  name:"Họ và tên",                      code:"HVTN",     type:"input" },
    { col:"D",  name:"Đơn vị",                         code:"NV",       type:"input" },
    { col:"E",  name:"Loại HĐLĐ",                      code:"LOIHL",    type:"input" },
    { col:"G",  name:"Mức lương HĐLĐ",                 code:"MCLNGHL",  type:"input" },
    { col:"H",  name:"Phụ cấp (PCCC, ATVSV)",          code:"PHCPPCCC", type:"calc"  },
    { col:"I",  name:"Định mức Thưởng HQCV",           code:"NHMCHQCV", type:"calc"  },
    { col:"Y",  name:"Lương Ngày thường",              code:"LNGNGYTH", type:"calc"  },
    { col:"AB", name:"Lương ngày nghỉ Lễ Tết",         code:"LNGNGLTT", type:"calc"  },
    { col:"AC", name:"Lương Tăng ca ngày thường",      code:"LNGTNGCA", type:"calc"  },
    { col:"AN", name:"Phụ cấp PCCC (ĐT,ĐP), AT-VSV",   code:"PHCPATVSV",type:"calc"  },
  ];

  const analytics = {
    headcount: 28, payroll: 520400000, avgNet: 16100000, contributions: 78240000,
    payrollTrendPct: 4.2, conversionNote:"on Vietnam Standard Payroll",
    departments: [
      { name:"Sales",       cost:146000000 },
      { name:"Operations",  cost:98500000 },
      { name:"Finance",     cost:84200000 },
      { name:"Warehouse",   cost:71800000 },
      { name:"HR",          cost:62300000 },
      { name:"Maintenance", cost:57600000 },
    ],
    components: [
      { name:"Basic salary",        amt:312000000 },
      { name:"Allowances",          amt:96400000 },
      { name:"Overtime",            amt:54200000 },
      { name:"HQCV bonus",          amt:57800000 },
    ],
    trend: [430,448,455,470,498,512,520],   // last 7 months (M)
    approvals: [
      { name:"April 2026 — Vietnam Standard Payroll", amount:160971000, headcount:7, stage:"GM approval", score:96 },
      { name:"April 2026 — Indonesia Monthly",        amount:412300000, headcount:11, stage:"HR review",  score:88 },
      { name:"April 2026 — Singapore Monthly",        amount:298400000, headcount:6,  stage:"HR review",  score:91 },
    ],
  };

  const STATE_LABEL = { draft:"Draft", level1:"HR Manager pending", level2:"GM pending", done:"Done",
                        testing:"Testing", validated:"Validated", active:"Active", cancel:"Cancelled" };
  const STATE_CLASS = { draft:"b-draft", level1:"b-level1", level2:"b-level2", done:"b-done",
                        testing:"b-level1", validated:"b-level2", active:"b-done", cancel:"b-cancel" };

  /* ---------------- Lucide icon set (MIT, inlined for offline file://) ---------------- */
  const ICONS = {
    home:'<path d="M3 9.2 12 3l9 6.2"/><path d="M5 10v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V10"/><path d="M9 21v-6h6v6"/>',
    calendar:'<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    receipt:'<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
    zap:'<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    upload:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    file:'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    'file-text':'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8M16 17H8M10 9H8"/>',
    calculator:'<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M8 6h8"/><path d="M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01"/>',
    layers:'<path d="m12 2 9 4.5-9 4.5-9-4.5L12 2Z"/><path d="m3 12 9 4.5 9-4.5"/><path d="m3 17 9 4.5 9-4.5"/>',
    shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>',
    percent:'<line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    'trending-up':'<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    'bar-chart':'<line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/>',
    'clipboard-check':'<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
    'check-circle':'<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    check:'<path d="M20 6 9 17l-5-5"/>',
    lock:'<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    compass:'<circle cx="12" cy="12" r="10"/><polygon points="16.2 7.8 14.1 14.1 7.8 16.2 9.9 9.9 16.2 7.8"/>',
    settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    search:'<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    message:'<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    bell:'<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    menu:'<line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="18" y2="18"/>',
    wallet:'<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h14a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5"/><path d="M18 12a2 2 0 0 0 0 4h3v-4Z"/>',
    banknote:'<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
    clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    alert:'<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    printer:'<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect width="12" height="8" x="6" y="14"/>',
    mail:'<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m2 7 10 6 10-6"/>',
    refresh:'<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 3v5h-5"/>',
    plus:'<path d="M12 5v14M5 12h14"/>',
    sparkles:'<path d="m12 3 1.9 5.8 5.8 1.9-5.8 1.9L12 18.4l-1.9-5.8L4.3 10.7l5.8-1.9L12 3Z"/><path d="M5 3v4M19 17v4M3 5h4M17 19h4"/>',
    building:'<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
    brain:'<path d="M12 5a3 3 0 0 0-5.99.14 3.5 3.5 0 0 0-2 5.5A3.5 3.5 0 0 0 6 17a3 3 0 0 0 6 .5Z"/><path d="M12 5a3 3 0 0 1 5.99.14 3.5 3.5 0 0 1 2 5.5A3.5 3.5 0 0 1 18 17a3 3 0 0 1-6 .5Z"/>',
    flask:'<path d="M9 3h6"/><path d="M10 3v6.5L5 18a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-8.5V3"/><path d="M7.5 14h9"/>',
    table:'<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
    eye:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    database:'<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    puzzle:'<path d="M15.4 3.3a2 2 0 0 0-3 1.7V6H9.5a2 2 0 0 0-2 2v2.6H6a2 2 0 1 0 0 4h1.5V18a2 2 0 0 0 2 2h2.6v-1.5a2 2 0 1 1 4 0V20H18a2 2 0 0 0 2-2v-3h1a2 2 0 1 0 0-4h-1V8a2 2 0 0 0-2-2h-3V5a2 2 0 0 0-1.6-1.7Z"/>',
    dot:'<circle cx="12" cy="12" r="9"/>',
  };
  function icon(name, size, cls){
    size = size || 18; cls = cls || "";
    return `<svg class="lic ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name]||ICONS.dot}</svg>`;
  }

  /* ---------------- Palettes (live-switchable) ---------------- */
  const PALETTES = [
    { id:"aurora",   name:"Aurora · Violet + Emerald" },
    { id:"indigo",   name:"Indigo · Enterprise" },
    { id:"graphite", name:"Graphite · Coral" },
  ];
  function setPalette(id){
    const el = document.documentElement;
    el.classList.remove("pal-aurora","pal-indigo","pal-graphite");
    if(id && id!=="aurora") el.classList.add("pal-"+id);
  }

  /* ---------------- Helpers ---------------- */
  function fmtVND(n){
    if (n>=1e9) return "₫"+(n/1e9).toFixed(1)+"B";
    if (n>=1e6) return "₫"+(n/1e6).toFixed(1)+"M";
    if (n>=1e3) return "₫"+(n/1e3).toFixed(0)+"K";
    return "₫"+n;
  }
  function fmtFull(n){ return "₫"+n.toLocaleString("en-US"); }
  function initials(name){ const p=name.trim().split(/\s+/); return (p[0][0]+(p[p.length-1][0]||"")).toUpperCase(); }
  function badge(state){ return `<span class="badge ${STATE_CLASS[state]||"b-draft"}"><span class="d"></span>${STATE_LABEL[state]||state}</span>`; }
  function ringColor(v){ return v>=70?"#10B981": v>=40?"#F59E0B":"#EF4444"; }

  /* SVG score ring */
  function ring(value, size=56, label){
    const c = ringColor(value), r=(size-8)/2, circ=2*Math.PI*r, off=circ*(1-value/100);
    return `<span class="ring" style="width:${size}px;height:${size}px">
      <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
        <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="#EDEBF5" stroke-width="6"/>
        <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${c}" stroke-width="6"
          stroke-linecap="round" stroke-dasharray="${circ}" stroke-dashoffset="${off}"
          transform="rotate(-90 ${size/2} ${size/2})"/>
      </svg>
      <span class="num" style="font-size:${size*0.3}px;color:${c}">${label!==undefined?label:value}</span>
    </span>`;
  }
  function avatar(name,color,cls=""){ return `<span class="av ${cls}" style="background:${color}">${initials(name)}</span>`; }

  /* tiny inline sparkline / bar svg */
  function sparkline(arr, w=120, h=34, color="#6D28D9"){
    const max=Math.max(...arr), min=Math.min(...arr), span=(max-min)||1;
    const pts=arr.map((v,i)=>`${(i/(arr.length-1))*w},${h-((v-min)/span)*(h-6)-3}`).join(" ");
    return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  }
  function barChart(items, opts={}){
    const max=Math.max(...items.map(i=>i.cost||i.amt));
    return `<div style="display:flex;flex-direction:column;gap:11px">`+items.map(it=>{
      const v=it.cost||it.amt, pct=Math.round(v/max*100);
      return `<div><div class="row" style="justify-content:space-between;font-size:12.5px;margin-bottom:4px">
        <span style="font-weight:600">${it.name}</span><span class="mono muted">${fmtVND(v)}</span></div>
        <div class="prog"><span style="width:${pct}%"></span></div></div>`;
    }).join("")+`</div>`;
  }

  /* ---------------- Shell rendering ---------------- */
  let CURRENT_ROLE = "officer";
  let CURRENT_WF = "home";
  let CURRENT_PAL = "indigo";
  let WORKFLOWS = {};
  let OPTION = {};

  function navItemsFor(role){
    return NAV.map(grp=>({ section:grp.section, items: grp.items.filter(it=>it.roles.includes(role)) }))
              .filter(grp=>grp.items.length);
  }

  function renderSidebar(){
    const groups = navItemsFor(CURRENT_ROLE);
    const r = ROLES[CURRENT_ROLE];
    let html = `<div class="pb-side-brand">
        <div class="pb-side-logo">P</div>
        <div class="tx"><div class="nm">Payobook</div><div class="sub">${OPTION.name||""}</div></div>
      </div>`;
    groups.forEach(grp=>{
      if (grp.section) html += `<div class="sec-label">${grp.section}</div>`;
      html += `<div class="pb-nav">`;
      grp.items.forEach(it=>{
        const active = it.wf===CURRENT_WF ? "active":"";
        html += `<button class="pb-nav-item ${active}" data-wf="${it.wf}" data-label="${it.label}">
          <span class="ico">${icon(it.icon,18)}</span><span class="tx">${it.label}</span>
          ${it.badge?`<span class="badge">${it.badge}</span>`:""}</button>`;
      });
      html += `</div>`;
    });
    html += `<div class="pb-side-spacer"></div>
      <div class="pb-nav"><button class="pb-nav-item"><span class="ico">${icon("settings",18)}</span><span class="tx">Settings</span></button></div>
      <div class="pb-side-user"><div class="av" style="background:${r.color}">${r.initial}</div>
        <div class="umeta"><div class="nm">${r.name}</div><div class="ro">${r.title}</div></div></div>`;
    document.getElementById("pb-side").innerHTML = html;
    document.querySelectorAll(".pb-nav-item[data-wf]").forEach(b=>{
      b.onclick = ()=> go(b.dataset.wf, b.dataset.label);
    });
  }

  function renderTopbar(label){
    document.getElementById("pb-top").innerHTML = `
      <button class="burger" title="Toggle sidebar">${icon("menu",18)}</button>
      <div class="pb-crumbs"><span>Payobook</span><span>›</span><span class="cur">${label||"Home"}</span></div>
      <div class="grow"></div>
      <div class="pb-search">${icon("search",15)} <span>Search payslips, employees…</span></div>
      <button class="ico-btn" title="Messages">${icon("message",16)}<span class="dot"></span></button>
      <button class="ico-btn" title="Activities">${icon("bell",16)}</button>
      <div class="me">${ROLES[CURRENT_ROLE].initial}</div>`;
    document.querySelector(".burger").onclick = ()=> document.querySelector(".pb-app").classList.toggle("collapsed");
  }

  function renderPocBar(){
    const el = document.getElementById("poc-bar"); if(!el) return;
    el.innerHTML = `
      <span class="poc-tag">${OPTION.tag||"POC"}</span>
      <strong>${OPTION.name||""}</strong>
      <span class="poc-spacer"></span>
      <label>Palette</label>
      <select id="poc-pal">
        ${PALETTES.map(p=>`<option value="${p.id}" ${p.id===CURRENT_PAL?"selected":""}>${p.name}</option>`).join("")}
      </select>
      <label style="margin-left:8px">Role</label>
      <select id="poc-role">
        ${Object.values(ROLES).map(r=>`<option value="${r.id}" ${r.id===CURRENT_ROLE?"selected":""}>${r.title}</option>`).join("")}
      </select>
      <span style="opacity:.5">|</span>
      <a href="index.html">↤ All options</a>
      <a href="option-a.html">A</a><a href="option-b.html">B</a><a href="option-c.html">C</a>`;
    document.getElementById("poc-role").onchange = e=>{ CURRENT_ROLE=e.target.value; renderSidebar(); renderTopbar(labelFor(CURRENT_WF)); renderTopMe(); };
    document.getElementById("poc-pal").onchange = e=>{ CURRENT_PAL=e.target.value; setPalette(CURRENT_PAL); };
  }
  function renderTopMe(){ const me=document.querySelector(".pb-top .me"); if(me) me.textContent=ROLES[CURRENT_ROLE].initial; }

  function labelFor(wf){
    for (const g of NAV) for (const it of g.items) if (it.wf===wf) return it.label;
    return "Home";
  }

  function go(wf, label){
    // if current role can't see this wf, fall back to home
    const allowed = navItemsFor(CURRENT_ROLE).some(g=>g.items.some(it=>it.wf===wf));
    if (!allowed) wf="home";
    CURRENT_WF = wf;
    renderSidebar();
    renderTopbar(label||labelFor(wf));
    document.querySelectorAll(".wf-panel").forEach(p=>p.classList.remove("active"));
    const panel = document.getElementById("wf-"+wf);
    if (panel){
      panel.classList.add("active");
      if (!panel.dataset.rendered || WORKFLOWS[wf]?.alwaysRender){
        panel.innerHTML = (WORKFLOWS[wf] ? WORKFLOWS[wf].render() : stub(wf));
        panel.dataset.rendered = "1";
        if (WORKFLOWS[wf]?.mounted) WORKFLOWS[wf].mounted(panel);
      }
    }
  }

  function stub(wf){
    const titles={people:"People",config:"Configuration",admin:"Administration"};
    return `<div class="card card-pad" style="max-width:560px;margin:40px auto;text-align:center">
      <div style="color:var(--pb-brand);margin-bottom:4px">${icon("puzzle",34)}</div>
      <h2 style="margin:10px 0 6px">${titles[wf]||wf}</h2>
      <p class="muted">This area is part of the full build. It appears in the sidebar to demonstrate the
      <strong>role-aware navigation</strong> — try switching roles in the top bar and watch the menu change.
      The 3-option comparison focuses on <strong>Home, Payroll Run, Formula Config & Analytics</strong>.</p>
    </div>`;
  }

  function mountShell(opt){
    OPTION = opt; WORKFLOWS = opt.workflows||{};
    CURRENT_ROLE = opt.role || "officer";
    document.body.classList.add(opt.bodyClass||"");
    document.getElementById("app-root").innerHTML = `
      <div id="poc-bar" class="poc-bar"></div>
      <div class="pb-app">
        <aside id="pb-side" class="pb-side"></aside>
        <div class="pb-main">
          <header id="pb-top" class="pb-top"></header>
          <main class="pb-content" id="pb-content">
            ${["home","run","formula","analytics","people","config","admin"].map(w=>`<section class="wf-panel" id="wf-${w}"></section>`).join("")}
          </main>
        </div>
      </div>
      <div class="scrim" id="scrim"></div>
      <div class="drawer" id="drawer"><div class="drawer-head"><div id="drawer-title"></div><button class="x" id="drawer-x">✕</button></div><div class="drawer-body" id="drawer-body"></div></div>`;
    setPalette(CURRENT_PAL);
    renderPocBar(); renderSidebar();
    document.getElementById("drawer-x").onclick = closeDrawer;
    document.getElementById("scrim").onclick = closeDrawer;
    go(opt.start||"home");
  }

  function openDrawer(title, body){
    document.getElementById("drawer-title").innerHTML = title;
    document.getElementById("drawer-body").innerHTML = body;
    document.getElementById("drawer").classList.add("open");
    document.getElementById("scrim").classList.add("open");
  }
  function closeDrawer(){
    document.getElementById("drawer").classList.remove("open");
    document.getElementById("scrim").classList.remove("open");
  }

  return { ROLES, NAV, payslips, run, batches, formulaConfigs, formulaRules, analytics,
           STATE_LABEL, STATE_CLASS, fmtVND, fmtFull, initials, badge, ring, avatar,
           sparkline, barChart, mountShell, openDrawer, closeDrawer, go,
           icon, setPalette, PALETTES,
           get role(){return CURRENT_ROLE;}, get wf(){return CURRENT_WF;} };
})();
