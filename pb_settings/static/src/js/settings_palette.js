/** @odoo-module **/
/**
 * The Settings hub's row in the global ⌘K palette.
 *
 * Until the rail cutover (Cycle 5) the hub has exactly two doors: the cog in a
 * hub's command bar, and this. Both are deliberate — a settings surface that can
 * only be reached from inside another surface is one people cannot find when
 * they are not already in that surface.
 *
 * The GROUP is imported, not written. `_t()` returns a new String subclass on
 * every call and the palette keys its section Map on that value, so a local
 * `_t("Admin")` here would render a SECOND "Admin" heading under the first —
 * which is why Cycle 3 exported the two shared headings from the seed file
 * rather than letting every module mint its own.
 *
 * The GATE is the UNION of the hub's own category gates, imported from the hub
 * rather than restated. It has to be a union: the hub shows a formula manager
 * four categories and an administrator four different ones, and an entry gated
 * on one of those tiers alone would hide the door from half the people it was
 * built for. And it has to be imported: two copies of a gate list drift, and
 * the drift is silent in both directions — a palette row that opens the empty
 * state, or a persona who can use Settings and cannot find it.
 *
 * The SEQUENCE is 180. It was 900 — after every shipping surface and before
 * Cycle 2's preview block — because until the rail cutover Settings had no rail
 * item and was a place you went on purpose rather than a destination the
 * product advertised. Cycle 5 gave it the last item on the rail, so the palette
 * says the same: eighth of the eight mission rows, exactly where the cog sits.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { G_ADMIN } from "@pb_hub/js/hub_palette_entries";
import { CATEGORIES } from "@pb_settings/js/settings_hub";

const palette = registry.category("pb_hub_palette");

/** Anyone who can see at least one category can find the hub. */
const GATE = [...new Set(CATEGORIES.flatMap((c) => c.groups || []))];

palette.add("settings", {
    id: "settings",
    label: _t("Settings"),
    sublabel: _t("Admin"),
    icon: "settings",
    group: G_ADMIN,
    // By XMLID (with the tag as the presence probe): opened by tag the action
    // carries no name, and the breadcrumb the native admin cards return
    // through reads "Unnamed".
    action: { xmlid: "pb_settings.action_pb_settings_hub" },
    requires: "pb_settings_hub",
    groups: GATE,
}, { sequence: 180 });
