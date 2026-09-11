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
export class PbPipelineField extends Component {
    static template = "pb_payruns.PipelineField";
    static props = { ...standardFieldProps };

    get value() { return this.props.record.data[this.props.name] || "draft"; }
    get rejected() { return this.value === "cancel"; }

    get stages() {
        // Officer review is a tier a database may switch off. The record says
        // so when the view loaded the flag; with no flag, keep all five — that
        // is what every database had before the switch existed. A run still
        // parked at a switched-off stage keeps its step, so the rail never
        // shows it as further along than it is.
        const officer =
            this.props.record.data.pb_officer_tier !== false ||
            this.value === "level0";
        const stages = STAGES.filter((s) => officer || s.key !== "level0");
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
