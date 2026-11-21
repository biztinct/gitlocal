/** @odoo-module **/
/**
 * `pb_pip_request` — the ONE door a line manager has into this module.
 *
 * Not a board and not a lens: a single dialog-shaped client action reached from
 * the command bar. A manager picks somebody who reports to them, writes what
 * they have seen, and that is the whole of what they can do. They cannot see
 * anybody else's plan, they cannot see the objectives on their own person's
 * plan, and they cannot move it on.
 *
 * WHY THE PALETTE ROW IS OFFERED TO EVERY INTERNAL USER. A palette gate is a
 * list of group xmlids, and "manages at least one person" is not a group —
 * it is a fact about `hr.employee.parent_id`. So the row is ungated and the
 * SERVER answers the question: `pb.pip.request_options()` returns
 * `allowed: false` with a sentence for somebody who manages nobody, and this
 * component shows that sentence rather than an empty picker. A door that
 * explains itself is not a dead end (W29 is about doors that can only produce
 * an ERROR; this one produces an answer).
 *
 * THE EMPLOYEE ID IS RE-DERIVED ON THE SERVER. `raise_request` checks that the
 * person actually reports to the caller, because a forged id from here would
 * otherwise plant a request on a colleague's record — the same hole
 * `pb_me_portal` closed on profile change requests.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbPipRequest extends Component {
    static template = "pb_pip.PbPipRequest";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            allowed: false,
            why: "",
            team: [],
            templates: [],
            mine: [],
            employeeId: 0,
            templateId: 0,
            reason: "",
            busy: false,
            done: null,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        try {
            const d = await this.orm.call("pb.pip", "request_options", []);
            Object.assign(this.state, {
                allowed: !!d.allowed,
                why: d.why || "",
                team: d.team || [],
                templates: d.templates || [],
                loaded: true,
            });
        } catch (e) {
            console.warn("pb_pip: could not open the request form", e);
            this.state.loaded = true;
            this.state.allowed = false;
            this.state.why = _t("That could not be opened just now. Try again in a moment.");
        }
        // The requests this person already raised, read through the record rule
        // rather than through a second copy of it — so when the setting is off
        // this list is simply empty and the page says so.
        try {
            this.state.mine = await this.orm.call("pb.pip", "my_requests", []);
        } catch (e) {
            this.state.mine = [];
        }
    }

    pick(id) {
        this.state.employeeId = this.state.employeeId === id ? 0 : id;
    }

    pickTemplate(id) {
        this.state.templateId = this.state.templateId === id ? 0 : id;
    }

    onReason(ev) { this.state.reason = ev.target.value; }

    get chosen() {
        return this.state.team.find((p) => p.id === this.state.employeeId)
            || null;
    }

    get canSend() {
        return !!(this.state.employeeId
            && (this.state.reason || "").trim().length >= 20
            && !this.state.busy);
    }

    /** The sentence under the box — ONE expression (R34). */
    get hint() {
        if (!this.state.employeeId) {
            return _t("Choose who this is about first.");
        }
        const written = (this.state.reason || "").trim().length;
        if (written < 20) {
            return _t("Write a few lines about what you have actually seen. HR reads this before anything else happens, and it is the difference between a useful conversation and a defensive one.");
        }
        return _t("HR will read this and come back to you. Nothing is written to anybody's record by sending it.");
    }

    async send() {
        if (!this.canSend) { return; }
        this.state.busy = true;
        try {
            const res = await this.orm.call(
                "pb.pip", "raise_request",
                [this.state.employeeId, this.state.reason,
                 this.state.templateId || false]);
            this.state.done = {
                who: this.chosen ? this.chosen.name : "",
                existing: !!res.existing,
                label: res.label || "",
            };
            await this.load();
        } catch (e) {
            const msg = (e && e.data && e.data.message) || (e && e.message)
                || _t("That could not be sent. Try again in a moment.");
            this.notif.add(msg, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    again() {
        Object.assign(this.state, {
            done: null, employeeId: 0, templateId: 0, reason: "",
        });
    }
}

registry.category("actions").add("pb_pip_request", PbPipRequest);
