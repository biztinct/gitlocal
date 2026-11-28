/** @odoo-module **/
/**
 * The doors into "Past-month re-work".
 *
 *   1. A lens on the Payroll hub, registered into pb_payhub's soft registry
 *      (`PAY_LENSES`, the Loans / Fund payments precedent). Bolted-on lenses
 *      start at 20 (Calendar 20, Awards 30, Loans 40, Funds & tax 45); this
 *      one is 50.
 *   2. One ⌘K palette row, in the 4400 block (Loans 4400, Fund payments 4410;
 *      this one 4420).
 *
 * Every door is an XMLID and never a bare tag (a bare tag returns through a
 * breadcrumb labelled "Unnamed").
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PAY_LENSES } from "@pb_payhub/js/pay_hub";
import { PbRetroBoard } from "@pb_retro/js/retro_board";

/** `pb.retro.review._pb_may_use()`'s group: the people who approve or reopen
 *  a pay run. Administrators are let in by the server too. */
export const RETRO_GATE = ["om_hr_payroll.group_hr_payroll_manager"];

registry.category(PAY_LENSES).add("retro", {
    key: "retro",
    icon: "history",
    label: _t("Past months"),
    Component: PbRetroBoard,
    groups: RETRO_GATE,
}, { sequence: 50 });

registry.category("pb_hub_palette").add("pl_retro", {
    id: "pl_retro",
    label: _t("Past-month re-work"),
    sublabel: _t("Payroll"),
    icon: "history",
    groups: RETRO_GATE,
    requires: "pb_retro_board",
    action: { xmlid: "pb_payhub.action_pb_pay_hub", lens: "retro" },
}, { sequence: 4420 });
