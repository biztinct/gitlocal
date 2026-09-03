/** @odoo-module **/
/**
 * `pb_compliance_hub` — the Compliance mission, on Cycle 1's HubShell.
 *
 * Four surfaces become four lenses of one workspace, in the order an obligation
 * actually arrives:
 *
 *     filings · bank · young · audit
 *
 * What you owe an authority, what you owe an employee's bank account, who you
 * may not schedule after eight in the evening, and the trail that proves all
 * three. Every lens is the EXISTING cockpit mounted with `embedded: true`
 * (W17). The hub owns no model, no ACL and no RPC — each facade keeps its own
 * gate regardless of what this file says (W12).
 *
 * ---------------------------------------------------------------------------
 * The gates (W95: derived from the model behind the door, never copied from the
 * rail item that used to open it)
 *
 * All four answers are DIFFERENT, and that is the whole argument for the rule.
 * A hub that gated its four lenses on one "compliance" group would hide the
 * bank cockpit from the employees whose bank details it exists to collect, and
 * would offer the audit console to a payroll officer whose first click gets an
 * AccessError.
 *
 *   filings   `pb.govt.report.wizard` has exactly one `ir.model.access` row and
 *             it names `pb_hr_govt.group_pb_hr_govt_user`, which itself implies
 *             the payroll-user group. One group, and no more.
 *
 *   bank      `pb.bank.change.request` grants read+write+create to
 *             `base.group_user`: on this surface an employee uploads their own
 *             bank letter. The cockpit's own `_is_hr` / `_is_finance` decide
 *             what ELSE they see — the queues, the approvals — so the lens is
 *             correctly open to every internal user and narrow inside.
 *
 *   young     `pb.young.worker.guard` is abstract and enforces
 *             `_require_access()`: HR user OR attendance officer (plus admin).
 *             The `pb.young.worker.rule` ACL says payroll user / manager /
 *             system, which is the same population reached from the other side;
 *             the facade is the tighter and more accurate statement, so it is
 *             the one used.
 *
 *   audit     `pb.audit.console._require_manager()`: payroll MANAGER or
 *             `base.group_system`. This is the lens that proves the gating
 *             works — a payroll officer sees three lenses, not four.
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

import { PbGovtReports } from "@pb_govt_reports/js/govt_reports";
import { PbBankOcr } from "@pb_bank_ocr/js/pb_bank_ocr";
import { PbYoungWorker } from "@pb_young_worker/js/pb_young_worker";
import { PbAudit } from "@pb_audit/js/pb_audit";

/** `pb.govt.report.wizard`'s only ACL row. */
export const FILINGS_GATE = ["pb_hr_govt.group_pb_hr_govt_user"];

/** `pb.bank.change.request` — every internal user, on purpose. */
export const BANK_GATE = ["base.group_user"];

/** `pb.young.worker.guard._require_access()`, verbatim. */
export const YOUNG_GATE = [
    "om_hr_payroll.group_hr_payroll_user",
    "hr_attendance.group_hr_attendance_officer",
];

/** `pb.audit.console._require_manager()`, verbatim. */
export const AUDIT_GATE = [
    "om_hr_payroll.group_hr_payroll_manager",
    "base.group_system",
];

export class PbComplianceHub extends Component {
    static template = "pb_compliance_hub.PbComplianceHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");

        this.config = {
            key: "compliance",               // -> pbhub.compliance.lens.v1
            brand: { label: _t("Compliance"), icon: "shield" },
            // FLEET P4. The whole mission is one part of the product; two of
            // its four lenses are ALSO sold on their own, so a company can
            // have Compliance without bank statement scanning. The narrower
            // switch is the one on the lens.
            feature: "compliance",
            defaultLens: "filings",
            cog: () => this.openSettings(),
            lenses: [
                { key: "filings", icon: "fileText", label: _t("Filings"),
                  Component: PbGovtReports, groups: FILINGS_GATE,
                  // The board's Generate buttons open the filing flow, and the
                  // flow needs a way back to the LENS the user left, not to the
                  // standalone board they never opened. The descriptor comes
                  // from here because pb_govt_reports must not know the name of
                  // a hub built after it (the C3 `connectorBack` precedent).
                  props: {
                      action: { context: { pb_back: {
                          label: _t("Compliance"), tag: "pb_compliance_hub",
                          xmlid: "", lens: "filings", lensKey: "pb_lens",
                          context: {},
                      } } },
                  } },
                { key: "bank", icon: "scan", label: _t("Bank"),
                  Component: PbBankOcr, groups: BANK_GATE,
                  feature: "bank_ocr" },
                { key: "young", icon: "shield", label: _t("Young workers"),
                  Component: PbYoungWorker, groups: YOUNG_GATE,
                  feature: "young_workers" },
                { key: "audit", icon: "scrollText", label: _t("Audit"),
                  Component: PbAudit, groups: AUDIT_GATE },
            ],
        };
    }

    /** The cog. A CLICK handler — the shell calls it, nothing else does. */
    openSettings() {
        openHub(this.actionService, {
            // By XMLID: a bare tag reaches the shell with no action NAME, and
            // the breadcrumb Settings' own native cards return through then
            // reads "Unnamed" (W98).
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("Compliance"), tag: "pb_compliance_hub" },
        });
    }
}

registry.category("actions").add("pb_compliance_hub", PbComplianceHub);
