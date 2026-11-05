/** @odoo-module **/
// PDR P2 W3b — a contract component answer shown and picked as a word
// (Yes / No, or the rule's own words). The line still stores the number:
// the server turns the word back into it (hr.contract.advantage
// pb_amount_word inverse), so nothing here ever writes a number.
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class ValueWordField extends Component {
    static template = "pb_hr_payroll_formula.ValueWordField";
    static props = { ...standardFieldProps };
    get value() { return this.props.record.data[this.props.name] || ""; }
    get options() {
        let words = [];
        try { words = JSON.parse(this.props.record.data.pb_value_words || "[]"); } catch { words = []; }
        // An unmatched number stays visible as itself — a value is never hidden.
        return this.value && !words.some((w) => w.label === this.value)
            ? [...words, { value: this.value, label: this.value }] : words;
    }
    get ariaLabel() { return _t("Answer"); }
    onChange(ev) { this.props.record.update({ [this.props.name]: ev.target.value }); }
}

registry.category("fields").add("pb_value_word", {
    component: ValueWordField,
    supportedTypes: ["char"],
    fieldDependencies: [{ name: "pb_value_words", type: "char" }],
});
