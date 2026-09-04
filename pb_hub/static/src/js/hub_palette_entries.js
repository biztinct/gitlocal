/** @odoo-module **/
/**
 * The `pb_hub_palette` registry, seeded with today's surfaces.
 *
 * Entry shape (this IS the contract; later cycles add to the registry, not to
 * this file):
 *
 *   registry.category("pb_hub_palette").add(id, {
 *       id,                                  // must equal the registry key
 *       label,                               // what the user types and reads
 *       sublabel,                            // where it lives / what it is
 *       icon,                                // a key in pb_import_kit's IC
 *       group:   "Surfaces" | "Admin",       // the palette's section header
 *       action:  { tag } | { xmlid },        // exactly one door
 *                { lens, lensKey },          // optional arrival lens
 *       groups:  [group xmlid, …],           // ANY-of; omitted = ungated
 *       requires: "<client action tag>",     // presence probe for xmlid doors
 *   }, { sequence });
 *
 * Two rules the seeds obey, both of them scar tissue:
 *
 *  1. **Every gate mirrors the rail item that owns the same door.** A palette
 *     that offers a surface the facade would refuse is W29's door that can only
 *     produce an error, reached through a second entrance. Where the rail item
 *     is ungated, so is the entry — the facade still enforces its own (W12).
 *  2. **No entry names a door that does not exist here.** The tag entries are
 *     probed against the client-actions registry at open time (see the service);
 *     the two xmlid entries carry a `requires` tag from the same module, except
 *     `base.action_res_users`, which is in `base`.
 *
 * ---------------------------------------------------------------------------
 * IA CYCLE 5 — THE PROMOTION.
 *
 * Until the rail cutover these were the palette: thirty-six surfaces at
 * sequences 10-360, with the four hubs added below them as "(preview)" rows in
 * a 900-1200 block. The rail is now six missions plus Learn and Settings, so
 * the palette says the same thing the rail does: the eight MISSION rows sit at
 * 110-180, and everything in this file moves DOWN into a 2000 block, where it
 * stays as a deep link.
 *
 * Nothing is removed. A deep link to Payslips, to the Explorer or to Bank
 * Verification is still exactly the right thing to type when you know which
 * screen you want, and every one of those client actions still exists (the
 * cutover retired rail ENTRIES, never surfaces). What changes is which rows a
 * user sees when they open the palette and type nothing.
 *
 * Two of the rows here are missions rather than deep links, because their
 * modules own the rail item and there is no hub module to declare them: Mission
 * Control (140) and Learn (170). They carry an explicit `seq` for that reason,
 * and the loop below honours it — a per-entry override rather than a second
 * list, so the reading order of this file stays the order it has always had.
 * ---------------------------------------------------------------------------
 *
 * Mission Control's eight lenses are sub-entries, and they are the one place a
 * `lensKey` appears: `pb_mission` reads its lens from `pb_shell_lens`, because
 * it forwards `pb_lens` unchanged to the Time hub embedded inside it. Sending
 * plain `pb_lens` would therefore open Mission Control on the REMEMBERED lens
 * and hand the Time hub a view name it has never heard of. Not refactoring
 * pb_mission is a binding non-goal of this cycle, so the palette speaks its
 * vocabulary instead.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { GROUP_DEFAULT } from "@pb_hub/js/hub_palette";

const palette = registry.category("pb_hub_palette");

// The two section headers, as SHARED lazy strings. Shared on purpose: the
// palette groups its rows into a Map keyed by this value, and `_t()` returns a
// new String subclass on every call — a fresh one per entry would give every
// row its own "Surfaces" heading.
//
// EXPORTED (Cycle 3) for exactly that reason: a later module adding an Admin
// row cannot write `_t("Admin")` of its own — it would be a different object,
// the Map would key on it separately, and the palette would grow a SECOND
// "Admin" heading under the first. There is one of each, and this is where it
// lives.
// Re-exported from the COMPONENT rather than minted here: the palette's grouped
// render falls back to its own `GROUP_DEFAULT` for any row that names no group,
// and two `_t("Surfaces")` calls are two different objects in the Map that
// render two identical headings (see the note beside GROUP_DEFAULT).
export { GROUP_DEFAULT as G_SURFACES } from "@pb_hub/js/hub_palette";
export const G_ADMIN = _t("Admin");

const OFFICER = "pb_hr_payroll_base.group_payroll_base_officer";
const MANAGER = "pb_hr_payroll_base.group_payroll_base_manager";
const SUPER = "pb_hr_payroll_base.group_payroll_super_admin";
const INTEGRATION = "pb_hr_payroll_base.group_payroll_integration_user";
const FINAL_APPROVER = "pb_hr_payroll_base.group_payroll_final_approver";
const ANALYTICS_USER = "pb_hr_payroll_base.group_payroll_analytics_user";
const ANALYTICS_MGR = "pb_hr_payroll_base.group_payroll_analytics_manager";
const PAYROLL_MGR = "om_hr_payroll.group_hr_payroll_manager";
const PAYROLL_USER = "om_hr_payroll.group_hr_payroll_user";
const SYSTEM = "base.group_system";

const ANALYTICS = [ANALYTICS_USER, ANALYTICS_MGR, MANAGER, FINAL_APPROVER, SUPER];
const OPS = [OFFICER, MANAGER, SUPER];

/** Registered in reading order; `sequence` is what the palette's list obeys. */
const ENTRIES = [
    // ------------------------------------------------------------ everyday
    { id: "dashboard", label: _t("Dashboard"), sublabel: _t("Overview"), icon: "home",
      action: { tag: "pb_dashboard" } },
    { id: "approvals", label: _t("Approvals"), sublabel: _t("Overview"), icon: "inbox",
      action: { tag: "pb_approval" },
      groups: [OFFICER, MANAGER, FINAL_APPROVER, SUPER] },

    // ------------------------------------------------------------- pay run
    { id: "payrun_wizard", label: _t("Run Payroll"), sublabel: _t("Pay Run"), icon: "zap",
      action: { tag: "pb_payrun_wizard" }, groups: OPS },
    { id: "payruns", label: _t("Pay Runs"), sublabel: _t("Pay Run"), icon: "calendar",
      action: { xmlid: "pb_payruns.action_pb_payruns_kanban" },
      requires: "pb_payruns" },
    { id: "payslips", label: _t("Payslips"), sublabel: _t("Pay Run"), icon: "receipt",
      action: { tag: "pb_payslip_review" } },
    { id: "results", label: _t("Results Grid"), sublabel: _t("Pay Run"), icon: "table",
      action: { tag: "pb_payrun_results" } },
    { id: "import", label: _t("Import Data"), sublabel: _t("Pay Run"), icon: "download",
      action: { tag: "pb_import" },
      groups: [OFFICER, MANAGER, INTEGRATION, SUPER] },
    { id: "pay_delivery", label: _t("Pay & Deliver"), sublabel: _t("Pay Run"), icon: "send",
      action: { tag: "pb_pay_delivery" },
      groups: [PAYROLL_MGR, "account.group_account_invoice",
               "account.group_account_user"] },
    { id: "fullfinal", label: _t("Full & Final"), sublabel: _t("Pay Run"), icon: "file",
      action: { tag: "pb_fullfinal" } },
    { id: "proration", label: _t("Proration Audit"), sublabel: _t("Pay Run"),
      icon: "percent", action: { tag: "pb_proration" } },
    { id: "retro", label: _t("Retro Adjustments"), sublabel: _t("Pay Run"), icon: "rotate",
      action: { tag: "pb_retro" } },

    // -------------------------------------------------------------- people
    { id: "employees", label: _t("Employees"), sublabel: _t("People"), icon: "users",
      action: { tag: "pb_people" }, groups: OPS },
    { id: "contracts", label: _t("Contracts"), sublabel: _t("People"), icon: "file",
      action: { tag: "pb_contracts" }, groups: OPS },

    // ----------------------------------------------------------- workforce
    // The hub itself, then its eight lenses. `pb_shell_lens` — see the header.
    // A MISSION, not a deep link: this is OPERATE > Workforce on the rail, and
    // its item lives in pb_mission rather than in a hub module of its own.
    { id: "workforce", label: _t("Workforce"), sublabel: _t("Mission Control"),
      icon: "compass", seq: 140, action: { tag: "pb_workforce" } },
    { id: "wf_today", label: _t("Today"), sublabel: _t("Mission Control"), icon: "activity",
      action: { tag: "pb_workforce", lens: "today", lensKey: "pb_shell_lens" } },
    { id: "wf_schedule", label: _t("Schedule"), sublabel: _t("Mission Control"),
      icon: "calendar",
      action: { tag: "pb_workforce", lens: "schedule", lensKey: "pb_shell_lens" } },
    { id: "wf_time", label: _t("Time"), sublabel: _t("Mission Control"), icon: "clock",
      action: { tag: "pb_workforce", lens: "time", lensKey: "pb_shell_lens" } },
    { id: "wf_timeoff", label: _t("Time Off"), sublabel: _t("Mission Control"),
      icon: "umbrella",
      action: { tag: "pb_workforce", lens: "timeoff", lensKey: "pb_shell_lens" } },
    { id: "wf_overtime", label: _t("Overtime"), sublabel: _t("Mission Control"), icon: "zap",
      action: { tag: "pb_workforce", lens: "overtime", lensKey: "pb_shell_lens" } },
    { id: "wf_trips", label: _t("Trips"), sublabel: _t("Mission Control"), icon: "plane",
      action: { tag: "pb_workforce", lens: "trips", lensKey: "pb_shell_lens" } },
    { id: "wf_approvals", label: _t("Team Approvals"), sublabel: _t("Mission Control"),
      icon: "inbox",
      action: { tag: "pb_workforce", lens: "approvals", lensKey: "pb_shell_lens" } },
    { id: "wf_close", label: _t("Close the week"), sublabel: _t("Mission Control"),
      icon: "lock",
      action: { tag: "pb_workforce", lens: "close", lensKey: "pb_shell_lens" } },

    // ------------------------------------------------------------- insight
    { id: "insights", label: _t("Insights"), sublabel: _t("Analytics"), icon: "trendingUp",
      action: { tag: "pb_insights" }, groups: ANALYTICS },
    { id: "explorer", label: _t("Explorer"), sublabel: _t("Analytics"), icon: "compass",
      action: { tag: "pb_explorer_cockpit" }, groups: ANALYTICS },
    { id: "workforce_insights", label: _t("Workforce Analytics"),
      sublabel: _t("Analytics"), icon: "users",
      action: { tag: "pb_workforce_insights" }, groups: ANALYTICS },

    // ---------------------------------------------------------- compliance
    { id: "govt_reports", label: _t("Government Reports"), sublabel: _t("Compliance"),
      icon: "fileText", action: { tag: "pb_govt_reports" } },
    { id: "bank_ocr", label: _t("Bank Verification"), sublabel: _t("Compliance"),
      icon: "scan", action: { tag: "pb_bank_ocr" }, groups: [PAYROLL_USER] },
    { id: "young_worker", label: _t("Young Workers"), sublabel: _t("Compliance"),
      icon: "shield", action: { tag: "pb_young_worker" }, groups: [PAYROLL_USER] },

    // --------------------------------------------------------------- setup
    { id: "formula_studio", label: _t("Formula Engine"), sublabel: _t("Setup"),
      icon: "calculator", action: { tag: "pb_formula_studio" }, groups: OPS },
    { id: "structures", label: _t("Salary Structures"), sublabel: _t("Setup"),
      icon: "layers", action: { tag: "pb_structures" }, groups: [MANAGER, SUPER] },
    { id: "statutory", label: _t("Statutory"), sublabel: _t("Setup"), icon: "shield",
      action: { tag: "pb_statutory" }, groups: [MANAGER, SUPER] },
    { id: "integrations", label: _t("Integrations"), sublabel: _t("Setup"),
      icon: "database", action: { tag: "pb_integrations" },
      groups: [INTEGRATION, MANAGER, SUPER] },
    // Integrations Cycle 2. Gated exactly like Integrations: the studio reads
    // and writes the same connectors and field mappings, so an entry offered
    // more widely would be an entry that can only produce an access dialog.
    { id: "mapping_studio", label: _t("Mapping"), sublabel: _t("Setup"),
      icon: "gitMerge", action: { tag: "pb_mapping_studio" },
      groups: [INTEGRATION, MANAGER, SUPER] },

    // --------------------------------------------------------------- learn
    // A MISSION too: GROW > Learn, whose rail item is generated data owned by
    // pb_learn.
    { id: "learn", label: _t("Learn"), sublabel: _t("Guides"), icon: "bookOpen",
      seq: 170, action: { tag: "learn_journey" } },

    // --------------------------------------------------------------- admin
    { id: "audit", label: _t("Audit Trail"), sublabel: _t("Admin"), icon: "scrollText",
      group: G_ADMIN, action: { tag: "pb_audit" }, groups: [PAYROLL_MGR] },
    { id: "tenants", label: _t("Tenants"), sublabel: _t("Admin"), icon: "building",
      group: G_ADMIN, action: { tag: "pb_tenants" }, groups: [SYSTEM] },
    { id: "roles", label: _t("Roles & Access"), sublabel: _t("Admin"), icon: "lock",
      group: G_ADMIN, action: { xmlid: "base.action_res_users" },
      groups: [SYSTEM] },
];

/**
 * 2000+ unless the entry names its own sequence.
 *
 * The mission rows are 110-180 and they are declared by the modules that own
 * the rail item; everything seeded here is a DEEP LINK and belongs after them,
 * in the reading order this file has always had. `seq` is the override for the
 * two entries above that are missions with no hub module of their own.
 */
export const DEEP_LINK_BASE = 2000;

ENTRIES.forEach((entry, i) => {
    const { seq, ...row } = entry;
    palette.add(entry.id, { group: GROUP_DEFAULT, ...row },
                { sequence: seq || DEEP_LINK_BASE + (i + 1) * 10 });
});
