/** @odoo-module **/
/**
 * The review form inside the Goals drawer (WDGAP S9-A) — a `patch()` of
 * pb_goals' board, never an edit of it.
 *
 * The manager opens the form from the end-of-year review row, reads the
 * employee's own view beside each line (once they have sent it), rates, writes
 * the overall comment and finishes. The overall result shown is the SERVER's
 * figure after each save; nothing here works one out.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PbGoalsBoard } from "@pb_goals/js/goals_board";

const SELF_WORDS = {
    todo: _t("Their own view: not started"),
    draft: _t("Their own view: started"),
    sent: _t("Their own view: sent"),
};
const MGR_WORDS = {
    todo: _t("Manager: not started"),
    draft: _t("Manager: started"),
    done: _t("Manager: finished"),
};

patch(PbGoalsBoard.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.rfOpen = 0;
        this.state.rf = null;
        this.state.rfAnswers = {};
        this.state.rfComment = "";
    },

    rfSelfWord(form) { return SELF_WORDS[form.self_state] || ""; },
    rfMgrWord(form) { return MGR_WORDS[form.mgr_state] || ""; },
    rfTone(stateKey) {
        return (stateKey === "sent" || stateKey === "done") ? "ok" : "wait";
    },

    async rfToggle(reviewId) {
        if (this.state.rfOpen === reviewId) {
            this.state.rfOpen = 0;
            this.state.rf = null;
            return;
        }
        try {
            const d = await this.orm.call("pb.review.forms", "drawer_form", [reviewId]);
            if (!d.ok) {
                this.notif.add(d.why || _t("That could not be opened."), { type: "warning" });
                return;
            }
            this.rfTake(d);
            this.state.rfOpen = reviewId;
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        }
    },

    rfTake(d) {
        this.state.rf = d;
        const answers = {};
        for (const line of [...(d.skills || []), ...(d.questions || [])]) {
            if (line.asks_me) { answers[line.id] = line.mine || ""; }
        }
        this.state.rfAnswers = answers;
        this.state.rfComment = d.comment || "";
    },

    rfPick(lineId, value) {
        if (!this.state.rf || !this.state.rf.may_edit) { return; }
        this.state.rfAnswers[lineId] = value;
    },

    rfInput(lineId, ev) { this.rfPick(lineId, ev.target.value); },

    async rfSave(finish = false, withoutSelf = false) {
        const rf = this.state.rf;
        if (!rf) { return; }
        if (finish && rf.self_state !== "sent" && !withoutSelf) {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Finish without their own view?"),
                body: _t("They have not sent their own view yet. Finish the review without it?"),
                confirmLabel: _t("Finish without it"),
                cancelLabel: _t("Wait for it"),
                confirm: () => this.rfSave(true, true),
                cancel: () => {},
            });
            return;
        }
        this.state.busy = true;
        try {
            const d = await this.orm.call("pb.review.forms", "drawer_save", [
                rf.review_id, this.state.rfAnswers, this.state.rfComment,
                finish, withoutSelf]);
            this.rfTake(d);
            this.notif.add(d.sentence || _t("Saved."), { type: "success" });
            if (finish) {
                await this.openSheet(this.state.sheet.id);
                this.state.rfOpen = d.review_id;
                this.rfTake(d);
                await this.reload();
            }
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    },
});
