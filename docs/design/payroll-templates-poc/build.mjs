import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
const base=new URL('./',import.meta.url);
const read=name=>fs.readFileSync(new URL(name,base),'utf8');
let html=read('index.html');
const font=fs.readFileSync(new URL('InterVariable.woff2',base)).toString('base64');
const css=read('styles.css').replace('url("InterVariable.woff2")','url("data:font/woff2;base64,'+font+'")');
html=html.replace('<link rel="stylesheet" href="styles.css">',()=>'<style>\n'+css+'\n</style>');
for(const name of ['vendor/xlsx.full.min.js','data.js','workbooks.js','app.js']){
  const js=read(name).replace(/<\/script/gi,'<\\/script');
  html=html.replace('<script src="'+name+'"></script>',()=>'<script>\n'+js+'\n</script>');
}
html=html.replace('<head>','<head>\n<!-- Self-contained Payobook design preview. Fictional data only. Inter: SIL OFL. SheetJS: Apache 2.0; licenses included with source. -->');
const target=new URL('../payroll-templates-poc.html',base);
fs.writeFileSync(target,html);
console.log('Built '+fileURLToPath(target)+' ('+Buffer.byteLength(html)+' bytes)');
