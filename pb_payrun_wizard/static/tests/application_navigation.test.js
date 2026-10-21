/** @odoo-module **/
import { expect, test } from '@odoo/hoot';
import { PayrunWizard } from '@pb_payrun_wizard/js/payrun_wizard';

test('source settings carry period and scope, without treating reviews as approvals on return', async () => {
    let opened;
    const fake = {sheetConfigId:42,orm:{call:async()=>({params:{config_id:42}})},
        action:{doAction:async action=>{opened=action;}},
        applicationPayload:()=>({name:'November',date_start:'2026-11-01',date_end:'2026-11-30',employee_ids:[7],statuses:['active'],application_certifications:{channels:{leave:true}}})};
    await PayrunWizard.prototype.openApplicationSettings.call(fake);
    expect(opened.params.return_payrun.formula_config_id).toBe(42);
    expect(opened.params.return_payrun.date_start).toBe('2026-11-01');
    expect(opened.params.return_payrun.employee_ids).toEqual([7]);
    expect('application_certifications' in opened.params.return_payrun).toBe(false);
});
test('issue records open over the current review and trigger a fresh check on close', async () => {
    let opened,closed=false;
    const fake={orm:{call:async()=>({res_model:'hr.leave',res_id:9})},
        action:{doAction:async(action,options)=>{opened=action;await options.onClose();}},
        applicationPayload:()=>({}),previewApplicationData:async()=>{closed=true;}};
    await PayrunWizard.prototype.openApplicationIssue.call(fake,{kind:'leave',code:'PAID'},7);
    expect(opened.target).toBe('new');
    expect(opened.res_id).toBe(9);
    expect(closed).toBe(true);
});
