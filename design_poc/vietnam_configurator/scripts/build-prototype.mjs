import { readFileSync, writeFileSync } from 'node:fs';
let html = readFileSync('src/template.html', 'utf8');
for (const [key, file] of Object.entries({CSS:'style.css', DATA:'data.js', ENGINE:'engine.js', UI:'ui.js'})) html = html.replace(`/*__${key}__*/`, () => readFileSync(`src/${file}`, 'utf8'));
writeFileSync('public/prototype.html', html);
