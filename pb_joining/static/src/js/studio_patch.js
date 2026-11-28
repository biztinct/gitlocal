/** @odoo-module **/
import { useEffect } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { NewHireStudio } from "@pb_new_hire/js/new_hire_studio";
import { StepDocs } from "@pb_new_hire/js/step_docs";

patch(NewHireStudio.prototype, {
    async openOfferDoor() {
        if (this.props.action?.context?.pb_joining_paper_settings && this.nh.data) {
            this.api.openJoiningPaperSettings = true;
            await this.go("docs");
            return;
        }
        return super.openOfferDoor(...arguments);
    },
});

patch(StepDocs.prototype, {
    setup() {
        super.setup(...arguments);
        useEffect(() => {
            if (this.editable && this.api.openJoiningPaperSettings) {
                this.api.openJoiningPaperSettings = false;
                this.openEditor();
            }
        }, () => [this.editable]);
    },
});
