process.on('uncaughtException', e => { console.error(e.message); process.exit(1); });
import fs from 'node:fs';
import assert from 'node:assert/strict';

const read = name => fs.readFileSync(new URL(`../../pb_formula_studio/static/src/js/mapping/${name}.js`, import.meta.url), 'utf8')
    .replace(/^import [\s\S]*?from ["'][^"']+["'];\n/gm, '');
const common = `class Component {}\nconst _t = (s,...args) => args.reduce((v,a)=>v.replace('%s',a),s);\n`;
const {MappingCanvas} = await import('data:text/javascript;base64,' + Buffer.from(common + read('mapping_canvas')).toString('base64'));
const canvas = Object.create(MappingCanvas.prototype);
canvas.props = {leftItems: [], rightItems: [
    {id: 1, label: 'Salary', meta: {type: 'input'}},
    {id: 2, label: 'Factor', meta: {type: 'constant', collapsedGroup: 'Constants', constantValue: 12}},
], wires: []};
canvas.ui = {rightGroupOpen: false, q: {right: ''}, qa: {right: ''}, f: {right: 'all'}, focusSide: 'left'};
canvas._schedule = () => {};
assert.deepEqual(canvas.rightView.map(i=>i.id), [1]);
assert.equal(canvas.rightGroupedView.length, 1);
assert.equal(canvas.isFilteredOut('right', 2), true);
canvas.toggleRightGroup();
assert.deepEqual(canvas.rightView.map(i=>i.id), [1,2]);
canvas.toggleRightGroup();
assert.deepEqual(canvas.rightView.map(i=>i.id), [1]);

const stubs = `const registry={category:()=>({add:()=>{}})};\nclass HubBackChip {}\nclass ConfirmationDialog {}\nclass MappingCanvas {}\nclass TransformFlowBoard {}\nclass ConnectionDesk {}\nclass JourneyBoard {}\nclass ComponentTreatmentBoard {}\nclass RuleComposer {}\n`;
const {MappingStudio} = await import('data:text/javascript;base64,' + Buffer.from(common + stubs + read('mapping_studio')).toString('base64'));
const studio = Object.create(MappingStudio.prototype);
const fixed = {id: 2, label: 'Factor', meta: {collapsedGroup: 'Constants', constantValue: 0, constantDisplay: '0'}};
studio.state = {extraCols: [], mode: 'import', configId: 1, batchId: false, data: {left:[{id:'c:Factor',label:'Factor column'}],right:[fixed]}};
const calls = [];
let dialog;
studio.orm = {call: async (...args) => {calls.push(args);return {ok:true,converted_constant:true}}};
studio.dialog = {add: (_type, props) => {dialog=props}};
studio.notif = {add:()=>{}};
studio.load = async () => {calls.push(['reload'])};
await studio.draw('c:Factor',2);
assert.equal(calls.length,0,'Opening the confirmation must make no write call');
assert.ok(dialog.body.includes('0'),'The reviewed fixed value, including zero, must be visible');
assert.equal(dialog.confirmLabel,'Change to input and map');
assert.equal(dialog.cancelLabel,'Cancel');
dialog.cancel();
assert.equal(calls.length,0);
await dialog.confirm();
assert.equal(calls[0][1],'import_mapping_use_constant');
assert.deepEqual(calls[0][2],[1,false,'c:Factor',2,0]);
assert.equal(calls[1][0],'reload');
console.log('Constant group, no-write confirmation/cancel, and explicit conversion checks passed');

canvas.props.blockedLeftKeys = ['Age', 'People|Age', 'C'];
canvas.props.canAddLeft = true;
const added = [];
canvas.props.onAddLeft = value => added.push(value);
for (const key of ['Age','age','People|Age','C']) {
    canvas.ui.q.left = key;
    assert.equal(canvas.showAddLeft,false);
    canvas.addLeft();
}
assert.deepEqual(added,[],'A calculated source cannot be restored through the Add column shortcut');
canvas.ui.q.left = 'New input';
assert.equal(canvas.showAddLeft,true);
canvas.addLeft();
assert.deepEqual(added,['New input']);
console.log('Calculated-source aliases cannot be re-added from destination search');
