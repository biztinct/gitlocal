/* Browser-only demo export and review model. No database writes or API calls. */
window.PayrollWorkbooks = (function () {
  'use strict';
  const D=window.PayrollDemo, X=window.XLSX;
  function blank(v){return v===null||v===undefined||typeof v==='string'&&v.trim()==='';}
  function same(a,b){if(blank(a)&&blank(b))return true;return String(a)===String(b);}
  function monthValue(ctx,r,f) {
    if(f.context)return r[f.key];
    const row=(ctx.monthly||{})[r.id]||{};
    if(Object.prototype.hasOwnProperty.call(row,f.key))return row[f.key];
    return f.key==='standardDays'?D.workingDays(ctx.period):'';
  }
  function sheetFields(ctx,tab){
    if(ctx.kind==='employee')return D.masterFields;
    const by=Object.fromEntries(D.fields(ctx.country).map(function(f){return [f.key,f];}));
    return [{key:'id',label:'Employee ID',type:'text',locked:true},{key:'name',label:'Employee name',type:'text',locked:true}].concat(ctx.layout[tab].map(function(key){return Object.assign({},by[key],{locked:!!by[key].context});}));
  }
  function xmlEscape(value){return String(value).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
  function styleExport(bytes,defs) {
    const c=X.CFB.read(new Uint8Array(bytes),{type:'array'});
    const decoder=new TextDecoder(),encoder=new TextEncoder();
    function replace(path,transform){const full=c.FullPaths.find(function(p){return p.endsWith('/'+path);});const file=c.FileIndex[c.FullPaths.indexOf(full)];if(!file)throw Error('Workbook part missing: '+path);X.CFB.utils.cfb_add(c,full,encoder.encode(transform(decoder.decode(file.content))));}
    const style='<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      +'<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
      +'<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00;[Red](#,##0.00);0"/></numFmts>'
      +'<fonts count="3"><font><sz val="11"/><name val="Calibri"/><color rgb="FF1B1733"/></font><font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font><font><sz val="11"/><name val="Calibri"/><color rgb="FF64748B"/></font></fonts>'
      +'<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF5A4BB0"/><bgColor indexed="64"/></patternFill></fill></fills>'
      +'<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
      +'<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5">'
      +'<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
      +'<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>'
      +'<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyProtection="1"><protection locked="0"/></xf>'
      +'<xf numFmtId="49" fontId="2" fillId="0" borderId="0" xfId="0" applyProtection="1"><protection locked="1"/></xf>'
      +'<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyProtection="1"><protection locked="0"/></xf>'
      +'</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>';
    replace('xl/styles.xml',function(){return style;});
    defs.forEach(function(fields,i){
      replace('xl/worksheets/sheet'+(i+1)+'.xml',function(xml){
        xml=xml.replace(/<c\b([^>]*)>/g,function(all,attrs){
          const ref=(attrs.match(/\br="([A-Z]+)(\d+)"/)||[]);
          if(!ref[1])return all;
          const col=X.utils.decode_col(ref[1]),row=Number(ref[2]);
          const f=fields[col],s=row===1?1:f&&f.locked?3:f&&f.type==='number'?4:2;
          return '<c'+attrs.replace(/\s+s="[^"]*"/g,'')+' s="'+s+'">';
        });
        const views='<sheetViews><sheetView workbookViewId="0"><pane xSplit="2" ySplit="1" topLeftCell="C2" activePane="bottomRight" state="frozen"/><selection pane="bottomRight" activeCell="C2" sqref="C2"/></sheetView></sheetViews>';
        if(/<sheetViews>/.test(xml))xml=xml.replace(/<sheetViews>[\s\S]*?<\/sheetViews>/,views);
        else xml=xml.replace('<sheetData>',views+'<sheetData>');
        xml=xml.replace(/<row\b([^>]*)>/g,function(all,a){const r=(a.match(/\br="(\d+)"/)||[])[1];return '<row'+a.replace(/\s+(?:ht|customHeight)="[^"]*"/g,'')+' ht="'+(r==='1'?34:25)+'" customHeight="1">';});
        return xml.replace('</sheetData>','</sheetData><sheetProtection sheet="1" objects="1" scenarios="1" formatCells="0" formatColumns="0" formatRows="0" insertRows="0" deleteRows="0" sort="0" autoFilter="0" selectLockedCells="0" selectUnlockedCells="0"/>');
      });
    });
    return new Uint8Array(X.CFB.write(c,{type:'array',fileType:'zip',compression:true}));
  }
  function build(ctx,overrides) {
    const wb=X.utils.book_new(),tabs=ctx.kind==='employee'?['Employee records']:['Time','Monthly adjustments'],defs=[],maps={};
    tabs.forEach(function(name,i){
      const f=sheetFields(ctx,ctx.kind==='employee'?'employee':i===0?'time':'adjustments');defs.push(f);maps[name]=f.map(function(v){return {key:v.key,label:v.label};});
      const rows=[f.map(function(v){return v.label;})].concat(ctx.records.map(function(r){return f.map(function(v){return ctx.kind==='employee'?r[v.key]:v.key==='id'||v.key==='name'?r[v.key]:monthValue(ctx,r,v);});}));
      if(overrides&&overrides[name])overrides[name].forEach(function(edit){const idx=f.findIndex(function(v){return v.key===edit.key;});if(idx>=0&&rows[edit.row+1])rows[edit.row+1][idx]=edit.value;});
      const ws=X.utils.aoa_to_sheet(rows);
      ws['!cols']=f.map(function(v){return {wch:Math.max(v.key==='email'?29:18,Math.min(34,v.label.length+4))};});
      ws['!autofilter']={ref:ws['!ref']};
      f.forEach(function(v,j){const cell=ws[X.utils.encode_cell({r:0,c:j})];cell.c=[{a:'Payobook',t:(v.locked?'Read-only identity or saved context. Keep this value unchanged. ':'Editable input. Blank = keep the current value; 0 = set the value to zero. ')+'Field: '+v.key+(v.unit?' · '+v.unit:'')}];});
      X.utils.book_append_sheet(wb,ws,name);
    });
    const meta=[['Template kind',ctx.kind],['Country',ctx.country],['Currency',D.definitions[ctx.country].currency],['Pay month',ctx.kind==='monthly'?ctx.period:''],['Layout version',ctx.version],['Column map',JSON.stringify(maps)],['Exported at',new Date().toISOString()]];
    ctx.records.forEach(function(r){meta.push(['Record snapshot '+r.id,JSON.stringify(r)]);});
    X.utils.book_append_sheet(wb,X.utils.aoa_to_sheet(meta),'_Payobook');
    wb.Workbook={Sheets:tabs.map(function(name){return {name:name,Hidden:0};}).concat([{name:'_Payobook',Hidden:2}])};
    wb.Props={Title:'Payobook '+(ctx.kind==='employee'?'employee records':'monthly inputs'),Author:'Payobook',Comments:'Interactive preview with fictional example data.'};
    return styleExport(X.write(wb,{type:'array',bookType:'xlsx',compression:false}),defs);
  }
  function parse(bytes,filename) {
    const wb=X.read(bytes,{type:'array',cellDates:true}),meta={snapshots:{}};
    if(wb.Sheets._Payobook)X.utils.sheet_to_json(wb.Sheets._Payobook,{header:1,defval:null,raw:true}).forEach(function(row){if(String(row[0]).startsWith('Record snapshot ')){try{const r=JSON.parse(row[1]);meta.snapshots[r.id]=r;}catch(ignore){}}else meta[row[0]]=row[1];});
    const sheets={};wb.SheetNames.filter(function(n){return n!=='_Payobook';}).forEach(function(n){sheets[n]=X.utils.sheet_to_json(wb.Sheets[n],{header:1,defval:null,raw:true});});
    return {meta:meta,sheets:sheets,filename:filename};
  }
  function review(file,ctx,resolutions) {
    resolutions=resolutions||{};
    const result={changes:[],issues:[],warnings:[],blanks:0,unchanged:0,emptyRows:0,filename:file.filename,people:new Set(),resolutions:resolutions};
    const meta=file.meta,all=D.fields(ctx.country),lookup=Object.fromEntries(D.masterFields.concat(all).map(function(f){return [f.label,f];}));
    if(meta['Template kind']&&meta['Template kind']!==ctx.kind)result.issues.push({title:'This is the other workbook',detail:'Use the '+(ctx.kind==='employee'?'employee records':'monthly pay inputs')+' workbook for this import.'});
    if(meta.Country&&meta.Country!==ctx.country)result.issues.push({title:'Payroll configuration does not match',detail:'This workbook belongs to '+(D.definitions[meta.Country]||{}).name+'. Download the workbook for '+D.definitions[ctx.country].name+'.'});
    if(ctx.kind==='monthly'&&meta['Pay month']!==ctx.period)result.issues.push({title:'The pay month does not match',detail:'The file is for '+(meta['Pay month']||'an unspecified month')+'. This run is for '+ctx.period+'. Select the correct month or download a fresh workbook.'});
    if(ctx.kind==='monthly'&&Number(meta['Layout version'])!==ctx.version)result.issues.push({title:'The template layout has changed',detail:'Download the latest workbook and transfer your inputs. This prevents columns being read under an older layout.'});
    const names=ctx.kind==='employee'?[file.sheets['Employee records']?'Employee records':Object.keys(file.sheets)[0]]:['Time','Monthly adjustments'];
    const timeIDs=new Set(),adjIDs=new Set();
    names.forEach(function(name,tabIndex){
      const rows=file.sheets[name];if(!rows){result.issues.push({title:'Worksheet missing: '+name,detail:'Keep both monthly worksheet names unchanged.'});return;}
      const heads=rows[0]||[],idCol=heads.indexOf('Employee ID'),emailCol=heads.indexOf('Email');
      if(idCol<0){result.issues.push({title:'Employee ID column is missing',detail:'Keep the Employee ID heading on each worksheet.'});return;}
      const seen=new Set(),allowed=ctx.kind==='employee'?new Set(D.masterFields.map(function(f){return f.key;})):new Set(ctx.layout[tabIndex===0?'time':'adjustments']);
      rows.slice(1).forEach(function(row,rowIndex){
        if(row.every(blank)){result.emptyRows++;return;}
        const id=blank(row[idCol])?'':String(row[idCol]).trim(),at=name+' · row '+(rowIndex+2);
        if(!id){result.issues.push({title:'Employee ID required',detail:at+' has values but no employee identity. Keep Employee ID populated.'});return;}
        if(seen.has(id)){result.issues.push({title:'Duplicate Employee ID: '+id,detail:at+' repeats an employee on the same worksheet. Use one row per employee.'});return;}seen.add(id);
        if(ctx.kind==='monthly')(tabIndex===0?timeIDs:adjIDs).add(id);
        const person=ctx.records.find(function(r){return r.id===id;});
        if(!person){const email=emailCol<0?'':String(row[emailCol]||'');const match=ctx.records.find(function(r){return r.email===email;});result.issues.push({title:match?'Employee ID was edited':'Employee ID not found: '+id,detail:at+'. '+(match?'Keep the original Employee ID '+match.id+'.':'Use an existing employee ID, including its leading zeros. New people are created through employee onboarding.')});return;}
        if(ctx.kind==='employee'&&emailCol>=0&&!blank(row[emailCol])&&String(row[emailCol])!==person.email)result.issues.push({title:'Email is read-only',detail:person.name+' · '+at+'. Restore the original email '+person.email+'.'});
        heads.forEach(function(label,j){
          const f=lookup[label];if(!f||f.key==='id'||f.key==='email')return;
          const raw=row[j];if(blank(raw)){result.blanks++;return;}
          if(ctx.kind==='monthly'&&(f.context||f.key==='name')){
            const original=(meta.snapshots[person.id]||person)[f.key];
            if(!same(original,raw))result.issues.push({title:'Saved context is read-only',detail:f.label+' for '+person.name+' can be changed in the employee workbook. Monthly files do not update employee records.'});
            else result.unchanged++;return;
          }
          if(!allowed.has(f.key)){result.warnings.push('Ignored column: '+label);return;}
          let value=raw;
          if(f.type==='number'){value=typeof raw==='number'?raw:Number(String(raw).replace(/,/g,'').trim());if(!Number.isFinite(value)){result.issues.push({title:'A numeric value is required',detail:person.name+' · '+f.label+' · '+at+'. Enter a number, 0, or leave the cell blank.'});return;}}
          else if(f.key==='joinDate'){
            value=raw instanceof Date?raw.getFullYear()+'-'+String(raw.getMonth()+1).padStart(2,'0')+'-'+String(raw.getDate()).padStart(2,'0'):String(raw).trim();
            if(!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(Date.parse(value))){result.issues.push({title:'A date is required',detail:person.name+' · Join date. Use an Excel date or YYYY-MM-DD.'});return;}
          } else value=String(raw);
          const current=ctx.kind==='employee'?person[f.key]:monthValue(ctx,person,f),resolutionKey=id+'|'+f.key;
          if(same(current,value)||resolutions[resolutionKey]==='current'){result.unchanged++;return;}
          const snap=meta.snapshots[person.id];
          if(ctx.kind==='employee'&&snap&&!same(snap[f.key],current)&&resolutions[resolutionKey]!=='incoming'){
            result.issues.push({title:'This value changed after the download',detail:person.name+' · '+f.label+'. The saved record now has a different value. Choose which value to keep before applying.',key:resolutionKey,before:current,incoming:value,field:f.label});return;
          }
          const previous=result.changes.find(function(c){return c.id===id&&c.key===f.key;});
          if(previous){result.issues.push({title:'An input appears in both worksheets',detail:f.label+' for '+person.name+' has more than one supplied value. Keep each input in its configured tab.'});return;}
          result.changes.push({id:id,name:person.name,key:f.key,label:f.label,before:current,after:value,selected:true,tab:name});result.people.add(id);
        });
      });
    });
    if(ctx.kind==='monthly')adjIDs.forEach(function(id){if(!timeIDs.has(id))result.issues.push({title:'Employee missing from Time: '+id,detail:'An adjustment row has no matching Time row. Include the same Employee ID in both tabs.'});});
    result.people=result.people.size;result.warnings=[...new Set(result.warnings)];
    return result;
  }
  return {blank:blank,same:same,monthValue:monthValue,sheetFields:sheetFields,build:build,parse:parse,review:review,xmlEscape:xmlEscape};
})();
