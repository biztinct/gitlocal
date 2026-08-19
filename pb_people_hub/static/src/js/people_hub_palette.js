/** @odoo-module **/
/**
 * The People hub's rows in the global ⌘K palette.
 *
 * The mission row sits at 130 — third in the palette, third on the rail. Its
 * gate is the UNION of the three lens gates, imported from the modules that own
 * them rather than restated, because a palette gate that drifts from the
 * shell's produces one of two silent failures: a row that opens a hub with no
 * lenses in it, or a hub nobody can find.
 *
 * The three lens rows sit in a 1400 block, after the other hubs' lens blocks,
 * in the order the missions were built.
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
import { EMPLOYEE_GATE, CONTRACT_GATE } from "@pb_people_hub/js/people_hub";
import { PLAN_GATE } from "@pb_people_hub/js/plan_launcher";

const palette = registry.category("pb_hub_palette");

const HUB_TAG = "pb_people_hub";
const HUB_XMLID = "pb_people_hub.action_pb_people_hub";
const SUB = _t("People");

/** Anyone who can open at least one lens can find the hub. */
const HUB_GATE = [...new Set([...EMPLOYEE_GATE, ...CONTRACT_GATE, ...PLAN_GATE])];

palette.add("peoplehub", {
    id: "peoplehub", label: _t("People"), sublabel: _t("Employees & contracts"),
    icon: "users", groups: HUB_GATE, requires: HUB_TAG,
    action: { xmlid: HUB_XMLID },
}, { sequence: 130 });

const LENSES = [
    { id: "peoplehub_employees", label: _t("Employees"), icon: "users",
      groups: EMPLOYEE_GATE, requires: HUB_TAG,
      action: { xmlid: HUB_XMLID, lens: "employees" } },
    { id: "peoplehub_contracts", label: _t("Contracts"), icon: "file",
      groups: CONTRACT_GATE, requires: HUB_TAG,
      action: { xmlid: HUB_XMLID, lens: "contracts" } },
    { id: "peoplehub_plan", label: _t("Workforce Planning"), icon: "trendingUp",
      groups: PLAN_GATE, requires: HUB_TAG,
      action: { xmlid: HUB_XMLID, lens: "plan" } },
];

LENSES.forEach((entry, i) => {
    palette.add(entry.id, { sublabel: SUB, ...entry },
                { sequence: 1400 + (i + 1) * 10 });
});
