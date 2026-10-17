/** @odoo-module **/
/**
 * The door to "Compare schemes".
 *
 * ONE ⌘K ROW, AT 3350. The group took 3300–3320 (GROUP P1) and the scheme map
 * 3330–3340 (P2), so this phase's row is 3350.
 *
 * NO NEW RAIL ITEM and NO NEW SETTINGS CATEGORY: comparing schemes is not a
 * place of its own, it is one of the Explorer's starting points, and
 * `pb_sidebar`'s own test asserts the rail exactly. The row is therefore a
 * door into the Explorer with the comparison asked for by name.
 *
 * THE DOOR IS AN XMLID AND NEVER A BARE TAG: a bare tag is synthesised with no
 * action NAME, so anything returning through a breadcrumb lands on a crumb
 * reading "Unnamed" (ledger GR8).
 *
 * `focus` is the only thing the palette forwards besides the destination, so
 * the lens is asked for through `pb_focus` — the Explorer reads it in `setup`.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/** `pb.explorer`'s own read gate, restated once. */
export const EXPLORER_GATE = [
    "pb_hr_payroll_base.group_payroll_base_manager",
    "pb_hr_payroll_base.group_payroll_analytics_user",
    "pb_hr_payroll_base.group_payroll_super_admin",
    "base.group_system",
];

registry.category("pb_hub_palette").add("explorer_compare", {
    id: "explorer_compare",
    label: _t("Compare schemes"),
    sublabel: _t("Analytics"),
    icon: "gitMerge",
    groups: EXPLORER_GATE,
    action: {
        xmlid: "pb_explorer.action_pb_explorer",
        focus: "compare",
    },
}, { sequence: 3350 });
