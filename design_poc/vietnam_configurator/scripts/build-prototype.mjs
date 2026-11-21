import { readFileSync, writeFileSync } from 'node:fs';
let html = readFileSync('src/template.html', 'utf8');
for (const [key, file] of Object.entries({CSS:'style.css', DATA:'data.js', ENGINE:'engine.js', UI:'ui.js'})) html = html.replace(`/*__${key}__*/`, () => readFileSync(`src/${file}`, 'utf8'));
writeFileSync('public/prototype.html', html);
let option2 = readFileSync('src/option2.html', 'utf8');
for (const [key, file] of Object.entries({STYLE2:'option2.css', DATA:'data.js', ENGINE:'engine.js', CORE2:'option2-core.js', UI2:'option2-ui.js', JCORE:'option2-journey-core.js', JOURNEY:'option2-journey.js'})) option2 = option2.replace(`/*__${key}__*/`, () => readFileSync(`src/${file}`, 'utf8'));
writeFileSync('public/option2.html', option2);

writeFileSync('Payroll_Blueprint_Option2.html', option2.replace('href="prototype.html"', 'href="public/prototype.html"'));
writeFileSync('public/IMPLEMENTATION_HANDOFF.md', readFileSync('IMPLEMENTATION_HANDOFF.md', 'utf8'));
