/** @odoo-module **/
/**
 * One request, opened: the facts, what is attached, the route, and the answer.
 *
 * THE FACTS ARE FROZEN AND THE DRAWER SAYS SO. Everything in the grid at the
 * top is what the request looked like when it was sent in, not what the record
 * looks like now. That is the whole promise a signature makes: a person approves
 * a number, and the number cannot change under them afterwards.
 *
 * THE ROUTE IS A TIMELINE, NOT A LIST. Who has decided, who is deciding, who is
 * next and why they are next ("only because the amount is 600,000,000 or more"),
 * with a backup shown as "covering for" under both names. A joint step counts
 * its seats out loud — "1 of 3 approvals received".
 *
 * THREE ANSWERS AND EACH ONE COSTS WHAT IT SHOULD.
 *   Approve      — one press, unless the reader was part of preparing it, in
 *                  which case it becomes "Approve with exception" and a written
 *                  reason of real length is required.
 *   Send back    — a reason, because somebody has to act on it.
 *   Turn down    — a reason, and the drawer says in advance what ending the
 *                  request actually does.
 *
 * A STUCK REQUEST IS NOT A DEAD END. When nobody could be found for a step, the
 * drawer says which step and offers the door that mends it; nothing has to be
 * sent in again afterwards.
 */
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { initials, money, when } from "@pb_approval_config/js/sentence";

/** How long a reason has to be. Mirrors the server, which is the authority. */
const MIN_EXCEPTION_REASON = 12;
const MIN_REASON = 6;

export class RequestDrawer extends Component {
    static template = "pb_approval_config.RequestDrawer";
    static props = {
        requestId: { type: Number },
        scope: { type: String, optional: true },
        onClose: { type: Function },
        onChanged: { type: Function, optional: true },
        onOpenMatrix: { type: Function, optional: true },
    };

    setup() {
        this.ic = ic;
        this.initials = initials;
        this.money = money;
        this.when = when;
        this.orm = useService("orm");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            failed: "",
            request: null,
            modal: "",
            reason: "",
            // Who a stuck step would be handed to.
            moveTo: "",
            busy: false,
        });

        this.load();
    }

    async load() {
        this.state.loading = true;
        this.state.failed = "";
        try {
            this.state.request = await this.orm.call(
                "pb.approval.inbox", "get_request",
                [this.props.requestId, this.props.scope || "me"]);
        } catch (error) {
            this.state.failed = (error.data && error.data.message)
                || _t("This request could not be opened.");
        } finally {
            this.state.loading = false;
        }
    }

    get request() { return this.state.request || {}; }
    get conflict() { return this.request.conflict || null; }

    get currentStep() {
        return (this.request.steps || []).find(
            (step) => step.status === "active"
                || step.status === "blocked") || null;
    }

    get canApprove() {
        return Boolean(this.request.can_decide);
    }

    get mustUseException() {
        return Boolean(this.conflict && !this.conflict.blocked);
    }

    get isStuckOnMe() {
        return Boolean(this.conflict && this.conflict.blocked);
    }

    get minLength() {
        return this.state.modal === "exception"
            ? MIN_EXCEPTION_REASON : MIN_REASON;
    }

    get reasonOk() {
        return this.state.reason.trim().length >= this.minLength;
    }

    get modalCopy() {
        const request = this.request;
        return {
            exception: {
                title: _t("Approve, and say why you may"),
                note: this.conflict ? this.conflict.text : "",
                body: _t("You were part of this, so an exception is being used. Your name, your reason and the exception are all kept with the decision, and whoever looks after this route is told."),
                label: _t("Why is it safe for you to approve this?"),
                hint: _t("Say who else checked it, or what makes this one different."),
                confirm: _t("Approve with exception"),
                tone: "warn",
            },
            sendback: {
                title: _t("Send it back to %s", request.submitted_by || ""),
                note: "",
                body: _t("It goes back for changes. The approvals already given stay in the history; sending it in again starts a fresh attempt."),
                label: _t("What should change?"),
                hint: _t("Be specific — the person reading this is the one who has to fix it."),
                confirm: _t("Send it back"),
                tone: "info",
            },
            moveit: {
                title: _t("Move it to somebody else"),
                note: "",
                body: _t("The step goes to the person you choose, and the one it was with stops waiting. Your name and your reason are kept with the request, and the person who gets it reads them."),
                label: _t("Why is it moving? (required)"),
                hint: _t("Say what is wrong with the seat it is on — away, left, or the only person named is the one who sent it in."),
                confirm: _t("Move it"),
                tone: "info",
            },
            reject: {
                title: _t("Turn this down"),
                note: _t("This ends the request."),
                body: _t("Whoever sent it in has to start again. When a correction would be enough, send it back instead."),
                label: _t("Why? (required)"),
                hint: "",
                confirm: _t("Turn it down"),
                tone: "err",
            },
        }[this.state.modal] || null;
    }

    // ------------------------------------------------------------- acting
    openModal(kind) {
        this.state.modal = kind;
        this.state.reason = "";
        this.state.moveTo = "";
    }

    /** Whom this step could be handed to: anybody but the seats it is on. */
    get movePeople() {
        return (this.request.move_people || []);
    }

    get canMoveIt() {
        const can = this.request.can_move_it;
        return !!(can && can.can && (can.seats || []).length);
    }

    setMoveTo(ev) { this.state.moveTo = ev.target.value; }

    async moveIt() {
        const can = this.request.can_move_it || {};
        const seat = (can.seats || [])[0];
        if (!seat) { return; }
        this.state.busy = true;
        try {
            this.state.request = await this.orm.call(
                "pb.approval.inbox", "move_it",
                [this.props.requestId, seat.key,
                 parseInt(this.state.moveTo, 10), this.state.reason]);
            this.notif.add(_t("Moved. It is with them now."), { type: "info" });
            this.closeModal();
            if (this.props.onChanged) { this.props.onChanged(); }
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                    || _t("It could not be moved."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    closeModal() {
        this.state.modal = "";
        this.state.reason = "";
    }

    setReason(ev) { this.state.reason = ev.target.value; }

    async decide(action, useException) {
        const step = this.currentStep;
        if (!step) { return; }
        this.state.busy = true;
        try {
            this.state.request = await this.orm.call(
                "pb.approval.inbox", "decide",
                [this.props.requestId, step.key, action, this.state.reason,
                 this.request.lock_revision, false, Boolean(useException)]);
            this.state.modal = "";
            this.state.reason = "";
            this.notif.add({
                approve: _t("Recorded. Thank you."),
                return: _t("Sent back, with your note."),
                reject: _t("Turned down. Whoever sent it in is told, with your reason."),
            }[action], { type: action === "approve" ? "success" : "info" });
            if (this.props.onChanged) { this.props.onChanged(); }
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That could not be recorded."), { type: "danger" });
            await this.load();
        } finally {
            this.state.busy = false;
        }
    }

    async approve() { await this.decide("approve", false); }
    async approveWithException() { await this.decide("approve", true); }
    async sendBack() { await this.decide("return", false); }
    async reject() { await this.decide("reject", false); }

    async repair() {
        this.state.busy = true;
        try {
            this.state.request = await this.orm.call(
                "pb.approval.inbox", "repair", [this.props.requestId]);
            this.notif.add(
                this.state.request.blocked
                    ? _t("Still stuck — somebody still has to be named.")
                    : _t("It can go ahead again. Nothing has to be sent in again."),
                { type: this.state.request.blocked ? "warning" : "success" });
            if (this.props.onChanged) { this.props.onChanged(); }
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That could not be mended from here."),
                { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async cancel() {
        this.state.busy = true;
        try {
            this.state.request = await this.orm.call(
                "pb.approval.inbox", "cancel",
                [this.props.requestId, _t("Withdrawn by the person who sent it in")]);
            this.notif.add(_t("Withdrawn."), { type: "info" });
            if (this.props.onChanged) { this.props.onChanged(); }
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That could not be withdrawn."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    openMatrix() {
        if (this.props.onOpenMatrix) { this.props.onOpenMatrix(); }
    }
}
