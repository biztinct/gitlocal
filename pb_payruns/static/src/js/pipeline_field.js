/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

const STAGES = [
    { key: "draft", label: _t("Draft") },
    { key: "level0", label: _t("Officer review") },
    { key: "level1", label: _t("HR review") },
    { key: "level2", label: _t("Finance approval") },
    { key: "done", label: _t("Done") },
];
const INDEX = { draft: 0, level0: 1, level1: 2, level2: 3, done: 4 };

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
