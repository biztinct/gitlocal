/** @odoo-module **/
/**
 * PSCHEME P2a D.2 — "Country of work is now Singapore. Change the pay scheme
 * too?"
 *
 * Every employee form saves through the platform's form controller: the
 * native Full details form and the employee workspace's Pay tab (a projected
 * section of the same form, `pb_form_studio`). One patch on its "after a
 * save" hook covers both. When the save changed Country of work and the
 * person's pay scheme is now of another country (`country_mismatch`, D.1),
 * the shared "Change pay scheme" dialog opens at once, preselected to the
 * scheme that fits, From = the 1st of next month. "Not now" closes it and the
 * amber line stays on the panel, the contract strip and the "Paid by" chip.
 *
 * The server never changes a scheme because a country changed (ledger A7):
 * this only ASKS. Without this module nothing here exists, so nothing asks.
 */
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { loadPersonScheme, openChangePayScheme } from "@pb_scheme_map/js/person_scheme";

export async function askAfterCountryChange(env, orm, dialog, employeeId) {
    let data = null;
    try {
        data = await orm.silent.call("pb.scheme.board", "person_scheme", [Number(employeeId)]);
    } catch {
        return false;           // a question we cannot ask is not asked
    }
    const m = data && data.found && data.country_mismatch;
    if (!m || !data.can_propose || data.blocked || data.waiting) {
        return false;
    }
    openChangePayScheme(dialog, {
        employeeId, data, pick: m.target_id,
        lead: _t("Country of work is now %s. Change the pay scheme too?", m.country_name),
        cancelLabel: _t("Not now"),
        onSaved: () => env.bus.trigger("PB_PERSON_SCHEME_CHANGED", { empId: Number(employeeId), source: "prompt" }),
    });
    return true;
}

patch(FormController.prototype, {
    async onRecordSaved(record, changes) {
        const out = await super.onRecordSaved(...arguments);
        if (record && record.resModel === "hr.employee" && record.resId
                && changes && Object.prototype.hasOwnProperty.call(changes, "payroll_country")) {
            // after the save, never inside it: the form keeps its own flow
            setTimeout(() => askAfterCountryChange(this.env, this.orm, this.dialogService, record.resId), 0);
        }
        return out;
    },
});

export { loadPersonScheme };
