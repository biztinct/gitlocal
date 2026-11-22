/** @odoo-module **/
/**
 * DOCSTUDIO X4 — "Send as: standard Excel / my layout" in the Explorer's
 * Send regularly drawer. The drawer markup is extended from this module
 * (template inheritance in excel_layout.xml); the only seam inside the
 * Explorer itself is `scheduleExtraVals`.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbExplorer } from "@pb_explorer/js/explorer";

patch(PbExplorer.prototype, {
    scheduleExtraVals(form) {
        return { ...super.scheduleExtraVals(form), layout_id: form.layout_id || false };
    },

    _blankForm(me) {
        return { ...super._blankForm(me), layout_id: 0 };
    },

    editSchedule(sc) {
        super.editSchedule(sc);
        const form = this.state.sched?.form;
        if (form) { form.layout_id = sc.layout_id || 0; }
    },

    setSendAs(layoutId) {
        const form = this.state.sched?.form;
        if (form) { form.layout_id = layoutId || 0; }
    },

    get sendAsLayouts() {
        return this.state.sched?.layouts || [];
    },

    sendAsLine(sc) {
        return sc.layout_ok
            ? _t("In your layout “%s”", sc.layout_name)
            : _t("In your layout “%s” — its sheet is missing, so the standard Excel is sent", sc.layout_name);
    },

    get sendAsChosen() {
        const form = this.state.sched?.form;
        return this.sendAsLayouts.find((l) => l.id === form?.layout_id) || null;
    },
});
