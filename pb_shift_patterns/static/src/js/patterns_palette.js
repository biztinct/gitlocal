/** @odoo-module **/
/**
 * The doors into "Shift patterns".
 *
 *   1. **The Patterns lens on Mission Control**, registered into the soft
 *      registry `pb_mission` grew for later modules.
 *
 *      THE CATEGORY IS NAMED BY ITS STRING AND NOT BY AN IMPORT — the
 *      `pb_timeoff` Holidays precedent. Mission Control mounts the Schedule
 *      this module extends, and loading `@pb_mission/js/pb_mission` from here
 *      would make this module depend on the whole workspace. A static test
 *      (`tests/test_static.py` S1) reads pb_mission's own source and fails if
 *      the two spellings ever stop agreeing.
 *
 *      Bolted-on lenses start at 20 (Holidays 20, Insights 90); this one is
 *      30, so it sits beside Holidays, after the shipped lenses. Gated like
 *      the Schedule lens (attendance officers); the server decides what the
 *      buttons may do (`can_edit`).
 *
 *   2. **Two ⌘K rows in the 5000 block** (no other module uses it): the lens,
 *      and "Make drafts from a pattern", which opens the same lens with the
 *      make-drafts panel up (`focus: "make"`, read by the lens on mount).
 *
 *      Every door is an XMLID and never a bare tag: a bare tag returns through
 *      a breadcrumb labelled "Unnamed" (R180). `requires` is the presence
 *      probe — the actions registry holding this module's own tag is what says
 *      its JS actually shipped.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PbShiftPatterns } from "@pb_shift_patterns/js/patterns_board";

/** The literal `pb_mission` exports as `MISSION_LENSES`. Gated by a test. */
const MISSION_LENSES = "pb_mission_lens";

/** Who plans the schedule — the gate `pb.shift.patterns._can_read` asks. */
export const PATTERN_READERS = ["hr_attendance.group_hr_attendance_officer"];
/** Who makes drafts — `pb.shift.pattern.engine._pb_can_make`. */
export const PATTERN_MAKERS = ["hr_attendance.group_hr_attendance_manager"];

registry.category(MISSION_LENSES).add("patterns", {
    key: "patterns",
    icon: "repeat",
    label: _t("Patterns"),
    Component: PbShiftPatterns,
    groups: PATTERN_READERS,
    props: { embedded: true },
}, { sequence: 30 });

const palette = registry.category("pb_hub_palette");

palette.add("wf_patterns", {
    id: "wf_patterns",
    label: _t("Shift patterns"),
    sublabel: _t("Mission Control"),
    icon: "repeat",
    groups: PATTERN_READERS,
    keywords: ["rota", "roster", "rotation", "cycle", "crew"],
    requires: "pb_shift_patterns",
    action: {
        xmlid: "pb_mission.action_pb_workforce",
        lens: "patterns",
        // Mission Control reads its lens from `pb_shell_lens`, because it
        // forwards plain `pb_lens` to the Time hub embedded inside it.
        lensKey: "pb_shell_lens",
    },
}, { sequence: 5000 });

palette.add("wf_patterns_make", {
    id: "wf_patterns_make",
    label: _t("Make shifts from a pattern"),
    sublabel: _t("Schedule"),
    icon: "calendarClock",
    groups: PATTERN_MAKERS,
    keywords: ["rota", "generate", "fill weeks", "draft shifts"],
    requires: "pb_shift_patterns",
    action: {
        xmlid: "pb_mission.action_pb_workforce",
        lens: "patterns",
        lensKey: "pb_shell_lens",
        focus: "make",
    },
}, { sequence: 5010 });
