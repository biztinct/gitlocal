/** @odoo-module **/
/**
 * The Probation lens's doors.
 *
 *   1. **The Lifecycle hub's Probation lens.** Registered into P0's lens
 *      registry rather than imported into its config, because the dependency
 *      runs the other way: this module depends on the hub, so the hub cannot
 *      import this one back. The shipped Journeys lens carries no sequence,
 *      P3's New joiners took 20 and P4's Exits took 30, so Probation takes
 *      **40** — which is right in the story as well as in the number:
 *      everything running, then the people arriving, then the people leaving,
 *      then the people still being decided about.
 *
 *      Its gate is P0's tier list, restated here because the Python/JS
 *      boundary cannot be imported across. `pb.probation._can_read()` enforces
 *      it independently and answers an EXPLAINED empty board rather than an
 *      access dialog, so this only decides whether the lens is OFFERED.
 *
 *   2. **⌘K palette rows**, in the **2600** deep-link block.
 *
 *      `pb_hub/js/hub_palette_entries` auto-numbers its seeded deep links
 *      `DEEP_LINK_BASE + (i + 1) * 10`, which runs to 2370 and grows every
 *      time somebody adds a row (R41). P3 took 2400-2420 and P4 took
 *      2500-2540, so P5 starts at 2600. Count the seed file rather than
 *      trusting the comment in it.
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
import { LIFECYCLE_LENSES, LIFECYCLE_GATE } from "@pb_lifecycle/js/lifecycle_hub";
import { PbProbationBoard } from "@pb_probation/js/probation_board";

registry.category(LIFECYCLE_LENSES).add("probation", {
    key: "probation",
    icon: "stamp",
    label: _t("Probation"),
    Component: PbProbationBoard,
    groups: LIFECYCLE_GATE,
}, { sequence: 40 });

const HUB_XMLID = "pb_lifecycle.action_pb_lifecycle_hub";
const ADMIN = ["pb_lifecycle.group_lifecycle_admin", "base.group_system"];
const MANAGER = [
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

const palette = registry.category("pb_hub_palette");

palette.add("probation_board", {
    id: "probation_board",
    label: _t("Probation"),
    sublabel: _t("Lifecycle"),
    icon: "stamp",
    groups: LIFECYCLE_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_probation_board",
    action: { xmlid: HUB_XMLID, lens: "probation" },
}, { sequence: 2600 });

palette.add("probation_reviews", {
    id: "probation_reviews",
    label: _t("Probation reviews"),
    sublabel: _t("Probation"),
    icon: "fileText",
    groups: MANAGER,
    requires: "pb_probation_board",
    action: { xmlid: "pb_probation.action_pb_probation_review" },
}, { sequence: 2610 });

palette.add("probation_courses", {
    id: "probation_courses",
    label: _t("Training courses"),
    sublabel: _t("Probation"),
    icon: "bookOpen",
    groups: MANAGER,
    requires: "pb_probation_board",
    action: { xmlid: "pb_probation.action_pb_training_track" },
}, { sequence: 2620 });

palette.add("probation_training_status", {
    id: "probation_training_status",
    label: _t("Who has done what"),
    sublabel: _t("Probation"),
    icon: "checkCircle",
    groups: MANAGER,
    requires: "pb_probation_board",
    action: { xmlid: "pb_probation.action_pb_training_status" },
}, { sequence: 2630 });

palette.add("probation_policies", {
    id: "probation_policies",
    label: _t("Probation policies"),
    sublabel: _t("Probation"),
    icon: "calendar",
    groups: ADMIN,
    requires: "pb_probation_board",
    action: { xmlid: "pb_probation.action_pb_probation_policy" },
}, { sequence: 2640 });
