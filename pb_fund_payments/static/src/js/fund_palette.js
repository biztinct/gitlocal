/** @odoo-module **/
/**
 * The doors into the Fund & tax payments board.
 *
 *   1. A lens on the Payroll hub, registered into pb_payhub's soft registry
 *      (`PAY_LENSES`, the Loans precedent). Bolted-on lenses start at 20
 *      (Calendar 20, Awards 30, Loans 40); this one is 45.
 *   2. A ⌘K palette row, in the 4400 block (Loans 4400; this one 4410).
 *
 * Every door is an XMLID and never a bare tag (a bare tag returns through a
 * breadcrumb labelled "Unnamed").
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PAY_LENSES } from "@pb_payhub/js/pay_hub";
import { PbFundPaymentsBoard } from "@pb_fund_payments/js/fund_board";

/** `pb.fund.payments._can_read()`'s groups (the finance roles are let in by
 *  the server too; the hub hides the tab only for nobody else). */
export const FUND_GATE = [
    "om_hr_payroll.group_hr_payroll_user",
    "om_hr_payroll.group_hr_payroll_manager",
];

registry.category(PAY_LENSES).add("fundpay", {
    key: "fundpay",
    icon: "landmark",
    label: _t("Funds & tax"),
    Component: PbFundPaymentsBoard,
    groups: FUND_GATE,
}, { sequence: 45 });

registry.category("pb_hub_palette").add("pl_fund_payments", {
    id: "pl_fund_payments",
    label: _t("Fund and tax payments"),
    sublabel: _t("Payroll"),
    icon: "landmark",
    groups: FUND_GATE,
    requires: "pb_fund_payments_board",
    action: { xmlid: "pb_payhub.action_pb_pay_hub", lens: "fundpay" },
}, { sequence: 4410 });
