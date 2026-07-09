/** @odoo-module */
// =============================================================================
// Form State Injector — Adds .vu-state--{state} class to the form view DOM
// =============================================================================
// This patch reads the record's `state` field and applies a CSS class to
// the .o_form_view element, enabling the entire state-driven design system.
// =============================================================================

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { useEffect } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);

        useEffect(
            (state) => {
                if (!state) return;

                // Find the form view container for this controller.
                // Use querySelectorAll to handle stacked form views (e.g. dialogs).
                const formViews = document.querySelectorAll(".o_action_manager .o_form_view");
                const el = formViews[formViews.length - 1];
                if (!el) return;

                // Strip any existing state classes
                const toRemove = [];
                el.classList.forEach((cls) => {
                    if (cls.startsWith("vu-state--")) toRemove.push(cls);
                });
                toRemove.forEach((cls) => el.classList.remove(cls));

                // Apply the current state class
                el.classList.add(`vu-state--${state}`);

                return () => {
                    // Cleanup on unmount
                    el.classList.forEach((cls) => {
                        if (cls.startsWith("vu-state--")) el.classList.remove(cls);
                    });
                };
            },
            () => [this.model?.root?.data?.state]
        );
    },
});
