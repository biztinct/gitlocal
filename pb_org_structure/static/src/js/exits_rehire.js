/** @odoo-module **/
/**
 * Would we hire them again? — the two presses of the Exits drawer's new
 * question (S8-C). A patch, so `pb_offboarding` is not edited. The server
 * (`pb.exits.set_rehire`) decides who may answer.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbExitsBoard } from "@pb_offboarding/js/exits_board";

patch(PbExitsBoard.prototype, {
    async pbRehireSave(value, note) {
        const d = this.state.drawer;
        if (!d || !d.pb_rehire) { return; }
        try {
            const res = await this.orm.call("pb.exits", "set_rehire",
                [d.pb_rehire.case_id, value, note]);
            d.pb_rehire = Object.assign({}, d.pb_rehire, res);
            this.notif.add(_t("Saved. Seen by HR only."), { type: "success" });
        } catch (e) {
            this.fail(e);
        }
    },
    pbRehirePick(value) {
        const d = this.state.drawer;
        const next = d.pb_rehire.value === value ? "" : value;
        return this.pbRehireSave(next, d.pb_rehire.note || "");
    },
    pbRehireNote(note) {
        const d = this.state.drawer;
        return this.pbRehireSave(d.pb_rehire.value || "", note);
    },
});
