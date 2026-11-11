'use strict';
/* WF2 P4a — everyone can take part: teams ("Take it"), cover while away,
   employee-home logins and people with no login (private link), reminders
   the approvals way, the task page inside the Approvals inbox (embed=1), and
   removing a stage Hiring added. Loaded last: it only adds, and wraps the
   click dispatcher for its own verbs. */
const EMBED=query.get('embed')==='1';
Object.assign(UI_ICONS,{
 team:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
 away:'<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'
});
if(EMBED)document.documentElement.classList.add('is-embed');
function dayWords(v){const d=new Date(String(v||'').slice(0,10)+'T00:00:00');return isNaN(d)?String(v||''):d.toLocaleDateString(undefined,{weekday:'short',day:'numeric',month:'short'});}

/* ---------------------------------------------------------- the inspector */
function teamRows(){return (S.w?.metadata.teams||[]).map(t=>[t.id,t.members?`${t.name} · ${t.members===1?'1 person':t.members+' people'}`:`${t.name} · nobody on it yet`]);}
function teamPicker(path,owner){
 const teams=S.w?.metadata.teams||[];
 if(!teams.length)return stepEmpty('team','There are no teams yet. Make one in Approvals › Who approves (“A group of people”).');
 const team=teams.find(t=>t.id===owner.id);
 return field('<span id="team-label">Team</span>',`<select data-edit="${path}.id" aria-labelledby="team-label">${opts(teamRows(),owner.id)}</select>`)
  +(team&&!team.members?hint('Nobody is on this team here yet, so the task would have nobody to go to. Add people in Approvals › Who approves.','alert','warn'):'')
  +hint('Anyone on the team sees it in their Approvals list and can take it. The first to take it does it; the others see who has it. Only staff logins are counted.','team');
}
function personHints(n){
 const kind=n.owner?.kind;let html='';
 if(['subject','manager','field','initiator'].includes(kind))html+=hint('People with an employee-home login do this on their home page. Someone with no login gets a private link by email, when their work email is known.','link');
 html+=hint(S.w?.metadata.late_words||'Reminded a day after it is due, then their manager is told a day later — the same way approvals work.','clock');
 html+=hint('If the person is away and has someone covering for them in Approvals, it goes to the person covering.','away');
 return html;
}

/* ------------------------------------------------- my tasks, task page */
function taskChips(t){
 const out=[];
 if(t.late)out.push(pill('Late','failed'));
 else if(t.due)out.push(pill('Due '+dayWords(t.due),''));
 if(t.sent_back)out.push(pill('Sent back','waiting'));
 if(t.team)out.push(`<span class="pill team">${svgIcon('team')}${t.team.taken?esc(t.team.name)+' · '+esc(t.team.taken_by||'taken'):'Team: '+esc(t.team.name)+' · nobody has taken it'}</span>`);
 if(t.covering_for)out.push(`<span class="pill">${svgIcon('away')}Covering for ${esc(t.covering_for)}</span>`);
 return out.join('');
}
function tasks(){
 const rows=S.boot.tasks||[];
 const card=t=>`<div class="card task-card ${t.late?'is-late':''}"><div class="row"><span class="type-icon ${t.kind}">${svgIcon(t.kind)}</span><div class="grow"><h2>${esc(t.name)}</h2><small>${esc(t.workflow)}${t.record?' · '+esc(t.record):''}</small></div></div><div class="row wrap task-chips">${taskChips(t)}</div><div class="row wrap">${t.can_take?btn('take','Take it','check','primary',`data-id="${t.id}"`)+btn('task','Look first','arrow','',`data-id="${t.id}"`):btn('task',t.kind==='input'?'Fill in details':t.kind==='confirm'?'Read and confirm':'Open task','arrow','primary',`data-id="${t.id}"`)}${t.can_release?btn('release','Put it back','','plain',`data-id="${t.id}"`):''}</div></div>`;
 return `<main class="page"><div class="pagehead"><div><h1>My tasks</h1><p class="muted">The next small steps that move work forward. They are in your Approvals list too.</p></div>${btn('tasks','Refresh','history')}</div>${rows.length?`<div class="cards">${rows.map(card).join('')}</div>`:'<div class="empty"><span class="type-icon trigger">'+svgIcon('check')+'</span><h2>You’re all caught up</h2><p class="muted">Tasks given to you, or to a team you are on, appear here and in Approvals.</p></div>'}</main>`;
}
function peopleExtras(t){
 let html='';
 if(t.team&&!t.team.taken)html+=`<div class="banner team-banner" role="note">${svgIcon('team')}<div><strong>For the team ${esc(t.team.name)}</strong><p>Nobody has taken it yet. Answering it takes it for you, or take it first so the others know.</p></div>${btn('take','Take it','check','primary',`data-id="${t.id}"`)}</div>`;
 else if(t.team&&t.team.mine)html+=`<div class="banner team-banner is-mine" role="note">${svgIcon('team')}<div><strong>You took this for the team ${esc(t.team.name)}</strong></div>${btn('release','Put it back','','plain',`data-id="${t.id}"`)}</div>`;
 if(t.covering_for)html+=`<div class="banner" role="note">${svgIcon('away')}<span>You are covering for ${esc(t.covering_for)} while they are away.</span></div>`;
 if(t.due)html+=`<p class="task-due ${t.late?'is-late':''}">${svgIcon('clock')}${t.late?'Late · it was due ':'Needed by '}${esc(dayWords(t.due))}</p>`;
 return html;
}
/* After a task is done: back to My tasks, or tell the inbox around us. */
function taskFinished(){
 if(EMBED&&parent!==window){parent.postMessage({type:'pb.workflow.task.done',id:S.task?.id},location.origin);S.page='done';$('#app').innerHTML=`<main class="form-page embed-done"><div class="card"><span class="type-icon trigger">${svgIcon('check')}</span><h2>Done</h2><p class="muted">It has moved on to the next step.</p></div></main>`;return;}
 return action('tasks');
}

/* ------------------------------------------------------------- progress */
function peopleProgress(step){
 if(!step)return '';
 let html='';
 if(step.team)html+=`<p class="progress-chip">${svgIcon('team')}${esc(step.team)}</p>`;
 if(step.covering)html+=`<p class="progress-chip">${svgIcon('away')}${esc(step.covering)}</p>`;
 if(step.done_by)html+=`<p class="progress-chip">${svgIcon('link')}${esc(step.done_by)}</p>`;
 if(step.link){html+=`<div class="link-box"><p>${svgIcon('link')}<span>${esc(step.link.text)}${step.link.until?' · works until '+esc(dayWords(step.link.until)):''}${step.link.opened?' · opened':' · not opened yet'}</span></p>${step.link.can_resend?btn('resend-link','Send the link again','email','small',`data-id="${step.id}"`)+'<small>A new link replaces the old one.</small>':''}</div>`;}
 return html;
}

/* --------------------------------------------------------------- review */
function reviewPeople(r){
 const rows=r.people_notes||[];
 if(!rows.length)return '';
 return `<section class="review-people"><h3>Who takes part</h3>${rows.map(x=>`<div class="checkrow ${x.tone==='warn'?'is-warning':''}"><span class="check-icon" aria-hidden="true">${svgIcon(x.code==='team'?'team':x.tone==='warn'?'alert':'link')}</span><div>${esc(x.text)} ${btn('fix','Open step','','small plain',`data-id="${esc(x.id)}"`)}</div></div>`).join('')}</section>`;
}

/* ---------------------------------------------------------- the verbs */
const _p4aAction=action;
action=async function(name,el){
 const id=el?.dataset?.id;
 if(name==='take'){
  try{const t=await rpc('take',[Number(id)]);notify('It is yours now. The rest of the team sees that you have it.');
   if(S.page==='task'){S.task=t;S.answers=clone(t.answers);S.errors={};render();}
   else{S.boot.tasks=await rpc('tasks');render();}}
  catch(e){notify(e.message,true);S.boot.tasks=await rpc('tasks');if(S.page==='tasks')render();}
  return;
 }
 if(name==='release'){
  try{await rpc('release',[Number(id)]);notify('Put back for the team.');}catch(e){notify(e.message,true);}
  if(EMBED&&parent!==window&&S.page==='task'){parent.postMessage({type:'pb.workflow.task.done',id:Number(id)},location.origin);return;}
  return _p4aAction('tasks',el);
 }
 if(name==='resend-link'){
  try{const r=await rpc('resend_link',[Number(id)]);notify(`A new link was sent to ${r.sent_to}. The old one no longer works.`);await _p4aAction('refresh-progress',el);}
  catch(e){notify(e.message,true);}
  return;
 }
 if(name==='area-stage-remove'){
  const i=Number(el.dataset.index),info=sectionInfo(i);S.removingArea={index:i,row:info.row};
  modal(`Remove “${info.name}” from ${areaName()}?`,`<p>It comes off every ${esc(areaName())} board and preset, and this section becomes a heading. ${esc(areaName())} refuses while anyone is in it.</p><p class="muted">Its history stays. Only stages your company added can be removed.</p>`,btn('close','Keep it')+btn('area-stage-remove-yes','Remove it','trash','danger'));
  return;
 }
 if(name==='area-stage-remove-yes'){
  const r=S.removingArea;
  try{const cat=await rpc('stage_remove_area',[S.w.source_model,r.row.key]);S.w.metadata.stage_catalogue=cat;close();
   mutate(()=>{for(const s of S.w.definition.stages)if(s.bind?.kind==='core'&&String(s.bind.value)===String(r.row.key))delete s.bind;},false);
   notify(cat.removed?.note||'Removed.');S.sheetError=null;refreshWork();renderSheet();}
  catch(e){close();S.sheetError={index:r.index,text:e.message};renderSheet();}
  return;
 }
 return _p4aAction(name,el);
};
/* Step cards name a team as a team. */
const _p4aOwnerName=ownerName;
ownerName=function(n){if(n?.owner?.kind==='team'){const t=(S.w?.metadata.teams||[]).find(x=>x.id===n.owner.id);return t?'Team: '+t.name:'Choose a team';}return _p4aOwnerName(n);};
/* An area may word its own value on the step card ("Adds the tag “IT”"). */
const _p4aNewSummary=newSummary;
newSummary=function(n){if(n?.type==='update'&&!n.value_from){const f=safeSpec(n.field);if(f?.card_words&&n.value!==undefined&&n.value!==''){const o=(f.options||[]).find(x=>String(x.key??x)===String(n.value));if(o)return f.card_words.replace('%s',o.label??o);}}return _p4aNewSummary(n);};
