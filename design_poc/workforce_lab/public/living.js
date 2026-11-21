/* The Living Plan — page behaviour. Depends on model.js (WFM) and living-model.js (LIVING). */
(function(){
'use strict';
const M=WFM,L=LIVING,$=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const {money,signed,pct,esc,levers,metrics}=L;
const reduceMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---------- state ---------- */
const examples={balanced:{name:'Thoughtful growth',state:{ops:20,specialists:3,leads:1,growth:15,evening:30,night:14,start:3}},pay:{name:'Invest in people',state:{raise:5,training:5}},hours:{name:'Ease overtime',state:{ot:0,training:8,evening:30,night:14}}};
let state=M.normalize({...M.defaults,...examples.balanced.state}),sceneName='Thoughtful growth · example plan';
let pinned=null;
let history=[],saved=[],reference={name:'Original baseline',state:{...M.defaults}},month=8,metric='profit',diffMode=false,motion=!reduceMotion,role='ops',detail='coverage',playing=null,paths=[],goalKind='growth';
function readSaved(){try{return JSON.parse(localStorage.getItem('workforceFutures.scenarios')||'[]').filter(x=>x&&typeof x.name==='string'&&x.state).slice(0,5).map(x=>({...x,state:M.normalize(x.state)}));}catch(e){return [];}}
saved=readSaved();
const baseline=M.compute(M.defaults);
let plan=M.compute(state),ref=baseline,band=L.stressBand(state);
function recompute(){plan=M.compute(state);ref=M.compute(reference.state);band=L.stressBand(state);}

/* ---------- helpers ---------- */
function stopPlay(){if(playing)clearInterval(playing);playing=null;$('#play').setAttribute('aria-pressed','false');$('#play').setAttribute('aria-label','Play through the year');$('#play').textContent='▶';}
function toast(msg){const el=$('#toast');el.hidden=false;el.textContent=msg;clearTimeout(toast.t);toast.t=setTimeout(()=>el.hidden=true,4200);}
function pushHistory(){history.push({state:{...state},name:sceneName});if(history.length>40)history.shift();$('#undo').disabled=false;}
function commit(next,name){pushHistory();state=M.normalize(next);sceneName=name||'Your working plan';syncControls();render(true);}
function css(v){return getComputedStyle(document.body).getPropertyValue(v).trim();}
function canvas2d(c){const b=c.getBoundingClientRect();if(b.width<1||b.height<1)return null;const dpr=window.devicePixelRatio||1;c.width=b.width*dpr;c.height=b.height*dpr;const x=c.getContext('2d');x.scale(dpr,dpr);return {x,w:b.width,h:b.height};}
function pctFill(el){const r=M.ranges[el.dataset.key];el.style.setProperty('--fill',((state[el.dataset.key]-r[0])/(r[1]-r[0])*100).toFixed(1)+'%');}

/* ---------- controls ---------- */
function lever(key){const d=levers[key],r=M.ranges[key],v=state[key],rv=reference.state[key];const refPos=((rv-r[0])/(r[1]-r[0])*100).toFixed(1);
 return `<div class="lever"><div class="lever-head"><label for="${key}">${d.label}</label><span class="lever-number"><input id="${key}-number" data-key="${key}" type="number" min="${r[0]}" max="${r[1]}" step="1" value="${v}" aria-label="${d.label}, exact value"><span>${d.unit}</span></span></div><div class="slider-track"><span class="reference-tick" style="--ref:${refPos}%" title="Comparison plan: ${rv}"></span><input id="${key}" data-key="${key}" type="range" min="${r[0]}" max="${r[1]}" step="1" value="${v}" aria-label="${d.label}" aria-describedby="${key}-note"></div><div class="lever-note" id="${key}-note"><span>${d.today?`${d.today} today · `:''}${d.note}</span><span data-was="${key}">Was ${rv}</span></div></div>`;}
function buildControls(){
 $('#role-control').innerHTML=lever(role);
 $('#main-controls').innerHTML=lever('growth')+lever('ot');
 $('#people-controls').innerHTML=lever('raise')+lever('training')+lever('absence');
 $('#pay-controls').innerHTML=lever('employer')+lever('deduction');
 $('#shift-evening').innerHTML=lever('evening');$('#shift-night').innerHTML=lever('night');
 const start=$('#start');start.innerHTML=M.months.map((m,i)=>`<option value="${i+1}">${m}</option>`).join('');start.value=state.start;
 $('#month-labels').innerHTML=M.months.map((m,i)=>`<button data-month="${i}" class="${i===month?'active':''}">${m}</button>`).join('');
 syncControls();
}
function syncControls(){$$('[data-was]').forEach(e=>e.textContent='Was '+reference.state[e.dataset.was]);$$('[data-key]').forEach(el=>{el.value=state[el.dataset.key];if(el.type==='range')pctFill(el);});$('#start').value=state.start;$('#role').value=role;$('#undo').disabled=!history.length;
 $$('.presets button').forEach(b=>{const ex=examples[b.dataset.example];b.classList.toggle('active',Object.keys(M.defaults).every(k=>state[k]===M.normalize({...M.defaults,...ex.state})[k]));});
 $$('[data-stress]').forEach(b=>{const on=+b.dataset.stress===state.stress;b.classList.toggle('active',on);b.setAttribute('aria-pressed',on);});
 $$('.reference-tick').forEach(t=>{const key=t.nextElementSibling.dataset.key,r=M.ranges[key];t.style.setProperty('--ref',((reference.state[key]-r[0])/(r[1]-r[0])*100).toFixed(1)+'%');t.title=`Comparison plan: ${reference.state[key]}`;});
}

/* ---------- hero stage ---------- */
let heroFrame=0,heroLast=null,heroMetric=null;
function setHero(value,format){cancelAnimationFrame(heroFrame);const from=heroMetric===metric&&heroLast!==null?heroLast:value;heroMetric=metric;heroLast=value;if(!motion||from===value){$('#hero-value').textContent=format(value);return;}const at=performance.now();function tick(now){const t=Math.min(1,(now-at)/350);$('#hero-value').textContent=format(from+(value-from)*(1-Math.pow(1-t,3)));if(t<1)heroFrame=requestAnimationFrame(tick);}heroFrame=requestAnimationFrame(tick);}
function renderHero(){const m=metrics[metric],a=m.total(plan),b=m.total(ref),d=a-b,good=m.goodUp?d>=0:d<=0,unit=metric==='coverage'?'pp':'money';
 $('#metric-title').textContent=m.title;setHero(a,m.fmt);
 const pill=$('#hero-delta');pill.textContent=`${signed(d,unit)} vs ${reference.name.toLowerCase()}`;pill.className='delta-pill'+(Math.abs(d)>(unit==='money'?.5:.05)&&!good?' bad':'');
 $('#hero-before').innerHTML=`${esc(reference.name)} <b>${m.fmt(b)}</b> → your plan <b>${m.fmt(a)}</b>. ${metric==='profit'?`Margin ${pct(plan.margin)} on ${money(plan.revenue)} revenue.`:metric==='people'?`${plan.headcount} people on payroll by December.`:`${money(plan.unserved*150)} of demand goes unserved this year.`}`;
 $$('.metric-tabs button').forEach(t=>{const on=t.dataset.metric===metric;t.classList.toggle('active',on);t.setAttribute('aria-pressed',on);});
 $('#chart-unit').textContent=diffMode?m.unit.replace('MONTHLY','DIFFERENCE IN MONTHLY').replace('· %','· PP'):m.unit;$('#plan-key').textContent=diffMode?'Difference from comparison':'Your plan';$('#baseline-key').textContent=diffMode?'Zero difference':reference.name;$('#range-key').hidden=diffMode||metric==='coverage';
 $('#scenario-label').textContent=sceneName;
 $('#view-mode').setAttribute('aria-pressed',diffMode);$('#view-mode').textContent=diffMode?'Show full picture':'Show only the difference';
 $('#motion').setAttribute('aria-pressed',!motion);$('#motion').textContent=motion?'Motion on':'Motion off';document.body.classList.toggle('motion-off',!motion);
 drawHorizon();
 const r=plan.rows[month],rr=ref.rows[month];
 $('#month-callout').innerHTML=`<b>${r.name}</b> · ${diffMode?signed(m.row(r)-m.row(rr),unit):m.fmt(m.row(r))}<br>${r.headcount} people · ${pct(r.coverage)} served${r.hiring?'<br>Recruiting costs land this month':month+1<state.start&&Object.keys(levers).slice(0,4).some(k=>state[k])?'<br>New hires not yet arrived':''}`;
 $('#month-stamp').textContent=r.name.toUpperCase();$('#month').value=month;$$('#month-labels button').forEach(b=>b.classList.toggle('active',+b.dataset.month===month));
 const worse=(v,up)=>up?v<0:v>0;
 $('#stage-metrics').innerHTML=[['PEOPLE ON PAYROLL · '+r.name.toUpperCase(),String(r.headcount),signed(r.headcount-rr.headcount,'n')+' people',false],['WORKFORCE COST · '+r.name.toUpperCase(),money(r.people),signed(r.people-rr.people),worse(r.people-rr.people,false)],['DEMAND SERVED · '+r.name.toUpperCase(),pct(r.coverage),signed(r.coverage-rr.coverage,'pp'),worse(r.coverage-rr.coverage,true)]].map(([l,v,d,bad])=>`<div class="stage-metric"><span>${l}</span><div><strong>${v}</strong><small class="${bad?'worse':''}">${d}</small></div></div>`).join('');
}
function drawHorizon(){const c=$('#horizon'),g=canvas2d(c);if(!g)return;const {x:ctx,w,h}=g,m=metrics[metric],p={l:50,r:12,t:14,b:26};
 const planV=plan.rows.map(m.row),refV=ref.rows.map(m.row),loV=band.lo.rows.map(m.row),hiV=band.hi.rows.map(m.row);
 let series=diffMode?planV.map((v,i)=>v-refV[i]):planV,all=diffMode?[...series,0]:[...planV,...refV,...(metric==='coverage'?[]:[...loV,...hiV])];
 let min=Math.min(...all),max=Math.max(...all);if(metric==='coverage'&&!diffMode){min=Math.min(min,60);max=100;}else{const pad=(max-min||1)*.12;min-=pad;max+=pad;if(!diffMode&&min>0&&metric!=='coverage')min=Math.min(min,0);}
 const X=i=>p.l+(w-p.l-p.r)*i/11,Y=v=>p.t+(h-p.t-p.b)*(max-v)/(max-min);
 ctx.font='9px Arial';ctx.textAlign='right';for(let k=0;k<=4;k++){const v=min+(max-min)*k/4,y=Y(v);ctx.strokeStyle='#a9c5b21c';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(w-p.r,y);ctx.stroke();ctx.fillStyle='#9fb9a8';ctx.fillText(metric==='coverage'?Math.round(v)+(diffMode?' pp':'%'):money(v),p.l-7,y+3);}
 if(diffMode){const y0=Y(0);ctx.strokeStyle='#86a69e';ctx.setLineDash([3,4]);ctx.beginPath();ctx.moveTo(p.l,y0);ctx.lineTo(w-p.r,y0);ctx.stroke();ctx.setLineDash([]);const bw=Math.max(8,(w-p.l-p.r)/11*.42);series.forEach((v,i)=>{const good=m.goodUp?v>=0:v<=0;ctx.fillStyle=Math.abs(v)<1e-6?'#86a69e':good?'#d2ec92':'#efb294';ctx.globalAlpha=i===month?1:.75;const y=Y(v);ctx.beginPath();ctx.roundRect(X(i)-bw/2,Math.min(y,y0),bw,Math.max(2,Math.abs(y-y0)),3);ctx.fill();});ctx.globalAlpha=1;}
 else{
  if(metric!=='coverage'){ctx.beginPath();hiV.forEach((v,i)=>i?ctx.lineTo(X(i),Y(v)):ctx.moveTo(X(i),Y(v)));for(let i=11;i>=0;i--)ctx.lineTo(X(i),Y(loV[i]));ctx.closePath();ctx.fillStyle='#82c2a62b';ctx.fill();}
  const path=vals=>{ctx.beginPath();vals.forEach((v,i)=>i?ctx.lineTo(X(i),Y(v)):ctx.moveTo(X(i),Y(v)));};
  path(planV);ctx.lineTo(X(11),Y(min));ctx.lineTo(X(0),Y(min));ctx.closePath();const grad=ctx.createLinearGradient(0,p.t,0,h-p.b);grad.addColorStop(0,'#d2ec9230');grad.addColorStop(1,'#d2ec9200');ctx.fillStyle=grad;ctx.fill();
  path(refV);ctx.setLineDash([4,5]);ctx.lineWidth=1.6;ctx.strokeStyle='#86a69e';ctx.stroke();ctx.setLineDash([]);
  path(planV);ctx.lineWidth=2.6;ctx.strokeStyle='#d2ec92';ctx.lineJoin='round';ctx.stroke();
  planV.forEach((v,i)=>{ctx.beginPath();ctx.fillStyle=i===month?'#f4ffd6':'#d2ec92';ctx.arc(X(i),Y(v),i===month?5:2.6,0,Math.PI*2);ctx.fill();if(i===month){ctx.strokeStyle='#d2ec9255';ctx.lineWidth=6;ctx.stroke();}});
 }
 ctx.strokeStyle='#d5e9b833';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(X(month),p.t);ctx.lineTo(X(month),h-p.b);ctx.stroke();
 ctx.font='9px Arial';ctx.textAlign='center';ctx.fillStyle='#93ad9c';M.months.forEach((n,i)=>{if(w>430||i%2===0)ctx.fillText(n,X(i),h-8);});
 c.setAttribute('aria-label',`${diffMode?'Monthly differences from '+reference.name:m.title.toLowerCase()+' by month'}. ${plan.rows.map((r,i)=>r.name+': '+(diffMode?signed(m.row(r)-m.row(ref.rows[i]),metric==='coverage'?'pp':'money'):'plan '+m.fmt(m.row(r))+', comparison '+m.fmt(m.row(ref.rows[i])))).join('; ')}. Demand stress band is an assumption range, not a probability.`);
}

/* ---------- caption + impact journey ---------- */
function renderStory(){const s=L.story(state,plan,reference.state,ref,reference.name);$('#story-title').textContent=s.title;$('#story-copy').textContent=s.copy;
 const dec=plan.rows[11],rdec=ref.rows[11],dHeads=dec.headcount-rdec.headcount,added=Math.max(0,dHeads),removed=Math.max(0,-dHeads);
 const dots=[];for(let i=0;i<Math.round((rdec.headcount-removed)/5);i++)dots.push('<i class="person-dot"></i>');for(let i=0;i<Math.round(removed/5);i++)dots.push('<i class="person-dot removed"></i>');for(let i=0;i<Math.round(added/5);i++)dots.push('<i class="person-dot added"></i>');
 $('#people-viz').innerHTML=dots.join('');$('#people-viz').title='Each square represents approximately 5 people.';$('#people-value').textContent=dec.headcount+' people';$('#people-change').textContent=dHeads?`${signed(dHeads,'n')} people by December`:'same team as the comparison';
 $('#people-copy').textContent=dHeads<0?`${removed} fewer planned roles than the comparison. This model keeps the original 240 jobs.`:dHeads>0?`${state.ops+state.specialists+state.leads+state.office} planned hires arrive in ${M.months[state.start-1]}, on full pay, at half capacity for their first month. Recruiting costs ${money(plan.hiring)} once.`:state.raise||state.training?`Same headcount, ${state.raise?`${state.raise}% higher pay`:''}${state.raise&&state.training?' and ':''}${state.training?`${state.training}% more productive time`:''}.`:'Same team. Changes come from hours, shifts or demand, not people.';
 drawRing();$('#ring-value').textContent=pct(plan.coverage);$('#coverage-change').textContent=signed(plan.coverage-ref.coverage,'pp');
 const dCov=plan.coverage-ref.coverage,skill=plan.rows.filter(r=>r.skillRatio<.999).length;
 $('#coverage-copy').textContent=`${signed(dCov,'pp')} vs ${reference.name.toLowerCase()}. ${skill?`In ${skill} month${skill>1?'s':''}, specialists or team leads limit delivery, not operators.`:plan.unserved<.01?'Every modeled hour of demand is served.':`${money(plan.unserved*150)} of demand is left on the table.`}`;
 $('#profit-viz').innerHTML=(()=>{const max=Math.max(...plan.rows.map(r=>Math.abs(r.profit)),...ref.rows.map(r=>Math.abs(r.profit)),1);return plan.rows.map((r,i)=>`<span title="${r.name}: ${money(r.profit)} vs ${money(ref.rows[i].profit)}"><i style="height:${Math.abs(ref.rows[i].profit)/max*100}%;${ref.rows[i].profit<0?'background:#e0a97f':''}"></i><i style="height:${Math.abs(r.profit)/max*100}%;${r.profit<0?'background:#b67859':''}"></i></span>`).join('');})();

 const dP=plan.profit-ref.profit;$('#profit-change').textContent=signed(dP);$('#profit-change').className=dP<-.5?'negative':'';
 $('#profit-copy').textContent=`${money(plan.revenue)} revenue − ${money(plan.people)} workforce − ${money(plan.other)} other costs = ${money(plan.profit)} operating profit. Margin ${pct(plan.margin)}. Paired bars show monthly magnitude; amber denotes a loss.`;
}
function drawRing(){const c=$('#coverage-ring'),g=canvas2d(c);if(!g)return;const {x,w,h}=g,cx=w/2,cy=h/2,r=Math.min(w,h)/2-6;
 x.lineWidth=9;x.lineCap='round';x.strokeStyle='#e6ecdf';x.beginPath();x.arc(cx,cy,r,Math.PI*.75,Math.PI*2.25);x.stroke();
 const refA=Math.PI*.75+Math.PI*1.5*Math.min(1,ref.coverage/100);x.strokeStyle='#c4d3b8';x.lineWidth=3;x.beginPath();x.arc(cx,cy,r,Math.PI*.75,refA);x.stroke();
 x.lineWidth=9;x.strokeStyle=plan.coverage>=95?'#7fa65a':'#e0b57e';x.beginPath();x.arc(cx,cy,r,Math.PI*.75,Math.PI*.75+Math.PI*1.5*Math.min(1,plan.coverage/100));x.stroke();}
function ripple(){if(!motion)return;const j=$('#impact-journey');j.classList.remove('ripple');void j.offsetWidth;j.classList.add('ripple');}

/* ---------- detail workspace ---------- */
function renderDetail(){$$('.detail-tabs button').forEach(b=>{const on=b.dataset.detail===detail;b.classList.toggle('active',on);b.setAttribute('aria-pressed',on);});$('#coverage-detail').hidden=detail!=='coverage';$('#money-detail').hidden=detail!=='money';$('#people-detail').hidden=detail!=='people';$$('.impact-card').forEach(c=>c.classList.toggle('selected',c.dataset.focus===detail));
 if(detail==='coverage')renderShifts();if(detail==='money')renderBridge();if(detail==='people')renderPeople();}
function renderShifts(){const r=plan.rows[month],rr=ref.rows[month];$('#shift-month').textContent=`SHIFT COVERAGE · ${r.name.toUpperCase()} · ${r.heads.ops} OPERATORS`;
 $('#shift-cards').innerHTML=['Day','Evening','Night'].map((n,i)=>{const served=Math.min(100,r.fulfilled[i]/r.demand[i]*100),before=Math.min(100,rr.fulfilled[i]/rr.demand[i]*100),gap=r.demand[i]-r.fulfilled[i];
  return `<article class="shift-tile"><div class="shift-title"><span>${n}</span><span class="shift-icon" aria-hidden="true">${['☀','◐','☾'][i]}</span></div><div class="shift-times">${['06:00–14:00 · base rate','14:00–22:00 · +10% premium','22:00–06:00 · +25% premium'][i]}</div><div class="shift-people">${r.split[i]} <small>OPERATORS</small></div><div class="capacity-track" role="img" aria-label="${n} shift serves ${pct(served)} of demand"><div class="capacity-fill ${served<95?'gap':''}" style="width:${served}%"></div><b class="capacity-before" style="left:${before}%" title="Comparison: ${pct(before)}"></b><span><i>${Math.round(r.fulfilled[i]).toLocaleString()} h served</i><i>${pct(served)}</i></span></div><p class="shift-status ${gap>1?'bad':''}">${gap>1?`${Math.round(gap).toLocaleString()} hours of demand unserved`:'Demand fully covered'}${r.available[i]>r.demand[i]*1.15&&gap<=1?' · spare capacity here':''}</p></article>`;}).join('');}
function renderBridge(){const b=L.bridge(plan,ref),c=$('#bridge'),g=canvas2d(c);
 $('#bridge-legend').innerHTML=b.steps.map(s=>`<div class="bridge-item"><span>${s.label}<br><span class="tiny">${s.note}</span></span><strong class="${s.value<-.5?'negative':s.value>.5?'positive':''}">${signed(s.value)}</strong></div>`).join('');
 if(!g)return;const {x,w,h}=g,p={l:54,r:10,t:18,b:46},items=[{label:esc(reference.name),value:b.start,kind:'total'},...b.steps.map(s=>({label:s.label,value:s.value,kind:'step'})),{label:'Your plan',value:b.end,kind:'total'}];
 let run=0,lo=Math.min(0,b.start,b.end),hi=Math.max(b.start,b.end);items.forEach(it=>{if(it.kind==='step'){run+=it.value;lo=Math.min(lo,run);hi=Math.max(hi,run);}else run=it.value;});
 const pad=(hi-lo||1)*.1;lo-=pad;hi+=pad;const n=items.length,slot=(w-p.l-p.r)/n,bw=Math.min(52,slot*.62),Y=v=>p.t+(h-p.t-p.b)*(hi-v)/(hi-lo);
 x.font='9px Arial';x.textAlign='right';for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4,y=Y(v);x.strokeStyle=css('--line');x.beginPath();x.moveTo(p.l,y);x.lineTo(w-p.r,y);x.stroke();x.fillStyle=css('--sub');x.fillText(money(v),p.l-7,y+3);}
 let level=0;items.forEach((it,i)=>{const cx=p.l+slot*i+slot/2,x0=cx-bw/2;let top,bot,color;if(it.kind==='total'){top=Y(Math.max(0,it.value));bot=Y(Math.min(0,it.value));color='#2f4e3c';level=it.value;}else{const from=level,to=level+it.value;top=Y(Math.max(from,to));bot=Y(Math.min(from,to));color=it.value>=0?'#9dbf77':'#e0a97f';level=to;}
  x.fillStyle=color;x.beginPath();x.roundRect(x0,top,bw,Math.max(2,bot-top),3);x.fill();
  if(i<n-1){x.strokeStyle='#b9c7ad';x.setLineDash([2,3]);x.beginPath();x.moveTo(x0+bw,Y(level));x.lineTo(p.l+slot*(i+1)+slot/2-bw/2,Y(level));x.stroke();x.setLineDash([]);}
  x.fillStyle=css('--ink');x.textAlign='center';x.font='600 9px Arial';x.fillText(it.kind==='total'?money(it.value):signed(it.value),cx,top-6);
  x.fillStyle=css('--sub');x.font='8px Arial';const words=it.label.split(' ');const l1=words.slice(0,Math.ceil(words.length/2)).join(' '),l2=words.slice(Math.ceil(words.length/2)).join(' ');x.fillText(l1,cx,h-p.b+16);if(l2)x.fillText(l2,cx,h-p.b+27);});
 c.setAttribute('aria-label',`Profit bridge from ${reference.name} ${money(b.start)} to your plan ${money(b.end)}: ${b.steps.map(s=>s.label+' '+signed(s.value)).join(', ')}.`);}
function renderPeople(){const dec=plan.rows[11],rdec=ref.rows[11],maxH=Math.max(...M.roles.map(r=>Math.max(dec.heads[r.key],rdec.heads[r.key])))*1.1;
 $('#role-bars').innerHTML=`<h3 style="font-size:11px;font-weight:500;margin:0 0 15px">Who is on the team in December</h3>`+M.roles.map(r=>`<div class="role-row"><div class="role-heading"><span>${r.name}</span><span><strong>${dec.heads[r.key]}</strong> <span class="tiny">${dec.heads[r.key]!==rdec.heads[r.key]?`(${signed(dec.heads[r.key]-rdec.heads[r.key],'n')})`:''} · $${Math.round(r.pay*(1+state.raise/100)).toLocaleString()}/mo</span></span></div><div class="role-track" role="img" aria-label="${r.name}: ${dec.heads[r.key]} people, comparison ${rdec.heads[r.key]}"><i style="width:${dec.heads[r.key]/maxH*100}%"></i><b style="width:${rdec.heads[r.key]/maxH*100}%"></b></div></div>`).join('')+`<p class="tiny">Solid bar: your plan. Faint bar: ${esc(reference.name)}.</p>`;
 const take=plan.takehome/plan.gross*100,ded=plan.withholding/plan.gross*100;
 $('#pay-river').innerHTML=`<h3>Where a year of pay goes</h3><div class="money-strip" role="img" aria-label="Gross pay splits into ${pct(take)} take-home and ${pct(ded)} employee deductions"><span style="flex:${take}">Take-home ${pct(take)}</span><span style="flex:${ded}">${ded>=12?'Deductions':''}</span></div><div class="money-row"><span>Gross pay to employees</span><b>${money(plan.gross)}</b></div><div class="money-row"><span>− Employee deductions (${state.deduction}%)</span><b>${money(plan.withholding)}</b></div><div class="money-row"><span>= What reaches employees</span><b>${money(plan.takehome)}</b></div><div class="employer-box"><div class="money-row"><span>Employer contributions (${state.employer}%), paid on top</span><b>${money(plan.contributions)}</b></div><div class="money-row"><span>Recruiting & development</span><b>${money(plan.hiring+plan.learning)}</b></div><div class="money-row"><span><strong>Total workforce cost to the business</strong></span><b>${money(plan.people)}</b></div></div><p class="tiny">Deductions are shown once, inside gross pay. They never add to business cost.</p>`;}

/* ---------- side panel extras ---------- */
function renderMarginal(){const mg=L.marginal(state,plan);$('#marginal-title').textContent=mg.title;$('#marginal-copy').textContent=mg.copy;$('#try-five').disabled=!mg.possible;}
function renderStress(){$('#stress-outcome').innerHTML=L.stressOutcome(state,plan);}

/* ---------- scenario dock ---------- */
function persist(){try{localStorage.setItem('workforceFutures.scenarios',JSON.stringify(saved));return true;}catch(e){toast('Browser storage is unavailable. Scenarios stay in this tab only.');return false;}}
function renderDock(){const sel=$('#reference');sel.innerHTML=`<option value="baseline">Original baseline</option>${pinned?'<option value="pinned">Pinned plan</option>':''}${saved.map((s,i)=>`<option value="${i}">${esc(s.name)}</option>`).join('')}`;sel.value=reference.name==='Original baseline'?'baseline':reference.name==='Pinned plan'?'pinned':String(saved.findIndex(s=>s.name===reference.name));if(sel.selectedIndex<0)sel.value='baseline';
 const rows=[{name:reference.name,state:reference.state,tag:'comparison'},{name:sceneName,state,tag:'current'},...saved.map((s,i)=>({...s,idx:i}))];
 $('#scenario-table').innerHTML=`<table><thead><tr><th>Scenario</th><th>People · Dec</th><th>Workforce cost</th><th>Demand served</th><th>Operating profit</th><th>vs comparison</th><th></th></tr></thead><tbody>${rows.map(r=>{const a=M.compute(r.state),d=a.profit-ref.profit;return `<tr class="${r.tag==='current'?'current-row':''}"><td>${esc(r.name)}${r.tag==='comparison'?' <span class="tiny">· comparison</span>':r.tag==='current'?' <span class="tiny">· on canvas</span>':''}</td><td>${a.headcount}</td><td>${money(a.people)}</td><td>${pct(a.coverage)}</td><td><strong>${money(a.profit)}</strong></td><td class="${d<-.5?'negative':d>.5?'positive':''}">${r.tag==='comparison'?'—':signed(d)}</td><td>${r.idx!==undefined?`<button data-load="${r.idx}">Open</button><button data-compare="${r.idx}">Compare</button><button data-remove="${r.idx}" aria-label="Remove ${esc(r.name)}">×</button>`:''}</td></tr>`;}).join('')}</tbody></table>`;}

/* ---------- dialogs ---------- */
function renderAssumptions(){$('#assumptions-content').innerHTML=`<div class="assumption-grid">${L.assumptions.map(([h,p])=>`<div class="assumption"><h3>${h}</h3><p>${p}</p></div>`).join('')}</div>`;}
function goalUI(){const k=goalKind,t=$('#goal-target');$('#goal-target-label').textContent=k==='growth'?'Growth by December (%)':k==='cost'?'Workforce cost reduction (%)':'Annual demand served (%)';t.min=k==='coverage'?80:0;t.max=k==='coverage'?100:50;t.value=k==='growth'?15:k==='cost'?5:97;$('#goal-constraint').textContent=k==='growth'?'Serve at least 95% of annual demand at a minimum 20% operating margin. Existing jobs and salaries are protected.':k==='cost'?'Keep serving at least 90% of demand. No pay cuts and no headcount reductions.':'Find the lowest-cost way to reach your coverage target. Check the monthly picture too.';}
function findPaths(){const t=$('#goal-target'),target=Number(t.value);if(t.value.trim()===''||!Number.isFinite(target)||target<+t.min||target>+t.max){toast(`Enter a target between ${t.min} and ${t.max}.`);t.focus();return;}paths=M.search(goalKind,target);
 const names={hire:'Build the team',develop:'Develop the team',balanced:'Blend the two'},tag={hire:'HIRING FIRST',develop:'DEVELOPMENT FIRST',balanced:'MOST FLEXIBLE'},desc={hire:'Add capacity by hiring. No productivity assumption.',develop:'Keep operator headcount. Improve productivity and adjust support roles.',balanced:'Mix hiring, support skills and productivity where each helps most.'};
 $('#goal-options').innerHTML=paths.map((p,i)=>`<article class="path-option"><span class="eyebrow">PATH ${i+1} · ${tag[p.lane]}</span><h3>${names[p.lane]}</h3><span class="path-status ${p.meets?'':'bad'}">${p.meets?'✓ Reaches your target':'! Closest we found, target not reached'}</span><div><div class="path-number">${money(p.result.profit)}</div><span class="tiny">operating profit a year</span></div><p>${desc[p.lane]}</p><div class="path-spec"><span>Extra operators</span><b>+${p.state.ops}</b></div><div class="path-spec"><span>Specialists / leads</span><b>+${p.state.specialists} / +${p.state.leads}</b></div><div class="path-spec"><span>Productivity gain</span><b>+${p.state.training}%</b></div><div class="path-spec"><span>Overtime per operator</span><b>${p.state.ot} h</b></div><div class="path-spec"><span>Demand served</span><b>${pct(p.result.coverage)}</b></div><div class="path-spec"><span>Workforce cost</span><b>${money(p.result.people)}</b></div><button data-path="${i}" class="${i===2?'button-dark':''}">Preview on my canvas →</button></article>`).join('');}

/* ---------- master render ---------- */
function render(animate){recompute();renderHero();renderStory();renderDetail();renderMarginal();renderStress();renderDock();if(animate)ripple();}

/* ---------- events ---------- */
document.addEventListener('input',e=>{if(e.target.id==='month'){stopPlay();month=+e.target.value;render(false);return;}if(e.target.id==='goal-target'){paths=[];$('#goal-options').innerHTML='<div class="goal-empty"><p>Target changed. Find my options to recalculate.</p></div>';return;}const k=e.target.dataset.key;if(!k)return;const v=e.target.value;if(v===''||!Number.isFinite(+v))return;const next=M.normalize({...state,[k]:+v});if(next[k]===state[k])return;if(e.target.dataset.rec!=='1'){pushHistory();e.target.dataset.rec='1';}state=next;sceneName='Your working plan';$$(`[data-key="${k}"]`).forEach(el=>{if(el!==e.target)el.value=state[k];if(el.type==='range')pctFill(el);});syncControls();render(false);});
document.addEventListener('change',e=>{const t=e.target;if(t.dataset.key){t.dataset.rec='';syncControls();render(true);return;}
 if(t.id==='role'){role=t.value;$('#role-control').innerHTML=lever(role);syncControls();return;}
 if(t.id==='start'){commit({...state,start:+t.value});return;}
 if(t.id==='month'){month=+t.value;render(false);return;}
 if(t.id==='reference'){const v=t.value;if(v==='baseline')reference={name:'Original baseline',state:{...M.defaults}};else if(v==='pinned'&&pinned)reference={name:'Pinned plan',state:{...pinned}};else if(v!=='pinned'&&saved[+v])reference={name:saved[+v].name,state:{...saved[+v].state}};buildControls();render(true);toast(`Now comparing against “${reference.name}”.`);return;}
 if(t.id==='goal-kind'){goalKind=t.value;goalUI();$('#goal-options').innerHTML='<div class="goal-empty"><span>✧</span><h3>Goal changed.</h3><p>Press “Find my options” to search again.</p></div>';}
});
document.addEventListener('focusin',e=>{if(e.target.dataset.key)e.target.dataset.rec='';});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopPlay();});
document.addEventListener('pointerdown',e=>{if(e.target.type==='range')e.target.dataset.rec='';});
document.addEventListener('click',e=>{const el=e.target.closest('button');if(!el)return;const d=el.dataset;
 if(d.month!==undefined){stopPlay();month=+d.month;render(false);return;}
 if(d.metric){metric=d.metric;render(false);return;}
 if(d.example){const ex=examples[d.example];commit({...M.defaults,...ex.state},`${ex.name} · example plan`);toast('Example loaded. Change any lever to make it yours.');return;}
 if(d.stress!==undefined){commit({...state,stress:+d.stress});return;}
 if(d.detail){detail=d.detail;renderDetail();return;}
 if(d.focus){detail=d.focus;renderDetail();$('#detail-workspace').scrollIntoView({behavior:motion?'smooth':'instant',block:'start'});return;}
 if(d.load!==undefined){commit({...saved[+d.load].state},saved[+d.load].name);toast(`“${saved[+d.load].name}” is on the canvas.`);return;}
 if(d.compare!==undefined){reference={name:saved[+d.compare].name,state:{...saved[+d.compare].state}};buildControls();render(true);toast(`Now comparing against “${reference.name}”.`);return;}
 if(d.remove!==undefined){const item=saved[+d.remove];saved=readSaved();const idx=saved.findIndex(s=>s.name===item.name&&JSON.stringify(s.state)===JSON.stringify(item.state));if(idx<0){render(false);return;}const [s]=saved.splice(idx,1);if(reference.name===s.name)reference={name:'Original baseline',state:{...M.defaults}};persist();buildControls();render(false);return;}
 if(d.path!==undefined){const p=paths[+d.path];if(!p)return;commit({...p.state},['Build the team','Develop the team','Blend the two'][+d.path]+' · suggested path');$('#goal-dialog').close();window.scrollTo({top:0,behavior:motion?'smooth':'instant'});toast(p.meets?'This path reaches your goal. Now make it yours.':'Closest path found. Your target was not reached.');return;}
 if(d.close!==undefined){el.closest('dialog').close();return;}
 switch(el.id){
  case'undo':if(history.length){const prev=history.pop();state=prev.state;sceneName=prev.name;syncControls();render(true);}return;
  case'reset':stopPlay();commit({...M.defaults},'Original baseline');toast('Back to the original baseline.');return;
  case'save-plan':$('#scenario-name').value='';$('#save-feedback').textContent='You can return to it and compare the results.';$('#save-dialog').showModal();return;
  case'confirm-save':{saved=readSaved();const name=$('#scenario-name').value.trim();if(!name){$('#save-feedback').textContent='Give it a name first.';$('#scenario-name').focus();return;}if(saved.length>=5){$('#save-feedback').textContent='Five scenarios saved. Remove one in the comparison table first.';return;}saved.push({name,state:{...state}});sceneName=name;const ok=persist();$('#save-dialog').close();render(false);if(ok)toast(`“${name}” saved on this browser.`);return;}
  case'open-goals':stopPlay();$('#goal-dialog').showModal();return;
  case'find-paths':findPaths();return;
  case'open-assumptions':renderAssumptions();$('#assumptions-dialog').showModal();return;
  case'try-five':{const mg=L.marginal(state,plan);if(mg.possible)commit(mg.state);return;}
  case'balance':commit({...state,evening:30,night:14});toast('Shift shares matched to demand: day 56%, evening 30%, night 14%.');return;
  case'motion':motion=!motion;if(!motion)stopPlay();render(false);return;
  case'view-mode':diffMode=!diffMode;render(false);return;
  case'pin-reference':pinned={...state};reference={name:'Pinned plan',state:{...pinned}};buildControls();render(true);toast('This plan is now the comparison. Every number is measured against it.');return;
  case'play':if(playing){stopPlay();return;}if(month===11)month=0;render(false);el.setAttribute('aria-pressed','true');el.setAttribute('aria-label','Pause year playback');el.textContent='❙❙';playing=setInterval(()=>{if(month>=11){stopPlay();return;}month++;render(false);},1100);return;
  case'export':exportBrief();return;
 }
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')$$('dialog[open]').forEach(dlg=>dlg.close());});
$$('dialog').forEach(dlg=>dlg.addEventListener('click',e=>{if(e.target===dlg)dlg.close();}));
window.addEventListener('storage',e=>{if(e.key==='workforceFutures.scenarios'){saved=readSaved();if(reference.name!=='Original baseline'&&reference.name!=='Pinned plan'&&!saved.some(s=>s.name===reference.name&&JSON.stringify(s.state)===JSON.stringify(reference.state))){pinned={...reference.state};reference.name='Pinned plan';}syncControls();render(false);}});
window.addEventListener('resize',()=>{drawHorizon();drawRing();if(detail==='money')renderBridge();});

/* ---------- export ---------- */
function exportBrief(){const b=L.bridge(plan,ref),s=L.story(state,plan,reference.state,ref,reference.name),ch=L.changes(state,reference.state);
 const html=`<!doctype html><html lang="en"><meta charset="utf-8"><title>Workforce decision brief</title><style>body{font:15px/1.8 Arial;color:#253c31;max-width:860px;margin:50px auto;padding:24px}h1{font:40px Georgia}h2{font:24px Georgia;margin-top:40px}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:10px;text-align:left}p,li{color:#5b6c61}</style><h1>${esc(sceneName)}</h1><p>Payobook · The Living Plan · Fictional USD demonstration · ${new Date().toLocaleDateString()}<br>Compared against: ${esc(reference.name)}</p><h2>In one sentence</h2><p><strong>${esc(s.title)}</strong> ${esc(s.copy)}</p><h2>Annual outcome</h2><table><tr><th>Measure</th><th>${esc(reference.name)}</th><th>This plan</th></tr>${[['Revenue','revenue'],['Workforce cost','people'],['Other operating costs','other'],['Operating profit','profit'],['Gross pay','gross'],['Employee deductions','withholding'],['Take-home pay','takehome']].map(([l,k])=>`<tr><td>${l}</td><td>${money(ref[k])}</td><td>${money(plan[k])}</td></tr>`).join('')}<tr><td>Demand served</td><td>${pct(ref.coverage)}</td><td>${pct(plan.coverage)}</td></tr><tr><td>People in December</td><td>${ref.headcount}</td><td>${plan.headcount}</td></tr></table><h2>Why profit changed</h2><table>${b.steps.map(x=>`<tr><td>${x.label}</td><td>${signed(x.value)}</td></tr>`).join('')}<tr><td><strong>Difference in operating profit</strong></td><td><strong>${signed(b.total)}</strong></td></tr></table><h2>Decisions that differ from the comparison</h2>${ch.length?`<ul>${ch.map(c=>`<li>${levers[c.key].label}: ${c.from} → ${c.to} ${levers[c.key].unit}</li>`).join('')}</ul>`:'<p>None.</p>'}<h2>Full input assumptions</h2><table><tr><th>Input</th><th>Comparison</th><th>Your plan</th></tr>${Object.keys(levers).map(k=>`<tr><td>${levers[k].label}</td><td>${reference.state[k]}</td><td>${state[k]} ${levers[k].unit}</td></tr>`).join('')}</table><h2>Month by month</h2><table><tr><th>Month</th><th>People</th><th>Workforce cost</th><th>Demand served</th><th>Profit</th></tr>${plan.rows.map(r=>`<tr><td>${r.name}</td><td>${r.headcount}</td><td>${money(r.people)}</td><td>${pct(r.coverage)}</td><td>${money(r.profit)}</td></tr>`).join('')}</table><h2>Assumptions</h2>${L.assumptions.map(([h,p])=>`<p><strong>${h}.</strong> ${p}</p>`).join('')}<p>Illustrative decision support only. Nothing in payroll, hiring or schedules is changed by this file.</p></html>`;
 const blob=new Blob([html],{type:'text/html'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='living-plan-decision-brief.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Decision brief exported, with the profit bridge and assumptions.');}

/* ---------- boot ---------- */
buildControls();render(false);
})();
