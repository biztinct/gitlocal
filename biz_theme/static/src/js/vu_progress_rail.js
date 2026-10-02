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
//
// Or with the steps decided by the SERVER, when the stages a record can move
// through depend on a setting rather than on the code (a pay run's approval
// chain, say, where one database signs off twice and another three times):
//   <widget name="vu_progress_rail"
//           steps_field="pb_stage_rail" state_field="state"/>
// The named field holds "state:Label,state:Label,…". It wins over `steps` when
// it has a value, and falls back to `steps` when it is empty, so a view can
// carry both and still render on a database that has never set the field.
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
        stepsField: { type: String, optional: true },
    };

    get stateField() {
        return this.props.stateField || "state";
    }

    get currentState() {
        return this.props.record?.data?.[this.stateField] || "";
    }

    get stepList() {
        // A server-supplied list wins: the record knows which stages apply to
        // it, the view only knows what the code was written with.
        const fromField =
            this.props.stepsField && this.props.record?.data?.[this.props.stepsField];
        if (fromField) {
            const pairs = String(fromField).split(",").filter((p) => p.trim());
            if (pairs.length) {
                return pairs.map((pair) => {
                    const cut = pair.indexOf(":");
                    const state = (cut === -1 ? pair : pair.slice(0, cut)).trim();
                    return {
                        state,
                        label: (cut === -1 ? state : pair.slice(cut + 1)).trim() || state,
                        icon: "fa-circle",
                    };
                });
            }
        }
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
        stepsField: attrs.steps_field,
    }),
});
