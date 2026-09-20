/** @odoo-module **/
/**
 * The doors to "Where they work".
 *
 * TWO ⌘K ROWS, IN THE 3380 BLOCK. The group took 3300–3320, the scheme map
 * 3330–3340, the Explorer 3350 and the Decision Room 3360–3370, so this phase
 * starts at 3380: the month strip (3380) and the "Same person?" review (3390,
 * which lands with the review already open rather than on the strip).
 *
 * TIDY P1 — BOTH ROWS NOW LAND ON THE PEOPLE HUB'S `where` LENS rather than on
 * the bare client action. Two roads, one place: the lens on the hub and the
 * ⌘K row arrive at the same screen with the same breadcrumb back to People,
 * so nobody can end up on a version of this screen the other road cannot
 * reach. `focus` carries what the row MEANT — the review, rather than the
 * strip — because a row can be more specific than the lens it opens.
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
    label: _t("Where they work"),
    sublabel: _t("People"),
    icon: "mapPin",
    groups: WORKSEG_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS. The door is the hub's xmlid, so it needs one.
    requires: "pb_assignments",
    action: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "where" },
}, { sequence: 3380 });

palette.add("workseg_same_person", {
    id: "workseg_same_person",
    label: _t("Same person?"),
    sublabel: _t("People"),
    icon: "userCheck",
    groups: WORKSEG_GATE,
    requires: "pb_assignments",
    action: { xmlid: "pb_people_hub.action_pb_people_hub",
              lens: "where", focus: "merge" },
}, { sequence: 3390 });

// Imported so this file's own bundle order is meaningful — the screen is
// registered in its own file, and this one only names doors to it.
export { PbAssignmentsScreen };
