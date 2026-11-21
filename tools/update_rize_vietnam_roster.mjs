// Narrow update of existing delivery workbooks after the owner's roster reply.
import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const [workDir,outputDir,decisionPath,mode]=process.argv.slice(2);
const src=JSON.parse(await fs.readFile(`${workDir}/source-review.json`,'utf8'));
const decision=JSON.parse(await fs.readFile(decisionPath,'utf8'));
const selected=src.roster.filter(p=>decision.included_source_statuses.includes(p.status));
if(selected.length!==70 || new Set(selected.map(p=>p.key)).size!==70)throw Error('Review roster must contain 70 unique IDs');
const names=['Vietnam_Configuration_Review.xlsx','Vietnam_Monthly_Input_Template.xlsx'];
const [review,monthly]=await Promise.all(names.map(async name=>SpreadsheetFile.importXlsx(await FileBlob.load(`${outputDir}/${name}`))));
if(mode==='preview'){
 for(const [wb,sheetName,range,name]of [[review,'Review','B17:E19','review'],[monthly,'Time','A1:F5','monthly']]){
  const img=await wb.render({sheetName,range,scale:1.2,format:'png'});
  await fs.writeFile(`${workDir}/roster-before-${name}.png`,new Uint8Array(await img.arrayBuffer()));
 }
 process.exit(0);
}
const front=review.worksheets.getItem('Review');
front.getRange('C18:E18').values=[['Include 68 Active and 2 Notice Period employees for review. Pay-month eligibility and record exceptions still require validation.','Approved','Owner confirmed inclusion for review on 17 October 2026.']];
const roster=review.worksheets.getItem('Roster review');
const wanted=new Set(selected.map(p=>p.key));
const rosterRows=roster.getRange('A2:F128').values;
for(let i=0;i<rosterRows.length;i++){
 const key=String(rosterRows[i][1]);
 const chosen=wanted.has(key);
 roster.getRange(`E${i+2}:F${i+2}`).values=[[chosen?'Included in 70-person review roster':'Outside the 70-person review roster',chosen?'Include':'Exclude']];
}
if(rosterRows.filter(r=>wanted.has(String(r[1]))).length!==70)throw Error('Saved review roster does not match source');
for(const tab of ['Time','Monthly adjustments']){
 const sh=monthly.worksheets.getItem(tab);
 const existing=sh.getRange('A2:B71').values;
 if(existing.some((r,i)=>r.some(v=>v!==null&&v!=='') && (String(r[0])!==selected[i].key || r[1]!==selected[i].name)))throw Error('Existing identity entries need reconciliation; do not overwrite');
 sh.getRange('A2:B71').values=selected.map(p=>[p.key,p.name]);
}
const guide=monthly.worksheets.getItem('Instructions');
guide.getRange('B2').values=[['The owner included 68 Active and 2 Notice Period employees for review. Resolve configuration, salary and record exceptions before import. The payroll configuration remains Draft.']];
guide.getRange('B5').values=[['Country-Based Employee ID and Employee Name are prefilled for the same 70 people on both tabs. Verify identities, keep one row per employee and retain IDs as text.']];
for(const wb of [review,monthly])wb.recalculate();
if(front.getRange('C30').values[0][0]!==10)throw Error('Remaining review decisions should equal 10');
for(const [wb,sheetName,range,name]of [[review,'Review','B17:E20','review'],[review,'Roster review','A1:F8','roster'],[monthly,'Time','A1:F8','time'],[monthly,'Monthly adjustments','A1:F8','adjustments'],[monthly,'Instructions','A1:B6','instructions']]){
 const img=await wb.render({sheetName,range,scale:1.2,format:'png'});
 await fs.writeFile(`${workDir}/roster-after-${name}.png`,new Uint8Array(await img.arrayBuffer()));
}
for(const [i,wb]of [review,monthly].entries()){
 console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:500})).ndjson);
 await(await SpreadsheetFile.exportXlsx(wb)).save(`${outputDir}/${names[i]}`);
}
console.log(JSON.stringify({review_people:70,active:68,notice:2,pending_decisions:10,monthly_amounts:'unchanged'}));
