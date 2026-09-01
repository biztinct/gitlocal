/** @odoo-module **/
/**
 * The doors into this module.
 *
 *   1. **Two lenses on the Pay Run hub.** Registered into pb_payhub's soft
 *      registry rather than imported into its config, because the dependency
 *      runs the other way: this module depends on the hub, so the hub cannot
 *      import this one back. `pb_payhub` had no such registry — its eight
 *      lenses are a literal array — so P7 added ONE: the exported constant
 *      `PAY_LENSES` and an `extraLenses()` spread at the end of the list, an
 *      exact clone of `pb_people_hub`'s (`people_hub.js:113`). That is the
 *      whole of the edit to pb_payhub.
 *
 *      The eight shipped lenses carry no sequence, so bolted-on ones start at
 *      20 and land after them: **Calendar 20, Awards 30**. Calendar first
 *      because it is the question that comes first — when does this close —
 *      and Awards second because it is work you do inside that window.
 *
 *   2. **⌘K palette rows, in the 2800 block.** `hub_palette_entries.js`
 *      auto-numbers its seeded deep links to 2370 and grows (R41); P2 took
 *      2200, P3 2400, P4 2500, P5 2600 and P6 2700, so P7 starts at **2800**.
 *      Count the seed file rather than trusting the comment in it.
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
import { PAY_LENSES } from "@pb_payhub/js/pay_hub";
import { PbPaycalBoard } from "@pb_comp_ben/js/paycal_board";
import { PbIncentivesBoard } from "@pb_comp_ben/js/incentives_board";

/** `pb.paycal._can_read()` / `pb.incentives._can_read()`, verbatim. */
export const COMP_GATE = [
    "pb_comp_ben.group_comp_user",
    "pb_comp_ben.group_comp_head",
];

registry.category(PAY_LENSES).add("paycal", {
    key: "paycal",
    icon: "calendar",
    // R63 — the lens rail's label box is 60px and it wraps between words but
    // never inside one. "Calendar" measures well inside it; "Payroll calendar"
    // would not.
    label: _t("Calendar"),
    Component: PbPaycalBoard,
    groups: COMP_GATE,
}, { sequence: 20 });

registry.category(PAY_LENSES).add("awards", {
    key: "awards",
    icon: "award",
    label: _t("Awards"),
    Component: PbIncentivesBoard,
    groups: COMP_GATE,
}, { sequence: 30 });

const HUB_XMLID = "pb_payhub.action_pb_pay_hub";
const SUB = _t("Pay Run Hub");
const palette = registry.category("pb_hub_palette");

palette.add("cb_paycal", {
    id: "cb_paycal",
    label: _t("Payroll calendar"),
    sublabel: SUB,
    icon: "calendar",
    groups: COMP_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_comp_ben_paycal",
    action: { xmlid: HUB_XMLID, lens: "paycal" },
}, { sequence: 2800 });

palette.add("cb_awards", {
    id: "cb_awards",
    label: _t("Awards"),
    sublabel: SUB,
    icon: "award",
    groups: COMP_GATE,
    requires: "pb_comp_ben_incentives",
    action: { xmlid: HUB_XMLID, lens: "awards" },
}, { sequence: 2810 });

palette.add("cb_packages", {
    id: "cb_packages",
    label: _t("Pay packages"),
    sublabel: _t("Pay & benefits"),
    icon: "banknote",
    groups: COMP_GATE,
    requires: "pb_comp_ben_incentives",
    action: { xmlid: "pb_comp_ben.action_pb_employee_comp" },
}, { sequence: 2820 });

palette.add("cb_benefits", {
    id: "cb_benefits",
    label: _t("Benefit plans"),
    sublabel: _t("Pay & benefits"),
    icon: "umbrella",
    groups: COMP_GATE,
    requires: "pb_comp_ben_incentives",
    action: { xmlid: "pb_comp_ben.action_pb_benefit_plan" },
}, { sequence: 2830 });

palette.add("cb_my_pay", {
    id: "cb_my_pay",
    label: _t("My pay package"),
    sublabel: _t("Your own page"),
    icon: "user",
    groups: ["base.group_user"],
    requires: "pb_comp_ben_incentives",
    // The palette contract knows exactly two doors — `{tag}` and `{xmlid}` —
    // so the person's own page is reached through an `ir.actions.act_url`
    // record rather than a raw URL the palette would not understand.
    action: { xmlid: "pb_comp_ben.action_my_compensation" },
}, { sequence: 2840 });
