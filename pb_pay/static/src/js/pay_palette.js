/** @odoo-module **/
/**
 * The doors to Pay.
 *
 *   1. **The People hub's Pay lens**, at sequence 45 — after Records (40) and
 *      Assets (50)'s neighbours, and before the Plan launcher the hub ships
 *      last, which is the right place in the story: who works here, what their
 *      record says, what we pay them for it, and then what we plan to spend.
 *
 *      Registered into `pb_people_hub`'s lens REGISTRY rather than imported
 *      into its config, because the dependency runs the other way: this module
 *      depends on the hub, so the hub cannot import this one back.
 *
 *      Its gate is this module's own tier list. The facade refuses
 *      independently — it answers an EXPLAINED empty board rather than an
 *      access dialog — so the gate here only decides whether the lens is
 *      offered at all.
 *
 *   2. **SIX ⌘K ROWS, IN THE 3400 BLOCK.** The group took 3300-3320, the
 *      scheme map 3330-3340, the Explorer 3350, the Decision Room 3360-3370
 *      and "Where people work" 3380-3390, so Pay starts at 3400: bands,
 *      fairness and place-a-hire in the first phase, and the review, a new
 *      pay change and "waiting for my approval" in the second.
 *
 * NO NEW RAIL ITEM. `pb_sidebar`'s own test asserts the rail exactly, and the
 * IA programme cut it from thirty-eight items to eight.
 *
 * THE DOOR IS AN XMLID AND NEVER A BARE TAG: a bare tag is synthesised with no
 * action NAME, so anything returning through a breadcrumb lands on a crumb
 * reading "Unnamed" (ledger GR8).
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { PbPayScreen } from "@pb_pay/js/pay_hub";

/** Who is offered Pay. The facade decides who actually gets it. */
export const PAY_GATE = [
    "pb_pay.group_pay_viewer",
    "pb_pay.group_pay_manager",
    "pb_group.group_group_admin",
    "hr.group_hr_manager",
    "base.group_system",
];

registry.category(PEOPLE_LENSES).add("pay", {
    key: "pay",
    icon: "banknote",
    label: _t("Pay"),
    Component: PbPayScreen,
    groups: PAY_GATE,
}, { sequence: 45 });

const HUB_XMLID = "pb_people_hub.action_pb_people_hub";

const palette = registry.category("pb_hub_palette");

palette.add("pay_bands", {
    id: "pay_bands",
    label: _t("Pay bands"),
    sublabel: _t("Pay"),
    icon: "sliders",
    groups: PAY_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_pay",
    action: { xmlid: HUB_XMLID, lens: "pay" },
}, { sequence: 3400 });

palette.add("pay_fairness", {
    id: "pay_fairness",
    label: _t("Fairness"),
    sublabel: _t("Pay"),
    icon: "scale",
    groups: PAY_GATE,
    requires: "pb_pay",
    action: { xmlid: "pb_pay.action_pb_pay_fairness" },
}, { sequence: 3410 });

palette.add("pay_place_hire", {
    id: "pay_place_hire",
    label: _t("Place a new hire"),
    sublabel: _t("Pay"),
    icon: "userPlus",
    groups: PAY_GATE,
    requires: "pb_pay",
    action: { xmlid: "pb_pay.action_pb_pay_place" },
}, { sequence: 3420 });

palette.add("pay_review", {
    id: "pay_review",
    label: _t("Pay review"),
    sublabel: _t("Pay"),
    icon: "checkCircle",
    groups: PAY_GATE,
    requires: "pb_pay",
    action: { xmlid: "pb_pay.action_pb_pay_review" },
}, { sequence: 3430 });

palette.add("pay_new_change", {
    id: "pay_new_change",
    label: _t("New pay change"),
    sublabel: _t("Pay"),
    icon: "pencil",
    groups: PAY_GATE,
    requires: "pb_pay",
    action: { xmlid: "pb_pay.action_pb_pay_change" },
}, { sequence: 3440 });

palette.add("pay_awaiting", {
    id: "pay_awaiting",
    label: _t("Waiting for my approval"),
    sublabel: _t("Pay"),
    icon: "inbox",
    groups: PAY_GATE,
    requires: "pb_pay",
    action: { xmlid: "pb_pay.action_pb_pay_awaiting" },
}, { sequence: 3450 });

// Imported so this file's own bundle order is meaningful — the screen is
// registered in its own file, and this one only names doors to it.
export { PbPayScreen };
