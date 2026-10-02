/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { AiCoachingChatWidget } from "./ai_coaching_chat_widget";

/**
 * Form Controller Hook for AI Coaching Chat
 * This patches the form renderer to mount the chat widget
 */
export class AiCoachingChatFormWidget extends Component {
    static components = { AiCoachingChatWidget };
    static template = "hr_development_ai.AiCoachingChatFormWidget";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");

        onWillStart(async () => {
            // Setup is handled by the widget itself
        });

        onMounted(() => {
            // Widget is now mounted in the form
        });

        onWillUnmount(() => {
            // Cleanup if needed
        });
    }

    /**
     * Get the current record from the form
     */
    get record() {
        // Try to get record from props or parent form
        if (this.props.record) {
            return this.props.record;
        }

        // Try to get from form controller in component tree
        let node = this.__owl__.parent;
        while (node) {
            const comp = node.component;
            if (comp && comp.model && comp.model.root) {
                return comp.model.root;
            }
            if (comp && comp.props && comp.props.record) {
                return comp.props.record;
            }
            node = node.parent;
        }

        return null;
    }

    /**
     * Get the field name
     */
    get fieldName() {
        return 'ai_transcript';
    }
}

// Register as a view widget (for form hooks)
registry.category("view_widgets").add("ai_coaching_chat_form", {
    component: AiCoachingChatFormWidget,
});
