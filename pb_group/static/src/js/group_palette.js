/** @odoo-module **/
/**
 * The Group screen's doors.
 *
 *   1. **One panel behind the Settings cog.** Registered into `pb_settings`'s
 *      soft registry (`SETTINGS_CATEGORIES`) rather than imported into its
 *      descriptor, because the dependency runs the other way: this module
 *      depends on the hub, so the hub cannot import this one back.
 *
 *      The shipped categories carry no sequence, so bolted-on ones start at
 *      20; Vendors took 20, so the group sits at **30**. It has TWO cards —
 *      the screen itself and the exchange-rate list — so the hub draws the
 *      section page rather than opening the sole card straight through.
 *
 *   2. **⌘K palette rows, in the 3300 block.** Vendors took 3200, so this
 *      programme starts at 3300: the group (3300), the divisions board
 *      (3310, which asks for the board rather than the top of the page) and
 *      the exchange rates (3320).
 *
 *      Every door is an XMLID and never a bare tag: a bare tag is synthesised
 *      with no action NAME, so anything returning through a breadcrumb lands
 *      on a crumb labelled "Unnamed".
 *
 * NO NEW RAIL ITEM. `pb_sidebar`'s own test asserts the rail exactly, and the
 * rail is eight missions on purpose. A group is set up once and looked at
 * rarely; the cog and ⌘K are the right doors for it.
 *
 * THE GATE IS THE FACADE'S, RESTATED ONCE. A gate that drifts from
 * `pb.group.room`'s produces either a door that can only make an access dialog
 * or a screen the people it was built for cannot find.
 *
 * Every icon comes from the shared `ic()` set in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { PbGroupRoom } from "@pb_group/js/group_room";

/** `pb.group.room`'s own read gate, plus the system escape it also grants. */
export const GROUP_GATE = [
    "pb_group.group_group_admin",
    "hr.group_hr_user",
    "pb_decision_room.group_decision_user",
    "base.group_system",
];

/** Who may actually change any of it. */
export const GROUP_ADMIN_GATE = [
    "pb_group.group_group_admin",
    "base.group_system",
];

// =========================================================== the one panel

const categories = registry.category(SETTINGS_CATEGORIES);

categories.add("group", {
    key: "group",
    icon: "landmark",
    label: _t("Group"),
    blurb: _t("Your companies, the money the board reads in, exchange rates "
              + "and the parts of the business that cross company lines."),
    groups: GROUP_GATE,
    cards: [{
        id: "group",
        // An XMLID and not the bare tag. A bare tag is synthesised with no
        // action NAME, so the moment this screen opens anything of its own —
        // the rate list behind a coverage cell — the breadcrumb back to it
        // reads "Unnamed". Seen, and fixed, in the P1 browser walk.
        xmlid: "pb_group.action_pb_group",
        icon: "landmark",
        label: _t("Your group"),
        sub: _t("The companies in it, the group currency, how rates are "
                + "picked, and your divisions."),
    }, {
        id: "rates",
        xmlid: "pb_group.action_pb_exchange_rates",
        icon: "coins",
        label: _t("Exchange rates"),
        sub: _t("What one currency is worth in another, by date."),
    }],
}, { sequence: 30 });

// ================================================================== the ⌘K

const palette = registry.category("pb_hub_palette");

palette.add("group_home", {
    id: "group_home",
    label: _t("Group"),
    sublabel: _t("Admin"),
    icon: "landmark",
    groups: GROUP_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_group",
    action: { xmlid: "pb_group.action_pb_group" },
}, { sequence: 3300 });

palette.add("group_divisions", {
    id: "group_divisions",
    label: _t("Divisions"),
    sublabel: _t("Group"),
    icon: "layers",
    groups: GROUP_GATE,
    requires: "pb_group",
    // `focus` is what makes a row more specific than its screen: this one
    // lands on the divisions board rather than the top of the page.
    action: { xmlid: "pb_group.action_pb_group", focus: "divisions" },
}, { sequence: 3310 });

palette.add("group_rates", {
    id: "group_rates",
    label: _t("Exchange rates"),
    sublabel: _t("Group"),
    icon: "coins",
    groups: GROUP_GATE,
    requires: "pb_group",
    action: { xmlid: "pb_group.action_pb_exchange_rates" },
}, { sequence: 3320 });

// The component is imported so this file's `requires` probe has something to
// find — the registry entry itself is made in its own file.
export { PbGroupRoom };
