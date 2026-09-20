/** @odoo-module **/
/**
 * The PIP lens's doors.
 *
 *   1. **The Lifecycle hub's PIP lens.** Registered into P0's lens registry
 *      rather than imported into its config, because the dependency runs the
 *      other way: this module depends on the hub, so the hub cannot import
 *      this one back. The shipped Journeys lens carries no sequence, P3's
 *      New joiners took 20, P4's Exits 30 and P5's Probation 40, so this takes
 *      **50** — last, which is right in the story as well as in the number:
 *      everything running, the people arriving, the people leaving, the people
 *      still being decided about, and then the ones somebody is trying to
 *      keep.
 *
 *      ITS GATE IS THIS MODULE'S OWN TWO GROUPS AND NOTHING ELSE. Not the
 *      lifecycle tiers — deliberately, and it is the whole point of the phase:
 *      a lifecycle administrator who can see every joining checklist has no
 *      business seeing who is on an improvement plan. `base.group_system` is
 *      not on the list either; an administrator who needs this is one row in a
 *      group away, by name. `pb.pip._can_read()` enforces the same thing
 *      independently and answers an EXPLAINED refusal rather than an access
 *      dialog, so this only decides whether the lens is OFFERED.
 *
 *   2. **⌘K palette rows**, in the **2700** deep-link block.
 *
 *      `pb_hub/js/hub_palette_entries` auto-numbers its seeded deep links
 *      `DEEP_LINK_BASE + (i + 1) * 10`, which runs to 2370 and grows every
 *      time somebody adds a row (R41). P2 took 2200-2220, P3 2400-2420, P4
 *      2500-2540 and P5 2600-2640, so P6 starts at 2700. Count the seed file
 *      rather than trusting the comment in it.
 *
 *      Every door is an XMLID and never a bare tag: a bare tag is synthesised
 *      with no action NAME, so anything returning through a breadcrumb lands
 *      on a crumb labelled "Unnamed".
 *
 * Every icon is from the shared `ic()` registry in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { LIFECYCLE_LENSES } from "@pb_lifecycle/js/lifecycle_hub";
import { PbPipBoard } from "@pb_pip/js/pip_board";

/** `pb.pip._can_read()`'s tiers, verbatim. Two groups, no admin fallback. */
export const PIP_GATE = [
    "pb_pip.group_pip_user",
    "pb_pip.group_pip_head",
];

registry.category(LIFECYCLE_LENSES).add("pip", {
    key: "pip",
    icon: "sunrise",
    label: _t("Growth plans"),
    Component: PbPipBoard,
    groups: PIP_GATE,
}, { sequence: 50 });

const HUB_XMLID = "pb_lifecycle.action_pb_lifecycle_hub";

const palette = registry.category("pb_hub_palette");

palette.add("pip_board", {
    id: "pip_board",
    label: _t("Growth plans"),
    sublabel: _t("Lifecycle"),
    icon: "sunrise",
    groups: PIP_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_pip_board",
    action: { xmlid: HUB_XMLID, lens: "pip" },
}, { sequence: 2700 });

// THE MANAGER'S ROW, and the one gate in this module that is not tight.
// "Manages at least one person" is a fact about hr.employee.parent_id and not
// a group, and a palette gate is a list of group xmlids — so this is offered
// to every internal user and the SERVER answers the question, with a sentence,
// for somebody who manages nobody. See pip_request.js.
palette.add("pip_request", {
    id: "pip_request",
    label: _t("Ask HR about someone in my team"),
    sublabel: _t("Growth plans"),
    icon: "smilePlus",
    groups: ["base.group_user"],
    requires: "pb_pip_request",
    action: { xmlid: "pb_pip.action_pb_pip_request" },
}, { sequence: 2710 });

palette.add("pip_cases", {
    id: "pip_cases",
    label: _t("All growth plans"),
    sublabel: _t("Growth plans"),
    icon: "fileText",
    groups: PIP_GATE,
    requires: "pb_pip_board",
    action: { xmlid: "pb_pip.action_pb_pip_case" },
}, { sequence: 2720 });

palette.add("pip_templates", {
    id: "pip_templates",
    label: _t("Growth plan templates"),
    sublabel: _t("Growth plans"),
    icon: "layers",
    groups: ["pb_pip.group_pip_head"],
    requires: "pb_pip_board",
    action: { xmlid: "pb_pip.action_pb_pip_template" },
}, { sequence: 2730 });
