/** @odoo-module **/
/**
 * The Home hub's rows in the global ⌘K palette.
 *
 * Cycle 5 promotes the six missions out of the "(preview)" block they were
 * seeded into: they are now the FIRST thing the palette offers, in rail order,
 * and the old per-surface rows stay below them as deep links. Sequence 110
 * makes Home the first row of the whole palette, which is the same promise the
 * rail makes.
 *
 * **The gate.** The hub-level entry is UNGATED, exactly like the rail item and
 * exactly like the Pulse lens it opens on — `pb.dashboard` answers every caller
 * and narrows itself per read. The Approvals row carries the approvals lens's
 * own gate, imported from `home_hub.js` rather than restated, because a palette
 * gate that drifts from the shell's gate fails silently in one of two
 * directions: a row that opens a lens the rail then hides, or a lens nobody can
 * find.
 *
 * **The door is an XMLID, not a tag** (W98). A bare tag makes the action service
 * synthesise `{type: "ir.actions.client", tag}`, so the `ir.actions.client`
 * RECORD — with its name — is never loaded and anything that later returns
 * through a BREADCRUMB comes back to a crumb labelled "Unnamed". That is
 * invisible on a bespoke cockpit, because none of them render Odoo's control
 * panel; it becomes visible the moment such a surface opens a NATIVE act_window
 * without clearing the breadcrumbs, which is exactly what the People hub's Plan
 * lens does seven times. Found on the Cycle-5 live run, reached through the
 * palette rather than through the rail — the rail navigates by `action_xmlid`
 * and was always correct. `requires` keeps the presence probe: the actions
 * registry is what tells you the module shipped its JS.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { APPROVAL_GATE } from "@pb_home_hub/js/home_hub";

const palette = registry.category("pb_hub_palette");

const HUB_TAG = "pb_home_hub";
const HUB_XMLID = "pb_home_hub.action_pb_home_hub";
const SUB = _t("Home");

/** The mission row. First in the palette, as Home is first on the rail. */
palette.add("homehub", {
    id: "homehub", label: _t("Home"), sublabel: _t("Overview"), icon: "home",
    action: { xmlid: HUB_XMLID }, requires: HUB_TAG,
}, { sequence: 110 });

const LENSES = [
    { id: "homehub_pulse", label: _t("Pulse"), icon: "activity",
      action: { xmlid: HUB_XMLID, lens: "pulse" }, requires: HUB_TAG },
    { id: "homehub_approvals", label: _t("Approvals"), icon: "inbox",
      groups: APPROVAL_GATE, requires: HUB_TAG,
      action: { xmlid: HUB_XMLID, lens: "approvals" } },
];

LENSES.forEach((entry, i) => {
    palette.add(entry.id, { sublabel: SUB, ...entry },
                { sequence: 1300 + (i + 1) * 10 });
});
