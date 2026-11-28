// Run from a task directory linked to the bundled artifact-tool dependencies.
import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const [workDir,outputDir]=process.argv.slice(2);
const d=JSON.parse(await fs.readFile(`${workDir}/definition.json`,'utf8'));
const src=JSON.parse(await fs.readFile(`${workDir}/source-review.json`,'utf8'));
const receipt=JSON.parse(await fs.readFile(`${workDir}/install-receipt.json`,'utf8'));
await fs.mkdir(outputDir,{recursive:true});
const col=n=>{let s='';while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s};
function base(wb,name){const s=wb.worksheets.add(name);s.showGridLines=false;return s}
function table(s,headers,rows,widths){
 const last=col(headers.length),n=rows.length+1;
 s.getRange(`A1:${last}${Math.max(2,n)}`).format={font:{name:'Arial',size:10,color:'#27344A'},rowHeight:28,verticalAlignment:'center'};
 s.getRange(`A1:${last}1`).values=[headers];
 s.getRange(`A1:${last}1`).format={fill:'#40376E',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:48,horizontalAlignment:'center'};
 if(rows.length)s.getRange(`A2:${last}${n}`).values=rows;
 widths.forEach((w,i)=>s.getRange(`${col(i+1)}1:${col(i+1)}${Math.max(2,n)}`).format.columnWidth=w);
 s.freezePanes.freezeRows(1);s.freezePanes.freezeColumns(1);
 if(rows.length)s.tables.add(`A1:${last}${n}`,true,nameSafe(s.name));
 return s;
}
function nameSafe(s){return s.replace(/[^A-Za-z]/g,'')+'Table'}
const wb=Workbook.create();
const review=base(wb,'Review');
review.getRange('B2').values=[['Vietnam payroll configuration review']];
review.getRange('B2').format={font:{name:'Arial',size:14,bold:true,color:'#27344A'},columnWidth:28};
const summary=[['Configuration',d.name],['State','Draft. Validate before cutover.'],['Source population',127],['Active / Notice / Inactive','68 / 2 / 57'],['Source columns covered',d.mapping.length],['Mapped source fields',d.mapping.filter(m=>m.status==='Mapped').length],['Configured components',d.rules.length],['Stored test cases',receipt.tests.passed],['Independent assertions',receipt.independent_checks],['Employees assigned',0],['Source exceptions',src.issues.length]];
review.getRange('B4:C14').values=summary;
review.getRange('B4:C14').format={font:{name:'Arial',size:10,color:'#27344A'},rowHeight:25,columnWidth:32};
review.getRange('C4:C14').format.columnWidth=75;
if(receipt.roster_reconciliation){
 const rc=receipt.roster_reconciliation;
 review.getRange('E4:F8').values=[['Source / current records','To review'],['Active / Notice IDs matched',`${rc.matched} of ${rc.source_active_notice}`],['No existing employee match',rc.missing],['Missing source salary',rc.missing_salary],['Source salary differs from contract',rc.salary_differences]];
 review.getRange('E4:F8').format={font:{name:'Arial',size:10,color:'#27344A'},rowHeight:28,columnWidth:48};
 review.getRange('E4:F4').format={fill:'#40376E',font:{name:'Arial',size:10,color:'#FFFFFF',bold:true}};
 review.getRange('F5:F8').format.fill='#FFF4D6';
}
review.getRange('B17:E17').values=[['Review area','Action','Decision','Your notes']];
review.getRange('B17:E17').format={fill:'#40376E',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:32};
review.getRange('B18:E28').values=d.review.map(r=>[...r,'']);
review.getRange('B18:E28').format={font:{name:'Arial',size:10,color:'#27344A'},rowHeight:64,wrapText:true,verticalAlignment:'center'};
review.getRange('C17:C28').format.columnWidth=75;
review.getRange('D17:D28').format.columnWidth=20;
review.getRange('E17:E28').format.columnWidth=48;
review.getRange('D18:E28').format.fill='#FFF4D6';
review.getRange('D18:D28').dataValidation={rule:{type:'list',values:['Pending','Approved','Change requested']}};
review.getRange('D18:D28').conditionalFormats.add('cellIs',{operator:'equal',formula:'"Change requested"',format:{fill:'#FDE7E7',font:{color:'#9C2020'}}});
review.getRange('B30').values=[['Reviews still pending']];
review.getRange('C30').formulas=[['=11-COUNTIFS(D18:D28,"Approved")']];
review.getRange('B30:C30').format={font:{name:'Arial',size:10,bold:true},rowHeight:28};
const maps=table(base(wb,'Source mapping'),['VN column','Source heading','People populated','Disposition','Component','Value type','Destination','Treatment'],d.mapping.map(m=>[m.column,m.source,m.populated,m.status,m.code,m.kind,m.destination,m.note]),[12,50,16,20,18,15,44,80]);
maps.getRange('B2:B105').format.wrapText=true;maps.getRange('H2:H105').format.wrapText=true;maps.getRange('A2:H105').format.rowHeight=64;
const ruleSheet=table(base(wb,'Payroll rules'),['Code','Component','Input / formula','Value type','Report group','Pay role','Detail only','Record destination','Formula or source','Review note'],d.rules.map(r=>[r.code,r.name,r.type,r.kind,r.group,r.role,r.detail?'Yes':'No',r.destination,r.formula?"'="+r.formula:r.value??r.source_key??'Recurring settings|'+r.name,r.note]),[18,42,20,16,29,20,14,44,90,80]);
ruleSheet.getRange(`B2:B${d.rules.length+1}`).format.wrapText=true;ruleSheet.getRange(`J2:J${d.rules.length+1}`).format.wrapText=true;ruleSheet.getRange(`A2:J${d.rules.length+1}`).format.rowHeight=48;
ruleSheet.getRange(`I2:I${d.rules.length+1}`).format.wrapText=true;
d.rules.forEach((r,i)=>{if(r.formula)ruleSheet.getRange(`A${i+2}:J${i+2}`).format.rowHeight=Math.max(64,Math.ceil(r.formula.length/90)*14+20)});
const issues=table(base(wb,'Source exceptions'),['Source row','Country-Based Employee ID','VN column','Issue','Review status','Your decision'],src.issues.map(i=>[i.row,i.key,i.field,i.issue,i.status,'']),[14,24,14,90,20,55]);
issues.getRange(`E2:F${src.issues.length+1}`).format.fill='#FFF4D6';
issues.getRange(`E2:E${src.issues.length+1}`).dataValidation={rule:{type:'list',values:['Open','Resolved','Accepted for review']}};
const recurring=d.rules.filter(r=>r.destination==='c:amount'||r.destination==='c:text');
const cs=table(base(wb,'Contract components'),['Code','Component','Storage','Value type','Purpose','Payroll effect'],recurring.map(r=>[r.code,r.name,r.destination==='c:text'?'Text':'Amount',r.kind,r.note,r.code.startsWith('VNHC')?'Reference only':'Recurring payroll input']),[18,43,15,17,95,28]);
cs.getRange(`E2:E${recurring.length+1}`).format.wrapText=true;cs.getRange(`A2:F${recurring.length+1}`).format.rowHeight=50;
const roster=table(base(wb,'Roster review'),['Source row','Country-Based Employee ID','Employee Name','Source status','Proposed inclusion','Your decision'],src.roster.map(p=>[p.row,p.key,p.name,p.status,p.status==='Inactive'?'Exclude unless approved final pay':'Review for monthly population','Pending']),[14,24,40,22,48,25]);
roster.getRange('B2:B128').setNumberFormat('@');roster.getRange('F2:F128').format.fill='#FFF4D6';
roster.getRange('F2:F128').dataValidation={rule:{type:'list',values:['Pending','Include','Exclude']}};
const sources=table(base(wb,'Sources'),['Source / scope'],d.sources.map(v=>[v]),[150]);
sources.getRange(`A2:A${d.sources.length+1}`).format.wrapText=true;sources.getRange(`A2:A${d.sources.length+1}`).format.rowHeight=42;
wb.recalculate();
if(review.getRange('C30').values[0][0]!==11)throw Error('Pending review formula');
review.getRange('D18').values=[['Approved']];
wb.recalculate();
if(review.getRange('C30').values[0][0]!==10)throw Error('Review status did not recalculate');
review.getRange('D18').values=[['Pending']];
wb.recalculate();
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
for(const [name,range] of [['Review','B2:E14'],['Source mapping','A1:D7'],['Payroll rules','A1:G8'],['Source exceptions','A1:D8'],['Contract components','A1:D8'],['Roster review','A1:F8'],['Sources','A1:A5']]){
 const img=await wb.render({sheetName:name,range,scale:1.3,format:'png'});
 await fs.writeFile(`${workDir}/${name.replaceAll(' ','-')}.png`,new Uint8Array(await img.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(wb)).save(`${outputDir}/Vietnam_Configuration_Review.xlsx`);

// This is a clean import schema. A populated, period-specific server download
// follows approved record changes and population assignment.
const monthly=Workbook.create();
for(const tab of ['Time','Monthly adjustments']){
 const inputRules=d.rules.filter(r=>r.tab===tab);
 const headers=['Country-Based Employee ID','Employee Name',...inputRules.map(r=>r.name)];
 const sh=table(base(monthly,tab),headers,[],headers.map((h,i)=>i===1?35:28));
 const last=col(headers.length);
 sh.getRange(`A2:${last}101`).format={font:{name:'Arial',size:10,color:'#27344A'},rowHeight:24,fill:'#FFF4D6'};
 sh.getRange('A2:B101').setNumberFormat('@');
 sh.getRange(`C2:${last}101`).setNumberFormat(tab==='Time'?'0.00':'#,##0');
 for(let i=2;i<headers.length;i++)sh.getRange(`${col(i+1)}2:${col(i+1)}101`).dataValidation={rule:{type:'decimal',operator:'greaterThanOrEqual',formula1:0}};
 sh.freezePanes.freezeColumns(2);
}
const instructions=table(base(monthly,'Instructions'),['Step','Monthly upload instruction'],[
 [1,'First approve the configuration, source exceptions, recurring settings and payroll population. This blank schema has no assigned employees.'],
 [2,'Apply only approved employee and contract changes through Records Desk. Assign the reviewed scheme to the intended population.'],
 [3,'Prefer the populated template from Configure Templates once the new scheme has eligible employees. Its roster and saved record context are current.'],
 [4,'For this blank schema, enter the same Country-Based Employee ID and Employee Name on both tabs. One row per employee, no duplicate IDs. Keep IDs as text.'],
 [5,'Choose the pay month in Pay Run. Time: enter standard working days and paid days. Unpaid leave and weekend hours are reference only.'],
 [6,'Monthly adjustments: enter approved actual cash payments and deductions as positive VND amounts. Do not enter annual bonus targets or CTC.'],
 [7,'Approved overtime pay is the complete overtime payment. Include only its approved exempt amount in Approved cash tax exemption, with other validated exemptions.'],
 [8,'Manual PIT is required for Manual tax mode. Set an explicit reviewed zero where appropriate. Resident mode calculates progressive tax.'],
 [9,'Fixed salary, recurring allowances, tax mode, dependents and insurance settings come from records. They are not monthly adjustment columns.'],
 [10,'Use a new copy for every month. Blank variable amounts are zero in a new month. A zero is an explicit update when reviewing an existing month.'],
 [11,'Preview the import, resolve unmatched IDs and missing settings, then compare a draft parallel payroll with the approved control before cutover.'],
 [12,'Source file: '+d.source+'. The unlabelled Sheet4 and name-only Dependent sheet are not used as monthly input sources.'],
 ],[10,125]);
instructions.getRange('B2:B13').format.wrapText=true;instructions.getRange('A2:B13').format.rowHeight=48;
monthly.recalculate();
for(const [name,range]of [['Time','A1:F8'],['Monthly adjustments','A1:F8'],['Instructions','A1:B7']]){
 const img=await monthly.render({sheetName:name,range,scale:1.3,format:'png'});
 await fs.writeFile(`${workDir}/Monthly-${name.replaceAll(' ','-')}.png`,new Uint8Array(await img.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(monthly)).save(`${outputDir}/Vietnam_Monthly_Input_Template.xlsx`);
for(const tab of ['Time','Monthly adjustments']){
 const inputRules=d.rules.filter(r=>r.tab===tab);
 monthly.worksheets.getItem(tab).getRange(`A2:${col(inputRules.length+2)}2`).values=[['VNTEST001','Example employee',...inputRules.map(r=>r.code==='VNSTDDAYS'||r.code==='VNPAIDDAYS'?22:r.code==='VNACTBONUS'?1000000:0)]];
}
monthly.recalculate();
await(await SpreadsheetFile.exportXlsx(monthly)).save(`${workDir}/monthly-probe.xlsx`);
console.log(JSON.stringify({reviewSheets:7,monthlySheets:3,monthlyRows:0,sourcePeople:src.roster.length,sourceExceptions:src.issues.length}));
