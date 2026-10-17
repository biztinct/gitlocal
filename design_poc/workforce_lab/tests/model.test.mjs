import test from 'node:test';
import assert from 'node:assert/strict';
await import('../public/model.js');
const {compute,defaults,search}=globalThis.WFM;
const near=(a,b)=>assert.ok(Math.abs(a-b)<.001, a+' != '+b);
test('money flows reconcile and deductions are not an extra cost',()=>{
 for(const s of [defaults,{...defaults,ops:40,raise:8,training:10,employer:25,deduction:30},{...defaults,ot:0,growth:-20,absence:20}]){
 const a=compute(s);for(const r of [a,...a.rows]){near(r.revenue-r.people-r.other,r.profit);near(r.gross-r.withholding,r.takehome);near(r.salary+r.overtime+r.premium,r.gross);near(r.gross+r.contributions+r.hiring+r.learning,r.people);}near(a.rows.reduce((x,r)=>x+r.profit,0),a.profit);}
 const before=compute(defaults),after=compute({...defaults,deduction:30});near(before.people,after.people);near(before.profit,after.profit);assert.ok(after.takehome<before.takehome);
});
test('hiring respects start month and one-off recruiting cost',()=>{
 const a=compute({...defaults,ops:10,start:12});assert.equal(a.rows[10].heads.ops,140);assert.equal(a.rows[11].heads.ops,150);assert.equal(a.rows[10].hiring,0);assert.equal(a.rows[11].hiring,24000);assert.equal(a.headcount,250);near(a.rows[0].people,compute(defaults).rows[0].people);
});
test('delivery is bounded by demand, shifts and skills at extreme inputs',()=>{
 for(const growth of [-20,50])for(const ops of [0,60])for(const ot of [0,32]){const a=compute({...defaults,growth,ops,ot,training:15});for(const m of a.rows){assert.ok(m.hours<=m.totalDemand+.001);assert.ok(m.hours<=m.skillCap+.001);assert.equal(m.split.reduce((x,v)=>x+v,0),m.heads.ops);m.fulfilled.forEach((v,i)=>assert.ok(v<=m.available[i]+.001&&v<=m.demand[i]+.001));assert.ok(Number.isFinite(m.profit));assert.ok(m.coverage<=100.00001);}}
});
test('office hiring cannot invent revenue; salary rise does not change coverage',()=>{
 const a=compute({...defaults,growth:-20,ops:60,specialists:20,leads:10,training:15});const b=compute({...a.state,office:20});near(a.revenue,b.revenue);assert.ok(b.people>a.people);const c=compute({...defaults,raise:5});assert.ok(c.profit<compute(defaults).profit);near(c.coverage,compute(defaults).coverage);
});
test('goal search is reproducible and discloses an impossible target',()=>{
 const paths=search('growth',15);assert.equal(paths.length,3);assert.ok(paths.every(p=>p.meets));paths.forEach(p=>{near(compute(p.state).people,p.result.people);assert.ok(p.result.coverage>=95&&p.result.margin>=20);});assert.equal(paths[1].state.ops,0);assert.equal(paths[0].state.training,0);assert.ok(search('cost',50).every(p=>!p.meets));
});
