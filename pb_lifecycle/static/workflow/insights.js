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
 catch(e){t.error=_t('Where time goes could not be worked out just now.');t.data=null;console.warn('time_report',e.message);}
 finally{t.loading=false;}
 if(S.page==='editor'&&S.tab==='runs')render();
}
const TIME_TINTS=['#5A4BB0','#7a6cc6','#9a8fd6','#b9b1e5','#d6d1f1','#8577cc','#a79de0'];
function timeBar(stages){
 const rows=stages.filter(s=>s.share>0);
 if(!rows.length)return '<p class="time-quiet">'+_t('No time is counted in these stages yet.')+'</p>';
 return `<div class="time-bar" role="img" aria-label="${esc(rows.map(s=>`${s.name} ${Math.round(s.share)}%`).join(', '))}">${rows.map((s,i)=>`<span class="time-seg" style="flex:${Math.max(s.share,1.5)} 1 0;background:${TIME_TINTS[i%TIME_TINTS.length]};color:${i%TIME_TINTS.length>=3&&i%TIME_TINTS.length<5?'#2f2569':'#fff'}" title="${esc(s.name)} · ${_t('%(n)s% of the time',{n:Math.round(s.share)})}">${s.share>=9?`<b>${esc(s.name)}</b><small>${Math.round(s.share)}%</small>`:''}</span>`).join('')}</div>`;
}
function timeStageRows(stages,enough){
 return `<div class="time-table" role="table" aria-label="${_t('Time in each stage')}"><div class="time-row time-head" role="row"><span role="columnheader">${_t('Stage')}</span><span role="columnheader" class="num">${_t('Usually')}</span><span role="columnheader" class="num">${_t('Slow ones')}</span><span role="columnheader" class="num">${_t('Went through')}</span><span role="columnheader" class="num">${_t('Sitting now')}</span></div>${stages.map(s=>{
  const late=s.late_share!==null&&s.late_share!==undefined?`<small class="${s.late_share>0?'is-late':''}">${_t('%(n)s% past its %(target)s target',{n:s.late_share,target:esc(s.target_words)})}</small>`:'';
  const sit=s.sitting?btn('time-sitting',`${s.sitting}`,'', `small plain time-sit ${S.time?.filter===s.key?'on':''}`,`data-id="${esc(s.key)}" aria-label="${_t('Show the %(n)s sitting in %(stage)s',{n:s.sitting,stage:esc(s.name)})}" aria-pressed="${S.time?.filter===s.key}"`):'<span class="time-zero">0</span>';
  return `<div class="time-row" role="row"><span role="cell" class="time-name"><b>${esc(s.name)}</b>${s.kind==='yours'?`<small>${_t('your stage')}</small>`:''}${late}</span><span role="cell" class="num">${s.enough?esc(s.median_words):`<em>${_t('Not enough yet')}</em>`}</span><span role="cell" class="num">${s.enough?esc(s.p90_words):'—'}</span><span role="cell" class="num">${s.passed}</span><span role="cell" class="num">${sit}</span></div>`;}).join('')}</div><p class="time-fine">${_t('“Usually” is the middle time; “slow ones” is the time nine in ten stay under. Numbers show once %(n)s records have been through.',{n:enough})}</p>`;
}
function timeSteps(steps){
 if(!steps.length)return '<p class="time-quiet">'+_t('No person or approval step has run in this period.')+'</p>';
 return `<ol class="time-steps">${steps.map((s,i)=>`<li class="time-step"><span class="time-rank">${i+1}</span><div class="grow"><b>${esc(s.title)}</b><small>${s.approval?_t('Approval (managed in Approvals)'):s.who?_t('Usually with %(who)s',{who:esc(s.who)}):_t('Nobody yet')}${s.sent_back?' · '+_t.n(s.sent_back,'sent back %(n)s time','sent back %(n)s times'):''}${s.passed_up?' · '+_t.n(s.passed_up,'manager told %(n)s time','manager told %(n)s times'):''}${s.waiting?' · '+_t('%(n)s waiting now',{n:s.waiting}):''}</small></div><span class="num time-typical">${s.enough?esc(s.median_words):`<em>${_t('Not enough yet')}</em>`}</span><span class="num time-late ${s.late_share?'is-late':''}">${s.late_share===null||s.late_share===undefined?'':_t('%(n)s% late',{n:s.late_share})}</span>${s.exists?btn('time-open-step',_t('Open step'),'arrow','small plain',`data-id="${esc(s.key)}" aria-label="${_t('Open %(step)s in Build',{step:esc(s.title)})}"`):`<span class="time-gone">${_t('not in the draft')}</span>`}</li>`).join('')}</ol>`;
}
function timePanel(){
 const t=timeState();if(!t)return '';
 if(!t.data&&!t.loading&&!t.error){loadTime();}
 const periods=[['30',_t('30 days')],['90',_t('90 days')],['all',_t('All')]];
 const head=`<div class="time-head-row"><div><h3>${svgIcon('clock')} ${_t('Where time goes')}</h3><p class="muted small">${_t('Working time on the company calendar. Your own steps and the record’s stages, side by side.')}</p></div><div class="segmented" role="group" aria-label="${_t('Period')}">${periods.map(([k,l])=>btn('time-period',l,'',t.period===k?'on':'',`data-id="${k}" aria-pressed="${t.period===k}"`)).join('')}</div></div>`;
 let body;
 if(t.loading&&!t.data)body='<div class="time-skeleton" aria-busy="true"><span></span><span></span><span></span></div>';
 else if(t.error)body=`<div class="banner warn">${esc(t.error)} ${btn('time-period',_t('Try again'),'history','small',`data-id="${t.period}"`)}</div>`;
 else if(!t.data||t.data.empty)body='<p class="time-empty">'+_t('Nothing has run yet. Publish and start this workflow to see where time goes.')+'</p>';
 else{const d=t.data;
  body=`${d.counting_since?`<p class="time-since">${svgIcon('info')} ${_t('Counting since %(day)s.',{day:esc(d.counting_since)})}</p>`:''}${!d.calendar?`<p class="time-since">${_t('No company working calendar is set, so this counts every hour of the day.')}</p>`:''}<div class="time-summary"><span>${_t('%(n)s started in this period',{n:`<b>${d.runs}</b>`})}</span><span>${_t('%(n)s records looked at',{n:`<b>${d.records}</b>`})}</span><span>${_t('%(n)s sitting in a stage now',{n:`<b>${d.sitting_total}</b>`})}</span></div>${d.stages.length?timeBar(d.stages)+timeStageRows(d.stages,d.enough):''}<h4 class="time-sub">${_t('Slowest steps')}</h4>${timeSteps(d.steps||[])}`;}
 return `<section class="time-panel ${t.loading?'is-loading':''}" aria-labelledby="time-h"><span id="time-h" class="sr">${_t('Where time goes')}</span>${head}${body}</section>`;
}
const _p4bActivity=activity;
activity=function(embedded=false){
 if(!embedded||!S.w)return _p4bActivity(embedded);
 const t=timeState(),all=S.runs;
 const sitting=t?.filter&&t.data?.stages?.find(s=>s.key===t.filter);
 if(sitting)S.runs=all.filter(r=>(sitting.run_ids||[]).includes(r.id));
 let html;try{html=_p4bActivity(embedded);}finally{S.runs=all;}
 const chip=sitting?`<div class="time-filter">${svgIcon('flag')}<span>${_t('Showing the %(n)s sitting in %(stage)s',{n:S.runs.filter(r=>(sitting.run_ids||[]).includes(r.id)).length,stage:`<b>${esc(sitting.name)}</b>`})}</span>${btn('time-sitting',_t('Show all'),'close','small plain','data-id=""')}</div>`:'';
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
 const extra=list.map(p=>`<option value="participant" ${owner?.kind==='participant'&&(owner.key===p.key||list.length===1)?'selected':''}>${_t('%(who)s (by email link)',{who:esc(p.label)})}</option>`).join('');
 html=html.replace('</select>',extra+'</select>');
 if(owner?.kind==='participant'){
  if(list.length>1)html+=field(_t('Who'),selectEdit(path+'.key',list.map(p=>[p.key,p.label]),owner.key));
  html+=hint(_t('They get a private link by email and answer on a simple page: no login, nothing else of the record. A link page cannot take files or record choices.'),'link');
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
ownerName=function(n){if(n?.owner?.kind==='participant'){const p=participants().find(x=>x.key===n.owner.key);return p?p.label:_t('Someone this record names');}return _p4bOwnerName(n);};

/* --------------------------------------- late, no manager (D19) */
function lateRoleField(){
 const roles=S.w?.metadata?.late_roles||[],cur=S.w?.definition?.late_tell?.id||'';
 const rows=roles.map(r=>[r.id,r.team?_t('%(name)s (a team)',{name:r.name}):r.name]);
 return field(_t('If a task is late and there is no manager, tell…'),`<select id="setting-late">${opts(rows,cur,_t('The person who published it'))}</select>`,_t('Their manager is told first. This person or team is told when nobody manages them; otherwise the person who published the workflow is.'));
}

/* ------------------------------------------------------------ verbs */
const _p4bAction=action;
action=async function(name,el){
 const id=el?.dataset?.id;
 if(name==='time-period'){const t=timeState();t.filter=null;await loadTime(id||t.period);return;}
 if(name==='time-sitting'){const t=timeState();t.filter=id&&t.filter!==id?id:null;render();return;}
 if(name==='time-open-step'){if(!byId(S.w.definition,id)){notify(_t('This step is no longer in the draft.'),true);return;}S.tab='build';S.selected=id;render();setTimeout(()=>$(`[data-act="node"][data-id="${CSS.escape(id)}"]`)?.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}),30);return;}
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
