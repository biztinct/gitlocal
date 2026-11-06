/** @odoo-module **/
/**
 * The Org chart's rows in the global ⌘K palette (ORG CHART P4 §1.5).
 *
 * THE 2950 BLOCK. Every hundred-block from 2600 to 2900 is taken (2600–2640,
 * 2700–2730, 2800–2840, 2900–2940 — counted with a grep over every
 * `*_palette.js`, 2026-11-05), so the chart takes the free tail of the 29xx
 * block: 2950–2980.
 *
 * All four rows land on the People hub's `orgchart` lens (an XMLID, never a
 * bare tag: a bare tag leaves an "Unnamed" breadcrumb — GR8/W98). `focus`
 * says what a row MEANT, and the lens reads it (`wantsArrival`):
 *   "me"      — focused on the reader's own card, their team open
 *   "plan"    — planning mode opened (HR users only)
 *   "suggest" — the Suggest a chart dialog (HR users only)
 * `requires` is the presence probe: the actions registry holding the
 * `pb_orgchart` tag says this module shipped its JS.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { EMPLOYEE_GATE } from "@pb_people_hub/js/people_hub";

const palette = registry.category("pb_hub_palette");
const HUB = "pb_people_hub.action_pb_people_hub";
/** Who may change the chart — the server's `_may_write()` restated for the row gate. */
const WRITE_GATE = ["hr.group_hr_user", "base.group_system"];

palette.add("orgchart", {
    id: "orgchart",
    label: _t("Org chart"),
    sublabel: _t("People"),
    icon: "network",
    groups: EMPLOYEE_GATE,
    requires: "pb_orgchart",
    action: { xmlid: HUB, lens: "orgchart" },
}, { sequence: 2950 });

palette.add("orgchart_me", {
    id: "orgchart_me",
    label: _t("Who reports to me?"),
    sublabel: _t("People · Org chart"),
    icon: "crosshair",
    groups: EMPLOYEE_GATE,
    requires: "pb_orgchart",
    action: { xmlid: HUB, lens: "orgchart", focus: "me" },
}, { sequence: 2960 });

palette.add("orgchart_plan", {
    id: "orgchart_plan",
    label: _t("Plan org chart changes"),
    sublabel: _t("People · Org chart"),
    icon: "pencil",
    groups: WRITE_GATE,
    requires: "pb_orgchart",
    action: { xmlid: HUB, lens: "orgchart", focus: "plan" },
}, { sequence: 2970 });

palette.add("orgchart_suggest", {
    id: "orgchart_suggest",
    label: _t("Suggest a chart"),
    sublabel: _t("People · Org chart"),
    icon: "wand",
    groups: WRITE_GATE,
    requires: "pb_orgchart",
    action: { xmlid: HUB, lens: "orgchart", focus: "suggest" },
}, { sequence: 2980 });
