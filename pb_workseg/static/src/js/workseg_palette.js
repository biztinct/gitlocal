/** @odoo-module **/
/**
 * The doors to "Where people work".
 *
 * TWO ⌘K ROWS, IN THE 3380 BLOCK. The group took 3300–3320, the scheme map
 * 3330–3340, the Explorer 3350 and the Decision Room 3360–3370, so this phase
 * starts at 3380: the month strip (3380) and the "Same person?" review (3390,
 * which lands with the review already open rather than on the strip).
 *
 * NO NEW RAIL ITEM. `pb_sidebar`'s own test asserts the rail exactly, and the
 * IA programme cut it from thirty-eight items to eight; a ninth whose content
 * is empty on most days is exactly what that work removed.
 *
 * THE DOOR IS AN XMLID AND NEVER A BARE TAG: a bare tag is synthesised with no
 * action NAME, so anything returning through a breadcrumb lands on a crumb
 * reading "Unnamed" (ledger GR8).
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PbAssignmentsScreen } from "@pb_workseg/js/assignments";

/** `pb.assignments`' own read gate, restated once. */
export const WORKSEG_GATE = [
    "pb_workseg.group_workseg_manager",
    "pb_group.group_group_admin",
    "hr.group_hr_user",
    "pb_hr_payroll_formula.group_formula_user",
];

const palette = registry.category("pb_hub_palette");

palette.add("workseg_days", {
    id: "workseg_days",
    label: _t("Where people work"),
    sublabel: _t("People"),
    icon: "calendar",
    groups: WORKSEG_GATE,
    action: { xmlid: "pb_workseg.action_pb_assignments" },
}, { sequence: 3380 });

palette.add("workseg_same_person", {
    id: "workseg_same_person",
    label: _t("Same person?"),
    sublabel: _t("People"),
    icon: "userCheck",
    groups: WORKSEG_GATE,
    action: { xmlid: "pb_workseg.action_pb_same_person" },
}, { sequence: 3390 });

// Imported so this file's own bundle order is meaningful — the screen is
// registered in its own file, and this one only names doors to it.
export { PbAssignmentsScreen };
