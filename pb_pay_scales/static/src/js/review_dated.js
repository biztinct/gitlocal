/** @odoo-module **/
/**
 * WDGAP W3-B (PRV1) — the Pay Review waits for its start date.
 *
 * The review screen (pb_pay) is patched, never edited: one door, "Re-work
 * those months", that opens the NEW draft Past-month re-work(s) the server
 * prepares through `pb_retro`'s own gate. The re-work board is looked up by
 * the S8-D opener (`pb_pay_scales_open_rework`), never imported, so a
 * database without `pb_retro` loads none of its code (C-6: no back-pay input
 * is written here).
 */
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { PbPayReview } from "@pb_pay/js/pay_review";

patch(PbPayReview.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbsAction = useService("action");
    },

    async pbsRework() {
        const card = this.card;
        if (!card || this.state.busy) { return; }
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.pay.reviews", "pbs_open_rework", [card.id]);
            await this.reopen();
            if (res && res.review_id) {
                await this.pbsAction.doAction({
                    type: "ir.actions.client", tag: "pb_pay_scales_open_rework",
                    name: _t("Past-month re-work"), params: { review_id: res.review_id },
                });
            }
        } catch (error) {
            this._fail(error, _t("The re-work could not be opened."));
        }
        this.state.busy = false;
    },
});
