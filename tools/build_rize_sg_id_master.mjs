// Run in a private task directory linked to bundled @oai/artifact-tool deps.
// Usage: node build_rize_sg_id_master.mjs consolidated|monthly PRIVATE_DIR OUTPUT_DIR
import fs from 'node:fs/promises';
import {Workbook, SpreadsheetFile, FileBlob} from '@oai/artifact-tool';

const [mode, work, output, countryFilter]=process.argv.slice(2);
await fs.mkdir(output,{recursive:true});
const col=n=>{let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const palette={ink:'#243247',purple:'#51439A',paper:'#F4F2FA',input:'#FFF4D4',source:'#EAF2F8',error:'#FDE8E8',muted:'#65748B'};
function table(sheet,headers,rows,widths=[]){
  const n=headers.length;
  sheet.showGridLines=false;
  sheet.getRangeByIndexes(0,0,rows.length+1,n).format={font:{name:'Arial',size:10,color:palette.ink},rowHeight:24,columnWidth:22,verticalAlignment:'center'};
  sheet.getRangeByIndexes(0,0,1,n).values=[headers];
  sheet.getRangeByIndexes(0,0,1,n).format={fill:palette.purple,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:64,wrapText:true,horizontalAlignment:'center'};
  if(rows.length){sheet.getRangeByIndexes(1,0,rows.length,n).values=rows;sheet.getRangeByIndexes(1,0,rows.length,n).format.wrapText=true;}
  widths.forEach((w,i)=>{if(w)sheet.getRangeByIndexes(0,i,rows.length+1,1).format.columnWidth=w;});
  sheet.freezePanes.freezeRows(1);
}
function typed(value,kind){
  if(value===null||value===undefined||value==='')return null;
  if(kind==='date'&&/^\d{4}-\d\d-\d\d/.test(String(value)))return new Date(String(value).slice(0,10)+'T00:00:00Z');
  if(['text','identifier'].includes(kind))return String(value);
  return value;
}
function numberFormat(kind,country){
  return kind==='date'?'dd-mmm-yyyy':kind==='rate'?'0.00%':['text','identifier'].includes(kind)?'@':kind==='integer'?'0':kind==='quantity'?'0.00':country==='ID'?'#,##0;[Red](#,##0);0':'#,##0.00;[Red](#,##0.00);0.00';
}
function destinationLabel(value){
  if(!value)return 'This month only';
  if(value==='c:text')return 'Contract reference';
  if(value==='c:amount')return 'Contract amount';
  const labels={barcode:'Employee code',employee_id:'Employee ID',name:'Name',birthday:'Date of birth',
    payroll_country:'Payroll country',country_id:'Nationality country',job_title:'Job title',date_start:'Start date',
    date_end:'End date',wage:'Basic salary',trial_date_end:'Probation end',private_email:'Personal email',
    private_phone:'Personal phone',work_phone:'Work phone',work_email:'Work email',identification_id:'Government ID',
    permit_no:'Work permit',passport_id:'Passport',department_id:'Department',private_street:'Home address',
    emergency_phone:'Emergency phone',emergency_contact:'Emergency contact',place_of_birth:'Place of birth',
    marital:'Marital status',tax_identification_number:'Tax ID',study_school:'School',study_field:'Study field',
    bank_name:'Bank name',acc_number:'Account number',acc_holder_name:'Account holder',bank_bic:'SWIFT/BIC'};
  const parts=value.split(':');
  return `${parts[0]==='b'?'Bank account':parts[1]==='hr.contract'?'Contract':'Employee'}: ${labels[parts.at(-1)]||parts.at(-1).replaceAll('_',' ')}`;
}
async function render(wb,key,names){
  for(const [name,range] of names){
    const blob=await wb.render({sheetName:name,range,scale:1.25,format:'png'});
    await fs.writeFile(`${work}/${key}-${name.replaceAll(' ','-')}-${mode}.png`,new Uint8Array(await blob.arrayBuffer()));
  }
}
const checks=[];
for(const key of ['sg','id']){
  if(countryFilter&&key!==countryFilter.toLowerCase())continue;
  const def=JSON.parse(await fs.readFile(`${work}/${key}-definition.json`,'utf8'));
  const records=JSON.parse(await fs.readFile(`${work}/${key}-record-plan.json`,'utf8')).records;
  const fixtures=JSON.parse(await fs.readFile(`${work}/${key}-fixtures.json`,'utf8'));
  const country=key==='sg'?'Singapore':'Indonesia';
  if(mode==='consolidated'){
    const wb=Workbook.create();
    const overview=wb.worksheets.add('Overview');
    const source=wb.worksheets.add('Consolidated');
    const calc=wb.worksheets.add('Calculations');
    const rates=wb.worksheets.add('Statutory');
    const audit=wb.worksheets.add('August check');
    const guide=wb.worksheets.add('Field guide');
    overview.showGridLines=false;overview.tabColor=palette.purple;
    overview.getRange('B2:K32').format={font:{name:'Arial',size:10,color:palette.ink},columnWidth:17,rowHeight:24,verticalAlignment:'center'};
    overview.getRange('B2').values=[[`Rize ${country} payroll master`]];
    overview.getRange('B2').format.font={name:'Arial',size:14,bold:true,color:palette.purple};
    overview.getRange('B4:C7').values=[['Period','August 2026'],['Currency',key==='sg'?'SGD':'IDR'],['August payroll employees',fixtures.length],['Master profiles retained',records.length]];
    overview.getRange('B4:B7').format.columnWidth=35;overview.getRange('C4:C7').format.columnWidth=95;
    overview.getRange('B9').values=[['Monthly use']];overview.getRange('B9').format.font.bold=true;
    const workflow=[
      '1. Maintain employee, contract and bank details in Records Desk. Use Employee Code as the matching key.',
      '2. Select the payroll scheme and the new pay month, then download a fresh monthly workbook in Pay Run.',
      '3. Complete Time and Monthly adjustments. Required blank values must be reviewed; an explicit zero is valid.',
      '4. Upload, review employee matches and calculated results, then compute a Draft before normal payroll approvals.',
      '5. Refresh statutory editions for the applicable effective date. Preserve historical editions and August controls.',
    ];
    workflow.forEach((v,i)=>overview.getRange(`B${10+i}:C${10+i}`).values=[['Step '+(i+1),v]]);
    overview.getRange('B16').values=[['Source decisions and limitations']];overview.getRange('B16').format.font.bold=true;
    def.notes.forEach((v,i)=>{overview.getRange(`B${17+i}:C${17+i}`).values=[['Source decision '+(i+1),v]];});
    // A single wide narrative column avoids overflowing notes into data cells.
    overview.getRange('C10:C14').format.wrapText=true;
    overview.getRange(`C17:C${16+def.notes.length}`).format.wrapText=true;
    overview.getRange('B10:C14').format.rowHeight=34;
    overview.getRange(`B17:B${16+def.notes.length}`).format.rowHeight=44;
    const inputs=def.rules.filter(s=>s.type==='input');
    const ordered=[def.primary_code,def.name_code,def.native_id_code].map(c=>inputs.find(s=>s.code===c));
    ordered.push(...inputs.filter(s=>!ordered.includes(s)));
    const inputIndex=new Map(ordered.map((s,i)=>[s.code,i]));
    const rows=records.map(r=>ordered.map(s=>typed(r.values[s.code],s.kind)));
    table(source,ordered.map(s=>s.name),rows);
    source.tabColor=palette.source;
    source.freezePanes.freezeColumns(2);
    for(let i=0;i<ordered.length;i++){
      const s=ordered[i];const r=source.getRangeByIndexes(1,i,rows.length,1);
      r.setNumberFormat(numberFormat(s.kind,def.country));
      if(s.kind==='date')r.format.horizontalAlignment='center';
      r.format.font.color='#164B75';
      if(s.tab)r.format.fill=palette.input;
      if(s.code===def.name_code||/address|name|title/i.test(s.name))source.getRangeByIndexes(0,i,rows.length+1,1).format.columnWidth=34;
    }
    source.getRangeByIndexes(0,0,1,ordered.length).format.rowHeight=92;
    rows.forEach((values,i)=>{
      const lines=Math.max(1,...values.map((v,c)=>typeof v==='string'?Math.ceil(v.length/(/address|name|title/i.test(ordered[c].name)?34:22)):1));
      source.getRangeByIndexes(i+1,0,1,ordered.length).format.rowHeight=Math.max(26,lines*15+6);
    });
    const sources=JSON.parse(await fs.readFile(`${work}/sources.json`,'utf8'));
    const provenance=Object.entries(sources).filter(([k])=>k.endsWith('_'+key)).map(([k,v])=>`${k}: ${v.path}; SHA-256 ${v.sha256}`).join('\n');
    wb.notes.add({id:key+'-source',target:{cell:{sheetName:source.name,sheetId:source.sheetId,address:'A2'}},authorId:'',createdAt:'',body:{plainText:provenance}});
    const constants=def.rules.filter(s=>s.type==='constant');
    const rateIndex=new Map(constants.map((s,i)=>[s.column,i+2]));
    table(rates,['Component code','Parameter or band','Value','Edition','Effective from','Maintenance'],constants.map(s=>[
      s.code,s.name,s.value,'2026-08',new Date('2026-08-01T00:00:00Z'),'Refresh the linked statutory edition in the app; retain this August source baseline.']),[24,45,22,18,19,80]);
    rates.getRangeByIndexes(1,4,constants.length,1).setNumberFormat('dd-mmm-yyyy');
    rates.getRangeByIndexes(1,3,constants.length,2).format.horizontalAlignment='center';
    constants.forEach((s,i)=>rates.getRange(`C${i+2}`).setNumberFormat(numberFormat(s.kind,def.country)));
    const core=def.rules.filter(s=>s.original_code&&s.type!=='constant'||['IDTAXROUND','IDFINALALLOW','IDYTDREVIEW','IDSEVELIG'].includes(s.code)||s.code===def.country+'READY');
    const coreIndex=new Map(core.map((s,i)=>[s.column,i]));
    const coreByCode=new Map(core.map((s,i)=>[s.code,i]));
    table(calc,core.map(s=>s.name),fixtures.map(()=>core.map(()=>null)));
    core.forEach((s,i)=>{if(/name|title|department/i.test(s.name))calc.getRangeByIndexes(0,i,fixtures.length+1,1).format.columnWidth=36;});
    calc.freezePanes.freezeColumns(key==='sg'?3:5);
    function formula(text,row){
      return text.replace(/\$?([A-Z]{1,3})\$?(\d+)/g,(match,c)=>{
        if(rateIndex.has(c))return `'Statutory'!$C$${rateIndex.get(c)}`;
        if(coreIndex.has(c))return `${col(coreIndex.get(c)+1)}${row}`;
        throw Error(`Unknown calculation reference ${match}`);
      });
    }
    fixtures.forEach((f,i)=>{
      const recordRow=records.findIndex(r=>r.code===f.code)+2;
      core.forEach((s,c)=>{
        const sourceRef=`'Consolidated'!${col(inputIndex.get(s.code)+1)}${recordRow}`;
        calc.getCell(i+1,c).formulas=[[s.type==='formula'?formula(s.formula,i+2):`=IF(ISBLANK(${sourceRef}),"",${sourceRef})`]];
      });
      const values=calc.getRangeByIndexes(i+1,0,1,core.length).values[0];
      const lines=Math.max(1,...values.map((v,c)=>typeof v==='string'?Math.ceil(v.length/(/name|title|department/i.test(core[c].name)?36:22)):1));
      calc.getRangeByIndexes(i+1,0,1,core.length).format.rowHeight=Math.max(26,lines*15+6);
    });
    core.forEach((s,i)=>{const r=calc.getRangeByIndexes(1,i,fixtures.length,1);r.setNumberFormat(numberFormat(s.kind,def.country));if(s.kind==='date')r.format.horizontalAlignment='center';});
    const columns=key==='sg'?{gross:'AJ',deduction:'AI',net:'AA',tax:'AL'}:{gross:'Z',deduction:'AP',net:'AQ',tax:'AN'};
    const rulesByColumn=new Map(def.rules.map(s=>[s.column,s]));
    const auditRows=fixtures.map(f=>{
      const sourceValues=JSON.parse(JSON.stringify(f.expected));
      if(key==='sg')sourceValues[rulesByColumn.get('AL').code]=0;
      return [f.code,records.find(r=>r.code===f.code).name,...Object.values(columns).flatMap(c=>[sourceValues[rulesByColumn.get(c).code],null,null])];
    });
    const auditHeaders=['Employee Code','Name',...Object.keys(columns).flatMap(k=>['Source '+k,'Calculated '+k,k+' difference'])];
    table(audit,auditHeaders,auditRows,[20,34,...Array(12).fill(22)]);
    for(let i=0;i<fixtures.length;i++){
      let c=2;
      for(const [metric,original] of Object.entries(columns)){
        const rule=rulesByColumn.get(original);
        audit.getCell(i+1,c+1).formulas=[[`='Calculations'!${col(coreByCode.get(rule.code)+1)}${i+2}`]];
        audit.getCell(i+1,c+2).formulas=[[`=${col(c+2)}${i+2}-${col(c+1)}${i+2}`]];
        c+=3;
      }
    }
    audit.getRangeByIndexes(1,2,fixtures.length,12).setNumberFormat(numberFormat('money',def.country));
    for(const c of ['E','H','K','N'])audit.getRange(`${c}2:${c}${fixtures.length+1}`).conditionalFormats.add('cellIs',{operator:'notEqual',formula:0,format:{fill:palette.error,font:{color:'#9C2333',bold:true}}});
    const guideRows=ordered.map(s=>[s.code,s.name,s.kind,s.tab||'Employee records',destinationLabel(s.destination),s.required?'Required':'Optional',s.note]);
    table(guide,['Component code','Heading','Type','Monthly section or record','Record destination','Requirement','Definition and update rule'],guideRows,[25,44,16,28,35,18,105]);
    guide.getRangeByIndexes(1,6,guideRows.length,1).format.wrapText=true;
    guide.getRangeByIndexes(1,0,guideRows.length,7).format.rowHeight=44;
    guideRows.forEach((values,i)=>{
      const widths=[25,44,16,28,35,18,105];
      const lines=Math.max(...values.map((v,c)=>Math.ceil(String(v).length/widths[c])));
      guide.getRangeByIndexes(i+1,0,1,7).format.rowHeight=Math.max(36,lines*15+8);
    });
    wb.recalculate();
    const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2400});
    console.log(country,errors.ndjson);
    let comparisons=0;
    for(let i=0;i<fixtures.length;i++){
      const actual=calc.getRangeByIndexes(i+1,0,1,core.length).values[0];
      for(const [code,expected] of Object.entries(fixtures[i].expected)){
        const value=actual[coreByCode.get(code)];
        if(typeof expected==='number'){if(typeof value!=='number'||Math.abs(value-expected)>.00001)throw Error(`${country} ${fixtures[i].row} ${code}: ${value} != ${expected}`);}
        else if(value!==expected)throw Error(`${country} ${fixtures[i].row} ${code}: ${value} != ${expected}`);
        comparisons++;
      }
    }
    // Exercise a real input change in the same build, then restore it.
    const salaryIndex=inputIndex.get(def.salary_code),salaryCell=source.getCell(1,salaryIndex);
    const before=salaryCell.values[0][0];
    const netRule=rulesByColumn.get(columns.net),netCell=calc.getCell(1,coreByCode.get(netRule.code));
    const netBefore=netCell.values[0][0];
    salaryCell.values=[[before+1000]];
    const netChanged=netCell.values[0][0];
    if(netChanged===netBefore)throw Error('Salary edit did not recalculate net pay');
    salaryCell.values=[[before]];wb.recalculate();
    if(netCell.values[0][0]!==netBefore)throw Error('Salary scenario was not restored');
    console.log((await wb.inspect({kind:'table',range:'August check!A1:H4',include:'values,formulas',tableMaxRows:4,tableMaxCols:8,maxChars:2000})).ndjson);
    await render(wb,key,[['Overview',`B2:D${18+def.notes.length}`],['Consolidated','A1:H6'],['Calculations',key==='sg'?'F1:M4':'L1:S5'],['Statutory','A1:E8'],['August check','A1:H6'],['Field guide','A1:F7']]);
    const path=`${output}/Rize_${country}_Consolidated_Payroll_and_Master.xlsx`;
    await (await SpreadsheetFile.exportXlsx(wb)).save(path);
    checks.push({country,path,sourceRows:records.length,payrollRows:fixtures.length,exactComparisons:comparisons,inputMutationRecalculated:true,restored:true});
  }else if(mode==='monthly'){
    const fill=JSON.parse(await fs.readFile(`${work}/${key}-fill-plan.json`,'utf8'));
    const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(`${work}/${key}-issued-template.xlsx`));
    const current=await SpreadsheetFile.importXlsx(await FileBlob.load(`${work}/${key}-current-template.xlsx`));
    await render(current,key+'-October',[['Time','A1:H6'],['Monthly adjustments','A1:H6'],['Employee records','A1:H6']]);
    await render(wb,key,[['Time','A1:H6'],['Monthly adjustments','A1:H6'],['Employee records','A1:H6']]);
    for(const item of fill.cells)wb.worksheets.getItem(item.sheet).getRange(item.cell).values=[[item.value]];
    wb.recalculate();
    const err=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},maxChars:1000});
    console.log(country,err.ndjson);
    await render(wb,key,[['Time','A1:H6'],['Monthly adjustments','A1:H6']]);
    await (await SpreadsheetFile.exportXlsx(wb)).save(`${work}/${key}-artifact-monthly.xlsx`);
    checks.push({country,monthlyAuthoredCells:fill.cells.length});
  }else throw Error('Choose consolidated or monthly');
}
await fs.writeFile(`${work}/${mode}${countryFilter?'-'+countryFilter.toLowerCase():''}-workbook-verification.json`,JSON.stringify(checks,null,2));
console.log(JSON.stringify(checks));
