/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const STAGES = [
    { key: "draft", label: "Draft" },
    { key: "level1", label: "HR review" },
    { key: "level2", label: "GM review" },
    { key: "done", label: "Done" },
];
const INDEX = { draft: 0, level1: 1, level2: 2, done: 3 };

export class PbPipelineField extends Component {
    static template = "pb_payruns.PipelineField";
    static props = { ...standardFieldProps };

    get value() { return this.props.record.data[this.props.name] || "draft"; }
    get rejected() { return this.value === "cancel"; }

    get stages() {
        const cur = INDEX[this.value] ?? 0;
        return STAGES.map((s, i) => ({
            ...s,
            cls: i < cur ? "done" : (i === cur ? "current" : "future"),
        }));
    }
}

registry.category("fields").add("pb_pipeline", {
    component: PbPipelineField,
    supportedTypes: ["selection"],
});
