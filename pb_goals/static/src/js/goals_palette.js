/** @odoo-module **/
/**
 * The doors into this module.
 *
 *   1. **The Goals lens on the People hub.** Registered into `pb_people_hub`'s
 *      soft registry (`PEOPLE_LENSES`) rather than imported into its config,
 *      because the dependency runs the other way: this module depends on the
 *      hub, so the hub cannot import this one back.
 *
 *      Records took 40, Assets 50 and Praise 60, so Goals takes **70** — which
 *      is also the right place in the story the rail tells: who works here,
 *      what their record says, what they were handed, what colleagues said
 *      about them, and then what they are working towards.
 *
 *      R63 — THE LENS RAIL'S LABEL BOX IS 60px and it wraps between words but
 *      never inside one. "Goals" is five characters and sits comfortably
 *      inside it — narrower than the shipped "Employees" (61px) and
 *      "Contracts" (63px), which both marginally overflow today — and it is
 *      the same word the employee reads on their own page, which is the more
 *      useful property and the reason P6 and P8 both renamed their surfaces.
 *
 *   2. **⌘K palette rows, in the 3600 block.** A1 took 3500 and stayed there
 *      through A3; E1 took 3900 and stayed there through E3. B1 takes
 *      **3600**, as the wave plan says.
 *
 *      Every door is an XMLID and never a bare tag: a bare tag is synthesised
 *      with no action NAME, so anything returning through a breadcrumb lands
 *      on a crumb labelled "Unnamed". The employee's own page is reached
 *      through an `ir.actions.act_url` record, because the palette contract
 *      knows exactly two doors — a client-action tag and an xmlid — and there
 *      is no URL door (R180).
 *
 *      `requires` is the PRESENCE PROBE: the actions registry holding this
 *      tag is what says the module shipped its JS. Trusting a version number
 *      is what R110/R116 are about.
 *
 * Every icon comes from the shared `ic()` set in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { PbGoalsBoard } from "@pb_goals/js/goals_board";

/**
 * THE LENS IS OPEN TO EVERY MEMBER OF STAFF, AND THAT IS THE WHOLE POINT.
 *
 * The obvious gate — the three goals groups — is wrong, and it was wrong live:
 * a line manager holds NO goals group by definition (they are somebody's
 * manager, not somebody in HR), so the lens the team view exists for was
 * invisible to every manager in the company. The People hub drew no rail at
 * all for them. R157 written down again: the gate that decides what somebody
 * may DO and the gate that decides whether they may LOOK have to agree, and
 * here what they may do is decided by a RECORD rule rather than by a group.
 *
 * So the door is open and the SERVER decides what is behind it —
 * `pb.goals.get_board` answers the HR team the company, a manager their own
 * team, and everybody else their own sheet, with one honest sentence at the
 * top saying which. That is never a dead end: the worst case is somebody
 * looking at their own goals, which is a thing they are entitled to do.
 *
 * The two CONFIGURATION doors below (goal years, templates) keep the HR gate,
 * because those really are the HR team's.
 */
export const GOALS_ANYBODY = ["base.group_user"];

/** The HR side of the ladder — for the configuration doors only. */
export const GOALS_GATE = [
    "pb_goals.group_goals_user",
    "pb_goals.group_goals_manager",
    "pb_goals.group_goals_admin",
];

registry.category(PEOPLE_LENSES).add("goals", {
    key: "goals",
    icon: "target",
    label: _t("Goals"),
    Component: PbGoalsBoard,
    groups: GOALS_ANYBODY,
}, { sequence: 70 });

const palette = registry.category("pb_hub_palette");

palette.add("goals_board", {
    id: "goals_board",
    label: _t("Goals"),
    sublabel: _t("People"),
    icon: "target",
    groups: GOALS_ANYBODY,
    requires: "pb_goals_board",
    action: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "goals" },
}, { sequence: 3600 });

palette.add("goals_my", {
    id: "goals_my",
    label: _t("My goals"),
    sublabel: _t("Your own page"),
    icon: "user",
    groups: ["base.group_user"],
    requires: "pb_goals_board",
    action: { xmlid: "pb_goals.action_my_goals" },
}, { sequence: 3610 });

palette.add("goals_cycles", {
    id: "goals_cycles",
    label: _t("Goal years"),
    sublabel: _t("Goals"),
    icon: "calendar",
    groups: GOALS_GATE,
    requires: "pb_goals_board",
    action: { xmlid: "pb_goals.action_pb_goal_cycle" },
}, { sequence: 3620 });

palette.add("goals_templates", {
    id: "goals_templates",
    label: _t("Goal templates"),
    sublabel: _t("Goals"),
    icon: "sparkles",
    groups: GOALS_GATE,
    requires: "pb_goals_board",
    action: { xmlid: "pb_goals.action_pb_goal_template" },
}, { sequence: 3630 });
