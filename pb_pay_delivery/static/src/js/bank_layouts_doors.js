/** @odoo-module **/
/**
 * The doors into Bank layouts (WDGAP S2-C).
 *
 *   1. Settings › Payroll › "Bank layouts". A soft-registry category: the
 *      registry key is WRITTEN OUT, not imported, so this module does not
 *      depend on pb_settings (the pb_leave_setup / pb_blueprint precedent).
 *      One card, so the category opens the screen directly.
 *   2. One ⌘K row.
 *
 * The doors are XMLIDs, never bare tags (R180). The gates are hints; the
 * screen's server methods refuse anybody but the payroll manager.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const GATE = ["om_hr_payroll.group_hr_payroll_manager", "base.group_system"];
const XMLID = "pb_pay_delivery.action_pb_bank_layouts";

registry.category("pb_settings_category").add("bank_layouts", {
    key: "bank_layouts",
    group: "payroll",
    icon: "landmark",
    label: _t("Bank layouts"),
    blurb: _t("The payment files each bank takes, and your own copies of them."),
    groups: GATE,
    cards: [{
        id: "bank_layouts",
        xmlid: XMLID,
        icon: "landmark",
        label: _t("Bank layouts"),
        sub: _t("See the bank file layouts, copy one and shape it to your bank's template."),
    }],
}, { sequence: 33 });

registry.category("pb_hub_palette").add("pay_bank_layouts", {
    id: "pay_bank_layouts",
    label: _t("Bank layouts"),
    sublabel: _t("Settings"),
    icon: "landmark",
    groups: GATE,
    requires: "pb_bank_layouts",
    action: { xmlid: XMLID },
}, { sequence: 2190 });
