/** @odoo-module **/
/**
 * `pb_home_hub` — the Home mission, on Cycle 1's HubShell.
 *
 * Two lenses, in the order the IA mockup fixes them:
 *
 *     pulse · approvals
 *
 * The pulse is what the company looks like this morning; approvals is what is
 * waiting on YOU. Both are the EXISTING cockpits mounted with `embedded: true`
 * (W17) — nothing here reimplements one and nothing forks one, and both
 * standalone client actions keep working.
 *
 * ---------------------------------------------------------------------------
 * The gates (W95: derived from the model BEHIND the door, never copied from the
 * rail item that used to open it)
 *
 *   pulse      `pb.dashboard.get_dashboard_data` has NO gate at all — every
 *              read inside it goes through a `safe()` wrapper that answers 0
 *              for anything the caller may not read, on purpose, because this
 *              is the first screen of every tenant. So the lens is UNGATED, and
 *              that matches the rail item it replaces (`item_dashboard` ships
 *              no `groups_id`).
 *   approvals  `pb.approval._require_access()`'s `_APPROVAL_GROUPS`, verbatim —
 *              including `pb_demo.group_payobook_demo`, which really is in that
 *              tuple. Restating the list here rather than importing it is not
 *              possible across the Python/JS boundary, so the test reads the
 *              tuple back out of the facade and compares.
 * ---------------------------------------------------------------------------
 *
 * The tracker is the only thing this hub adds, and it is deliberately the Pay
 * Run hub's own read (`pb.pay.hub.get_period_state`) rather than a second
 * derivation of "where is this month". Two surfaces answering the same question
 * must read the same source (W62); the chip on Home and the chip on Pay Run are
 * the same fact, and a click hands over to the lens where the outstanding work
 * lives, carrying a back chip that says Home.
 *
 * `config` is built ONCE per instance, never in a getter: HubShell's `config`
 * prop must keep a stable identity or every render recreates every lens (the
 * refetch trap, W21).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";

import { PbDashboard } from "@pb_dashboard/js/pb_dashboard";
import { PbApproval } from "@pb_approval/js/approval";

/** `pb.approval._APPROVAL_GROUPS`, verbatim. The test reads the tuple back. */
export const APPROVAL_GATE = [
    "pb_hr_payroll_base.group_payroll_base_officer",
    "pb_hr_payroll_base.group_payroll_base_manager",
    "pb_hr_payroll_base.group_payroll_final_approver",
    "pb_hr_payroll_base.group_payroll_super_admin",
    "pb_demo.group_payobook_demo",
];

/**
 * Which Pay Run lens the tracker's click should land on, per stage.
 *
 * The same map `pb_payhub` uses for the same chip, restated here because the
 * two hubs must not import each other's private constants — and asserted equal
 * by `pb_home_hub/tests`, so "restated" can never become "diverged".
 */
export const STAGE_LENS = {
    1: "run", 2: "runs", 3: "payslips", 4: "deliver", 5: "runs",
};

/**
 * Where a later module bolts a lens onto Home.
 *
 *     registry.category(HOME_LENSES).add("wall", {
 *         key, icon, label, Component, groups,
 *         propsFromContext(ctx) { return { ... }; },   // optional
 *     }, { sequence: 20 });
 *
 * A REGISTRY rather than an import, and the direction of the dependency is the
 * whole reason: a module that mounts a lens here depends on this hub, so this
 * hub cannot import it back without a cycle no manifest can express. This is an
 * exact clone of `pb_people_hub`'s (`people_hub.js:82`) — the same shape P7 gave
 * `pb_payhub` (R73), for the same reason and with the same properties: absent
 * module, absent lens, no error.
 *
 * The two shipped lenses carry no sequence, so bolted-on ones start at 20 and
 * land after them.
 */
export const HOME_LENSES = "pb_home_hub_lens";

export class PbHomeHub extends Component {
    static template = "pb_home_hub.PbHomeHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");

        // The tracker is the only piece of the config that is DATA, so it is
        // the only piece kept in state. Everything else is declaration.
        this.state = useState({ period: null });

        this.config = {
            key: "home",                      // -> pbhub.home.lens.v1
            brand: { label: _t("Home"), icon: "home" },
            defaultLens: "pulse",
            tracker: this.tracker,
            cog: () => this.openSettings(),
            lenses: [
                { key: "pulse", icon: "activity", label: _t("Pulse"),
                  Component: PbDashboard },
                { key: "approvals", icon: "inbox", label: _t("Approvals"),
                  Component: PbApproval, groups: APPROVAL_GATE },
                // Bolted-on lenses sit after the two this hub ships — what
                // needs you first, everything else after.
                ...this.extraLenses(),
            ],
        };

        onWillStart(async () => { await this.loadPeriod(); });
    }

    /** Lenses other modules registered, resolved ONCE (never in a getter, W21). */
    extraLenses() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return registry.category(HOME_LENSES).getAll().map((def) => {
            const props = typeof def.propsFromContext === "function"
                ? def.propsFromContext(ctx) : (def.props || {});
            return { ...def, props };
        });
    }

    // ------------------------------------------------------------- the period
    /**
     * A READ, in a mount hook, that writes only THIS component's own state.
     *
     * W21 is about a child writing its HOST's state during the host's render
     * fiber. This IS the host and `state.period` is its own; the tracker object
     * handed to the shell reads through getters, so the shell sees the numbers
     * on the next render without anyone calling back up.
     */
    async loadPeriod() {
        try {
            this.state.period = await this.orm.call(
                "pb.pay.hub", "get_period_state", []);
        } catch (e) {
            // Reported, never swallowed into a decoration (W40). A hub whose
            // tracker failed still opens; it simply does not claim a stage.
            console.warn("pb_home_hub: could not read the period state", e);
            this.state.period = null;
        }
    }

    /** Stable identity, live numbers — the pay hub's shape, verbatim. */
    get tracker() {
        const self = this;
        return {
            get label() {
                return self.state.period ? self.state.period.label
                                         : _t("This month");
            },
            get stage() { return self.state.period ? self.state.period.stage : 0; },
            get total() { return self.state.period ? self.state.period.total : 0; },
            onClick: () => this.onTrackerClick(),
        };
    }

    /**
     * A CLICK handler, and the only place in this file that leaves the hub for
     * the pay run.
     *
     * By XMLID rather than by tag: a bare tag reaches the shell with no action
     * NAME, and anything that later returns through a breadcrumb reads
     * "Unnamed" (W98). The back chip says Home, so the errand is a round trip
     * and not a page you have to find your way home from (W5).
     */
    onTrackerClick() {
        const p = this.state.period;
        if (!p) { return; }
        this.notif.add(p.stage_label, { type: "info" });
        openHub(this.actionService, {
            xmlid: "pb_payhub.action_pb_pay_hub",
            lens: STAGE_LENS[p.stage] || "runs",
            back: { label: _t("Home"), xmlid: "pb_home_hub.action_pb_home_hub" },
        });
    }

    /** The cog. A CLICK handler — the shell calls it, nothing else does. */
    openSettings() {
        openHub(this.actionService, {
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("Home"), xmlid: "pb_home_hub.action_pb_home_hub" },
        });
    }
}

registry.category("actions").add("pb_home_hub", PbHomeHub);
