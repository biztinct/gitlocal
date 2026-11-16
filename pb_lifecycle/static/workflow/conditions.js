/* One typed rule builder for starts, steps, paths and waits. */
function availableFields(){
 const fields=[...S.w.metadata.fields];
 for(const n of S.w.definition.nodes)for(const f of n.form?.fields||[])if(f.type!=='section')fields.push({...f,key:`step.${n.id}.${f.id}`,label:_t('%(step)s · %(field)s',{step:n.title,field:f.label})});
 /* WF2 P3b: the button a person chose is a value later steps can use. */
 for(const n of S.w.definition.nodes)if(n.type==='task'&&n.buttons?.length>1)fields.push({key:`step.${n.id}.outcome`,label:_t('%(step)s · answer',{step:n.title}),type:'selection',options:n.buttons.map(b=>[b.key,b.label])});
 return [...fields,{key:'person.user_id',label:_t('Started by · person'),type:'many2one',options:S.w.metadata.users.map(u=>[u.id,u.name])},
  {key:'person.group_ids',label:_t('Started by · access role'),type:'ids',options:S.w.metadata.starter_groups.map(g=>[g.id,g.name])},
  {key:'workflow.stage',label:_t('This workflow · current section'),type:'integer',options:S.w.definition.stages.map((s,i)=>[i,s.name])},
  {key:'workflow.completed_stages',label:_t('This workflow · completed section'),type:'ids',options:S.w.definition.stages.map((s,i)=>[i,s.name])}];
}
function conditionLeaves(rule){return !rule?[]:rule.rules?rule.rules.flatMap(conditionLeaves):[rule];}
/* `stageForm.*` paths edit the Stages sheet's unsaved form, not the definition. */
const formPath=path=>/^stageForm\./.test(path||'');
function editRoot(path){return formPath(path)?S:/^(scope|trigger)\./.test(path)||path==='scope'?S.w.definition:byId(S.w.definition,S.selected);}
function applyEdit(path,fn,redraw=true){if(formPath(path)){fn();renderSheet();return;}mutate(fn,redraw);}
function atPath(path){return path.split('.').reduce((o,k)=>o?.[k],editRoot(path));}
function ruleOptions(f){return f?.options?.map(o=>Array.isArray(o)?o:[o,o])||[];}
function operators(f){
 if(f?.type==='ids'||f?.type==='multiselect')return [['contains',_t('includes')],['not_contains',_t('does not include')],['set',_t('has a value')],['unset',_t('has no value')]];
 const out=[['eq',_t('is')],['ne',_t('is not')]];
 if(f?.type!=='boolean')out.push(['set',_t('has a value')],['unset',_t('has no value')]);
 if(['integer','float','monetary','number','date','datetime'].includes(f?.type)&&!f?.options?.length)out.push(['gt',_t('is after / more than')],['gte',_t('is at least')],['lt',_t('is before / less than')],['lte',_t('is at most')]);
 if(['char','text','textarea','email'].includes(f?.type))out.push(['icontains',_t('contains')],['not_contains',_t('does not contain')]);
 if(ruleOptions(f).length&&f?.type!=='boolean')out.push(['in',_t('is one of')],['not_in',_t('is not one of')]);
 return out;
}
function conditionEditor(rule,path,available){
 const f=available.find(f=>f.key===rule?.field),choices=ruleOptions(f),ops=operators(f);
 if(rule?.op==='contains'&&!ops.some(o=>o[0]==='contains'))ops.push(['contains',_t('contains (case sensitive)')]);
 let value='';
 if(!['set','unset'].includes(rule?.op)){
  if(f?.type==='boolean')value=selectEdit(path+'.value',[['true',_t('Yes')],['false',_t('No')]],String(rule?.value),_t('Choose Yes or No'));
  else if(choices.length){const multi=['in','not_in'].includes(rule?.op);value=multi?`<select data-edit="${esc(path)}.value" multiple aria-label="${_t('Matching values')}">${choices.map(([v,l])=>`<option value="${esc(v)}" ${(rule.value||[]).includes(v)?'selected':''}>${esc(l)}</option>`).join('')}</select>`:selectEdit(path+'.value',choices,rule?.value);}
  else if(f?.type==='many2one')value=btn('filter-lookup',esc(rule?.value_label|| (rule?.value?_t('Selected record #%(id)s',{id:rule.value}):_t('Choose a record'))),'search','',`data-path="${esc(path)}"`);
  else value=inputEdit(path+'.value',rule?.value??'',f?.type==='date'?'date':f?.type==='datetime'?'datetime-local':['integer','float','monetary','number'].includes(f?.type)?'number':'text','placeholder="'+_t('Value')+'" aria-label="'+_t('Filter value')+'"');
 }
 return `<div class="condition-line">${selectEdit(path+'.field',available,rule?.field,_t('Choose a field'))}${selectEdit(path+'.op',ops,rule?.op||'eq',null)}${value}</div>`;
}
function filterEditor(tree,path,available,depth=0){
 if(!tree||tree.rules?.length===0)return `<div class="filter-empty"><span>${_t('Always')}</span>${btn('condition-add',_t('Add a filter'),'plus','small plain',`data-path="${esc(path)}"`)}</div>`;
 if(!tree.rules)return `<div class="condition-leaf">${conditionEditor(tree,path,available)}${btn('condition-remove',_t('Remove filter'),'','small plain',`data-path="${esc(path)}"`)}</div>`;
 return `<div class="condition-group"><div class="condition-heading">${selectEdit(path+'.match',[['all',_t('All of these match')],['any',_t('Any of these match')]],tree.match,null)}${path!=='scope'?btn('condition-remove','×','','small plain',`data-path="${esc(path)}" aria-label="${_t('Remove filter group')}"`):''}</div>${tree.rules.map((r,i)=>filterEditor(r,path+'.rules.'+i,available,depth+1)).join('')}<div class="row wrap">${btn('condition-add',_t('Add filter'),'plus','small plain',`data-path="${esc(path)}"`)}${depth<3?btn('condition-group',_t('Add group'),'','small plain',`data-path="${esc(path)}"`):''}</div></div>`;
}
function sampleFields(){const d=S.w.definition,all=[d.scope,d.trigger.before,...d.nodes.flatMap(n=>[n.when,n.wait_for,...(n.branches||[]).map(b=>b.condition)])],keys=new Set(all.flatMap(conditionLeaves).map(r=>r.field));return availableFields().filter(f=>keys.has(f.key)&&f.key!=='workflow.stage');}
function sampleInput(f){const choices=ruleOptions(f);return `<${choices.length||f.type==='boolean'?'select':'input'} data-sample="${esc(f.key)}" data-kind="${esc(f.type)}" ${f.type==='ids'?'multiple':''} ${!choices.length&&f.type!=='boolean'?'placeholder="'+_t('Example value')+'"':''}>${choices.length?opts(choices,''):f.type==='boolean'?opts([['true',_t('Yes')],['false',_t('No')]],''):''}${choices.length||f.type==='boolean'?'</select>':''}`;}
async function conditionAction(name,el){
 const path=el.dataset.path;
 if(name==='condition-add'||name==='condition-group'){
  const available=/^(scope|trigger)/.test(path)||formPath(path)?S.w.metadata.fields:availableFields(),f=available[0];
  if(!f)throw Error(_t('No accessible fields are available for this record.'));
  const rule={field:f.key,op:'eq',value:defaultRuleValue(f)};
  applyEdit(path,()=>{let tree=atPath(path);if(!tree){tree={match:'all',rules:[]};setPath(editRoot(path),path,tree);}if(!tree.rules){tree={match:'all',rules:[tree]};setPath(editRoot(path),path,tree);}tree.rules.push(name==='condition-group'?{match:'any',rules:[rule]}:rule);});return true;
 }
 if(name==='condition-remove'){
  applyEdit(path,()=>{if(/\.rules\.\d+$/.test(path)){const parts=path.split('.'),i=Number(parts.pop()),arr=parts.reduce((o,k)=>o[k],editRoot(path));arr.splice(i,1);const parent=parts.slice(0,-1).join('.');if(!arr.length&&parent!=='scope'){const keys=parent.split('.'),last=keys.pop();delete keys.reduce((o,k)=>o[k],editRoot(path))[last];}}else if(path==='scope')S.w.definition.scope={match:'all',rules:[]};else{const keys=path.split('.'),last=keys.pop();delete keys.reduce((o,k)=>o[k],editRoot(path))[last];}});return true;
 }
 if(name==='filter-lookup'){S.filterLookup=path;modal(_t('Choose a matching record'),'<div class="row"><input id="condition-search" placeholder="'+_t('Search by name')+'" aria-label="'+_t('Find a matching record')+'">'+btn('filter-search',_t('Search'),'search')+'</div><div id="condition-results" class="choice-list"></div>');await conditionAction('filter-search',el);return true;}
 if(name==='filter-search'){const r=atPath(S.filterLookup);S.conditionResults=await rpc('filter_choices',[S.w.id,r.field,$('#condition-search').value,r.value||null]);$('#condition-results').innerHTML=S.conditionResults.map(r=>btn('filter-picked',esc(r.name),'','',`data-id="${r.id}"`)).join('')||'<p>'+_t('No accessible matches.')+'</p>';return true;}
 if(name==='filter-picked'){const r=S.conditionResults.find(r=>r.id===Number(el.dataset.id));const at=S.filterLookup;close();applyEdit(at,()=>Object.assign(atPath(at),{value:r.id,value_label:r.name}));return true;}
 return false;
}
function defaultRuleValue(f){return ruleOptions(f)[0]?.[0]??(f?.type==='boolean'?true:['number','float','monetary','integer','many2one','ids'].includes(f?.type)?0:'');}

function beforeSamples(){const tree=S.w.definition.trigger.before;if(!tree)return '';const keys=new Set(conditionLeaves(tree).map(r=>r.field));return '<h3>'+_t('Before the change')+'</h3>'+S.w.metadata.fields.filter(f=>keys.has(f.key)).map(f=>field(esc(f.label),sampleInput(f).replace('data-sample=', 'data-before-sample='))).join('')+'<hr><h3>'+_t('After the change')+'</h3>';}
