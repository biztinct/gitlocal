/* Fictional fixtures only. This preview makes no application API calls. */
window.PayrollDemo = (function () {
  'use strict';
  const common = [
    {key:'standardDays',label:'Standard working days',type:'number',unit:'Days',kind:'time',why:'The working-day calendar for this month.'},
    {key:'paidDays',label:'Paid days',type:'number',unit:'Days',kind:'time',why:'Attendance approved for the selected pay month.'},
    {key:'arrearsDays',label:'Arrears days',type:'number',unit:'Days',kind:'time',why:'Additional paid days attributable to this run.'},
    {key:'overtimeHours',label:'Overtime hours',type:'number',unit:'Hours',kind:'time',why:'A time quantity, rather than an overtime payment.'},
    {key:'bonus',label:'Bonus',type:'number',unit:'Money',kind:'adjustments',why:'A one-off payment for this month.'},
    {key:'reimbursement',label:'Reimbursement',type:'number',unit:'Money',kind:'adjustments',why:'Expenses being paid in the selected month.'},
    {key:'deduction',label:'Other deduction',type:'number',unit:'Money',kind:'adjustments',why:'A deduction supplied for this month only.'},
    {key:'taxAdjustment',label:'Tax adjustment',type:'number',unit:'Money',kind:'adjustments',why:'A signed tax adjustment for this month.'},
    {key:'leaveDays',label:'Paid leave days',type:'number',unit:'Days',kind:'available',suggestion:'time',why:'A quantity of leave to include when your payroll reads it.'},
    {key:'holidayHours',label:'Holiday overtime hours',type:'number',unit:'Hours',kind:'available',suggestion:'time',why:'Approved holiday overtime, in hours.'},
    {key:'department',label:'Department',type:'text',unit:'Text',kind:'available',context:true,why:'Saved employee context. Changes belong in the employee workbook.'},
    {key:'salary',label:'Contracted salary',type:'number',unit:'Money',kind:'available',context:true,why:'Saved contract context. Changes belong in the employee workbook.'}
  ];
  const definitions = {
    VN:{name:'Vietnam',scheme:'Rize Vietnam Payroll v2',currency:'VND',symbol:'₫',flag:'VN',salary:[30000000,38000000,26000000],phone:500000,fixed:800000,names:['Maya Nguyen','Sam Le','Noah Tran'],extra:[{key:'weekendHours',label:'Weekend hours',unit:'Hours',kind:'time',type:'number',why:'Approved weekend time for this run.'},{key:'severance',label:'Severance',unit:'Money',kind:'adjustments',type:'number',why:'A settlement payment. It must not repeat next month.'}]},
    IN:{name:'India',scheme:'Rize India Payroll',currency:'INR',symbol:'₹',flag:'IN',salary:[150000,180000,120000],phone:2500,fixed:5000,names:['Maya Shah','Arjun Rao','Sam Kapoor'],extra:[{key:'tds',label:'Tax Deducted at Source (TDS)',unit:'Money',kind:'adjustments',type:'number',why:'A reviewed deduction for the selected pay month.'},{key:'leaveEncashment',label:'Leave encashment',unit:'Money',kind:'adjustments',type:'number',why:'A payment for this run, not a recurring allowance.'}]},
    ID:{name:'Indonesia',scheme:'Rize Indonesia Payroll',currency:'IDR',symbol:'Rp',flag:'ID',salary:[20000000,24000000,18000000],phone:300000,fixed:500000,names:['Maya Sari','Arjun Pratama','Sam Putra'],extra:[{key:'thr',label:'THR',unit:'Money',kind:'adjustments',type:'number',why:'The THR amount being paid in this period.'},{key:'dailyAllowance',label:'Daily allowance amount',unit:'Money',kind:'adjustments',type:'number',why:'The total allowance paid this month, not a number of days.'}]},
    SG:{name:'Singapore',scheme:'Rize Singapore Payroll',currency:'SGD',symbol:'S$',flag:'SG',salary:[5000,6500,4500],phone:80,fixed:150,names:['Maya Tan','Arjun Rao','Sam Lim'],extra:[{key:'cpfEmployee',label:'Employee CPF',unit:'Money',kind:'adjustments',type:'number',why:'A reviewed monthly input, following the agreed Singapore setup.'},{key:'selfHelp',label:'Self-help fund deduction',unit:'Money',kind:'adjustments',type:'number',why:'A reviewed deduction supplied for this month.'}]}
  };
  const masterFields = [
    {key:'id',label:'Employee ID',type:'text',locked:true},
    {key:'email',label:'Email',type:'text',locked:true},
    {key:'name',label:'Employee name',type:'text'},
    {key:'department',label:'Department',type:'text'},
    {key:'job',label:'Job title',type:'text'},
    {key:'joinDate',label:'Join date',type:'text'},
    {key:'salary',label:'Contracted salary',type:'number'},
    {key:'phone',label:'Fixed phone allowance',type:'number'},
    {key:'fixed',label:'Fixed recurring allowance',type:'number'}
  ];
  function fields(code) {return common.concat(definitions[code].extra).map(function(f){return Object.assign({},f,{unit:f.unit==='Money'?definitions[code].currency:f.unit});});}
  function layout(code) {
    const list=fields(code);
    return {time:list.filter(function(f){return f.kind==='time';}).map(function(f){return f.key;}),adjustments:list.filter(function(f){return f.kind==='adjustments';}).map(function(f){return f.key;}),available:list.filter(function(f){return f.kind==='available';}).map(function(f){return f.key;})};
  }
  function seed(code) {
    const d=definitions[code];
    const records=d.names.map(function(name,i){return {id:'00000'+(i+1),email:['maya','sam','noah'][i]+'@example.com',name:name,department:['Operations','Finance','People'][i],job:['Operations specialist','Finance manager','People partner'][i],joinDate:['2025-03-03','2024-06-10','2025-09-01'][i],salary:d.salary[i],phone:d.phone,fixed:d.fixed};});
    const october={};
    records.forEach(function(r,i){october[r.id]={standardDays:22,paidDays:i===2?21:22,arrearsDays:0,overtimeHours:0};});
    october['000001'].bonus=code==='VN'?1200000:code==='ID'?1000000:code==='IN'?5000:250;
    return {records:records,periods:{'2026-10':october},history:[],version:1};
  }
  function workingDays(period) {
    const parts=period.split('-').map(Number), end=new Date(parts[0],parts[1],0).getDate();let days=0;
    for(let i=1;i<=end;i++){const day=new Date(parts[0],parts[1]-1,i).getDay();if(day!==0&&day!==6)days++;}
    return days;
  }
  return {definitions:definitions,masterFields:masterFields,fields:fields,layout:layout,seed:seed,workingDays:workingDays};
})();
