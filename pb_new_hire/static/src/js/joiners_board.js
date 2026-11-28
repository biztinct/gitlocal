/** @odoo-module **/
/**
 * NEWHIRE P3b — the New joiners board shows what each new person was asked
 * (handover §2.6). Patched from here; `pb_onboarding`'s files are not edited.
 *
 * The row (`row.asked`) and the drawer (`state.drawer.joiner.asked`) come
 * from the server in ONE batched read. The chip is grey unless HR must act
 * (something needed for the first pay is still open within 7 days of the
 * first day) — the quiet board pattern. "Send again" and "Copy the welcome
 * link" are the invite facade's own, gated and rate-limited there.
 */
import { onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PbOnboardingBoard } from "@pb_onboarding/js/onboarding_board";
import { copyText } from "./studio_util";

const INVITE = "pb.new.hire.invite";

patch(PbOnboardingBoard.prototype, {
    setup() {
        super.setup(...arguments);
        this.nhUi = useState({ busy: false, link: "", hint: "", forId: 0, msg: "", msgKind: "" });
        // P8 E: a reader with only the "New joiners board" right (the HR
        // manager role) runs the board, not the Lifecycle team's settings
        // and daily run — those buttons stay out of their way
        this.nhBoard = useState({ only: false });
        onWillStart(async () => {
            const [board, life, admin] = await Promise.all([
                user.hasGroup("pb_new_hire.group_joiners_board"),
                user.hasGroup("pb_lifecycle.group_lifecycle_user"),
                user.hasGroup("base.group_system"),
            ]);
            this.nhBoard.only = board && !life && !admin;
        });
    },
    nhChipCls(asked) {
        if (asked.act) {
            return "warn";
        }
        return asked.done === asked.total ? "ok" : "muted";
    },
    nhStateCls(item) {
        return item.state === "done" ? "ok" : item.state === "waiting" ? "info" : "muted";
    },
    nhStateText(item, asked) {
        if (item.state === "done") {
            return _t("Done");
        }
        if (item.state === "waiting") {
            return _t("Sent, waiting for HR");
        }
        return _t("Waiting for %s", asked.first);
    },
    nhTitle(asked) { return _t("Asked from %s", asked.first); },
    nhNote(asked) {
        if (!asked.has_login) {
            return _t("No welcome link: %s has no email sign-in. They find these on My Payobook after signing in.", asked.first);
        }
        if (!asked.mail_on) {
            return _t("This site does not send email. Copy the welcome link and send it to %s yourself.", asked.first);
        }
        return "";
    },
    async nhSend(joiner) {
        if (this.nhUi.busy) {
            return;
        }
        this.nhUi.busy = true;
        try {
            const res = await this.orm.call(INVITE, "send_again", [joiner.employee_id]);
            this.nhSay(joiner, res.message || _t("Done."), res.sent ? "ok" : "warn");
            if (res.sent && this.state.drawer) {
                await this.openJoiner(this.state.drawer.joiner.id);
            }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work. Try again in a moment."), { type: "danger" });
        } finally {
            this.nhUi.busy = false;
        }
    },
    async nhCopy(joiner) {
        if (this.nhUi.busy) {
            return;
        }
        this.nhUi.busy = true;
        this.nhUi.link = "";
        this.nhUi.msg = "";
        try {
            const res = await this.orm.call(INVITE, "copy_link", [joiner.employee_id]);
            if (!res.ok) {
                this.nhSay(joiner, res.message, "warn");
                return;
            }
            const copied = await copyText(res.link);
            if (copied) {
                this.nhSay(joiner, _t("Link copied. %s", res.expires_hint || ""), "ok");
            } else {
                // no clipboard here: show the link to select and copy by hand
                this.nhUi.link = res.link;
                this.nhUi.hint = res.expires_hint || "";
                this.nhUi.forId = joiner.employee_id;
            }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work. Try again in a moment."), { type: "danger" });
        } finally {
            this.nhUi.busy = false;
        }
    },
    /** The answer, said twice: a toast, and under the buttons (the drawer
     *  sits above the toasts' layer, so the toast alone can be hidden). */
    nhSay(joiner, text, kind) {
        this.nhUi.msg = text;
        this.nhUi.msgKind = kind;
        this.nhUi.forId = joiner.employee_id;
        this.notif.add(text, { type: kind === "ok" ? "success" : "warning" });
    },
    nhSelect(ev) { ev.target.select(); },
    closeDrawer() {
        this.nhUi.link = "";
        this.nhUi.msg = "";
        return super.closeDrawer(...arguments);
    },
});
