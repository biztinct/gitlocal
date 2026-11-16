/** @odoo-module **/
/**
 * Change job's doors on other modules' screens — by `patch()` and template
 * inheritance only (S8 lane rule: no edit of pb_employee_vault or pb_orgchart).
 *
 *   1. The person's side panel: a "Change job" button in the header, and a
 *      chip (the `pb_employee_360_chips` seam) when a change is waiting or
 *      starts later.
 *   2. The org chart person panel: a "Change job" button in its footer.
 *   3. `pb_job_change_open_rework` — a client FUNCTION that opens the
 *      Past-month re-work straight on one re-work. `pb_retro` is optional, so
 *      it is looked up in the actions registry when pressed, never imported:
 *      a database without it never loads a line of its code from here.
 *   4. Pay › Changes (WDGAP S8-D, PC1): "New pay change" opens Change job for
 *      the person picked. The list and history of pay changes stay as they
 *      are; a database without this module keeps the old form exactly.
 */
import { Component, onWillStart, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { Employee360Drawer } from "@pb_employee_vault/js/employee_360";
import { PbOrgChart } from "@pb_orgchart/js/orgchart";
import { PbPayChanges } from "@pb_pay/js/pay_review";

/** Mirrors `job_change.GATE_GROUPS`; the server refuses everybody else too. */
export const JOB_CHANGE_GATE = [
    "hr.group_hr_manager",
    "pb_pay.group_pay_manager",
    "om_hr_payroll.group_hr_payroll_manager",
];

async function mayChangeJobs() {
    for (const g of [...JOB_CHANGE_GATE, "base.group_system"]) {
        if (await user.hasGroup(g)) { return true; }
    }
    return false;
}

function openFlow(action, empId) {
    return action.doAction({
        type: "ir.actions.client", tag: "pb_job_change", name: _t("Change job"),
        params: { employee_id: Number(empId) },
    });
}

// ============================================================ 1. side panel
patch(Employee360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbJc = useState({ allowed: false });
        onWillStart(async () => {
            try { this.pbJc.allowed = await mayChangeJobs(); } catch { this.pbJc.allowed = false; }
        });
    },
    pbJcIcon(name, size = 14) { return pbfIcon(name, size); },
    openChangeJob() {
        return openFlow(this.action, this.props.empId);
    },
});

export class JobChangeChip extends Component {
    static template = "pb_job_change.JobChangeChip";
    static props = { empId: { type: [Number, String], optional: true } };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: {} });
        onWillStart(async () => {
            try {
                this.state.data = (await this.orm.silent.call(
                    "pb.job.change.board", "chip", [Number(this.props.empId) || 0])) || {};
            } catch {
                this.state.data = {};
            }
        });
    }
    icon(n, s = 13) { return pbfIcon(n, s); }
    open() {
        const id = this.state.data.id;
        if (!id) { return; }
        this.action.doAction({
            type: "ir.actions.client", tag: "pb_job_change", name: _t("Job changes"),
            params: { change_id: id },
        });
    }
}
registry.category("pb_employee_360_chips").add("job_change", JobChangeChip);

// ============================================================ 2. org chart
patch(PbOrgChart.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbJc = useState({ allowed: false });
        onWillStart(async () => {
            try { this.pbJc.allowed = await mayChangeJobs(); } catch { this.pbJc.allowed = false; }
        });
    },
    pbJcIcon(name, size = 15) { return pbfIcon(name, size); },
    pbJcOpen(node) {
        if (!node || node.isRole || !node.empId) { return; }
        return openFlow(this.action, node.empId);
    },
});

// ======================================================= 4. Pay › Changes
// WDGAP S8-D (owner ruling PC1): Pay › Changes keeps its list and history, but
// a NEW raise opens Change job for the person picked (one sign-off, and the
// new pay starts on its date — a pay change written here used to move the
// wage at once). Only where Change job is installed (this file only loads
// then) and only for people who may change jobs; anybody else keeps the old
// form exactly as it was.
patch(PbPayChanges.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbJcAction = useService("action");
        this.pbJc = useState({ allowed: false });
        onWillStart(async () => {
            try { this.pbJc.allowed = await mayChangeJobs(); } catch { this.pbJc.allowed = false; }
        });
    },
    pbJcIcon(name, size = 14) { return pbfIcon(name, size); },
    async choosePerson(person) {
        if (!this.pbJc.allowed) {
            return super.choosePerson(person);
        }
        this.state.busy = true;
        try {
            const act = await this.orm.call("pb.job.change", "pb_start_for_employee", [
                person.id, { reason_kind: "pay", source: "pay_changes" }]);
            this.state.drafting = null;
            await this.pbJcAction.doAction(act);
        } catch (error) {
            this.state.dialogError = this._msg(error, _t("Change job could not be opened for this person."));
        }
        this.state.busy = false;
    },
});

// ============================================================ 3. re-work door
let ReworkOpener = null;

function reworkOpener() {
    if (ReworkOpener) { return ReworkOpener; }
    const actions = registry.category("actions");
    if (!actions.contains("pb_retro_board")) { return null; }
    const Board = actions.get("pb_retro_board");
    ReworkOpener = class extends Board {
        setup() {
            super.setup(...arguments);
            const params = (this.props.action && this.props.action.params) || {};
            onMounted(async () => {
                if (params.review_id && this.state.allowed !== false) {
                    await this.openReview(params.review_id);
                }
            });
        }
    };
    actions.add("pb_job_change_rework_board", ReworkOpener, { force: true });
    return ReworkOpener;
}

registry.category("actions").add("pb_job_change_open_rework", (env, action) => {
    const params = action.params || {};
    if (!reworkOpener()) {
        env.services.notification.add(
            _t("Past-month re-work is not part of this database. The pay team can work out any difference by hand on the next pay run."),
            { type: "warning" });
        return;
    }
    return {
        type: "ir.actions.client", tag: "pb_job_change_rework_board",
        name: _t("Past-month re-work"), params: { review_id: params.review_id },
    };
});
