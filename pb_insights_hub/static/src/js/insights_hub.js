/** @odoo-module **/
/**
 * `pb_insights_hub` — the Insights mission, on Cycle 1's HubShell.
 *
 * Four surfaces that used to be four rail items become four lenses of one
 * workspace, in the order the IA mockup specifies:
 *
 *     pulse · explorer · workforce · payroll
 *
 * That order is a sentence, not a preference: the Pulse is the briefing you
 * open with, the Explorer is where you go to ask it a question, Workforce is
 * the same question about people rather than money, and the Payroll Report is
 * the row-level evidence under both.
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
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";

import { PbInsights } from "@pb_insights/js/insights";
import { PbExplorer } from "@pb_explorer/js/explorer";
import { PbWorkforceInsights } from "@pb_workforce_insights/js/workforce_insights";
import { PayrollReport } from "@pb_hr_workforce/js/payroll_report";

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

export class PbInsightsHub extends Component {
    static template = "pb_insights_hub.PbInsightsHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");

        this.config = {
            key: "insights",                 // -> pbhub.insights.lens.v1
            brand: { label: _t("Insights"), icon: "activity" },
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
                { key: "workforce", icon: "users", label: _t("Workforce"),
                  Component: PbWorkforceInsights, groups: ANALYTICS_GATE },
                { key: "payroll", icon: "fileText", label: _t("Payroll Report"),
                  Component: PayrollReport, groups: PAYSLIP_RUN_GATE },
            ],
        };
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
