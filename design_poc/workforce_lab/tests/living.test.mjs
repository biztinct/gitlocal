import test from 'node:test';
import assert from 'node:assert/strict';
await import('../public/model.js');
await import('../public/living-model.js');
const {compute,defaults}=globalThis.WFM;
const L=globalThis.LIVING;
const near=(a,b)=>assert.ok(Math.abs(a-b)<.01,a+' != '+b);

test('profit bridge reconciles exactly for any pair of plans',()=>{
 const pairs=[[defaults,{...defaults,ops:20,specialists:3,leads:1,growth:15,evening:30,night:14}],[{...defaults,raise:5},{...defaults,ot:0,training:8}],[{...defaults,growth:50,ops:60},{...defaults,growth:-20,stress:-20}]];
 for(const [a,b] of pairs){const plan=compute(b),ref=compute(a),br=L.bridge(plan,ref);assert.ok(br.check);near(br.start+br.total,br.end);assert.equal(br.steps.length,6);}
 const same=L.bridge(compute(defaults),compute(defaults));same.steps.forEach(s=>near(s.value,0));
});
test('stress band brackets the plan and respects the stress range',()=>{
 const s={...defaults,ops:10};const plan=compute(s),{lo,hi}=L.stressBand(s);
 assert.ok(lo.coverage<=plan.coverage+.001||lo.profit<=plan.profit+.001);
 assert.ok(hi.totalDemand>lo.totalDemand);
 const edge=L.stressBand({...defaults,stress:20});assert.equal(edge.hi.state.stress,20);assert.equal(edge.lo.state.stress,10);
});
test('marginal experiment stops at the demo limit and otherwise proposes +5 operators',()=>{
 const s={...defaults,growth:25};const m=L.marginal(s,compute(s));assert.ok(m.possible);assert.equal(m.state.ops,5);assert.ok(m.title.includes('Five more operators'));
 const full=L.marginal({...defaults,ops:58},compute({...defaults,ops:58}));assert.equal(full.possible,false);
});
test('story names the changes and explains coverage in plain words',()=>{
 const st=L.story(defaults,compute(defaults),defaults,compute(defaults),'Original baseline');assert.ok(st.title.includes('Nothing changed'));
 const s={...defaults,ops:20,raise:5};const st2=L.story(s,compute(s),defaults,compute(defaults),'Original baseline');
 assert.ok(/adding 20 operators/i.test(st2.title));assert.ok(/salary increase/.test(st2.title));assert.ok(/profit/.test(st2.title));assert.ok(st2.copy.length>20);
 const ch=L.changes(s,defaults);assert.equal(ch.length,2);assert.equal(ch[0].key,'ops');
});
test('formatting is stable',()=>{
 assert.equal(L.money(1234567),'$1.23m');assert.equal(L.money(-4500),'−$5k');assert.equal(L.signed(0),'±$0');assert.equal(L.signed(2.34,'pp'),'+2.3 pp');assert.equal(L.signed(-7,'n'),'−7');
 assert.ok(L.stressOutcome(defaults,compute(defaults)).includes('<b>'));
});
