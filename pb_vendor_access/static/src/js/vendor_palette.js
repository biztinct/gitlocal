/** @odoo-module **/
/**
 * The doors into this module.
 *
 *   1. **Two panels behind the Settings cog.** Registered into `pb_settings`'s
 *      soft registry (`SETTINGS_CATEGORIES`) rather than imported into its
 *      descriptor, because the dependency runs the other way: this module
 *      depends on the hub, so the hub cannot import this one back.
 *
 *      `pb_settings` had no such registry — its eight categories were a
 *      literal array — so this change adds ONE, exactly as P7 added the same
 *      thing to `pb_payhub` (R73), P8 to `pb_home_hub` (R83) and P9 to
 *      `pb_insights_hub` (R96): an exported category name, an `extraCategories`
 *      resolver and an `allCategories` spread that every rule in the hub then
 *      reads. That is the whole of the edit to pb_settings, it is JS ONLY, and
 *      it needs the asset cache purged rather than a `-u` (R110 — the bundle
 *      does not always rebuild, and the check that matters is reading the
 *      registry in the browser rather than trusting a version number).
 *
 *      The eight shipped categories carry no sequence, so bolted-on ones start
 *      at 20: **Vendors 20, Access & delegation 30**. Each has exactly ONE
 *      card, which means the hub's own `soleCard` rule opens it directly
 *      instead of drawing a section page whose only content is that door.
 *
 *   2. **⌘K palette rows, in the 3200 block.** `hub_palette_entries.js`
 *      auto-numbers its seeded deep links into the 2000s and grows (R41); P2
 *      took 2200, P3 2400, P4 2500, P5 2600, P6 2700, P7 2800, P8 2900, P9
 *      3000 and P10 3100, so P11 starts at **3200**.
 *
 *      Every door is an XMLID and never a bare tag: a bare tag is synthesised
 *      with no action NAME, so anything returning through a breadcrumb lands on
 *      a crumb labelled "Unnamed".
 *
 * THE GATES ARE THE FACADES', RESTATED ONCE AND IMPORTED EVERYWHERE ELSE. A
 * gate that drifts from the facade's produces either a door that can only make
 * an access dialog (W29) or a surface the people it was built for cannot find.
 *
 * Every icon comes from the shared `ic()` set in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { PbVendorsBoard } from "@pb_vendor_access/js/vendors_board";
import { PbAccessBoard } from "@pb_vendor_access/js/access_board";

/** `pb.vendors.GATE_GROUPS`, verbatim, plus the system escape it also grants. */
export const VENDOR_GATE = [
    "pb_vendor_access.group_vendor_user",
    "pb_vendor_access.group_vendor_manager",
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

/**
 * `pb.access.BOARD_GROUPS`, verbatim.
 *
 * Everybody with a login, because the "hand my access over" half is for
 * everybody by requirement — a person going on leave should not have to ask HR
 * to arrange cover. What each of them then SEES is the record rules' business:
 * an ordinary person sees the catalogue and their own hand-overs, and the grant
 * buttons are simply not drawn for them.
 */
export const ACCESS_GATE = ["base.group_user"];

/** Only the people who may grant on somebody else's behalf. */
export const ACCESS_MANAGE_GATE = [
    "pb_vendor_access.group_access_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

// =========================================================== the two panels

const categories = registry.category(SETTINGS_CATEGORIES);

categories.add("vendors", {
    key: "vendors",
    icon: "briefcase",
    label: _t("Vendors"),
    blurb: _t("The agencies, trainers, insurers and software suppliers HR "
              + "deals with — and when their agreements run out."),
    groups: VENDOR_GATE,
    cards: [{
        id: "vendors_board",
        tag: "pb_vendors_board",
        icon: "briefcase",
        label: _t("Vendors"),
        sub: _t("Who we use, who here looks after them, and what has been "
                + "agreed."),
    }],
}, { sequence: 20 });

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

// ================================================================== the ⌘K

const palette = registry.category("pb_hub_palette");

palette.add("va_vendors", {
    id: "va_vendors",
    label: _t("Vendors"),
    sublabel: _t("Admin"),
    icon: "briefcase",
    groups: VENDOR_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_vendors_board",
    action: { xmlid: "pb_vendor_access.action_pb_vendors_board" },
}, { sequence: 3200 });

palette.add("va_access", {
    id: "va_access",
    label: _t("Access & delegation"),
    sublabel: _t("Admin"),
    icon: "key",
    groups: ACCESS_GATE,
    requires: "pb_access_board",
    action: { xmlid: "pb_vendor_access.action_pb_access_board" },
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
    action: { xmlid: "pb_vendor_access.action_pb_access_board" },
}, { sequence: 3220 });

palette.add("va_history", {
    id: "va_history",
    label: _t("Access history"),
    sublabel: _t("Admin"),
    icon: "history",
    groups: ACCESS_MANAGE_GATE,
    requires: "pb_access_board",
    action: { xmlid: "pb_vendor_access.action_pb_access_delegation" },
}, { sequence: 3230 });

palette.add("va_roles", {
    id: "va_roles",
    label: _t("Roles"),
    sublabel: _t("Admin"),
    icon: "idCard",
    groups: ACCESS_MANAGE_GATE,
    requires: "pb_access_board",
    action: { xmlid: "pb_vendor_access.action_pb_role_profile" },
}, { sequence: 3240 });

// The components are imported so this file's `requires` probes have something
// to find — the registry entries themselves are made in their own files.
export { PbVendorsBoard, PbAccessBoard };
