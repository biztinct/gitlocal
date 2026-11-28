/** @odoo-module **/
/**
 * The doors into the Loans board.
 *
 *   1. A lens on the Payroll hub, registered into pb_payhub's soft registry
 *      (`PAY_LENSES`, the awards precedent `comp_ben_palette.js`). Bolted-on
 *      lenses start at 20 (Calendar 20, Awards 30); Loans is 40.
 *   2. A ⌘K palette row, in the 4400 block (hiring holds 4000-4020).
 *
 * Every door is an XMLID and never a bare tag (a bare tag returns through a
 * breadcrumb labelled "Unnamed").
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PAY_LENSES } from "@pb_payhub/js/pay_hub";
import { PbLoansBoard } from "@pb_loans/js/loans_board";

/** `pb.loans._can_read()`, verbatim. */
export const LOANS_GATE = [
    "pb_hr_payroll_base.group_payroll_base_officer",
    "pb_hr_payroll_base.group_payroll_base_manager",
];

registry.category(PAY_LENSES).add("loans", {
    key: "loans",
    icon: "wallet",
    label: _t("Loans"),
    Component: PbLoansBoard,
    groups: LOANS_GATE,
}, { sequence: 40 });

registry.category("pb_hub_palette").add("pl_loans", {
    id: "pl_loans",
    label: _t("Loans and salary advances"),
    sublabel: _t("Payroll"),
    icon: "wallet",
    groups: LOANS_GATE,
    requires: "pb_loans_board",
    action: { xmlid: "pb_payhub.action_pb_pay_hub", lens: "loans" },
}, { sequence: 4400 });
