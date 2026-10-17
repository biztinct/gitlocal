/* Fictional USD demonstration. No statutory or predictive claims. */
(function(root){
'use strict';
const roles=[{key:'ops',name:'Operators',base:140,pay:3200},{key:'specialists',name:'Specialists',base:40,pay:5200},{key:'leads',name:'Team leads',base:16,pay:6200},{key:'office',name:'Office team',base:44,pay:4800}];
const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const defaults={ops:0,specialists:0,leads:0,office:0,growth:12,raise:0,ot:12,training:0,evening:25,night:15,start:3,absence:8,employer:18,deduction:12,stress:0};
const season=[.94,.94,1,1,1.02,1.03,1,.97,1.03,1.09,1.12,1.06];
const ranges={ops:[0,60],specialists:[0,20],leads:[0,10],office:[0,20],growth:[-20,50],raise:[0,15],ot:[0,32],training:[0,15],evening:[20,40],night:[5,30],start:[1,12],absence:[0,20],employer:[0,35],deduction:[0,35],stress:[-20,20]};
function normalize(s){const out={...defaults};for(const k in ranges){const v=Number(s[k]??defaults[k]);out[k]=Number.isFinite(v)?Math.max(ranges[k][0],Math.min(ranges[k][1],v)):defaults[k];}for(const k of ['ops','specialists','leads','office','start'])out[k]=Math.round(out[k]);return out;}
function compute(input){const s=normalize(input);const rows=months.map((name,i)=>{
 const active=i+1>=s.start, ramp=active?Math.min(1,(i+2-s.start)/2):0;
 const heads=Object.fromEntries(roles.map(r=>[r.key,r.base+(active?s[r.key]:0)]));
 const ftes=Object.fromEntries(roles.map(r=>[r.key,r.base+s[r.key]*ramp]));
 const n=heads.ops, evening=Math.round(n*s.evening/100),night=Math.round(n*s.night/100),day=n-evening-night;
 const split=[day,evening,night];const effective=ftes.ops/n;
 const available=split.map(h=>h*effective*(160+s.ot)*(1-s.absence/100)*(1+s.training/100));
 const demand=[12000,6500,3000].map(h=>h*season[i]*(1+s.growth/100*(i+1)/12)*(1+s.stress/100));
 const served=available.map((h,j)=>Math.min(h,demand[j]));
 const skillCap=Math.min(ftes.specialists*650,ftes.leads*1700);
 const raw=served.reduce((a,b)=>a+b,0), skillRatio=Math.min(1,skillCap/Math.max(raw,1));
 const fulfilled=served.map(v=>v*skillRatio), hours=fulfilled.reduce((a,b)=>a+b,0), totalDemand=demand.reduce((a,b)=>a+b,0);
 const salary=roles.reduce((sum,r)=>sum+heads[r.key]*r.pay,0)*(1+(active?s.raise:0)/100);
 const opPay=3200*(1+(active?s.raise:0)/100), overtime=n*s.ot*opPay/160*1.5;
 const premium=(evening*.1+night*.25)*opPay;
 const gross=salary+overtime+premium, contributions=gross*s.employer/100;
 const hiring=active&&i+1===s.start?roles.reduce((sum,r)=>sum+s[r.key]*r.pay*.75,0):0;
 const learning=heads.ops*s.training*35;
 const people=gross+contributions+hiring+learning, revenue=hours*150, other=420000+revenue*.25;
 const profit=revenue-people-other, withholding=gross*s.deduction/100;
 return {name,index:i,heads,headcount:Object.values(heads).reduce((a,b)=>a+b,0),split,available,demand,fulfilled,skillCap,skillRatio,hours,totalDemand,coverage:hours/totalDemand*100,salary,overtime,premium,gross,contributions,hiring,learning,people,revenue,other,profit,margin:profit/revenue*100,withholding,takehome:gross-withholding};
});
const sum=k=>rows.reduce((a,m)=>a+m[k],0);const a={rows,state:s};for(const k of ['revenue','people','other','profit','salary','overtime','premium','gross','contributions','hiring','learning','withholding','takehome','hours','totalDemand'])a[k]=sum(k);
a.margin=a.profit/a.revenue*100;a.coverage=a.hours/a.totalDemand*100;a.headcount=rows[11].headcount;a.unserved=a.totalDemand-a.hours;return a;}
function search(goal,target){const base=compute(defaults), buckets={hire:[],develop:[],balanced:[]};
for(let ops=0;ops<=60;ops+=5)for(let specialists=0;specialists<=15;specialists+=5)for(let leads=0;leads<=6;leads+=2)for(const ot of [0,8,16,24])for(const training of [0,5,10]){
const state={...defaults,ops,specialists,leads,ot,training,evening:30,night:14,start:2,growth:goal==='growth'?target:defaults.growth};const result=compute(state);
const meets=goal==='cost'?result.people<=base.people*(1-target/100)&&result.coverage>=90:goal==='coverage'?result.coverage>=target:result.coverage>=95&&result.margin>=20;
const item={state,result,meets};buckets.balanced.push(item);if(training===0)buckets.hire.push(item);if(ops===0)buckets.develop.push(item);
}
return Object.entries(buckets).map(([lane,list])=>{list.sort((a,b)=>Number(b.meets)-Number(a.meets)||(a.meets?(a.result.people-b.result.people):(goal==='cost'?a.result.people-b.result.people:b.result.coverage-a.result.coverage)));return {lane,...list[0]};});}
root.WFM={roles,months,defaults,ranges,normalize,compute,search};
})(globalThis);
