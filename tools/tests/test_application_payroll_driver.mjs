import assert from 'node:assert/strict';
import { test } from 'node:test';
import { runPayroll } from '../../pb_payrun_wizard/static/src/js/run_driver.js';

test('application route carries scheme, scope and certification through chunked compute', async () => {
    const calls = [];
    const payload = { formula_config_id: 4760, date_start: '2026-11-01', date_end: '2026-11-30',
        spreadsheet_skipped: true, application_certifications: { channels: { leave: true } },
        application_certification_reason: 'Reviewed test records' };
    const orm = { silent: { call: async (model, method, args) => {
        calls.push({ model, method, args });
        if (method === 'sync_plan') { return { steps: [] }; }
        if (method === 'prepare_run') {
            assert.deepEqual(args[0], payload);
            return { run_id: 99, name: 'Test', ...payload, emp_ids: [11, 12] };
        }
        if (method === 'compute_batch') {
            assert.equal(args[0].formula_config_id, 4760);
            assert.deepEqual(args[0].emp_ids, [11, 12]);
            assert.equal(args[0].run_id, 99);
            return { computed: 2, exceptions: [] };
        }
        if (method === 'get_summary') { return { count: 2 }; }
        throw new Error(`Unexpected ${method}`);
    } } };
    const answer = await runPayroll(orm, payload);
    assert.equal(answer.stage, 'done');
    assert.equal(answer.computed, 2);
    assert.deepEqual(calls.map((c) => c.method), ['sync_plan', 'prepare_run', 'compute_batch', 'get_summary']);
});

test('application blockers stop orchestration before any payslips are computed', async () => {
    const calls = [];
    const preview = { ok: false, blockers: [{ code: 'PAIDDAYS', reason: 'Leave not reviewed' }] };
    const orm = { silent: { call: async (model, method) => {
        calls.push(method);
        if (method === 'sync_plan') { return { steps: [] }; }
        if (method === 'prepare_run') { return { blocked: true, application_preflight: preview }; }
        throw new Error('Blocked payroll must not reach ' + method);
    } } };
    const answer = await runPayroll(orm, { spreadsheet_skipped: true, formula_config_id: 4760 });
    assert.equal(answer.stage, 'blocked');
    assert.equal(answer.prep.application_preflight, preview);
    assert.deepEqual(calls, ['sync_plan', 'prepare_run']);
});
