// Run from a task directory linked to the bundled artifact-tool dependencies.
import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [outputDir, probeDataPath, probeOutputPath] = process.argv.slice(2);
await fs.mkdir(outputDir, {recursive: true});
const wb = Workbook.create();
const payroll = wb.worksheets.add('Payroll');
const guide = wb.worksheets.add('Instructions');
const fields = [
 ['Department','text','Optional','Department name.'],
 ['Cost Centre','text','Optional','Cost centre code. Preserve any leading zeros.'],
 ['No.','integer','Optional','Row number for reference only.'],
 ['Employee ID','identifier','Every employee','Use the employee code registered in Payobook. One row per employee; no duplicates.'],
 ['Name','text','Every employee','Employee name for review. Employee ID is the matching key.'],
 ['Job Title','text','Optional','Employee job title.'],
 ['Join Date','date','When applicable','Actual employment start date; otherwise leave blank.'],
 ['Resign Date','date','When applicable','Actual leaving date; otherwise leave blank.'],
 ['Employee Status','text','Optional','Employment type, for example Permanent or Contract. Reference only.'],
 ['S/M','text','Every employee','PTKP status: S/0, S/1, S/2, S/3, M/0, M/1, M/2 or M/3. Keep the slash.'],
 ['L/E','text','Optional','Local / expatriate reference: L or E. This field does not select a separate tax calculation.'],
 ['Bonus','money','Zero if none','Bonus paid in this period, IDR.'],
 ['THR','money','Zero if none','Religious holiday allowance in this period, IDR.'],
 ['Incentive','money','Zero if none','Incentive in this period, IDR.'],
 ['Daily allowance','money','Zero if none','Total allowance amount for this period, IDR; not a daily rate.'],
 ['Tax allowance irregular','money','Zero if none','Irregular tax allowance amount provided by payroll, IDR.'],
 ['Qualifying severance paid','money','Zero if none','Qualifying severance in this period, IDR. Confirm treatment before a first severance payment.'],
 ['THR already paid','money','Zero if none','THR already paid outside this payroll; positive amount deducted from take-home pay, IDR.'],
 ['Incentive already paid','money','Zero if none','Incentive already paid outside this payroll; positive amount deducted from take-home pay, IDR.'],
 ['Other deduction','money','Zero if none','Positive deduction, IDR. Use a negative amount only for an agreed refund.'],
 ['Tax adjustment','money','Zero if none','Positive additional deduction or negative refund, IDR.'],
 ['Remarks','text','Optional','Explanation of changes or unusual payments.'],
 ['Contract basic salary','money','Every employee','Full-period contracted basic salary, IDR. The scheme calculates prorated salary.'],
 ['Paid days','quantity','Every employee','Days paid at the current salary. May include fractions.'],
 ['Period days','quantity','Every employee','Proration denominator for this month; must be greater than zero. Use the agreed payroll calendar.'],
 ['Salary adjustment','money','Zero if none','Signed salary backpay or correction, IDR; added after proration.'],
 ['Annual insurance premium','money','Zero if none','Annual private insurance premium, IDR. The scheme calculates its monthly amount.'],
 ['BPJS TK covered','integer','Every employee','1 = covered; 0 = not covered.'],
 ['BPJS health covered','integer','Every employee','1 = covered; 0 = not covered.'],
 ['Employer reimburses employee BPJS','integer','Every employee','1 = employer reimburses employee BPJS deductions; 0 = employee bears them.'],
 ['Tax allowance mode','integer','Every employee','0 = no tax allowance; 1 = premium tax allowance; 2 = full monthly net-to-gross.'],
 ['Final tax period','integer','Every employee','0 = ordinary monthly TER; 1 = final annual tax settlement. Set 1 for the relevant final tax period.'],
 ['Prior YTD taxable gross','money','Final period; otherwise 0','Taxable gross before this month in the same tax year, IDR. Exclude this month.'],
 ['Prior YTD deductible JHT and JP','money','Final period; otherwise 0','Employee deductible JHT and JP before this month in the same tax year, IDR.'],
 ['Job expense eligible months','integer','Final period; otherwise 0','Number of eligible months in the tax year, including this month, from 0 to 12.'],
 ['Prior YTD PPh21 withheld','money','Final period; otherwise 0','PPh21 already withheld before this month in the same tax year, IDR.'],
 ['Leave balance days','quantity','Zero if none','Unused leave days being paid now. The scheme calculates the amount using salary and period days.'],
 ['Prior qualifying severance paid','money','Severance; otherwise 0','Prior qualifying severance within the applicable payment window, IDR. Exclude this payment.'],
 ['Prior severance tax withheld','money','Severance; otherwise 0','Tax already withheld on those prior qualifying severance payments, IDR.'],
];
const letter = n => {let s=''; for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s; return s;};
const last=letter(fields.length), end=301;
payroll.showGridLines=false;
payroll.tabColor='#5747B5';
payroll.getRange(`A1:${last}${end}`).format={font:{name:'Arial',size:10,color:'#26324A'},rowHeight:23,verticalAlignment:'center'};
payroll.getRange(`A1:${last}1`).values=[fields.map(f=>f[0])];
payroll.getRange(`A1:${last}1`).format={fill:'#35286F',font:{name:'Arial',size:10,color:'#FFFFFF',bold:true},wrapText:true,rowHeight:62,horizontalAlignment:'center',verticalAlignment:'center'};
payroll.getRange(`A2:${last}${end}`).format.fill='#FFF6DB';
fields.forEach(([name,kind],i)=>{
 const col=letter(i+1), range=payroll.getRange(`${col}2:${col}${end}`);
 payroll.getRange(`${col}1:${col}${end}`).format.columnWidth=['Name','Remarks'].includes(name)?30:kind==='money'?21:19;
 range.setNumberFormat(kind==='date'?'dd/mm/yyyy':['text','identifier'].includes(kind)?'@':kind==='quantity'?'0.00':'#,##0;[Red](#,##0);0');
 range.format.horizontalAlignment=['text','identifier'].includes(kind)?'left':'right';
 if(name==='S/M')range.dataValidation={rule:{type:'list',values:['S/0','S/1','S/2','S/3','M/0','M/1','M/2','M/3']}};
 if(name==='L/E')range.dataValidation={rule:{type:'list',values:['L','E']}};
 if(['BPJS TK covered','BPJS health covered','Employer reimburses employee BPJS','Final tax period'].includes(name))range.dataValidation={rule:{type:'whole',operator:'between',formula1:0,formula2:1}};
 if(name==='Tax allowance mode')range.dataValidation={rule:{type:'whole',operator:'between',formula1:0,formula2:2}};
 if(name==='Job expense eligible months')range.dataValidation={rule:{type:'whole',operator:'between',formula1:0,formula2:12}};
 if(name==='Period days')range.dataValidation={rule:{type:'decimal',operator:'greaterThan',formula1:0}};
});
payroll.freezePanes.freezeRows(1);
payroll.freezePanes.freezeColumns(5);
wb.names.add('PayrollHeader',payroll.getRange(`A1:${last}1`));

guide.showGridLines=false;
guide.getRange('A1:E58').format={font:{name:'Arial',size:10,color:'#26324A'},verticalAlignment:'center',rowHeight:26};
guide.getRange('A2').values=[['Rize Indonesia monthly payroll inputs']];
guide.getRange('A2').format.font={name:'Arial',size:14,bold:true,color:'#35286F'};
const notes=[
 'Use one copy per month. Name it Rize_Indonesia_Inputs_YYYY-MM.xlsx.',
 'Complete Payroll from row 2. One employee per row; keep the headings and sheet name unchanged.',
 'Amounts are IDR. Enter numeric values, not currency symbols. Enter 0 where an amount does not apply.',
 'Every employee needs Employee ID, Name, S/M, salary, paid days, period days and all five control flags/modes.',
 'Leave optional text and dates blank if not applicable. Remove unused employee rows; add more rows if needed.',
 'Payroll contains inputs only. Payobook keeps the formulas and statutory tables; do not add calculated columns.',
 'Return this file to the payroll operator. The operator selects the pay month and Indonesia configuration in Pay Run.',
 'For final settlements, complete the prior YTD fields and eligible months; the calculation can produce a tax refund.',
 'Final tax period = 1 with tax allowance mode = 2 requires a separate annual gross-up review before payroll.',
 'Severance uses qualifying first-two-year treatment. Confirm eligibility and prior totals before processing.',
 'This input layout is paired with Rize Indonesia · August 2026. Later statutory changes are managed in Payobook.',
];
notes.forEach((v,i)=>{guide.getRange(`A${4+i}`).values=[[v]];guide.getRange(`A${4+i}:E${4+i}`).merge();});
guide.getRange('A16:E16').values=[['Column','Input field','Value type','When needed','What to enter']];
guide.getRange('A16:E16').format={fill:'#35286F',font:{name:'Arial',size:10,color:'#FFFFFF',bold:true},rowHeight:28};
guide.getRange(`A17:E${16+fields.length}`).values=fields.map((f,i)=>[letter(i+1),...f]);
guide.getRange(`A17:E${16+fields.length}`).format={rowHeight:42,wrapText:true};
guide.getRange('A1:A58').format.columnWidth=9;
guide.getRange('B1:B58').format.columnWidth=38;
guide.getRange('C1:C58').format.columnWidth=15;
guide.getRange('D1:D58').format.columnWidth=28;
guide.getRange('E1:E58').format.columnWidth=110;
guide.freezePanes.freezeRows(16);
// A disposable filled copy exercises the actual monthly import parser. The
// client deliverable is cleared again before export and contains no examples.
if(probeDataPath && probeOutputPath) {
 const examples=JSON.parse(await fs.readFile(probeDataPath,'utf8'));
 const rows=examples.map(row=>fields.map(([name])=>row[name]??null));
 payroll.getRange(`A2:${last}${rows.length+1}`).values=rows;
 wb.recalculate();
 await (await SpreadsheetFile.exportXlsx(wb)).save(probeOutputPath);
 payroll.getRange(`A2:${last}${rows.length+1}`).clear({applyTo:'contents'});
}
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Payroll!A1:L3',include:'values,formulas',tableMaxRows:3,tableMaxCols:12,maxChars:2000})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:1000})).ndjson);
for(const [sheetName,range,file] of [['Payroll','A1:H8','inputs-preview.png'],['Instructions','A1:E23','instructions-preview.png']]) {
 const preview=await wb.render({sheetName,range,scale:1.5,format:'png'});
 await fs.writeFile(`${outputDir}/${file}`,new Uint8Array(await preview.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(`${outputDir}/Rize_Indonesia_Monthly_Inputs.xlsx`);
console.log(JSON.stringify({columns:fields.length,blankRows:end-1,formulas:0,statutoryTables:0}));
