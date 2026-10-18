// Requires jsdom on NODE_PATH. Exercises the real OWL template and event handlers.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const { JSDOM } = createRequire(import.meta.url)('jsdom');
const root = new URL('../../', import.meta.url);
const read = path => fs.readFileSync(new URL(path, root), 'utf8');
const dom = new JSDOM('<!doctype html><body><main></main></body>', {runScripts: 'outside-only', pretendToBeVisual: true});
const { window } = dom;
const errors = [];
window.addEventListener('error', ev => { errors.push(ev.error); ev.preventDefault(); });
window.HTMLCanvasElement.prototype.getContext = () => ({measureText: text => ({width: text.length * 5})});
window.eval(read('web/static/lib/owl/owl.js'));
window.eval(`const {Component, useState, useExternalListener, onWillUnmount} = owl;
${read('pb_formula_studio/static/src/js/payslip_document_tools.js').replaceAll('export function', 'function')}
${read('pb_formula_studio/static/src/js/payslip_document_designer.js').replace(/^import .*;\n/gm, '').replace('export class', 'class')}
window.Designer = PayslipDocumentDesigner; window.makeField = documentField;`);
let saved, closed = 0;
const field = window.makeField('net', 'Net pay', 100, 200, 180, 24);
Object.assign(field, {binding: 'component', rule_id: 1});
const app = new window.owl.App(window.Designer, {
    templates: read('pb_formula_studio/static/src/xml/payslip_document_designer.xml'),
    props: {document: {version: 1, pages: [{width: 612, height: 792, image: '', fields: [field]},
        {width: 420, height: 595, image: '', fields: []}]},
    components: [{id: 1, col: 'A', name: 'Net pay', value: 1234, value_kind: 'money'}],
    meta: {month: '10'}, onSave: async value => {saved = value; return {ok: true};}, onClose: () => closed++},
});
const tick = () => new Promise(resolve => setTimeout(resolve, 30));
await app.mount(window.document.querySelector('main'));
const query = label => window.document.querySelector(`[aria-label="${label}"]`);
const change = async (label, value) => { const el = query(label); el.value = value; el.dispatchEvent(new window.Event('change', {bubbles: true})); await tick(); };
const button = text => [...window.document.querySelectorAll('button')].find(el => el.textContent.trim() === text);
await change('Document zoom', '0.7');
assert.equal(errors.length, 0, 'zoom uses a callable OWL handler');
assert.equal(window.document.querySelector('.ps-document-sheet').style.width, '428.4px');
const preview = window.document.querySelector('.ps-document-toolbar input[type=checkbox]');
preview.click(); await tick();
assert.ok(window.document.querySelector('.ps-document-sheet.preview'), 'preview toggles field decorations');
preview.click(); await tick();
window.document.querySelector('.ps-document-field-list button').click(); await tick();
await change('Field font size', '12');
assert.equal(query('Field font size').value, '12');
await change('Field x', '110');
assert.equal(query('Field x').value, '110');
button('Duplicate').click(); await tick();
assert.equal(window.document.querySelectorAll('.ps-document-field').length, 2);
button('Undo').click(); await tick();
assert.equal(window.document.querySelectorAll('.ps-document-field').length, 1);
button('Redo').click(); await tick();
assert.equal(window.document.querySelectorAll('.ps-document-field').length, 2);
button('Undo').click(); await tick();
await change('Document page', '1');
assert.equal(window.document.querySelectorAll('.ps-document-field').length, 0);
await change('Document page', '0');
window.document.querySelector('.ps-document-field-list button').click(); await tick();
window.document.querySelector('.ps-document-sheet').dispatchEvent(new window.KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true})); await tick();
assert.equal(query('Field x').value, '111', 'keyboard moves the selected field by one PDF point');
await change('Live source', 'blank');
assert.ok(window.document.querySelector('.ps-document-field.unbound'), 'unbound sources remain explicit');
await change('Live source', 'component:1');
assert.equal(window.document.querySelector('.ps-document-field span').textContent, '1,234');
button('Save design').click(); await tick();
assert.equal(saved.pages[0].fields.length, 1);
assert.equal(saved.pages[0].fields[0].x, 111);
assert.equal(closed, 1);
assert.equal(errors.length, 0, 'all real template handlers finish without browser errors');
app.destroy(); window.close();
console.log('16 mounted OWL designer checks passed');
