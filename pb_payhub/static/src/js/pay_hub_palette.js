/** @odoo-module **/
/**
 * The Pay Run hub's rows in the global ⌘K palette.
 *
 * Cycle 1 fixed the entry SHAPE and said that later cycles add to the registry
 * rather than to `hub_palette_entries.js` — so this file is the whole of the
 * hub's discoverability this cycle. There is no menu, no rail item and no
 * breadcrumb into it; ⌘K is the one door, and the rail cutover is Cycle 5.
 *
 * Two decisions worth stating.
 *
 * **The gate.** Every payroll surface the hub absorbs is reachable today from
 * a rail item, and those items are gated at the pb_hr_payroll_base OFFICER /
 * MANAGER / SUPER tiers or not at all. The hub is not a wider door than the
 * surfaces inside it (each lens re-asks its own question through HubShell's
 * `groups`, and each facade keeps its own gate regardless, W12), but a PREVIEW
 * of an unfinished IA should not be offered to every reader of a payslip
 * either. `om_hr_payroll.group_hr_payroll_user` is the group the handover named
 * and it exists on this database (`pb_hub`'s own registry already gates the
 * Bank Verification and Young Workers entries on it); the payroll ops tiers are
 * listed beside it because `groups` is ANY-of and an Officer who does not
 * happen to hold the om_ group must still find the hub.
 *
 * **The sequence.** IA CYCLE 5 PROMOTED THIS ROW. It shipped at 1000+ — after
 * every surface in the palette — because until the rail cutover it was a
 * PREVIEW of an IA that did not exist yet, and a preview that outranks the
 * thing it previews is a navigation change. The cutover made it the rail, so
 * the row loses "(preview)" and takes mission sequence 120: second in the
 * palette, second on the rail. The eight LENS rows stay in the 1000 block,
 * where they are deep links like every other per-surface row.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const palette = registry.category("pb_hub_palette");

const HUB_TAG = "pb_pay_hub";
// By XMLID, never by tag: a bare tag leaves any breadcrumb this hub opens
// reading "Unnamed" (W98). `requires` keeps the registry presence probe.
const HUB_XMLID = "pb_payhub.action_pb_pay_hub";
const SUB = _t("Pay Run Hub");

const OFFICER = "pb_hr_payroll_base.group_payroll_base_officer";
const MANAGER = "pb_hr_payroll_base.group_payroll_base_manager";
const SUPER = "pb_hr_payroll_base.group_payroll_super_admin";
const PAYROLL_USER = "om_hr_payroll.group_hr_payroll_user";
const GATE = [PAYROLL_USER, OFFICER, MANAGER, SUPER];

/**
 * The hub, then its eight lenses — the Mission Control pattern from C1, with
 * one difference that matters: these carry NO `lensKey`. `pb_mission` reads
 * `pb_shell_lens` because it forwards `pb_lens` to the Time hub embedded inside
 * it; a plain pb_hub shell reads `pb_lens`, which is `openHub`'s default.
 */
/** The mission row. Second in the palette, as Pay Run is second on the rail. */
palette.add("payhub", {
    id: "payhub", label: _t("Pay Run"), sublabel: _t("Payroll operations"),
    icon: "zap", groups: GATE, requires: HUB_TAG,
    action: { xmlid: HUB_XMLID },
}, { sequence: 120 });

const ENTRIES = [
    { id: "payhub_run", label: _t("Run Payroll"), sublabel: SUB, icon: "zap",
      action: { tag: HUB_TAG, lens: "run" } },
    { id: "payhub_runs", label: _t("Pay Runs"), sublabel: SUB, icon: "calendar",
      action: { tag: HUB_TAG, lens: "runs" } },
    { id: "payhub_payslips", label: _t("Payslips"), sublabel: SUB, icon: "receipt",
      action: { tag: HUB_TAG, lens: "payslips" } },
    { id: "payhub_results", label: _t("Results Grid"), sublabel: SUB, icon: "table",
      action: { tag: HUB_TAG, lens: "results" } },
    { id: "payhub_import", label: _t("Import Data"), sublabel: SUB, icon: "download",
      action: { tag: HUB_TAG, lens: "import" } },
    { id: "payhub_deliver", label: _t("Pay & Deliver"), sublabel: SUB, icon: "send",
      action: { tag: HUB_TAG, lens: "deliver" } },
    { id: "payhub_adjust", label: _t("Adjust — retro & proration"), sublabel: SUB,
      icon: "percent", action: { tag: HUB_TAG, lens: "adjust" } },
    { id: "payhub_settle", label: _t("Settle — full & final"), sublabel: SUB,
      icon: "file", action: { tag: HUB_TAG, lens: "settle" } },
];

ENTRIES.forEach((entry, i) => {
    palette.add(entry.id, { groups: GATE, ...entry }, { sequence: 1000 + (i + 1) * 10 });
});
