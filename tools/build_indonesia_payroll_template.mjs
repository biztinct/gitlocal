// Run from a conversation directory linked to the bundled artifact-tool deps.
// Arguments: anonymous analysis JSON, output directory.
import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [sourcePath, outputDir] = process.argv.slice(2);
const source = JSON.parse(await fs.readFile(sourcePath, 'utf8'));
await fs.mkdir(outputDir, {recursive: true});
const wb = Workbook.create();
const sheet = wb.worksheets.add('Payroll');
const map = wb.worksheets.add('Tax Map');
sheet.showGridLines = false;
map.showGridLines = false;
sheet.tabColor = '#5747B5';
const letter = n => { let s=''; for (;n;n=Math.floor((n-1)/26)) s=String.fromCharCode(65+(n-1)%26)+s; return s; };
const colNum = s => [...s].reduce((n,c)=>n*26+c.charCodeAt(0)-64,0);
const metadata = [['Table Code','Country','Version','Effective From','Effective To','Method','Basis','Slot','Field','Payroll Sheet','Cell','Label']];
const refs = {};
function constant(cell, value, label, table, slot, field, method='parameters', basis='monthly') {
  sheet.getRange(cell).values = [[value]];
  sheet.getRange(cell).format.font = {name:'Arial',size:10,color:'#0000FF'};
  sheet.getRange(cell).setNumberFormat(field==='rate' || (method==='parameters' && label.toLowerCase().includes('rate')) ? '0.00%' : '#,##0');
  metadata.push([table,'ID','2026-08','2026-08-01','',method,basis,slot,field,'Payroll',cell,label]);
}
// Reference creation is intentionally simple and kept independent of formatting.
const absolute = cell => cell.replace(/^([A-Z]+)(\d+)$/, '$$$1$$$2');
const parameters = [
  ['JKMRATE',0.003,'Life insurance rate'], ['JKKRATE',0.0024,'Accident insurance rate'],
  ['JHTER',0.037,'JHT employer rate'],['JHTEE',0.02,'JHT employee rate'],
  ['JPER',0.02,'JP employer rate'],['JPEE',0.01,'JP employee rate'],
  ['TKMIN',1000000,'BPJS TK minimum'],['JPCAP',11086300,'JP wage ceiling'],
  ['HIMIN',5729876,'Health wage minimum'],['HICAP',12000000,'Health wage ceiling'],
  ['HIER',0.04,'Health employer rate'],['HIEE',0.01,'Health employee rate'],
  ['PREMMONTHS',12,'Annual premium months'],['JOBRATE',0.05,'Job expense rate'],
  ['JOBCAP',500000,'Job expense monthly cap'],['PKPROUND',1000,'Annual PKP rounding'],
  ['PTKPS0',54000000,'PTKP S/0'],['PTKPS1',58500000,'PTKP S/1'],
  ['PTKPS2',63000000,'PTKP S/2'],['PTKPS3',67500000,'PTKP S/3'],
  ['PTKPM0',58500000,'PTKP M/0'],['PTKPM1',63000000,'PTKP M/1'],
  ['PTKPM2',67500000,'PTKP M/2'],['PTKPM3',72000000,'PTKP M/3'],
];
sheet.getRange('A2').values=[['Indonesia payroll formula template']];
sheet.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#241F52'};
sheet.getRange('A3').values=[['August 2026 (IDR). Blue numbers are statutory constants. Enter payroll inputs in the shaded columns.']];
parameters.forEach(([key,value,label],i)=>{
  const r=4+i%3,c=1+Math.floor(i/3)*4;
  sheet.getRange(`${letter(c)}${r}`).values=[[label]];
  const cell=`${letter(c+2)}${r}`;
  constant(cell,value,label,'IDPARAMS',key,'parameter'); refs[key]=absolute(cell);
  sheet.getRange(`${letter(c)}${r}:${letter(c+1)}${r}`).merge();
});
const bands = {};
for (let cat=0;cat<3;cat++) {
  const key='ABC'[cat]; bands[key]=[];
  const base=1+cat*10;
  sheet.getRange(`${letter(base)}8`).values=[[`TER ${key}: whole monthly income`]];
  sheet.getRange(`${letter(base)}8:${letter(base+8)}8`).merge();
  for (let block=0;block<3;block++) {
    const c=base+block*3;
    sheet.getRange(`${letter(c)}9:${letter(c+2)}9`).values=[['Band','Up to','Rate']];
  }
  source.bands[key].forEach(([cap,rate],i)=>{
    const r=10+i%15,c=base+Math.floor(i/15)*3;
    sheet.getRange(`${letter(c)}${r}`).values=[[i+1]];
    const capCell=`${letter(c+1)}${r}`,rateCell=`${letter(c+2)}${r}`;
    constant(capCell,cap,`TER ${key} band ${i+1} upper`,'IDTER'+key,i+1,'upper','whole_income');
    constant(rateCell,rate,`TER ${key} band ${i+1} rate`,'IDTER'+key,i+1,'rate','whole_income');
    bands[key].push({cap,rate,capRef:absolute(capCell),rateRef:absolute(rateCell)});
  });
}
const annual=[], severance=[];
for (const [name,code,c,start,values,dest] of [
  ['Annual PPh21','IDANNUAL',32,10,[[60000000,.05],[250000000,.15],[500000000,.25],[5000000000,.30],[0,.35]],annual],
  ['Qualifying severance','IDSEVERANCE',36,10,[[50000000,0],[100000000,.05],[500000000,.15],[0,.25]],severance],
]) {
  sheet.getRange(`${letter(c)}8`).values=[[name]];
  sheet.getRange(`${letter(c)}8:${letter(c+2)}8`).merge();
  sheet.getRange(`${letter(c)}9:${letter(c+2)}9`).values=[['Band','Up to','Rate']];
  values.forEach(([cap,rate],i)=>{
    const r=start+i;
    sheet.getRange(`${letter(c)}${r}`).values=[[i+1]];
    const capCell=`${letter(c+1)}${r}`,rateCell=`${letter(c+2)}${r}`;
    constant(capCell,cap,`${name} band ${i+1} upper`,code,i+1,'upper','progressive','annual');
    constant(rateCell,rate,`${name} band ${i+1} rate`,code,i+1,'rate','progressive','annual');
    dest.push({capRef:absolute(capCell),rateRef:absolute(rateCell)});
  });
}
const notes=[
  'Source: client August 2026 workbook: BPJS TK, BPJS Health, Premi Insurance, Calculation and TER A B C.',
  'TER and BPJS rates are the client August snapshot. Effective date identifies this snapshot, not the original regulation date.',
  'Allowance mode: 0 = none; 1 = tax on regular insurance premium; 2 = full monthly tax gross-up. BPJS reimbursement is a separate flag.',
  'Paid days and period days are payroll inputs. Salary adjustment covers backpay. Annual premium / 12 calculates monthly insurance.',
  'Final period: supply prior YTD gross, deductible JHT + JP, eligible job-expense months and tax already withheld. Refunds remain signed.',
  'Final-period full net contracts require a separate annual gross-up review. The template exposes that case as an unavailable calculation.',
  'Severance calculation is for qualifying PP 68/2009 payments in the first two years. Include prior qualifying payments and tax withheld.',
  'Import Payroll only; Tax Map is read automatically. Publish the imported editions, then activate the reviewed payroll configuration.',
  'https://www.pajak.go.id/id/peraturan/harmonisasi-peraturan-perpajakan',
  'https://pajak.go.id/id/peraturan/petunjuk-pelaksanaan-pemotongan-pajak-atas-penghasilan-sehubungan-dengan-pekerjaan-jasa-1',
  'https://www.pajak.go.id/id/tarif-pajak-penghasilan-pasal-21-atas-penghasilan-berupa-uang-pesangon-uang-manfaat-pensiun',
];
sheet.getRange('A25').values=[['Upper bound 0 means unlimited. Each numbered band keeps its own database mapping.']];
notes.forEach((text,i)=>sheet.getRange(`AF${16+i}`).values=[[text]]);
const headers = [
 'Department','Cost Centre','No.','Employee ID','Name','Job Title','Join Date','Resign Date','Employee Status','S/M','L/E',
 'Basic Salary','Tax allowance regular','BPJS allowance','Leave balance paid','Bonus','THR','Incentive','Daily allowance',
 'Life insurance income','Accident insurance income','BPJS health company income','Insurance premium income','Tax allowance irregular',
 'Qualifying severance paid','Total income','Old age company','Pension company','Life insurance deduction','Accident insurance deduction',
 'BPJS health company deduction','Insurance premium deduction','Old age employee','Pension employee','BPJS health employee',
 'THR already paid','Incentive already paid','Other deduction','Tax adjustment','Payable tax','Severance tax','Total deduction','Take home pay',
 'Remarks','Contract basic salary','Paid days','Period days','Salary adjustment','Annual insurance premium','BPJS TK covered',
 'BPJS health covered','Employer reimburses employee BPJS','Tax allowance mode','Final tax period',
 'Prior YTD taxable gross','Prior YTD deductible JHT and JP','Job expense eligible months','Prior YTD PPh21 withheld',
 'PTKP annual','Annual taxable PKP','Annual PPh21 liability','BPJS TK wage base','BPJS JP wage base','BPJS health wage base',
 'Regular gross before premium and tax allowance','Regular tax before premium','Gross-up target net','Grossed-up gross',
 'Gross-up allowance candidate','Monthly TER rate','Gross-up residual','Employer cost','Leave balance days',
 'Prior qualifying severance paid','Prior severance tax withheld'
];
const last=letter(headers.length), headerRow=29, dataStart=30;
sheet.getRange(`A${headerRow}:${last}${headerRow}`).values=[headers];
wb.names.add('PayrollHeader',sheet.getRange(`A${headerRow}:${last}${headerRow}`));
for(const [first,end,label] of [['A','K','Employee details'],['L','Y','Earnings'],['AA','AB','Employer contributions'],['AC','AP','Deductions'],['AS','BF','Payroll inputs'],['BG','BT','Calculation steps'],['BU','BW','Payment inputs']]) {
 sheet.getRange(`${first}28`).values=[[label]];
 sheet.getRange(`${first}28:${end}28`).merge();
 sheet.getRange(`${first}28:${end}28`).format={fill:'#EDE9F9',font:{name:'Arial',size:10,bold:true,color:'#35286F'}};
}
sheet.getRange(`A${headerRow}:${last}${headerRow}`).format={fill:'#35286F',font:{name:'Arial',size:10,color:'#FFFFFF',bold:true},wrapText:true,rowHeight:58,verticalAlignment:'center',horizontalAlignment:'center'};
const missing='"Missing PTKP status"';
function category(r, exprs) {
  return `IF(OR(J${r}="S/0",J${r}="S/1",J${r}="M/0"),${exprs.A},IF(OR(J${r}="S/2",J${r}="S/3",J${r}="M/1",J${r}="M/2"),${exprs.B},IF(J${r}="M/3",${exprs.C},${missing})))`;
}
function rateLookup(gross,key) {
  let result=bands[key].at(-1).rateRef;
  for(let i=bands[key].length-2;i>=0;i--) result=`IF(ROUND(${gross},0)<=${bands[key][i].capRef},${bands[key][i].rateRef},${result})`;
  return result;
}
function inverse(net,key) {
  let result=`${net}/(1-${bands[key].at(-1).rateRef})`;
  for(let i=bands[key].length-2;i>=0;i--) result=`IF(${net}<=${bands[key][i].capRef}*(1-${bands[key][i].rateRef}),${net}/(1-${bands[key][i].rateRef}),${result})`;
  return result;
}
function progressive(value,rows) {
  return rows.map((b,i)=>`MAX(0,${i===rows.length-1 ? value : `MIN(${value},${b.capRef})`}-${i ? rows[i-1].capRef : '0'})*${b.rateRef}`).join('+');
}
function formulas(r) {
 const fp={}; const rates=g=>category(r,Object.fromEntries('ABC'.split('').map(k=>[k,rateLookup(g,k)])));
 fp.L=`ROUND(AS${r}*AT${r}/AU${r},0)+AV${r}`;
 fp.BJ=`IF(AX${r}=1,IF(L${r}=0,0,MAX(L${r},${refs.TKMIN})),0)`;
 fp.BK=`IF(AX${r}=1,MIN(MAX(L${r},${refs.TKMIN}),${refs.JPCAP}),0)`;
 fp.BL=`IF(AY${r}=1,MIN(MAX(L${r},${refs.HIMIN}),${refs.HICAP}),0)`;
 for(const [c,base,rate] of [['T','BJ','JKMRATE'],['U','BJ','JKKRATE'],['AA','BJ','JHTER'],['AG','BJ','JHTEE'],['AB','BK','JPER'],['AH','BK','JPEE'],['V','BL','HIER'],['AI','BL','HIEE']]) fp[c]=`ROUND(${base}${r}*${refs[rate]},0)`;
 fp.W=`ROUND(AW${r}/${refs.PREMMONTHS},0)`;
 fp.N=`IF(AZ${r}=1,SUM(AG${r}:AI${r}),0)`;
 fp.O=`ROUND(AS${r}*BU${r}/AU${r},0)`;
 fp.BM=`SUM(L${r},N${r},O${r},S${r},T${r}:V${r})`;
 fp.BN=`ROUND(BM${r}*${rates(`BM${r}`)},0)`;
 fp.BO=`IF(BA${r}=2,SUM(L${r},N${r}:W${r},X${r}),BM${r}+W${r}-BN${r})`;
 fp.BP=category(r,Object.fromEntries('ABC'.split('').map(k=>[k,inverse(`BO${r}`,k)])));
 fp.BQ=`ROUND(BP${r}-IF(BA${r}=2,SUM(L${r},N${r}:W${r},X${r}),BM${r}+W${r}),0)`;
 fp.M=`IF(AND(BB${r}=1,BA${r}=2),"Review final-period gross-up",IF(BA${r}=0,0,MAX(0,BQ${r})))`;
 fp.Z=`SUM(L${r}:X${r})`;
 fp.BR=rates(`Z${r}`);
 const pt=Object.fromEntries(parameters.filter(x=>x[0].startsWith('PTKP')).map(([k])=>[k.slice(4,5)+'/'+k.slice(5),refs[k]]));
 fp.BG=Object.entries(pt).reduceRight((rest,[status,value])=>`IF(J${r}="${status}",${value},${rest})`,missing);
 fp.BH=`MAX(0,FLOOR(BC${r}+Z${r}-MIN((BC${r}+Z${r})*${refs.JOBRATE},BE${r}*${refs.JOBCAP})-BD${r}-AG${r}-AH${r}-BG${r},${refs.PKPROUND}))`;
 fp.BI=`ROUND(${progressive(`BH${r}`,annual)},0)`;
 fp.AN=`IF(BB${r}=1,BI${r}-BF${r},ROUND(Z${r}*BR${r},0))`;
 fp.AO=`ROUND(${progressive(`Y${r}+BV${r}`,severance)},0)-BW${r}`;
 for(const [c,other] of [['AC','T'],['AD','U'],['AE','V'],['AF','W']]) fp[c]=`${other}${r}`;
 fp.AP=`SUM(AC${r}:AO${r})`;fp.AQ=`Z${r}+Y${r}-AP${r}`;
 fp.BS=`IF(BA${r}=0,0,M${r}-(ROUND((IF(BA${r}=2,SUM(L${r},N${r}:W${r},X${r}),BM${r}+W${r})+M${r})*${rates(`(IF(BA${r}=2,SUM(L${r},N${r}:W${r},X${r}),BM${r}+W${r})+M${r})`)},0)-IF(BA${r}=2,0,BN${r})))`;
 fp.BT=`Z${r}+Y${r}+AA${r}+AB${r}`;
 return fp;
}
const formulaCols=Object.keys(formulas(dataStart));
function writeRows(records) {
 const matrix=records.map((record,i)=>{
  const values=Array(headers.length).fill(null);
  const defaults={A:'Example',B:'Example',C:i+1,D:`EXAMPLE${String(i+1).padStart(3,'0')}`,E:`Example employee ${i+1}`,F:'',I:'Permanent',J:'S/0',K:'L',
    P:0,Q:0,R:0,S:0,X:0,Y:0,AJ:0,AK:0,AL:0,AM:0,AR:'',AS:8000000,AT:31,AU:31,AV:0,AW:3600000,AX:1,AY:1,AZ:0,BA:1,BB:0,BC:0,BD:0,BE:8,BF:0,BU:0,BV:0,BW:0};
  for(const [c,v] of Object.entries({...defaults,...record.inputs})) values[colNum(c)-1]=v;
  return values;
 });
 sheet.getRange(`A${dataStart}:${last}${dataStart+records.length-1}`).values=matrix;
 for(const c of formulaCols) sheet.getRange(`${c}${dataStart}:${c}${dataStart+records.length-1}`).formulas=records.map((_,i)=>['='+formulas(dataStart+i)[c]]);
}
// Compute all 122 anonymous source controls before replacing them with six
// fictional examples. The delivered workbook contains no client employee data.
writeRows(source.controls);
wb.recalculate();
const actual=sheet.getRange(`L${dataStart}:AQ${dataStart+source.controls.length-1}`).values;
const differences=[];
source.controls.forEach((control,i)=>{
 for(const [c,expected] of Object.entries(control.expected)) {
  const result=actual[i][colNum(c)-12];
  if(typeof result!=='number'||Math.abs(result-expected)>0.000001) differences.push({sourceRow:control.source_row,column:c,expected,result,delta:typeof result==='number'?result-expected:null});
 }
});
await fs.writeFile(`${outputDir}/verification.json`,JSON.stringify({employees:source.controls.length,differences},null,2));
console.log(JSON.stringify({sourceEmployees:source.controls.length,differences}));
if(differences.some(d=>d.delta===null||Math.abs(d.delta)>1)) throw new Error('Payroll reconciliation exceeded Rp1 tolerance.');
sheet.getRange(`A${dataStart}:${last}${dataStart+source.controls.length-1}`).clear({applyTo:'all'});
const examples=[
 {inputs:{AR:'Monthly premium gross-up'}},
 {inputs:{AS:90000000,AW:5700000,J:'M/2',AZ:1,BA:2,AR:'Monthly net contract'}},
 {inputs:{AS:28500000,AT:22,AW:0,BA:0,AR:'New hire: 22 of 31 days'}},
 {inputs:{AS:17000000,AT:4,AW:0,AY:0,BA:0,BB:1,BC:50000000,BD:1300000,BE:4,BF:3000000,AR:'Final-period refund example'}},
 {inputs:{AS:0,AW:0,AX:0,AY:0,BA:0,AR:'No pay and no insurance cover'}},
 {inputs:{AS:12500000,J:'M/3',P:4000000,AK:0,AR:'Category C with bonus'}},
];
writeRows(examples);
const end=dataStart+examples.length-1;
sheet.getRange(`A1:${last}${end}`).format.font.name='Arial';
sheet.getRange(`A4:${last}${end}`).format.font.size=10;
sheet.getRange(`A${dataStart}:${last}${end}`).format={rowHeight:22,verticalAlignment:'center'};
sheet.getRange(`L${dataStart}:${last}${end}`).setNumberFormat('#,##0;[Red](#,##0);0');
sheet.getRange(`BR${dataStart}:BR${end}`).setNumberFormat('0.00%');
for(let c=1;c<=headers.length;c++) sheet.getRange(`${letter(c)}1:${letter(c)}${end}`).format.columnWidth=16;
for(const c of ['A','B','E','F','AR']) sheet.getRange(`${c}1:${c}${end}`).format.columnWidth=24;
for(const c of ['AS','BC','BD','BE','BF','BM','BN','BO','BP','BQ','BS','BT']) sheet.getRange(`${c}1:${c}${end}`).format.columnWidth=21;
for(const c of ['J','K','C']) sheet.getRange(`${c}1:${c}${end}`).format.columnWidth=10;
for(const c of ['G','H']) sheet.getRange(`${c}${dataStart}:${c}${end}`).setNumberFormat('dd/mm/yyyy');
for(const c of headers.map((_,i)=>letter(i+1)).filter(c=>!formulaCols.includes(c))) sheet.getRange(`${c}${dataStart}:${c}${end}`).format.fill='#FFF6DB';
sheet.getRange(`AQ${headerRow}:AQ${end}`).format.font.bold=true;
sheet.getRange(`J${dataStart}:J${end}`).dataValidation={rule:{type:'list',values:['S/0','S/1','S/2','S/3','M/0','M/1','M/2','M/3']}};
for(const c of ['AX','AY','AZ','BB']) sheet.getRange(`${c}${dataStart}:${c}${end}`).dataValidation={rule:{type:'list',values:['0','1']}};
sheet.getRange(`BA${dataStart}:BA${end}`).dataValidation={rule:{type:'list',values:['0','1','2']}};
sheet.getRange(`BS${dataStart}:BS${end}`).conditionalFormats.add('cellIs',{operator:'notEqual',formula:0,format:{fill:'#FEE2E2',font:{color:'#991B1B'}}});
sheet.freezePanes.freezeRows(headerRow);
sheet.freezePanes.freezeColumns(5);
map.getRange(`A1:L${metadata.length}`).values=metadata;
map.getRange(`A1:L${metadata.length}`).format.font={name:'Arial',size:10};
map.getRange('A1:L1').format={fill:'#35286F',font:{name:'Arial',size:10,color:'#FFFFFF',bold:true},rowHeight:28};
map.getRange(`A1:L${metadata.length}`).format.columnWidth=19;
map.getRange(`L1:L${metadata.length}`).format.columnWidth=34;
map.freezePanes.freezeRows(1);
// Exercise actual recalculation, then restore every temporary edit.
const originalZ=sheet.getRange('Z30').formulas;
const originalStatus=sheet.getRange('J30').values;
let boundaryChecks=0;
for(const key of 'ABC') {
 sheet.getRange('J30').values=[[{A:'S/0',B:'M/2',C:'M/3'}[key]]];
 for(const band of bands[key].filter(b=>b.cap)) {
  for(const gross of [band.cap-1,band.cap,band.cap+1]) {
   sheet.getRange('Z30').values=[[gross]];
   const expected=bands[key].find(b=>!b.cap||gross<=b.cap).rate;
   const result=sheet.getRange('BR30').values[0][0];
   if(Math.abs(result-expected)>1e-10) throw new Error(`TER boundary failed: ${key} ${gross}`);
   boundaryChecks++;
  }
 }
}
sheet.getRange('J30').values=[['Invalid']];
if(sheet.getRange('BR30').values[0][0]!=='Missing PTKP status') throw new Error('Missing status was hidden.');
sheet.getRange('J30').values=originalStatus;
sheet.getRange('Z30').formulas=originalZ;
const originalSalary=sheet.getRange('AS31').values;
sheet.getRange('AS31').values=[[11000000]];
if(Math.abs(sheet.getRange('AQ31').values[0][0]-11000000)>1) throw new Error('Net contract failed to recalculate.');
sheet.getRange('AS31').values=originalSalary;
const originalCap=sheet.getRange(refs.HICAP.replaceAll('$','')).values;
sheet.getRange(refs.HICAP.replaceAll('$','')).values=[[10000000]];
if(sheet.getRange('V31').values[0][0]!==400000) throw new Error('BPJS cap edit did not recalculate.');
sheet.getRange(refs.HICAP.replaceAll('$','')).values=originalCap;
sheet.getRange('A36:BW36').copyFrom(sheet.getRange('A30:BW30'),'all');
if(sheet.getRange('AQ36').values[0][0]!==sheet.getRange('AQ30').values[0][0]) throw new Error('Next employee row failed.');
sheet.getRange('A36:BW36').clear({applyTo:'all'});
console.log(JSON.stringify({boundaryChecks,recalculationChecks:4}));
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Payroll!AS29:BF35',include:'values,formulas',tableMaxRows:7,tableMaxCols:14,maxChars:2500})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30},maxChars:1500})).ndjson);
for(const [name,range,filename] of [['Payroll','A8:J24','ter-a.png'],['Payroll','K8:T24','ter-b.png'],['Payroll','U8:AC24','ter-c.png'],['Payroll','AF8:AL14','annual.png'],['Payroll','L29:S35','earnings.png'],['Payroll','AM29:AQ35','pay-results.png'],['Payroll','AS29:BA35','inputs.png'],['Tax Map','A1:L8','tax-map.png']]) {
 const preview=await wb.render({sheetName:name,range,scale:1.5,format:'png'});
 await fs.writeFile(`${outputDir}/${filename}`,new Uint8Array(await preview.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save(`${outputDir}/Rize_Indonesia_Payroll_Formula_Template_Aug2026.xlsx`);
console.log(JSON.stringify({exported:true,constants:metadata.length-1,formulasPerEmployee:formulaCols.length,columns:headers.length}));
