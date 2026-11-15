/** @odoo-module **/
/**
 * The Schedule, extended from here (no pb_schedule file is edited):
 *
 *   * a "Patterns" button in its toolbar, beside Copy week, for the people
 *     who may make drafts — it opens the Patterns lens of Mission Control;
 *   * a small repeat mark on every card a pattern made (the card's
 *     `pattern` key, added by `hr.shift.planning.grid._pb_shift_card`).
 *
 * The template side is `schedule_patch.xml` (t-inherit, extension mode).
 */
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { onWillStart } from "@odoo/owl";
import { PbSchedule } from "@pb_schedule/js/pb_schedule";
import { openHub } from "@pb_hub/js/hub_nav";

patch(PbSchedule.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbspCanMake = false;
        onWillStart(async () => {
            try {
                this.pbspCanMake = await user.hasGroup("hr_attendance.group_hr_attendance_manager");
            } catch {
                this.pbspCanMake = false;
            }
        });
    },

    pbspMark(sh) {
        return sh && sh.pattern ? _t("Made from the pattern %(name)s", { name: sh.pattern }) : "";
    },

    pbspOpenPatterns() {
        openHub(this.actionService, {
            xmlid: "pb_mission.action_pb_workforce",
            lens: "patterns",
            lensKey: "pb_shell_lens",
        });
    },
});
