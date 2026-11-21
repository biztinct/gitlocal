/** @odoo-module **/
/**
 * WDGAP S6-C — Expenses › Claims: "How claims are paid" (the company's
 * choice) and, under each row's status, where the money of a pay-run claim
 * is. A patch from this module: no file of pb_expenses_hub is edited.
 */
import { patch } from "@web/core/utils/patch";
import { PbClaimsLens } from "@pb_expenses_hub/js/claims_lens";

patch(PbClaimsLens.prototype, {
    /** May the reader change the company's choice? (server says) */
    get pbCanSetup() {
        return Boolean(this.kit && this.kit.extra && this.kit.extra.pb_can_setup);
    },
    /** The company's choice, in words ("By finance" / "In the next pay run"). */
    get pbPaidBy() {
        return (this.kit && this.kit.extra && this.kit.extra.pb_paid_by) || "";
    },
    /** A CLICK handler: the small form; the list reads again when it closes. */
    openPaySetup() {
        this.action.doAction("pb_expense_payroll.action_pb_expense_pay_setup", {
            onClose: () => this.loadPage(),
        });
    },
});
