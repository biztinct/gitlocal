/** @odoo-module **/
/**
 * The Overtime desk learns "Approve as time off" (owner ruling L3).
 *
 * Click handlers only. They call the desk's server `act` with the verb this
 * module adds (`approve_time_off`: set the choice, then approve, per row, as
 * the real user) and then do what the desk's own `_act` does afterwards —
 * per-row results, one toast, clear the selection, re-read — with the toast
 * saying what actually happened. The desk's own `_act` is not touched: its
 * toast only knows "approved" and "refused".
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbOtDesk } from "@pb_hr_workforce/js/pb_ot_desk";

patch(PbOtDesk.prototype, {
    async approveTimeOffOne(id) { await this._actTimeOff([id]); },
    async bulkApproveTimeOff() {
        if (!this.selectedCount) { return; }
        await this._actTimeOff(this.selectedIds);
    },
    timeOffTitle() {
        return _t("Approve and give the same number of hours as time off in lieu, instead of paying them");
    },
    async _actTimeOff(ids) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.ot.desk", "act", [ids, "approve_time_off"], {});
            const results = (res && res.results) || [];
            let ok = 0;
            const fails = [];
            for (const r of results) {
                this.state.rowResults[r.id] = r;
                if (r.ok) { ok += 1; } else { fails.push(r); }
            }
            if (ok) {
                this.notif.add(
                    _t("%s overtime request(s) approved as time off in lieu.", ok),
                    { type: "success" });
            }
            if (fails.length) {
                this.notif.add(
                    fails.map((f) => `${f.name || f.id}: ${f.error}`).join("  ·  "),
                    { type: "warning", sticky: fails.length > 1 });
            }
            this.clearSel();
            await this.load();
            await this.kit.refresh();
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    },
});
