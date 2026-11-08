/* Workflow Studio POC. Browser-only, fictional data, zero network requests. */
'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)], clone=v=>JSON.parse(JSON.stringify(v));
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const TYPES={branch:{name:'Choose a path',icon:'◇',description:'Named routes and a shared rejoin'},parallel:{name:'Work in parallel',icon:'⑂',description:'Independent tasks, explicit join'},subprocess:{name:'Reusable process',icon:'▦',description:'A versioned group of steps'},policy:{name:'Decision table',icon:'▤',description:'Readable rules, clear results'},input:{name:'Collect information',icon:'▧',description:'A form with required evidence'},trigger:{name:'Trigger',icon:'ϟ',description:'Start a process'},approval:{name:'Approval',icon:'♧',description:'Ask the right person'},condition:{name:'Condition',icon:'◇',description:'Choose the next path'},email:{name:'Send email',icon:'✉',description:'Keep people informed'},task:{name:'Create task',icon:'✓',description:'Make work happen'},wait:{name:'Wait',icon:'◷',description:'Pause before continuing'},state:{name:'Change state',icon:'↗',description:'Move the record forward'},webhook:{name:'Integration',icon:'⇄',description:'Call a connected service'}};
const PEOPLE=['Their manager','HR partner','Finance approver','IT team','Employee','System','Policy result'];
const icons=type=>`<span class="block-icon type-${type}">${svgIcon(type)}</span>`;
const select=(name,values,value,attrs='')=>`<select ${attrs} name="${name}">${values.map(v=>{let [key,label]=Array.isArray(v)?v:[v,v];return `<option value="${esc(key)}" ${String(key)===String(value)?'selected':''}>${esc(label)}</option>`}).join('')}</select>`;
const field=(label,content,hint='')=>`<label class="field"><span>${label}</span>${content}${hint?`<small>${hint}</small>`:''}</label>`;
const input=(name,value,type='text',attrs='')=>`<input name="${name}" type="${type}" value="${esc(value)}" ${attrs}>`;
const initialNode=(id,type,title,stage,extra={})=>({id,type,title,stage,owner:type==='trigger'?'Employee':type==='approval'?'Their manager':type==='task'?'HR partner':'System',due:2,delegate:true,independent:true,recipient:'Employee',body:'Your request has progressed. View the latest update in Payobook.',field:'amount',op:'gt',value:1000,hours:24,state:'Approved',...extra});
const TEMPLATES={expense:{name:'Expense reimbursement',domain:'Expenses',icon:'↗',model:'hr.expense',desc:'A smarter approval path, from claim to confirmation.',event:'Claim submitted',numeric:'Claim amount',unit:'AUD',value:2400,stages:[{name:'Submit',state:'Submitted'},{name:'Review',state:'Pending approval'},{name:'Complete',state:'Approved'}],nodes:[initialNode('trigger','trigger','Claim submitted',0),initialNode('manager','approval','Manager approval',1),initialNode('rule','condition','An extra check?',1),initialNode('finance','approval','Finance approval',1,{owner:'Finance approver'}),initialNode('finish','state','Approve the claim',2),initialNode('email','email','Let the employee know',2)]},leave:{name:'Time-off request',domain:'Time & attendance',icon:'☀',model:'hr.leave',desc:'Keep leave simple, with cover when a manager is away.',event:'Leave requested',numeric:'Days requested',unit:'days',value:7,stages:[{name:'Request',state:'To approve'},{name:'Review',state:'Second approval'},{name:'Complete',state:'Approved'}],nodes:[initialNode('trigger','trigger','Leave requested',0),initialNode('manager','approval','Manager approval',1),initialNode('rule','condition','More than five days?',1,{value:5}),initialNode('hr','approval','HR review',1,{owner:'HR partner'}),initialNode('finish','state','Approve time off',2),initialNode('email','email','Send the confirmation',2)]},onboarding:{name:'New hire onboarding',domain:'People',icon:'✧',model:'hr.employee',desc:'Bring HR, IT and the new starter into one shared journey.',event:'Offer accepted',numeric:'Equipment budget',unit:'AUD',value:1500,stages:[{name:'Welcome',state:'Offer accepted'},{name:'Prepare',state:'Preparing'},{name:'Ready',state:'Onboarded'}],nodes:[initialNode('trigger','trigger','Offer accepted',0),initialNode('email1','email','Send a warm welcome',0),initialNode('manager','task','Prepare employment pack',1,{owner:'HR partner'}),initialNode('it','task','Provision equipment',1,{owner:'IT team'}),initialNode('wait','wait','Wait for start day',1,{hours:48}),initialNode('finish','state','Mark onboarding complete',2,{state:'Onboarded'}),initialNode('email','email','Share the day-one guide',2)]},hiring:{name:'Candidate to offer',domain:'Talent acquisition',icon:'◎',model:'hr.applicant',desc:'Structured interviews, consistent decisions and a personal touch.',event:'Candidate shortlisted',numeric:'Proposed annual salary',unit:'AUD',value:120000,stages:[{name:'Shortlist',state:'Shortlisted'},{name:'Evaluate',state:'Interview'},{name:'Offer',state:'Offer approved'}],nodes:[initialNode('trigger','trigger','Candidate shortlisted',0),initialNode('manager','task','Arrange an interview',1,{owner:'HR partner'}),initialNode('rule','condition','Senior salary band?',1,{value:100000}),initialNode('finance','approval','Approve salary exception',1,{owner:'Finance approver'}),initialNode('finish','state','Advance to offer',2,{state:'Offer approved'}),initialNode('email','email','Send offer update',2)]},offboarding:{name:'Employee offboarding',domain:'People',icon:'↗',model:'pb.offboarding.case',desc:'Clear handovers, asset return and a coordinated final day.',event:'Resignation accepted',numeric:'Outstanding asset value',unit:'AUD',value:800,stages:[{name:'Initiate',state:'Open'},{name:'Clearance',state:'In progress'},{name:'Close',state:'Completed'}],nodes:[initialNode('trigger','trigger','Resignation accepted',0),initialNode('manager','task','Complete the handover',1,{owner:'Their manager'}),initialNode('it','task','Collect company assets',1,{owner:'IT team'}),initialNode('hr','approval','HR clearance',1,{owner:'HR partner'}),initialNode('finish','state','Complete offboarding',2,{state:'Completed'}),initialNode('email','email','Confirm final arrangements',2)]},payroll:{name:'Payrun sign-off',domain:'Payroll',icon:'▥',model:'hr.payslip.run',desc:'A controlled path from payroll preparation to authorised release.',event:'Payrun ready for review',numeric:'Total net payroll',unit:'AUD',value:210000,stages:[{name:'Prepare',state:'Draft'},{name:'Check',state:'Under review'},{name:'Authorise',state:'Approved'}],nodes:[initialNode('trigger','trigger','Payrun ready for review',0),initialNode('manager','approval','HR payroll review',1,{owner:'HR partner'}),initialNode('rule','condition','Above release threshold?',1,{value:100000}),initialNode('finance','approval','Finance sign-off',1,{owner:'Finance approver'}),initialNode('finish','state','Authorise the payrun',2),initialNode('email','email','Notify payroll team',2,{recipient:'HR partner'})]}};

/* A structured graph: groups own sequences; routing never depends on card position. */
const SCHEMA='payobook.workflow.poc/2';
const uid=prefix=>prefix+'_'+Math.random().toString(36).slice(2,10);
const HUMAN=['approval','task','input'];
const GROUPS=['branch','parallel','subprocess'];
const PERSONS={'Their manager':'Maya Chen','HR partner':'Alex Lee','Finance approver':'Jordan Taylor','IT team':'Sam Rivera','Employee':'Priya Shah'};
const SAMPLE={amount:2400,department:'Operations',country:'Australia',manager:'available',access:'allowed',actor:'other',decision:'approve',failure:'none',employee:'Priya Shah',email:'priya@example.invalid'};
const TOKENS=[
 {key:'employee.name',label:'Employee name',type:'text',value:'Priya Shah',source:'trigger'},
 {key:'employee.email',label:'Employee email',type:'email',value:'priya@example.invalid',source:'trigger'},
 {key:'request.amount',label:'Request amount',type:'number',value:2400,source:'trigger'},
 {key:'request.department',label:'Department',type:'text',value:'Operations',source:'trigger'},
 {key:'request.country',label:'Country',type:'text',value:'Australia',source:'trigger'},
 {key:'request.status',label:'Current record status',type:'text',value:'Approved',source:'trigger'}
];
function nodeDefaults(n){return {...n,notes:n.notes||'',retry:n.retry??2,prompt:n.prompt||'Please provide the supporting information.',required:n.required??true,fieldLabel:n.fieldLabel||'Supporting details',onReject:n.onReject||'stop',onReturn:n.onReturn||'resubmit'};}
function migrate(old){
 const d=clone(old);if(d.schema===SCHEMA)return d;
 d.schema=SCHEMA;d.order=[];d.nodes=d.nodes.map(n=>{const c=nodeDefaults(n);delete c.pos;return c});
 for(let i=0;i<d.nodes.length;i++){
  const n=d.nodes[i];d.order.push(n.id);
  if(n.type==='condition'){
   const child=d.nodes[i+1];n.type='branch';n.branches=[{id:uid('route'),label:'When the rule matches',condition:{field:n.field,op:n.op,value:n.value},steps:child?[child.id]:[]},{id:uid('route'),label:'Otherwise',condition:null,steps:[]}];
   if(child)i++;
  }
 }
 d.scope=d.scope||{company:'Demo company',match:'all',rules:[]};return d;
}
function makeNode(type,stage,id=uid('step')){
 const n=nodeDefaults(initialNode(id,type,TYPES[type].name,stage));
 if(type==='input'){n.owner='Employee';n.form={id:uid('form'),version:1,title:'Tell us a little more',description:'Complete the details below.',fields:[newFormField('text')]};}
 if(type==='matrix'){n.owner='Approval Matrix';n.matrixProcess='connected';}
 if(type==='branch')n.branches=[{id:uid('route'),label:'Above the limit',condition:{field:'amount',op:'gt',value:1000},steps:[]},{id:uid('route'),label:'Otherwise',condition:null,steps:[]}];
 if(type==='parallel'){n.join='all';n.branches=[{id:uid('route'),label:'HR',steps:[]},{id:uid('route'),label:'IT',steps:[]}];}
 if(type==='subprocess'){n.steps=[];n.component={name:'Local subprocess',version:1};}
 if(type==='policy'){n.rows=[{department:'Any',min:0,max:1000,owner:'Their manager'},{department:'Any',min:1000,max:null,owner:'Finance approver'}];n.fallback='HR partner';}
 return n;
}
function freshDraft(key){
 if(TEMPLATES[key].integrated)return integratedDraft(key);
 const t=TEMPLATES[key],d=migrate({template:key,name:t.name,event:t.event,scope:{company:'Demo company',match:'all',rules:[]},stages:clone(t.stages),nodes:clone(t.nodes),revision:0});
 d.nodes.filter(n=>n.type==='email').forEach(n=>{n.body='Hi {{employee.name}}, your request for {{request.amount}} has reached {{request.status}}. View the next steps in Payobook.'});
 if(key==='expense'){
  const rule=d.nodes.find(n=>n.type==='branch');rule.title='Choose the right review';rule.branches[0].label='Above AUD 1,000';rule.branches[1].label='Standard claim';
  const evidence=makeNode('input',1,'evidence');evidence.title='Collect supporting details';delete evidence.form;evidence.fieldLabel='Business purpose';evidence.prompt='Tell Finance why this expense was needed.';rule.branches[0].steps.unshift(evidence.id);d.nodes.push(evidence);
 }
 if(key==='onboarding'||key==='offboarding'){
  const ids=key==='onboarding'?['manager','it']:['manager','it'];
  const p=makeNode('parallel',1,'parallel');p.title=key==='onboarding'?'Prepare together':'Complete clearances';p.branches=[{id:'hr_branch',label:'People & documents',steps:[ids[0]]},{id:'it_branch',label:'Equipment & access',steps:[ids[1]]}];
  const idx=d.order.indexOf(ids[0]);d.order=d.order.filter(x=>!ids.includes(x));d.order.splice(idx,0,p.id);d.nodes.push(p);
 }
 if(key==='payroll'){
  const old=d.nodes.find(n=>n.type==='branch');const index=d.order.indexOf(old.id);d.order.splice(index,1,'policy','finance');d.nodes=d.nodes.filter(n=>n.id!==old.id);
  const p=makeNode('policy',1,'policy');p.title='Resolve the release policy';p.rows=[{department:'Any',min:0,max:100000,owner:'HR partner'},{department:'Any',min:100000,max:null,owner:'Finance approver'}];d.nodes.push(p);d.nodes.find(n=>n.id==='finance').owner='Policy result';
 }
 d.nodes.forEach(n=>(n.branches||[]).forEach((b,i)=>b.id=n.id+'__route_'+i));
 return d;
}
const byId=(d,id)=>d.nodes.find(n=>n.id===id);
function containers(d){const result=[{key:'main',ids:d.order}];d.nodes.forEach(n=>{if(n.branches)n.branches.forEach(b=>result.push({key:b.id,ids:b.steps,parent:n,branch:b}));if(n.steps)result.push({key:n.id,ids:n.steps,parent:n})});return result;}
const containerFor=(d,id)=>containers(d).find(c=>c.ids.includes(id));
function descendants(d,id){const n=byId(d,id);if(!n)return[];return [id,...(n.branches||[]).flatMap(b=>b.steps.flatMap(c=>descendants(d,c))),...(n.steps||[]).flatMap(c=>descendants(d,c))];}
function ordered(d){const result=[];const walk=ids=>ids.forEach(id=>{const n=byId(d,id);if(!n)return;result.push(n);if(n.branches)n.branches.forEach(b=>walk(b.steps));if(n.steps)walk(n.steps)});walk(d.order);return result;}
function ancestors(d,id){let c=containerFor(d,id),out=[];while(c?.parent){out.unshift(c.parent);c=containerFor(d,c.parent.id)}return out;}
function previousIds(d,id){const c=containerFor(d,id);if(!c)return[];return [...(c.parent?previousIds(d,c.parent.id):[]),...c.ids.slice(0,c.ids.indexOf(id))];}
function availableTokens(d,id){return [...TOKENS,...previousIds(d,id).filter(k=>byId(d,k)?.type!=='trigger').flatMap(k=>{const n=byId(d,k);return n.form?n.form.fields.filter(f=>f.type!=='section'&&!f.visibility).map(f=>({key:`step.${k}.field.${f.id}`,label:f.label,type:f.type,value:sampleFormAnswers(n.form,SAMPLE)[f.id],source:k})):[{key:`step.${k}.result`,label:n.title+' · result',type:'text',value:'Sample result',source:k}]})];}
function routeText(r,key='expense'){
 if(!r)return'Otherwise';const labels={gt:'>',gte:'≥',lt:'<',eq:'is',ne:'is not'};
 return `${r.field==='amount'?TEMPLATES[key].numeric:r.field==='department'?'Department':'Country'} ${labels[r.op]} ${r.value}`;
}
function matches(r,f){const a=r.field==='amount'?Number(f[r.field]):String(f[r.field]??'').toLowerCase(),b=r.field==='amount'?Number(r.value):String(r.value).toLowerCase();return r.op==='gt'?a>b:r.op==='gte'?a>=b:r.op==='lt'?a<b:r.op==='ne'?a!==b:a===b;}
function compile(d){
 const edges=[],visual=[],seen=new Set();
 function seq(ids,target){for(let i=0;i<ids.length;i++){const id=ids[i],n=byId(d,id),next=ids[i+1]||target;if(!n||seen.has(id))continue;seen.add(id);visual.push({...n,virtual:false});
  if(GROUPS.includes(n.type)){
   const join=id+'__join';visual.push({id:join,type:'join',title:n.type==='parallel'?(n.join==='any'?'First completed route':'Wait for every route'):'Rejoin',stage:n.stage,parent:id,virtual:true});
   const branches=n.branches||[{id:id+'__inner',label:'Run component',steps:n.steps}];
   branches.forEach(b=>{edges.push({from:id,to:b.steps[0]||join,label:b.label,kind:n.type==='parallel'?'parallel':n.type==='branch'?'choice':'call'});seq(b.steps,join)});
   if(next)edges.push({from:join,to:next,label:'Continue',kind:'sequence'});
  }else if(next)edges.push({from:id,to:next,label:'',kind:'sequence'});
 }}seq(d.order,null);return {nodes:visual,edges};
}
function issues(d){
 const out=[],add=(id,text,severity='error')=>out.push({id,text,severity});
 if(!d.name.trim()||!d.event.trim())add('trigger','Name the process and its start event.');
 if(!d.scope.company.trim())add('trigger','Choose a company boundary.');
 if(d.order[0]!=='trigger'||d.nodes.filter(n=>n.type==='trigger').length!==1)add('trigger','Keep one start event at the beginning.');
 if(!d.nodes.some(n=>['state','matrix'].includes(n.type)))add('trigger','Add a business action to define the final record status.');
 const visiting=new Set(),done=new Set();function walk(id){if(visiting.has(id)){add(id,'Recursive groups are not supported.');return}if(done.has(id))return;visiting.add(id);const n=byId(d,id);if(n){for(const b of n.branches||[])b.steps.forEach(walk);(n.steps||[]).forEach(walk)}visiting.delete(id);done.add(id)}d.nodes.forEach(n=>walk(n.id));
 if(out.some(i=>i.text==='Recursive groups are not supported.'))return out;
 const counts={};containers(d).forEach(c=>c.ids.forEach(id=>{counts[id]=(counts[id]||0)+1;if(!byId(d,id))add(c.parent?.id||'trigger','A step reference is missing.')}));
 for(const n of d.nodes){
  if(counts[n.id]!==1)add(n.id,'Each step must belong to exactly one route.');
  if(!n.title.trim())add(n.id,'Give this step a name.');
  if(n.stage<0||n.stage>=d.stages.length)add(n.id,'Select a valid phase.');
  if(HUMAN.includes(n.type)){
   if(!n.owner||n.owner==='System')add(n.id,'Choose a person or responsibility.');
   if(!Number.isFinite(+n.due)||+n.due<1)add(n.id,'Set a positive working-day deadline.');
   if(n.type==='approval'&&!n.delegate)add(n.id,'No approval cover is enabled.','warning');
   if(n.owner==='Policy result'&&!previousIds(d,n.id).some(k=>byId(d,k).type==='policy'))add(n.id,'Place a decision table before this policy-based assignment.');
  }
  if(n.type==='input'){if(n.form)formDefinitionErrors(n.form).forEach(message=>add(n.id,message));else if(!n.fieldLabel.trim())add(n.id,'Name the information you need.');}
  if(n.type==='email'){
   if(!n.body.trim())add(n.id,'Write the email message.');
   const keys=availableTokens(d,n.id).map(t=>t.key);for(const token of n.body.matchAll(/\{\{([^}]+)\}\}/g))if(!keys.includes(token[1].trim()))add(n.id,'Unknown or unavailable token: '+token[1]);
  }
  if(n.type==='wait'&&(!Number.isFinite(+n.hours)||+n.hours<1))add(n.id,'Set a wait of at least one hour.');
  if(n.type==='branch'){
   if(n.branches.length<2||n.branches.filter(b=>!b.condition).length!==1||n.branches.at(-1).condition)add(n.id,'Keep one Otherwise route, last in the group.');
   n.branches.forEach(b=>{if(!b.label.trim())add(n.id,'Name each route.');if(b.condition&&(b.condition.value===''||b.condition.field==='amount'&&(!Number.isFinite(+b.condition.value)||+b.condition.value<0)))add(n.id,'Complete each route with a valid value.')});
  }
  if(n.type==='parallel'&&n.branches.some(b=>!b.steps.length))add(n.id,'Add work to every parallel route.');
  if(n.type==='subprocess'&&!n.steps.length)add(n.id,'Add a step to this subprocess.');
  if(n.type==='policy'){
   n.rows.forEach((r,i)=>{if(!Number.isFinite(+r.min)||+r.min<0||r.max!==null&&(!Number.isFinite(+r.max)||+r.max<=+r.min))add(n.id,`Policy row ${i+1}: use a valid amount range.`);
    n.rows.slice(i+1).forEach((s,j)=>{if((r.department==='Any'||s.department==='Any'||r.department===s.department)&&Math.max(+r.min,+s.min)<Math.min(r.max===null?Infinity:+r.max,s.max===null?Infinity:+s.max))add(n.id,`Policy rows ${i+1} and ${i+j+2} overlap.`)})});
  }
 }
 for(const r of d.scope.rules)if(r.value===''||r.field==='amount'&&!Number.isFinite(+r.value)||['gt','lt','gte'].includes(r.op)&&r.field!=='amount')add('trigger','Complete eligibility filters with compatible values.');
 return out.concat(integrationIssues(d));
}
function tokenValue(key,run){const map={'employee.name':run.facts.employee,'employee.email':run.facts.email,'request.amount':run.facts.amount,'request.department':run.facts.department,'request.country':run.facts.country,'request.status':run.recordState};if(Object.hasOwn(map,key))return map[key];const fm=key.match(/^step\.([^.]+)\.field\.([^.]+)$/);if(fm){const v=run.outputs[fm[1]]?.[fm[2]];return v===undefined?undefined:displayAnswer(v);}const m=key.match(/^step\.(.+)\.result$/);return m?run.outputs[m[1]]:undefined;}
function expandMessage(body,run){return body.replace(/\{\{([^}]+)\}\}/g,(_,key)=>{const v=tokenValue(key.trim(),run);if(v===undefined)throw Error('No value is available for '+key.trim());return String(v)});}
function createRun(d,facts={}){
 const run={id:uid('run'),draft:clone(d),facts:{...SAMPLE,...facts},status:'running',states:{},outputs:{},choices:{},trace:[],answers:{},attempts:{},failures:{},returns:{},recordState:d.stages[0].state,clock:0,at:new Date().toISOString()};
 const errors=issues(d).filter(x=>x.severity==='error');if(errors.length){run.status='invalid';run.trace.push({id:'trigger',title:'Definition needs attention',text:errors.map(e=>e.text).join(' '),status:'blocked'});return run;}
 const matched=d.scope.rules.map(r=>matches(r,run.facts));if(matched.length&&!(d.scope.match==='all'?matched.every(Boolean):matched.some(Boolean))){run.status='excluded';run.trace.push({id:'trigger',title:'Record excluded',text:'The example does not match the eligibility filters.',status:'skipped'});return run;}advanceRun(run);return run;
}
function logRun(run,n,text,status='done'){run.trace.push({id:n.id,title:n.title,text,status});}
function actorFor(n,run){if(n.type==='matrix')return actorFor(matrixActorNode(n,run),run);let role=n.owner==='Policy result'?run.facts.policyReviewer:n.owner;if(role==='Their manager'&&run.facts.manager==='away'&&n.delegate)return {name:'Alex Lee',role,cover:'Valid cover for Maya Chen'};return {name:PERSONS[role]||'Unresolved person',role,cover:null};}
function skipTree(run,id){descendants(run.draft,id).forEach(k=>{if(run.states[k]!=='done')run.states[k]='skipped'});}
function advanceRun(run){
 if(['rejected','returned','complete','excluded','invalid'].includes(run.status))return;run.status='running';
 const d=run.draft;
 function seq(ids){for(const id of ids){if(!visit(id))return false;if(run.status==='blocked'||run.status==='rejected')return false;}return true;}
 function visit(id){const n=byId(d,id),status=run.states[id];if(['done','skipped'].includes(status))return true;if(['waiting','returned','failed','blocked'].includes(status)){if(['failed','blocked'].includes(status))run.status='blocked';return false;}
  if(n.optional&&!n.enabled){run.states[id]='skipped';logRun(run,n,'Additional message is off. Existing approval notifications remain the owner.','skipped');return true;}
  if(n.type==='branch'){
   if(!run.choices[id]){const b=n.branches.find(b=>!b.condition||matches(b.condition,run.facts));run.choices[id]=b.id;run.states[id]='active';n.branches.filter(x=>x!==b).forEach(x=>x.steps.forEach(k=>skipTree(run,k)));logRun(run,n,`Selected “${b.label}”. Other routes are skipped.`, 'active');}
   const branch=n.branches.find(b=>b.id===run.choices[id]);if(seq(branch.steps)){run.states[id]='done';run.outputs[id]=branch.label;logRun(run,n,'Chosen route finished; rejoin released.');return true}return false;
  }
  if(n.type==='parallel'){
   if(!status){run.states[id]='active';logRun(run,n,`Opened ${n.branches.length} independent routes. Join: ${n.join==='any'?'first completed route':'all routes'}.`,'active');}
   let count=0;for(const b of n.branches){if(seq(b.steps))count++;if(n.join==='any'&&count){n.branches.filter(x=>x!==b).forEach(x=>x.steps.forEach(k=>skipTree(run,k)));break;}}
   if(n.join==='any'?count>0:count===n.branches.length){run.states[id]='done';run.outputs[id]=n.join==='any'?'First route completed; remaining work cancelled':'All routes completed';logRun(run,n,run.outputs[id]+'; join released.');return true;}return false;
  }
  if(n.type==='subprocess'){run.states[id]='active';if(seq(n.steps)){run.states[id]='done';run.outputs[id]='Completed '+n.component.name+' v'+n.component.version;logRun(run,n,run.outputs[id]);return true}return false;}
  if(n.type==='matrix')return advanceMatrix(run,n);
  if(HUMAN.includes(n.type)){
   let why='';if(run.facts.access==='denied')why='The assigned person cannot read or act on this record.';else if(n.independent&&run.facts.actor==='self'&&n.type==='approval')why='The approver is also the requester. An independent person is required.';else if(n.owner==='Their manager'&&run.facts.manager!=='available'&&(!n.delegate||run.facts.manager==='expired'))why=n.delegate?'Approval cover has expired.':'The manager is away and cover is disabled.';else if(n.owner==='Policy result'&&!run.facts.policyReviewer)why='No decision table result is available.';
   if(why){run.states[id]='blocked';run.status='blocked';logRun(run,n,why,'blocked');return false;}
   run.states[id]='waiting';const actor=actorFor(n,run);logRun(run,n,`${actor.name} · ${actor.role}. ${actor.cover||'Assignment and sample access checked.'} Awaiting ${n.type==='approval'?'a decision':n.type==='input'?'required information':'completion'}.`,'waiting');return false;
  }
  if(n.type==='wait'){run.states[id]='waiting';logRun(run,n,`Timer waits ${n.hours} hours. Advance simulated time to continue.`,'waiting');return false;}
  if(['email','webhook'].includes(n.type)&&run.facts.failure===n.type&&!run.failures[id]){run.failures[id]=true;run.states[id]='failed';run.status='blocked';run.attempts[id]=0;logRun(run,n,'Injected example failure. No external service was called. Retry this action to continue.','failed');return false;}
  if(n.type==='policy'){
   const rows=n.rows.filter(r=>(r.department==='Any'||r.department===run.facts.department)&&run.facts.amount>=+r.min&&(r.max===null||run.facts.amount<+r.max));run.facts.policyReviewer=rows[0]?.owner||n.fallback;run.outputs[id]=run.facts.policyReviewer;logRun(run,n,`Policy matched ${rows.length?'one row':'the fallback'} → ${run.facts.policyReviewer}.`);
  }else if(n.type==='email'){
   try{run.outputs[id]=expandMessage(n.body,run);logRun(run,n,`Email preview to ${n.recipient}: ${run.outputs[id]}`)}catch(e){run.states[id]='blocked';run.status='blocked';logRun(run,n,e.message,'blocked');return false;}
  }else if(n.type==='state'){run.recordState=n.state;run.outputs[id]=n.state;logRun(run,n,`Proposed business action → ${n.state}. No record updated.`);
  }else if(n.type==='trigger'){run.outputs[id]='Started';logRun(run,n,`${d.event}. Eligibility matched in ${d.scope.company}.`);
  }else{run.outputs[id]='Completed';logRun(run,n,'Proposed integration completed in the simulator; no network call.');}
  run.states[id]='done';return true;
 }
 const finished=seq(d.order);if(finished)run.status='complete';else if(run.status!=='blocked')run.status='waiting';return run;
}
function respond(run,id,outcome,answer=''){
 const n=byId(run.draft,id);if(run.states[id]!=='waiting'||!['waiting','running'].includes(run.status))return {error:'This step is not available.'};
 if(n.type==='matrix')return respondMatrix(run,n,outcome,answer);
 if(n.type==='input'&&n.form){const result=validateForm(n.form,answer&&typeof answer==='object'?answer:{},run.facts);if(Object.keys(result.errors).length)return {error:'Complete the highlighted fields.',fields:result.errors};run.states[id]='done';run.outputs[id]=result.answers;run.answers[id]=result.answers;run.formDrafts??={};delete run.formDrafts[id];logRun(run,n,'Form submitted: '+Object.keys(result.answers).length+' typed answers.');advanceRun(run);return {};}
 if(n.type==='input'&&n.required&&!answer.trim())return{error:`Enter ${n.fieldLabel.toLowerCase()} to continue.`};
 if(outcome==='reject'){run.status='rejected';run.states[id]='rejected';logRun(run,n,'Rejected. Downstream actions will not run.','rejected');return{};}
 if(outcome==='return'){if(!answer.trim())return{error:'Explain what needs to change.'};run.states[id]='returned';run.status='returned';run.answers[id]=answer;logRun(run,n,'Sent back for changes: '+answer,'returned');return{};}
 run.states[id]='done';run.outputs[id]=n.type==='input'?answer:n.type==='wait'?`Waited ${n.hours} hours`:outcome==='approve'?'Approved':'Completed';run.answers[id]=answer;
 if(n.type==='wait')run.clock+=+n.hours;logRun(run,n,run.outputs[id]+(answer&&n.type!=='input'?' · '+answer:''));advanceRun(run);return{};
}
function resubmitRun(run){const id=Object.keys(run.states).find(k=>run.states[k]==='returned');if(!id)return;run.returns[id]=(run.returns[id]||0)+1;if(run.returns[id]>3){run.status='blocked';run.states[id]='blocked';logRun(run,byId(run.draft,id),'Rework limit reached; process owner intervention required.','blocked');return;}if(byId(run.draft,id).type==='matrix'){run.matrix[id].index=0;run.matrix[id].attempt++;for(const input of run.draft.nodes.filter(n=>n.type==='input')){run.states[input.id]='todo';run.formDrafts??={};run.formDrafts[input.id]=clone(run.answers[input.id]||{});delete run.outputs[input.id];}}run.states[id]='todo';run.status='running';logRun(run,byId(run.draft,id),'Requester corrected the example and resubmitted.');advanceRun(run);}
function retryRun(run,id){const n=byId(run.draft,id);if(run.states[id]!=='failed')return;run.attempts[id]=(run.attempts[id]||0)+1;if(run.attempts[id]>n.retry){logRun(run,n,'Retry limit exhausted. Escalate to the process owner.','failed');return;}run.states[id]='todo';run.status='running';logRun(run,n,'Retry '+run.attempts[id]+' of '+n.retry+' · example fault cleared.');advanceRun(run);}
function autoRun(d,facts={}){const run=createRun(d,facts);let first=true;for(let i=0;i<120&&run.status==='waiting';i++){const id=Object.keys(run.states).find(k=>run.states[k]==='waiting');if(!id)break;const n=byId(d,id);let outcome=['approval','matrix'].includes(n.type)?'approve':'complete';if(['approval','matrix'].includes(n.type)&&first){outcome=run.facts.decision;first=false;}respond(run,id,outcome,n.type==='input'&&n.form?sampleFormAnswers(n.form,run.facts):'Example evidence supplied');}return run;}
function outcomeSignature(run){return JSON.stringify({status:run.status,recordState:run.recordState,steps:Object.entries(run.states).filter(([,s])=>s==='done').map(([id])=>id).sort()});}
function diffDraft(before,after){const changes=[],old=Object.fromEntries(before.nodes.map(n=>[n.id,n])),now=Object.fromEntries(after.nodes.map(n=>[n.id,n]));const strip=n=>{const c=clone(n);delete c.pos;delete c.collapsed;return c};
 for(const n of after.nodes){if(!old[n.id])changes.push({id:n.id,kind:'added',title:n.title,text:TYPES[n.type].name+' added'});else{const keys=Object.keys(strip(n)).filter(k=>JSON.stringify(strip(n)[k])!==JSON.stringify(strip(old[n.id])[k]));if(keys.length)changes.push({id:n.id,kind:'changed',title:n.title,text:keys.map(k=>k==='branches'?'Routes changed':k==='rows'?'Policy rules changed':`${k}: ${typeof old[n.id][k]==='object'?'configured':String(old[n.id][k]??'—')} → ${typeof n[k]==='object'?'configured':String(n[k]??'—')}`).join(' · ')})}}
 for(const n of before.nodes)if(!now[n.id])changes.push({id:n.id,kind:'removed',title:n.title,text:TYPES[n.type].name+' removed'});
 if(JSON.stringify(before.order)!==JSON.stringify(after.order))changes.push({kind:'changed',title:'Execution order',text:'Main sequence changed.'});
 for(const key of ['scope','stages','name','event'])if(JSON.stringify(before[key])!==JSON.stringify(after[key]))changes.push({kind:'changed',title:key==='scope'?'Eligibility':key,text:'Process configuration updated.'});return changes;
}
