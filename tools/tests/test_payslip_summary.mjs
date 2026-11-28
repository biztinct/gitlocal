import fs from 'node:fs';
import assert from 'node:assert/strict';
import { test } from 'node:test';

const source = fs.readFileSync(new URL('../../pb_payslip/static/src/js/pay_summary.js', import.meta.url), 'utf8');
const { paySummary, statementMoney, statementChange } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const summary = (gross, deductions, net, extra = {}) => paySummary({gross, deductions_total: deductions, net, ...extra});

test('the summary splits gross into exact proportions, without a gross segment', () => {
    const actual = summary(3600, 1000, 2600);
    assert.equal(actual.canSplit, true);
    assert.ok(Math.abs(actual.deductionPercent - 27.77777777777778) < 1e-12);
    assert.equal(actual.deductionPercent + actual.netPercent, 100);
});
test('tiny, zero and large deductions retain their actual share', () => {
    assert.equal(summary(100000, 1, 99999).deductionPercent, .001);
    assert.equal(summary(100, 0, 100).deductionPercent, 0);
    assert.equal(summary(100, 90, 10).deductionPercent, 90);
    assert.equal(summary(100, 100, 0).canSplit, true);
});
test('refunds, advances, zero gross and negative pay use calculation rows', () => {
    assert.equal(summary(100, -20, 120).canSplit, false);
    assert.equal(summary(100, 10, 60, {adjustment: 30}).canSplit, false);
    assert.equal(summary(0, 0, 0).canSplit, false);
    assert.equal(summary(100, 150, -50).canSplit, false);
    assert.equal(summary(-100, -10, -90).canSplit, false);
});
test('a gap, nonfinite input or net above gross never creates a fake split', () => {
    assert.equal(summary(100, 10, 89).canSplit, false);
    assert.equal(summary(100, NaN, 90).canSplit, false);
    assert.equal(summary(100, 0, 100.001).canSplit, false);
    assert.equal(summary(100.10, 10.01, 90.09, {currency_rounding: .01}).canSplit, true);
});
test('exact currency amounts retain cents and large integer values', () => {
    assert.equal(statementMoney(123456789, {currency:'Rp',currency_precision:0}), 'Rp123,456,789');
    assert.equal(statementMoney(12908.25, {currency:'S$',currency_precision:2}), 'S$12,908.25');
    assert.equal(statementMoney(0, {currency:'Rp',currency_precision:0}), 'Rp0');
});
test('calculation signs explain charges, refunds and credits', () => {
    const data = {currency:'S$',currency_precision:2};
    assert.equal(statementChange(-1250.25, data), '−S$1,250.25');
    assert.equal(statementChange(1250.25, data), '+S$1,250.25');
    assert.equal(statementChange(0, data), 'S$0');
    assert.equal(statementMoney(-1250.25, data), '−S$1,250.25');
});
