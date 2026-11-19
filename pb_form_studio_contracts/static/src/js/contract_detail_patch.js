/** @odoo-module **/
/**
 * FS-3 — the contract page (`pb_contract_detail`) shows the administrator's
 * own contract fields, look-only, under the lifecycle panel.
 *
 * The sections come in the page's own payload (`get_contract_detail` →
 * `pbfs`, added by `_inherit` on the server from `pb.form.studio.render`, so
 * the reader only ever receives what they may see). The Form builder wand
 * sits in the page's top bar for the administrator.
 */
import { patch } from "@web/core/utils/patch";
import { PbContractDetail } from "@pb_contracts/js/contract_detail";
import { PbFieldGrid } from "@pb_form_studio/js/field_grid";
import { FormStudioOverlay } from "@pb_form_studio/js/studio_overlay";
import { useFormStudio, FormStudioWand } from "@pb_form_studio/js/use_form_studio";
import { FS3_HOST } from "./contract_drawer_patch";

PbContractDetail.components = {
    ...(PbContractDetail.components || {}), PbFieldGrid, FormStudioWand, FormStudioOverlay,
};

patch(PbContractDetail.prototype, {
    setup() {
        super.setup(...arguments);
        this.fs3Studio = useFormStudio({
            hostKey: FS3_HOST,
            recordId: () => Number(this.cid) || false,
            onPublished: () => this.refresh(),
        });
    },
    get fs3Sections() {
        const payload = this.d && this.d.pbfs;
        return (payload && payload.sections) || [];
    },
    get fs3Currency() { return (this.d && this.d.currency) || ""; },
});
