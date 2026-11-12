'use strict';
/* WF2 P5a — "Start on a schedule".
   A third way to start (beside "someone starts it" and "something happens
   to a record"): every day / week / month / year, once, at a time, on
   working days only if wanted; for a new process or for each matching
   record. The "Next 5 starts" list and "Would start for 12 records today"
   come from the server, computed with the same function the worker uses.
   Loaded last: it only adds, and wraps shipped functions by assignment
   (ledger G45). A workflow that does not start on a schedule renders
   exactly as before: every wrapper returns the shipped output untouched. */

UI_ICONS.clock='<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>';

const SCHED_DAYS=[['Mon','Monday'],['Tue','Tuesday'],['Wed','Wednesday'],['Thu','Thursday'],['Fri','Friday'],['Sat','Saturday'],['Sun','Sunday']];
const SCHED_MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
const SCHED_EVERY=[['day','Every day'],['week','Every week'],['month','Every month'],['year','Every year'],['once','Once']];

function schedOf(d){const t=(d||S.w?.definition)?.trigger||{};return t.kind==='schedule'?(t.schedule||null):null;}
function schedDefaults(){return {every:'week',at:'09:00',weekdays:[0],day:1,month:1,date:'',working_days:false,starts:S.w?.source_model?'each_record':'process'};}
function schedOrdinal(n){const t=n%100;return n+((t>=10&&t<=20)?'th':({1:'st',2:'nd',3:'rd'}[n%10]||'th'));}
function schedTime(at){const m=/^(\d{1,2}):(\d{2})$/.exec(String(at||''));return m?`${Number(m[1])}:${m[2]}`:'9:00';}
/* The same words as the server's `workflow_schedule.words`. */
function schedWords(s){const w=schedWordsBare(s);return s&&s.working_days&&s.every!=='day'&&w!=='On a schedule'?`${w}, or the next working day`:w;}
function schedWordsBare(s){
 if(!s||!SCHED_EVERY.some(e=>e[0]===s.every))return 'On a schedule';
 const at=schedTime(s.at);
 if(s.every==='day')return s.working_days?`Every working day at ${at}`:`Every day at ${at}`;
 if(s.every==='week'){
  const days=[...new Set((s.weekdays||[]).filter(d=>Number.isInteger(d)&&d>=0&&d<=6))].sort();
  if(days.join()==='0,1,2,3,4')return `Every weekday at ${at}`;
  if(days.length===7)return `Every day at ${at}`;
  const names=(days.length?days:[0]).map(d=>SCHED_DAYS[d][1]);
  return `Every ${names.length===1?names[0]:names.slice(0,-1).join(', ')+' and '+names.at(-1)} at ${at}`;
 }
 if(s.every==='month')return `On ${s.day==='last'?'the last day':'the '+schedOrdinal(Number(s.day)||1)} of each month at ${at}`;
 if(s.every==='year'){const m=SCHED_MONTHS[(Number(s.month)||1)-1]||'January';return `Every year on ${s.day==='last'?'the last day of '+m:(Number(s.day)||1)+' '+m} at ${at}`;}
 const d=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s.date||''));
 return d?`Once, on ${Number(d[3])} ${SCHED_MONTHS[Number(d[2])-1].slice(0,3)} ${d[1]} at ${at}`:'Once';
}
function schedLabel(){return String(contract().label||S.w.module||'record').split(' ').map(x=>/^[A-Z0-9]{2,}$/.test(x)?x:x.toLowerCase()).join(' ');}
function schedWho(){
 const w=S.w,d=w.definition;
 if(!w.source_model)return {lead:`start a new “${d.name}”`,scope:''};
 const ruled=conditionLeaves(d.scope).filter(r=>['set','unset'].includes(r.op)||!(r.value===''||r.value===null||r.value===undefined||(Array.isArray(r.value)&&!r.value.length))).length;
 const where=ruled?softLower(String(w.scope_summary||'').replace(/^Records\s+/,'')):'';
 return {lead:`for each ${schedLabel()}`,scope:where};
}

/* ------------------------------------------------ the "When …" sentence */
const _p5aWhenSentence=whenSentence;
whenSentence=function(){
 const s=S.w&&schedOf();if(!s)return _p5aWhenSentence();
 const words=schedWords(s),who=schedWho(),say=`${words}, ${who.lead}${who.scope?' '+who.scope:''}`;
 return `<section class="when-card is-scheduled" id="when-card"><button class="when-say" data-act="node" data-id="trigger" aria-label="${esc(say)}. Change when this starts."><span class="when-word sched-word">${svgIcon('clock')}<span>On a schedule</span></span> <span class="when-chip">${esc(words)}</span><span class="when-comma">,</span> <span class="when-chip">${esc(who.lead)}</span>${who.scope?` <span class="when-chip">${esc(who.scope)}</span>`:''}</button>${btn('node','Change','design','small','data-id="trigger" aria-label="Change when this workflow starts"')}</section>`;
};

/* ------------------------------------------------------- the picker */
function schedPicker(s){
 const on=(a,b)=>a===b?'on':'',every=s.every;
 const seg=`<div class="segmented sched-every" role="group" aria-label="How often">${SCHED_EVERY.map(([k,l])=>`<button type="button" class="${on(k,every)}" data-sched-every="${k}" aria-pressed="${k===every}">${l}</button>`).join('')}</div>`;
 let html=field('How often',seg);
 if(every==='week'){
  const days=s.weekdays||[];
  html+=field('On these days',`<div class="sched-days" role="group" aria-label="Days of the week">${SCHED_DAYS.map(([short,long],i)=>`<button type="button" class="sched-day ${days.includes(i)?'on':''}" data-sched-day="${i}" aria-pressed="${days.includes(i)}" aria-label="${long}">${short}</button>`).join('')}</div>`,days.length?'':'Choose at least one day.');
 }
 const dayRows=[...Array(31)].map((_,i)=>[i+1,schedOrdinal(i+1)]).concat([['last','The last day']]);
 if(every==='month')html+=field('Day of the month',`<select data-sched="day">${opts(dayRows,String(s.day??1),null)}</select>`,Number(s.day)>28?'In a shorter month it starts on the last day.':'');
 if(every==='year')html+=field('Each year on',`<div class="row sched-pair"><select data-sched="day" aria-label="Day">${opts(dayRows,String(s.day??1),null)}</select><select data-sched="month" aria-label="Month">${opts(SCHED_MONTHS.map((m,i)=>[i+1,m]),String(s.month??1),null)}</select></div>`,Number(s.month)===2&&Number(s.day)===29?'In years without 29 February it starts on 28 February.':'');
 if(every==='once')html+=field('On',`<input type="date" data-sched="date" value="${esc(s.date||'')}">`);
 html+=field('At',`<input type="time" data-sched="at" value="${esc(s.at||'09:00')}" step="300">`,`The company’s own time${S.schedPreview?.data?.tz?` (${esc(S.schedPreview.data.tz.replace(/_/g,' '))})`:''}.`);
 html+=`<label class="sched-check"><input type="checkbox" data-sched="working_days" ${s.working_days?'checked':''}> Working days only</label><small>A start that falls on a weekend or a public holiday moves to the next working day.</small>`;
 html+=hint('If the system was off at that time, it starts once when it is back. Pausing stops the starts; switching it back on does not catch up.','clock');
 html+=`<div class="sched-next" id="sched-next" data-pending="1" aria-live="polite"><p class="muted small">Working out the next starts…</p></div>`;
 return `<div class="sched" id="sched-picker">${html}</div>`;
}
const _p5aInspector=inspector;
inspector=function(){
 const html=_p5aInspector();
 const n=S.w&&byId(S.w.definition,S.selected);
 if(!n||n.type!=='trigger')return html;
 const kind=S.w.definition.trigger?.kind;
 let out=html.replace(/(<select data-edit="trigger\.kind">[\s\S]*?)(<\/select>)/,(m,a,b)=>a+`<option value="schedule" ${kind==='schedule'?'selected':''}>On a schedule</option>`+b);
 if(kind==='schedule'){
  const marker='<hr><h3>Only for matching records</h3>';
  const picker=schedPicker(schedOf()||schedDefaults());
  out=out.includes(marker)?out.replace(marker,picker+marker+(S.w.source_model?'':'<p class="muted small">A new process started on a schedule has no record to filter, so leave this empty.</p>')):out+picker;
 }
 return out;
};

/* edits: the trigger choice and the picker's own controls */
document.addEventListener('change',e=>{
 const t=e.target;if(!t?.dataset||S.page!=='editor'||!S.w)return;
 if(t.dataset.edit==='trigger.kind'&&t.value==='schedule'){
  e.stopImmediatePropagation();
  mutate(()=>{const tr=S.w.definition.trigger;tr.kind='schedule';if(!tr.schedule)tr.schedule=schedDefaults();tr.schedule.starts=S.w.source_model?'each_record':'process';});
  return;
 }
 const key=t.dataset.sched;if(!key)return;
 const s=schedOf();if(!s)return;
 let v=t.type==='checkbox'?t.checked:t.value;
 if(key==='day')v=v==='last'?'last':Number(v);
 if(key==='month')v=Number(v);
 if(key==='at'&&!/^\d{2}:\d{2}$/.test(v))return;
 mutate(()=>{s[key]=v;});
},true);
document.addEventListener('click',e=>{
 const b=e.target.closest?.('[data-sched-every],[data-sched-day]');if(!b||S.page!=='editor'||!S.w)return;
 const s=schedOf();if(!s)return;
 e.preventDefault();
 if(b.dataset.schedEvery){const k=b.dataset.schedEvery;if(k===s.every)return;mutate(()=>{for(const [dk,dv] of Object.entries(schedDefaults()))if(s[dk]===undefined||s[dk]===null)s[dk]=dv;s.every=k;if(k==='week'&&!(s.weekdays||[]).length)s.weekdays=[0];if(k==='once'&&!s.date)s.date=new Date(Date.now()+864e5).toISOString().slice(0,10);});}
 else{const i=Number(b.dataset.schedDay),days=new Set(s.weekdays||[]);days.has(i)?days.delete(i):days.add(i);mutate(()=>{s.weekdays=[...days].sort();});}
 setTimeout(()=>$(`[data-sched-every="${b.dataset.schedEvery}"],[data-sched-day="${b.dataset.schedDay}"]`)?.focus({preventScroll:true}),0);
});

/* ------------------------------------------- the server's preview */
function schedKey(){return JSON.stringify([S.w?.id,S.w?.definition?.trigger,S.w?.definition?.scope,S.w?.revision]);}
async function schedLoad(){
 if(!S.w)return null;
 const key=schedKey();
 if(S.schedPreview?.key===key&&S.schedPreview.data)return S.schedPreview.data;
 if(S.schedPreview?.key===key&&S.schedPreview.loading)return S.schedPreview.loading;
 const loading=rpc('schedule_preview',[S.w.id,clone(S.w.definition.trigger)]).then(data=>{if(S.schedPreview?.key===key)S.schedPreview.data=data;return data;})
  .catch(err=>{console.warn('schedule_preview',err.message);if(S.schedPreview?.key===key)S.schedPreview.data={ok:false,issues:[],next:[],error:true};return S.schedPreview?.data;});
 S.schedPreview={key,loading,data:null};
 return loading;
}
function schedNextHtml(p){
 if(!p)return '<p class="muted small">Working out the next starts…</p>';
 if(p.error)return '<p class="muted small">The next starts could not be worked out just now.</p>';
 if(p.issues?.length)return `<p class="sched-fix">${svgIcon('alert')}<span>${esc(p.issues[0].text)}</span></p>`;
 const rows=(p.next||[]).map((x,i)=>`<li class="${i===0?'is-first':''}"><span class="sched-dot" aria-hidden="true"></span><span class="sched-day-name">${esc(x.day)}</span><span class="sched-at">${esc(x.time)}</span></li>`).join('');
 const clock=p.clock_on?'':`<p class="sched-off">${svgIcon('alert')}<span>This site's workflow clock is switched off, so nothing starts here until it is switched on.</span></p>`;
 return `<h4>Next 5 starts</h4>${rows?`<ol class="sched-list">${rows}</ol>`:'<p class="muted small">No more starts: that date has passed.</p>'}${clock}${schedCountHtml(p)}`;
}
function schedCountHtml(p,full=false){
 if(!S.w?.source_model)return full?`<p class="sched-count">${svgIcon('play')}<span>Each start makes one new “${esc(S.w.definition.name)}”.</span></p>`:'';
 if(p.count===null||p.count===undefined)return '';
 const label=schedLabel(),many=label.endsWith('s')?label:label+'s';
 if(p.over_cap)return `<p class="sched-off">${svgIcon('alert')}<span>${p.count.toLocaleString()} ${esc(many)} match today, more than the ${p.cap} it may start at once, so it would start none. Narrow the filters.</span></p>`;
 if(!p.count)return `<p class="sched-count muted">${svgIcon('info')}<span>No ${esc(many)} match today.</span></p>`;
 const names=(p.names||[]).map(esc),more=p.count-names.length;
 return `<p class="sched-count">${svgIcon('play')}<span>Would start for <b>${p.count===1?'1 '+esc(label):p.count.toLocaleString()+' '+esc(many)}</b> today${full&&names.length?`: ${names.join(', ')}${more>0?` …and ${more} more`:''}`:''}.</span></p>`;
}
function schedFill(){
 const host=$('#sched-next[data-pending]'),tryHost=$('#sched-try[data-pending]');
 if(!host&&!tryHost)return;
 host?.removeAttribute('data-pending');tryHost?.removeAttribute('data-pending');
 const key=schedKey(),cached=S.schedPreview?.key===key?S.schedPreview.data:null;
 const paint=p=>{if(host?.isConnected)host.innerHTML=schedNextHtml(p);if(tryHost?.isConnected)tryHost.innerHTML=schedTryHtml(p);};
 if(cached){paint(cached);return;}
 clearTimeout(S.schedTimer);
 S.schedTimer=setTimeout(()=>schedLoad().then(p=>{if(schedKey()===key)paint(p);}),220);
}
new MutationObserver(()=>{if(document.querySelector('#sched-next[data-pending],#sched-try[data-pending]'))schedFill();}).observe(document.body,{childList:true,subtree:true});

/* ------------------------------------------------------- Try it out */
function schedTryHtml(p){
 if(!p)return '<p class="muted small">Working out when it would start…</p>';
 if(p.error||p.issues?.length)return schedNextHtml(p);
 const next=(p.next||[])[0];
 return `<div class="sched-try-head">${svgIcon('clock')}<div><strong>${esc(p.words||schedWords(schedOf()))}</strong><p class="muted small">${next?`Next start: ${esc(next.day)} at ${esc(next.time)}.`:'No more starts.'}</p></div></div>${schedCountHtml(p,true)}${p.clock_on?'':`<p class="sched-off">${svgIcon('alert')}<span>This site's workflow clock is switched off, so nothing starts here until it is switched on.</span></p>`}`;
}
const _p5aTryPage=tryPage;
tryPage=function(){
 const html=_p5aTryPage();
 if(!S.w||!schedOf())return html;
 const card=`<div class="card sched-try" id="sched-try" data-pending="1" aria-live="polite"><p class="muted small">Working out when it would start…</p></div>`;
 const k=html.indexOf('<div class="card">');
 return k>0?html.slice(0,k)+card+html.slice(k):card+html;
};

/* ------------------------------------------------------------ Review */
const _p5aReviewPeople=reviewPeople;
reviewPeople=function(r){
 const base=_p5aReviewPeople(r),p=r?.schedule;
 if(!p)return base;
 const next=(p.next||[]).slice(0,3).map(x=>`${x.day} at ${x.time}`).join(' · ');
 const warn=(p.warnings||[]).map(x=>`<div class="checkrow is-warning"><span class="check-icon" aria-hidden="true">${svgIcon(x.code==='schedule_clock_off'?'clock':'alert')}</span><div><span class="repeat-warning">${esc(x.text)}</span></div></div>`).join('');
 const count=S.w?.source_model&&p.count!==null&&p.count!==undefined&&!(p.count>p.cap)?`<div class="checkrow"><span class="check-icon" aria-hidden="true">${svgIcon('play')}</span><div>${p.count?`Would start for ${p.count.toLocaleString()} ${p.count===1?'record':'records'} today${p.names?.length?': '+esc(p.names.join(', '))+(p.count>p.names.length?` …and ${p.count-p.names.length} more`:''):''}.`:'No record matches today.'}</div></div>`:'';
 return `<section class="review-schedule"><h3>On a schedule</h3><div class="checkrow is-ok"><span class="check-icon" aria-hidden="true">${svgIcon('clock')}</span><div><strong>${esc(p.words||'')}</strong>${next?`<br><small>Next: ${esc(next)}</small>`:''}</div></div>${count}${warn}</section>`+base;
};

/* ---------------------------------------------------------- Activity */
const _p5aActivity=activity;
activity=function(embedded=false){
 let html=_p5aActivity(embedded);
 if(!embedded||!S.w)return html;
 html=html.split('<td>Started on schedule</td>').join(`<td><span class="sched-chip">${svgIcon('clock')}Started on schedule</span></td>`);
 const h=S.schedHist?.wid===S.w.id?S.schedHist:null;
 if(!h||!h.rows?.length)return html;
 const rows=h.rows.map(x=>`<li class="${x.problem?'is-problem':''}">${svgIcon(x.problem?'alert':'clock')}<span class="sched-when">${esc(x.day)} · ${esc(x.time)}</span><span>${esc(x.text)}</span></li>`).join('');
 const panel=`<section class="sched-history"><h3>Scheduled starts</h3>${h.clock_on?'':`<p class="sched-off">${svgIcon('alert')}<span>This site's workflow clock is switched off, so nothing starts here until it is switched on.</span></p>`}<ul>${rows}</ul></section>`;
 const k=html.indexOf('<div class="table-wrap">')>0?html.indexOf('<div class="table-wrap">'):html.indexOf('<div class="empty">');
 return k>0?html.slice(0,k)+panel+html.slice(k):html.replace('</main>',panel+'</main>');
};
async function schedHistory(){
 if(!S.w||!schedOf())return;
 try{S.schedHist={wid:S.w.id,...await rpc('schedule_history',[S.w.id])};}
 catch(err){S.schedHist={wid:S.w.id,rows:[]};console.warn('schedule_history',err.message);}
}
const _p5aAction=action;
action=async function(name,el){
 const r=await _p5aAction(name,el);
 if(S.page==='editor'&&S.w&&((name==='tab'&&el?.dataset?.id==='runs')||name==='refresh-runs')&&schedOf()){await schedHistory();if(S.tab==='runs')render();}
 return r;
};

/* WF2 P5c (owner decision D30) — "Around a date" in the How often choices.
   One engine: choosing it switches the workflow to the shipped "At a record
   date" start and shows that start's own settings in place, with the same
   How often row above them, so picking Every day / week / … switches back.
   The schedule a person had set is kept in the draft while they look, so
   going back restores it; filters are never touched. Record workflows only
   (a new process has no date of its own). */
function schedAroundOk(){return !!S.w?.source_model&&(S.w.metadata.fields||[]).some(f=>['date','datetime'].includes(f.type))}
function schedAroundBtn(on){return `<button type="button" class="${on?'on':''}" data-sched-around="1" aria-pressed="${on}">Around a date</button>`}
const _p5cSchedPicker=schedPicker;
schedPicker=function(s){const html=_p5cSchedPicker(s);if(!schedAroundOk())return html;const k=html.indexOf('</div>');return k>0?html.slice(0,k)+schedAroundBtn(false)+html.slice(k):html};
const _p5cAroundInspector=inspector;
inspector=function(){const html=_p5cAroundInspector();const n=S.w&&byId(S.w.definition,S.selected);if(!n||n.type!=='trigger'||S.w.definition.trigger?.kind!=='date'||!schedAroundOk())return html;const back=SCHED_EVERY.map(([k,l])=>`<button type="button" data-sched-back="${k}" aria-pressed="false">${l}</button>`).join('');const row=`<div class="sched sched-around">${field('How often',`<div class="segmented sched-every" role="group" aria-label="How often">${back}${schedAroundBtn(true)}</div>`)}<p class="muted small">Starts a set number of days before or after a date on each record. Choose another option above to start on a calendar pattern instead.</p></div>`;const marker='<label>Record date</label>';return html.includes(marker)?html.replace(marker,row+marker):html};
document.addEventListener('click',e=>{const b=e.target.closest?.('[data-sched-around],[data-sched-back]');if(!b||S.page!=='editor'||!S.w)return;e.preventDefault();e.stopImmediatePropagation();const tr=S.w.definition.trigger;if(b.dataset.schedAround){if(tr.kind==='date')return;mutate(()=>{tr.kind='date';const dates=S.w.metadata.fields.filter(f=>['date','datetime'].includes(f.type));if(!dates.some(f=>f.key===tr.date_field))tr.date_field=dates[0]?.key||'';if(typeof tr.delay!=='number')tr.delay=3;if(!tr.mode)tr.mode='before';if(!['minutes','hour','day','month'].includes(tr.unit))tr.unit='day'});setTimeout(()=>$('[data-sched-around]')?.focus({preventScroll:true}),0);return}const k=b.dataset.schedBack;mutate(()=>{tr.kind='schedule';const s=tr.schedule||(tr.schedule=schedDefaults());for(const[dk,dv]of Object.entries(schedDefaults()))if(s[dk]===undefined||s[dk]===null)s[dk]=dv;s.every=k;s.starts='each_record';if(k==='week'&&!(s.weekdays||[]).length)s.weekdays=[0];if(k==='once'&&!s.date)s.date=new Date(Date.now()+864e5).toISOString().slice(0,10)});setTimeout(()=>$(`[data-sched-every="${k}"]`)?.focus({preventScroll:true}),0)},true);
