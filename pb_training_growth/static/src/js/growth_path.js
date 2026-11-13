/** @odoo-module **/
/**
 * Growth plans × learning paths (LEARNING L3, bridge module).
 *
 * Patches the growth-plan board (`PbPipBoard`) with two doors on each
 * objective in the plan drawer: a "Learning path" picker and, when the
 * objective points at a path the person is not on yet, "Enrol". The chip
 * "Leading a line · 40%" says how far they have got. `pb_pip` itself is not
 * edited: the template is extended from here (`growth_path.xml`).
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbPipBoard } from "@pb_pip/js/pip_board";

patch(PbPipBoard.prototype, {
    /** The quiet chip's colour: green finished, rose late, indigo on it. */
    pathChipClass(path) {
        if (!path || !path.enrolment_id) { return ""; }
        if (path.state === "done") { return "is-ok"; }
        if (path.late) { return "is-bad"; }
        return "is-go";
    },

    async setObjectivePath(objective, ev) {
        const pathId = Number(ev.target.value) || 0;
        if (await this.call("set_objective_path", [objective.id, pathId],
                            pathId ? _t("The objective now points at that learning path.") : _t("The learning path is taken off the objective."))) {
            await this.refresh();
        }
    },

    async enrolObjectivePath(objective) {
        const res = await this.call("enrol_objective_path", [objective.id]);
        if (res) {
            if (res.message) { this.notif.add(res.message, { type: "success" }); }
            await this.refresh();
        }
    },
});
