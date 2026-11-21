/** @odoo-module **/
/**
 * The doors into this module's new surfaces.
 *
 *   1. **The Holidays lens on Mission Control.** Registered into the soft
 *      registry `pb_mission` grew for D1.
 *
 *      THE CATEGORY IS NAMED BY ITS STRING AND NOT BY AN IMPORT, and that is
 *      the one place this file differs from every other palette file in the
 *      product. Every other hub sits BELOW the modules that bolt onto it, so
 *      `pb_goals` imports `PEOPLE_LENSES` from `pb_people_hub` and the
 *      dependency runs one way. Mission Control is the other shape: it
 *      DEPENDS on `pb_timeoff` — it mounts this module's Leave cockpit as its
 *      Time Off lens — so importing `@pb_mission/js/pb_mission` here would
 *      make the manifest graph a cycle. `pb_timeoff/tests/test_holidays.py`
 *      reads `pb_mission`'s own source and fails if the two spellings ever
 *      stop agreeing, which is the drift an import would have prevented.
 *
 *      The eight shipped lenses carry no sequence, so bolted-on ones start at
 *      20 — **Holidays 20**.
 *
 *      NO GROUP GATE. R209's lesson: the obvious gate is the HR one and it is
 *      the wrong one here, because the whole requirement is that everybody can
 *      see every country's holidays. The SERVER decides what the buttons may
 *      do — `pb.holidays` answers `can_edit`, so the Add and Paste doors are
 *      absent for a reader rather than present and refused.
 *
 *   2. **⌘K rows in the 3800 block**, as the wave plan says: A took 3500, B
 *      3600, C 3700, D 3800, E 3900.
 *
 *      The door is an XMLID and never a bare tag: a bare tag is synthesised
 *      with no action NAME and anything returning through a breadcrumb lands
 *      on a crumb labelled "Unnamed" (R180). `requires` is the presence probe
 *      — the actions registry holding this module's own tag is what says its
 *      JS actually shipped (R110/R116: never trust a version number).
 *
 * "Holidays" is eight characters in one word and sits comfortably inside the
 * 60px lens-rail label box (R63); the labels that spilled were eleven
 * characters with no break in them.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PbHolidays } from "@pb_timeoff/js/pb_holidays";

/** The literal `pb_mission` exports as `MISSION_LENSES`. Gated by a test. */
const MISSION_LENSES = "pb_mission_lens";

/** Who looks after time off — the gate `pb.timeoff._require_officer` asks. */
export const TIMEOFF_OFFICERS = [
    "hr_holidays.group_hr_holidays_user",
    "hr.group_hr_manager",
    "om_hr_payroll.group_hr_payroll_manager",
];

registry.category(MISSION_LENSES).add("holidays", {
    key: "holidays",
    icon: "sun",
    label: _t("Holidays"),
    Component: PbHolidays,
    groups: [],
    props: { embedded: true },
}, { sequence: 20 });

const palette = registry.category("pb_hub_palette");

palette.add("wf_holidays", {
    id: "wf_holidays",
    label: _t("Public holidays"),
    sublabel: _t("Mission Control"),
    icon: "sun",
    groups: [],
    requires: "pb_holidays",
    action: {
        xmlid: "pb_mission.action_pb_workforce",
        lens: "holidays",
        // Mission Control reads its lens from `pb_shell_lens`, because it
        // forwards plain `pb_lens` to the Time hub embedded inside it.
        lensKey: "pb_shell_lens",
    },
}, { sequence: 3800 });

/**
 * THE CARRY-FORWARD WATCH, AND A DELIBERATE DEVIATION.
 *
 * The handover asked for a row that opens "the Leave lens on the balances
 * tab". The Leave cockpit has no tabs — the balance board is a panel on the
 * same page — so that row would have been a second door onto the screen
 * `wf_timeoff` already opens, which is the duplicate the palette contract
 * warns about. It points instead at the watch's OWN list: who was warned,
 * when, how many days they were holding and whether their manager was told.
 * That is the screen somebody typing "carry" actually wants, and it did not
 * exist before this phase.
 *
 * Gated on the time-off team, because the log is about other people.
 */
palette.add("wf_carry", {
    id: "wf_carry",
    label: _t("Carry-forward watch"),
    sublabel: _t("Time Off"),
    icon: "clock",
    groups: TIMEOFF_OFFICERS,
    requires: "pb_holidays",
    action: { xmlid: "pb_timeoff.action_pb_carry_log" },
}, { sequence: 3820 });
