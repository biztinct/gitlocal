'use strict';
/* WF2 P4b — where time goes (Activity tab), "The candidate" in "Who does
   this?" (D18), "If a task is late and there is no manager, tell…" in
   Settings (D19), and who was told about a late task in progress.
   Loaded last: it only adds, and wraps shipped functions by assignment
   (ledger G45). Plain DOM, no chart library; one hue (brand indigo tints)
   and the shipped late colour only for late. */

/* ------------------------------------------------------ where time goes */
function timeState(){
 if(!S.w)return null;
 if(!S.time||S.time.wid!==S.w.id)S.time={wid:S.w.id,period:'90',data:null,loading:false,error:'',filter:null};
 return S.time;
}
async function loadTime(period){
 const t=timeState();if(!t)return;
 if(period)t.period=period;
 t.loading=true;t.error='';
 try{t.data=await rpc('time_report',[S.w.id,t.period]);}
 catch(e){t.error=e.message||'This could not load.';t.data=null;}
 finally{t.loading=false;}
 if(S.page==='editor'&&S.tab==='runs')render();
}
const TIME_TINTS=['#5A4BB0','#7a6cc6','#9a8fd6','#b9b1e5','#d6d1f1','#8577cc','#a79de0'];
function timeBar(stages){
 const rows=stages.filter(s=>s.share>0);
 if(!rows.length)return '<p class="time-quiet">No time is counted in these stages yet.</p>';
 return `<div class="time-bar" role="img" aria-label="${esc(rows.map(s=>`${s.name} ${Math.round(s.share)}%`).join(', '))}">${rows.map((s,i)=>`<span class="time-seg" style="flex:${Math.max(s.share,1.5)} 1 0;background:${TIME_TINTS[i%TIME_TINTS.length]};color:${i%TIME_TINTS.length>=3&&i%TIME_TINTS.length<5?'#2f2569':'#fff'}" title="${esc(s.name)} · ${Math.round(s.share)}% of the time">${s.share>=9?`<b>${esc(s.name)}</b><small>${Math.round(s.share)}%</small>`:''}</span>`).join('')}</div>`;
}
function timeStageRows(stages,enough){
 return `<div class="time-table" role="table" aria-label="Time in each stage"><div class="time-row time-head" role="row"><span role="columnheader">Stage</span><span role="columnheader" class="num">Usually</span><span role="columnheader" class="num">Slow ones</span><span role="columnheader" class="num">Went through</span><span role="columnheader" class="num">Sitting now</span></div>${stages.map(s=>{
  const late=s.late_share!==null&&s.late_share!==undefined?`<small class="${s.late_share>0?'is-late':''}">${s.late_share}% past its ${esc(s.target_words)} target</small>`:'';
  const sit=s.sitting?btn('time-sitting',`${s.sitting}`,'', `small plain time-sit ${S.time?.filter===s.key?'on':''}`,`data-id="${esc(s.key)}" aria-label="Show the ${s.sitting} sitting in ${esc(s.name)}" aria-pressed="${S.time?.filter===s.key}"`):'<span class="time-zero">0</span>';
  return `<div class="time-row" role="row"><span role="cell" class="time-name"><b>${esc(s.name)}</b>${s.kind==='yours'?'<small>your stage</small>':''}${late}</span><span role="cell" class="num">${s.enough?esc(s.median_words):'<em>Not enough yet</em>'}</span><span role="cell" class="num">${s.enough?esc(s.p90_words):'—'}</span><span role="cell" class="num">${s.passed}</span><span role="cell" class="num">${sit}</span></div>`;}).join('')}</div><p class="time-fine">“Usually” is the middle time; “slow ones” is the time nine in ten stay under. Numbers show once ${enough} records have been through.</p>`;
}
function timeSteps(steps){
 if(!steps.length)return '<p class="time-quiet">No person or approval step has run in this period.</p>';
 return `<ol class="time-steps">${steps.map((s,i)=>`<li class="time-step"><span class="time-rank">${i+1}</span><div class="grow"><b>${esc(s.title)}</b><small>${s.approval?'Approval (managed in Approvals)':s.who?'Usually with '+esc(s.who):'Nobody yet'}${s.sent_back?` · sent back ${s.sent_back} time${s.sent_back===1?'':'s'}`:''}${s.passed_up?` · manager told ${s.passed_up} time${s.passed_up===1?'':'s'}`:''}${s.waiting?` · ${s.waiting} waiting now`:''}</small></div><span class="num time-typical">${s.enough?esc(s.median_words):'<em>Not enough yet</em>'}</span><span class="num time-late ${s.late_share?'is-late':''}">${s.late_share===null||s.late_share===undefined?'':s.late_share+'% late'}</span>${s.exists?btn('time-open-step','Open step','arrow','small plain',`data-id="${esc(s.key)}" aria-label="Open ${esc(s.title)} in Build"`):'<span class="time-gone">not in the draft</span>'}</li>`).join('')}</ol>`;
}
function timePanel(){
 const t=timeState();if(!t)return '';
 if(!t.data&&!t.loading&&!t.error){loadTime();}
 const periods=[['30','30 days'],['90','90 days'],['all','All']];
 const head=`<div class="time-head-row"><div><h3>${svgIcon('clock')} Where time goes</h3><p class="muted small">Working time on the company calendar. Your own steps and the record’s stages, side by side.</p></div><div class="segmented" role="group" aria-label="Period">${periods.map(([k,l])=>btn('time-period',l,'',t.period===k?'on':'',`data-id="${k}" aria-pressed="${t.period===k}"`)).join('')}</div></div>`;
 let body;
 if(t.loading&&!t.data)body='<div class="time-skeleton" aria-busy="true"><span></span><span></span><span></span></div>';
 else if(t.error)body=`<div class="banner warn">${esc(t.error)} ${btn('time-period','Try again','history','small',`data-id="${t.period}"`)}</div>`;
 else if(!t.data||t.data.empty)body='<p class="time-empty">Nothing has run yet. Publish and start this workflow to see where time goes.</p>';
 else{const d=t.data;
  body=`${d.counting_since?`<p class="time-since">${svgIcon('info')} Counting since ${esc(d.counting_since)}.</p>`:''}${!d.calendar?'<p class="time-since">No company working calendar is set, so this counts every hour of the day.</p>':''}<div class="time-summary"><span><b>${d.runs}</b> started in this period</span><span><b>${d.records}</b> records looked at</span><span><b>${d.sitting_total}</b> sitting in a stage now</span></div>${d.stages.length?timeBar(d.stages)+timeStageRows(d.stages,d.enough):''}<h4 class="time-sub">Slowest steps</h4>${timeSteps(d.steps||[])}`;}
 return `<section class="time-panel ${t.loading?'is-loading':''}" aria-labelledby="time-h"><span id="time-h" class="sr">Where time goes</span>${head}${body}</section>`;
}
const _p4bActivity=activity;
activity=function(embedded=false){
 if(!embedded||!S.w)return _p4bActivity(embedded);
 const t=timeState(),all=S.runs;
 const sitting=t?.filter&&t.data?.stages?.find(s=>s.key===t.filter);
 if(sitting)S.runs=all.filter(r=>(sitting.run_ids||[]).includes(r.id));
 let html;try{html=_p4bActivity(embedded);}finally{S.runs=all;}
 const chip=sitting?`<div class="time-filter">${svgIcon('flag')}<span>Showing the ${S.runs.filter(r=>(sitting.run_ids||[]).includes(r.id)).length} sitting in <b>${esc(sitting.name)}</b></span>${btn('time-sitting','Show all','close','small plain','data-id=""')}</div>`:'';
 const k=html.indexOf('</button></div>');
 return k>0?html.slice(0,k+15)+timePanel()+chip+html.slice(k+15):timePanel()+chip+html;
};

/* ------------------------------------------- "The candidate" (D18) */
function participants(){return S.w?.metadata?.participants||[];}
const _p4bOwnerControl=ownerControl;
ownerControl=function(path,owner,label,noRecord=false,allowTeam=false){
 let html=_p4bOwnerControl(path,owner,label,noRecord,allowTeam);
 const list=participants();
 if(!allowTeam||!list.length)return html;
 const extra=list.map(p=>`<option value="participant" ${owner?.kind==='participant'&&(owner.key===p.key||list.length===1)?'selected':''}>${esc(p.label)} (by email link)</option>`).join('');
 html=html.replace('</select>',extra+'</select>');
 if(owner?.kind==='participant'){
  if(list.length>1)html+=field('Who',selectEdit(path+'.key',list.map(p=>[p.key,p.label]),owner.key));
  html+=hint('They get a private link by email and answer on a simple page: no login, nothing else of the record. A link page cannot take files or record choices.','link');
 }
 return html;
};
document.addEventListener('change',e=>{
 const t=e.target;if(!t?.dataset||t.dataset.edit!=='owner.kind'||S.page!=='editor')return;
 const n=byId(S.w.definition,S.selected);if(!n?.owner)return;
 if(t.value==='participant'&&!n.owner.key){const list=participants();if(list.length)mutate(()=>{n.owner.key=list[0].key;});}
 else if(t.value!=='participant'&&n.owner.key!==undefined){mutate(()=>{delete n.owner.key;});}
});
const _p4bOwnerName=ownerName;
ownerName=function(n){if(n?.owner?.kind==='participant'){const p=participants().find(x=>x.key===n.owner.key);return p?p.label:'Someone this record names';}return _p4bOwnerName(n);};

/* --------------------------------------- late, no manager (D19) */
function lateRoleField(){
 const roles=S.w?.metadata?.late_roles||[],cur=S.w?.definition?.late_tell?.id||'';
 const rows=roles.map(r=>[r.id,r.team?`${r.name} (a team)`:r.name]);
 return field('If a task is late and there is no manager, tell…',`<select id="setting-late">${opts(rows,cur,'The person who published it')}</select>`,'Their manager is told first. This person or team is told when nobody manages them; otherwise the person who published the workflow is.');
}

/* ------------------------------------------------------------ verbs */
const _p4bAction=action;
action=async function(name,el){
 const id=el?.dataset?.id;
 if(name==='time-period'){const t=timeState();t.filter=null;await loadTime(id||t.period);return;}
 if(name==='time-sitting'){const t=timeState();t.filter=id&&t.filter!==id?id:null;render();return;}
 if(name==='time-open-step'){if(!byId(S.w.definition,id)){notify('This step is no longer in the draft.',true);return;}S.tab='build';S.selected=id;render();setTimeout(()=>$(`[data-act="node"][data-id="${CSS.escape(id)}"]`)?.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}),30);return;}
 if(name==='refresh-runs'&&S.page==='editor'){const t=timeState();if(t){t.data=null;t.filter=null;}}
 if(name==='settings'){
  const r=await _p4bAction(name,el);
  const actions=$('#dialog .actions');
  if(actions&&S.w&&!$('#setting-late'))actions.insertAdjacentHTML('beforebegin',`<div class="setting-late">${lateRoleField()}</div>`);
  return r;
 }
 if(name==='settings-save'&&S.w){
  const sel=$('#setting-late');
  if(sel){const v=Number(sel.value)||null;if(v)S.w.definition.late_tell={id:v};else delete S.w.definition.late_tell;}
 }
 return _p4bAction(name,el);
};

/* ----------------------------------------------- progress: who was told */
const _p4bPeopleProgress=peopleProgress;
peopleProgress=function(step){return _p4bPeopleProgress(step)+(step?.passed_up?`<p class="progress-chip">${svgIcon('bell')}${esc(step.passed_up)}</p>`:'');};
