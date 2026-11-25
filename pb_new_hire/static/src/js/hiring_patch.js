/** @odoo-module **/
/**
 * NEWHIRE P4 A.4 — Hiring's "Confirm they joined" opens the New Hire Studio
 * with the signed offer brought across; "Many at once" lands on the Updates
 * desk's new-employee sheet.
 *
 * PATCHES, never edits (D10). Every "Confirm they joined" in Hiring — the
 * candidate drawer's joining door, the Next box's `confirm_open` verb and the
 * role's offer panel (`closeOffer` → `p6FromOffer`) — funnels into ONE method,
 * `p6OpenConfirm`. For an HR user it now opens the studio; Hiring's own
 * dialog stays one click away as the quiet "Confirm without the form"
 * (`p6OpenConfirmPlain`), and is what everybody else (a recruiter without the
 * HR right, who cannot use the studio) still gets from the main button.
 *
 * Without `pb_new_hire` installed none of this file exists: Hiring keeps its
 * own dialog untouched.
 */
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { onWillStart } from "@odoo/owl";
import { PbHiringBoard } from "@pb_hiring/js/hiring_board";
import { PbUpdatesDesk } from "@pb_updates/js/updates_desk";
import { ACTION_XMLID } from "./studio_util";

patch(PbHiringBoard.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbnhHR = false;
        onWillStart(async () => {
            try {
                this.pbnhHR = await user.hasGroup("hr.group_hr_user");
            } catch {
                this.pbnhHR = false;
            }
        });
    },
    /** The studio, with the offer brought across (HR); Hiring's dialog otherwise. */
    p6OpenConfirm() {
        const cand = this.state.cand;
        const jn = cand && cand.joining;
        if (!this.pbnhHR || !jn || !jn.offer_id) {
            return super.p6OpenConfirm(...arguments);
        }
        return this.action.doAction(ACTION_XMLID, {
            additionalContext: { pb_nh_offer_id: jn.offer_id, pb_nh_step: "who" },
        });
    },
    /** Hiring's own one-press confirm, kept reachable. */
    p6OpenConfirmPlain() {
        return super.p6OpenConfirm(...arguments);
    },
    async p6FromOfferPlain(offer) {
        if (!offer || !offer.applicant_id) {
            return;
        }
        await this.openCand(offer.applicant_id);
        if (this.state.cand && this.state.cand.joining) {
            this.p6OpenConfirmPlain();
        }
    },
});

patch(PbUpdatesDesk.prototype, {
    /** "Many at once" in the studio: start a lasting sheet with the blank
     *  new-employee sheet already open. */
    async loadHome() {
        const out = await super.loadHome(...arguments);
        const ctx = (this.props.action && this.props.action.context) || {};
        if (ctx.pb_nh_joiners_sheet && !this.pbnhJoinersDone) {
            this.pbnhJoinersDone = true;
            if (this.canHire) {
                this.newUpdate("lasting");
                if (!this.state.joinerSheet.open) {
                    await this.openJoinerSheet();
                }
            }
        }
        return out;
    },
});
