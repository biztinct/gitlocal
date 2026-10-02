/** @odoo-module **/
/**
 * The doors to "Who is paid by what".
 *
 * TWO ⌘K ROWS, IN THE 3330 BLOCK. The group took 3300–3320 (ledger P1), so
 * this phase starts at 3330: the map itself (3330) and the people nobody pays
 * (3340, which lands with the exceptions list already open rather than at the
 * top of the board).
 *
 * NO NEW RAIL ITEM and NO NEW SETTINGS CATEGORY. The map is not a place of its
 * own: it is one of the Mapping screen's boards, next to the other things that
 * are wired on that surface, and `pb_sidebar`'s own test asserts the rail
 * exactly. Both rows are therefore doors into the Mapping screen with the
 * scheme board asked for by name.
 *
 * THE DOOR IS AN XMLID AND NEVER A BARE TAG: a bare tag is synthesised with no
 * action NAME, so anything returning through a breadcrumb lands on a crumb
 * reading "Unnamed" (ledger GR8).
 *
 * `focus` is the only thing the palette forwards besides the destination
 * itself, so the board is asked for through `pb_focus` — "scheme" for the
 * board, "scheme:exceptions" for the board with its list open. The Mapping
 * screen reads both.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { SchemeMapBoard } from "@pb_scheme_map/js/scheme_map_board";

/** `pb.scheme.board`'s own read gate, restated once. */
export const SCHEME_MAP_GATE = [
    "pb_hr_payroll_formula.group_formula_user",
    "om_hr_payroll.group_hr_payroll_user",
    "hr.group_hr_user",
    "base.group_system",
];

const palette = registry.category("pb_hub_palette");

palette.add("scheme_map", {
    id: "scheme_map",
    label: _t("Who is paid by what"),
    sublabel: _t("Payroll"),
    icon: "gitMerge",
    groups: SCHEME_MAP_GATE,
    // The presence probe is the MAPPING screen: without it there is no surface
    // for this board to appear on, and a row that opens nothing is worse than
    // a row that was never offered.
    requires: "pb_mapping_studio",
    action: {
        xmlid: "pb_formula_studio.action_pb_mapping_studio",
        focus: "scheme",
    },
}, { sequence: 3330 });

palette.add("scheme_map_exceptions", {
    id: "scheme_map_exceptions",
    label: _t("People not covered"),
    sublabel: _t("Payroll"),
    icon: "userX",
    groups: SCHEME_MAP_GATE,
    requires: "pb_mapping_studio",
    action: {
        xmlid: "pb_formula_studio.action_pb_mapping_studio",
        focus: "scheme:exceptions",
    },
}, { sequence: 3340 });

// Imported so this file's own bundle order is meaningful — the board is
// registered in its own file, and this one only names doors to it.
export { SchemeMapBoard };
