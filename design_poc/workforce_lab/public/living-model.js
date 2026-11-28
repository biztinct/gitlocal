/* The Living Plan — derived views over the shared WFM engine (model.js).
   Pure functions only: no DOM. Fictional USD demonstration. */
(function(root){
'use strict';
const M=root.WFM;
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));

/* Formatting */
const money=n=>`${n<0?'−':''}$${Math.abs(n)>=1e6?(Math.abs(n)/1e6).toFixed(2)+'m':Math.abs(n)>=1000?Math.round(Math.abs(n)/1000).toLocaleString()+'k':Math.round(Math.abs(n)).toLocaleString()}`;
const signed=(n,unit='money')=>{const a=Math.abs(n);if(a<(unit==='money'?.5:.05))return unit==='money'?'±$0':'±0';const s=n>0?'+':'−';return s+(unit==='money'?money(a):unit==='pp'?a.toFixed(1)+' pp':unit==='pct'?a.toFixed(1)+'%':Math.round(a).toLocaleString());};
const pct=n=>n.toFixed(1)+'%';
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

/* Plain-language names for every lever */
const levers={
 ops:{label:'Add operators',unit:'people',note:'Hands-on delivery capacity',today:140},
 specialists:{label:'Add specialists',unit:'people',note:'Each supports 650 delivery hours a month',today:40},
 leads:{label:'Add team leads',unit:'people',note:'Each supports 1,700 delivery hours a month',today:16},
 office:{label:'Add office roles',unit:'people',note:'Finance, HR and business support. No delivery capacity.',today:44},
 growth:{label:'Demand growth by December',unit:'%',note:'How much more work arrives by year end'},
 raise:{label:'Salary increase',unit:'%',note:'Applies from your chosen start month'},
 ot:{label:'Overtime per operator',unit:'h / mo',note:'Paid at 1.5× base hourly rate'},
 training:{label:'Productivity improvement',unit:'%',note:'Assumed benefit. Costs $35 per point per operator per month.'},
 evening:{label:'Evening shift share',unit:'%',note:'Share of operators · 10% shift premium'},
 night:{label:'Night shift share',unit:'%',note:'Share of operators · 25% shift premium'},
 start:{label:'New hires arrive in',unit:'month',note:'First month at 50% productivity'},
 absence:{label:'Unavailable paid time',unit:'%',note:'Leave, absence and other non-delivery time'},
 employer:{label:'Employer contributions',unit:'% of gross',note:'Added on top of pay. A cost to the business.'},
 deduction:{label:'Employee deductions',unit:'% of gross',note:'Taken from gross pay. Not an extra business cost.'},
 stress:{label:'Demand stress',unit:'%',note:'Immediate change to all demand'}
};

/* Metrics the hero stage can show */
const metrics={
 profit:{title:'ANNUAL OPERATING PROFIT',unit:'MONTHLY PROFIT · USD',row:r=>r.profit,total:a=>a.profit,fmt:money,goodUp:true},
 people:{title:'ANNUAL WORKFORCE COST',unit:'MONTHLY WORKFORCE COST · USD',row:r=>r.people,total:a=>a.people,fmt:money,goodUp:false},
 coverage:{title:'DEMAND SERVED THIS YEAR',unit:'MONTHLY DEMAND SERVED · %',row:r=>r.coverage,total:a=>a.coverage,fmt:pct,goodUp:true}
};

/* Waterfall from a reference plan's profit to this plan's profit. Sums exactly. */
function bridge(plan,ref){
 const steps=[
  ['More revenue delivered',plan.revenue-ref.revenue,'Demand you could serve × $150 an hour'],
  ['Base salaries',-(plan.salary-ref.salary),'Headcount and pay levels'],
  ['Overtime & shift premiums',-((plan.overtime+plan.premium)-(ref.overtime+ref.premium)),'Hours beyond 160 plus evening and night uplifts'],
  ['Employer contributions',-(plan.contributions-ref.contributions),'A share of gross pay, paid by the business'],
  ['Recruiting & development',-((plan.hiring+plan.learning)-(ref.hiring+ref.learning)),'One-off hiring cost plus training spend'],
  ['Other operating costs',-(plan.other-ref.other),'Fixed $420k a month plus 25% of revenue']
 ].map(([label,value,note])=>({label,value,note}));
 const total=steps.reduce((s,x)=>s+x.value,0);
 return {start:ref.profit,end:plan.profit,steps,total,check:Math.abs(total-(plan.profit-ref.profit))<.01};
}

/* Same plan under softer and stronger demand */
function stressBand(state,width=10){
 const lo=M.compute({...state,stress:clamp(state.stress-width,M.ranges.stress[0],M.ranges.stress[1])});
 const hi=M.compute({...state,stress:clamp(state.stress+width,M.ranges.stress[0],M.ranges.stress[1])});
 return {lo,hi};
}

/* What five more operators would do from here */
function marginal(state,plan){
 const room=M.ranges.ops[1]-state.ops;
 if(room<5)return {possible:false,title:'You have reached the demo limit for extra operators.',copy:'Try support roles, productivity or shift balance instead.'};
 const next=M.compute({...state,ops:state.ops+5});
 const dProfit=next.profit-plan.profit,dCov=next.coverage-plan.coverage,dCost=next.people-plan.people;
 const title=dProfit>0?`Five more operators would add ${money(dProfit)} of profit.`:`Five more operators would cost ${money(-dProfit)} of profit.`;
 const copy=dCov>.05?`Coverage rises ${signed(dCov,'pp')} for ${money(dCost)} more workforce cost a year.`:`Coverage barely moves. The work is not there, or specialists and leads are the limit.`;
 return {possible:true,title,copy,state:{...state,ops:state.ops+5}};
}

/* Which levers differ from the reference, most important first */
function changes(state,refState){
 const list=[];
 for(const k in levers){const d=state[k]-refState[k];if(d)list.push({key:k,delta:d,from:refState[k],to:state[k]});}
 const weight={ops:6,specialists:5,leads:5,office:4,growth:5,raise:5,ot:4,training:4,evening:2,night:2,start:2,absence:3,employer:2,deduction:1,stress:3};
 return list.sort((a,b)=>weight[b.key]*Math.abs(b.delta)/(M.ranges[b.key][1]-M.ranges[b.key][0])-weight[a.key]*Math.abs(a.delta)/(M.ranges[a.key][1]-M.ranges[a.key][0]));
}
function describeChange(c){
 const m=M.months;
 switch(c.key){
  case'ops':case'specialists':case'leads':case'office':return `${c.delta>0?'adding':'removing'} ${Math.abs(c.delta)} ${levers[c.key].label.replace('Add ','')}`;
  case'growth':return `planning for ${c.to}% demand growth`;
  case'raise':return `a ${c.to}% salary increase`;
  case'ot':return `${c.to} hours of overtime per operator a month`;
  case'training':return `a ${c.to}% productivity gain`;
  case'evening':return `${c.to}% of operators on evenings`;
  case'night':return `${c.to}% of operators on nights`;
  case'start':return `hires arriving in ${m[c.to-1]}`;
  case'absence':return `${c.to}% unavailable time`;
  case'employer':return `${c.to}% employer contributions`;
  case'deduction':return `${c.to}% employee deductions`;
  case'stress':return `${c.to>0?'+':''}${c.to}% demand stress`;
 }
 return '';
}

/* One caption: what you changed, what happened, why */
function story(state,plan,refState,ref,refName){
 const ch=changes(state,refState),dP=plan.profit-ref.profit,dC=plan.coverage-ref.coverage,dCost=plan.people-ref.people;
 if(!ch.length)return {title:`This is the ${refName.toLowerCase()}. Nothing changed yet.`,copy:'Move one lever on the left and watch people, coverage and profit respond together.'};
 const lead=ch.slice(0,2).map(describeChange).join(' and ');
 const title=`${lead[0].toUpperCase()+lead.slice(1)} ${dP>=0?'adds':'costs'} ${money(Math.abs(dP))} of annual profit${ch.length>2?` with ${ch.length-2} smaller change${ch.length>3?'s':''}`:''}.`;
 const why=[];
 if(Math.abs(dC)>=.05)why.push(`Demand served changes by ${signed(dC,'pp')}.`);
 else why.push('The percentage of demand served is unchanged.');
 const dR=plan.revenue-ref.revenue;
 why.push(Math.abs(dR)>=1?`Delivered revenue is ${signed(dR)} for the year.`:'Delivered revenue is unchanged.');
 if(Math.abs(dCost)>=1)why.push(`Workforce cost is ${signed(dCost)} for the year.`);
 const skill=plan.rows.filter(r=>r.skillRatio<.999).length;
 if(skill)why.push(`In ${skill} month${skill>1?'s':''} specialists or team leads cap what operators can deliver.`);
 if(plan.coverage<95)why.push(`${pct(100-plan.coverage)} of demand still goes unserved.`);
 return {title,copy:why.join(' ')};
}

/* Stress sentence for the reality-check panel */
function stressOutcome(state,plan){
 const {lo,hi}=stressBand(state);
 const label=state.stress<0?'softer demand':state.stress>0?'stronger demand':'your forecast';
 return `Under <b>${label}</b> this plan makes <b>${money(plan.profit)}</b> and serves <b>${pct(plan.coverage)}</b> of demand. If demand lands 10% either side of that, profit ranges from <b>${money(Math.min(lo.profit,hi.profit))}</b> to <b>${money(Math.max(lo.profit,hi.profit))}</b>. ${hi.coverage<95?'Stronger demand would leave '+pct(100-hi.coverage)+' unserved: capacity, not demand, becomes the limit.':'The team can absorb the upside.'}`;
}

/* Model assumptions, for the dialog */
const assumptions=[
 ['People and pay','240 fictional staff: 140 operators ($3,200), 40 specialists ($5,200), 16 team leads ($6,200), 44 office ($4,800) monthly base pay. 160 ordinary paid hours a month.'],
 ['Extra hours','Overtime is paid at 1.5×. Evening shifts carry a 10% premium and night shifts 25%. Shift shares apply to operators all year.'],
 ['Hiring','New people are paid in full from their arrival month and deliver 50% capacity in that month, then 100%. Recruiting costs 75% of one month’s base pay per hire.'],
 ['Demand and revenue','Every fulfilled hour earns $150. Delivery is capped by demand, by available operator hours per shift, and by specialist (650 h) and team lead (1,700 h) support per person per month. Demand follows a seasonal curve and grows to your December target.'],
 ['Other costs','$420,000 a month plus 25% of revenue. Profit is operating profit before financing and income tax.'],
 ['Contributions and deductions','Employer contributions are added to cost. Employee deductions are withholding within gross pay, not an extra business cost. Both are flat illustrative rates, not statutory rules.'],
 ['What is left out','Attrition, severance, working capital, roster legality and individual employees. This is a planning sketch, not a payroll calculation.']
];

root.LIVING={money,signed,pct,esc,levers,metrics,bridge,stressBand,marginal,changes,describeChange,story,stressOutcome,assumptions,clamp};
})(globalThis);
