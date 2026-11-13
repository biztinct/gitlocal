/** @odoo-module **/

import { registry } from "@web/core/registry";
import { FloatField, floatField } from "@web/views/fields/float/float_field";
import { formatFloat } from "@web/views/fields/formatters";

/**
 * SmartFloatField — conditionally formats float display:
 *   |value| >= 1000  → 0 decimal places (salary amounts in VND)
 *   |value| < 1000   → 2 decimal places (hours, rates, small quantities)
 */
class SmartFloatField extends FloatField {
    get formattedValue() {
        const val = this.props.record.data[this.props.name];
        if (val === undefined || val === null || val === false) return "";
        const decimals = Math.abs(val) >= 1000 ? 0 : 2;
        return formatFloat(val, { digits: [16, decimals] });
    }
}

const smartFloatField = {
    ...floatField,
    component: SmartFloatField,
};

registry.category("fields").add("smart_float", smartFloatField);
