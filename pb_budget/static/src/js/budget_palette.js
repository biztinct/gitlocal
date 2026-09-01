/** @odoo-module **/
/**
 * The doors into this module.
 *
 *   1. **The Budget lens on the Insights mission.** Registered into
 *      `pb_insights_hub`'s soft registry (`INSIGHTS_LENSES`) rather than
 *      imported into its config, because the dependency runs the other way:
 *      this module depends on the hub, so the hub cannot import this one back.
 *
 *      `pb_insights_hub` had no such registry — its four lenses were a literal
 *      array — so this change adds ONE, exactly as P7 added the same thing to
 *      `pb_payhub` (R73) and P8 to `pb_home_hub` (R83): the exported constant
 *      `INSIGHTS_LENSES` and an `extraLenses()` spread at the end of the list.
 *      That is the whole of the edit to pb_insights_hub, it is JS only, and it
 *      needs the asset cache purged rather than a `-u`.
 *
 *      The four shipped lenses carry no sequence, so bolted-on ones start at
 *      20. Budget takes **20** and lands after the Payroll Report — what
 *      happened first, and what it was supposed to cost after.
 *
 *      R63 — THE LENS RAIL'S LABEL BOX IS 60px and it wraps between words but
 *      never inside one. "Budget" is six characters and measures well inside
 *      it — and it is the same word the person reads at the top of the lens,
 *      in the spreadsheet it exports and on the tile in their own function.
 *
 *   2. **⌘K palette rows, in the 3000 block.** `hub_palette_entries.js`
 *      auto-numbers its seeded deep links into the 2000s and grows (R41); P2
 *      took 2200, P3 2400, P4 2500, P5 2600, P6 2700, P7 2800 and P8 2900, so
 *      P9 starts at **3000**.
 *
 *      Every door is an XMLID and never a bare tag: a bare tag is synthesised
 *      with no action NAME, so anything returning through a breadcrumb lands on
 *      a crumb labelled "Unnamed".
 *
 * Every icon comes from the shared `ic()` set in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { INSIGHTS_LENSES } from "@pb_insights_hub/js/insights_hub";
import { PbBudgetBoard } from "@pb_budget/js/budget_board";

/**
 * `pb.budget._require()`, verbatim, plus the system escape it also grants.
 * The facade refuses independently — this only decides what is OFFERED, and a
 * gate that drifts from the facade's produces either a door that can only make
 * an error or a surface nobody can find.
 */
export const BUDGET_GATE = [
    "pb_budget.group_budget_viewer",
    "pb_budget.group_budget_manager",
    "pb_budget.group_budget_finance",
    "base.group_system",
];

registry.category(INSIGHTS_LENSES).add("budget", {
    key: "budget",
    icon: "gauge",
    label: _t("Budget"),
    Component: PbBudgetBoard,
    groups: BUDGET_GATE,
}, { sequence: 20 });

const palette = registry.category("pb_hub_palette");

palette.add("bdg_board", {
    id: "bdg_board",
    label: _t("Budget"),
    sublabel: _t("Insights"),
    icon: "gauge",
    groups: BUDGET_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_budget_board",
    action: { xmlid: "pb_insights_hub.action_pb_insights_hub", lens: "budget" },
}, { sequence: 3000 });

palette.add("bdg_upload", {
    id: "bdg_upload",
    label: _t("Upload a budget"),
    sublabel: _t("Budgets"),
    icon: "upload",
    groups: ["pb_budget.group_budget_manager", "base.group_system"],
    requires: "pb_budget_board",
    action: { xmlid: "pb_budget.action_pb_budget_upload" },
}, { sequence: 3010 });

palette.add("bdg_expenses", {
    id: "bdg_expenses",
    label: _t("What HR and the office spent"),
    sublabel: _t("Budgets"),
    icon: "receipt",
    groups: BUDGET_GATE,
    requires: "pb_budget_board",
    action: { xmlid: "pb_budget.action_pb_budget_expense" },
}, { sequence: 3020 });

palette.add("bdg_rows", {
    id: "bdg_rows",
    label: _t("Budget rows"),
    sublabel: _t("Budgets"),
    icon: "list",
    groups: BUDGET_GATE,
    requires: "pb_budget_board",
    action: { xmlid: "pb_budget.action_pb_budget_rows" },
}, { sequence: 3030 });
