// Match display labels to the source while preserving the approved review workbooks.
import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const [definitionPath,outputDir,workDir,mode]=process.argv.slice(2);
const d=JSON.parse(await fs.readFile(definitionPath,'utf8'));
const names=new Map(d.rules.map(r=>[r.code,r.name]));
const files=['Vietnam_Configuration_Review.xlsx','Vietnam_Monthly_Input_Template.xlsx'];
const books=await Promise.all(files.map(async n=>SpreadsheetFile.importXlsx(await FileBlob.load(`${outputDir}/${n}`))));
const [review,monthly]=books;
if(mode!=='preview'){
 for(const tab of ['Payroll rules','Contract components']){
  const sh=review.worksheets.getItem(tab);
  const rows=sh.getUsedRange().values;
  for(let i=1;i<rows.length;i++)if(names.has(rows[i][0]))sh.getRange(`B${i+1}`).values=[[names.get(rows[i][0])]];
 }
 for(const tab of ['Source exceptions','Roster review'])review.worksheets.getItem(tab).getRange('B1').values=[[names.get('VNHCE')]];
 review.worksheets.getItem('Roster review').getRange('C1').values=[[names.get('VNHCF')]];
 const front=review.worksheets.getItem('Review');
 front.getRange('C19').values=[[String(front.getRange('C19').values[0][0]).replace('Country employee ID',names.get('VNHCE'))]];
 for(const tab of ['Time','Monthly adjustments'])monthly.worksheets.getItem(tab).getRange('A1:B1').values=[[names.get('VNHCE'),names.get('VNHCF')]];
 const guide=monthly.worksheets.getItem('Instructions');
 guide.getRange('B5').values=[[String(guide.getRange('B5').values[0][0]).replace('Country employee ID',names.get('VNHCE')).replace('Employee name',names.get('VNHCF'))]];
 // Header cell edits do not refresh imported table-column metadata in this
 // runtime. Refresh only affected table objects, retaining their
 // ranges, names and presentation so Excel has one consistent header name.
 for(const [book,tabs]of [[review,['Source exceptions','Roster review']],[monthly,['Time','Monthly adjustments']]])for(const tab of tabs){
  const sh=book.worksheets.getItem(tab);
  if(sh.tables.items.length===0)continue;
  if(sh.tables.items.length!==1)throw Error(`Review table layout changed on ${tab}`);
  const metadata=await book.inspect({kind:'table',sheetId:tab,maxChars:2000,tableMaxRows:0,tableMaxCols:0});
  const ref=metadata.ndjson.split('\n').map(s=>{try{return JSON.parse(s)}catch{return {}}}).find(t=>t.kind==='table'&&t.sheet===tab);
  if(!ref?.address)throw Error(`Cannot inspect the table range on ${tab}`);
  for(const old of [...sh.tables.items]){
   const tableName=old.name;
   const props={style:old.style,showHeaders:old.showHeaders,showTotals:old.showTotals,showBandedColumns:old.showBandedColumns,showFilterButton:old.showFilterButton};
   old.delete();
   const updated=sh.tables.add(ref.address,props.showHeaders,tableName);
   updated.style=props.style;
   updated.showTotals=props.showTotals;updated.showBandedColumns=props.showBandedColumns;updated.showFilterButton=props.showFilterButton;
  }
 }
 for(const wb of books)wb.recalculate();
 if(front.getRange('D18').values[0][0]!=='Approved'||front.getRange('C30').values[0][0]!==10)throw Error('Preserve the approved roster and pending decisions');
}
for(const [wb,tab,range,label]of [[review,'Payroll rules','A1:D8','rules'],[review,'Contract components','A1:D8','contracts'],[monthly,'Time','A1:F6','time']]){
 const img=await wb.render({sheetName:tab,range,scale:1.2,format:'png'});
 await fs.writeFile(`${workDir}/labels-${mode==='preview'?'before':'after'}-${label}.png`,new Uint8Array(await img.arrayBuffer()));
}
if(mode!=='preview')for(let i=0;i<books.length;i++){
 console.log((await books[i].inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!',options:{useRegex:true,maxResults:5},maxChars:500})).ndjson);
 await(await SpreadsheetFile.exportXlsx(books[i])).save(`${outputDir}/${files[i]}`);
}
console.log(JSON.stringify({mode,files}));
