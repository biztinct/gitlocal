/* Stages on the workbench (WF2 P3a): what each section is, what already
   happens there, the "When …" sentence, the By stage board, the Stages sheet
   and the record's progress track. Everything here ADDS to the shipped views
   (owner ruling R1); the definition still changes only through mutate(). */

/* ------------------------------------------------------------ helpers */
function lowerFirst(text){
 const t=String(text||'').trim();
 return /^[A-Z]{2}/.test(t)?t:t.slice(0,1).toLowerCase()+t.slice(1);
}
/* Lower-case the first word of a sentence only when it is an ordinary word,
   so a person's name ("Mai presses …") keeps its capital. */
const SOFT_WORDS=new Set(['the','a','an','every','each','someone','somebody','by','when','it','they','records','all','no','nobody','waiting','whoever','one','any']);
function softLower(text){const t=String(text||'').trim(),first=t.split(/\s/)[0];return SOFT_WORDS.has(first.toLowerCase())?first.toLowerCase()+t.slice(first.length):t;}
function listWords(items,last='and'){
 const xs=items.filter(Boolean);
 return xs.length<2?(xs[0]||''):xs.slice(0,-1).join(', ')+' '+last+' '+xs.at(-1);
}
const article=word=>/^[aeiou]/i.test(word)?'an':'a';
const plural=(n,one,many)=>`${n} ${n===1?one:many||one+'s'}`;
function localTime(value){
 if(!value)return '';
 const text=String(value),d=new Date(text.replace(' ','T')+(/[zZ]$|[+-]\d\d:?\d\d$/.test(text)?'':'Z'));
 return isNaN(d)?text:d.toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'});
}
const contract=()=>S.w?.metadata.contract||{};
const catalogue=()=>S.w?.metadata.stage_catalogue?.stages||[];
const areaName=()=>contract().area||S.w?.module||'';
const possessive=name=>/s$/i.test(name)?name+'’':name+'’s';
const isRecordFlow=()=>!!S.w?.source_model;
const ownRows=()=>!!contract().own_stage_rows;
const bindKey=b=>!b?null:b.kind==='core'?String(b.value):'yours:'+b.id;
const catId=b=>!b?null:b.kind==='core'?'core:'+b.value:'yours:'+b.id;
function catRow(bind){const id=catId(bind);return id?catalogue().find(s=>s.id===id)||null:null;}
function catIndex(bind){const id=catId(bind);return catalogue().findIndex(s=>s.id===id);}
function areaOwner(){return (S.w?.metadata.owners||[]).find(o=>!['approvals','access','settings'].includes(o.key));}

/* ------------------------------------------------- "already happens" */
function existingRows(){return S.existing?.state==='ready'?S.existing.rows:[];}
async function loadExisting(){
 const w=S.w;if(!w)return;
 S.existing={state:'loading',rows:[],workflow:w.id};
 try{
  const rows=await rpc('existing_behaviour',[w.source_model||'',w.id]);
  if(S.w!==w)return;
  S.existing={state:'ready',rows:rows||[],workflow:w.id};
 }catch(e){if(S.w!==w)return;S.existing={state:'error',rows:[],workflow:w.id};}
 refreshWork();
}
async function refreshCatalogue(){
 if(!S.w)return;
 const cat=await rpc('stage_catalogue',[S.w.source_model||'',S.w.source_model?null:S.w.id]);
 S.w.metadata.stage_catalogue=cat;
}
/* Redraw only the work area (or Review), so an open inspector keeps what
   the person is typing when late data arrives. */
function refreshWork(){
 if(S.page!=='editor')return;
 const undo=$('.editor-head [data-act="undo"]'),redo=$('.editor-head [data-act="redo"]');
 if(undo)undo.disabled=!S.history.length;if(redo)redo.disabled=!S.future.length;
 if(S.tab==='build'){
  const wa=$('.builder .workarea');if(!wa)return;
  const x=wa.scrollLeft,y=wa.scrollTop;wa.innerHTML=workView();wa.scrollLeft=x;wa.scrollTop=y;
 }else if(S.tab==='review'&&!document.activeElement?.matches('input,textarea,select'))render();
 if($('#sheet')?.open)renderSheet();
}
function existingProblem(){
 return S.existing?.state==='error'?`<div class="existing-error" role="status">${svgIcon('info')}<span>Could not load what already happens here.</span>${btn('existing-retry','Try again','history','small plain')}</div>`:'';
}
const EFFECT_ICON={message:'email',todo:'task',record:'input',reminder:'bell',change:'state'};
function effectLink(e){
 const s=e.settings;if(!s)return '';
 if(s.workflow_id)return btn('open-workflow','Open','external','small link',`data-id="${Number(s.workflow_id)}" aria-label="Open ${esc(e.owner)}"`);
 const owner=(S.w?.metadata.owners||[]).find(o=>o.action===s.action);
 return owner?btn('resource','Open','external','small link',`data-key="${esc(owner.key)}" aria-label="Open ${esc(owner.owner)}"`):'';
}
function effectRow(e){
 return `<div class="already-row"><span class="already-icon">${svgIcon(EFFECT_ICON[e.kind]||'state')}</span><div class="grow"><p>${esc(e.text)}</p><div class="already-foot"><small>${esc(e.owner)}</small>${effectLink(e)}</div>${e.detail?`<small class="already-detail">${esc(e.detail)}</small>`:''}</div></div>`;
}
function alreadyBlock(info,title='Already happens here',limit=0){
 const rows=info.effects;if(!rows.length)return '';
 const shown=limit&&rows.length>limit?rows.slice(0,limit):rows,rest=rows.slice(shown.length);
 return `<div class="already"><p class="already-title">${title}</p>${shown.map(effectRow).join('')}${rest.length?`<details class="already-more"><summary>${svgIcon('down')}${plural(rest.length,'more thing')}</summary>${rest.map(effectRow).join('')}</details>`:''}</div>`;
}

/* --------------------------------------------------- one section, described */
function sectionInfo(i,d=S.w.definition){
 const st=d.stages[i]||{},bind=st.bind||null,row=catRow(bind);
 const kind=!bind?'heading':!row?'missing':row.kind==='core'?'area':'yours';
 const key=bindKey(bind);
 return {index:i,kind,bind,row,name:row?.name||st.name||'',
  enters:row?.enters||'',
  effects:key?existingRows().filter(e=>e.stage!==null&&e.stage!==undefined&&String(e.stage)===key):[],
  steps:d.nodes.filter(n=>n.stage===i&&n.type!=='trigger').length};
}
function sectionTitle(i){return S.w?sectionInfo(i).name:'';}
function tagWords(info){
 if(info.kind==='area')return `${areaName()} owns this stage`;
 if(info.kind==='yours')return isRecordFlow()&&info.row.counts_as?`Your stage · counts as ${info.row.counts_as} in ${areaName()}`:'Your stage';
 if(info.kind==='missing')return 'This stage no longer exists';
 return 'Heading';
}
const TAG_ICON={area:'lock',yours:'flag',missing:'alert',heading:'heading'};
function stageTag(info){return `<span class="stage-tag ${info.kind}">${svgIcon(TAG_ICON[info.kind])}<span>${esc(tagWords(info))}</span></span>`;}
function getsHere(info){return info.enters?`<p class="gets-here">${svgIcon('arrow')}<span>Gets here when: ${esc(softLower(info.enters))}</span></p>`:'';}
function sectionMeta(info,limit=0){return `<div class="stage-meta">${stageTag(info)}${getsHere(info)}</div>${alreadyBlock(info,'Already happens here',limit)}`;}
function exitsNote(){
 if(!S.w||!S.w.definition.stages.some(s=>s.bind))return '';
 const exits=catalogue().filter(s=>s.exit);if(!exits.length)return '';
 const text=exits.length===1&&exits[0].enters?`If ${softLower(exits[0].enters)}, it becomes ${exits[0].name}.`:`If it becomes ${listWords(exits.map(e=>e.name),'or')}, it stops there.`;
 return `<p class="exits-note">${svgIcon('stop')}<span>${esc(text)} Steps after that point do not run.</span></p>`;
}
/* Across: the tag sits in the heading; what already happens folds into one line. */
function acrossMeta(i){
 if(!S.w)return '';const info=sectionInfo(i);
 return {tag:stageTag(info),more:`${getsHere(info)}${info.effects.length?`<details class="already-line"><summary>${svgIcon('info')}${plural(info.effects.length,'thing')} already happen${info.effects.length===1?'s':''} here</summary>${info.effects.map(effectRow).join('')}</details>`:''}`};
}
/* Flowchart: the label keeps its height; a chip opens a popover. */
function flowLabelExtras(i){
 if(!S.w)return '';const info=sectionInfo(i);
 return `<span class="flow-tag ${info.kind}" title="${esc(tagWords(info))}" aria-label="${esc(tagWords(info))}">${svgIcon(TAG_ICON[info.kind])}</span>${info.effects.length?`<button class="flow-chip" data-act="already-pop" data-index="${i}" aria-haspopup="dialog">${info.effects.length} already happen${info.effects.length===1?'s':''}</button>`:''}`;
}
function openPopover(anchor,title,html){
 let p=$('#popover');
 if(!p){p=document.createElement('div');p.id='popover';p.setAttribute('role','dialog');document.body.appendChild(p);}
 p.innerHTML=`<div class="row between popover-head"><strong>${esc(title)}</strong>${btn('popover-close','','close','plain small','aria-label="Close"')}</div>${html}`;
 p.setAttribute('aria-label',title);p.hidden=false;
 const r=anchor.getBoundingClientRect(),w=Math.min(380,innerWidth-24);
 p.style.width=w+'px';p.style.left=Math.max(12,Math.min(r.left,innerWidth-w-12))+'px';
 const below=r.bottom+8,height=p.offsetHeight;
 p.style.top=(below+height>innerHeight-12&&r.top-height-8>12?r.top-height-8:below)+'px';
 S.popoverAnchor=anchor;p.querySelector('button')?.focus();
}
function closePopover(focus=true){
 const p=$('#popover');if(!p||p.hidden)return;p.hidden=true;
 if(focus&&S.popoverAnchor?.isConnected)S.popoverAnchor.focus();S.popoverAnchor=null;
}
document.addEventListener('pointerdown',e=>{const p=$('#popover');if(p&&!p.hidden&&!p.contains(e.target)&&!e.target.closest('[data-act="already-pop"]'))closePopover(false);});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('#popover')&&!$('#popover').hidden){closePopover();e.preventDefault();}});

/* ----------------------------------------------------- the "When …" sentence */
function whenWords(){
 const w=S.w,d=w.definition,t=d.trigger||{},fields=w.metadata.fields||[];
 const label=String(contract().label||w.module||'record').split(' ').map(x=>/^[A-Z0-9]{2,}$/.test(x)?x:x.toLowerCase()).join(' ');
 if(!w.source_model)return {subject:'someone',verb:t.kind==='manual'||!t.kind?`starts ${d.name}`:'starts it',scope:''};
 let verb={manual:'is started by a person',created:'is created',approval_applied:'has its approval finished'}[t.kind];
 if(t.kind==='changed'){const names=(t.fields||[]).map(k=>fields.find(f=>f.key===k)?.label).filter(Boolean);verb=names.length?`has ${listWords(names,'or')} changed`:'has a chosen field changed';}
 if(t.kind==='date'){
  const date=fields.find(f=>f.key===t.date_field)?.label,unit={minutes:'minute',hour:'hour',day:'day',month:'month'}[t.unit]||'day';
  verb=!date?'reaches a date you choose':Number(t.delay)?`is ${plural(Number(t.delay),unit)} ${t.mode==='before'?'before':'after'} its ${date}`:`reaches its ${date}`;
 }
 const ruled=d.scope?.rules?.length;
 return {subject:`${article(label)} ${label}`,verb:verb||'is started by a person',scope:ruled?`for ${softLower(w.scope_summary||'matching records')}`:'for everyone'};
}
function whenSentence(){
 const s=whenWords(),say=`When ${s.subject} ${s.verb}${s.scope?', '+s.scope:''}`;
 return `<section class="when-card" id="when-card"><button class="when-say" data-act="node" data-id="trigger" aria-label="${esc(say)}. Change when this starts."><span class="when-word">When</span> <span class="when-chip">${esc(s.subject)}</span> <span class="when-chip">${esc(s.verb)}</span>${s.scope?`<span class="when-comma">,</span> <span class="when-chip">${esc(s.scope)}</span>`:''}</button>${btn('node','Change','design','small','data-id="trigger" aria-label="Change when this workflow starts"')}</section>`;
}
function refreshWhen(){const el=$('#when-card');if(el&&!el.contains(document.activeElement))el.outerHTML=whenSentence();}

/* ------------------------------------------------------------- By stage */
function byStage(d){
 const ts=targets(d);
 const columns=d.stages.map((st,i)=>{
  const info=sectionInfo(i,d),ids=d.order.filter(k=>byId(d,k).stage===i),next=d.order.find(k=>byId(d,k).stage>i)||null;
  const end=ts.find(t=>t.key==='main'&&t.stage===i&&t.before===next),empty=!ids.some(k=>k!=='trigger');
  return `<section class="stage-column kind-${info.kind}" aria-label="Stage ${i+1}: ${esc(info.name)}"><header class="column-head"><div class="stage-head"><span class="stage-number">${i+1}</span><h3>${esc(info.name)}</h3><span class="column-count" aria-label="${plural(info.steps,'step')}">${info.steps}</span></div>${sectionMeta(info,2)}</header><div class="column-body">${journeySeq(d,ts,ids,'main',i,next)}${empty?'<p class="column-empty">No steps here yet. Add one, or drag a card in.</p>':''}${end?btn('add-at','Add a step','plus','column-add',`data-id="${esc(end.id)}"`):''}</div></section>`;
 }).join('');
 return `<div class="stage-board">${columns}<button class="stage-column add-stage-column" data-act="stages" data-at="end">${svgIcon('plus')}<strong>Add a stage</strong><small>${isRecordFlow()&&!ownRows()?`Your own, or one of ${esc(possessive(areaName()))}`:'Give your steps a new place'}</small></button></div>${exitsNote()}`;
}

/* ----------------------------------------------------- section changes */
/* The one renumbering (moved here from the old sections dialog): `map`
   turns an old section index into its new one. The start stays first, the
   main path stays in section order, `workflow.*` filters follow. */
function renumberSections(d,map){
 for(const n of d.nodes){
  if(n.type==='trigger'){n.stage=0;continue;}
  n.stage=map(n.stage);
  for(const r of [n.when,n.wait_for,...(n.branches||[]).map(b=>b.condition)].flatMap(conditionLeaves))
   if(r.field?.startsWith('workflow.')){const f=v=>{const m=map(v);return m<0?v:m;};r.value=Array.isArray(r.value)?r.value.map(f):f(r.value);}
 }
 const rest=d.order.filter(k=>k!=='trigger');
 rest.sort((a,b)=>byId(d,a).stage-byId(d,b).stage);
 d.order=['trigger',...rest];
}
function insertSection(d,at,section){renumberSections(d,i=>i>=at?i+1:i);d.stages.splice(at,0,section);}
function filtersUse(d,i){
 return d.nodes.flatMap(n=>[n.when,n.wait_for,...(n.branches||[]).map(b=>b.condition)]).flatMap(conditionLeaves)
  .some(r=>r.field?.startsWith('workflow.')&&[r.value].flat().includes(i));
}
function removeSection(d,i){renumberSections(d,k=>k===i?-1:k>i?k-1:k);d.stages.splice(i,1);}
/* Where a stage from the record's list belongs among this workflow's sections. */
function placeFor(row){
 const d=S.w.definition,ci=catalogue().findIndex(s=>s.id===row.id);let at=null;
 d.stages.forEach((s,i)=>{if(s.bind&&catIndex(s.bind)>=0&&catIndex(s.bind)<ci)at=i+1;});
 if(at!==null)return at;
 const later=d.stages.findIndex(s=>s.bind&&catIndex(s.bind)>ci);
 return later>=0?later:d.stages.length;
}
/* The company's stage list in the order this workflow's sections need:
   per area stage, the user-made stages bound here (in section order) first. */
function desiredOrder(sections,anchors={}){
 const cat=catalogue().filter(s=>!s.exit),yours=cat.filter(s=>s.kind==='yours');
 const bound=sections.filter(s=>s.bind?.kind==='yours').map(s=>s.bind.id);
 const group=a=>{const g=yours.filter(s=>String(anchors[s.key]??s.anchor??'')===a);return [...bound.map(id=>g.find(s=>s.key===id)).filter(Boolean),...g.filter(s=>!bound.includes(s.key))].map(s=>s.key);};
 if(!isRecordFlow())return group('');
 return cat.filter(s=>s.kind==='core').flatMap(s=>[String(s.key),...group(String(s.key))]);
}
const currentOrder=()=>catalogue().filter(s=>!s.exit).map(s=>s.kind==='core'?String(s.key):s.key);
async function syncOrder(sections,anchors={}){
 const want=desiredOrder(sections,anchors);
 if(JSON.stringify(want)===JSON.stringify(currentOrder()))return;
 S.w.metadata.stage_catalogue=await rpc('stage_reorder',[S.w.source_model||'',S.w.source_model?null:S.w.id,want]);
}
function anchorBefore(sections,at){
 for(let i=at-1;i>=0;i--){const b=sections[i].bind;if(!b)continue;if(b.kind==='core')return String(b.value);const r=catRow(b);if(r)return String(r.anchor||'');}
 return null;
}
function anchorChoices(sections,at){
 const nextBound=sections.slice(at).find(s=>s.bind&&catIndex(s.bind)>=0),limit=nextBound?catIndex(nextBound.bind):Infinity;
 return catalogue().filter((s,i)=>s.kind==='core'&&!s.exit&&i<limit);
}
/* Move section `from` so it ends at index `to` (sheet arrows and drag). */
async function moveSection(from,to){
 const d=S.w.definition,n=d.stages.length;S.sheetRename=null;S.sheetBlocked=null;
 if(to<0||to>=n||from===to)return;
 const order=[...d.stages.keys()];order.splice(to,0,order.splice(from,1)[0]);
 const next=order.map(i=>d.stages[i]);
 const cores=next.filter(s=>s.bind?.kind==='core').map(s=>catIndex(s.bind));
 if(cores.some((c,i)=>i&&c<cores[i-1]))throw Error(`${possessive(areaName())} stages keep their own order.`);
 const anchors={},said=[];
 if(isRecordFlow()){
  const nearest=(arr,idx)=>{for(let k=idx-1;k>=0;k--)if(arr[k].bind?.kind==='core')return String(arr[k].bind.value);return null;};
  d.stages.forEach((s,i)=>{
   if(s.bind?.kind!=='yours')return;
   const before=nearest(d.stages,i),after=nearest(next,order.indexOf(i));
   if(before===after)return;
   if(after===null)throw Error(`Your own stages come after one of ${possessive(areaName())} stages.`);
   anchors[s.bind.id]=after;said.push(`“${catRow(s.bind)?.name||s.name}” will now count as ${catalogue().find(c=>c.id==='core:'+after)?.name||after}.`);
  });
 }
 const want=desiredOrder(next,anchors),pos=b=>want.indexOf(b.kind==='core'?String(b.value):b.id);
 const bound=next.filter(s=>s.bind&&catIndex(s.bind)>=0).map(s=>pos(s.bind));
 if(bound.some((p,i)=>i&&p<bound[i-1]))throw Error(`Those stages follow different ${areaName()} stages, so they keep this order.`);
 await syncOrder(next,anchors);
 mutate(()=>{renumberSections(S.w.definition,i=>order.indexOf(i));S.w.definition.stages=next;},false);
 S.sheetFocus=`[data-row="${to}"] [data-act="${S.sheetMoveAct||'section-up'}"]`;
 if(said.length){notify(said.join(' '));loadExisting();}
 refreshWork();renderSheet();
}

/* After Undo/Redo: a move may have made a stage of yours count as another
   stage of the record. If the restored order no longer fits the company list,
   put the stage back after the record's stage it now follows (the reverse of
   the move), so one Undo really undoes one move. */
async function realignStages(){
 if(!S.w||!isRecordFlow())return;
 const sections=S.w.definition.stages,cur=currentOrder(),pos=b=>cur.indexOf(b.kind==='core'?String(b.value):b.id);
 const bound=sections.filter(x=>x.bind&&catIndex(x.bind)>=0).map(x=>pos(x.bind));
 if(!bound.some((p,i)=>i&&p<bound[i-1]))return;
 const anchors={},said=[];
 sections.forEach((x,i)=>{
  if(x.bind?.kind!=='yours')return;
  let near=null;for(let k=i-1;k>=0;k--)if(sections[k].bind?.kind==='core'){near=String(sections[k].bind.value);break;}
  const row=catRow(x.bind);
  if(near!==null&&row&&String(row.anchor)!==near){anchors[x.bind.id]=near;said.push(`“${row.name}” counts as ${catalogue().find(c=>c.id==='core:'+near)?.name||near} again.`);}
 });
 if(!said.length)return;
 try{await syncOrder(sections,anchors);notify(said.join(' '));loadExisting();}
 catch(e){notify(e.message,true);}
}

/* ------------------------------------------------------------- the sheet */
function openSheet(at=null){
 const sheet=$('#sheet');
 S.sheetReturn=document.activeElement;
 S.sheetBlocked=null;S.sheetRename=null;
 S.stageForm=at===null?null:newStageForm(at==='end'?S.w.definition.stages.length:Number(at));
 renderSheet();
 if(!sheet.open)sheet.showModal();
 (S.stageForm?$('#sf-name'):sheet.querySelector('.sheet-head button'))?.focus();
}
function closeSheet(){const sheet=$('#sheet');if(sheet.open)sheet.close();}
function sheetClosed(){
 S.stageForm=null;S.sheetBlocked=null;S.sheetRename=null;
 const back=S.sheetReturn?.isConnected&&S.sheetReturn!==document.body&&!$('#sheet').contains(S.sheetReturn)?S.sheetReturn:$('.viewbar [data-act="stages"]');
 back?.focus();S.sheetReturn=null;
}
/* A real stage needs one of the record's own stages before it (or a new process). */
function canRealAt(at,anchor){
 if(ownRows())return false;if(!isRecordFlow())return true;
 return anchor!==null&&anchor!==undefined||anchorChoices(S.w.definition.stages,at).length>0;
}
function newStageForm(at,stage=null){
 const sections=S.w.definition.stages,anchor=anchorBefore(sections,at);
 const choices=anchorChoices(sections,at);
 return {mode:stage?'edit':'add',at,stageId:stage?.key||null,name:stage?.name||'',
  kind:stage||canRealAt(at,anchor)?'real':'heading',enter:stage?.enter||'auto',owner:clone(stage?.enter_owner&&Object.keys(stage.enter_owner).length?stage.enter_owner:{kind:'initiator'}),
  rule:stage?.enter_rule?.rules?.length?clone(stage.enter_rule):undefined,target:stage?.target_hours||0,
  anchor:stage?String(stage.anchor||''):anchor??(choices.at(-1)?String(choices.at(-1).key):null),anchorFixed:!!stage||anchor!==null,error:''};
}
function sheetIntro(){
 if(!isRecordFlow())return 'This is your own process, so every stage is yours.';
 if(ownRows())return `${contract().label||'Record'} stages belong to ${areaName()}. Here you can use them and group steps under headings.`;
 if(!catalogue().some(s=>s.kind==='core'))return `${contract().label||'These'} records have no stages of their own, so this workflow groups its steps under headings.`;
 return `Stages with a lock belong to ${areaName()}. You can add your own between them, here, with no set-up by anyone else.`;
}
const TARGETS=[[0,'No target'],[24,'1 day'],[72,'3 days'],[168,'1 week'],[336,'2 weeks']];
function stageForm(){
 const f=S.stageForm,sections=S.w.definition.stages,prev=sections[f.at-1],prevName=prev?sectionInfo(f.at-1).name:'';
 const anchorName=catalogue().find(s=>s.kind==='core'&&String(s.key)===String(f.anchor))?.name;
 const choices=anchorChoices(sections,f.at),canReal=f.mode==='edit'||canRealAt(f.at,f.anchorFixed?f.anchor:null);
 const radio=(name,value,current,icon,title,text)=>`<label class="choice-card"><input type="radio" name="${name}" value="${value}" data-form="${name}" ${current===value?'checked':''}><span class="choice-icon">${svgIcon(icon)}</span><span><strong>${title}</strong><small>${text}</small></span></label>`;
 const real=isRecordFlow()?`People see it on the record. ${anchorName?`It sits after ${esc(anchorName)}, and ${esc(areaName())} still treats the record as ${esc(anchorName)}`:`${esc(areaName())} still treats the record as the stage before it`}, so its reports and rules keep working.`:'People see where each request is, and the work waits for it.';
 const heading=f.mode==='edit'?'':`<fieldset><legend>What is it?</legend>${canReal?radio('kind','real',f.kind,'flag','A real stage',real):''}${radio('kind','heading',f.kind,'heading','Just a heading','Groups steps in this picture only.')}${!canReal&&!ownRows()&&isRecordFlow()&&catalogue().some(s=>s.kind==='core')?`<p class="form-note">${svgIcon('info')}<span>A real stage here must come after one of ${esc(possessive(areaName()))} stages. Add theirs first, or add it further down.</span></p>`:''}</fieldset>`;
 let more='';
 if(f.kind==='real'&&canReal){
  if(isRecordFlow()&&!f.anchorFixed)more+=field(`<span id="sf-anchor-label">Which ${esc(areaName())} stage does it come after?</span>`,`<select id="sf-anchor" data-form="anchor" aria-labelledby="sf-anchor-label">${opts(choices.map(s=>[String(s.key),s.name]),f.anchor,null)}</select>`);
  const thing=isRecordFlow()?'record':'request';
  more+=`<fieldset><legend>How does a ${thing} get here?</legend>${radio('enter','auto',f.enter,'arrow','By itself','When the steps before are finished.')}${radio('enter','person',f.enter,'people','A person moves it',`They get a “Move to” button on the ${thing}.`)}${isRecordFlow()?radio('enter','rule',f.enter,'branch','When a rule is true','For example: the amount is over a limit.'):''}</fieldset>`;
  if(f.enter==='person')more+=`<div class="form-sub">${ownerControl('stageForm.owner',f.owner,'Who may move it',!isRecordFlow())}</div>`;
  if(f.enter==='rule')more+=`<div class="form-sub"><label>The rule</label>${filterEditor(f.rule,'stageForm.rule',S.w.metadata.fields)}</div>`;
  const rows=TARGETS.some(t=>t[0]===f.target)?TARGETS:[...TARGETS,[f.target,plural(f.target,'hour')]];
  more+=field('<span id="sf-target-label">Target time in this stage</span>',`<select id="sf-target" data-form="target" aria-labelledby="sf-target-label">${opts(rows,f.target,null)}</select>`,'Shown beside the stage. Late work is chased by the approval reminders, never twice.');
 }
 const title=f.mode==='edit'?`Change “${esc(f.name)}”`:prevName?`New stage after “${esc(prevName)}”`:'New stage at the start';
 return `<li class="stage-form-wrap"><div class="stage-form" role="group" aria-labelledby="sf-title"><h3 id="sf-title">${title}</h3>${field('<span id="sf-name-label">Name</span>',`<input id="sf-name" data-form="name" maxlength="40" value="${esc(f.name)}" placeholder="For example: Payment scheduled" aria-labelledby="sf-name-label" autocomplete="off">`)}${ownRows()?`<p class="form-note">${svgIcon('lock')}<span>${esc(contract().label||'Record')} stages are managed in ${esc(areaName())}. This adds a heading.</span></p>`:''}${heading}${more}${f.error?`<p class="form-error" role="alert">${svgIcon('alert')}<span>${esc(f.error)}</span></p>`:''}<div class="row form-buttons">${btn('sf-cancel','Cancel','','plain')}${btn('sf-save',f.mode==='edit'?'Save changes':f.kind==='heading'?'Add this heading':'Add this stage','check','primary')}</div></div></li>`;
}
function stageRow(i){
 const d=S.w.definition,info=sectionInfo(i),n=d.stages.length,row=info.row;
 const steps=plural(info.steps,'step');
 const facts=[info.enters?`Gets here when: ${esc(softLower(info.enters))}`:'',info.steps?steps:'No steps yet'];
 if(info.kind==='yours'&&row.target_hours)facts.push(`Target ${esc(TARGETS.find(t=>t[0]===row.target_hours)?.[1]||plural(row.target_hours,'hour'))}`);
 if(info.kind==='yours'&&row.count)facts.push(`<strong class="here-now">${row.count===1?'1 record is':row.count+' records are'} here now</strong>`);
 const owner=areaOwner(),act=[];
 if(info.kind==='area'){
  if(row.renamable)act.push(btn('shared-rename','Rename','design','small plain',`data-index="${i}"`));
  if(owner)act.push(btn('resource',`Open in ${esc(areaName())}`,'external','small plain',`data-key="${esc(owner.key)}"`));
  act.push(btn('section-remove','Stop using here','','small plain',`data-index="${i}"`));
 }else if(info.kind==='yours'){
  act.push(btn('sf-edit','Change','design','small plain',`data-index="${i}"`));
  act.push(btn('section-remove','Remove from this workflow','','small plain',`data-index="${i}"`));
  act.push(btn('stage-delete','Delete for everyone','trash','small plain danger',`data-index="${i}"`));
 }else{
  act.push(btn('heading-rename','Rename','design','small plain',`data-index="${i}"`));
  if(info.kind==='missing')act.push(btn('section-unbind','Make it a heading','heading','small plain',`data-index="${i}"`));
  act.push(btn('section-remove','Remove','','small plain',`data-index="${i}"`));
 }
 const name=S.sheetRename===i?`<input class="rename-input" data-heading-name="${i}" value="${esc(d.stages[i].name)}" maxlength="60" aria-label="Heading name">`:`<strong class="stage-row-name">${esc(info.name)}</strong>`;
 const blocked=S.sheetBlocked===i?`<div class="row-blocked" role="alert">${svgIcon('info')}<span>${info.steps===1?'Move its step first.':`Move its ${steps} first.`}</span>${btn('section-move-steps',`Move ${info.steps===1?'it':'them'} to “${esc(sectionInfo(i?i-1:1).name)}”`,'arrow','small',`data-index="${i}"`)}</div>`:'';
 return `<li class="stage-row kind-${info.kind}" data-row="${i}"><div class="stage-row-main"><span class="row-grip" data-section-drag="${i}" title="Drag to reorder" aria-hidden="true">${svgIcon('grip')}</span><span class="stage-number">${i+1}</span><div class="grow"><div class="row wrap stage-row-title">${name}${stageTag(info)}</div><p class="stage-row-facts">${facts.filter(Boolean).join(' · ')}</p></div><div class="row-move">${btn('section-up','','up','small plain',`data-index="${i}" aria-label="Move ${esc(info.name)} earlier" ${i===0?'disabled':''}`)}${btn('section-down','','down','small plain',`data-index="${i}" aria-label="Move ${esc(info.name)} later" ${i===n-1?'disabled':''}`)}</div></div><div class="row wrap stage-row-actions">${act.join('')}</div>${blocked}</li>`;
}
function addSlot(at){
 if(S.stageForm&&S.stageForm.mode==='add'&&S.stageForm.at===at)return stageForm();
 const last=at===S.w.definition.stages.length;
 return `<li class="add-slot" data-section-slot="${at}">${btn('sf-open',last?'Add a stage at the end':'Add a stage here','plus','small plain',`data-at="${at}"`)}</li>`;
}
function notUsedStrip(){
 if(!isRecordFlow())return '';
 const used=new Set(S.w.definition.stages.map(s=>catId(s.bind)).filter(Boolean));
 const free=catalogue().filter(s=>!s.exit&&!used.has(s.id));
 if(!free.length)return '';
 const core=free.filter(s=>s.kind==='core');
 return `<section class="not-used"><div class="row between wrap"><h3>Not used yet</h3>${core.length>1?btn('use-all','Use all of them','plus','small'):''}</div><p class="muted small">One click puts it in its place.</p><div class="row wrap">${free.map(s=>btn('use-stage',`${esc(s.name)}${s.kind==='yours'?' · your stage':''}`,s.kind==='core'?'lock':'flag','small chip-button',`data-id="${esc(s.id)}"`)).join('')}</div></section>`;
}
function anyTime(){
 const rows=existingRows().filter(e=>e.stage===null||e.stage===undefined);
 return rows.length?`<section class="any-time"><h3>Any time</h3><p class="muted small">Not tied to one stage.</p>${rows.map(effectRow).join('')}</section>`:'';
}
function focusKey(el){
 if(el.id)return '#'+CSS.escape(el.id);
 const row=el.closest('[data-row]'),act=el.dataset.act,attrs=['index','at','id','form','edit'].filter(k=>el.dataset[k]!==undefined).map(k=>`[data-${k}="${CSS.escape(el.dataset[k])}"]`).join('');
 return act||attrs?`${row?`[data-row="${row.dataset.row}"] `:''}${act?`[data-act="${act}"]`:''}${attrs}`:'';
}
function renderSheet(){
 const sheet=$('#sheet');if(!sheet||!S.w)return;
 const body=sheet.querySelector('.sheet-body'),top=body?.scrollTop||0,active=document.activeElement,keep=active&&sheet.contains(active)?focusKey(active):'';
 const d=S.w.definition,hiring=ownRows()&&areaOwner();
 const rows=d.stages.map((_,i)=>(S.stageForm?.mode==='edit'&&S.stageForm.index===i?stageForm():stageRow(i))+addSlot(i+1)).join('');
 sheet.innerHTML=`<header class="sheet-head"><div><div class="eyebrow">${esc(S.w.definition.name)}</div><h2 id="sheet-title">Stages</h2></div>${btn('sheet-done','Done','check','sheet-done')}</header><div class="sheet-body"><p class="sheet-intro">${esc(sheetIntro())}</p>${hiring?`<div class="banner sheet-banner">${svgIcon('lock')}<span>${esc(contract().label||'Record')} stages are managed in ${esc(areaName())}.</span>${btn('resource',`Open ${esc(areaName())} set-up`,'external','small',`data-key="${esc(hiring.key)}"`)}</div>`:''}${existingProblem()}<ol class="stage-list">${rows}</ol>${notUsedStrip()}${anyTime()}${exitsNote()}</div>`;
 const nb=sheet.querySelector('.sheet-body');if(nb)nb.scrollTop=top;
 const want=S.sheetFocus?sheet.querySelector(S.sheetFocus):keep?sheet.querySelector(keep):null;
 S.sheetFocus=null;want?.focus();
}
async function saveStageForm(){
 const f=S.stageForm,name=($('#sf-name')?.value??f.name).trim();f.name=name;
 if(!name){f.error='Give it a name.';renderSheet();$('#sf-name')?.focus();return;}
 if(f.kind==='real'&&f.enter==='person'&&['user','role'].includes(f.owner.kind)&&!f.owner.id){f.error='Choose who may move it.';renderSheet();return;}
 if(f.kind==='real'&&f.enter==='rule'&&!f.rule?.rules?.length){f.error='Add the rule that moves records here.';renderSheet();return;}
 const values={name,enter:f.enter,target_hours:Number(f.target)||0};
 if(f.enter==='person')values.enter_owner=f.owner;
 if(f.enter==='rule')values.enter_rule=f.rule;
 const model=S.w.source_model||'',wid=S.w.source_model?null:S.w.id;
 try{
  if(f.mode==='edit'){
   S.w.metadata.stage_catalogue=await rpc('stage_update',[f.stageId,values]);
   const i=f.index;if(S.w.definition.stages[i].name!==name)mutate(()=>{S.w.definition.stages[i].name=name;},false);
   S.stageForm=null;S.sheetFocus=`[data-row="${i}"] [data-act="sf-edit"]`;notify(`“${name}” is saved.`);
  }else if(f.kind==='heading'||!canRealAt(f.at,f.anchorFixed?f.anchor:null)){
   mutate(()=>insertSection(S.w.definition,f.at,{name}),false);
   S.stageForm=null;S.sheetFocus=`[data-row="${f.at}"] [data-act="heading-rename"]`;S.flash=f.at;
  }else{
   if(model)values.anchor_value=f.anchor;
   const cat=await rpc('stage_create',[model,wid,values]);S.w.metadata.stage_catalogue=cat;
   const made=cat.stages.find(s=>s.kind==='yours'&&s.name.toLowerCase()===name.toLowerCase());
   const next=[...S.w.definition.stages];next.splice(f.at,0,{name,bind:{kind:'yours',id:made.key}});
   try{await syncOrder(next);}catch(e){notify(e.message,true);}
   mutate(()=>insertSection(S.w.definition,f.at,{name:made.name,bind:{kind:'yours',id:made.key}}),false);
   S.stageForm=null;S.sheetFocus=`[data-row="${f.at}"] [data-act="sf-edit"]`;S.flash=f.at;
   notify(model?`“${made.name}” added. It counts as ${made.counts_as} in ${areaName()}.`:`“${made.name}” added.`);
   loadExisting();
  }
 }catch(e){f.error=e.message;renderSheet();return;}
 refreshWork();renderSheet();
}
function useStages(rows){
 if(!rows.length)return;
 mutate(()=>{for(const row of rows){const at=placeFor(row);insertSection(S.w.definition,at,{name:row.name,bind:row.kind==='core'?{kind:'core',value:row.key}:{kind:'yours',id:row.key}});}},false);
 refreshWork();renderSheet();
}
/* A new workflow from a record type: its own stages replace the three
   default headings (one save, before any step exists). */
async function startWithOwnStages(){
 const core=catalogue().filter(s=>s.kind==='core'&&!s.exit);
 if(!core.length||!S.w)return;
 S.w.definition.stages=core.map(s=>({name:s.name,bind:{kind:'core',value:s.key}}));
 S.w.definition.nodes.forEach(n=>{n.stage=0;});
 S.dirty=true;await save();render();loadExisting();
}
async function offerOwnStages(model,holder){
 if(!holder)return;holder.innerHTML='';if(!model)return;
 holder.innerHTML='<p class="muted small own-stages-wait">Checking the stages these records already have…</p>';
 try{
  const c=await rpc('stage_catalogue',[model]),core=c.stages.filter(s=>s.kind==='core'&&!s.exit);
  if(!holder.isConnected)return;
  holder.innerHTML=c.source==='declared'&&core.length?`<label class="check own-stages"><input type="checkbox" id="own-stages" checked> Start with the ${esc(possessive(lowerFirst(c.label)))} own stages</label><p class="own-stages-preview">${core.map(s=>`<span>${esc(s.name)}</span>`).join(svgIcon('chevron'))}</p>`:'';
 }catch(e){if(holder.isConnected)holder.innerHTML='';}
}

/* ------------------------------------------------------------- actions */
async function stageAction(name,el){
 const d=S.w?.definition,i=Number(el?.dataset?.index);
 if(name==='stages'){
  if(S.page!=='editor')return false;
  if(S.tab!=='build'){S.tab='build';render();}
  openSheet(el?.dataset?.at??null);return true;
 }
 if(name==='sheet-done'){closeSheet();return true;}
 if(name==='existing-retry'){await loadExisting();return true;}
 if(name==='already-pop'){const info=sectionInfo(Number(el.dataset.index));openPopover(el,`Already happens in ${info.name}`,info.effects.map(effectRow).join(''));return true;}
 if(name==='popover-close'){closePopover();return true;}
 if(name==='open-workflow'){closeSheet();closePopover(false);await openWorkflow(el.dataset.id);return true;}
 if(name==='sf-open'){S.stageForm=newStageForm(Number(el.dataset.at));S.sheetBlocked=null;S.sheetFocus='#sf-name';renderSheet();return true;}
 if(name==='sf-cancel'){const f=S.stageForm;S.stageForm=null;S.sheetFocus=f?.mode==='edit'?`[data-row="${f.index}"] [data-act="sf-edit"]`:`[data-section-slot="${f?.at}"] button`;renderSheet();return true;}
 if(name==='sf-save'){await saveStageForm();return true;}
 if(name==='sf-edit'){const info=sectionInfo(i);S.stageForm=Object.assign(newStageForm(i+1,info.row),{index:i,kind:'real'});S.sheetFocus='#sf-name';renderSheet();return true;}
 if(name==='heading-rename'){S.sheetRename=i;S.sheetFocus=`[data-heading-name="${i}"]`;renderSheet();$(`[data-heading-name="${i}"]`)?.select();return true;}
 if(name==='section-up'||name==='section-down'){const to=name==='section-up'?i-1:i+1,last=d.stages.length-1;S.sheetMoveAct=name==='section-up'&&to===0?'section-down':name==='section-down'&&to===last?'section-up':name;try{await moveSection(i,to);}catch(e){notify(e.message,true);}return true;}
 if(name==='section-remove'){
  const info=sectionInfo(i);
  if(info.steps){S.sheetBlocked=i;S.sheetFocus='.row-blocked button';renderSheet();return true;}
  if(d.stages.length<2){notify('Keep at least one stage.',true);return true;}
  if(filtersUse(d,i)){notify('Update filters that use this stage before removing it.',true);return true;}
  mutate(()=>removeSection(S.w.definition,i),false);
  S.sheetFocus=`[data-section-slot="${i}"] button`;refreshWork();renderSheet();notify(`“${info.name}” is no longer used here. Undo is available.`);return true;
 }
 if(name==='section-move-steps'){
  const to=i?i-1:1,target=sectionInfo(to).name;
  mutate(()=>{const dd=S.w.definition;for(const n of dd.nodes)if(n.type!=='trigger'&&n.stage===i)n.stage=to;renumberSections(dd,k=>k);},false);
  S.sheetBlocked=null;S.sheetFocus=`[data-row="${i}"] [data-act="section-remove"]`;refreshWork();renderSheet();notify(`Steps moved to “${target}”. Undo is available.`);return true;
 }
 if(name==='section-unbind'){mutate(()=>{const s=S.w.definition.stages[i];delete s.bind;},false);refreshWork();renderSheet();return true;}
 if(name==='use-stage'){const row=catalogue().find(s=>s.id===el.dataset.id);if(row)useStages([row]);($('#sheet .not-used button')||$('#sheet .sheet-done'))?.focus();return true;}
 if(name==='use-all'){const used=new Set(d.stages.map(s=>catId(s.bind)));useStages(catalogue().filter(s=>s.kind==='core'&&!s.exit&&!used.has(s.id)));($('#sheet .not-used button')||$('#sheet .sheet-done'))?.focus();notify('The record’s own stages are in place. Your headings stay where they were.');return true;}
 if(name==='stage-delete'){
  const info=sectionInfo(i);
  modal(`Delete “${info.name}” for everyone?`,`<p>It leaves the company’s list of stages, so no workflow can use it any more. ${info.steps?`Its ${plural(info.steps,'step')} here stay, under a heading with the same name.`:'Its place in this workflow goes too.'}</p>`,btn('close','Keep it')+btn('stage-delete-confirm','Delete for everyone','trash','danger',`data-index="${i}"`));
  return true;
 }
 if(name==='stage-delete-confirm'){
  const info=sectionInfo(i);close();
  try{S.w.metadata.stage_catalogue=await rpc('stage_delete',[info.row.key]);}
  catch(e){S.sheetFocus=`[data-row="${i}"] [data-act="stage-delete"]`;renderSheet();notify(e.message,true);return true;}
  mutate(()=>{const dd=S.w.definition;if(info.steps){dd.stages[i]={name:info.name};}else removeSection(dd,i);},false);
  notify(info.steps?`“${info.name}” is deleted. Its steps here are now under a heading.`:`“${info.name}” is deleted.`);
  loadExisting();refreshWork();renderSheet();return true;
 }
 if(name==='shared-rename'){
  const info=sectionInfo(i);S.renamingShared={index:i,row:info.row};
  modal('Rename shared stage',field('<span id="shared-name-label">Stage name</span>',`<input id="shared-stage-name" value="${esc(info.name)}" maxlength="60" aria-labelledby="shared-name-label">`)+`<p class="muted">This renames the same stage everywhere in ${esc(areaName())}. Existing records keep their stage. Its behaviour and rules stay the same.</p>`,btn('close','Cancel')+btn('shared-rename-save','Save shared name','check','primary'));
  return true;
 }
 if(name==='shared-rename-save'){
  const r=S.renamingShared,value=$('#shared-stage-name').value.trim();
  S.w.metadata.stage_catalogue=await rpc('stage_rename_shared',[S.w.source_model,r.row.stage_id||r.row.key,value,r.row.revision]);
  close();mutate(()=>{S.w.definition.stages[r.index].name=sectionInfo(r.index).name;},false);
  S.sheetFocus=`[data-row="${r.index}"] [data-act="shared-rename"]`;refreshWork();renderSheet();return true;
 }
 if(name==='move-record'){
  const p=S.progress;
  await rpc('move_record_stage',[p.source_model||'pb.workflow.run',p.source_model?p.source_id:p.id,Number(el.dataset.id)]);
  notify(`Moved to ${el.dataset.name}.`);
  if(p.id)await action('refresh-progress');else await recordChooser(p.source_model,p.source_id);
  return true;
 }
 return false;
}
function commitHeading(input,refocus=true){
 const i=Number(input.dataset.headingName),v=input.value.trim();
 if(S.sheetRename!==i)return;
 S.sheetRename=null;
 if(v&&v!==S.w.definition.stages[i].name)mutate(()=>{S.w.definition.stages[i].name=v;},false);
 if(refocus)S.sheetFocus=`[data-row="${i}"] [data-act="heading-rename"]`;
 refreshWork();renderSheet();
}
(function wireSheet(){
 const sheet=$('#sheet');if(!sheet)return;
 sheet.addEventListener('close',sheetClosed);
 sheet.addEventListener('input',e=>{const t=e.target;if(t.dataset.form==='name'&&S.stageForm){S.stageForm.name=t.value;if(S.stageForm.error){S.stageForm.error='';}}});
 sheet.addEventListener('change',e=>{
  const t=e.target,f=S.stageForm;
  if(t.dataset.headingName!==undefined){commitHeading(t);return;}
  if(!f||!t.dataset.form||t.dataset.form==='name')return;
  if(t.dataset.form==='kind')f.kind=t.value;
  if(t.dataset.form==='enter'){f.enter=t.value;if(t.value==='rule'&&!f.rule)f.rule=undefined;}
  if(t.dataset.form==='target')f.target=Number(t.value)||0;
  if(t.dataset.form==='anchor')f.anchor=t.value;
  f.error='';S.sheetFocus=t.id?'#'+CSS.escape(t.id):`[data-form="${t.dataset.form}"][value="${CSS.escape(t.value)}"]`;renderSheet();
 });
 sheet.addEventListener('focusout',e=>{if(e.target.dataset?.headingName!==undefined&&e.target.isConnected)commitHeading(e.target,false);});
 sheet.addEventListener('keydown',e=>{
  if(e.key==='Enter'&&e.target.dataset.headingName!==undefined){e.preventDefault();commitHeading(e.target);}
  if(e.key==='Enter'&&e.target.id==='sf-name'){e.preventDefault();action('sf-save',{dataset:{}}).catch(err=>notify(err.message,true));}
  if(e.key==='Escape'&&e.target.dataset.headingName!==undefined){e.preventDefault();e.stopPropagation();S.sheetRename=null;renderSheet();}
 });
})();

/* ------------------------------------------------------- record progress */
function progressSentence(p){
 const r=p.record_stage,here=r?.current?.name;
 if(!p.id&&!p.native)return here?`No workflow has started for this record. It is at ${here}.`:'No workflow has started for this record.';
 const waiting=(p.steps||[]).find(s=>['waiting','active'].includes(s.state)&&!GROUPS.includes(byId(p.graph,s.key)?.type));
 if(waiting){const n=byId(p.graph,waiting.key);return waiting.owner?`Waiting for ${waiting.owner}: ${n?.title||'a step'}.`:`${n?.title||'Waiting'}: ${softLower(waiting.reason||'waiting')}.`;}
 if(p.gate?.reason)return p.gate.reason;
 const exit=r?.exits?.find(e=>e.here);
 if(exit&&['cancelled','done','rejected'].includes(p.state))return `Stopped: this is now ${exit.name}. Steps after that point do not run.`;
 return {done:'This workflow is finished.',cancelled:'This workflow was cancelled.',rejected:'This workflow was turned down.',held:'This workflow is on hold.',failed:'This workflow needs attention.',applied:'The approval is applied.'}[p.state]||`${status(p.state)}.`;
}
const TRACK_ICON={done:'check',here:'dot',later:'circle',passed:'minus',stopped:'stop'};
const TRACK_WORDS={done:'Done',here:'Here now',later:'Later',passed:'It went past this stage',stopped:'Stopped'};
function recordTrack(p){
 const r=p.record_stage;
 if(!r||!r.track?.length)return stageTrail(p.record_stages)+(p.native?approvalStageNote(p.record_stages):'');
 const steps=r.track.map(t=>`<li class="track-step ${t.state} kind-${t.kind}" ${t.state==='here'?'aria-current="step"':''} title="${esc(TRACK_WORDS[t.state]||'')}"><span class="track-icon">${svgIcon(TRACK_ICON[t.state]||'circle')}</span><span class="track-name"><strong>${esc(t.name)}</strong>${t.kind==='yours'&&t.counts_as?`<small>${svgIcon('flag')}counts as ${esc(t.counts_as)}</small>`:''}</span>${t.state==='here'?'<span class="here-tag">Here now</span>':`<span class="sr">${esc(TRACK_WORDS[t.state]||'')}</span>`}</li>`).join('');
 const exits=r.exits?.length?`<p class="track-exits">${svgIcon('stop')}<span>Can stop at</span>${r.exits.map(e=>`<span class="track-exit ${e.here?'here':''}">${esc(e.name)}${e.here?' · here now':''}</span>`).join('')}</p>`:'';
 const m=r.next_move,since=r.current?.since?`<small class="track-since">In ${esc(r.current.name)} since ${esc(localTime(r.current.since))}${r.current.by?` · moved by ${esc(r.current.by)}`:''}</small>`:'';
 const move=m?(m.allowed?btn('move-record',`Move to ${esc(m.name)}`,'arrow','primary',`data-id="${m.stage_id}" data-name="${esc(m.name)}"`):`<p class="track-who">${svgIcon('info')}<span>${esc(m.reason)}</span></p>`):'';
 return `<section class="record-track" aria-label="Where this record is"><div class="track-top"><p class="track-sentence">${esc(progressSentence(p))}</p>${move}</div><ol>${steps}</ol>${exits}${since}</section>${p.native?approvalStageNote(p.record_stages):''}`;
}

/* ------------------------------------------------------------- review */
function reviewAlready(){
 const rows=existingRows();if(!rows.length)return S.existing?.state==='error'?existingProblem():'';
 const groups=[],seen=new Set();
 for(const s of catalogue()){const key=s.kind==='core'?String(s.key):'yours:'+s.key,hit=rows.filter(e=>e.stage!==null&&e.stage!==undefined&&String(e.stage)===key);hit.forEach(e=>seen.add(e));if(hit.length)groups.push([s.name,hit]);}
 const other=rows.filter(e=>e.stage!==null&&e.stage!==undefined&&!seen.has(e));if(other.length)groups.push(['Other stages',other]);
 const any=rows.filter(e=>e.stage===null||e.stage===undefined);if(any.length)groups.push(['Any time',any]);
 return `<section class="review-already"><h3>Already happens for these records</h3><p class="muted small">These keep running as they are. Your steps add to them.</p>${groups.map(([name,list])=>`<div class="already-group"><h4>${esc(name)}</h4>${list.map(effectRow).join('')}</div>`).join('')}</section>`;
}
