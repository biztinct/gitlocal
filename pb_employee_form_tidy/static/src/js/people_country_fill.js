/** @odoo-module **/
/**
 * TIDY-E 3b — the People list's "Fill Country of Work" button (HR managers,
 * only while someone has none). Reached by `patch()` + template inheritance,
 * no edit of pb_people. The figure comes from `get_roster_head`
 * (`kpis.cow_empty`, `kpis.cow_can_fill`, added by this module's
 * `pb.people._roster_kpis` override).
 */
import { patch } from "@web/core/utils/patch";
import { PbPeople } from "@pb_people/js/people";

patch(PbPeople.prototype, {
    get cowFillShown() {
        const k = this.state.kpis || {};
        return Boolean(k.cow_can_fill && k.cow_empty);
    },
    get cowEmpty() {
        return Number((this.state.kpis || {}).cow_empty || 0).toLocaleString();
    },
    async openCountryFill() {
        await this.action.doAction("pb_employee_form_tidy.action_pb_cow_fill_wizard", {
            onClose: async () => {
                await this.load();
                await this.loadPage();
            },
        });
    },
});
