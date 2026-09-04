/** @odoo-module */
// =============================================================================
// VuProgressRail — OWL widget for horizontal workflow progress timeline
// =============================================================================
// Usage in form XML:
//   <widget name="vu_progress_rail"/>
//
// Or with custom steps:
//   <widget name="vu_progress_rail"
//           steps="draft,confirmed,assigned,in_progress,completed,closed"
//           labels="Created,Confirmed,Assigned,In Progress,Completed,Closed"
//           state_field="state"/>
// =============================================================================

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

const DEFAULT_STEPS = [
    { state: "draft", label: _t("Created"), icon: "fa-file-o" },
    { state: "confirmed", label: _t("Confirmed"), icon: "fa-check" },
    { state: "assigned", label: _t("Assigned"), icon: "fa-users" },
    { state: "in_progress", label: _t("In Progress"), icon: "fa-play" },
    { state: "completed", label: _t("Completed"), icon: "fa-flag-checkered" },
    { state: "closed", label: _t("Closed"), icon: "fa-folder" },
];

export class VuProgressRail extends Component {
    static template = "biz_theme.VuProgressRail";
    static props = {
        ...standardWidgetProps,
        steps: { type: String, optional: true },
        labels: { type: String, optional: true },
        stateField: { type: String, optional: true },
    };

    get stateField() {
        return this.props.stateField || "state";
    }

    get currentState() {
        return this.props.record?.data?.[this.stateField] || "";
    }

    get stepList() {
        if (this.props.steps) {
            const states = this.props.steps.split(",");
            const labels = (this.props.labels || this.props.steps).split(",");
            return states.map((s, i) => ({
                state: s.trim(),
                label: (labels[i] || s).trim(),
                icon: "fa-circle",
            }));
        }
        return DEFAULT_STEPS;
    }

    get processedSteps() {
        const current = this.currentState;
        const steps = this.stepList;
        let foundCurrent = false;

        // Handle cancelled — show all prior steps as completed, cancelled as current
        if (current === "cancelled") {
            return steps.map((step, index) => ({
                ...step,
                status: "completed",
                isLast: index === steps.length - 1,
                stepNumber: index + 1,
            }));
        }

        return steps.map((step, index) => {
            let status;
            if (step.state === current || step.state === "completed_pending_invoice" && current === "completed_pending_invoice") {
                status = "current";
                foundCurrent = true;
            } else if (!foundCurrent) {
                status = "completed";
            } else {
                status = "future";
            }

            return {
                ...step,
                status,
                isLast: index === steps.length - 1,
                stepNumber: index + 1,
            };
        });
    }

    get isCancelled() {
        return this.currentState === "cancelled";
    }
}

registry.category("view_widgets").add("vu_progress_rail", {
    component: VuProgressRail,
    extractProps: ({ attrs }) => ({
        steps: attrs.steps,
        labels: attrs.labels,
        stateField: attrs.state_field,
    }),
});
