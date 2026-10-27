const fs=require('fs'),assert=require('assert/strict'),{JSDOM}=require(process.env.STUDIO_NODE_MODULES ? process.env.STUDIO_NODE_MODULES + '/jsdom' : 'jsdom');
const dom=new JSDOM('<html><body><div id="app"></div></body></html>',{runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window;
const read=p=>fs.readFileSync(p,'utf8');w.eval(read('web/static/lib/owl/owl.js'));const o=w.owl;
const reg={category:()=>({add:()=>{},getAll:()=>[]})};
const patch=w.Function(read('web/static/src/core/utils/patch.js').replaceAll('export ','')+';return patch;')();
class Dummy extends o.Component{};Dummy.template=o.xml`<div/>`;Dummy.props=['*'];
const user={id:2,name:'Review owner',login:'owner@example.invalid',in_module:true,assignments:[],extras:[]};
const data={workspace:'hiring',workspaces:[{key:'hiring',label:'Hiring'},{key:'people',label:'People'}],can_manage:true,central_owner:true,company:'Example company',profiles:[],people:[user],roles:[{id:5,name:'Recruiter',workspace:'hiring',allowed:true},{id:6,name:'Payroll viewer',workspace:'payroll',allowed:true}],role_ids:[5],requests:[],history:[],resources:[{key:'hr.applicant',label:'Candidates',fields:[{key:'partner_name',label:'Name',required:true},{key:'salary_expected',label:'Salary expected',sensitive:true}],department:true,states:[],owner_label:'Recruiter'}],departments:[],owners:[]};
const calls=[];const svc={call:async(m,method,args)=>{calls.push({method,args});if(method==='get_board')return{can_manage:true,me:user,profiles:[],areas:[],mine:[],delegations:[],kpis:{}};if(method==='studio_data')return structuredClone(data);if(method==='studio_role_policy')return{id:5,name:'Recruiter',revision:1,people:[],profiles:[],policy:{}};if(method==='studio_explain')return{allowed:false,sources:[],company:'Example company',note:'Application rules apply'};if(method==='people')return[];if(method==='screens')return{sections:[],rows:[]};return{message:'Submitted',sections:[],rows:[]}},add:()=>{},doAction:()=>{}};
const source=read('biz_access/static/src/js/access_board.js').replace(/^import .*;$/gm,'').replaceAll('export ','');
const C=w.Function('Component','useState','onWillStart','useExternalListener','useService','registry','_t','deserializeDateTime','formatDateTime','ic','HubBackChip','hubBack','PbMiniRail','railIcon',source+';return PbAccessBoard;')(o.Component,o.useState,o.onWillStart,o.useExternalListener,()=>svc,reg,s=>s,s=>s,s=>s,()=>o.markup(''),Dummy,()=>null,Dummy,()=>o.markup(''));
const extension=read('biz_access/static/src/js/access_studio.js').replace(/^import .*;$/gm,'');
w.Function('patch','registry','_t','PbAccessBoard','useEffect','onWillUnmount',extension)(patch,reg,s=>s,C,o.useEffect,o.onWillUnmount);
const merged=new w.DOMParser().parseFromString(read('biz_access/static/src/xml/access_board.xml'),'text/xml');
const extensionDoc=new w.DOMParser().parseFromString(read('biz_access/static/src/xml/access_studio.xml'),'text/xml');
for(const xp of extensionDoc.documentElement.children[0].children){
 const result=merged.evaluate(xp.getAttribute('expr'),merged,null,w.XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,null);
 assert(result.snapshotLength,'Extension XPath must match');
 for(let i=0;i<result.snapshotLength;i++){
  const target=result.snapshotItem(i),position=xp.getAttribute('position');
  for(const child of xp.children){const copy=merged.importNode(child,true);if(position==='inside')target.appendChild(copy);else if(position==='after')target.parentNode.insertBefore(copy,target.nextSibling);else target.parentNode.insertBefore(copy,target);}
  if(position==='replace')target.remove();
 }
}
for(const t of [...extensionDoc.documentElement.children].slice(1))merged.documentElement.appendChild(merged.importNode(t,true));
const dummy=merged.createElement('t');dummy.setAttribute('t-name','pb_import_kit.QuietGlance');dummy.appendChild(merged.createElement('div'));merged.documentElement.appendChild(dummy);
const templates=new w.XMLSerializer().serializeToString(merged);
const app=new o.App(C,{templates,props:{},env:{bus:{trigger:()=>{}}}});
const tick=()=>new Promise(r=>setTimeout(r,50));
const button=text=>[...w.document.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
(async()=>{const c=await app.mount(w.document.getElementById('app'));assert(w.document.body.textContent.includes('Access Studio'));assert(button('Explain access'));
button('Explain access').click();await tick();assert(w.document.querySelector('[role=dialog]'));assert(w.document.body.textContent.includes('Not allowed by current access'));button('Close').click();await tick();
button('Profiles').click();await tick();button('New profile').click();await tick();assert(button('Submit for review').disabled);assert(w.document.body.textContent.includes('Roles in this profile'));assert(!w.document.querySelector('[role=dialog]').textContent.includes('Payroll viewer'));
c.state.studioDialog.includeOtherModules=true;await tick();assert(w.document.querySelector('[role=dialog]').textContent.includes('Payroll viewer'));
c.state.studioDialog.roleSearch='Recruiter';await tick();assert(!w.document.querySelector('[role=dialog]').textContent.includes('Payroll viewer'));button('Close').click();await tick();
await c.studioOpenPolicy({id:5});await tick();button('Add a policy').click();await tick();assert(w.document.querySelector('[aria-label="View scope"]'));
button('Form fields').click();await tick();assert(w.document.querySelector('[aria-label="Name permission"]'));button('Review & submit').click();await tick();assert(w.document.body.textContent.includes('Review policy changes'));button('Close').click();await tick();
c.setLens('reviews');await tick();assert(w.document.body.textContent.includes('No requests in this view'));c.setLens('studio_history');await tick();assert(w.document.body.textContent.includes('No Studio changes yet'));c.setLens('screens');await tick();assert(w.document.body.textContent.includes('See it as'));
app.destroy();w.close();console.log('PASS mounted full inherited Access Studio: people, explain drawer, profile editor, policy fields, review, history, preserved screens and preview control');})().catch(e=>{console.error(e);process.exitCode=1});
