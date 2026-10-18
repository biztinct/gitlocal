// Run with: node tools/tests/test_payslip_document_geometry.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
const source = fs.readFileSync(new URL('../../pb_formula_studio/static/src/js/payslip_document_tools.js', import.meta.url), 'utf8');
const { detectDocumentCells, documentIssues, documentField } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const width = 600, height = 400;
const pixels = new Uint8Array(width * height * 4).fill(255);
function black(x, y) { const i = (y * width + x) * 4; pixels[i] = pixels[i + 1] = pixels[i + 2] = 0; }
for (const y of [40, 70, 110, 150]) for (let x = 40; x <= 560; x++) black(x, y);
for (let y = 40; y <= 150; y++) for (const x of [40, 560]) black(x, y);
for (let y = 70; y <= 150; y++) for (const x of [190, 300, 450]) black(x, y);
const items = [{ text: 'EMPLOYEE INFORMATION', x: 50, y: 60, font_size: 10 },
    { text: 'Employee name', x: 50, y: 90, font_size: 10 },
    { text: 'Employee ID', x: 310, y: 90, font_size: 10 },
    { text: 'Actual monthly salary', x: 50, y: 130, font_size: 10 },
    { text: 'Source Person', x: 200, y: 90, font_size: 10 },
    { text: 'Final net pay', x: 310, y: 130, font_size: 10 }];
const found = detectDocumentCells(pixels, width, height, width, height, items);
assert.equal(found.fields.length, 4, 'two independent label/value pairs survive on each row');
assert.equal(found.cellCount, 9, 'merged heading has one cell');
assert.ok(found.fields.every(field => field.binding === 'blank'), 'geometry alone cannot authorize payroll mappings');
assert.ok(found.fields.every(field => !field.text.includes('Source Person')), 'a populated sample is covered, never copied as a live value');
assert.ok(found.fields[0].x > 190 && found.fields[1].x > 450);
assert.equal(documentIssues({ pages: [{ width, height, fields: found.fields }] }).length, 4);
const empty = detectDocumentCells(new Uint8Array(width * height * 4).fill(255), width, height, width, height, []);
assert.equal(empty.fields.length, 0, 'borderless/scanned input remains eligible for manual placement');
const field = documentField('manual-1', 'Manual field', 580, 390, 100, 30);
field.binding = 'text';
assert.equal(documentIssues({ pages: [{ width, height, fields: [field] }] }).length, 1, 'out-of-page placements are reported');
console.log('7 geometry/placement checks passed');
