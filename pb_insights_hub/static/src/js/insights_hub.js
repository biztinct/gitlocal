/** @odoo-module **/
/**
 * `pb_insights_hub` — the Insights mission, on Cycle 1's HubShell.
 *
 * Pulse and Explorer remain the cross-module analysis workspace. Workforce
 * reports belong to People; payroll reports and Budget to Payroll; Hiring,
 * goal and training reports live with Hiring, Talent and Learning. Existing
 * Insights deep links redirect to those homes with their context intact.
 *
 * Every lens is the EXISTING cockpit, mounted with `embedded: true` (W17).
 * Nothing here holds data: the hub owns no model, no ACL and no RPC — each
 * facade keeps its own gate regardless of what this file says (W12).
 *
 * ---------------------------------------------------------------------------
 * The gates (W95: derived from the ACL of the model BEHIND the door, never
 * copied from the rail item that used to open it)
 *
 *   pulse      pb.insights._require()             the three analytics tiers
 *   explorer   pb.explorer._require()             …the same three, verbatim
 *   workforce  pb.workforce.insights._require()   …and the same three again
 *   payroll    hr.payroll.report.api → no facade gate at all; it reads
 *              `hr.payslip.run` with the caller's own rights, so the gate is
 *              that model's `ir.model.access` READ set
 *
 * The first three read their answer straight out of the facades' `_GATE_GROUPS`
 * tuples, each of which also returns early for `base.group_system`. The fourth
 * does NOT include `base.group_system`, because the ACL does not: an
 * administrator who does not hold a payroll group cannot read a payslip run,
 * and offering them the lens would be W29's door that can only produce an
 * error. On this database the administrator holds
 * `om_hr_payroll.group_hr_payroll_manager`, so all four lenses render — that is
 * a fact about the database, and it is asserted in the tests rather than
 * assumed here.
 *
 * `pb_demo.group_payobook_demo` IS listed on the payroll lens, and only there,
 * because the demo persona really is granted read on `hr.payslip.run` and the
 * Payroll Report is a read-only surface. It is deliberately absent from the
 * three analytics lenses, whose facades would refuse it.
 * ---------------------------------------------------------------------------
 *
 * `config` is built ONCE per instance, never in a getter: HubShell's `config`
 * prop must keep a stable identity or every render recreates every lens (the
 * refetch trap, W21).
 */
import { Component, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";
import { HUB_LENS_GATES } from "@pb_hub/js/hub_gates";

import { PbInsights } from "@pb_insights/js/insights";
import { PbExplorer } from "@pb_explorer/js/explorer";
import { PbWorkforceInsights } from "@pb_workforce_insights/js/workforce_insights";
import { PayrollReport } from "@pb_hr_workforce/js/payroll_report";
import { PbModuleInsights } from "@pb_insights/js/module_insights";

/** The three analytics facades' own `_GATE_GROUPS`, plus their system escape. */
export const ANALYTICS_GATE = [
    "pb_hr_payroll_base.group_payroll_base_manager",
    "pb_hr_payroll_base.group_payroll_analytics_user",
    "pb_hr_payroll_base.group_payroll_super_admin",
    "base.group_system",
];

/** `hr.payslip.run`'s READ access, which is what the Payroll Report needs. */
export const PAYSLIP_RUN_GATE = [
    "om_hr_payroll.group_hr_payroll_manager",
    "pb_hr_payroll_base.group_payroll_base_officer",
    "pb_demo.group_payobook_demo",
];

/**
 * Where a later module bolts a lens onto Insights.
 *
 *     registry.category(INSIGHTS_LENSES).add("budget", {
 *         key, icon, label, Component, groups,
 *         propsFromContext(ctx) { return { ... }; },   // optional
 *     }, { sequence: 20 });
 *
 * A REGISTRY rather than an import, and the direction of the dependency is the
 * whole reason: a module that mounts a lens here depends on this hub, so this
 * hub cannot import it back without a cycle no manifest can express. An exact
 * clone of `pb_people_hub`'s, of the one P7 gave `pb_payhub` (R73) and of the
 * one P8 gave `pb_home_hub` (R83) — same shape, same properties: absent module,
 * absent lens, no error.
 *
 * The four shipped lenses carry no sequence, so bolted-on ones start at 20 and
 * land after them. A bolted-on lens brings its OWN gate; the shell's per-lens
 * `groups` is advisory and the facade behind it enforces (W12), which is what
 * lets a lens live here whose readers are not analytics readers at all.
 */
export const INSIGHTS_LENSES = "pb_insights_hub_lens";

// One home for each operational report. Keep explicit old Insights deep links
// working while the visible rail and search results use the owning module.
//
// RAIL FIT 2026-11-02: `under` puts a report inside its home's own Insights
// lens as a tab instead of a rail item of its own (People and Payroll had 13
// and 14 rail items; the rail scrolled and sliced its labels). The lens key is
// unchanged, so every deep link, ⌘K row and remembered tab still lands on it.
// Hiring, Talent and Learning have no separate Insights lens: theirs IS the
// report, so they stay rail items.
export const INSIGHT_DESTINATIONS = {
    workforce: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "workforce", category: "pb_people_hub_lens", under: "insights" },
    payroll: { xmlid: "pb_payhub.action_pb_pay_hub", lens: "report", category: "pb_payhub_lens", under: "insights" },
    budget: { xmlid: "pb_payhub.action_pb_pay_hub", lens: "budget", category: "pb_payhub_lens", under: "insights" },
    hiring: { xmlid: "pb_hiring.action_pb_hiring_hub", lens: "numbers", category: "pb_hiring_hub_lens" },
    goals: { xmlid: "pb_talent_hub.action_pb_talent_hub", lens: "goal_numbers", category: "pb_talent_hub_lens" },
    training: { xmlid: "pb_learning_hub.action_pb_learning_hub", lens: "numbers", category: "pb_learning_hub_lens" },
};

export function registerModuleInsight(key, definition, options) {
    const destination = INSIGHT_DESTINATIONS[key];
    const placed = destination.under ? { under: destination.under } : {};
    registry.category(destination.category).add(destination.lens, {
        ...definition, ...placed, key: destination.lens, feature: "insights",
    }, options);
}

registerModuleInsight("workforce", {
    icon: "users", label: _t("Workforce"), title: _t("Workforce insights"),
    Component: PbWorkforceInsights, groups: ANALYTICS_GATE,
}, { sequence: 85 });
registerModuleInsight("payroll", {
    icon: "fileText", label: _t("Reports"), title: _t("Payroll report"),
    Component: PayrollReport, groups: PAYSLIP_RUN_GATE,
}, { sequence: 85 });


export class PbInsightsHub extends Component {
    static template = "pb_insights_hub.PbInsightsHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");
        const context = this.props.action?.context || {};
        this.redirect = INSIGHT_DESTINATIONS[context.pb_lens];
        onMounted(() => {
            if (this.redirect) {
                openHub(this.actionService, {
                    ...this.redirect,
                    context: { ...context, pb_lens: this.redirect.lens },
                });
            }
        });

        this.config = {
            key: "insights",                 // -> pbhub.insights.lens.v1
            brand: { label: _t("Insights"), icon: "activity" },
            // FLEET P4. Insights is sold on its own, so a company can be on
            // Payobook without it. The rail entry is the door people FIND;
            // this is the door people already know about — a bookmark, a link
            // from a colleague — and it is why the kit draws a sentence rather
            // than an empty workspace.
            feature: "insights",
            defaultLens: "pulse",
            // The cog, exactly as the pay hub carries it: a configuration
            // errand is a round trip, not a page you have to find your way
            // home from (W5). It names no lens — the chip returns you to the
            // hub, and the hub returns you to the lens it remembers.
            cog: () => this.openSettings(),
            lenses: [
                { key: "pulse", icon: "activity", label: _t("Pulse"),
                  Component: PbInsights, groups: ANALYTICS_GATE },
                { key: "explorer", icon: "compass", label: _t("Explorer"),
                  Component: PbExplorer, groups: ANALYTICS_GATE },
                { key: "reports", icon: "fileText", label: _t("Reports"),
                  Component: PbModuleInsights, groups: ANALYTICS_GATE,
                  props: { area: "all", startTab: "reports" } },
                ...this.extraLenses(),
            ],
        };
    }

    /** Lenses other modules registered, resolved ONCE (never in a getter, W21). */
    extraLenses() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return registry.category(INSIGHTS_LENSES).getAll().map((def) => {
            const props = typeof def.propsFromContext === "function"
                ? def.propsFromContext(ctx) : (def.props || {});
            return { ...def, props };
        });
    }

    /** The cog. A CLICK handler — the shell calls it, nothing else does. */
    openSettings() {
        openHub(this.actionService, {
            // By XMLID, not by tag: a bare tag reaches the shell with no action
            // NAME, and the breadcrumb Settings' own native cards return
            // through then reads "Unnamed" (W98).
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("Insights"), tag: "pb_insights_hub" },
        });
    }
}

registry.category("actions").add("pb_insights_hub", PbInsightsHub);

// The tabs' gates, as the config above declares them, so a lesson and the
// Access home can say "not for you" before anybody opens the hub.
registry.category(HUB_LENS_GATES).add("pb_insights_hub", () => [
    { key: "pulse", groups: ANALYTICS_GATE },
    { key: "explorer", groups: ANALYTICS_GATE },
    { key: "reports", groups: ANALYTICS_GATE },
    ...registry.category(INSIGHTS_LENSES).getAll(),
].map((l) => ({ ...l, hubFeature: "insights" })));
