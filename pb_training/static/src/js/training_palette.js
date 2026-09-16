/** @odoo-module **/
/**
 * The Training lens's doors.
 *
 *   1. **The Learn hub's Training lens.** Registered into E1's lens registry
 *      rather than imported into the hub's config, because the dependency
 *      runs the other way: this module depends on the hub, so the hub cannot
 *      import this one back.
 *
 *      SEQUENCE 20. The hub's one shipped lens (Lessons, the product journey)
 *      carries no sequence, so bolted-on lenses start at 20 and land after it
 *      — which is also the right reading order: how to use Payobook, then the
 *      courses a company puts its own people through.
 *
 *      The LABEL is "Training", eight characters. The lens rail's label box is
 *      60px and it wraps between words but never inside one (R63), so what
 *      matters is the longest WORD: "Training" is one word and measures
 *      comfortably inside — the two labels that spilled ("Improvement",
 *      "Recognition") were eleven characters with no break in them.
 *
 *      Its gate is this module's own tier list, restated here because the
 *      Python/JS boundary cannot be imported across. `pb.training._can_read()`
 *      enforces the real one independently; this only decides whether the lens
 *      is OFFERED on the hub. Deliberately NOT the hub's own gate: the Lessons
 *      lens is ungated (a learning screen must not hide itself from the person
 *      who needs it), and running courses is a job with a team attached to it.
 *
 *   2. **⌘K palette rows**, in the **3900** block — E's block in the Wave 2
 *      plan, after A's 3500. Every door is an XMLID and never a bare tag: a
 *      bare tag is synthesised with no action NAME, so anything returning
 *      through a breadcrumb lands on a crumb labelled "Unnamed".
 *
 *      The employee's own page is reached through an `ir.actions.act_url`
 *      record, because the palette contract knows exactly two doors — a
 *      client-action tag and an xmlid — and nothing else (the shape
 *      `pb_rnr.action_my_recognition` set for `/my/recognition`). That row is
 *      UNGATED: everybody in the company can be put on a course, so a gate on
 *      it would hide the page from exactly the people it is for.
 *
 * Every icon is from the shared `ic()` registry in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { LEARN_LENSES } from "@pb_learn/hub/learn_hub";
import { PbTrainingBoard } from "@pb_training/js/training_board";

const TRAINING_GATE = [
    "pb_training.group_training_user",
    "pb_training.group_training_manager",
    "pb_training.group_training_admin",
];

registry.category(LEARN_LENSES).add("training", {
    key: "training",
    icon: "graduationCap",
    label: _t("Training"),
    Component: PbTrainingBoard,
    groups: TRAINING_GATE,
}, { sequence: 20 });

/* ---------------------------------------------------------- command bar --- */
const palette = registry.category("pb_hub_palette");
const HUB_XMLID = "pb_learn.action_learn_hub";

palette.add("training_board", {
    id: "training_board",
    label: _t("Training"),
    sublabel: _t("Learn"),
    icon: "graduationCap",
    groups: TRAINING_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_training_board",
    action: { xmlid: HUB_XMLID, lens: "training" },
}, { sequence: 3900 });

palette.add("training_courses", {
    id: "training_courses",
    label: _t("Courses"),
    sublabel: _t("Training"),
    icon: "bookOpen",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: "pb_training.action_pb_training_courses" },
}, { sequence: 3910 });

palette.add("training_tests", {
    id: "training_tests",
    label: _t("Tests and question bank"),
    sublabel: _t("Training"),
    icon: "target",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: "pb_training.action_pb_training_tests" },
}, { sequence: 3920 });

// UNGATED, and that is the point: everybody in the company can be put on a
// course, so this is the one row here that is for everybody.
palette.add("training_my", {
    id: "training_my",
    label: _t("My training"),
    sublabel: _t("Me"),
    icon: "award",
    requires: "pb_training_board",
    action: { xmlid: "pb_training.action_my_training" },
}, { sequence: 3930 });

/* -------------------------------------------------------------- E2 rows ---
 * Still inside E's 3900 block; B1 starts at 3600 per the wave plan. Both are
 * XMLIDs, because a bare tag is synthesised with no action NAME and anything
 * returning through a breadcrumb then lands on a crumb labelled "Unnamed".
 */
palette.add("training_assignments", {
    id: "training_assignments",
    label: _t("Training assignments"),
    sublabel: _t("Training"),
    icon: "userCheck",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: "pb_training.action_pb_training_assignments" },
}, { sequence: 3940 });

palette.add("training_schedules", {
    id: "training_schedules",
    label: _t("Compliance schedules"),
    sublabel: _t("Training"),
    icon: "repeat",
    groups: TRAINING_GATE,
    requires: "pb_training_board",
    action: { xmlid: "pb_training.action_pb_training_schedules" },
}, { sequence: 3950 });
