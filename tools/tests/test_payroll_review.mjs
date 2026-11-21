// Mounted OWL regression: asynchronous source details must not erase cell edits.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {JSDOM}=createRequire(import.meta.url)('jsdom');
const root=new URL('../../',import.meta.url),read=p=>fs.readFileSync(new URL(p,root),'utf8');
const dom=new JSDOM('<body><main></main>',{runScripts:'outside-only',pretendToBeVisual:true});
const {window}=dom, errors=[];
window.addEventListener('error',ev=>{errors.push(ev.error);ev.preventDefault();});
window.eval(read('web/static/lib/owl/owl.js'));
const data={id:1,revision:1,name:'Test payroll',period:['2026-10-01','2026-10-31'],currency:'VND',issues:0,affected:0,changes:0,optional:1,global_issues:[],review:{},history:[],people:[{employee_id:1,name:'Test employee',issues:[],cells:{BONUS:{code:'BONUS',rule_id:1,label:'Bonus',editable:true,optional:true,value:null,status:'missing',source_owner:'Monthly adjustments'}}}],columns:[{id:1,code:'BONUS',name:'Bonus',kind:'money',group:'adjustments',optional:true}]};
data.columns.push({id:2,code:'PHONE',name:'Phụ cấp điện thoại (Phone)',kind:'money',group:'records',optional:true},
 {id:3,code:'NETTOTAL',name:'Net pay',kind:'money',group:'results',optional:false});
data.people[0].cells.PHONE={code:'PHONE',rule_id:2,label:'Phụ cấp điện thoại (Phone)',editable:false,optional:false,value:150,status:'resolved',source_owner:'Saved record'};
data.people[0].cells.NETTOTAL={code:'NETTOTAL',rule_id:3,label:'Net pay',editable:false,optional:false,value:1000,status:'preview'};
let calls=[],resolveDetail;
window.services={orm:{call:async(model,method,args)=>{
 if(method==='open_payroll_review')return structuredClone(data);
 if(method==='application_source_detail')return new Promise(r=>{resolveDetail=r;});
 calls.push({method,args});
 if(method==='save_cells'){
  const change=args[3][0];data.revision++;data.changes=change.restore?0:1;data.optional=change.restore?1:0;
  Object.assign(data.people[0].cells.BONUS,{value:change.restore?null:Number(change.value),optional:!!change.restore,edit:change.restore?false:change,tone:change.restore?'normal':'edited'});
  return structuredClone(data);
 }
}},action:{},dialog:{}};
window.eval(`const {Component,useState,onWillStart,useRef,onWillUnmount,xml}=owl;
const useService=n=>window.services[n];
class Dialog extends Component {static template=xml\`<div><t t-slot="default"/><t t-slot="footer"/></div>\`;static props=['*'];}
class ConfirmationDialog extends Component {}
${read('pb_payrun_wizard/static/src/js/payroll_review.js').replace(/^import .*;\n/gm,'').replace('export class','class')}
window.Review=PayrollReviewDialog;`);
const app=new window.owl.App(window.Review,{templates:read('pb_payrun_wizard/static/src/xml/payroll_review.xml'),props:{payload:{formula_config_id:1},onReviewed:()=>{},close:()=>{}}});
const component=await app.mount(window.document.querySelector('main'));
const tick=()=>new Promise(r=>setTimeout(r,30));
const input=()=>window.document.querySelector('[aria-label="Test employee · Bonus"]');
input().focus();input().value='250000';input().dispatchEvent(new window.Event('input',{bubbles:true}));
resolveDetail({explanation:'Optional bonus',actions:[],consumers:[]});await tick();
assert.equal(input().value,'250000','source-detail response preserves in-flight entry');
input().blur();await tick();
assert.equal(calls.length,1,'leaving cell autosaves exactly once');
assert.equal(calls[0].args[3][0].value,'250000');
assert.equal(window.document.querySelector('[role=status]').textContent,'Saved on server');
assert.ok(window.document.querySelector('.pr-edited'),'saved correction is highlighted');
const button=text=>[...window.document.querySelectorAll('button')].find(e=>e.textContent.trim()===text);
button('Restore source value').click();await tick();
assert.equal(input().value,'');assert.equal(data.changes,0);
assert.match(window.document.querySelector('.pr-cell small').textContent,/Optional · left blank/);
const beforeBlank=calls.length;
button('Save correction').click();await tick();
assert.equal(calls.length,beforeBlank,'saving an optional blank sends no write');
input().focus();input().value='0';input().dispatchEvent(new window.Event('input',{bubbles:true}));input().blur();await tick();
assert.equal(calls.length,beforeBlank+1,'explicit zero is saved');
assert.equal(input().value,'0');assert.equal(data.people[0].cells.BONUS.value,0);
input().focus();input().value='';input().dispatchEvent(new window.Event('input',{bubbles:true}));input().blur();await tick();
assert.equal(calls.length,beforeBlank+1,'blank does not erase an existing zero');assert.equal(input().value,'0');
button('Maximize').click();await tick();assert.ok(window.document.querySelector('.pr-max'));
button('Review & continue').click();await tick();assert.equal(window.document.querySelectorAll('.pr-confirm input[type=checkbox]').length,3);
const search=()=>window.document.querySelector('[aria-label="Find a component"]');
const filter=async value=>{search().value=value;search().dispatchEvent(new window.Event('input',{bubbles:true}));await tick();};
const headers=()=>[...window.document.querySelectorAll('.pr-grid thead th')].map(e=>e.textContent);
await filter('dien thoai');assert.equal(headers().length,2);assert.match(headers()[1],/điện thoại/);
assert.equal(headers()[0],'Employee','employee column stays visible');
await filter('phone');assert.equal(headers().length,2,'code match is case insensitive');
const groups=window.document.querySelector('[aria-label="Worksheet columns"]');
groups.value='adjustments';groups.dispatchEvent(new window.Event('change',{bubbles:true}));await tick();
assert.match(window.document.querySelector('.pr-empty').textContent,/No matching components/);
groups.value='all';groups.dispatchEvent(new window.Event('change',{bubbles:true}));await tick();
assert.equal(headers().length,2,'category and search combine');
await filter('nettotal');assert.match(headers()[1],/Net pay/,'search also finds calculated components');
await filter('does not exist');assert.match(window.document.querySelector('.pr-empty').textContent,/No matching components/);
window.document.querySelector('[aria-label="Clear component search"]').click();await tick();
assert.equal(headers().length,4,'clear restores all components');
component.state.pending=true;await tick();assert.ok(search().disabled,'filters cannot hide an unsaved correction');
component.state.pending=false;
component.state.data.people[0].cells.PHONE.issue=true;component.state.data.issues=1;
await filter('bonus');button('Next issue →').click();await tick();
assert.equal(search().value,'','next issue clears the component filter');
assert.equal(component.selected.code,'PHONE');
assert.equal(errors.length,0);app.destroy();window.close();
// Existing workbook addon uses an exact class XPath; status must not match it.
assert.ok(read('pb_payrun_wizard/static/src/xml/payrun_wizard.xml').includes('pw-cov pw-review-status'));
console.log('Payroll worksheet mounted OWL checks passed: delayed source, autosave, highlight, restore, maximize, review checklist, inherited-template compatibility, component name/code/accent search, groups, empty results, clearing, pending-edit protection and next-issue navigation.');
