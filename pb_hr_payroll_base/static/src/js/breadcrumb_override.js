/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

// Patch FormController to override breadcrumb for country selector
// Odoo 19 patch syntax - second argument is the patch object directly
patch(FormController.prototype, {
    /**
     * Override the display name in breadcrumb for new records
     * when opened from the enhanced country selector
     */
    getDisplayName() {
        const context = this.props.context || {};
        const isEnhancedSelector = context.enhanced_selector;
        const isNewRecord = !this.model.root.resId;

        // If this is a new record from enhanced selector, use custom name
        if (isEnhancedSelector && isNewRecord) {
            return context.default_name || "Payroll Dashboard";
        }

        // Otherwise, use default behavior (super.getDisplayName in Odoo 19)
        return super.getDisplayName(...arguments);
    },
});

console.log("Payroll breadcrumb override loaded (Odoo 19)");
