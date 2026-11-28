/* Option 05. Pure executive-goal views over the shared fictional WFM engine. */
(function(root){
'use strict';
const M=root.WFM;
const definitions={
 margin:{label:'Operating margin',short:'Margin',unit:'%',sense:'min',min:0,max:60,step:.5,value:a=>a.margin,format:v=>v.toFixed(1)+'%'},
 profit:{label:'Annual operating profit',short:'Profit',unit:'$m',sense:'min',min:0,max:50,step:.1,value:a=>a.profit/1e6,format:v=>'$'+v.toFixed(2)+'m'},
 cost:{label:'Annual workforce budget',short:'Budget',unit:'$m',sense:'max',min:1,max:50,step:.1,value:a=>a.people/1e6,format:v=>'$'+v.toFixed(2)+'m'},
 coverage:{label:'Annual demand served',short:'Coverage',unit:'%',sense:'min',min:50,max:100,step:.5,value:a=>a.coverage,format:v=>v.toFixed(1)+'%'},
 heads:{label:'Team size ceiling',short:'Team size',unit:'people',sense:'max',min:240,max:350,step:1,value:a=>a.headcount,format:v=>Math.round(v)+' people'},
 overtime:{label:'Overtime per operator',short:'Overtime',unit:'h/mo',sense:'max',min:0,max:32,step:1,value:a=>a.state.ot,format:v=>v+' h/mo'}
};
const defaults={margin:{on:true,target:25},profit:{on:true,target:10.5},cost:{on:true,target:16.5},coverage:{on:true,target:97},heads:{on:false,target:270},overtime:{on:false,target:8}};
function normalizeGoals(input){return Object.fromEntries(Object.entries(definitions).map(([k,d])=>{const g=input?.[k]||defaults[k],v=Number(g.target);return [k,{on:typeof g.on==='boolean'?g.on:defaults[k].on,target:Number.isFinite(v)?Math.min(d.max,Math.max(d.min,d.step===1?Math.round(v):v)):defaults[k].target}];}));}
function evaluate(plan,goals){const g=normalizeGoals(goals);return Object.entries(definitions).filter(([k])=>g[k].on).map(([key,d])=>{const actual=d.value(plan),target=g[key].target,gap=d.sense==='min'?target-actual:actual-target;return {key,...d,actual,target,gap,met:gap<=1e-8,shortfall:Math.max(0,gap)/Math.max(Math.abs(target),1)};});}
function grade(plan,goals){const checks=evaluate(plan,goals);return {checks,met:checks.every(c=>c.met),failed:checks.filter(c=>!c.met).length,score:checks.reduce((v,c)=>v+c.shortfall,0)};}
function candidates(input,goals){const state=M.normalize(input),g=normalizeGoals(goals),lanes={hire:null,develop:null,balanced:null};let count=0;
 if(!Object.values(g).some(x=>x.on))return {lanes:[],count:0};
 const values=(standard,current)=>[...new Set([...standard,current])].sort((a,b)=>a-b);
 const rank=(a,b)=>!b||a.failed<b.failed||(a.failed===b.failed&&(a.score<b.score-1e-9||(Math.abs(a.score-b.score)<1e-9&&(a.result.people<b.result.people-.01||(Math.abs(a.result.people-b.result.people)<.01&&a.change<b.change)))));
 function visit(s){const result=M.compute(s),rating=grade(result,g),change=['ops','specialists','leads','ot','training'].reduce((n,k)=>n+Math.abs(s[k]-state[k]),0),item={state:s,result,...rating,change};count++;for(const lane of ['balanced',...(s.training===state.training?['hire']:[]),...(s.ops===state.ops?['develop']:[])])if(rank(item,lanes[lane]))lanes[lane]=item;}
 visit({...state});
 for(const ops of values(Array.from({length:13},(_,i)=>i*5),state.ops))for(const specialists of values([0,5,10,15,20],state.specialists))for(const leads of values([0,2,4,6,8,10],state.leads))for(const ot of values([0,8,16,24],state.ot))for(const training of values([0,5,10,15],state.training))visit({...state,ops,specialists,leads,ot,training});
 return {count,lanes:['hire','develop','balanced'].map(lane=>({lane,...lanes[lane]}))};
}
function headroom(input,goals,key='ops'){if(!M.roles.some(r=>r.key===key))throw Error('Unknown workforce role');const s=M.normalize(input),checks=evaluate(M.compute(s),goals),points=[];
 for(let add=0;add<=M.ranges[key][1]-s[key];add++){const result=M.compute({...s,[key]:s[key]+add}),rating=grade(result,goals);points.push({add,profit:result.profit,met:checks.length>0&&rating.met,failed:rating.failed});}
 const intervals=[];for(const p of points)if(p.met){const last=intervals.at(-1);if(last&&last[1]===p.add-1)last[1]=p.add;else intervals.push([p.add,p.add]);}
 return {points,intervals,enabled:checks.length>0};
}
function series(plan,key,cumulative=true){let sum=0;return plan.rows.map(r=>cumulative&&key!=='coverage'?(sum+=r[key]):r[key]);}
root.DECISION={definitions,defaults,normalizeGoals,evaluate,grade,candidates,headroom,series};
})(globalThis);
