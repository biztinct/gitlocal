/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

// THREE STAGES, AND NEVER A LIST OF APPROVERS. How many people sign a pay run
// off, and who they are, is whatever route the business published — it can be
// nobody, one person or five, and it can differ per pay scheme. A rail that
// drew a fixed ladder would be telling every customer the same lie. What is
// always true is that a run is being prepared, then waiting, then finished.
const STAGES = [
    { key: "draft", label: _t("Draft") },
    { key: "approval_pending", label: _t("Waiting for approval") },
    { key: "done", label: _t("Done") },
];
export class PbPipelineField extends Component {
    static template = "pb_payruns.PipelineField";
    static props = { ...standardFieldProps };

    get value() { return this.props.record.data[this.props.name] || "draft"; }
    get rejected() { return this.value === "cancel"; }

    get stages() {
        const stages = STAGES;
        const cur = Math.max(stages.findIndex((s) => s.key === this.value), 0);
        return stages.map((s, i) => ({
            ...s,
            cls: i < cur ? "done" : (i === cur ? "current" : "future"),
        }));
    }
}

registry.category("fields").add("pb_pipeline", {
    component: PbPipelineField,
    supportedTypes: ["selection"],
});
