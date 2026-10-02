import test from 'node:test';
import assert from 'node:assert/strict';
await import('../public/model.js');await import('../public/decision-model.js');
const M=globalThis.WFM,D=globalThis.DECISION;
const sample={...M.defaults,ops:20,specialists:3,leads:1,growth:15,evening:30,night:14};
const near=(a,b)=>assert.ok(Math.abs(a-b)<.001,`${a} != ${b}`);
test('executive goals apply the correct units, floors and ceilings',()=>{
 const a=M.compute(sample),goals=D.normalizeGoals(D.defaults);
 for(const [k,d] of Object.entries(D.definitions)){goals[k]={on:true,target:d.value(a)};}
 assert.ok(D.grade(a,goals).met);
 goals.profit.target+=.01;assert.equal(D.grade(a,goals).failed,1);
 goals.cost.target-=.01;assert.equal(D.grade(a,goals).failed,2);
 goals.heads.target-=1;goals.overtime.target-=1;assert.equal(D.grade(a,goals).failed,4);
 const disabled=Object.fromEntries(Object.keys(goals).map(k=>[k,{...goals[k],on:false}]));assert.equal(D.candidates(sample,disabled).count,0);
});
test('goal paths preserve current business assumptions and disclose each unmet goal',()=>{
 const s={...sample,growth:28,stress:10,raise:4,start:5,office:3,evening:32,night:13,absence:6,employer:22,deduction:17};
 const results=D.candidates(s,D.defaults);assert.equal(results.lanes.length,3);assert.ok(results.count>1000);
 for(const p of results.lanes){for(const k of ['growth','stress','raise','start','office','evening','night','absence','employer','deduction'])assert.equal(p.state[k],s[k],k);assert.equal(p.met,D.evaluate(M.compute(p.state),D.defaults).every(c=>c.met));near(p.result.profit,M.compute(p.state).profit);}
 assert.equal(results.lanes[0].state.training,s.training);assert.equal(results.lanes[1].state.ops,s.ops);
});
test('infeasible combined targets never receive a meets-goals label',()=>{
 const goals=D.normalizeGoals({...D.defaults,profit:{on:true,target:50},cost:{on:true,target:1},heads:{on:true,target:240},overtime:{on:true,target:0}});
 const results=D.candidates(sample,goals);assert.ok(results.lanes.every(p=>!p.met&&p.failed>0));
});
test('hiring room describes exactly the feasible whole-person additions',()=>{
 const goals=D.normalizeGoals({...D.defaults,margin:{on:false,target:25},profit:{on:false,target:10.5},coverage:{on:false,target:97}});
 for(const key of ['ops','office']){const room=D.headroom(sample,goals,key);const listed=room.intervals.flatMap(([lo,hi])=>Array.from({length:hi-lo+1},(_,i)=>lo+i));const exact=room.points.filter(p=>p.met).map(p=>p.add);assert.deepEqual(listed,exact);assert.equal(room.points.length,M.ranges[key][1]-sample[key]+1);for(const p of room.points){const a=M.compute({...sample,[key]:sample[key]+p.add});near(p.profit,a.profit);assert.equal(p.met,D.grade(a,goals).met);}}
});
test('cumulative outlook reconciles to annual totals without summing coverage percentages',()=>{
 const a=M.compute(sample);near(D.series(a,'profit').at(-1),a.profit);near(D.series(a,'people').at(-1),a.people);assert.deepEqual(D.series(a,'coverage'),a.rows.map(r=>r.coverage));near(D.series(a,'profit',false)[2],a.rows[2].profit);
});
