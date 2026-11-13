/* WF2 P3b: the eight new steps, task buttons, richer waits and Duplicate.
   Every setting here edits the draft through mutate() (one Undo each) and
   never names a field, a model or a code: the words are the screen's. */

/* ------------------------------------------------------------ the shape */
function groupParents(d){const out={};for(const n of d.nodes){for(const b of n.branches||[])for(const c of b.steps)out[c]=[n,b.id];if(n.type==='subprocess')for(const c of n.steps||[])out[c]=[n,null];}return out;}
function ancestorsOf(d,key,pm=groupParents(d)){const out=[];let at=key,guard=0;while(pm[at]&&guard++<50){out.push(pm[at][0]);at=pm[at][0].id;}return out;}
function mainOf(d,key){const a=ancestorsOf(d,key);return a.length?a.at(-1).id:key;}
function isConditional(d,n){return !!n.when||ancestorsOf(d,n.id).some(g=>g.type==='branch');}
function inParallel(d,n){return ancestorsOf(d,n.id).some(g=>g.type==='parallel');}
/* Steps that may already have run when `key` is reached and would run again
   after a send back to `target` (the server's `between`, mirrored). */
function runsAgain(d,target,key){
 const pm=groupParents(d),top=mainOf(d,key),out=[];
 if(!d.order.includes(target)||!d.order.includes(top))return out;
 for(const k of d.order.slice(d.order.indexOf(target)+1,d.order.indexOf(top)))out.push(...descendants(d,k));
 let at=key,guard=0;
 while(pm[at]&&guard++<50){const [g,b]=pm[at],ids=b?g.branches.find(x=>x.id===b).steps:g.steps;for(const s of ids.slice(0,ids.indexOf(at)))out.push(...descendants(d,s));at=g.id;}
 return out.filter(k=>k!==key).map(k=>byId(d,k)).filter(Boolean);
}
const ONCE_ONLY=['matrix','action','update','create','start'],TELLS=['email','notify'];

/* -------------------------------------------------------------- words */
function waitAmount(n){const unit=n.unit||'hours';return unit==='hours'?(n.hours??1):(n.amount??Math.max(1,Math.round((n.hours||24)/24)));}
function waitWords(n){const unit=n.unit||'hours',a=waitAmount(n);return unit==='working'?plural(a,'working day'):unit==='days'?plural(a,'day'):plural(a,'hour');}
function stageRowById(id){return catalogue().find(s=>s.kind==='yours'&&s.key===Number(id));}
function safeSpec(key){return (S.w?.metadata.safe_fields||[]).find(f=>f.key===key);}
function creatorOf(key){return (S.w?.metadata.creators||[]).find(c=>c.key===key);}
function buttonsOf(n){return n.buttons?.length?n.buttons:n.type==='confirm'?[{key:'confirm',label:'I confirm'}]:[{key:'done',label:'Done'}];}
function newSummary(n){
 const d=S.w?.definition;
 if(n.type==='stage_move'){const r=stageRowById(n.target?.id);return r?`To ${r.name}`:'Choose one of your stages';}
 if(n.type==='send_back'){const t=d&&byId(d,n.target);return t?`Back to ${t.title}`:'Choose where it goes back to';}
 if(n.type==='update'){const f=safeSpec(n.field);return f?`Sets ${f.label}`:'Choose a value to set';}
 if(n.type==='create'){const c=creatorOf(n.creator),t=c?.templates.find(t=>t.id===n.template_id);return c?`Draft ${n.creator==='letter'?'letter':'announcement'}${t?' · '+t.name:''}`:'Choose what to create';}
 if(n.type==='notify')return `${ownerName(n)} · in the app`;
 if(n.type==='confirm')return `${ownerName(n)} · “${buttonsOf(n)[0].label}”`;
 if(n.type==='start'){const t=(S.w?.metadata.start_targets||[]).find(t=>t.id===n.workflow_id);return t?`Hands over to ${t.name}`:'Choose a workflow';}
 if(n.type==='end')return n.reason?`Stops: ${n.reason}`:'Ends the workflow here';
 return TYPES[n.type]?.[1]||'';
}

/* ------------------------------------------------------- inspector bits */
const sedit=(path,html)=>html.replace(/^<(input|select|textarea)/,`<$1 data-sedit="${esc(path)}"`);
function hint(text,icon='info',kind=''){return `<p class="step-hint ${kind}">${svgIcon(icon)}<span>${text}</span></p>`;}
function stepEmpty(icon,text,action=''){return `<div class="step-empty">${svgIcon(icon)}<p>${text}</p>${action}</div>`;}
function conditionWarning(n){
 const d=S.w.definition;
 if(inParallel(d,n))return hint(`“${esc(n.title)}” cannot sit inside work in parallel. Move it after the parallel paths.`,'alert','is-warn');
 if(isConditional(d,n))return '';
 return `<div class="step-warn" role="note">${svgIcon('alert')}<div><strong>${n.type==='send_back'?'This would always send the work back.':'This would always stop the workflow here.'}</strong><span>Put it inside a path, or give it an “Only when…”.</span>${btn('open-when','Add an “Only when…”','branch','small')}</div></div>`;
}
const PRESETS=[['done','Done',[{key:'done',label:'Done'}]],['cannot','Done / Cannot do',[{key:'done',label:'Done'},{key:'cannot',label:'Cannot do'}]],['yesno','Yes / No',[{key:'yes',label:'Yes'},{key:'no',label:'No'}]],['custom','Your own words',null]];
function presetOf(n){if(!n.buttons?.length)return 'done';if(n.buttons_custom)return 'custom';const hit=PRESETS.find(p=>p[2]&&JSON.stringify(p[2])===JSON.stringify(n.buttons));return hit?hit[0]:'custom';}
function buttonsEditor(n){
 const rows=buttonsOf(n),preset=presetOf(n);
 const chips=`<div class="button-preview" aria-label="What the person sees">${rows.map((b,i)=>`<span class="button-chip ${i===0?'primary':''}">${i===0?svgIcon('check'):''}${esc(b.label)}</span>`).join('')}</div>`;
 const edit=preset==='custom'?`<div class="button-rows">${rows.map((b,i)=>`<div class="button-row">${sedit(`buttons.${i}.label`,`<input value="${esc(b.label)}" maxlength="40" aria-label="Button ${i+1}">`)}${rows.length>1?btn('button-remove','','close','small plain',`data-index="${i}" aria-label="Remove button ${esc(b.label)}"`):''}</div>`).join('')}${rows.length<4?btn('button-add','Add a button','plus','small plain'):''}</div>`:'';
 const more=rows.length>1?hint(`The answer can choose what happens next. ${btn('answer-paths','Add a path for each answer','branch','small')}`,'branch'):'';
 return `<hr><h3 class="inspector-title">${svgIcon('buttons')}Buttons the person sees</h3>${field('<span id="buttons-label">Buttons</span>',sedit('buttons.preset',`<select aria-labelledby="buttons-label">${opts(PRESETS.map(p=>[p[0],p[1]]),preset,null)}</select>`))}${edit}${chips}${more}`;
}
function confirmText(n){
 return field('<span id="confirm-text-label">What they read and agree to</span>',sedit('text',`<textarea rows="4" maxlength="4000" aria-labelledby="confirm-text-label" placeholder="For example: I have read the travel policy and will follow it.">${esc(n.text||'')}</textarea>`),n.text?.trim()?'':'<span class="field-need">Write what the person is asked to read.</span>')
  +field('<span id="confirm-button-label">Their button</span>',sedit('buttons.0.label',`<input value="${esc(buttonsOf(n)[0].label)}" maxlength="40" aria-labelledby="confirm-button-label">`),'One tap records who confirmed, and when.');
}
function waitDuration(n){
 const unit=n.unit||'hours',amount=waitAmount(n);
 return field(`<span id="wait-label">${n.wait_for?'Wait at most':'Wait for'}</span>`,`<div class="row wait-row">${sedit('wait.amount',`<input type="number" value="${esc(amount)}" min="${unit==='hours'?'0.25':'1'}" max="${unit==='hours'?'8760':'365'}" step="${unit==='hours'?'0.25':'1'}" aria-labelledby="wait-label">`)}${sedit('wait.unit',`<select aria-label="Unit">${opts([['hours','hours'],['days','days'],['working','working days']],unit,null)}</select>`)}</div>`,unit==='working'?'Counted on the company’s working calendar, as task deadlines are.':'');
}
function detailOptions(){
 const rows=[];
 for(const f of S.w.metadata.fields||[])if(!['many2many','one2many'].includes(f.type))rows.push([f.key,f.label]);
 for(const f of availableFields())if(f.key.startsWith('step.'))rows.push([f.key,f.label]);
 return rows;
}
/* Notices hold {{detail}} holes. On screen the hole shows the detail's own
   words ("Receipt details · Receipt"); what is saved is its key. */
function toLabels(text){const m=Object.fromEntries(detailOptions());return String(text||'').replace(/\{\{\s*([^}]+?)\s*\}\}/g,(all,k)=>m[k]?`{{${m[k]}}}`:all);}
function toKeys(text){const m=Object.fromEntries(detailOptions().map(([k,l])=>[l,k]));return String(text||'').replace(/\{\{\s*([^}]+?)\s*\}\}/g,(all,l)=>m[l]?`{{${m[l]}}}`:all);}
function compatibleAnswers(spec){
 const feeds={text:['text','textarea','email','select','date','selection'],number:['number'],date:['date'],yesno:['boolean'],choice:['select','selection'],person:[]}[spec?.type]||[];
 return availableFields().filter(f=>f.key.startsWith('step.')&&feeds.includes(f.type));
}
function valueControl(spec,n){
 const v=n.value;
 if(spec.type==='number')return sedit('value',`<input type="number" step="any" value="${esc(v??'')}" aria-label="Value">`);
 if(spec.type==='date')return sedit('value',`<input type="date" value="${esc(v||'')}" aria-label="Value">`);
 if(spec.type==='yesno')return sedit('value',`<select aria-label="Value">${opts([['true','Yes'],['false','No']],v===undefined?'':String(v),'Choose Yes or No')}</select>`);
 if(spec.type==='choice')return sedit('value',`<select aria-label="Value">${opts((spec.options||[]).map(o=>[o.key??o,o.label??o]),v)}</select>`);
 if(spec.type==='person')return sedit('value',`<select aria-label="Value">${opts(S.w.metadata.users,v,'Choose a person')}</select>`);
 return sedit('value',`<input value="${esc(v??'')}" maxlength="2000" aria-label="Value" placeholder="What to write">`);
}
function newInspector(n){
 const d=S.w.definition,area=esc(areaName());
 if(n.type==='stage_move'){
  const action=Object.entries(S.w.metadata.actions||{}).find(([,a])=>(a.params||[]).some(p=>p.key==='stage_key'));
  const swap=action?`<div class="step-note">${svgIcon('lock')}<div><span>To move between ${area}’s own stages use: <strong>${esc(action[1].label)}</strong>.</span>${btn('swap-action',`Use “${esc(action[1].label)}” instead`,'state','small',`data-key="${esc(action[0])}"`)}</div></div>`:'';
  if(ownRows())return swap||hint(`${area}’s own stages are moved by ${area}.`,'lock');
  const rows=catalogue().filter(s=>s.kind==='yours');
  if(!rows.length)return stepEmpty('flag',`You have no stages of your own ${isRecordFlow()?'for these records':'in this process'} yet.`,btn('stages','Add one in Stages','flag','small','aria-haspopup="dialog"'))+swap;
  const chosen=stageRowById(n.target?.id);
  return field('<span id="move-to-label">Move it to</span>',sedit('target.id',`<select aria-labelledby="move-to-label">${opts(rows.map(s=>[s.key,s.name+(s.counts_as?` · counts as ${s.counts_as}`:'')]),n.target?.id)}</select>`))
   +(chosen?hint(isRecordFlow()?`If the record is not at ${esc(chosen.counts_as)} yet, this waits for it. If it has already moved past, this step is skipped and the work carries on.`:'The request moves to this stage straight away.','flag'):'')+swap;
 }
 if(n.type==='send_back'){
  const top=mainOf(d,n.id),before=d.order.slice(0,Math.max(0,d.order.indexOf(top))).map(k=>byId(d,k)).filter(x=>PERSON_TYPES.includes(x.type));
  let html=conditionWarning(n);
  if(!before.length)return html+stepEmpty('send_back','Add a task or a form earlier on the main path. That is where the work goes back to.');
  html+=field('<span id="back-to-label">Send it back to</span>',sedit('target',`<select aria-labelledby="back-to-label">${opts(before.map(x=>[x.id,x.title]),n.target)}</select>`));
  if(n.target&&byId(d,n.target)){
   const again=runsAgain(d,n.target,n.id),twice=again.filter(x=>ONCE_ONLY.includes(x.type)),tell=again.filter(x=>TELLS.includes(x.type));
   html+=`<div class="again"><p class="again-title">${svgIcon('history')}Runs again after the changes</p><div class="row wrap">${[byId(d,n.target),...again].map(x=>`<span class="again-chip ${ONCE_ONLY.includes(x.type)?'is-bad':TELLS.includes(x.type)?'is-warn':''}">${svgIcon(x.type)}${esc(x.title)}</span>`).join('')}</div></div>`;
   if(twice.length)html+=hint(`${esc(twice.map(x=>x.title).join(', '))} would run twice. Send it back to a later step, or move ${twice.length===1?'that step':'those steps'} after this one.`,'alert','is-bad');
   else if(tell.length)html+=hint(`${esc(tell.map(x=>x.title).join(', '))} would be sent again.`,'alert','is-warn');
  }
  return html+hint('The person gets it again with the latest note. Answers they gave are kept. It can go back three times; after that someone is asked to look.','note');
 }
 if(n.type==='update'){
  if(!isRecordFlow())return stepEmpty('update','A new process has no record to update. Ask for the value in a form instead.');
  const safe=S.w.metadata.safe_fields||[];
  if(!safe.length)return stepEmpty('lock',`${area} has not opened any values to workflows yet.`);
  const spec=safeSpec(n.field),mode=n.value_from!==undefined?'answer':'fixed';
  let html=field('<span id="update-field-label">Value to set</span>',sedit('field',`<select aria-labelledby="update-field-label">${opts(safe.map(f=>[f.key,f.label]),n.field)}</select>`));
  if(spec){
   const radio=(value,title)=>`<label class="choice-card compact"><input type="radio" name="update-mode" value="${value}" data-sedit="value_mode" ${mode===value?'checked':''}><span><strong>${title}</strong></span></label>`;
   html+=`<fieldset class="mode-set"><legend>Set it to</legend>${radio('fixed','A fixed value')}${radio('answer','An earlier answer')}</fieldset>`;
   if(mode==='fixed')html+=field('','<div class="value-wrap">'+valueControl(spec,n)+'</div>');
   else{const rows=compatibleAnswers(spec);html+=rows.length?sedit('value_from',`<select aria-label="Earlier answer">${opts(rows.map(f=>[f.key,f.label]),n.value_from)}</select>`):stepEmpty('input','No earlier answer fits. Add a question to a form before this step.');}
  }
  return html+hint(`Only values ${area} marks as safe appear here. Its status and money are never in this list.`,'lock');
 }
 if(n.type==='create'){
  const cs=S.w.metadata.creators||[],c=creatorOf(n.creator);
  let html=`<fieldset class="create-set"><legend>What to create</legend>${cs.map(x=>`<label class="choice-card ${x.reason?'is-off':''}"><input type="radio" name="creator" value="${x.key}" data-sedit="creator" ${n.creator===x.key?'checked':''} ${x.reason?'disabled':''}><span class="choice-icon">${svgIcon(x.key==='letter'?'create':'notify')}</span><span><strong>${esc(x.label)}</strong><small>${esc(x.reason||x.hint)}</small></span></label>`).join('')}</fieldset>`;
  if(c&&!c.reason)html+=c.templates.length?field('<span id="create-template-label">Start from</span>',sedit('template_id',`<select aria-labelledby="create-template-label">${opts(c.templates,n.template_id)}</select>`)):stepEmpty('templates',`No ${n.creator==='letter'?'letter':'announcement'} templates yet. Make one in ${n.creator==='letter'?'the letters library':'Announcements'} first.`);
  return html+hint('It is made as a draft and never sent from here. A letter still needs its own approval to be sent; an announcement follows its own sign-off.','shield');
 }
 if(n.type==='notify'){
  return ownerControl('owner',n.owner,'Who gets it?')
   +field('<span id="notify-text-label">The notice</span>',sedit('text',`<textarea id="notify-text" rows="4" maxlength="1000" aria-labelledby="notify-text-label" placeholder="For example: Your claim is approved and booked for payment.">${esc(toLabels(n.text))}</textarea>`),n.text?.trim()?'':'<span class="field-need">Write the notice.</span>')
   +`<div class="row insert-row"><label for="notify-insert" class="sr">Insert a detail</label><select id="notify-insert" aria-label="Insert a detail">${opts(detailOptions(),'','Insert a detail…')}</select></div>`
   +hint('Shown in their inbox in the app. No email and no task. People without a login are skipped, and the work carries on.','notify');
 }
 if(n.type==='start'){
  const rows=(S.w.metadata.start_targets||[]).filter(t=>t.manual);
  if(!rows.length)return stepEmpty('start','No other workflow for these records is started by a person yet. Create one and publish it, then choose it here.');
  const t=rows.find(t=>t.id===n.workflow_id);
  return field('<span id="start-label">Hand over to</span>',sedit('workflow_id',`<select aria-labelledby="start-label">${opts(rows.map(t=>[t.id,t.name+(!t.published?' · not published yet':!t.enabled?' · not switched on yet':'')]),n.workflow_id)}</select>`))
   +(t&&(!t.published||!t.enabled)?hint(`“${esc(t.name)}” must be ${!t.published?'published and ':''}switched on when this step is reached, or this step asks for attention.`,'alert','is-warn'):'')
   +hint('It starts for the same record, as if the person who started this one had started it. This workflow does not wait for it. Workflows hand over three times in a row at most.','start');
 }
 if(n.type==='end'){
  return conditionWarning(n)+field('<span id="end-label">Reason (optional)</span>',sedit('reason',`<input value="${esc(n.reason||'')}" maxlength="200" aria-labelledby="end-label" placeholder="For example: Nothing to pay">`),'Shown in the workflow’s progress.')
   +hint('Every step after this one is skipped and the workflow is marked finished.','end');
 }
 return '';
}

/* -------------------------------------------------------------- edits */
function typedValue(spec,v){
 if(!spec)return v;
 if(spec.type==='number')return v===''||v===null?null:Number(v);
 if(spec.type==='yesno')return v===''?undefined:v==='true'||v===true;
 if(spec.type==='person')return Number(v)||null;
 return v;
}
function applyStepEdit(n,path,v){
 if(path==='buttons.preset'){
  delete n.buttons_custom;
  if(v==='done')delete n.buttons;
  else if(v==='custom'){n.buttons=clone(buttonsOf(n));if(n.buttons.length<2)n.buttons.push({key:uid('answer'),label:'Cannot do'});n.buttons_custom=true;}
  else n.buttons=clone(PRESETS.find(p=>p[0]===v)[2]);
  return;
 }
 const m=/^buttons\.(\d+)\.label$/.exec(path);
 if(m){if(!n.buttons?.length)n.buttons=clone(buttonsOf(n));const b=n.buttons[Number(m[1])];if(b&&String(v).trim())b.label=String(v).trim().slice(0,40);return;}
 if(path==='target'){if(v)n.target=v;else delete n.target;return;}
 if(path==='target.id'){if(v)n.target={kind:'yours',id:Number(v)};else delete n.target;return;}
 if(path==='field'){n.field=v;delete n.value_from;const spec=safeSpec(v);n.value=spec?.type==='choice'?(spec.options?.[0]?.key??''):spec?.type==='yesno'?true:spec?.type==='number'?0:'';if(spec?.type==='person')delete n.value;return;}
 if(path==='value_mode'){if(v==='answer'){delete n.value;n.value_from=compatibleAnswers(safeSpec(n.field))[0]?.key||'';}else{delete n.value_from;n.value=typedValue(safeSpec(n.field),'');if(n.value===undefined||n.value===null)n.value='';}return;}
 if(path==='value'){n.value=typedValue(safeSpec(n.field),v);if(n.value===undefined)delete n.value;return;}
 if(path==='value_from'){n.value_from=v;return;}
 if(path==='creator'){n.creator=v;delete n.template_id;const c=creatorOf(v);if(c?.templates.length===1)n.template_id=c.templates[0].id;return;}
 if(path==='template_id'||path==='workflow_id'){if(Number(v))n[path]=Number(v);else delete n[path];return;}
 if(path==='wait.amount'||path==='wait.unit'){
  const unit=path==='wait.unit'?v:(n.unit||'hours');let amount=path==='wait.amount'?Number(v):waitAmount(n);
  if(path==='wait.unit'&&(n.unit||'hours')!==v)amount=v==='hours'?Math.max(0.25,Math.round((n.amount||1)*24)):Math.max(1,Math.round((n.hours||24)/24));
  if(!(amount>0))amount=unit==='hours'?1:1;
  if(unit==='hours'){delete n.unit;delete n.amount;n.hours=Math.min(8760,amount);}
  else{n.unit=unit;n.amount=Math.min(365,Math.round(amount));n.hours=n.amount*24;}
  return;
 }
 if(path==='text'&&n.type==='notify'){n.text=toKeys(v);return;}
 if(['text','reason'].includes(path)){n[path]=String(v);return;}
}
document.addEventListener('change',e=>{
 const t=e.target;
 if(t.id==='notify-insert'&&t.value){const area=$('#notify-text'),token=`{{${t.selectedOptions[0].text}}}`;if(area){const at=area.selectionStart??area.value.length;area.value=area.value.slice(0,at)+token+area.value.slice(area.selectionEnd??at);area.focus();area.setSelectionRange(at+token.length,at+token.length);const n=byId(S.w.definition,S.selected);mutate(()=>{n.text=toKeys(area.value);},false);refreshWork();}t.value='';return;}
 if(!t.dataset?.sedit||S.page!=='editor')return;
 const n=byId(S.w.definition,S.selected);if(!n)return;
 const path=t.dataset.sedit,v=t.type==='number'?(t.value===''?null:Number(t.value)):t.value;
 const redraw=t.tagName==='SELECT'||t.type==='radio';
 mutate(()=>applyStepEdit(n,path,v),false);
 if(redraw){const focus=t.type==='radio'?`[data-sedit="${path}"][value="${CSS.escape(t.value)}"]`:`[data-sedit="${path}"]`;render();$(focus)?.focus({preventScroll:true});}
 else refreshWork();
});

/* ---------------------------------------------------------- Duplicate */
function duplicateStep(){
 const d=S.w.definition,src=byId(d,S.selected);
 if(!src||src.type==='trigger'||src.type==='matrix')return;
 const ids=descendants(d,src.id),map={},paths={};
 ids.forEach(k=>{map[k]=uid(byId(d,k).type);for(const b of byId(d,k).branches||[])paths[b.id]=uid('path');});
 const remap=v=>{if(Array.isArray(v))return v.map(remap);if(v&&typeof v==='object')return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,remap(x)]));if(typeof v==='string'){if(map[v])return map[v];if(paths[v])return paths[v];for(const [from,to] of Object.entries(map))if(v.startsWith('step.'+from+'.'))return 'step.'+to+v.slice(from.length+5);}return v;};
 const copies=ids.map(k=>remap(clone(byId(d,k))));
 copies[0].title=(src.title+' (copy)').slice(0,120);delete copies[0].ack_repeat;
 mutate(()=>{const dd=S.w.definition;dd.nodes.push(...copies);const c=containers(dd).find(c=>c.ids.includes(src.id));c.ids.splice(c.ids.indexOf(src.id)+1,0,map[src.id]);S.selected=map[src.id];});
 const name=/[“”"]/.test(src.title)?src.title:`“${src.title}”`;
 notify(`${name} duplicated${ids.length>1?' with the steps inside it':''}. Undo is available.`);
}

/* -------------------------------------------------------------- actions */
async function stepAction(name,el){
 if(name==='duplicate'){duplicateStep();return true;}
 if(name==='button-add'||name==='button-remove'){const n=byId(S.w.definition,S.selected);mutate(()=>{if(!n.buttons?.length)n.buttons=clone(buttonsOf(n));n.buttons_custom=true;if(name==='button-add'&&n.buttons.length<4)n.buttons.push({key:uid('answer'),label:'Another answer'});if(name==='button-remove'&&n.buttons.length>1)n.buttons.splice(Number(el.dataset.index),1);});$(name==='button-add'?'.button-rows .button-row:last-of-type input':'[data-act="button-add"]')?.focus();return true;}
 if(name==='answer-paths'){
  const n=byId(S.w.definition,S.selected),rows=buttonsOf(n);if(rows.length<2)return true;
  const route={id:uid('branch'),type:'branch',title:`After “${n.title}”`.slice(0,120),stage:n.stage,branches:[...rows.slice(0,-1).map(b=>({id:uid('path'),label:b.label,condition:{match:'all',rules:[{field:`step.${n.id}.outcome`,op:'eq',value:b.key}]},steps:[]})),{id:uid('path'),label:rows.at(-1).label,steps:[]}]};
  mutate(()=>{const dd=S.w.definition;dd.nodes.push(route);const c=containers(dd).find(c=>c.ids.includes(n.id));c.ids.splice(c.ids.indexOf(n.id)+1,0,route.id);S.selected=route.id;});
  notify(`A path for each answer is ready. Drag steps into “${rows[0].label}” or “${rows.at(-1).label}”.`);return true;
 }
 if(name==='swap-action'){
  const n=byId(S.w.definition,S.selected),key=el.dataset.key;
  mutate(()=>{Object.keys(n).forEach(k=>{if(!['id','stage','when'].includes(k))delete n[k];});Object.assign(n,{type:'action',title:S.w.metadata.actions[key]?.label||TYPES.action[0],action_key:key});});
  notify('Changed to the area’s own move. Choose the stage in the step settings.');return true;
 }
 if(name==='open-when'){const box=$('.drawer .filter-section:last-of-type');if(box){box.open=true;box.querySelector('[data-act="condition-add"]')?.focus();}return true;}
 if(name==='complete-outcome'){
  const comment=$('#task-note')?.value?.trim();
  const r=await rpc('answer',[S.task.id,{outcome:el.dataset.id,...(comment?{comment}:{})},true]);
  if(!r.ok){S.errors={_form:r.errors?._outcome||'Choose one of the buttons.'};render();return true;}
  notify(S.task.kind==='confirm'?'Confirmed. Thank you.':`Saved: ${el.textContent.trim()}.`);return taskFinished(),true;
 }
 if(name==='open-made'){
  if(el.dataset.model==='pb.workflow.run'){await loadProgress(el.dataset.id);return true;}
  openAction({type:'ir.actions.act_window',res_model:el.dataset.model,res_id:Number(el.dataset.id),views:[[false,'form']],target:'current'});return true;
 }
 return false;
}

/* ------------------------------------------------- the person's screen */
function taskExtras(t){
 const back=peopleExtras(t)+(t.sent_back?`<div class="sent-back" role="note">${svgIcon('send_back')}<div><strong>Sent back${t.sent_back.by?` by ${esc(t.sent_back.by)}`:''} for changes</strong>${t.sent_back.note?`<p>“${esc(t.sent_back.note)}”</p>`:'<p>Check your answers, change what is needed and send it again.</p>'}</div></div>`:'');
 if(t.kind==='confirm')return back+`<div class="confirm-read" tabindex="0" aria-label="What you are asked to confirm">${esc(t.text)}</div>`;
 return back;
}
function taskNote(t){return t.kind==='task'?`<div class="task-note"><label for="task-note">Add a note (optional)</label><textarea id="task-note" maxlength="2000" placeholder="Anything the next person should know"></textarea></div>`:'';}
function taskButtons(t){
 const rows=t.buttons||[];
 if(t.kind==='input'||t.kind==='task'&&rows.length===1&&rows[0].key==='done'&&rows[0].label==='Done')return null;
 return rows.map((b,i)=>btn('complete-outcome',esc(b.label),i===0?'check':'',i===0?'primary':'',`data-id="${esc(b.key)}" ${S.formPreview?'disabled':''}`)).join('');
}
function stepHistory(p,step){
 const rows=(p.history||[]).filter(h=>step&&h.step===step.key&&!/ — done\.$/.test(h.text));
 if(!rows.length)return '';
 return `<div class="step-history"><p class="again-title">${svgIcon('history')}What happened</p><ol>${rows.slice(-8).map(h=>`<li><span>${esc(h.text)}</span><small>${esc(localTime(h.at))}${h.by?' · '+esc(h.by):''}</small></li>`).join('')}</ol></div>`;
}
/* "More possibilities" stays open once opened, so the new steps are one
   click away after each change (the step list is redrawn on every edit). */
document.addEventListener('toggle',e=>{if(e.target?.matches?.('.palette details[data-more]'))S.paletteMore=e.target.open;},true);
