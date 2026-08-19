/** @odoo-module **/
/**
 * The Insights hub's rows in the global ⌘K palette.
 *
 * Cycle 1 fixed the entry SHAPE and said later cycles add to the registry
 * rather than to `hub_palette_entries.js` — so this file is the whole of the
 * hub's discoverability this cycle. There is no menu, no rail item and no
 * breadcrumb into it; ⌘K is the one door, and the rail cutover is Cycle 5.
 *
 * **The gate.** The hub-level entry is offered to anyone who could open ANY of
 * its lenses, which is the union of the two gate sets in `insights_hub.js` —
 * imported from there rather than restated, because a palette gate that drifts
 * from the shell's gate produces one of two silent failures: a row that opens
 * an empty hub, or a hub nobody can find. The per-lens rows carry their OWN
 * lens's gate, so a persona is never offered a lens the rail would then hide.
 *
 * **The sequence.** IA CYCLE 5 PROMOTED THIS ROW. It shipped at 1100+ as a
 * PREVIEW, below every shipping surface, because the rail cutover had not
 * happened yet. It has now: the row loses "(preview)" and takes mission
 * sequence 150, which is where Insights sits on the rail. The four LENS rows
 * stay in the 1100 block as deep links.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { ANALYTICS_GATE, PAYSLIP_RUN_GATE } from "@pb_insights_hub/js/insights_hub";

const palette = registry.category("pb_hub_palette");

const HUB_TAG = "pb_insights_hub";
// By XMLID, never by tag — a bare tag leaves a breadcrumb reading "Unnamed"
// (W98); `requires` keeps the registry presence probe.
const HUB_XMLID = "pb_insights_hub.action_pb_insights_hub";
const SUB = _t("Insights Hub");

/** Anyone who can open at least one lens can find the hub. */
const HUB_GATE = [...new Set([...ANALYTICS_GATE, ...PAYSLIP_RUN_GATE])];

/** The mission row — fifth in the palette, fifth on the rail. */
palette.add("inshub", {
    id: "inshub", label: _t("Insights"), sublabel: _t("Analytics"),
    icon: "trendingUp", groups: HUB_GATE, requires: HUB_TAG,
    action: { xmlid: HUB_XMLID },
}, { sequence: 150 });

const ENTRIES = [
    { id: "inshub_pulse", label: _t("Insights Pulse"), sublabel: SUB,
      icon: "activity", groups: ANALYTICS_GATE,
      action: { tag: HUB_TAG, lens: "pulse" } },
    { id: "inshub_explorer", label: _t("Analytics Explorer"), sublabel: SUB,
      icon: "compass", groups: ANALYTICS_GATE,
      action: { tag: HUB_TAG, lens: "explorer" } },
    { id: "inshub_workforce", label: _t("Workforce Insights"), sublabel: SUB,
      icon: "users", groups: ANALYTICS_GATE,
      action: { tag: HUB_TAG, lens: "workforce" } },
    { id: "inshub_payroll", label: _t("Payroll Report"), sublabel: SUB,
      icon: "fileText", groups: PAYSLIP_RUN_GATE,
      action: { tag: HUB_TAG, lens: "payroll" } },
];

ENTRIES.forEach((entry, i) => {
    palette.add(entry.id, entry, { sequence: 1100 + (i + 1) * 10 });
});
