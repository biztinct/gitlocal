/** @odoo-module **/
/**
 * The Compliance hub's rows in the global ⌘K palette.
 *
 * ⌘K is the one door this cycle: no menu, no rail item, no breadcrumb, and the
 * rail cutover is Cycle 5.
 *
 * **The gate.** The hub-level entry is offered to anyone who could open ANY of
 * its lenses, which is the union of the four gate sets in `compliance_hub.js` —
 * imported from there rather than restated, because a palette gate that drifts
 * from the shell's gate produces one of two silent failures: a row that opens an
 * empty hub, or a hub nobody can find. Since the bank lens is open to every
 * internal user, that union is `base.group_user` and the entry is effectively
 * ungated — which is correct and worth saying out loud, because the union of a
 * broad gate and three narrow ones is always the broad one, and someone reading
 * only the narrow ones would think this was a mistake.
 *
 * Each per-lens row carries its OWN lens's gate, so a persona is never offered a
 * lens the rail would then hide.
 *
 * **The sequence.** IA CYCLE 5 PROMOTED THIS ROW. It shipped at 1200+ as a
 * PREVIEW, after the Pay Run hub's 1000 block and the Insights hub's 1100 one,
 * because the rail cutover had not happened yet. It has now: the row loses
 * "(preview)" and takes mission sequence 160, which is where Compliance sits on
 * the rail. The four LENS rows and the filing-flow verb stay in the 1200 block
 * as deep links.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { FILINGS_GATE, BANK_GATE, YOUNG_GATE, AUDIT_GATE }
    from "@pb_compliance_hub/js/compliance_hub";

const palette = registry.category("pb_hub_palette");

const HUB_TAG = "pb_compliance_hub";
// By XMLID, never by tag — a bare tag leaves a breadcrumb reading "Unnamed"
// (W98); `requires` keeps the registry presence probe.
const HUB_XMLID = "pb_compliance_hub.action_pb_compliance_hub";
const SUB = _t("Compliance Hub");

const HUB_GATE = [...new Set([...FILINGS_GATE, ...BANK_GATE,
                              ...YOUNG_GATE, ...AUDIT_GATE])];

/** The mission row — sixth in the palette, sixth on the rail. */
palette.add("cmphub", {
    id: "cmphub", label: _t("Compliance"), sublabel: _t("Filings & the trail"),
    icon: "shield", groups: HUB_GATE, requires: HUB_TAG,
    action: { xmlid: HUB_XMLID },
}, { sequence: 160 });

const ENTRIES = [
    { id: "cmphub_filings", label: _t("Government filings"), sublabel: SUB,
      icon: "fileText", groups: FILINGS_GATE,
      action: { tag: HUB_TAG, lens: "filings" } },
    { id: "cmphub_bank", label: _t("Bank Verification"), sublabel: SUB,
      icon: "scan", groups: BANK_GATE,
      action: { tag: HUB_TAG, lens: "bank" } },
    { id: "cmphub_young", label: _t("Young Worker Guard"), sublabel: SUB,
      icon: "shield", groups: YOUNG_GATE,
      action: { tag: HUB_TAG, lens: "young" } },
    { id: "cmphub_audit", label: _t("Audit & Compliance"), sublabel: SUB,
      icon: "scrollText", groups: AUDIT_GATE,
      action: { tag: HUB_TAG, lens: "audit" } },
];

ENTRIES.forEach((entry, i) => {
    palette.add(entry.id, entry, { sequence: 1200 + (i + 1) * 10 });
});

/**
 * The filing flow gets its own row, because "generate a filing" is a VERB and a
 * palette is where a verb belongs — it is also the surface this cycle built, so
 * a user who has heard of it must be able to reach it without knowing which
 * board it hangs off.
 *
 * Gated with the filings lens, since it drives the same wizard.
 */
palette.add("filing_flow", {
    id: "filing_flow",
    label: _t("Generate a filing"),
    sublabel: _t("Compliance"),
    icon: "download",
    groups: FILINGS_GATE,
    action: { xmlid: "pb_govt_reports.action_pb_filing_flow" },
    requires: "pb_filing_flow",
}, { sequence: 1260 });
