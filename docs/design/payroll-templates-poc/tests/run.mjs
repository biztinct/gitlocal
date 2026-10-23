import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const X=require('../vendor/xlsx.full.min.js');
const sandbox={window:{XLSX:X},TextEncoder,TextDecoder,Uint8Array,Date,console};
for(const f of ['data','workbooks'])vm.runInNewContext(fs.readFileSync(new URL('../'+f+'.js',import.meta.url),'utf8'),sandbox,{filename:f+'.js'});
const D=sandbox.window.PayrollDemo,W=sandbox.window.PayrollWorkbooks;
let passed=0;
function test(name,fn){fn();passed++;console.log('PASS '+name);}
function ctx(country='VN',kind='employee',period='2026-10'){
  const m=D.seed(country);return {country,kind,period,records:m.records,monthly:m.periods[period]||{},layout:D.layout(country),version:1};
}
function file(c,edits){return W.parse(W.build(c,edits),'example.xlsx');}
function part(bytes,path){const c=X.CFB.read(new Uint8Array(bytes),{type:'array'}),i=c.FullPaths.findIndex(p=>p.endsWith('/'+path));return new TextDecoder().decode(c.FileIndex[i].content);}
for(const country of ['VN','IN','ID','SG']){
  test(country+' employee export keeps identity and current records',()=>{
    const c=ctx(country),b=W.build(c),p=W.parse(b,'employee.xlsx'),r=W.review(p,c);
    assert.equal(p.sheets['Employee records'][1][0],'000001');
    assert.equal(p.sheets['Employee records'][1][1],'maya@example.com');
    assert.equal(r.changes.length,0);assert.equal(r.issues.length,0);
    assert.ok(part(b,'xl/workbook.xml').includes('state="veryHidden"'));
    const sheet=part(b,'xl/worksheets/sheet1.xml');
    assert.ok(sheet.includes('sheetProtection'));assert.ok(sheet.includes('state="frozen"'));
    assert.match(sheet,/<c r="A2"[^>]*s="3"/);
    assert.match(sheet,/<c r="B2"[^>]*s="3"/);
    assert.match(sheet,/<c r="G2"[^>]*s="4"/);
    assert.ok(part(b,'xl/styles.xml').includes('<protection locked="0"/>'));
  });
  test(country+' monthly export has exactly two visible tabs and matching employee ids',()=>{
    const c=ctx(country,'monthly'),p=file(c),r=W.review(p,c);
    assert.deepEqual(Object.keys(p.sheets),['Time','Monthly adjustments']);
    assert.deepEqual(Array.from(p.sheets.Time.slice(1),r=>r[0]),Array.from(p.sheets['Monthly adjustments'].slice(1),r=>r[0]));
    assert.equal(r.changes.length,0);assert.equal(r.issues.length,0);
  });
  test(country+' new month leaves payments and paid days blank',()=>{
    const c=ctx(country,'monthly','2026-11'),p=file(c);
    const time=p.sheets.Time,adj=p.sheets['Monthly adjustments'];
    assert.equal(time[1][time[0].indexOf('Standard working days')],21);
    assert.ok(W.blank(time[1][time[0].indexOf('Paid days')]));
    assert.ok(W.blank(adj[1][adj[0].indexOf('Bonus')]));
    assert.equal(W.review(p,c).changes.length,0);
  });
}
test('employee blanks preserve data and explicit zero is a change',()=>{
  const c=ctx(),p=file(c,{'Employee records':[{row:0,key:'salary',value:''},{row:1,key:'phone',value:0}]}),r=W.review(p,c);
  assert.equal(r.blanks,1);assert.equal(r.changes.length,1);
  assert.equal(r.changes[0].key,'phone');assert.equal(r.changes[0].after,0);
  assert.equal(c.records[0].salary,30000000);
});
test('monthly blanks preserve the selected month and zero clears an existing payment',()=>{
  const c=ctx('VN','monthly');
  const blank=W.review(file(c,{'Monthly adjustments':[{row:0,key:'bonus',value:''}]}),c);
  assert.equal(blank.changes.length,0);assert.equal(c.monthly['000001'].bonus,1200000);
  const zero=W.review(file(c,{'Monthly adjustments':[{row:0,key:'bonus',value:0}]}),c);
  assert.equal(zero.changes.length,1);assert.equal(zero.changes[0].after,0);assert.equal(zero.changes[0].before,1200000);
});
test('zero in a new month is saved distinctly from a blank',()=>{
  const c=ctx('VN','monthly','2026-11'),r=W.review(file(c,{'Monthly adjustments':[{row:0,key:'bonus',value:0}]}),c);
  assert.equal(r.changes.length,1);assert.equal(r.changes[0].after,0);
  assert.ok(W.blank(r.changes[0].before));
});
test('edited Employee ID and email are blocked',()=>{
  const c=ctx();
  assert.ok(W.review(file(c,{'Employee records':[{row:0,key:'id',value:'EDITED'}]}),c).issues.some(i=>i.title==='Employee ID was edited'));
  assert.ok(W.review(file(c,{'Employee records':[{row:0,key:'email',value:'changed@example.com'}]}),c).issues.some(i=>i.title==='Email is read-only'));
});
test('duplicate identities and missing cross-tab relationships are blocked',()=>{
  const c=ctx('VN','monthly'),p=file(c);p.sheets.Time.push(p.sheets.Time[1]);
  assert.ok(W.review(p,c).issues.some(i=>i.title.startsWith('Duplicate Employee ID')));
  p.sheets.Time=p.sheets.Time.filter((r,i)=>i===0||r[0]!=='000001');
  assert.ok(W.review(p,c).issues.some(i=>i.title.startsWith('Employee missing from Time')));
});
test('wrong month, configuration and stale layout are blocked',()=>{
  const c=ctx('VN','monthly'),p=file(c);
  p.meta['Pay month']='2026-09';p.meta.Country='SG';p.meta['Layout version']=0;
  const r=W.review(p,c);assert.ok(r.issues.some(i=>i.title==='The pay month does not match'));assert.ok(r.issues.some(i=>i.title==='Payroll configuration does not match'));assert.ok(r.issues.some(i=>i.title==='The template layout has changed'));
});
test('a record changed after download requires a conflict decision',()=>{
  const c=ctx(),p=file(c,{'Employee records':[{row:0,key:'salary',value:33000000}]});c.records[0].salary=31000000;
  const r=W.review(p,c);assert.equal(r.issues.length,1);assert.equal(r.issues[0].key,'000001|salary');
  assert.equal(W.review(p,c,{'000001|salary':'current'}).changes.length,0);
  const accepted=W.review(p,c,{'000001|salary':'incoming'});assert.equal(accepted.issues.length,0);assert.equal(accepted.changes[0].before,31000000);
});
test('a field moved across tabs exports and reviews under its new placement',()=>{
  const c=ctx('VN','monthly');c.layout.time.push('bonus');c.layout.adjustments=c.layout.adjustments.filter(k=>k!=='bonus');
  const p=file(c,{Time:[{row:0,key:'bonus',value:0}]}),r=W.review(p,c);
  assert.ok(p.sheets.Time[0].includes('Bonus'));assert.ok(!p.sheets['Monthly adjustments'][0].includes('Bonus'));
  assert.equal(r.changes[0].tab,'Time');assert.equal(r.changes[0].key,'bonus');assert.equal(r.changes[0].after,0);
});
test('saved record context in monthly files cannot be used to edit salary',()=>{
  const c=ctx('VN','monthly');c.layout.time.push('salary');c.layout.available=c.layout.available.filter(k=>k!=='salary');
  const r=W.review(file(c,{Time:[{row:0,key:'salary',value:45000000}]}),c);
  assert.ok(r.issues.some(i=>i.title==='Saved context is read-only'));assert.equal(r.changes.length,0);
});
test('unrecognised employees and non-numeric amounts are blocked',()=>{
  const c=ctx();const p=file(c,{'Employee records':[{row:0,key:'id',value:1},{row:0,key:'email',value:''},{row:1,key:'salary',value:'not a number'}]});
  const r=W.review(p,c);assert.ok(r.issues.some(i=>i.title.startsWith('Employee ID not found')));assert.ok(r.issues.some(i=>i.title==='A numeric value is required'));
});
console.log('\n'+passed+' behavioral checks passed.');
