/* Interactive design preview. All changes affect fictional browser-memory data. */
(function(){
  'use strict';
  const D=window.PayrollDemo,W=window.PayrollWorkbooks;
  const icons={
    home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-8H9v8H4a1 1 0 0 1-1-1z"/>',
    run:'<path d="m13 2-8 12h6l-1 8 9-12h-6z"/>',
    users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.9"/><circle cx="9" cy="7" r="4"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
    settings:'<path d="m9.8 2-.8 3-2.6 1.5-3-.8L1 9.5l2.2 2.2v2.6L1 16.5l2.4 3.8 3-.8L9 21l.8 3h4.4l.8-3 2.6-1.5 3 .8 2.4-3.8-2.2-2.2v-2.6L23 9.5l-2.4-3.8-3 .8L15 5l-.8-3z" transform="translate(0 -1) scale(1 .95)"/><circle cx="12" cy="12" r="3"/>',
    file:'<path d="M14 2H5a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9z"/><path d="M14 2v7h7M7 13h10M7 17h10"/>',
    table:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 9v12M15 9v12M3 15h18"/>',
    download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M12 3v12m-5-5 5 5 5-5"/>',
    upload:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M12 16V3m-5 5 5-5 5 5"/>',
    check:'<path d="m5 12 4 4L19 6"/>',lock:'<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4"/>',
    arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',back:'<path d="M19 12H5m6-6-6 6 6 6"/>',
    chevron:'<path d="m9 5 7 7-7 7"/>',down:'<path d="m6 9 6 6 6-6"/>',
    calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>',
    layers:'<path d="m12 3 10 5-10 5L2 8zM2 12l10 5 10-5M2 16l10 5 10-5"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    grip:'<circle cx="8" cy="5" r="1"/><circle cx="16" cy="5" r="1"/><circle cx="8" cy="12" r="1"/><circle cx="16" cy="12" r="1"/><circle cx="8" cy="19" r="1"/><circle cx="16" cy="19" r="1"/>',
    more:'<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>',
    close:'<path d="m6 6 12 12M6 18 18 6"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
    alert:'<path d="m10.2 3.9-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.8-3.1l-8-14a2 2 0 0 0-3.6 0zM12 9v4m0 4v.1"/>',
    history:'<path d="M3 12a9 9 0 1 0 3-6.7L3 8m0-5v5h5M12 7v5l3 2"/>',
    shield:'<path d="m12 3 9 4v6c0 4-5 7-9 9-4-2-9-5-9-9V7z"/><path d="m8 12 3 3 5-6"/>',
    activity:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    briefcase:'<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V3h8v4M3 12a22 22 0 0 0 18 0M12 12v3"/>',
    eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    minus:'<path d="M5 12h14"/>',plus:'<path d="M12 5v14M5 12h14"/>',
    save:'<path d="m19 3 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M7 3v6h10V3M7 21v-8h10v8"/>'
  };
  function icon(name){return '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(icons[name]||icons.file)+'</svg>';}
  function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function clone(v){return JSON.parse(JSON.stringify(v));}
  const S={country:'VN',period:'2026-10',page:'downloads',preview:'monthly',sheet:'time',models:{},layouts:{},drafts:{},draft:null,fieldMenu:null,search:'',modal:null,kind:'employee',fromRun:false,reading:false,readToken:0,pending:null,result:null,resolutions:{},success:null,lastFocus:null,dragKey:null};
  Object.keys(D.definitions).forEach(function(c){
    S.models[c]=D.seed(c);let saved=null;
    try{saved=JSON.parse(localStorage.getItem('pb_payroll_template_poc.layout.'+c)||'null');}catch(ignore){}
    const known=new Set(D.fields(c).map(function(f){return f.key;}));
    const valid=saved&&saved.layout&&['time','adjustments','available'].every(function(t){return Array.isArray(saved.layout[t]);})&&[].concat(saved.layout.time,saved.layout.adjustments,saved.layout.available).length===known.size&&new Set([].concat(saved.layout.time,saved.layout.adjustments,saved.layout.available)).size===known.size&&[].concat(saved.layout.time,saved.layout.adjustments,saved.layout.available).every(function(k){return known.has(k);});
    S.layouts[c]=valid?saved:{layout:D.layout(c),version:1};
  });
  S.draft=clone(S.layouts[S.country].layout);
  const root=document.getElementById('app'),overlay=document.getElementById('overlay'),fileInput=document.getElementById('file-input');
  let toastTimer;
  function toast(message){const e=document.getElementById('toast');e.textContent=message;e.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(function(){e.classList.remove('show');},3500);}
  function def(){return D.definitions[S.country];}
  function model(){return S.models[S.country];}
  function dirty(){return JSON.stringify(S.draft)!==JSON.stringify(S.layouts[S.country].layout);}
  function monthLabel(){return new Date(S.period+'-01T12:00:00').toLocaleDateString('en',{month:'long',year:'numeric'});}
  function context(kind,draft){return {kind:kind||S.kind,country:S.country,period:S.period,layout:draft?S.draft:S.layouts[S.country].layout,records:model().records,monthly:model().periods[S.period]||{},version:S.layouts[S.country].version};}
  function display(v){if(W.blank(v))return 'Not entered';return typeof v==='number'?new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(v):String(v);}
  function button(label,action,cls,extra){return '<button type="button" class="button '+(cls||'')+'" data-action="'+action+'" '+(extra||'')+'>'+label+'</button>';}
  function monthSelect(){return '<select class="month-control" aria-label="Pay month" data-control="period">'+['2026-09','2026-10','2026-11','2026-12','2027-01'].map(function(p){const l=new Date(p+'-01T12:00:00').toLocaleDateString('en',{month:'long',year:'numeric'});return '<option value="'+p+'" '+(S.period===p?'selected':'')+'>'+l+'</option>';}).join('')+'</select>';}
  function shell(body){
    return '<div class="shell"><aside class="sidebar"><div class="brand"><div class="logo">P</div><div><b>Payobook</b><small>Payroll Suite</small></div></div>'
      +'<div class="nav-btn">'+icon('home')+'<span>Home</span></div><div class="nav-label">Operate</div>'
      +'<button class="nav-btn '+(S.page==='payrun'?'active':'')+'" data-action="page" data-page="payrun">'+icon('run')+'<span>Pay Run</span></button>'
      +'<button class="nav-btn" data-action="employee-workbook">'+icon('users')+'<span>People</span></button><div class="nav-btn">'+icon('history')+'<span>Lifecycle</span></div><div class="nav-btn">'+icon('briefcase')+'<span>Workforce</span></div>'
      +'<div class="nav-label">Understand</div><div class="nav-btn">'+icon('activity')+'<span>Insights</span></div><div class="nav-btn">'+icon('shield')+'<span>Compliance</span></div>'
      +'<div class="nav-label">Grow</div><button class="nav-btn '+(S.page!=='payrun'?'active':'')+'" data-action="page" data-page="configurations">'+icon('settings')+'<span>Settings</span></button>'
      +'<div class="nav-spacer"></div><div class="profile"><div class="avatar">AS</div><div><b>Ash Sohani</b><small>Rize Farms</small></div></div></aside>'
      +'<main class="main"><header class="topbar"><div class="crumbs"><button class="button text sm" data-action="page" data-page="configurations">Payroll configurations</button>'+icon('chevron')+'<b>'+esc(S.page==='configurations'?'Templates':def().name)+'</b></div><div class="top-actions"><span class="preview-badge">Interactive preview · Sample data</span><span class="company">Rize Farms</span><div class="avatar" style="width:27px;height:27px;font-size:10px">AS</div></div></header>'
      +'<div class="content">'+(S.page==='configurations'?'':intro())+body+'<div class="demo-footer"><span>Design preview with fictional employees. Imports update this preview only.</span>'+button('Reset sample data','reset','text sm')+'</div></div></main></div>';
  }
  function intro(){
    const name=S.page==='payrun'?'Prepare this month’s payroll':'Payroll templates';
    return '<div class="intro"><div><div class="eyebrow">'+(S.page==='payrun'?'Pay Run':'Settings · Payroll configuration')+'</div><h1>'+name+'</h1><p>'+(S.page==='payrun'?'Bring time and monthly adjustments into one clear review.':'Keep employee records current. Bring this month’s pay into your run.')+'</p></div>'
      +'<div class="config-select"><div class="flag">'+S.country+'</div><div><select aria-label="Payroll configuration" data-control="country">'+Object.keys(D.definitions).map(function(c){return '<option value="'+c+'" '+(c===S.country?'selected':'')+'>'+esc(D.definitions[c].scheme)+'</option>';}).join('')+'</select><small>'+def().name+' · '+def().currency+' · Monthly payroll</small></div></div></div>'
      +(S.page==='payrun'?'':'<nav class="page-tabs" aria-label="Template workspace"><button class="page-tab '+(S.page==='downloads'?'active':'')+'" data-action="page" data-page="downloads">'+icon('download')+'Downloads</button><button class="page-tab '+(S.page==='layout'?'active':'')+'" data-action="page" data-page="layout">'+icon('table')+'Monthly layout'+(dirty()?'<span class="pill amber">Unsaved</span>':'')+'</button><button class="page-tab '+(S.page==='history'?'active':'')+'" data-action="page" data-page="history">'+icon('history')+'Import history</button><span class="spacer"></span><span class="tab-hint"><span class="dot"></span>Two workbooks. One place.</span></nav>');
  }
  function drawing(monthly,behind){return '<div class="sheet-drawing '+(behind?'behind':'')+'"><div class="sheet-top">'+icon('table')+(monthly?'Monthly pay inputs':'Employee records')+'</div><div class="sheet-lines">'+[1,2,3,4].map(function(){return '<div><i></i><i></i><i></i></div>';}).join('')+'</div><div class="mini-tabs">'+(monthly?'<span>Time</span><span>Monthly adjustments</span>':'<span>Employee records</span>')+'</div></div>';}
  function downloads(){
    const lay=S.layouts[S.country].layout,cols=lay.time.length+lay.adjustments.length,hasData=!!model().periods[S.period];
    return '<div class="download-grid"><section class="card download-card"><div class="card-heading"><div class="icon-box">'+icon('users')+'</div><div><div class="workflow-label">1 · Employee & contract records</div><h2>Make a lasting change</h2><p>Employee details, contracted salary and fixed recurring allowances. Pre-filled with the latest saved records.</p></div></div>'
      +'<div class="workbook-art">'+drawing(false,false)+'<div class="art-copy"><strong>Your people.<br>Their current records.</strong><p>'+model().records.length+' employees · '+D.masterFields.length+' columns<br>Employee ID & email read-only</p></div></div>'
      +'<div class="card-controls"><div class="card-meta"><span><span class="dot"></span>Latest saved records</span><span class="pill neutral">'+icon('lock')+'Identity protected</span></div><div class="card-buttons">'+button(icon('download')+'Download records','download-employee','')+button(icon('upload')+'Import changes','import-employee','soft')+'</div></div><div class="card-footer"><span>Update records only after you confirm.</span>'+button('Preview workbook '+icon('chevron'),'preview-employee','text')+'</div></section>'
      +'<section class="card download-card"><div class="card-heading"><div class="icon-box teal">'+icon('calendar')+'</div><div><div class="workflow-label">2 · Monthly pay inputs</div><h2>Prepare this month’s pay</h2><p>One Excel workbook with Time and Monthly adjustments tabs. Both identify employees by the same Employee ID.</p></div></div>'
      +'<div class="workbook-art monthly">'+drawing(true,true)+drawing(true,false)+'<div class="art-copy"><strong>Two tabs.<br>One monthly upload.</strong><p>'+model().records.length+' employees · '+cols+' input columns<br>Current month’s saved inputs</p></div></div>'
      +'<div class="card-controls"><div class="card-meta">'+monthSelect()+'<span class="pill '+(hasData?'green':'neutral')+'">'+(hasData?'Inputs already started':'New month · clean start')+'</span></div><div class="card-buttons">'+button(icon('download')+'Download month','download-monthly','primary')+button(icon('run')+'Use in Pay Run','page','', 'data-page="payrun"')+'</div></div><div class="card-footer"><span>Saved employee records stay separate.</span>'+button('Configure columns '+icon('chevron'),'page','text','data-page="layout"')+'</div></section></div>'
      +'<div class="rules-ribbon"><div class="rule"><div class="rule-icon">'+icon('minus')+'</div><div><b>Blank means keep</b><small>Leave cells blank to keep current values.</small></div></div><div class="rule"><div class="rule-icon">'+icon('check')+'</div><div><b>Zero means update</b><small>Enter 0 to set an amount to zero.</small></div></div><div class="rule"><div class="rule-icon">'+icon('eye')+'</div><div><b>Review before applying</b><small>See exactly what will change.</small></div></div></div>'
      +'<section class="preview-section"><div class="section-heading"><h2>See what you’ll download</h2><div class="segment"><button class="'+(S.preview==='employee'?'active':'')+'" data-action="preview-employee">Employee records</button><button class="'+(S.preview==='monthly'?'active':'')+'" data-action="preview-monthly">Monthly pay inputs</button></div></div>'
      +(S.preview==='monthly'&&!hasData?newMonthNote():'')+workbookPreview(S.preview,false)+
      '<div class="below-note">'+icon(S.preview==='monthly'?'calendar':'lock')+(S.preview==='monthly'?'Fresh downloads use the selected month. Previous bonuses and deductions never carry forward.':'Employee ID and email remain fixed. Blank editable cells are ignored during import.')+'</div></section>';
  }
  function newMonthNote(){return '<div class="new-month-note">'+icon('calendar')+'<div><b>A fresh start for '+monthLabel()+'.</b> Standard days are suggested from the preview calendar. Paid days and one-off adjustments start blank; review attendance before payroll.</div></div>';}
  function workbookPreview(kind,draft){
    const ctx=context(kind,draft),tab=S.sheet,fields=W.sheetFields(ctx,kind==='employee'?'employee':tab);
    const filename='Rize_'+def().name+'_'+(kind==='employee'?'Employee_Records':S.period+'_Monthly_Inputs')+'.xlsx';
    return '<div class="card excel-card"><div class="excel-top"><div class="file-icon">'+icon('file')+'</div><div><div class="excel-name">'+esc(filename)+'</div><small>'+(kind==='employee'?'Latest saved employee and contract data':monthLabel()+' · '+(draft?'Layout preview':'Saved monthly inputs'))+'</small></div><span class="spacer"></span><span class="pill neutral">'+icon('eye')+'Workbook preview</span></div>'
      +'<div class="grid-wrap"><table class="preview-table"><thead><tr>'+fields.map(function(f){return '<th class="'+(f.type==='number'?'currency':'')+'">'+esc(f.label)+(f.locked?icon('lock'):'')+(f.unit?'<div class="small muted" style="font-size:9px;font-weight:500;margin-top:3px">'+esc(f.unit)+'</div>':'')+'</th>';}).join('')+'</tr></thead><tbody>'
      +model().records.map(function(r){return '<tr>'+fields.map(function(f){const v=kind==='employee'?r[f.key]:f.key==='id'||f.key==='name'?r[f.key]:W.monthValue(ctx,r,f);return '<td class="'+(f.locked?'readonly ':'')+(W.blank(v)?'blank':'num')+'">'+(W.blank(v)?'—':esc(display(v)))+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table></div>'
      +'<div class="sheet-tabs">'+(kind==='employee'?'<button class="active">Employee records</button>':['time','adjustments'].map(function(t){return '<button class="'+(S.sheet===t?'active':'')+'" data-action="sheet" data-sheet="'+t+'">'+(t==='time'?'Time':'Monthly adjustments')+'</button>';}).join(''))+'<span class="sheet-note">Employee ID stays first'+(kind==='monthly'?' on both tabs':'')+'</span></div></div>';
  }
  function fieldCard(key,where){
    const f=D.fields(S.country).find(function(v){return v.key===key;});
    const suggested=f.suggestion||f.kind,isTime=f.unit==='Days'||f.unit==='Hours';
    const reason=f.context?'Saved context · read-only':where==='available'?'Suggested for '+(suggested==='time'?'Time':'Monthly adjustments'):(where===suggested?'Suggested · ':'Custom placement · ')+(isTime?'Time quantity':'Monthly amount');
    return '<div class="field-card" draggable="true" data-field="'+key+'" data-lane="'+where+'" tabindex="0" title="'+esc(f.why)+'" aria-label="'+esc(f.label)+', '+(where==='adjustments'?'Monthly adjustments':where)+'"><span class="grip">'+icon('grip')+'</span><div class="field-text"><strong>'+esc(f.label)+'</strong><small>'+esc(reason)+'</small></div><span class="unit">'+esc(f.unit)+'</span><button class="button icon" data-action="field-menu" data-key="'+key+'" aria-label="Move '+esc(f.label)+'">'+icon('more')+'</button>'
      +(S.fieldMenu===key?'<div class="field-menu" role="menu">'+['time','adjustments','available'].filter(function(t){return t!==where;}).map(function(t){return '<button data-action="move-field" data-key="'+key+'" data-to="'+t+'">'+icon(t==='available'?'minus':t==='time'?'clock':'table')+(t==='available'?'Remove from workbook':'Move to '+(t==='time'?'Time':'Monthly adjustments'))+'</button>';}).join('')+'<button data-action="field-up" data-key="'+key+'">'+icon('back')+'Move earlier</button><button data-action="field-down" data-key="'+key+'">'+icon('arrow')+'Move later</button></div>':'')+'</div>';
  }
  function layoutView(){
    const draft=S.draft;
    return '<div class="layout-top"><div><h2>A workbook that fits your payroll</h2><p>Drag fields between tabs, or use each field’s menu. Arrange them in the order your team works.</p></div><div class="layout-actions">'+(dirty()?'<span class="pill amber">Unsaved changes</span>':'<span class="pill green">'+icon('check')+'Layout saved</span>')+button(icon('eye')+'Preview','layout-preview','')+button(icon('save')+'Save layout','save-layout','primary',dirty()?'':'disabled')+'</div></div>'
      +'<div class="layout-board"><aside class="palette" data-drop="available"><h3>Available fields <span class="muted">· '+draft.available.length+'</span></h3><p>Add extra inputs or saved context to your workbook. Time and money fields start in their suggested tabs.</p><label class="search">'+icon('search')+'<input aria-label="Find a field" placeholder="Find a field…" value="'+esc(S.search)+'" data-control="field-search"></label><div class="palette-fields">'+draft.available.filter(function(k){return D.fields(S.country).find(function(f){return f.key===k;}).label.toLowerCase().includes(S.search.toLowerCase());}).map(function(k){return fieldCard(k,'available');}).join('')+(draft.available.length?'':'<div class="small muted">All fields are in the workbook.</div>')+'</div></aside>'
      +['time','adjustments'].map(function(t,i){return '<section class="lane" data-drop="'+t+'"><div class="lane-heading"><div class="row"><span class="tab-number">'+(i+1)+'</span><div><h3>'+(t==='time'?'Time':'Monthly adjustments')+'</h3><small>'+(t==='time'?'Days, hours and time quantities':'Amounts paid or deducted this month')+'</small></div></div><span class="count">'+draft[t].length+' fields</span></div><div class="lane-body"><div class="identity-lock">'+icon('lock')+'<div><b>Employee ID + employee name</b><br>Always included · Same identity on both tabs</div></div>'+draft[t].map(function(k){return fieldCard(k,t);}).join('')+(draft[t].length?'':'<div class="empty-lane">Drop fields here to include them in this tab.</div>')+'</div><div class="lane-footer">'+icon('minus')+' Blank cells keep this month’s saved values.</div></section>';}).join('')+'</div>'
      +'<div class="layout-explainer">'+icon('info')+'<span>Moving a field changes its worksheet and position. Its payroll calculation stays the same. Saved salary and fixed allowances belong in the employee workbook; optional context columns here are read-only.</span></div>'
      +'<div class="layout-preview-title"><h3>Live workbook preview</h3><span class="pill neutral">'+(dirty()?'Draft layout':'Saved layout')+'</span></div>'+workbookPreview('monthly',true)
      +'<div class="below-note">'+icon('layers')+'This layout is saved for '+esc(def().scheme)+'. Both monthly tabs keep their employee relationship.</div>';
  }
  function configurations(){
    return '<div class="intro" style="margin-bottom:24px"><div><div class="eyebrow">Settings</div><h1>Payroll configurations</h1><p>Open a configuration’s templates to update records or prepare a monthly workbook.</p></div><span class="pill neutral">Preview entry point</span></div><div class="configuration-cards">'+Object.keys(D.definitions).map(function(c){const d=D.definitions[c];return '<section class="card configuration-card"><div class="row between"><div class="flag">'+c+'</div><span class="pill green">Active</span></div><h2>'+esc(d.scheme)+'</h2><p>'+d.name+' · '+d.currency+' · Monthly</p><div class="configuration-detail">'+icon('layers')+'Employee records & monthly pay inputs</div><div class="row between">'+button(icon('file')+'Templates','choose-config','primary','data-country="'+c+'"')+button('Monthly layout '+icon('chevron'),'choose-layout','text','data-country="'+c+'"')+'</div></section>';}).join('')+'</div><div class="below-note" style="margin-top:20px">'+icon('info')+'The Templates action sits on each configuration card. Pay Run links to the same month’s download.</div>';
  }
  function historyView(){
    const items=model().history;
    return '<section class="card history-card"><div class="row between"><div><h2>Changes with a clear trail</h2><p class="small muted" style="margin-top:5px">Employee record updates and monthly inputs have separate destinations.</p></div><span class="pill neutral">'+items.length+' imports</span></div>'
      +(items.length?items.slice().reverse().map(function(item){return '<div class="history-row"><div class="icon-box '+(item.kind==='monthly'?'teal':'')+'">'+icon(item.kind==='monthly'?'calendar':'users')+'</div><div><b>'+item.count+' '+(item.count===1?'change':'changes')+' '+(item.kind==='monthly'?'saved to '+item.period:'saved to employee records')+'</b><p>'+esc(item.filename)+' · '+item.when+' · Preview user</p></div><span class="spacer"></span><span class="pill green">'+icon('check')+'Applied</span></div>';}).join(''):'<div class="history-empty">'+icon('history')+'<h2>Your next import starts the trail</h2><p class="small">Try an example import to see the review and receipt.</p>'+button('Try an employee change','import-employee','soft','style="margin-top:17px"')+'</div>')+'</section>';
  }
  function payrun(){
    return '<section class="card payrun-card" style="margin-top:27px"><div class="flow-steps"><div class="flow-step">'+icon('check')+'Select period</div><div class="flow-line"></div><div class="flow-step active"><i>2</i>Pay data</div><div class="flow-line"></div><div class="flow-step"><i>3</i>Compute</div><div class="flow-line"></div><div class="flow-step"><i>4</i>Review</div></div><div class="payrun-content"><div class="payrun-summary"><div><h2>'+monthLabel()+'</h2><p>'+esc(def().scheme)+' · '+model().records.length+' employees · '+def().currency+'</p></div>'+monthSelect()+'</div>'
      +'<div class="payrun-context">'+icon('layers')+'<span><b>One workbook. Two connected tabs.</b><br>Time + Monthly adjustments · Employee ID links each person’s inputs.</span><span class="spacer"></span><span class="pill neutral">'+icon('shield')+'This month only</span></div>'
      +(!model().periods[S.period]?newMonthNote():'')
      +'<div class="upload-zone" tabindex="0" role="button" aria-label="Choose monthly pay workbook" data-action="pick-monthly" data-drop-file="monthly"><div class="upload-symbol">'+icon('upload')+'</div><strong>Drop this month’s workbook here</strong><p>or click to choose · .xlsx · Time and Monthly adjustments</p></div>'
      +'<div class="row between" style="margin-top:16px"><span class="small muted">Need the latest copy for this month?</span>'+button(icon('download')+'Download '+monthLabel(),'download-monthly','soft')+'</div>'
      +'<div class="demo-examples"><span>Try the review:</span>'+button('Days & a payment set to 0','example-monthly','')+button('Wrong pay month','example-month-wrong','')+'</div>'
      +'<div class="below-note" style="margin-top:18px">'+icon('lock')+'Monthly imports update this pay month’s inputs. Employee and contract records are not changed.</div></div>'
      +'<div class="dialog-footer"><div class="small muted">Every supplied change is reviewed before it enters the run.</div>'+button('Back to templates','page','','data-page="downloads"')+'</div></section>';
  }
  function render(){
    const content=S.page==='layout'?layoutView():S.page==='history'?historyView():S.page==='configurations'?configurations():S.page==='payrun'?payrun():downloads();
    root.innerHTML=shell(content);
  }
  function modalFrame(title,sub,body,footer,wide,eyebrow){
    return '<div class="overlay-scrim" data-action="close-modal"></div><section class="dialog '+(wide?'wide':'')+'" role="dialog" aria-modal="true" aria-labelledby="dialog-title" tabindex="-1"><header class="dialog-header"><div><div class="eyebrow">'+(eyebrow||def().name+' · '+(S.kind==='monthly'?monthLabel():'Employee records'))+'</div><h2 id="dialog-title">'+title+'</h2><p>'+sub+'</p></div><button class="close-button" aria-label="Close" data-action="close-modal">'+icon('close')+'</button></header><div class="dialog-body">'+body+'</div><footer class="dialog-footer">'+footer+'</footer></section>';
  }
  function uploadModal(){
    const monthly=S.kind==='monthly';
    return modalFrame(monthly?'Bring in this month’s inputs':'Import employee record changes',monthly?'Review changes to Time and Monthly adjustments before using them in '+monthLabel()+'.':'Start with the downloaded employee workbook. We’ll compare it with the current records.',
      '<div class="upload-zone" role="button" tabindex="0" aria-label="Choose '+(monthly?'monthly':'employee')+' workbook" data-action="pick-file" data-drop-file="'+S.kind+'"><div class="upload-symbol">'+icon('upload')+'</div><strong>'+(S.reading?'Reading your workbook…':'Drop your updated workbook here')+'</strong><p>or click to choose · .xlsx'+(monthly?' with both monthly tabs':' or .csv')+' · Up to 10 MB</p></div>'
      +'<div class="upload-guide"><div class="item">'+icon('minus')+'<div><strong>Only fill what you want to change</strong><p>Blank cells are ignored. Enter 0 to reset a number.</p></div></div><div class="item">'+icon('lock')+'<div><strong>Keep the employee identity intact</strong><p>'+(monthly?'Employee ID must appear on both tabs.':'Employee ID and email cannot be changed here.')+'</p></div></div></div>'
      +'<div class="demo-examples"><span>Try an example:</span>'+button(monthly?'Days & zero payment':'Salary & allowance reset','example-edits','')+button('Blank cells only','example-blanks','')+button(monthly?'Wrong month':'Edited Employee ID','example-invalid','')+(!monthly?button('A changed record','example-stale',''):'')+'</div>',
      '<span class="small muted">Nothing is saved before your review.</span>'+button('Cancel','close-modal',''),false);
  }
  function reviewModal(){
    const r=S.result,count=r.changes.filter(function(c){return c.selected;}).length,monthly=S.kind==='monthly';
    const issues=r.issues.map(function(issue,i){return '<div class="issue">'+icon('alert')+'<div style="flex:1"><strong>'+esc(issue.title)+'</strong><p>'+esc(issue.detail)+'</p>'+(issue.key?'<div class="row" style="margin-top:9px;flex-wrap:wrap"><span class="small">Current: <b>'+esc(display(issue.before))+'</b> · Workbook: <b>'+esc(display(issue.incoming))+'</b></span>'+button('Keep current','resolve-current','sm','data-index="'+i+'"')+button('Use workbook value','resolve-incoming','soft sm','data-index="'+i+'"')+'</div>':'')+'</div></div>';}).join('');
    const changes=r.changes.length?'<div class="grid-wrap"><table class="review-table"><thead><tr><th style="width:25px"><input aria-label="Select all changes" type="checkbox" data-control="select-all" '+(count===r.changes.length?'checked':'')+'></th><th>Employee</th><th>Field</th><th>Current '+(monthly?'month':'record')+'</th><th></th><th>Will become</th></tr></thead><tbody>'+r.changes.map(function(c,i){return '<tr><td><input aria-label="Apply '+esc(c.label)+' for '+esc(c.name)+'" type="checkbox" data-control="select-change" data-index="'+i+'" '+(c.selected?'checked':'')+'></td><td><div class="person-name">'+esc(c.name)+'</div><div class="person-code">'+c.id+'</div></td><td>'+esc(c.label)+'<div class="person-code">'+(monthly?esc(c.tab):'Saved employee record')+'</div></td><td class="before num">'+esc(display(c.before))+'</td><td style="color:#a8a1c1">'+icon('arrow')+'</td><td class="after num">'+esc(display(c.after))+(c.after===0?'<span class="zero-marker">Set to 0</span>':'')+'</td></tr>';}).join('')+'</tbody></table></div>':r.issues.length?'':'<div class="history-empty" style="padding:23px 15px"><div class="success-symbol" style="width:44px;height:44px;margin-bottom:12px">'+icon('check')+'</div><h2>No changes to save</h2><p class="small">All supplied values already match, or were left blank. Existing values are kept.</p></div>';
    return modalFrame('Here’s what will change',monthly?'These updates belong to '+monthLabel()+'. Your employee records stay separate.':'Confirm the selected changes before they are saved to employee and contract records.',
      '<div class="review-banner"><div class="icon-box">'+icon(monthly?'calendar':'users')+'</div><div><strong>'+esc(r.filename)+'</strong><p>'+r.people+' '+(r.people===1?'employee':'employees')+' with changes · '+(monthly?monthLabel():'Compared with current saved records')+'</p></div><span class="spacer"></span><span class="pill '+(r.issues.length?'rose':'green')+'">'+(r.issues.length?r.issues.length+' need attention':icon('check')+'Ready to confirm')+'</span></div>'
      +'<div class="review-stats"><span class="review-stat"><b>'+r.changes.length+'</b> changes</span><span class="review-stat"><b>'+r.blanks+'</b> blanks ignored</span><span class="review-stat"><b>'+r.unchanged+'</b> unchanged values</span><span class="review-stat"><b>'+r.issues.length+'</b> issues</span></div>'+issues+changes
      +'<details class="ignored-detail"><summary>'+r.blanks+' blank cells will be ignored '+icon('down')+'</summary><p>'+(monthly?'Blank cells keep inputs already saved for this selected month. They never reuse a previous month’s bonus or deduction.':'Blank cells never erase saved records. You can leave all editable cells blank except the values you want to change.')+' Explicit 0 values are reviewed and saved. Employee ID must remain populated.</p></details>'
      +(r.warnings.length?'<div class="below-note">'+icon('info')+esc(r.warnings.join(' · '))+'</div>':''),
      '<span class="small muted">'+(r.issues.length?'Resolve the issues before applying any changes.':count?'Only these '+count+' selected changes will be saved.':'No values will be updated.')+'</span><div class="row">'+button('Back','back-upload','')+button(icon('check')+(monthly?'Use ':'Apply ')+count+' '+(count===1?'change':'changes'),'apply','primary',count&&!r.issues.length?'':'disabled')+'</div>',true);
  }
  function successModal(){
    const s=S.success,monthly=s.kind==='monthly';
    return modalFrame('', '', '<div class="success-body"><div class="success-symbol">'+icon('check')+'</div><h2>'+s.count+' '+(s.count===1?'change':'changes')+' '+(monthly?'ready for '+monthLabel():'saved')+'</h2><p>'+(monthly?'The selected inputs are saved in this preview’s pay month. Download again to see the latest monthly values.':'Your employee and contract workbook now reflects the confirmed changes. Download it again to see the updated records.')+'</p><div class="receipt">'+icon('shield')+s.people+' '+(s.people===1?'employee':'employees')+' · '+s.blanks+' blank cells ignored · Identity unchanged</div></div>',
      '<span class="small muted">Sample data updated in this preview only.</span><div class="row">'+button('View history','show-history','')+button(monthly?'Continue Pay Run':'Done',monthly?'continue-run':'close-modal','primary')+'</div>',false,'Import complete');
  }
  function missingTime(){
    const ctx=context('monthly');
    return ctx.records.map(function(r){const paid=W.monthValue(ctx,r,{key:'paidDays'}),standard=W.monthValue(ctx,r,{key:'standardDays'});const fields=[];if(W.blank(paid))fields.push('Paid days');if(!(Number(standard)>0))fields.push('Standard working days');return {record:r,fields:fields};}).filter(function(r){return r.fields.length;});
  }
  function coverageModal(){
    const rows=missingTime();
    return modalFrame('Complete the time inputs first',rows.length+' '+(rows.length===1?'employee needs':'employees need')+' attendance inputs before this month can be computed.',
      rows.map(function(item){return '<div class="issue">'+icon('calendar')+'<div><strong>'+esc(item.record.name)+' · '+item.record.id+'</strong><p>Provide '+esc(item.fields.join(' and '))+'. Download the latest workbook, complete the missing inputs and reimport it.</p></div></div>';}).join(''),
      '<span class="small muted">Calendar suggestions do not confirm attendance.</span><div class="row">'+button('Back to Pay Run','return-payrun','')+button(icon('download')+'Download updated month','download-monthly','primary')+'</div>',false,'Pay Run · '+monthLabel());
  }
  function renderOverlay(focus){
    root.inert=!!S.modal;
    if(!S.modal){overlay.innerHTML='';document.body.style.overflow='';return;}
    document.body.style.overflow='hidden';
    overlay.innerHTML=S.modal==='upload'?uploadModal():S.modal==='review'?reviewModal():S.modal==='success'?successModal():S.modal==='coverage'?coverageModal():S.modal==='layout-preview'?modalFrame('Your monthly workbook','This preview updates as you move columns. Save the layout before downloading.',workbookPreview('monthly',true),'<span class="small muted">Employee ID is fixed on both worksheets.</span>'+button('Close preview','close-modal','primary'),true,'Live preview'):modalFrame('Ready to compute','This is the end of the input workflow preview.','<div class="success-body"><div class="success-symbol">'+icon('check')+'</div><h2>Your monthly inputs are ready</h2><p>In the application, this continues to payroll computation and the usual checks and approval workflow.</p></div>','<span class="small muted">No payslips or payroll payments are created by this preview.</span>'+button('Back to templates','finish-run','primary'),false,'Pay Run · '+monthLabel());
    if(focus)overlay.querySelector('.dialog').focus();
  }
  function openModal(kind,modal,fromRun){S.lastFocus=document.activeElement;S.kind=kind;S.fromRun=!!fromRun;S.modal=modal||'upload';S.fieldMenu=null;renderOverlay(true);}
  function closeModal(){S.modal=null;S.reading=false;S.readToken++;renderOverlay();if(S.lastFocus&&S.lastFocus.isConnected)S.lastFocus.focus();}
  function setCountry(c){if(!D.definitions[c])return;S.drafts[S.country]=clone(S.draft);S.country=c;S.draft=clone(S.drafts[c]||S.layouts[c].layout);S.search='';S.fieldMenu=null;S.sheet='time';render();}
  function moveField(key,to,at){
    const from=['time','adjustments','available'].find(function(t){return S.draft[t].includes(key);});if(!from)return;
    S.draft[from]=S.draft[from].filter(function(k){return k!==key;});
    const list=S.draft[to],idx=at&&list.indexOf(at)>=0?list.indexOf(at):list.length;list.splice(idx,0,key);S.fieldMenu=null;render();
    const f=D.fields(S.country).find(function(v){return v.key===key;});toast(f.label+' '+(to==='available'?'removed from the workbook':'moved to '+(to==='time'?'Time':'Monthly adjustments')));
  }
  function saveLayout(){
    const defs=D.fields(S.country),count=S.draft.time.concat(S.draft.adjustments).filter(function(k){return !defs.find(function(f){return f.key===k;}).context;}).length;
    if(!count){toast('Add at least one monthly input before saving.');return;}
    if(!dirty())return;
    S.layouts[S.country]={layout:clone(S.draft),version:S.layouts[S.country].version+1};
    S.drafts[S.country]=clone(S.draft);
    try{localStorage.setItem('pb_payroll_template_poc.layout.'+S.country,JSON.stringify(S.layouts[S.country]));}catch(ignore){}
    render();toast('Monthly layout saved for '+def().name+'. Your next download uses this layout.');
  }
  function download(kind){
    try{
      const bytes=W.build(context(kind)),name='Rize_'+def().name+'_'+(kind==='employee'?'Employee_Records':S.period+'_Monthly_Inputs')+'.xlsx';
      const url=URL.createObjectURL(new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})),a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(url);},30000);
      toast((kind==='employee'?'Latest employee records':monthLabel()+' inputs')+' downloaded. Example data only.');
    }catch(e){toast('The workbook could not be created: '+e.message);}
  }
  function startReview(file){
    S.pending=file;S.resolutions={};S.result=W.review(file,context(),S.resolutions);S.reading=false;S.modal='review';renderOverlay(true);
  }
  async function takeFile(file,kind,fromRun){
    if(!file)return;if(file.size>10*1024*1024){toast('Choose a workbook smaller than 10 MB.');return;}
    if(!/\.(xlsx|xls|csv)$/i.test(file.name)){toast('Choose an Excel workbook or an employee CSV.');return;}
    if(kind==='monthly'&&/\.csv$/i.test(file.name)){toast('Monthly inputs need an .xlsx workbook with both tabs.');return;}
    if(!S.modal)openModal(kind,'upload',fromRun);
    S.kind=kind;S.reading=true;renderOverlay();const token=++S.readToken;
    try{const bytes=new Uint8Array(await file.arrayBuffer());if(token!==S.readToken)return;const parsed=W.parse(bytes,file.name);startReview(parsed);}
    catch(e){if(token!==S.readToken)return;S.reading=false;S.modal='upload';renderOverlay();toast('This file could not be read. Choose a valid Excel workbook.');}
    fileInput.value='';
  }
  function example(kind,scenario){
    S.kind=kind;if(!S.modal)S.lastFocus=document.activeElement;
    const ctx=context(kind),edits={},fields=kind==='employee'?D.masterFields:D.fields(S.country);
    function add(key,row,value){const tab=kind==='employee'?'Employee records':ctx.layout.time.includes(key)?'Time':ctx.layout.adjustments.includes(key)?'Monthly adjustments':null;if(tab)(edits[tab]||(edits[tab]=[])).push({key:key,row:row,value:value});}
    if(scenario==='blanks'){fields.filter(function(f){return !f.locked&&!f.context;}).forEach(function(f){for(let i=0;i<ctx.records.length;i++)add(f.key,i,'');});}
    else if(kind==='employee'){add('salary',0,Math.round(ctx.records[0].salary*1.05));add('phone',1,0);add('department',0,'');if(scenario==='invalid')add('id',0,'EDITED-ID');}
    else{add('paidDays',0,20);add('bonus',0,0);add('reimbursement',1,Math.max(100,Math.round(def().salary[0]*.01)));add('deduction',2,0);}
    try{
      const payload=W.parse(W.build(ctx,edits),'Example_'+def().name+'_'+(kind==='employee'?'Employee_Changes':'Monthly_Inputs')+'.xlsx');
      if(scenario==='wrong')payload.meta['Pay month']='2026-09';
      if(scenario==='stale')model().records[0].salary+=Math.max(500,Math.round(model().records[0].salary*.01));
      startReview(payload);
    }catch(e){toast('Example could not be prepared: '+e.message);}
  }
  function applyChanges(){
    const checked=new Set(S.result.changes.filter(function(c){return c.selected;}).map(function(c){return c.id+'|'+c.key;}));
    const fresh=W.review(S.pending,context(),S.resolutions);
    fresh.changes.forEach(function(c){const shown=S.result.changes.find(function(old){return old.id===c.id&&old.key===c.key;});if(checked.has(c.id+'|'+c.key)&&shown&&!W.same(shown.before,c.before))fresh.issues.push({title:'This value changed during your review',detail:c.name+' · '+c.label+'. Review the latest value before applying.',key:c.id+'|'+c.key,before:c.before,incoming:c.after});});
    if(fresh.issues.length){S.result=fresh;renderOverlay();toast('The latest values need another review.');return;}
    const selected=fresh.changes.filter(function(c){return checked.has(c.id+'|'+c.key);});
    if(!selected.length){S.result=fresh;renderOverlay();toast('The supplied values already match the latest records.');return;}
    const people=new Set();
    selected.forEach(function(c){
      people.add(c.id);
      if(S.kind==='employee')model().records.find(function(r){return r.id===c.id;})[c.key]=c.after;
      else{const period=model().periods[S.period]||(model().periods[S.period]={}),person=period[c.id]||(period[c.id]={});person[c.key]=c.after;}
    });
    S.success={kind:S.kind,count:selected.length,people:people.size,blanks:fresh.blanks};
    model().history.push({kind:S.kind,count:selected.length,period:monthLabel(),filename:S.pending.filename,when:'Just now'});
    S.modal='success';S.preview=S.kind==='employee'?'employee':'monthly';render();renderOverlay(true);
  }
  function resolveIssue(index,choice){
    const issue=S.result.issues[index];if(!issue||!issue.key)return;
    const selections=new Map(S.result.changes.map(function(c){return [c.id+'|'+c.key,c.selected];}));
    S.resolutions[issue.key]=choice;S.result=W.review(S.pending,context(),S.resolutions);
    S.result.changes.forEach(function(c){if(selections.has(c.id+'|'+c.key))c.selected=selections.get(c.id+'|'+c.key);});renderOverlay();
  }
  function onClick(event){
    const el=event.target.closest('[data-action]');if(!el)return;const a=el.dataset.action;
    if(a==='page'){S.page=el.dataset.page;S.fieldMenu=null;render();window.scrollTo(0,0);}
    else if(a==='choose-config'||a==='choose-layout'){S.page=a==='choose-layout'?'layout':'downloads';setCountry(el.dataset.country);}
    else if(a==='employee-workbook'){S.page='downloads';S.preview='employee';render();}
    else if(a==='preview-employee'||a==='preview-monthly'){S.preview=a==='preview-employee'?'employee':'monthly';render();root.querySelector('.preview-section').scrollIntoView({behavior:'smooth',block:'start'});}
    else if(a==='sheet'){S.sheet=el.dataset.sheet;if(S.modal)renderOverlay();else render();}
    else if(a==='download-employee'||a==='download-monthly')download(a==='download-employee'?'employee':'monthly');
    else if(a==='import-employee')openModal('employee');
    else if(a==='pick-monthly'){openModal('monthly','upload',true);fileInput.click();}
    else if(a==='pick-file'){if(!S.reading)fileInput.click();}
    else if(a==='field-menu'){S.fieldMenu=S.fieldMenu===el.dataset.key?null:el.dataset.key;render();}
    else if(a==='move-field')moveField(el.dataset.key,el.dataset.to);
    else if(a==='field-up'||a==='field-down'){
      const key=el.dataset.key,t=['time','adjustments','available'].find(function(t){return S.draft[t].includes(key);}),list=S.draft[t],i=list.indexOf(key),target=i+(a==='field-up'?-1:1);
      if(target>=0&&target<list.length){list.splice(i,1);list.splice(target,0,key);}S.fieldMenu=null;render();
    }
    else if(a==='save-layout')saveLayout();
    else if(a==='layout-preview'){S.lastFocus=document.activeElement;S.modal='layout-preview';renderOverlay(true);}
    else if(a==='close-modal')closeModal();
    else if(a==='back-upload'){S.modal='upload';S.result=null;renderOverlay(true);}
    else if(a==='example-edits'||a==='example-blanks'||a==='example-invalid'||a==='example-stale')example(S.kind,a==='example-blanks'?'blanks':a==='example-invalid'?(S.kind==='monthly'?'wrong':'invalid'):a==='example-stale'?'stale':'edits');
    else if(a==='example-monthly'||a==='example-month-wrong'){S.fromRun=true;example('monthly',a==='example-month-wrong'?'wrong':'edits');}
    else if(a==='resolve-current'||a==='resolve-incoming')resolveIssue(Number(el.dataset.index),a==='resolve-current'?'current':'incoming');
    else if(a==='apply')applyChanges();
    else if(a==='show-history'){closeModal();S.page='history';render();}
    else if(a==='continue-run'){S.modal=missingTime().length?'coverage':'computed';renderOverlay(true);}
    else if(a==='return-payrun'){closeModal();S.page='payrun';render();}
    else if(a==='finish-run'){closeModal();S.page='downloads';render();}
    else if(a==='reset'){S.models[S.country]=D.seed(S.country);closeModal();render();toast('Sample records and monthly inputs reset. Your saved layout is kept.');}
  }
  document.addEventListener('click',onClick);
  document.addEventListener('change',function(e){
    const control=e.target.dataset.control;
    if(control==='country')setCountry(e.target.value);
    else if(control==='period'){S.period=e.target.value;render();}
    else if(control==='select-change'){S.result.changes[Number(e.target.dataset.index)].selected=e.target.checked;renderOverlay();}
    else if(control==='select-all'){S.result.changes.forEach(function(c){c.selected=e.target.checked;});renderOverlay();}
  });
  document.addEventListener('input',function(e){if(e.target.dataset.control==='field-search'){const start=e.target.selectionStart;S.search=e.target.value;render();const input=root.querySelector('[data-control="field-search"]');input.focus();input.setSelectionRange(start,start);}});
  fileInput.addEventListener('change',function(){takeFile(fileInput.files[0],S.kind,S.fromRun);});
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'){if(S.modal)closeModal();else if(S.fieldMenu){S.fieldMenu=null;render();}return;}
    if((e.key==='Enter'||e.key===' ')&&e.target.matches('.upload-zone')){e.preventDefault();e.target.click();}
    if(e.key==='Tab'&&S.modal){const nodes=[...overlay.querySelectorAll('button:not(:disabled),input:not(:disabled),select,summary,[tabindex="0"]')].filter(function(n){return n.offsetParent!==null;});if(!nodes.length)return;const i=nodes.indexOf(document.activeElement);if(e.shiftKey&&(i<=0)){e.preventDefault();nodes[nodes.length-1].focus();}else if(!e.shiftKey&&(i<0||i===nodes.length-1)){e.preventDefault();nodes[0].focus();}}
  });
  document.addEventListener('dragstart',function(e){const card=e.target.closest('.field-card');if(!card)return;S.dragKey=card.dataset.field;e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',S.dragKey);card.classList.add('dragging');});
  document.addEventListener('dragend',function(){S.dragKey=null;document.querySelectorAll('.dragging,.drag-over').forEach(function(e){e.classList.remove('dragging','drag-over');});});
  document.addEventListener('dragover',function(e){const fileZone=e.target.closest('[data-drop-file]'),lane=e.target.closest('[data-drop]');if(fileZone||lane&&S.dragKey){e.preventDefault();if(lane)lane.classList.add('drag-over');if(fileZone)fileZone.classList.add('over');}else if(e.dataTransfer&&[...e.dataTransfer.types].includes('Files'))e.preventDefault();});
  document.addEventListener('dragleave',function(e){const lane=e.target.closest('[data-drop]'),zone=e.target.closest('[data-drop-file]');if(lane&&!lane.contains(e.relatedTarget))lane.classList.remove('drag-over');if(zone&&!zone.contains(e.relatedTarget))zone.classList.remove('over');});
  document.addEventListener('drop',function(e){
    e.preventDefault();const zone=e.target.closest('[data-drop-file]');
    if(zone&&e.dataTransfer.files.length){takeFile(e.dataTransfer.files[0],zone.dataset.dropFile,S.page==='payrun');return;}
    const lane=e.target.closest('[data-drop]');if(!lane||!S.dragKey)return;const card=e.target.closest('.field-card'),key=S.dragKey;S.dragKey=null;moveField(key,lane.dataset.drop,card&&card.dataset.field!==key?card.dataset.field:null);
  });
  render();
})();
