/** @odoo-module **/
/**
 * WDGAP S6-B — contract C-1 on the hiring board.
 *
 * "Confirm they joined" for an internal candidate answers with
 * `pb_open_action` when the system has the Change job flow: open it, so the
 * move ends in the job change and never in a second employee record. Every
 * other answer is left exactly as pb_hiring handles it.
 */
import { patch } from "@web/core/utils/patch";
import { PbHiringBoard } from "@pb_hiring/js/hiring_board";
import "@pb_hiring/js/hiring_p6";

patch(PbHiringBoard.prototype, {
    async p6Act(verb, payload) {
        const res = await super.p6Act(verb, payload);
        if (res && res.pb_open_action) {
            await this.env.services.action.doAction(res.pb_open_action);
        }
        return res;
    },
});
