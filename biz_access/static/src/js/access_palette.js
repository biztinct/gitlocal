/** @odoo-module **/
/**
 * The doors into the Access home.
 *
 *   1. **Two panels behind the Settings cog.** Registered into the settings
 *      hub's soft registry (`SETTINGS_CATEGORIES`) rather than imported into
 *      its descriptor, because the dependency runs the other way: this module
 *      depends on the hub, so the hub cannot import this one back.
 *
 *      "Access & delegation" is the home itself. "Navigation" REPLACES the
 *      shipped category of the same key — `allCategories()` swaps a shipped
 *      entry for a registered one in place — so the cog keeps the same number
 *      of cards in the order people learnt, and on a database without this
 *      module the two raw list views behind it are still exactly where they
 *      were. Nothing is deleted: both actions stay registered, and the Screens
 *      lens carries a quiet link to them for the day somebody needs the row
 *      itself.
 *
 *      Each category has exactly ONE card, which means the hub's own
 *      `soleCard` rule opens it directly instead of drawing a section page
 *      whose only content is that door.
 *
 *   2. **Command-palette rows.** Every door is an XMLID and never a bare tag:
 *      a bare tag is synthesised with no action NAME, so anything returning
 *      through a breadcrumb lands on a crumb labelled "Unnamed".
 *
 * THE GATES ARE THE FACADE'S, RESTATED ONCE AND IMPORTED EVERYWHERE ELSE. A
 * gate that drifts from the facade's produces either a door that can only make
 * an access dialog or a surface the people it was built for cannot find.
 *
 * AND THE MANAGE GATE IS A REGISTRY, exactly as it is on the server. This
 * module ships its own access-team permission; an application whose own
 * administrator tier should also be able to edit a gate calls
 * `registerAccessManagerGroups()` from its own palette file. The array is
 * mutated in place, and the category descriptors hold a reference to it, so a
 * registration made later still counts.
 *
 * Every icon comes from the shared `ic()` set — no module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { PbAccessBoard } from "@biz_access/js/access_board";

/**
 * `pb.access.BOARD_GROUPS`, verbatim.
 *
 * Everybody with a login, because the "hand my access over" half is for
 * everybody by requirement — a person going on leave should not have to ask an
 * administrator to arrange cover. What each of them then SEES is the record
 * rules' business: an ordinary person sees the catalogue and their own
 * hand-overs, and the grant buttons are simply not drawn for them.
 */
export const ACCESS_GATE = ["base.group_user"];

/** `pb.access.MANAGE_GROUPS`, verbatim — and growable the same way. */
export const ACCESS_MANAGE_GATE = [
    "biz_access.group_access_manager",
    "base.group_system",
];

/** An application adds its own administrator tier to the manage gate. */
export function registerAccessManagerGroups(...xmlids) {
    for (const xmlid of xmlids) {
        if (xmlid && !ACCESS_MANAGE_GATE.includes(xmlid)) {
            // Before `base.group_system`, which stays last so the list reads
            // as "the people who do this, and the person who owns the box".
            ACCESS_MANAGE_GATE.splice(ACCESS_MANAGE_GATE.length - 1, 0, xmlid);
        }
    }
    return ACCESS_MANAGE_GATE;
}

// ============================================================== the panels

const categories = registry.category(SETTINGS_CATEGORIES);

categories.add("access", {
    key: "access",
    icon: "key",
    label: _t("Access & delegation"),
    blurb: _t("Who can do what, said in words — and covering for somebody "
              + "without giving away the building."),
    groups: ACCESS_GATE,
    cards: [{
        id: "access_board",
        tag: "pb_access_board",
        icon: "key",
        label: _t("Access & delegation"),
        sub: _t("Every role in plain English, who holds it, and hand-overs "
                + "that take themselves back."),
    }],
}, { sequence: 30 });

/**
 * NAVIGATION, RE-POINTED AT THE LENS THAT DRAWS IT AS THE MENU.
 *
 * The shipped "Navigation" category offered two raw list views — one row per
 * left-menu entry, with a column of permission-group names. That screen is why
 * a live menu ends up with no gates on it at all: the only place to change one
 * was unreadable, so nobody did. The Screens lens is the same rows drawn as the
 * rail, with the gate said as a ROLE and the people it lets in shown beside it
 * while you edit.
 */
categories.add("nav", {
    key: "nav",
    icon: "compass",
    label: _t("Navigation"),
    blurb: _t("What the left menu offers, who can see each entry, and in what "
              + "order."),
    // The people who can actually CHANGE a gate, which is narrower than the
    // people who may open the Access home. The lens itself is readable by
    // anybody who reaches it — a door that only ever shows somebody their own
    // reality is not a door worth putting on this cog.
    groups: ACCESS_MANAGE_GATE,
    cards: [{
        id: "screens",
        tag: "pb_access_board",
        // The lens to land on, under the hub protocol's own key
        // (`HUB_LENS_KEY`). `openHub` merges a card's `context` and the board
        // reads it on startup — which is how a card deep-links into a lens
        // without either side knowing anything about the other's internals.
        context: { pb_lens: "screens" },
        icon: "compass",
        label: _t("The left menu"),
        sub: _t("Every entry drawn as the menu itself — who can open it, why, "
                + "and in what order."),
    }],
}, { sequence: 15 });

// ================================================== the command palette

const palette = registry.category("pb_hub_palette");

palette.add("va_access", {
    id: "va_access",
    label: _t("Access & delegation"),
    sublabel: _t("Admin"),
    icon: "key",
    groups: ACCESS_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_access_board",
    action: { xmlid: "biz_access.action_pb_access_board" },
}, { sequence: 3210 });

/**
 * "Hand my access to somebody" — the row that makes this reachable for a person
 * who has never opened Settings in their life and is going on leave tomorrow.
 * Gated at `base.group_user` on purpose: it is everybody's, by requirement.
 */
palette.add("va_delegate", {
    id: "va_delegate",
    label: _t("Hand my access to somebody"),
    sublabel: _t("Access"),
    icon: "arrowLeftRight",
    groups: ACCESS_GATE,
    requires: "pb_access_board",
    action: { xmlid: "biz_access.action_pb_access_board" },
}, { sequence: 3220 });

palette.add("va_history", {
    id: "va_history",
    label: _t("Access history"),
    sublabel: _t("Admin"),
    icon: "history",
    groups: ACCESS_MANAGE_GATE,
    requires: "pb_access_board",
    action: { xmlid: "biz_access.action_pb_access_delegation" },
}, { sequence: 3230 });

palette.add("va_roles", {
    id: "va_roles",
    label: _t("Roles"),
    sublabel: _t("Admin"),
    icon: "idCard",
    groups: ACCESS_MANAGE_GATE,
    requires: "pb_access_board",
    action: { xmlid: "biz_access.action_pb_role_profile" },
}, { sequence: 3240 });

palette.add("va_screens", {
    id: "va_screens",
    label: _t("The left menu"),
    sublabel: _t("Access"),
    icon: "compass",
    groups: ACCESS_MANAGE_GATE,
    requires: "pb_access_board",
    action: { xmlid: "biz_access.action_pb_access_board", lens: "screens" },
}, { sequence: 3250 });

// The component is imported so this file's `requires` probes have something to
// find — the registry entry itself is made in its own file.
export { PbAccessBoard };
