/** @odoo-module **/
/**
 * The doors into the field check-in map.
 *
 *   1. **The Field lens on Mission Control**, through the soft registry
 *      `pb_mission` grew for D1.
 *
 *      THE CATEGORY IS NAMED BY ITS STRING AND NOT BY AN IMPORT, and this is
 *      the module where that is most obviously necessary: `pb_mission`
 *      depends on `pb_today`, which depends on THIS module for the very
 *      component being registered. Importing `@pb_mission/js/pb_mission` here
 *      would make the manifest graph a cycle no `depends` list can express.
 *      `pb_driver_checkin/tests/test_field.py` reads `pb_mission`'s own
 *      source and fails if the two spellings ever stop agreeing.
 *
 *      MOUNTED UN-EMBEDDED, which is a deliberate difference from every other
 *      lens in the workspace. `embedded` on this component suppresses its KPI
 *      strip, on the reasoning that the HOST already draws the page's numbers
 *      — true of the Today board, which has its own header full of them, and
 *      false of Mission Control, whose command bar carries no numbers at all.
 *      Dropping them here would lose "4 moving · 1 idle · 2 off duty" with
 *      nothing to replace it. The component has no H1 of its own, so there is
 *      nothing to duplicate.
 *
 *      Holidays took 20, so **Field is 30**. "Field" is five characters and
 *      sits well inside the 60px lens-rail label box (R63).
 *
 *      GATED ON THE ATTENDANCE OFFICER, the same question
 *      `pb.driver.map._require_officer` asks on the server. This is a map of
 *      where other people are: a lens whose every call would be refused is
 *      W29's door that can only produce an error.
 *
 *   2. **A ⌘K row at 3810**, inside D's 3800 block. The door is an XMLID and
 *      never a bare tag (R180), and `requires` is the presence probe.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { DriverMap } from "@pb_driver_checkin/js/driver_map";

/** The literal `pb_mission` exports as `MISSION_LENSES`. Gated by a test. */
const MISSION_LENSES = "pb_mission_lens";

const ATTENDANCE_OFFICER = ["hr_attendance.group_hr_attendance_officer",
                            "hr_attendance.group_hr_attendance_manager"];

registry.category(MISSION_LENSES).add("field", {
    key: "field",
    icon: "mapPin",
    label: _t("Field"),
    Component: DriverMap,
    groups: ATTENDANCE_OFFICER,
    props: { embedded: false, initialView: "full" },
}, { sequence: 30 });

registry.category("pb_hub_palette").add("wf_field", {
    id: "wf_field",
    label: _t("Field check-in map"),
    sublabel: _t("Mission Control"),
    icon: "mapPin",
    groups: ATTENDANCE_OFFICER,
    requires: "pb_driver_map",
    action: {
        xmlid: "pb_mission.action_pb_workforce",
        lens: "field",
        // Mission Control reads its lens from `pb_shell_lens`, because it
        // forwards plain `pb_lens` to the Time hub embedded inside it.
        lensKey: "pb_shell_lens",
    },
}, { sequence: 3810 });
