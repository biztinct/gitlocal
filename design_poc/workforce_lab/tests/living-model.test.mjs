import test from 'node:test';
import assert from 'node:assert/strict';
await import('../public/model.js');
await import('../public/living-model.js');
const {compute,defaults}=WFM,{bridge,stressBand,marginal}=LIVING;
const sample={...defaults,ops:10,growth:15,ot:0,training:5,evening:30,night:14,start:2};
const near=(a,b)=>assert.ok(Math.abs(a-b)<.001,`${a} != ${b}`);
test('profit bridge reconciles increases, savings, pinned comparisons and no change',()=>{
 const scenarios=[defaults,sample,{...defaults,ops:60,raise:15,training:15,ot:32,employer:35,growth:-20,stress:-20},{...defaults,ot:0,evening:30,night:14,deduction:30}];
 for(const s of scenarios)for(const r of scenarios){const a=compute(s),b=compute(r),v=bridge(a,b);near(v.steps.reduce((n,p)=>n+p.value,0),a.profit-b.profit);near(v.total,a.profit-b.profit);}
});
test('stress envelope respects model bounds and bounds realized profit and coverage',()=>{
 for(const stress of [-20,-10,0,10,20]){const s={...sample,stress},mid=compute(s),env=stressBand(s);assert.ok(env.lo.state.stress>=-20&&env.hi.state.stress<=20);assert.ok(env.lo.profit<=mid.profit+.001);assert.ok(env.hi.profit>=mid.profit-.001);assert.ok(env.lo.coverage>=mid.coverage-.001);assert.ok(env.hi.coverage<=mid.coverage+.001);}
});
test('five-more experiment uses full model and stops at the hiring bound',()=>{const result=marginal(sample,compute(sample));assert.equal(result.state.ops,sample.ops+5);assert.ok(result.possible);assert.equal(marginal({...sample,ops:56},compute({...sample,ops:56})).possible,false);assert.ok(marginal({...sample,ops:55},compute({...sample,ops:55})).possible);});
