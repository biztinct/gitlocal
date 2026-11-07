// Formula-only review workbook. Employee examples are fictional.
import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';
const [definitionPath, outputDir] = process.argv.slice(2);
const definitions = JSON.parse(await fs.readFile(definitionPath, 'utf8'));
const wb = Workbook.create();
const letter = n => {let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
await fs.mkdir(outputDir,{recursive:true});
for(const spec of definitions){
  const sheet=wb.worksheets.add(spec.view==='actual'?'Actual':'Audit');
  sheet.showGridLines=false;
  const last=letter(spec.rules.length), map=Object.fromEntries(spec.rules.map((r,i)=>[r.code,letter(i+1)]));
  sheet.getRange(`A1:${last}3`).format.font={name:'Arial',size:10};
  sheet.getRange(`A1:${last}1`).values=[spec.rules.map(r=>r.name)];
  sheet.getRange(`A1:${last}1`).format={fill:'#35286F',font:{name:'Arial',size:10,color:'#FFFFFF',bold:true},wrapText:true,rowHeight:65,verticalAlignment:'center',horizontalAlignment:'center'};
  sheet.getRange(`A1:${last}3`).format.columnWidth=20;
  sheet.getRange('B1:B3').format.columnWidth=27;
  for(let row=2;row<=3;row++){
    const example={VNID:`EXAMPLE${row-1}`,VNNAME:`Example ${row===2?'monthly':'daily'} employee`,VNBASIS:row===2?1:2,
      VNBASE:row===2?8000000:300000,VNPAIDDAYS:26,VNDIVISOR:26,VNHOURSDAY:8,
      VNLEAVERATE:spec.view==='actual'?190000:50000,VNRELIEF:15500000,VNRECOVERYUSED:1};
    sheet.getRange(`A${row}:${last}${row}`).values=[spec.rules.map(r=>r.formula?null:example[r.code]??0)];
    for(const [i,r] of spec.rules.entries()){
      const cell=sheet.getRange(`${letter(i+1)}${row}`);
      if(r.formula)cell.formulas=[['='+r.formula.replace(/\{([A-Z]+)\}/g,(_,code)=>map[code]+row)]];
      else cell.format.fill='#FFF3CF';
      if(r.kind==='money')cell.setNumberFormat('#,##0;[Red](#,##0);–');
      else if(['quantity','rate','decimal'].includes(r.kind))cell.setNumberFormat('0.00');
      if(r.role==='net')cell.format={fill:'#EEEAF8',font:{name:'Arial',size:10,bold:true}};
    }
  }
  sheet.freezePanes.freezeRows(1);
  sheet.getRange(`${map.VNBASIS}2:${map.VNBASIS}3`).dataValidation={rule:{type:'list',values:['1','2']}};
}
const readme=wb.worksheets.add('ReadMe');readme.showGridLines=false;
const notes=[
 ['Sudima September 2026 review template'],
 ['All amounts are VND. The original payroll uses thousands of VND.'],
 ['Import the Audit calculation sheet. Examples are fictional.'],
 ['Print-Audit is the draft base payroll. Actual Pay extras are excluded by owner instruction.'],
 ['Monthly and daily workers use one formula with the Pay basis field. Blue-purple headers are components; pale yellow cells are inputs.'],
 ['The application stores basic, responsibility and position rates on draft contracts. Historical time and variable amounts exist only in Test.'],
 ['Actual Pay differences are documented separately for a later decision. No extra-pay or bonus rule from Actual is installed.'],
 ['Salary divisor 26 and eight hours per salary day reproduce the source. They do not establish Sudima’s attendance calendar or break rules.'],
 ['Allowances, insurance, source zero overrides and cross-row tax carries require policy review before unattended payroll.'],
 ['No monthly source-file upload is proposed as the future routine. Confirm the policy, connect devices, approve attendance and resolve application source gaps first.'],
 ['Source: Sudima_ENG.xlsx, Actual pay_Sep (transfer+cash) and Salary_Sep (Print-Audit), September 2026.'],
 ['Employee roster cross-check: Sep 26_Attendance.xlsx, Attendance Sep-26(N).'],
 ['UI: Settings > Payroll configurations > configuration > Pay rules, Connect, Outputs and Test. Employee and contract values are editable in Records.'],
 ['Do not activate the historical review template as an unattended payroll. No wages are issued by importing or testing this workbook.']
];
readme.getRange(`A1:A${notes.length}`).values=notes;
readme.getRange(`A1:A${notes.length}`).format={font:{name:'Arial',size:11},columnWidth:120,rowHeight:42,wrapText:true,verticalAlignment:'center'};
readme.getRange('A1').format={fill:'#35286F',font:{name:'Arial',size:15,bold:true,color:'#FFFFFF'}};
wb.recalculate();
for(const spec of definitions){
 const name=spec.view==='actual'?'Actual':'Audit', sheet=wb.worksheets.getItem(name);
 const map=Object.fromEntries(spec.rules.map((r,i)=>[r.code,letter(i+1)]));
 const net=sheet.getRange(`${map.VNNET}2:${map.VNNET}3`).values.flat();
 if(net[0]!==8000000||net[1]!==7800000)throw new Error(`${name} example net mismatch ${net}`);
 console.log((await wb.inspect({kind:'table',range:`${name}!${map.VNNETRAW}1:${map.VNROUNDING}3`,include:'values,formulas',tableMaxRows:3,tableMaxCols:3})).ndjson);
 for(const [suffix,range] of [['inputs','A1:H3'],['outputs',`${map.VNGROSS}1:${map.VNROUNDING}3`]]){
   const blob=await wb.render({sheetName:name,range,scale:1.5});
   await fs.writeFile(`${outputDir}/${name}-${suffix}.png`,new Uint8Array(await blob.arrayBuffer()));
 }
}
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!',options:{useRegex:true,maxResults:10}})).ndjson);
const preview=await wb.render({sheetName:'ReadMe',range:'A1:A14',scale:1.5});
await fs.writeFile(`${outputDir}/ReadMe.png`,new Uint8Array(await preview.arrayBuffer()));
await (await SpreadsheetFile.exportXlsx(wb)).save(`${outputDir}/Sudima_September_Payroll_Review_Template.xlsx`);
console.log('Exported review template with fictional examples.');
