/* References model ownership; these are sample Matrix routes, never live configuration. */
TYPES.matrix={name:'Get approval',icon:'♧',description:'Follow the existing approval route'};
const MATRIX_SAMPLES={
 connected:{process:'Expense reimbursement',version:2,scope:'Demo company · all departments',route:'Manager → Finance above AUD 1,000',finalState:'Approved',people:['Their manager','Finance approver']},
 connected_payroll:{process:'Pay run',version:2,scope:'Demo company · all departments',route:'Payroll manager → HR lead → Finance approver',finalState:'Applied',people:['Payroll manager','HR lead','Finance approver']},
 settlement:{process:'Full and final settlement',version:1,scope:'Demo company · all departments',route:'No approval needed',finalState:'Applied',people:[]}
};
Object.assign(PERSONS,{'Payroll manager':'Maya Chen','HR lead':'Alex Lee'});
for(const [key,source] of Object.entries({connected:'expense',connected_payroll:'payroll',settlement:'offboarding'})){
 TEMPLATES[key]={...clone(TEMPLATES[source]),integrated:true,name:MATRIX_SAMPLES[key].process,desc:key==='settlement'?'Collect missing details, apply the existing no-approval route, then follow up.':'Collect information and follow your existing Approval Matrix.',event:key==='connected'?'Expense preparation started':key==='settlement'?'Settlement preparation started':'Payrun preparation started',stages:[{name:'Prepare',state:'Draft'},{name:'Decision',state:'Pending approval'},{name:'Follow up',state:MATRIX_SAMPLES[key].finalState}]};
}
function integratedDraft(key){const t=TEMPLATES[key],form=expenseForm();if(key!=='connected'){form.id=key+'-details';form.title=key==='settlement'?'Complete the settlement details':'Prepare the payrun handover';form.description='Confirm the missing information before submitting this request.';form.fields=[{id:'department',type:'text',label:'Department',source:'department',access:'readonly'},{id:'notes',type:'textarea',label:key==='settlement'?'Handover notes':'Variance explanation',required:true},{id:'checked',type:'boolean',label:key==='settlement'?'Company assets returned?':'Checks completed?',required:true},{id:'evidence',type:'file',label:'Supporting document',required:false}];}
 const collect=nodeDefaults(initialNode('details','input',key==='connected'?'Collect expense details':'Collect supporting details',0,{owner:'Employee',form}));
 const matrix=nodeDefaults(initialNode('matrix','matrix','Get approval',1,{owner:'Approval Matrix',matrixProcess:key}));
 const email=nodeDefaults(initialNode('email','email','Optional follow-up message',2,{optional:true,enabled:false,body:'Hi {{employee.name}}, here is the guide for your next steps. Contact the team if you need help.'}));
 return {schema:SCHEMA,template:key,name:t.name,event:t.event,scope:{company:'Demo company',match:'all',rules:[]},stages:clone(t.stages),nodes:[nodeDefaults(initialNode('trigger','trigger',t.event,0)),collect,matrix,email],order:['trigger','details','matrix','email'],revision:0,integration:'approval-matrix'};
}
function matrixRoute(n,run){const key=n.matrixProcess||run.draft.template,s=MATRIX_SAMPLES[key];if(!s)return null;return {...clone(s),people:key==='connected'&&run.facts.amount<=1000?['Their manager']:clone(s.people)};}
function matrixActorNode(n,run){const route=run.matrix?.[n.id]?.route||matrixRoute(n,run);return {...n,type:'approval',owner:route?.people[run.matrix?.[n.id]?.index||0]||'System',delegate:true,independent:true};}
function advanceMatrix(run,n){run.matrix??={};let entry=run.matrix[n.id];if(!entry){const route=matrixRoute(n,run);if(!route){run.states[n.id]='blocked';run.status='blocked';logRun(run,n,'No approval route resolved. The request stays blocked.','blocked');return false;}entry=run.matrix[n.id]={route,index:0,attempt:1};logRun(run,n,`Sample Matrix route v${route.version} · ${route.scope}. ${route.people.length?route.people.join(' → '):'No approval needed; still apply and record through the approval service.'}`,'active');}
 if(run.facts.access==='denied'){run.states[n.id]='blocked';run.status='blocked';logRun(run,n,'The assigned person cannot read or act on this record.','blocked');return false;}
 if(entry.index<entry.route.people.length){const actorNode=matrixActorNode(n,run);let why='';if(run.facts.actor==='self')why='The approver is also the requester. An independent person is required.';else if(actorNode.owner==='Their manager'&&run.facts.manager==='expired')why='Approval cover has expired.';
 if(why){run.states[n.id]='blocked';run.status='blocked';logRun(run,n,why,'blocked');return false;}
 run.states[n.id]='waiting';const actor=actorFor(actorNode,run);logRun(run,n,`Awaiting ${actor.name} · ${actor.role}. ${actor.cover||'People and safeguards inherited from Approval Matrix.'}`,'waiting');return false;}
 run.states[n.id]='done';run.outputs[n.id]='Applied';run.recordState=entry.route.finalState;run.appliedCount=(run.appliedCount||0)+1;logRun(run,n,'Approval service applied and recorded the business action once (simulated). Follow-up work can now start.');return true;
}
function respondMatrix(run,n,outcome,answer){if(outcome==='return'){if(!String(answer).trim())return {error:'Explain what needs to change.'};run.states[n.id]='returned';run.status='returned';logRun(run,n,'Sent back for changes: '+answer+'. Resubmission starts a fresh approval attempt.','returned');return {};}
 if(outcome==='reject'){run.states[n.id]='rejected';run.status='rejected';logRun(run,n,'Request rejected; application and follow-up stopped.','rejected');return {};}
 if(outcome!=='approve')return {error:'Choose an approval decision.'};logRun(run,n,`${matrixActorNode(n,run).owner} approved.`);run.matrix[n.id].index++;run.states[n.id]='todo';advanceRun(run);return {};}
function integrationIssues(d){if(d.integration!=='approval-matrix')return [];const out=[],add=(id,text)=>out.push({id,text,severity:'error'}),refs=d.nodes.filter(n=>n.type==='matrix');
 if(refs.length!==1||!d.order.includes(refs[0]?.id))add('trigger','Keep one Approval Matrix step on the main path so no branch bypasses submission.');
 const ref=refs[0],position=ref?d.order.indexOf(ref.id):-1;
 for(const n of d.nodes){if(['approval','policy'].includes(n.type))add(n.id,'Configure approval people and approval rules in Approval Matrix, not a second local sequence.');if(n.type==='state')add(n.id,'Approval Matrix already applies this business action. Remove the duplicate status update.');if(n.type==='input'&&(!d.order.includes(n.id)||d.order.indexOf(n.id)>position))add(n.id,'Collect this information on the main path before Approval Matrix submission.');if(n.type==='matrix'&&n.matrixProcess!==d.template)add(n.id,'The approval reference must match this business process.');}
 if(d.scope.rules.length)add('trigger','Eligibility for an approval-managed process comes from its existing entry point. Extra filters could bypass required submission.');return out;
}
