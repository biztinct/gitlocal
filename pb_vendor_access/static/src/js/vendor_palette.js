/** @odoo-module **/
/**
 * The doors into the vendor register — and the one line that tells the generic
 * access module about this product's own administrator tier.
 *
 *   1. **One panel behind the Settings cog.** Registered into `pb_settings`'s
 *      soft registry (`SETTINGS_CATEGORIES`) rather than imported into its
 *      descriptor, because the dependency runs the other way: this module
 *      depends on the hub, so the hub cannot import this one back.
 *
 *      The shipped categories carry no sequence, so bolted-on ones start at
 *      20: **Vendors 20**, and the Access home's two panels (Navigation 15,
 *      Access & delegation 30) are registered by `biz_access` itself. This one
 *      has exactly ONE card, which means the hub's own `soleCard` rule opens
 *      it directly instead of drawing a section page whose only content is
 *      that door.
 *
 *   2. **⌘K palette rows, in the 3200 block.** `hub_palette_entries.js`
 *      auto-numbers its seeded deep links into the 2000s and grows (R41); P2
 *      took 2200, P3 2400, P4 2500, P5 2600, P6 2700, P7 2800, P8 2900, P9
 *      3000 and P10 3100, so P11 starts at **3200**. The access rows sit at
 *      3210-3250 and now live in `biz_access`.
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
import { registerAccessManagerGroups } from "@biz_access/js/access_palette";
import { PbVendorsBoard } from "@pb_vendor_access/js/vendors_board";

/**
 * WHO ELSE MANAGES ACCESS ON THIS PRODUCT — the browser half of the same
 * registration `vendor_common.py` makes on the server. On this product a
 * lifecycle administrator also gives and takes roles, so the generic module is
 * TOLD that rather than being made to know it.
 */
registerAccessManagerGroups("pb_lifecycle.group_lifecycle_admin");

/** `pb.vendors.GATE_GROUPS`, verbatim, plus the system escape it also grants. */
export const VENDOR_GATE = [
    "pb_vendor_access.group_vendor_user",
    "pb_vendor_access.group_vendor_manager",
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

// =========================================================== the one panel

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

// The component is imported so this file's `requires` probe has something to
// find — the registry entry itself is made in its own file.
export { PbVendorsBoard };
