/** @odoo-module **/
/**
 * Expenses' rows in the global ⌘K palette (NAV P2). The mission row sits at
 * 145, after Workforce (140) and before Insights (150) — the rail's order.
 * The old words keep finding it (R10).
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { CLAIMS_GATE } from "@pb_expenses_hub/js/expenses_hub";

const palette = registry.category("pb_hub_palette");
const HUB_XMLID = "pb_expenses_hub.action_pb_expenses_hub";

palette.add("expenseshub", {
    id: "expenseshub",
    label: _t("Expenses"),
    sublabel: _t("Trips and expense claims"),
    icon: "wallet",
    // Mirrors the menu entry's permission lanes (rule 1 of the palette seeds).
    groups: ["hr.group_hr_user", ...CLAIMS_GATE],
    requires: "pb_expenses_hub",
    action: { xmlid: HUB_XMLID },
    keywords: ["trips", "travel", "business trip", "claims", "expense",
               "công tác", "chuyến đi", "chi phí"],
}, { sequence: 145 });

palette.add("expenseshub_claims", {
    id: "expenseshub_claims",
    label: _t("Expense claims"),
    sublabel: _t("Expenses"),
    icon: "receipt",
    groups: CLAIMS_GATE,
    requires: "pb_expenses_hub",
    action: { xmlid: HUB_XMLID, lens: "claims" },
    keywords: ["claims", "receipts"],
}, { sequence: 1360 });
