/** @odoo-module **/
/**
 * DOCSTUDIO B4 — "Send as: PDF in my look" in the Explorer's Send regularly
 * drawer, beside the Excel layout choices (pb_excel_layout). The drawer is
 * extended by template inheritance (send.xml); the only seam used inside the
 * Explorer is `scheduleExtraVals`.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbExplorer } from "@pb_explorer/js/explorer";
import { rpIcon } from "@pb_report_pdf/js/report_pdf";

patch(PbExplorer.prototype, {
    scheduleExtraVals(form) {
        const vals = super.scheduleExtraVals(form);
        if (form.pbrp_pdf) { vals.layout_id = false; }
        return { ...vals, pbrp_pdf: !!form.pbrp_pdf };
    },

    _blankForm(me) {
        return { ...super._blankForm(me), pbrp_pdf: false };
    },

    editSchedule(sc) {
        super.editSchedule(sc);
        const form = this.state.sched?.form;
        if (form) { form.pbrp_pdf = !!sc.pbrp_pdf; }
    },

    setSendAs(layoutId) {
        super.setSendAs(layoutId);
        const form = this.state.sched?.form;
        if (form) { form.pbrp_pdf = false; }
    },

    setSendPdf() {
        const form = this.state.sched?.form;
        if (form) {
            form.layout_id = 0;
            form.pbrp_pdf = true;
        }
    },

    pdfIcon() {
        return rpIcon("fileText", 13);
    },

    sendPdfLine() {
        return _t("As a PDF in your look");
    },
});
