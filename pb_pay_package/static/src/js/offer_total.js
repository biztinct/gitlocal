/** @odoo-module **/
/**
 * WDGAP S8-D (owner ruling SC3) — "Build from a total" on a Hiring offer.
 *
 * A door on the offer panel of the Hiring board (by `patch()` and template
 * inheritance — no edit of pb_hiring): it opens the same card the contract
 * drawer uses, on the offer. "Use these figures" writes the split as the
 * offer's monthly pay lines (server side) and the board reads the offer again.
 */
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { PbHiringBoard } from "@pb_hiring/js/hiring_board";
import { openBuildTotal } from "@pb_pay_package/js/build_total";

patch(PbHiringBoard.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbpkOverlay = useService("overlay");
    },
    pbpkCanBuild(offer) {
        return Boolean(offer && offer.id && offer.state === "draft" && !offer.money_locked
                       && this.state.canRecruit);
    },
    pbpkOpenTotal(offer) {
        if (!this.pbpkCanBuild(offer)) { return; }
        openBuildTotal(this.pbpkOverlay, {
            offerId: offer.id,
            onUse: async (res) => {
                if (res && res.note) { this.notif.add(res.note, { type: "success" }); }
                await this.refresh();
            },
        });
    },
});
