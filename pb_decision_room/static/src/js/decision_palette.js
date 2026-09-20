/** @odoo-module **/
/**
 * The room's three doors.
 *
 *   1. **The People hub's Plan lens.** The lens key does not change and no new
 *      rail item appears: what changes is what the Plan lens LANDS on. The
 *      launcher reads one registry — `pb_people_hub_plan_hero` — and renders
 *      the first thing in it above the legacy cards, which fold away under
 *      "Classic planning tools". A REGISTRY rather than an import because the
 *      dependency runs the other way: this module depends on the hub, so the
 *      hub cannot import this one back.
 *
 *   2. **⌘K palette rows**, in the 2300 deep-link block, clear of the Assets
 *      block at 2200. The door is an XMLID and not a bare tag: a bare tag is
 *      synthesised with no action NAME, so anything returning through a
 *      breadcrumb lands on a crumb labelled "Unnamed".
 *
 *   3. **The Home hub's own lens.** The owner's day starts on Home, and the
 *      room is a thing an owner opens on the way to a board meeting rather
 *      than a thing they navigate to through People. It is the SAME component
 *      mounted in a second shell — only the lens-memory key differs — so
 *      there is no second copy of the room to keep in step with the first.
 *
 *   4. `/odoo/action-pb_decision_room` — the standalone action record, for a
 *      deep link or a bookmark. The component renders the same, with the back
 *      chip the arrival protocol gives it.
 *
 * The gate here only decides whether the door is OFFERED. `pb.decision.room`
 * refuses independently and answers an EXPLAINED empty room rather than an
 * access dialog.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PLAN_HERO } from "@pb_people_hub/js/plan_launcher";
import { HOME_LENSES } from "@pb_home_hub/js/home_hub";
import { PbDecisionRoom } from "@pb_decision_room/js/decision_room";

/** Who is offered the room. The facade decides who actually gets it. */
export const DECISION_GATE = [
    "pb_decision_room.group_decision_user",
    "pb_decision_room.group_decision_manager",
    "base.group_system",
];

registry.category(PLAN_HERO).add("decision_room", {
    id: "decision_room",
    Component: PbDecisionRoom,
    groups: DECISION_GATE,
}, { sequence: 10 });

/**
 * The Home lens.
 *
 * `feature: "people_plan"` is the same switch that governs the People hub's
 * Plan lens, so a tenant that has planning turned off does not get it back
 * through a second door. The mapping the shell reads for the deep-link form
 * of the same lens lives in `pb_hub/static/src/js/hub_features.js`.
 */
registry.category(HOME_LENSES).add("decide", {
    key: "decide",
    icon: "target",
    label: _t("Decision Room"),
    Component: PbDecisionRoom,
    groups: DECISION_GATE,
    feature: "people_plan",
}, { sequence: 30 });

const HUB_XMLID = "pb_people_hub.action_pb_people_hub";

const palette = registry.category("pb_hub_palette");

palette.add("decision_room", {
    id: "decision_room",
    label: _t("Decision Room"),
    sublabel: _t("People"),
    icon: "target",
    groups: DECISION_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_decision_room",
    action: { xmlid: HUB_XMLID, lens: "plan" },
}, { sequence: 2300 });

palette.add("decision_room_plans", {
    id: "decision_room_plans",
    label: _t("Saved plans"),
    sublabel: _t("Decision Room"),
    icon: "layers",
    groups: DECISION_GATE,
    requires: "pb_decision_room",
    action: { xmlid: HUB_XMLID, lens: "plan", focus: "plans" },
}, { sequence: 2310 });

/**
 * GROUP Phase 4 — the two doors a group needs, in the 3300 block the group
 * programme owns (3300/3310/3320 are Phase 1's, 3330/3340 Phase 2's, 3350
 * Phase 3's).
 *
 * "Plan the group" carries the scope in its own arrival, so the room opens on
 * the group rather than on whatever the reader last looked at — a ⌘K row that
 * lands somewhere other than where its words said is worse than no row.
 */
palette.add("decision_room_group", {
    id: "decision_room_group",
    label: _t("Plan the group"),
    sublabel: _t("Decision Room"),
    icon: "globe",
    groups: DECISION_GATE,
    requires: "pb_decision_room",
    action: { xmlid: HUB_XMLID, lens: "plan", focus: "group" },
}, { sequence: 3360 });

palette.add("decision_room_approvals", {
    id: "decision_room_approvals",
    label: _t("Plans awaiting approval"),
    sublabel: _t("Decision Room"),
    icon: "checkCircle",
    groups: ["pb_decision_room.group_decision_manager", "base.group_system"],
    requires: "pb_decision_room",
    action: { xmlid: HUB_XMLID, lens: "plan", focus: "plans" },
}, { sequence: 3370 });
