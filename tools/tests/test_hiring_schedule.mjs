import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import vm from 'node:vm';
import { test } from 'node:test';

// Execute the shipped board and scorecard patch, with only Odoo services mocked.
const root = resolve(import.meta.dirname, '../..');
const context = vm.createContext({
    Component: class {}, PbHiringSetup: class {}, _t: (s) => s,
    registry: { category: () => ({ add() {} }) },
});
for (const file of ['web/static/src/core/utils/patch.js',
    'pb_hiring/static/src/js/hiring_board.js', 'pb_hiring/static/src/js/hiring_p5.js']) {
    const source = readFileSync(resolve(root, file), 'utf8')
        .replace(/^import .*;\n/gm, '').replace(/^export /gm, '');
    vm.runInContext(file.endsWith('hiring_p5.js') ? `{${source}\n}` : source,
        context, { filename: file });
}
const Board = vm.runInContext('PbHiringBoard', context);
const role = { id: 12, steps: [{ id: 4, name: 'Discussion' }],
    panel_people: [{ id: 8, name: 'Panel One', fold: 'panel one' }] };
function board(drawer = null) {
    const b = new Board();
    b.state = { cand: { id: 7, name: 'Candidate', requisition_id: 12 }, drawer,
        scheduling: null, view: 'offers' };
    b.calls = []; b.errors = []; b.warnings = [];
    b.fail = (e) => b.errors.push(e);
    b.notif = { add: (s) => b.warnings.push(s) };
    b.orm = { call: async (model, method, args) => {
        b.calls.push({ method, args });
        if (method === 'get_candidate') return { id: args[0], requisition_id: 12 };
        if (method === 'get_requisition') return role;
        if (method === 'get_schedule_defaults') return { scorecards: [{ id: 3 }], scorecard_id: 3 };
        throw Error(method);
    } };
    return b;
}
const candidate = { id: 7, name: 'Candidate' };

test('Offers without a role opens with candidate stages, panel and scorecard', async () => {
    const b = board();
    await b.startSchedule(candidate);
    assert.equal(b.state.drawer, null);
    assert.equal(b.state.view, 'offers');
    assert.equal(b.state.scheduling.requisition_id, 12);
    assert.equal(b.state.scheduling.steps, role.steps);
    assert.equal(b.panelChoices[0].id, 8);
    assert.equal(b.panelName(8), 'Panel One');
    assert.equal(b.state.scheduling.scorecard_id, '3');
    assert.equal(b.errors.length, 0);
});
test('A previously viewed role cannot supply stages or panel', async () => {
    const previous = { id: 99, steps: [{ id: 90 }], panel_people: [{ id: 91 }] };
    const b = board(previous);
    await b.startSchedule(candidate);
    assert.equal(b.state.drawer, previous);
    assert.equal(b.state.scheduling.steps[0].id, 4);
    assert.equal(b.panelName(91), '');
    b.state.panelQ = 'one';
    assert.equal(b.panelChoices.length, 1);
});
test('Role board entry works without an open candidate drawer', async () => {
    const b = board(role); b.state.cand = null;
    await b.startSchedule(candidate);
    assert.equal(b.calls[0].method, 'get_candidate');
    assert.equal(b.state.scheduling.requisition_id, 12);
});
test('Loading failure leaves scheduler closed and reports the error', async () => {
    const b = board(); b.orm.call = async () => { throw Error('Denied'); };
    await b.startSchedule(candidate);
    assert.equal(b.state.scheduling, null);
    assert.equal(b.errors[0].message, 'Denied');
});
test('Candidate without a request gets an actionable warning', async () => {
    const b = board(); b.state.cand.requisition_id = false;
    await b.startSchedule(candidate);
    assert.equal(b.state.scheduling, null);
    assert.equal(b.warnings.length, 1);
    assert.equal(b.calls.length, 0);
});
test('Cancelling during load does not reopen the scheduler', async () => {
    const b = board(); let finish;
    b.orm.call = () => new Promise(resolve => { finish = resolve; });
    const pending = b.startSchedule(candidate);
    b.cancelSchedule(); finish(role); await pending;
    assert.equal(b.state.scheduling, null);
});
test('Save uses the candidate role, selected stage and panel from Offers', async () => {
    const b = board({ id: 99 });
    await b.startSchedule(candidate);
    b.togglePanel(8); b.state.scheduling.step_id = '4';
    b.act = async (verb, payload) => { b.saved = { verb, payload }; return { id: 10 }; };
    b.openCand = async () => {};
    await b.saveSchedule();
    assert.equal(b.saved.verb, 'schedule');
    assert.equal(b.saved.payload.requisition_id, 12);
    assert.equal(b.saved.payload.applicant_id, 7);
    assert.equal(b.saved.payload.step_id, '4');
    assert.equal(b.saved.payload.panel_employee_ids[0], 8);
    assert.equal(b.saved.payload.scorecard_id, 3);
    assert.equal(b.state.scheduling, null);
});
