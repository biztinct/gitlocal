// Copy this builder into a task directory linked to bundled artifact-tool deps.
// Arguments: anonymous source controls, output directory.
import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [sourcePath, outputDir] = process.argv.slice(2);
const source = JSON.parse(await fs.readFile(sourcePath, 'utf8'));
await fs.mkdir(outputDir, {recursive:true});
const col = n => {let s=''; for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s; return s;};
const index = s => [...s].reduce((n,c)=>n*26+c.charCodeAt(0)-64,0)-1;
const headers = [
 'Employee ID','Country','Name','Designation','Date of birth','Join date','Local currency',
 'Monthly basic salary SGD','Employee CPF SGD','Self-help fund','Employee self-help contribution SGD',
 'Employer CPF SGD','SDL employer contribution SGD','Net salary per month SGD','CTC monthly SGD',
 'Gross CTC annual SGD','Net CTC annual SGD','Payroll start date','Payroll end date',
 'Standard working days','LOP days','Arrear days','Active working days','Salary payable SGD',
 'Medical allowance SGD','Other income SGD','Net take-home pay SGD','Bank name','Bank account number',
 'Account holder name','SWIFT code','Work pass or CPF status','Remarks','Prorated gross salary SGD',
 'Deductions applied to pay SGD','Cash earnings SGD','Employer cost SGD','Income tax withheld SGD',
];
const kinds = {A:'identifier',B:'text',C:'text',D:'text',E:'date',F:'date',G:'text',J:'text',
 R:'date',S:'date',T:'quantity',U:'quantity',V:'quantity',W:'quantity',AB:'text',AC:'identifier',
 AD:'text',AE:'identifier',AF:'text',AG:'text'};
function formulas(r) {
 return {
  M:`IF(ISNUMBER(AJ${r}),MIN(MAX(AJ${r}*$C$4,$G$4),$K$4),AJ${r})`,
  N:`H${r}-I${r}-K${r}`, O:`IF(ISNUMBER(M${r}),SUM(H${r},L${r},M${r}),M${r})`,
  P:`IF(ISNUMBER(O${r}),O${r}*12,O${r})`, Q:`N${r}*12`, W:`T${r}-U${r}+V${r}`,
  X:`IF(T${r}>0,ROUND(N${r}/T${r}*W${r},0)+Y${r},"Working days required")`,
  AA:`IF(ISNUMBER(X${r}),X${r}+Z${r},X${r})`,
  AH:`IF(T${r}>0,ROUND(H${r}/T${r}*W${r},0),"Working days required")`,
  AI:`IF(T${r}>0,AH${r}-ROUND(N${r}/T${r}*W${r},0),"Working days required")`,
  AJ:`IF(ISNUMBER(AH${r}),AH${r}+Y${r}+Z${r},AH${r})`,
  AK:`IF(ISNUMBER(AJ${r}),SUM(AJ${r},L${r},M${r}),AJ${r})`, AL:'0',
 };
}
const formulaCols = Object.keys(formulas(13));
const inputCols = headers.map((_,i)=>col(i+1)).filter(c=>!formulaCols.includes(c));
const inputFields = inputCols.map(c=>[c,headers[index(c)],kinds[c]||'money']);
const instructions = {
 A:['Every employee','Employee code registered in Payobook. Keep leading zeros. One row per employee.'],
 B:['Every employee','Singapore.'], C:['Every employee','Employee name for review. Employee ID is the matching key.'],
 D:['Optional','Current designation.'], E:['Optional','Actual birth date; leave blank if not supplied.'],
 F:['Optional','Actual employment start date.'], G:['Every employee','SGD. Salary amounts in this template are Singapore dollars.'],
 H:['Every employee','Full-month contracted basic salary in SGD. The source USD heading was mislabeled; no FX conversion applies.'],
 I:['Every employee','Reviewed full-month employee CPF. Enter 0 for CPF-exempt employees. No automatic age/PR calculation.'],
 J:['Every employee','None, CDAC, SINDA, MBMF or ECF. This label does not calculate the contribution.'],
 K:['Every employee','Reviewed full-month self-help contribution, SGD. Use 0 for a confirmed exemption or opt-out.'],
 L:['Every employee','Actual employer CPF payable for this month, SGD, reviewed separately. Enter 0 if exempt.'],
 R:['Every employee','First date of the selected pay month.'], S:['Every employee','Last date of the selected pay month.'],
 T:['Every employee','Agreed standard working days after public holidays. Greater than 0. August 2026 source uses 20.'],
 U:['Every employee','Unpaid or unpaid inactive working days. Include joiner/leaver days when using this proration method. Enter 0 if none.'],
 V:['Every employee','Arrear days at the current salary. Enter 0 if none. Use other income for separately priced backpay.'],
 Y:['Every employee','Cash medical allowance for this month, SGD. Enter 0 if none. Reimbursements require separate classification.'],
 Z:['Every employee','Other cash income for this month, SGD. Enter 0 if none. Explain nonzero payments in Remarks.'],
 AB:['Optional','Bank name.'], AC:['Optional','Bank account as text. Do not remove hyphens or leading zeros.'],
 AD:['Optional','Account holder name.'], AE:['Optional','Bank SWIFT code as text.'],
 AF:['Every employee','Work pass/residency reference, e.g. EP, LTVP, Citizen or PR. Does not select a CPF rate.'],
 AG:['When applicable','Explain salary changes, arrears, other income and reviewed deductions.'],
};
const defaults={B:'Singapore',D:'Example role',E:null,F:null,G:'SGD',H:3000,I:0,J:'None',K:0,L:0,
 R:46235,S:46265,T:20,U:0,V:0,Y:0,Z:0,AB:'',AC:'0000123456',AD:'Example account holder',
 AE:'EXAMPLE',AF:'EP',AG:''};
const cases = [
 ...source.controls.map((x,i)=>({inputs:{...x.inputs,J:i?'SINDA':'None',AF:i?'EP':'LTVP'},expected:x.expected,label:`Anonymous source control ${i+1}`})),
 {inputs:{H:3000,I:600,K:1,J:'CDAC',L:510,U:2,Y:100,Z:25,AF:'Citizen'},label:'Partial month with reviewed deductions'},
 {inputs:{H:4000,I:0,K:0,L:0,V:1.5,Y:0,Z:250},label:'Arrear days and other income'},
 {inputs:{H:609.5,I:0,K:0,L:0},label:'SDL minimum'},
 {inputs:{H:2000,I:0,K:0,L:0},label:'SDL standard rate'},
 {inputs:{H:4500,I:0,K:0,L:0},label:'SDL maximum threshold'},
 {inputs:{H:4502.03,I:0,K:0,L:0},label:'SDL maximum above threshold'},
];
const round = n => Math.sign(n)*Math.floor(Math.abs(n)+0.5);
function independent(v) {
 const W=v.T-v.U+v.V,N=v.H-v.I-v.K;
 const AH=round(v.H/v.T*W),X=round(N/v.T*W)+v.Y,AA=X+v.Z;
 const AJ=AH+v.Y+v.Z,M=Math.min(Math.max(AJ*.0025,2),11.25);
 const O=v.H+v.L+M;
 return {M,N,O,P:O*12,Q:N*12,W,X,AA,AH,AI:AH-round(N/v.T*W),AJ,AK:AJ+v.L+M,AL:0};
}
const wb=Workbook.create(), payroll=wb.worksheets.add('Payroll'), tax=wb.worksheets.add('Tax Map');
payroll.showGridLines=false; payroll.tabColor='#5747B5';
payroll.getRange('A1:AL20').format={font:{name:'Arial',size:10,color:'#26324A'},rowHeight:24,verticalAlignment:'center'};
payroll.getRange('A2').values=[['Rize Singapore payroll configuration']];
payroll.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#35286F'};
for(const [label,value,labelCell,valueCell,format] of [
 ['SDL rate',.0025,'A4','C4','0.00%'],['SDL minimum SGD',2,'E4','G4','0.00'],['SDL maximum SGD',11.25,'I4','K4','0.00'],
]) {
 payroll.getRange(labelCell).values=[[label]];
 payroll.getRange(valueCell).values=[[value]];
 payroll.getRange(valueCell).setNumberFormat(format);
 payroll.getRange(valueCell).format.font={name:'Arial',size:10,color:'#0000FF'};
}
const notes=[
 'SGD. August 2026 source baseline. Fictional employees are included for import testing.',
 'Proration follows the client: ROUND((basic salary - employee CPF - self-help) / working days * active days, 0).',
 'Medical allowance and other income are added after proration. CPF and self-help amounts require monthly review.',
 'SDL uses actual cash wages. Sum employee SDL, then round the employer remittance down to whole dollars.',
 'Import Payroll, header row 12, Employee ID as primary key. Tax Map is read automatically.',
];
notes.forEach((v,i)=>payroll.getRange(`A${6+i}`).values=[[v]]);
for(const [first,last,label] of [
 ['A','G','Employee details'],['H','L','Payroll inputs'],['M','M','Employer contributions'],
 ['N','Q','Full-month reference'],['R','V','Payroll inputs'],['W','X','Calculation steps'],
 ['Y','Z','Earnings'],['AA','AA','Totals'],['AB','AE','Bank details'],['AF','AG','Employee details'],
 ['AH','AH','Earnings'],['AI','AI','Deductions'],['AJ','AK','Totals'],['AL','AL','Deductions'],
]) {
 payroll.getRange(`${first}11`).values=[[label]];
 if(first!==last)payroll.getRange(`${first}11:${last}11`).merge();
 payroll.getRange(`${first}11:${last}11`).format={fill:'#EDE9F9',font:{name:'Arial',size:10,bold:true,color:'#35286F'},wrapText:true,rowHeight:36};
}
payroll.getRange('A12:AL12').values=[headers];
payroll.getRange('A12:AL12').format={fill:'#35286F',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:65,horizontalAlignment:'center',verticalAlignment:'center'};
wb.names.add('PayrollHeader',payroll.getRange('A12:AL12'));
const values=cases.map((c,i)=>{const v={...defaults,...c.inputs,A:i===0?'000001':`EXAMPLE${i+1}`,C:`Example employee ${i+1}`,AG:c.label};c.fullInputs=v;return headers.map((_,j)=>v[col(j+1)]??null);});
payroll.getRange('A13:AL20').values=values;
for(const c of formulaCols)payroll.getRange(`${c}13:${c}20`).formulas=cases.map((_,i)=>['='+formulas(i+13)[c]]);
headers.forEach((h,i)=>{
 const c=col(i+1),kind=kinds[c]||'money';
 payroll.getRange(`${c}12:${c}20`).format.columnWidth=['C','D','AG','AD'].includes(c)?29:20;
 payroll.getRange(`${c}13:${c}20`).setNumberFormat(kind==='date'?'dd/mm/yyyy':['text','identifier'].includes(kind)?'@':kind==='quantity'?'0.00':'#,##0.00;[Red](#,##0.00);0.00');
 if(inputCols.includes(c))payroll.getRange(`${c}13:${c}20`).format.fill='#FFF6DB';
});
payroll.freezePanes.freezeRows(12);payroll.freezePanes.freezeColumns(3);
tax.showGridLines=false;
const meta=[['Table Code','Country','Version','Effective From','Effective To','Method','Basis','Slot','Field','Payroll Sheet','Cell','Label'],
 ['RIZESGSDL','SG','2026-08','2026-08-01','','parameters','monthly','SDLRATE','parameter','Payroll','C4','SDL rate'],
 ['RIZESGSDL','SG','2026-08','2026-08-01','','parameters','monthly','SDLMIN','parameter','Payroll','G4','SDL minimum SGD'],
 ['RIZESGSDL','SG','2026-08','2026-08-01','','parameters','monthly','SDLMAX','parameter','Payroll','K4','SDL maximum SGD']];
tax.getRange('A1:L4').values=meta;
tax.getRange('A1:L4').format={font:{name:'Arial',size:10,color:'#26324A'},rowHeight:28,columnWidth:20};
tax.getRange('A1:L1').format={fill:'#35286F',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:42};
const sources=[
 'Source: SGP PayrollInput.xlsx, Payroll Input - August26, August 2026.',
 'Source: Zoho Payroll Singapore Configuration and Data Setup Pack, Compensation, Earning Codes, Deduction Codes and Statutory Config.',
 'SDL: https://www.cpf.gov.sg/employer/employer-obligations/skills-development-levy',
 'CPF eligibility and monthly review: https://www.cpf.gov.sg/employer/employer-obligations/who-should-receive-cpf-contributions',
 'CPF rates and ceilings: https://www.cpf.gov.sg/employer/employer-obligations/how-much-cpf-contributions-to-pay',
 'Only SDL is automated in this template. CPF, SHG fund eligibility, opt-outs and contribution amounts must be reviewed separately.',
 'Bonus, leave encashment, tax clearance, benefits, approval matrix, statutory filing and bank export are outside this monthly template.',
];
sources.forEach((v,i)=>{
 payroll.getRange(`AF${3+i}`).values=[[v]];
 payroll.getRange(`AF${3+i}:AL${3+i}`).merge();
 payroll.getRange(`AF${3+i}:AL${3+i}`).format={wrapText:true,rowHeight:35};
});
wb.recalculate();
const comparisons=[];
for(let i=0;i<cases.length;i++){
 const r=i+13, expected=independent(cases[i].fullInputs);
 for(const [c,v]of Object.entries(expected)){
  const actual=payroll.getRange(`${c}${r}`).values[0][0];
  if(typeof actual!=='number'||Math.abs(actual-v)>1e-8)throw new Error(JSON.stringify({case:i,column:c,expected:v,actual}));
  comparisons.push({case:i+1,column:c,expected:v,actual});
 }
 for(const [c,v]of Object.entries(cases[i].expected||{})){
  const actual=payroll.getRange(`${c}${r}`).values[0][0];
  if(typeof v!=='number'||Math.abs(actual-v)>1e-8)throw new Error(`Client control differs: row ${cases[i].source_row||i}, ${c}, ${v}, ${actual}`);
 }
 if(Math.abs(expected.AJ-expected.AI-expected.AA)>1e-8)throw new Error('Net treatment reconciliation failed');
}
// Retain the exact client controls only during reconciliation. Delivered and
// committed examples use fictional salaries and contain no client identity.
for(let i=0;i<source.controls.length;i++) {
 cases[i].fullInputs.H=i===0?25000:21000;
 cases[i].fullInputs.AG=i===0?'Full month, CPF-exempt, no self-help':'Full month, CPF-exempt, reviewed SINDA';
 payroll.getRange(`H${13+i}`).values=[[cases[i].fullInputs.H]];
 payroll.getRange(`AG${13+i}`).values=[[cases[i].fullInputs.AG]];
}
// Change the first row to exercise real recalculation, then restore it.
const original=payroll.getRange('H13').values[0][0];
payroll.getRange('H13').values=[[2000]];
if(payroll.getRange('M13').values[0][0]!==5||payroll.getRange('AA13').values[0][0]!==2000)throw new Error('Changed salary failed to recalculate');
payroll.getRange('H13').values=[[original]];
payroll.getRange('T13').values=[[0]];
if(payroll.getRange('AA13').values[0][0]!== 'Working days required')throw new Error('Missing denominator concealed');
payroll.getRange('T13').values=[[cases[0].fullInputs.T]];
wb.recalculate();
const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:1500});
console.log(scan.ndjson);
await(await SpreadsheetFile.exportXlsx(wb)).save(`${outputDir}/Rize_Singapore_Payroll_Configuration_Aug2026.xlsx`);
for(const [sheetName,range,name]of [['Payroll','A1:L10','configuration'],['Payroll','AH12:AL20','calculations'],['Payroll','AF1:AL10','sources'],['Tax Map','A1:L4','tax-map']]){
 const preview=await wb.render({sheetName,range,scale:1.4,format:'png'});
 await fs.writeFile(`${outputDir}/${name}.png`,new Uint8Array(await preview.arrayBuffer()));
}
const monthly=Workbook.create(), data=monthly.worksheets.add('Payroll'),guide=monthly.worksheets.add('Instructions');
data.showGridLines=false;data.tabColor='#5747B5';
const last=col(inputFields.length),end=301;
data.getRange(`A1:${last}${end}`).format={font:{name:'Arial',size:10,color:'#26324A'},rowHeight:24,verticalAlignment:'center'};
data.getRange(`A1:${last}1`).values=[inputFields.map(f=>f[1])];
data.getRange(`A1:${last}1`).format={fill:'#35286F',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:66,horizontalAlignment:'center',verticalAlignment:'center'};
data.getRange(`A2:${last}${end}`).format.fill='#FFF6DB';
inputFields.forEach(([original,name,kind],i)=>{
 const c=col(i+1),rng=data.getRange(`${c}2:${c}${end}`);
 data.getRange(`${c}1:${c}${end}`).format.columnWidth=['Name','Designation','Remarks','Account holder name'].includes(name)?29:22;
 rng.setNumberFormat(kind==='date'?'dd/mm/yyyy':['text','identifier'].includes(kind)?'@':kind==='quantity'?'0.00':'#,##0.00;[Red](#,##0.00);0.00');
 if(original==='B')rng.dataValidation={rule:{type:'list',values:['Singapore']}};
 if(original==='G')rng.dataValidation={rule:{type:'list',values:['SGD']}};
 if(original==='J')rng.dataValidation={rule:{type:'list',values:['None','CDAC','SINDA','MBMF','ECF']}};
 if(original==='T')rng.dataValidation={rule:{type:'decimal',operator:'greaterThan',formula1:0}};
 if(['H','I','K','L','U','V','Y'].includes(original))rng.dataValidation={rule:{type:'decimal',operator:'greaterThanOrEqual',formula1:0}};
});
data.freezePanes.freezeRows(1);data.freezePanes.freezeColumns(3);
monthly.names.add('PayrollHeader',data.getRange(`A1:${last}1`));
guide.showGridLines=false;
guide.getRange('A1:E52').format={font:{name:'Arial',size:10,color:'#26324A'},rowHeight:27,verticalAlignment:'center'};
guide.getRange('A2').values=[['Rize Singapore monthly payroll inputs']];
guide.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#35286F'};
const guideNotes=[
 'Save one copy per month as Rize_Singapore_Inputs_YYYY-MM.xlsx. Complete Payroll from row 2.',
 'Keep the Payroll sheet name and all headings unchanged. One employee per row. Remove unused rows or add more when needed.',
 'Use registered Employee IDs. Keep IDs and bank accounts as text. All salary and contribution amounts are SGD.',
 'Enter the agreed working-day denominator, LOP days and arrear days. Update both payroll dates to the selected month.',
 'Enter reviewed CPF and self-help amounts. Current EP/LTVP staff are CPF-exempt. Residency and fund labels do not calculate deductions.',
 'Client proration subtracts full-month CPF and self-help before applying the paid-day fraction and rounding to a whole dollar.',
 'Medical allowance and other income are added after proration. Review unusual payments, CPF and fund opt-outs before the run.',
 'In Pay Run, select the Singapore configuration and month, upload this file at Pay data, then review employee matching and results.',
 'The app calculates SDL and outputs. Do not add formulas, statutory tables, annual CTC or take-home-pay columns to this upload file.',
 'Sum all employee SDL amounts and round the employer remittance down to whole dollars. Individual payroll cost retains exact SDL.',
 'This monthly template does not calculate FnF, IR21 withholding, bonus CPF/AW limits or automated citizen/PR contribution rates.',
];
guideNotes.forEach((v,i)=>{guide.getRange(`A${4+i}`).values=[[v]];guide.getRange(`A${4+i}:E${4+i}`).merge();});
guide.getRange('A16:E16').values=[['Column','Input field','Value type','When needed','What to enter']];
guide.getRange('A16:E16').format={fill:'#35286F',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:29};
guide.getRange(`A17:E${16+inputFields.length}`).values=inputFields.map(([c,name,kind],i)=>[col(i+1),name,kind,...instructions[c]]);
guide.getRange(`A17:E${16+inputFields.length}`).format={wrapText:true,rowHeight:43};
for(const [c,width]of [['A',9],['B',40],['C',15],['D',23],['E',113]])guide.getRange(`${c}1:${c}52`).format.columnWidth=width;
guide.freezePanes.freezeRows(16);
const probe=cases.map(c=>inputCols.map(k=>c.fullInputs[k]??null));
data.getRange(`A2:${last}${cases.length+1}`).values=probe;
monthly.recalculate();
await(await SpreadsheetFile.exportXlsx(monthly)).save(`${outputDir}/monthly-probe.xlsx`);
data.getRange(`A2:${last}${cases.length+1}`).clear({applyTo:'contents'});
monthly.recalculate();
console.log((await monthly.inspect({kind:'table',range:'Payroll!A1:F3',include:'values,formulas',tableMaxRows:3,tableMaxCols:6,maxChars:1200})).ndjson);
await(await SpreadsheetFile.exportXlsx(monthly)).save(`${outputDir}/Rize_Singapore_Monthly_Inputs.xlsx`);
for(const [sheetName,range,name]of [['Payroll','A1:H7','monthly'],['Instructions','A1:E23','instructions']]){
 const preview=await monthly.render({sheetName,range,scale:1.4,format:'png'});
 await fs.writeFile(`${outputDir}/${name}.png`,new Uint8Array(await preview.arrayBuffer()));
}
await fs.writeFile(`${outputDir}/verification.json`,JSON.stringify({sourceEmployees:source.controls.length,cases:cases.length,
 comparisons:comparisons.length,sourceControls:source.controls.length*8,inputs:inputCols.length,formulas:formulaCols.length,
 constants:3,components:headers.length+3,changedSalary:true,zeroDenominator:true},null,2));
console.log(JSON.stringify({inputs:inputCols.length,formulas:formulaCols.length,constants:3,cases:cases.length,checks:comparisons.length}));
