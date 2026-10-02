/** @odoo-module **/
/**
 * The doors into this module.
 *
 *   1. **The Praise lens on the People hub.** Registered into
 *      `pb_people_hub`'s soft registry (`PEOPLE_LENSES`) rather than imported
 *      into its config, because the dependency runs the other way: this module
 *      depends on the hub, so the hub cannot import this one back. Records took
 *      40 and P2's Assets took 50, so Praise takes **60** — after what a person
 *      IS and what they were GIVEN, before the Plan launcher the hub ships
 *      last. That is the right place in the story: who works here, what their
 *      record says, what they were handed, what colleagues said about them, and
 *      then what we plan to spend.
 *
 *      R63 — THE LENS RAIL'S LABEL BOX IS 60px and it wraps between words but
 *      never inside one. "Recognition" is eleven characters with no break in it
 *      and measures wider than the rail, exactly as "Improvement" did; the
 *      label is therefore **"Praise"**, which fits comfortably and — the more
 *      useful property, and the reason P6 renamed its own surface — is the same
 *      word the employee reads on their own page and on the wall.
 *
 *   2. **The recognition wall on the Home mission.** `pb_home_hub` had no soft
 *      lens registry — its two lenses were a literal array — so this change adds
 *      ONE, exactly as P7 added the same thing to `pb_payhub`: the exported
 *      constant `HOME_LENSES` and an `extraLenses()` spread at the end of the
 *      list, a clone of `pb_people_hub`'s (`people_hub.js:113`). That is the
 *      whole of the edit to pb_home_hub, it is JS only, and it needs the asset
 *      cache purged rather than a `-u`.
 *
 *      The two shipped lenses carry no sequence, so bolted-on ones start at 20.
 *      The wall takes **20** and lands after Pulse and Approvals — what needs
 *      you first, what people said about each other second.
 *
 *      The wall is UNGATED, deliberately, exactly like the Pulse lens beside
 *      it: `pb.rnr.wall.get_wall()` reads nothing a colleague may not see, and
 *      a wall behind a permission is a cupboard.
 *
 *   3. **⌘K palette rows, in the 2900 block.** `hub_palette_entries.js`
 *      auto-numbers its seeded deep links to 2370 and grows (R41); P2 took
 *      2200, P3 2400, P4 2500, P5 2600, P6 2700 and P7 2800, so P8 starts at
 *      **2900**. Count the seed file rather than trusting the comment in it.
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
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { HOME_LENSES } from "@pb_home_hub/js/home_hub";
import { PbRnrBoard } from "@pb_rnr/js/rnr_board";
import { PbRnrWall } from "@pb_rnr/js/rnr_wall";

/** `pb.rnr._can_read()`, verbatim. The facade refuses independently. */
export const RNR_GATE = [
    "pb_rnr.group_rnr_user",
    "pb_rnr.group_rnr_manager",
];

registry.category(PEOPLE_LENSES).add("praise", {
    key: "praise",
    icon: "award",
    label: _t("Praise"),
    Component: PbRnrBoard,
    groups: RNR_GATE,
}, { sequence: 60 });

registry.category(HOME_LENSES).add("wall", {
    key: "wall",
    icon: "sparkles",
    label: _t("Wall"),
    Component: PbRnrWall,
}, { sequence: 20 });

const palette = registry.category("pb_hub_palette");

palette.add("rnr_wall", {
    id: "rnr_wall",
    label: _t("The recognition wall"),
    sublabel: _t("Home"),
    icon: "sparkles",
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_rnr_wall",
    action: { xmlid: "pb_home_hub.action_pb_home_hub", lens: "wall" },
}, { sequence: 2900 });

palette.add("rnr_board", {
    id: "rnr_board",
    label: _t("Praise"),
    sublabel: _t("People"),
    icon: "award",
    groups: RNR_GATE,
    requires: "pb_rnr_board",
    action: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "praise" },
}, { sequence: 2910 });

palette.add("rnr_values", {
    id: "rnr_values",
    label: _t("Company values"),
    sublabel: _t("Recognition"),
    icon: "shieldCheck",
    groups: RNR_GATE,
    requires: "pb_rnr_board",
    action: { xmlid: "pb_rnr.action_pb_company_value" },
}, { sequence: 2920 });

palette.add("rnr_cycles", {
    id: "rnr_cycles",
    label: _t("Recognition quarters"),
    sublabel: _t("Recognition"),
    icon: "calendar",
    groups: RNR_GATE,
    requires: "pb_rnr_board",
    action: { xmlid: "pb_rnr.action_pb_rnr_cycle" },
}, { sequence: 2930 });

palette.add("rnr_my", {
    id: "rnr_my",
    label: _t("My praise"),
    sublabel: _t("Your own page"),
    icon: "user",
    groups: ["base.group_user"],
    requires: "pb_rnr_wall",
    // The palette contract knows exactly two doors — `{tag}` and `{xmlid}` —
    // so the person's own page is reached through an `ir.actions.act_url`
    // record rather than a raw URL the palette would not understand.
    action: { xmlid: "pb_rnr.action_my_recognition" },
}, { sequence: 2940 });
