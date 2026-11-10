/* One typed rule builder for starts, steps, paths and waits. */
function availableFields(){
 const fields=[...S.w.metadata.fields];
 for(const n of S.w.definition.nodes)for(const f of n.form?.fields||[])if(f.type!=='section')fields.push({...f,key:`step.${n.id}.${f.id}`,label:n.title+' · '+f.label});
 return [...fields,{key:'person.user_id',label:'Started by · person',type:'many2one',options:S.w.metadata.users.map(u=>[u.id,u.name])},
  {key:'person.group_ids',label:'Started by · access role',type:'ids',options:S.w.metadata.starter_groups.map(g=>[g.id,g.name])},
  {key:'workflow.stage',label:'This workflow · current section',type:'integer',options:S.w.definition.stages.map((s,i)=>[i,s.name])},
  {key:'workflow.completed_stages',label:'This workflow · completed section',type:'ids',options:S.w.definition.stages.map((s,i)=>[i,s.name])}];
}
function conditionLeaves(rule){return !rule?[]:rule.rules?rule.rules.flatMap(conditionLeaves):[rule];}
function editRoot(path){return /^(scope|trigger)\./.test(path)||path==='scope'?S.w.definition:byId(S.w.definition,S.selected);}
function atPath(path){return path.split('.').reduce((o,k)=>o?.[k],editRoot(path));}
function ruleOptions(f){return f?.options?.map(o=>Array.isArray(o)?o:[o,o])||[];}
function operators(f){
 if(f?.type==='ids'||f?.type==='multiselect')return [['contains','includes'],['not_contains','does not include'],['set','has a value'],['unset','has no value']];
 const out=[['eq','is'],['ne','is not']];
 if(f?.type!=='boolean')out.push(['set','has a value'],['unset','has no value']);
 if(['integer','float','monetary','number','date','datetime'].includes(f?.type)&&!f?.options?.length)out.push(['gt','is after / more than'],['gte','is at least'],['lt','is before / less than'],['lte','is at most']);
 if(['char','text','textarea','email'].includes(f?.type))out.push(['icontains','contains'],['not_contains','does not contain']);
 if(ruleOptions(f).length&&f?.type!=='boolean')out.push(['in','is one of'],['not_in','is not one of']);
 return out;
}
function conditionEditor(rule,path,available){
 const f=available.find(f=>f.key===rule?.field),choices=ruleOptions(f),ops=operators(f);
 if(rule?.op==='contains'&&!ops.some(o=>o[0]==='contains'))ops.push(['contains','contains (case sensitive)']);
 let value='';
 if(!['set','unset'].includes(rule?.op)){
  if(f?.type==='boolean')value=selectEdit(path+'.value',[['true','Yes'],['false','No']],String(rule?.value),'Choose Yes or No');
  else if(choices.length){const multi=['in','not_in'].includes(rule?.op);value=multi?`<select data-edit="${esc(path)}.value" multiple aria-label="Matching values">${choices.map(([v,l])=>`<option value="${esc(v)}" ${(rule.value||[]).includes(v)?'selected':''}>${esc(l)}</option>`).join('')}</select>`:selectEdit(path+'.value',choices,rule?.value);}
  else if(f?.type==='many2one')value=btn('filter-lookup',esc(rule?.value_label|| (rule?.value?'Selected record #'+rule.value:'Choose a record')),'search','',`data-path="${esc(path)}"`);
  else value=inputEdit(path+'.value',rule?.value??'',f?.type==='date'?'date':f?.type==='datetime'?'datetime-local':['integer','float','monetary','number'].includes(f?.type)?'number':'text','placeholder="Value" aria-label="Filter value"');
 }
 return `<div class="condition-line">${selectEdit(path+'.field',available,rule?.field,'Choose a field')}${selectEdit(path+'.op',ops,rule?.op||'eq',null)}${value}</div>`;
}
function filterEditor(tree,path,available,depth=0){
 if(!tree||tree.rules?.length===0)return `<div class="filter-empty"><span>Always</span>${btn('condition-add','Add a filter','plus','small plain',`data-path="${esc(path)}"`)}</div>`;
 if(!tree.rules)return `<div class="condition-leaf">${conditionEditor(tree,path,available)}${btn('condition-remove','Remove filter','','small plain',`data-path="${esc(path)}"`)}</div>`;
 return `<div class="condition-group"><div class="condition-heading">${selectEdit(path+'.match',[['all','All of these match'],['any','Any of these match']],tree.match,null)}${path!=='scope'?btn('condition-remove','×','','small plain',`data-path="${esc(path)}" aria-label="Remove filter group"`):''}</div>${tree.rules.map((r,i)=>filterEditor(r,path+'.rules.'+i,available,depth+1)).join('')}<div class="row wrap">${btn('condition-add','Add filter','plus','small plain',`data-path="${esc(path)}"`)}${depth<3?btn('condition-group','Add group','','small plain',`data-path="${esc(path)}"`):''}</div></div>`;
}
function sampleFields(){const d=S.w.definition,all=[d.scope,d.trigger.before,...d.nodes.flatMap(n=>[n.when,n.wait_for,...(n.branches||[]).map(b=>b.condition)])],keys=new Set(all.flatMap(conditionLeaves).map(r=>r.field));return availableFields().filter(f=>keys.has(f.key)&&f.key!=='workflow.stage');}
function sampleInput(f){const choices=ruleOptions(f);return `<${choices.length||f.type==='boolean'?'select':'input'} data-sample="${esc(f.key)}" data-kind="${esc(f.type)}" ${f.type==='ids'?'multiple':''} ${!choices.length&&f.type!=='boolean'?'placeholder="Example value"':''}>${choices.length?opts(choices,''):f.type==='boolean'?opts([['true','Yes'],['false','No']],''):''}${choices.length||f.type==='boolean'?'</select>':''}`;}
async function conditionAction(name,el){
 const path=el.dataset.path;
 if(name==='condition-add'||name==='condition-group'){
  const available=/^(scope|trigger)/.test(path)?S.w.metadata.fields:availableFields(),f=available[0];
  if(!f)throw Error('No accessible fields are available for this record.');
  const rule={field:f.key,op:'eq',value:defaultRuleValue(f)};
  mutate(()=>{let tree=atPath(path);if(!tree){tree={match:'all',rules:[]};setPath(editRoot(path),path,tree);}if(!tree.rules){tree={match:'all',rules:[tree]};setPath(editRoot(path),path,tree);}tree.rules.push(name==='condition-group'?{match:'any',rules:[rule]}:rule);});return true;
 }
 if(name==='condition-remove'){
  mutate(()=>{if(/\.rules\.\d+$/.test(path)){const parts=path.split('.'),i=Number(parts.pop()),arr=parts.reduce((o,k)=>o[k],editRoot(path));arr.splice(i,1);const parent=parts.slice(0,-1).join('.');if(!arr.length&&parent!=='scope'){const keys=parent.split('.'),last=keys.pop();delete keys.reduce((o,k)=>o[k],editRoot(path))[last];}}else if(path==='scope')S.w.definition.scope={match:'all',rules:[]};else{const keys=path.split('.'),last=keys.pop();delete keys.reduce((o,k)=>o[k],editRoot(path))[last];}});return true;
 }
 if(name==='filter-lookup'){S.filterLookup=path;modal('Choose a matching record','<div class="row"><input id="condition-search" placeholder="Search by name" aria-label="Find a matching record">'+btn('filter-search','Search','search')+'</div><div id="condition-results" class="choice-list"></div>');await conditionAction('filter-search',el);return true;}
 if(name==='filter-search'){const r=atPath(S.filterLookup);S.conditionResults=await rpc('filter_choices',[S.w.id,r.field,$('#condition-search').value,r.value||null]);$('#condition-results').innerHTML=S.conditionResults.map(r=>btn('filter-picked',esc(r.name),'','',`data-id="${r.id}"`)).join('')||'<p>No accessible matches.</p>';return true;}
 if(name==='filter-picked'){const r=S.conditionResults.find(r=>r.id===Number(el.dataset.id));mutate(()=>Object.assign(atPath(S.filterLookup),{value:r.id,value_label:r.name}));close();return true;}
 return false;
}
function defaultRuleValue(f){return ruleOptions(f)[0]?.[0]??(f?.type==='boolean'?true:['number','float','monetary','integer','many2one','ids'].includes(f?.type)?0:'');}

function beforeSamples(){const tree=S.w.definition.trigger.before;if(!tree)return '';const keys=new Set(conditionLeaves(tree).map(r=>r.field));return '<h3>Before the change</h3>'+S.w.metadata.fields.filter(f=>keys.has(f.key)).map(f=>field(esc(f.label),sampleInput(f).replace('data-sample=', 'data-before-sample='))).join('')+'<hr><h3>After the change</h3>';}
