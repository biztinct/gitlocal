/** @odoo-module **/
/**
 * UPDATES P2d — one-off pay items from Updates on the Run Payroll screen.
 *
 * Two small additions to the existing screen, no new screen (handover §5.3):
 *
 *   * step 1 — one informational line under the pay scheme: "3 one-off pay
 *     items from Updates will be included for 2 people (₫1,500,000 added to
 *     pay)", or, for a scheme run from application data, that they are not
 *     included in that kind of pay run. The numbers come with the scheme's own
 *     preview (`scheme_preview`, extended in `pb_updates`).
 *   * the review step ("Review exceptions") — owner decision D11: when the
 *     pay data file carries a different amount for the same person, pay item
 *     and month, the run stops and asks. Both amounts are listed with two
 *     buttons; the choice is stored with who and when, and that person's
 *     payslip is worked out again at once. The questions come with the
 *     review's own summary (`get_summary`, extended in `pb_updates`).
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PayrunWizard } from "@pb_payrun_wizard/js/payrun_wizard";

patch(PayrunWizard.prototype, {
    /** The step-1 line, or "" when no one-off from Updates is waiting. */
    get pbuOneoff() {
        const preview = this.state.scheme && this.state.scheme.preview;
        return (preview && preview.updates_oneoffs) || null;
    },

    /** D11 questions this run asked and nobody has answered yet. */
    get pbuClashes() {
        const s = this.state.summary;
        return ((s && s.oneoff_clashes) || []).filter((c) => !c.chosen);
    },

    get pbuClashTitle() {
        const n = this.pbuClashes.length;
        return n === 1 ? _t("One pay item has two amounts")
            : _t("%s pay items have two amounts", n);
    },

    get pbuCanChoose() {
        return !!(this.state.summary && this.state.summary.oneoff_can_choose);
    },

    async pbuChoose(clash, choice) {
        if (this.state.pbuBusy) { return; }
        this.state.pbuBusy = `${clash.id}:${choice}`;
        try {
            const res = await this.orm.call("pb.updates.oneoff", "resolve_clash", [], {
                row_id: clash.id, choice });
            if (!res.ok) {
                this.notif.add(res.msg, { type: "warning" });
            } else {
                this.notif.add(res.msg, { type: "success" });
                // The exception line this question produced is answered now.
                const s = this.state.summary;
                s.exceptions = (s.exceptions || []).filter(
                    (e) => !(e.emp === clash.emp && String(e.why || "").includes(clash.item)));
            }
            const fresh = await this.orm.silent.call("pb.payrun.wizard", "get_summary", [this.state.summary.run_id]);
            this.state.summary.oneoff_clashes = (fresh && fresh.oneoff_clashes) || [];
        } catch (e) {
            this.notif.add(e.data?.message || _t("The choice could not be saved. Nothing has changed."),
                           { type: "danger" });
        } finally {
            this.state.pbuBusy = "";
        }
    },
});
