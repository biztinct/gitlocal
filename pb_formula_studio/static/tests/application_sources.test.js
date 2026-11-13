/** @odoo-module **/
import { expect, test } from '@odoo/hoot';
import { sourceChoices } from '@pb_formula_studio/js/application_sources';

const options = [
    {key:'employee.birthday',label:'Birthday',owner:'Employee profile',unit:'date'},
    {key:'period.paid_day_equivalents',label:'Paid days',owner:'Time off',unit:'days'},
    {key:'contract.wage',label:'Wage',owner:'Employment contract',unit:'monetary'},
    {key:'period.input.BONUS',component_code:'BONUS',label:'Bonus',owner:'Monthly adjustments',unit:'money'},
    {key:'period.input.OTHER',component_code:'OTHER',label:'Other',owner:'Monthly adjustments',unit:'money'},
    {key:'history.ytd.BONUS',label:'Bonus year to date',owner:'Payroll history',unit:'money'},
    {key:'pending.domain.BONUS',label:'Unreviewed',owner:'Application records',unit:'money',requires_domain_review:true},
];
const row = {code:'BONUS',kind:'money',key:'period.input.BONUS',owner:'Monthly adjustments'};

test('a bonus suggests money sources without unrelated employee fields or historical totals', () => {
    expect(sourceChoices(options,row).map(o=>o.key)).toEqual(['period.input.BONUS','contract.wage']);
});
test('advanced browsing retains approval and same-component monthly restrictions', () => {
    const keys=sourceChoices(options,row,'',true).map(o=>o.key);
    expect(keys.includes('employee.birthday')).toBe(true);
    expect(keys.includes('history.ytd.BONUS')).toBe(true);
    expect(keys.includes('pending.domain.BONUS')).toBe(false);
    expect(keys.includes('period.input.OTHER')).toBe(false);
});
test('current sources remain visible for review even with an unusual component type', () => {
    expect(sourceChoices(options,{...row,key:'employee.birthday'},'Birthday').map(o=>o.key)).toEqual(['employee.birthday']);
});
