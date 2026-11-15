/** @odoo-module **/
/**
 * Decision Room: an approved plan → draft hiring requests (WDGAP S8-C).
 *
 * A patch of the room (no edit of pb_decision_room): the dock row of an
 * approved plan gets "Hiring requests" and "3 of 5 lines have a request";
 * the button opens this dialog. The server (`pb.decision.plan`) builds the
 * lines, refuses what it must and never makes a line twice.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { PbDecisionRoom } from "@pb_decision_room/js/decision_room";

const MODEL = "pb.decision.plan";

export class PlanHiringDialog extends Component {
    static template = "pb_plan_hiring.PlanHiringDialog";
    static components = { Dialog };
    static props = { planId: Number, planName: String, close: Function, onDone: { type: Function, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = ic;
        this.state = useState({ loaded: false, data: null, picks: {}, titles: {}, busy: false });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.apply(await this.orm.call(MODEL, "pb_get_hiring_lines", [this.props.planId]));
        } catch (e) {
            this.fail(e);
        }
        this.state.loaded = true;
    }
    apply(data) {
        this.state.data = data;
        const picks = {};
        for (const line of data.lines || []) {
            if (line.can_make) { picks[line.key] = this.state.picks[line.key] !== false; }
        }
        this.state.picks = picks;
    }
    fail(e) {
        const msg = (e && e.data && e.data.message) || _t("That did not work. Try again in a moment.");
        this.notif.add(msg, { type: "warning" });
    }

    get lines() { return (this.state.data && this.state.data.lines) || []; }
    get hires() { return this.lines.filter((l) => l.n > 0); }
    get leavers() { return this.lines.filter((l) => l.n < 0); }
    get made() { return this.hires.filter((l) => l.request).length; }
    get picked() {
        return this.hires.filter((l) => l.can_make && this.state.picks[l.key]);
    }
    get missingTitle() {
        return this.picked.some((l) => l.needs_title && !(this.state.titles[l.key] || "").trim());
    }
    toggle(line) { this.state.picks[line.key] = !this.state.picks[line.key]; }
    setTitle(line, ev) { this.state.titles[line.key] = ev.target.value; }

    async make() {
        this.state.busy = true;
        try {
            const picks = this.picked.map((l) => ({ key: l.key, title: this.state.titles[l.key] || "" }));
            const res = await this.orm.call(MODEL, "pb_make_hiring_requests", [this.props.planId, picks]);
            this.apply(res);
            this.notif.add(_t("%s draft hiring requests made. Nothing has been sent in.", res.made || 0),
                           { type: "success" });
            if (this.props.onDone) {
                this.props.onDone({ lines: this.hires.length, made: this.made });
            }
        } catch (e) {
            this.fail(e);
        } finally {
            this.state.busy = false;
        }
    }
    async openRequest(line) {
        try {
            const action = await this.orm.call(MODEL, "pb_open_request", [line.request.id]);
            this.props.close();
            await this.action.doAction(action);
        } catch (e) {
            this.fail(e);
        }
    }
}

patch(PbDecisionRoom.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbDialog = useService("dialog");
    },
    /** {lines, made} for a saved, approved plan of the dock, or null. */
    pbHiringOf(row) {
        const plan = (this.state.plans || []).find((p) => p.id === row.id);
        return (plan && plan.pb_hiring) || null;
    },
    pbHiringLine(row) {
        const h = this.pbHiringOf(row);
        if (!h || !h.lines) { return ""; }
        return _t("%(made)s of %(lines)s hires have a request", { made: h.made, lines: h.lines });
    },
    openPlanHiring(row) {
        this.pbDialog.add(PlanHiringDialog, {
            planId: row.id,
            planName: row.name || "",
            onDone: (summary) => {
                const plan = (this.state.plans || []).find((p) => p.id === row.id);
                if (plan) { plan.pb_hiring = summary; }
            },
        });
    },
});
