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

    getExamples() {
        const funcName = this.props.func?.name;

        const examples = {
            "SUM": [
                { formula: "=SUM(A1, B1, C1)", result: _t("Sum of values") },
                { formula: "=SUM(A1:A10)", result: _t("Sum of range") },
            ],
            "IF": [
                { formula: "=IF(A1>100, \"High\", \"Low\")", result: _t("Conditional text") },
                { formula: "=IF(B1=0, 0, A1/B1)", result: _t("Avoid division by zero") },
            ],
            "ROUND": [
                { formula: "=ROUND(3.14159, 2)", result: "3.14" },
                { formula: "=ROUND(A1, 0)", result: _t("Round to integer") },
            ],
            "AVERAGE": [
                { formula: "=AVERAGE(A1, B1, C1)", result: _t("Average of values") },
            ],
            "VLOOKUP": [
                { formula: "=VLOOKUP(A1, B1:C10, 2, FALSE)", result: _t("Exact match lookup") },
            ],
            "IFERROR": [
                { formula: "=IFERROR(A1/B1, 0)", result: _t("0 if error") },
            ],
        };

        return examples[funcName] || [];
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
