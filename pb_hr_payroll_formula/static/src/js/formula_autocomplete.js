/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * FormulaAutocomplete - Autocomplete dropdown for formula input
 */
export class FormulaAutocomplete extends Component {
    static template = "pb_hr_payroll_formula.FormulaAutocomplete";
    static props = {
        items: { type: Array },
        highlightedIndex: { type: Number, optional: true },
        onSelect: { type: Function },
        onClose: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            localHighlight: this.props.highlightedIndex || 0,
        });
    }

    getItemClass(index) {
        const classes = ["autocomplete-item"];

        if (index === (this.props.highlightedIndex ?? this.state.localHighlight)) {
            classes.push("highlighted");
        }

        return classes.join(" ");
    }

    getItemIcon(item) {
        switch (item.type) {
            case "function":
                return "function-icon";
            case "column":
                return "column-icon";
            case "operator":
                return "operator-icon";
            default:
                return "";
        }
    }

    getItemIconText(item) {
        switch (item.type) {
            case "function":
                return "fx";
            case "column":
                return item.name || "C";
            case "operator":
                return "op";
            default:
                return "?";
        }
    }

    onItemClick(index) {
        this.props.onSelect(index);
    }

    onItemMouseEnter(index) {
        this.state.localHighlight = index;
    }

    getCategoryLabel(category) {
        const labels = {
            [_t("Math")]: _t("Mathematical Functions"),
            [_t("Logical")]: _t("Logical Functions"),
            [_t("Text")]: _t("Text Functions"),
            [_t("Lookup")]: _t("Lookup & Reference"),
            [_t("Statistical")]: _t("Statistical Functions"),
            [_t("Date")]: _t("Date & Time Functions"),
        };
        return labels[category] || category;
    }

    groupItemsByCategory() {
        const groups = {};

        for (const item of this.props.items) {
            const category = item.category || (item.type === "column" ? _t("Columns") : _t("Other"));

            if (!groups[category]) {
                groups[category] = [];
            }
            groups[category].push(item);
        }

        return groups;
    }
}

/**
 * FunctionHelp - Tooltip showing function syntax and examples
 */
export class FunctionHelp extends Component {
    static template = "pb_hr_payroll_formula.FunctionHelp";
    static props = {
        func: { type: Object },
        onClose: { type: Function, optional: true },
    };

    // WDGAP PR-A — the example comes with the function from the engine's one
    // table (hr.formula.rule.pb_formula_functions), not a second hand-kept list.
    getExamples() {
        const func = this.props.func || {};
        return func.example ? [{ formula: func.example, result: func.description || "" }] : [];
    }

    getCategoryBadgeClass() {
        const category = this.props.func?.category;
        const classes = {
            [_t("Math")]: "badge-math",
            [_t("Logical")]: "badge-logical",
            [_t("Text")]: "badge-text",
            [_t("Lookup")]: "badge-lookup",
            [_t("Statistical")]: "badge-statistical",
            [_t("Date")]: "badge-date",
        };
        return classes[category] || "badge-default";
    }

    onClose() {
        if (this.props.onClose) {
            this.props.onClose();
        }
    }
}

export default FormulaAutocomplete;
