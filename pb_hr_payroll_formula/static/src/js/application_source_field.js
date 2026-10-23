/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

export class ApplicationSourceField extends Component {
    static template = "pb_hr_payroll_formula.ApplicationSourceField";
    static props = { ...standardFieldProps };
    setup() {
        this.orm = useService("orm");
        this.state = useState({ options: [], error: false });
        onWillStart(async () => {
            const config = this.props.record.data.config_id;
            const configId = Array.isArray(config) ? config[0] : config?.id;
            try {
                if (configId) {
                    this.state.options = await this.orm.call("hr.formula.config", "application_source_options", [[configId]]);
                } else if (this.props.record.resId) {
                    this.state.options = await this.orm.call("hr.formula.rule", "application_source_options", [[this.props.record.resId]]);
                }
            } catch { this.state.error = true; }
        });
    }
    get value() { return this.props.record.data[this.props.name] || ""; }
    get options() {
        const values = this.state.options;
        return this.value && !values.some((v) => v.key === this.value)
            ? [...values, { key: this.value, label: this.value + " · source unavailable" }] : values;
    }
    get label() { return this.options.find((v) => v.key === this.value)?.label || "Employee / contract mapping"; }
    onChange(ev) { this.props.record.update({ [this.props.name]: ev.target.value || false }); }
}
registry.category("fields").add("application_source", {
    component: ApplicationSourceField, supportedTypes: ["char"],
});
