/** @odoo-module **/
/**
 * WFSETUP P5a — every old door into "Set up Workforce" opens this studio.
 *
 * Done from THIS module, never by editing the modules that own the doors, so
 * a database with `pb_workforce_workspace` alone keeps the old screen exactly
 * as it was (owner ruling R2: only some sites get the studio first). The
 * asset order makes it work: this module depends on every module patched
 * here, so their registrations run first and ours win with `force`.
 *
 *   Settings › HR › Workforce setup   one `tag` card → the studio (back chip
 *                                      returns to Settings)
 *   Settings › HR › Attendance calc.  removed: its five doors are studio steps
 *   Settings cards by xmlid            policies / employees / rosters /
 *                                      calendars / connectors → studio step
 *   action tag `pb_workforce_setup`    the studio itself (old links, bookmarks)
 *   Workforce lens `setup`, button     the studio, as its own screen
 *   Workforce overview buttons         "People", "Review setup", the
 *                                      connector stat → studio steps
 *   Schedule "Templates" (grouped)     studio step 1
 *   Overtime desk rate card (grouped)  studio step 4
 *
 * The Workforce menu trim itself lives in `pb_workforce_workspace`
 * (`TRIMMED_GROUPS`), switched on by the presence of the studio's tag.
 */
import { Component, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { PbSettingsHub, SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { PbMission } from "@pb_mission/js/pb_mission";
import { PbSchedule } from "@pb_schedule/js/pb_schedule";
import { PbOtDesk } from "@pb_hr_workforce/js/pb_ot_desk";
import { WorkforcePanel } from "@pb_workforce_workspace/workspace";
import { SetupStudio, ACTION_XMLID, SECTION_STEP } from "./setup_studio";

export const STUDIO_TAG = "pb_workforce_setup_studio";
const OFFICER = "hr_attendance.group_hr_attendance_officer";

// Settings cards that named a setup screen → the studio step that does it.
export const CARD_STEP = {
    "pb_attendance_policy.action_policy": "rules",
    "pb_attendance_policy.action_employee_policy": "people",
    "pb_hr_workforce.action_shift_planning_no_filter": "live",
    "resource.action_resource_calendar_form": "holidays",
    "pb_clock.action_clock_connectors": "clocks",
};

/** Open the studio, on `step` when given. */
export function openStudio(action, step = false, options = {}) {
    return action.doAction(ACTION_XMLID, {
        ...options,
        additionalContext: { ...(options.additionalContext || {}), ...(step ? { pb_wfs_step: step } : {}) },
    });
}

// ---------------------------------------------------------------- Settings
registry.category(SETTINGS_CATEGORIES).add("workforce_workspace", {
    key: "workforce_workspace", group: "hr", icon: "calendar", label: _t("Workforce setup"),
    blurb: _t("Shifts, working weeks, who works what, late and overtime rules, holidays and time clocks."),
    groups: [OFFICER],
    cards: [{ id: "setup", tag: STUDIO_TAG, icon: "compass", label: _t("Set up Workforce"),
              sub: _t("Shifts, working weeks, who works what, late and overtime rules, holidays and time clocks — seven steps, in order.") }],
}, { sequence: 39, force: true });

// "Attendance calculation" (pb_attendance_policy) held five doors that are
// all studio steps now; the advanced rules screen stays one click away from
// step 4.
if (registry.category(SETTINGS_CATEGORIES).contains("attendance_calculation")) {
    registry.category(SETTINGS_CATEGORIES).remove("attendance_calculation");
}

patch(PbSettingsHub.prototype, {
    openCard(card) {
        const step = card && card.xmlid && CARD_STEP[card.xmlid];
        if (step) {
            return super.openCard({ ...card, xmlid: undefined, tag: STUDIO_TAG,
                                    context: { ...(card.context || {}), pb_wfs_step: step } });
        }
        return super.openCard(...arguments);
    },
});

// ---------------------------------------------------------------- old action tag
// The old screen's client action (`pb_workforce_workspace.action_workspace_setup`,
// tag `pb_workforce_setup`) now renders the studio; a `pb_workspace_section`
// in its context picks the matching step (SECTION_STEP).
registry.category("actions").add("pb_workforce_setup", SetupStudio, { force: true });

// ---------------------------------------------------------------- Workforce lens
/** The `setup` lens reached by a deep link (`pb_shell_lens: "setup"`): it
 *  hands over to the studio, replacing the Workforce screen in the
 *  breadcrumbs so going back never lands on this hand-over again. */
export class SetupDoor extends Component {
    static template = "pb_workforce_setup.SetupDoor";
    static props = { "*": true };
    setup() {
        this.action = useService("action");
        onMounted(() => openStudio(this.action, false, { stackPosition: "replaceCurrentAction" }));
    }
}

registry.category("pb_mission_lens").add("setup", {
    key: "setup", label: _t("Workforce setup"), icon: "compass", Component: SetupDoor, props: {},
    groups: [OFFICER],
    features: { department: false, week: false, person: false, day: false, search: false },
}, { sequence: 95, force: true });

patch(PbMission.prototype, {
    /** The "Workforce setup" button (and any sibling hand-off to `setup`)
     *  opens the studio as its own screen; the lens stays where it was. */
    async setLens(key) {
        if (key === "setup") {
            const guard = this.workspaceEnv && this.workspaceEnv.guard;
            if (guard && !(await guard())) {
                return;
            }
            return openStudio(this.actionService);
        }
        return super.setLens(...arguments);
    },
});

// ---------------------------------------------------------------- overview buttons
const PANEL_STEP = { ...SECTION_STEP, rosters: false, setup: "", overview: false };

patch(WorkforcePanel.prototype, {
    /** Buttons on the grouped Workforce overview that named a setup section
     *  ("People", "Review setup", the connector stat) open the studio. */
    async go(key) {
        const step = PANEL_STEP[key];
        if (step !== undefined && step !== false) {
            if (this.guard && !(await this.guard())) {
                return;
            }
            return openStudio(this.action, step || false);
        }
        return super.go(...arguments);
    },
});

// ---------------------------------------------------------------- daily screens
// Only in the grouped menu: there these doors used to land on a setup tab
// that is no longer listed. The classic menu keeps its own editors.
patch(PbSchedule.prototype, {
    openTemplates() {
        if (this.env.pbWorkforce?.enabled) {
            return openStudio(this.actionService, "shifts");
        }
        return super.openTemplates(...arguments);
    },
    openTemplate(row) {
        if (this.env.pbWorkforce?.enabled) {
            return openStudio(this.actionService, "shifts");
        }
        return super.openTemplate(...arguments);
    },
});

patch(PbOtDesk.prototype, {
    openConfig(id) {
        if (this.env.pbWorkforce?.enabled) {
            return openStudio(this.action, "rules");
        }
        return super.openConfig(...arguments);
    },
});
