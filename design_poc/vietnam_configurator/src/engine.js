const STEPS = ['Basics','Components','Rules','Formulas','Test','Create schema'];
const NOTES = {
 UNIFORM:'Annual exemption needs the amount already exempted this tax year. Only the remaining limit is exempt.',
 SEVERANCE_STAT:'Use a separately approved statutory entitlement. Any excess is taxable; do not infer years of service from payroll amounts.',
 OTHER_EXEMPT:'Exemption requires valid supporting evidence. The sample qualification switch demonstrates the taxable fallback.',
 AL_ENCASH_EXEMPT:'Preserve the workbook’s qualifying leave-payment exemption; entitlement and qualification are separate inputs.',
 PRIVATE_INS_ALLOW:'Insurance-base treatment is marked Confirm in the source. This cash allowance is separate from an insurer-paid premium.',
 PREMIUM_INS_ALLOW:'Linked to the dependant health plan. Premium is counted once as non-cash income; the company bears incremental PIT.',
 ADJ_ADD:'Select the original earning. The amount is a signed current-period correction; historical tax/cap recalculation is a later integration.',
 ADJ_DEDUCT:'A negative earning correction, even though it appears in the Earning Codes tab. Never also enter the same adjustment as PRIOR_DED.',
 THIRTEENTH_MONTH:'Proposed formula: monthly contractual salary × eligible annual service days / annual scheduled days, capped at one month. January payout by default.',
 UNION_DUES:'Workbook conflict: Deduction Codes says 0.5%; Statutory Config cites a 1% reference alongside the company-applied 0.5%. Retain 0.5% for demonstration and obtain policy sign-off.',
 PRIOR_DED:'Post-tax recovery by default. Original reference and approved PIT-deductible amount are required when source-dependent treatment is selected.',
 OTHER_DED:'Requires a documented legal or contractual basis. Included in the schema with zero sample amount.',
 PRIVATE_HEALTH_EMP:'Eligibility and cost cells say TBD. Proposed: enrolled employees, company pays 100%, premium supplied per payroll period; PIT policy still needs review.',
 PRIVATE_HEALTH_DEP:'Proposed eligibility: enrolled spouse / children up to 18. Links to PREMIUM_INS_ALLOW so the premium is not counted twice.',
 OTHER_BENEFITS:'The source has no defined policy, eligibility or costs. Configure a named plan or remove this placeholder.',
 VN_SHUI_LOCAL:'Plan references EE_SI / EE_HI / EE_UI and creates employer costs. It does not create another 10.5% deduction.',
 VN_SI_HI_FOREIGN:'Separate foreign-employee eligibility. SI/HI only; never adds unemployment insurance.',
 UNION_MEMBER:'Member dues link to UNION_DUES. Employer union contribution uses a separate employer eligibility flag.'
};
function defaults(){return WORKBOOK_ROWS.map(r=>{
 const c={...r,included:true,category:r.original.C,mode:'input',amount:0,rate:0,proration:'none',cash:'cash',frequency:'monthly',month:1,eligibility:'all',tax:'taxable',insurance:'excluded',taxBearer:'employee',cap:5000000,sign:1,sourceCode:'',pitDeductible:'no',employeeShare:0,link:'',reviewed:false,note:NOTES[r.code]||'',eeSi:8,eeHi:1.5,eeUi:1,erSi:17.5,erHi:3,erUi:1};
 if(r.group==='earnings'){
  c.cash=r.original.D==='Non-cash'?'noncash':'cash'; c.frequency=r.original.H==='Annual'?'annual':r.original.H==='Ad hoc'?'adhoc':r.original.H==='Scheme'?'scheme':'monthly';
  c.proration=r.original.G==='Working-day proration'?'working':'none';
  if(r.original.E.includes('exempt')||r.original.E.includes('Exempt'))c.tax='qualified';
  if(r.code==='BASIC_SALARY'){c.mode='contract';c.insurance='included'}
  if(r.code==='UNIFORM')c.tax='annualcap';
  if(r.code==='SEVERANCE_STAT')c.tax='entitlement';
  if(r.code==='TRANSPORT'||r.code==='PHONE_ALLOW'){c.mode='role';c.eligibility='role'}
  if(r.code==='TRANSPORT_ADD')c.tax='taxable';
  if(r.code==='PRIVATE_INS_ALLOW'){c.insurance='review';c.eligibility='foreign'}
  if(r.code==='PREMIUM_INS_ALLOW'){c.mode='linked';c.link='PRIVATE_HEALTH_DEP';c.taxBearer='employer';c.eligibility='enrolled';c.frequency='monthly'}
  if(r.code.startsWith('ADJ_')){c.tax='inherit';c.insurance='inherit';c.sign=r.code==='ADJ_DEDUCT'?-1:1}
  if(r.code.startsWith('OT_')||r.code==='NIGHT_SHIFT'){c.mode='hourly';c.rate={OT_WEEKDAY:150,OT_WEEKEND:200,OT_HOLIDAY:300,NIGHT_SHIFT:30}[r.code]}
  if(r.code==='THIRTEENTH_MONTH'){c.mode='annual';c.frequency='annual'}
 }else if(r.group==='deductions'){
  c.pitDeductible=r.original.F==='Yes'?'yes':r.original.F.includes('Depends')?'source':'no';
  if(['EE_SI','EE_HI','EE_UI','UNION_DUES'].includes(c.code)){c.mode='percentage';c.rate={EE_SI:8,EE_HI:1.5,EE_UI:1,UNION_DUES:.5}[c.code];c.eligibility=c.code==='EE_UI'?'local':c.code==='UNION_DUES'?'union':'insured'}
  if(c.code==='PIT')c.mode='pit';
 }else{
  c.cash='noncash';c.eligibility=c.code==='VN_SHUI_LOCAL'?'local':c.code==='VN_SI_HI_FOREIGN'?'foreign':c.code==='UNION_MEMBER'?'union':'enrolled';
  c.mode=c.code.startsWith('VN_')||c.code==='UNION_MEMBER'?'plan':'premium';
  c.taxBearer='employer';c.rate=c.code==='UNION_MEMBER'?2:0;
  if(c.code==='PRIVATE_HEALTH_DEP')c.link='PREMIUM_INS_ALLOW';
 }
 return c;
});}
const DEFAULT_RULES={effective:'2026-07-01',siCap:50600000,uiCap:106200000,unionCap:253000,personalRelief:15500000,dependentRelief:6200000,shortThreshold:5000000,shortRate:10,nonresidentRate:20,rounding:'nearest',insuranceBasis:'contract',region:'Region I',transportAG:800000,phoneAG:300000,transportTM:960000,phoneTM:360000,transportCO:1100000,phoneCO:0,reviewed:false};
function sampleProfile(kind='standard'){
 const s={profile:kind,salary:30000000,paidDays:22,standardDays:22,calendarDays:30,paidCalendarDays:30,hoursPerDay:8,dependants:1,nationality:'local',resident:true,contractMonths:12,insured:true,union:true,employerUnion:true,role:'AG',month:9,qualified:true,commitment:false,serviceDays:240,annualDays:260,uniformYtd:4000000,entitlement:5000000,benefitEnrolled:false,values:{UNIFORM:2000000,OT_WEEKEND:8,ADVANCE:1000000,PRIVATE_HEALTH_EMP:1000000,PRIVATE_HEALTH_DEP:1200000},due:{},sourcePitAmount:0};
 if(kind==='joiner')s.paidDays=11;
 if(kind==='foreign'){s.nationality='foreign';s.resident=false;s.union=false;s.dependants=0;s.role='OTHER'}
 if(kind==='benefit'){s.benefitEnrolled=true;s.profile='benefit'}
 if(kind==='short'){s.contractMonths=2;s.insured=false;s.union=false;s.employerUnion=false;s.salary=6000000;s.role='OTHER';s.dependants=0;s.values={};}
 return s;
}
const R=name=>({ref:name}), L=value=>({value}), F=(fn,...args)=>({fn,args:args.map(a=>typeof a==='object'?a:L(a))});
const sum=a=>a.length?F('SUM',...a):L(0);
function formatExpr(e){if('ref'in e)return e.ref;if('value'in e)return typeof e.value==='string'?JSON.stringify(e.value):String(e.value);return `${e.fn}(${e.args.map(formatExpr).join(', ')})`;}
function exprRefs(e){return 'ref'in e?[e.ref]:e.args?[...new Set(e.args.flatMap(exprRefs))]:[];}
function compile(config){
 const cs=config.components.filter(c=>c.included), params=config.rules, nodes=[], inputDefs={};
 const input=(name,value,type='number')=>{inputDefs[name]={code:name,type,default:value};return R(name)};
 const node=(code,name,group,expr,source)=>{nodes.push({code,name,group,expr,formula:'='+formatExpr(expr),dependencies:exprRefs(expr),source:source||'Generated from configuration'});return R(code)};
 const I={salary:input('CONTRACT_SALARY',30000000),paid:input('PAID_DAYS',22),standard:input('STANDARD_DAYS',22),cal:input('CALENDAR_DAYS',30),paidCal:input('PAID_CALENDAR_DAYS',30),hpd:input('HOURS_PER_DAY',8),dependants:input('REGISTERED_DEPENDANTS',1),ytd:input('UNIFORM_YTD_EXEMPT',4000000),entitlement:input('APPROVED_SEVERANCE_ENTITLEMENT',5000000),service:input('ELIGIBLE_ANNUAL_DAYS',240),annual:input('ANNUAL_SCHEDULED_DAYS',260)};
 const param=k=>input('PARAM_'+k.toUpperCase(),params[k]);
 const round=e=>F(params.rounding==='floor'?'FLOOR':'ROUND',e);
 const eligible=c=>F('ELIGIBLE',c.eligibility,c.link&&c.mode==='linked'?c.link:c.code);
 const due=c=>F('DUE',c.code,c.frequency,c.month);
 const amount=c=>{
  let a=c.mode==='fixed'?L(c.amount):c.mode==='contract'?I.salary:c.mode==='hourly'?F('MUL',input(c.code+'_HOURS',0),F('DIV',I.salary,F('MUL',I.standard,I.hpd)),c.rate/100):c.mode==='role'?F('ROLE_RATE',c.code,param(c.code==='PHONE_ALLOW'?'phoneAG':'transportAG'),param(c.code==='PHONE_ALLOW'?'phoneTM':'transportTM'),param(c.code==='PHONE_ALLOW'?'phoneCO':'transportCO')):c.mode==='annual'?F('MUL',I.salary,F('MIN',1,F('DIV',I.service,I.annual))):c.mode==='linked'?F('PLAN_ER_PREMIUM',c.link):input(c.code+'_INPUT',0);
  if(c.proration==='working')a=F('MUL',a,F('DIV',I.paid,I.standard));
  if(c.proration==='calendar')a=F('MUL',a,F('DIV',I.paidCal,I.cal));
  return round(F('IF',F('AND',eligible(c),due(c)),F('MUL',a,c.sign),0));
 };
 const earnings=cs.filter(c=>c.group==='earnings');
 for(const c of earnings)node(c.code,c.name,'earnings',amount(c),c.source);
 const cash=[],noncash=[],taxes=[],employerTaxes=[],insurance=[];
 for(const c of earnings){
  (c.cash==='cash'?cash:noncash).push(R(c.code));
  let t=R(c.code);
  if(c.tax==='exempt')t=L(0);
  if(c.tax==='qualified')t=F('IF',F('QUALIFIED',c.code),0,R(c.code));
  if(c.tax==='annualcap')t=F('MAX',0,F('SUB',R(c.code),F('MAX',0,F('SUB',c.cap,input(c.code+'_YTD_EXEMPT',0)))));
  if(c.tax==='entitlement')t=F('MAX',0,F('SUB',R(c.code),I.entitlement));
  if(c.tax==='inherit')t=F('ORIGINAL_TAXABLE',c.sourceCode,R(c.code));
  taxes.push(node(c.code+'_TAXABLE',c.name+' · taxable','helpers',t,c.source));
  if(c.taxBearer==='employer')employerTaxes.push(R(c.code+'_TAXABLE'));
  if(c.insurance==='included')insurance.push(params.insuranceBasis==='contract'?F('IF',eligible(c),c.mode==='contract'?I.salary:c.mode==='role'?F('ROLE_RATE',c.code,param(c.code==='PHONE_ALLOW'?'phoneAG':'transportAG'),param(c.code==='PHONE_ALLOW'?'phoneTM':'transportTM'),param(c.code==='PHONE_ALLOW'?'phoneCO':'transportCO')):c.mode==='fixed'?c.amount:input(c.code+'_INPUT',0),0):R(c.code));
  if(c.insurance==='inherit')insurance.push(F('ORIGINAL_INSURANCE',c.sourceCode,R(c.code)));
 }
 node('INSURANCE_SALARY','Insurance salary base','helpers',F('MAX',0,sum(insurance)));
 node('SI_HI_BASE','Capped SI / HI base','helpers',F('MIN',R('INSURANCE_SALARY'),param('siCap')));
 node('UI_BASE','Capped UI base','helpers',F('MIN',R('INSURANCE_SALARY'),param('uiCap')));
 const erCosts=[],benefitEE=[];
 for(const c of cs.filter(c=>c.group==='benefits')){
  let expr;
  if(c.mode==='plan'){
   if(c.code==='UNION_MEMBER')expr=F('IF',F('EMPLOYER_UNION_ELIGIBLE'),F('MUL',R('SI_HI_BASE'),c.rate/100),0);
   else expr=F('IF',F('AND',eligible(c),F('ELIGIBLE','insured',c.code)),F('SUM',F('MUL',R('SI_HI_BASE'),(c.erSi+c.erHi)/100),c.code==='VN_SHUI_LOCAL'?F('MUL',R('UI_BASE'),c.erUi/100):0),0);
  }else{
   const total=F('IF',eligible(c),F('PLAN_PREMIUM',c.code),0);
   expr=F('MUL',total,1-c.employeeShare/100);
   benefitEE.push(node(c.code+'_EE',c.name+' · employee cost','deductions',round(F('MUL',total,c.employeeShare/100)),c.source));
   const linked=earnings.find(e=>e.mode==='linked'&&e.link===c.code);
   if(!linked){noncash.push(R(c.code));const t=c.tax==='exempt'?L(0):c.tax==='qualified'?F('IF',F('QUALIFIED',c.code),0,R(c.code)):R(c.code);taxes.push(t);if(c.taxBearer==='employer')employerTaxes.push(t);}
  }
  erCosts.push(node(c.code,c.name+' · employer cost','benefits',round(expr),c.source));
 }
 const ds=cs.filter(c=>c.group==='deductions'&&c.code!=='PIT'),deductions=[...benefitEE],taxDeduct=[];
 for(const c of ds){
  let e=c.mode==='percentage'?F('MUL',R(c.code==='EE_UI'?'UI_BASE':'SI_HI_BASE'),c.rate/100):c.mode==='fixed'?L(c.amount):input(c.code+'_INPUT',0);
  if(c.code==='UNION_DUES')e=F('MIN',e,param('unionCap'));
  e=round(F('IF',['EE_SI','EE_HI','EE_UI'].includes(c.code)?F('AND',eligible(c),F('ELIGIBLE','insured',c.code)):eligible(c),e,0));
  deductions.push(node(c.code,c.name,'deductions',e,c.source));
  if(c.pitDeductible==='yes')taxDeduct.push(R(c.code));
  if(c.pitDeductible==='source')taxDeduct.push(F('MIN',R(c.code),input(c.code+'_APPROVED_PIT_DEDUCTIBLE',0)));
 }
 node('CASH_GROSS','Cash earnings','outputs',sum(cash));
 node('NONCASH_TOTAL','Non-cash benefits','outputs',sum(noncash));
 node('TAXABLE_GROSS','Taxable income before relief','helpers',F('MAX',0,sum(taxes)));
 node('PIT_DEDUCTIBLE','PIT-deductible contributions','helpers',sum(taxDeduct));
 node('PERSONAL_RELIEF','Resident personal relief','helpers',param('personalRelief'));
 node('DEPENDANT_RELIEF','Registered dependant relief','helpers',F('MUL',I.dependants,param('dependentRelief')));
 node('ASSESSABLE','Resident assessable income','helpers',F('MAX',0,F('SUB',R('TAXABLE_GROSS'),R('PIT_DEDUCTIBLE'),R('PERSONAL_RELIEF'),R('DEPENDANT_RELIEF'))));
 node('EMPLOYER_TAXABLE','Income with employer-borne PIT','helpers',F('MAX',0,sum(employerTaxes)));
 const pitIncluded=cs.some(c=>c.code==='PIT'), pitComponent=cs.find(c=>c.code==='PIT');
 node('TAX_GROSS_UP','Employer-borne incremental PIT','outputs',pitIncluded?F('IF',eligible(pitComponent),F('GROSS_UP',R('TAXABLE_GROSS'),R('EMPLOYER_TAXABLE'),R('PIT_DEDUCTIBLE'),R('PERSONAL_RELIEF'),R('DEPENDANT_RELIEF')),0):L(0));
 node('PIT','Personal income tax','outputs',pitIncluded?F('IF',eligible(pitComponent),round(F('TAX',F('ADD',R('TAXABLE_GROSS'),R('TAX_GROSS_UP')),R('PIT_DEDUCTIBLE'),R('PERSONAL_RELIEF'),R('DEPENDANT_RELIEF'))),0):L(0));
 node('DEDUCTIONS','Employee deductions excluding PIT','outputs',sum(deductions));
 node('NET_PAY','Net bank payment','outputs',F('SUB',F('ADD',R('CASH_GROSS'),R('TAX_GROSS_UP')),R('DEDUCTIONS'),R('PIT')));
 // A linked premium is represented by its plan cost, not added to employer cost twice.
 const unlinkedNoncash=earnings.filter(c=>c.cash==='noncash'&&c.mode!=='linked').map(c=>R(c.code));
 node('EMPLOYER_COST','Total employer cost','outputs',F('SUM',R('CASH_GROSS'),sum(erCosts),sum(unlinkedNoncash),R('TAX_GROSS_UP')));
 return {format:'payobook.configuration-poc.v1',productionCompatible:false,name:config.name,country:'VN',currency:'VND',cycle:config.cycle,effectiveFrom:params.effective,parameters:structuredClone(params),components:structuredClone(cs),inputs:Object.values(inputDefs),nodes,removed:config.components.filter(c=>!c.included).map(c=>c.code),issues:issues(config),notes:'Executable prototype expression tree. Production import requires an adapter to create_config and the Formula Studio parser; this is not an activation payload.'};
}
function progressive(x){const bands=[[10000000,.05,0],[30000000,.1,500000],[60000000,.2,3500000],[100000000,.3,9500000],[Infinity,.35,14500000]];const b=bands.find(b=>x<=b[0]);return Math.max(0,x*b[1]-b[2]);}
function evaluateSchema(schema,s){
 const values={},rules=schema.parameters,cs=schema.components,byCode=Object.fromEntries(cs.map(c=>[c.code,c]));
 const mapped={CONTRACT_SALARY:s.salary,PAID_DAYS:s.paidDays,STANDARD_DAYS:s.standardDays,CALENDAR_DAYS:s.calendarDays,PAID_CALENDAR_DAYS:s.paidCalendarDays,HOURS_PER_DAY:s.hoursPerDay,REGISTERED_DEPENDANTS:s.dependants,UNIFORM_YTD_EXEMPT:s.uniformYtd,APPROVED_SEVERANCE_ENTITLEMENT:s.entitlement,ELIGIBLE_ANNUAL_DAYS:s.serviceDays,ANNUAL_SCHEDULED_DAYS:s.annualDays};
 for(const i of schema.inputs){let v=i.default;if(i.code in mapped)v=mapped[i.code];else if(i.code.endsWith('_INPUT'))v=s.values[i.code.slice(0,-6)]||0;else if(i.code.endsWith('_HOURS'))v=s.values[i.code.slice(0,-6)]||0;else if(i.code.endsWith('_APPROVED_PIT_DEDUCTIBLE'))v=s.sourcePitAmount||0;values[i.code]=v;}
 const eligible=(kind,code)=>kind==='all'?true:kind==='local'?s.nationality==='local':kind==='foreign'?s.nationality==='foreign':kind==='insured'?s.insured:kind==='union'?s.union:kind==='role'?['AG','TM','CO'].includes(s.role):kind==='enrolled'?s.benefitEnrolled:false;
 const premium=code=>{const c=byCode[code];return c&&eligible(c.eligibility,code)?(c.amount>0?c.amount:s.values[code]||0):0};
 const tax=(gross,d,p,dep)=>!s.resident?Math.max(0,gross)*rules.nonresidentRate/100:s.contractMonths<3?(gross>=rules.shortThreshold&&!s.commitment?gross*rules.shortRate/100:0):progressive(Math.max(0,gross-d-p-dep));
 const calc=e=>{
  if('ref'in e){if(!(e.ref in values))throw Error('Missing dependency: '+e.ref);return values[e.ref]}
  if('value'in e)return e.value;
  if(e.fn==='IF')return calc(e.args[0])?calc(e.args[1]):calc(e.args[2]);
  const a=e.args.map(calc);
  switch(e.fn){case'SUM':case'ADD':return a.reduce((x,y)=>x+y,0);case'SUB':return a.slice(1).reduce((x,y)=>x-y,a[0]);case'MUL':return a.reduce((x,y)=>x*y,1);case'DIV':if(a[1]<=0)throw Error('A day or hour denominator must be greater than zero.');return a[0]/a[1];case'MIN':return Math.min(...a);case'MAX':return Math.max(...a);case'ROUND':return Math.round(a[0]);case'FLOOR':return Math.floor(a[0]);case'AND':return a.every(Boolean);case'ELIGIBLE':return eligible(...a);case'EMPLOYER_UNION_ELIGIBLE':return s.employerUnion;case'DUE':return a[1]==='annual'?s.month===a[2]:a[1]==='scheme'?!!s.due[a[0]]:true;case'QUALIFIED':return s.qualified;case'ROLE_RATE':return s.role==='AG'?a[1]:s.role==='TM'?a[2]:s.role==='CO'?a[3]:0;case'PLAN_PREMIUM':return premium(a[0]);case'PLAN_ER_PREMIUM':return premium(a[0])*(byCode[a[0]]?.employeeShare!=null?1-byCode[a[0]].employeeShare/100:1);case'ORIGINAL_TAXABLE':return byCode[a[0]]?.tax==='exempt'?0:byCode[a[0]]?.tax==='qualified'&&s.qualified?0:a[1];case'ORIGINAL_INSURANCE':return byCode[a[0]]?.insurance==='included'?a[1]:0;case'TAX':return tax(...a);case'GROSS_UP':{const[gross,born,d,p,dep]=a;let x=0;const base=tax(Math.max(0,gross-born),d,p,dep);for(let n=0;n<200;n++){const next=Math.max(0,tax(gross+x,d,p,dep)-base);if(Math.abs(next-x)<.001)return Math.round(next);x=next}throw Error('Gross-up did not converge.');}default:throw Error('Unknown expression: '+e.fn)}
 };
 for(const n of schema.nodes)values[n.code]=calc(n.expr);
 if(Object.values(values).some(v=>typeof v==='number'&&!Number.isFinite(v)))throw Error('Invalid numeric result.');
 return values;
}
function issues(config){
 const cs=config.components.filter(c=>c.included),out=[];
 const add=(code,title,detail,severity='review')=>out.push({code,title,detail,severity});
 if(!config.rules.reviewed)add('rules','Confirm the effective-dated rule pack','Workbook values are proposed defaults. The union-rate notes conflict; statutory source and policy review are still required.');
 if(config.rules.effective<'2026-07-01')add('rules','Date outside this prototype’s rule pack','This prototype carries the July 2026 workbook pack only. Historical versions require a separate parameter set.','error');
 for(const c of cs){
  if(c.insurance==='review')add(c.code,'Choose the insurance treatment',c.name+' is marked Confirm in the workbook.');
  if((c.tax==='inherit'||c.insurance==='inherit')&&(!c.sourceCode||!cs.some(x=>x.code===c.sourceCode)))add(c.code,'Choose an original component',c.name+' needs an included source earning; no self or adjustment-to-adjustment references.');
  if(c.group==='benefits'&&c.mode==='premium'&&!c.reviewed)add(c.code,'Confirm benefit policy and funding',c.name+': eligibility/cost details were incomplete. The premium input remains explicit.');
  if(c.mode==='linked'&&!cs.some(x=>x.code===c.link))add(c.code,'Restore or replace a removed benefit link',c.name+' refers to '+c.link+'.','error');
  if(c.code==='UNION_DUES'&&!c.reviewed)add(c.code,'Resolve 0.5% / 1% source conflict',NOTES.UNION_DUES);
  if(c.code==='OTHER_DED'&&!c.reviewed)add(c.code,'Document the deduction basis',NOTES.OTHER_DED);
  if(c.code==='PRIOR_DED'&&c.pitDeductible==='source'&&!c.reviewed)add(c.code,'Define adjustment evidence',NOTES.PRIOR_DED);
 }
 if(!cs.some(c=>c.code==='PIT'))add('PIT','PIT component removed','No income tax will be withheld by this draft.','review');
 for(const [plan,links]of [['VN_SHUI_LOCAL',['EE_SI','EE_HI','EE_UI']],['VN_SI_HI_FOREIGN',['EE_SI','EE_HI']],['UNION_MEMBER',['UNION_DUES']]])if(cs.some(c=>c.code===plan))for(const code of links)if(!cs.some(c=>c.code===code))add(plan,'Missing employee contribution',plan+' refers to removed '+code+'. Employer costs remain separate.','error');
 return out;
}
