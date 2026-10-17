import fs from 'node:fs';
import assert from 'node:assert/strict';

const source = fs.readFileSync(new URL('../../pb_formula_studio/static/src/js/mapping/component_focus.js', import.meta.url), 'utf8');
const { componentJourneyScope: scope } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const rows = new Map([
    ['s:1', { id: 's:1', label: 'Salary' }], ['s:2', { id: 's:2', label: 'Other salary' }],
    ['s:3', { id: 's:3', label: 'Calculated contribution' }],
    ['file:salary', {}], ['output:salary', {}], ['record:salary', {}], ['unrelated', {}],
]);
const cardOf = new Map([
    ['s:1', 'scheme'], ['s:2', 'scheme'], ['s:3', 'scheme'],
    ['file:salary', 'feed'], ['output:salary', 'transform'], ['record:salary', 'record'],
    ['unrelated', 'unrelated-card'],
]);
const nb = new Map();
for (const [a, b] of [['s:1', 'output:salary'], ['output:salary', 'file:salary'],
    ['s:1', 'record:salary'], ['s:2', 'file:salary']]) {
    nb.set(a, [...(nb.get(a) || []), b]); nb.set(b, [...(nb.get(b) || []), a]);
}
const index = { rows, cardOf, nb };
const contains = [{from: 'system', to: 'feed'}, {from: 'organisation', to: 'system'}];
const focused = scope(index, 1, contains);
assert.equal(focused.target.label, 'Salary');
assert.deepEqual([...focused.rowIds].sort(), ['file:salary', 'output:salary', 'record:salary', 's:1']);
assert.ok(!focused.rowIds.has('s:2'), 'A shared source must not reveal another pay component');
assert.ok(!focused.cardIds.has('unrelated-card'));
assert.ok(focused.cardIds.has('organisation'), 'Containing systems remain visible');
assert.deepEqual([...scope(index, 3, contains).rowIds], ['s:3'], 'Calculated values remain visible without fake mapping wires');
assert.equal(scope(index, 999, contains).rowIds.size, 0, 'Stale component IDs must not show another component');
assert.equal(rows.size, 7, 'Focusing does not mutate the payload');

// Exercise the real board's view getters as well as graph traversal. This catches
// folded calculated rows, hidden lanes and stale wires after changing the scope.
const boardSource = fs.readFileSync(new URL('../../pb_formula_studio/static/src/js/mapping/journey_board.js', import.meta.url), 'utf8')
    .replace(/^import [\s\S]*?from ["'][^"']+["'];\n/gm, '');
const stubs = `class Component {}\nconst _t = s => s;\n${source}\n`;
const { JourneyBoard } = await import('data:text/javascript;base64,' + Buffer.from(stubs + boardSource).toString('base64'));
const board = Object.create(JourneyBoard.prototype);
const salary = rows.get('s:1'), other = rows.get('s:2'), calculated = rows.get('s:3');
board.props = { data: { config: {id: 1}, lanes: {
    scheme: [{id: 'scheme', kind: 'scheme', rows: [salary, other], folded: {rows: [calculated]}}],
    feeds: [{id: 'feed', rows: [{id: 'file:salary'}]}, {id: 'unrelated-card', rows: [{id: 'unrelated'}]}],
    transforms: [{id: 'transform', rows: [{id: 'output:salary'}]}],
    source: [{id: 'record', rows: [{id: 'record:salary'}]}],
    systems: [{id: 'system', rows: []}],
}, contains: [{from: 'system', to: 'feed'}], links: [
    {a: 's:1', b: 'output:salary'}, {a: 'output:salary', b: 'file:salary'},
    {a: 's:2', b: 'file:salary'}, {a: 's:1', b: 'record:salary'},
] }};
board.ui = { componentId: 1, q: '', open: {}, folded: false };
assert.deepEqual(board.rowsOf(board.cardsFor('scheme')[0]), [salary]);
assert.equal(board.cardsFor('feeds').length, 1);
assert.equal(board.drawn.some(w => w.rows.has('s:2')), false, 'Hidden components cannot leave ghost wires');
board.ui.componentId = 3;
assert.deepEqual(board.lanes.map(l => l.id), ['scheme']);
assert.equal(board.isOpen(board.cardsFor('scheme')[0]), true);
assert.deepEqual(board.foldedRowsOf(board.cardsFor('scheme')[0]), [calculated]);
assert.equal(board.focusedCalculated, true);
assert.equal(board.drawn.length, 0);
board._animate = () => {};
board.qRef = {el: null};
board.showAllComponents();
assert.equal(board.matches, null);
assert.equal(board.cardsFor('feeds').length, 2);
assert.equal(board.rowsOf(board.cardsFor('scheme')[0]).length, 2);
console.log('19 component-mapping focus regression checks passed');
