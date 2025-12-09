/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

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
            "Math": "Mathematical Functions",
            "Logical": "Logical Functions",
            "Text": "Text Functions",
            "Lookup": "Lookup & Reference",
            "Statistical": "Statistical Functions",
            "Date": "Date & Time Functions",
        };
        return labels[category] || category;
    }

    groupItemsByCategory() {
        const groups = {};

        for (const item of this.props.items) {
            const category = item.category || (item.type === "column" ? "Columns" : "Other");

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
                { formula: "=SUM(A1, B1, C1)", result: "Sum of values" },
                { formula: "=SUM(A1:A10)", result: "Sum of range" },
            ],
            "IF": [
                { formula: "=IF(A1>100, \"High\", \"Low\")", result: "Conditional text" },
                { formula: "=IF(B1=0, 0, A1/B1)", result: "Avoid division by zero" },
            ],
            "ROUND": [
                { formula: "=ROUND(3.14159, 2)", result: "3.14" },
                { formula: "=ROUND(A1, 0)", result: "Round to integer" },
            ],
            "AVERAGE": [
                { formula: "=AVERAGE(A1, B1, C1)", result: "Average of values" },
            ],
            "VLOOKUP": [
                { formula: "=VLOOKUP(A1, B1:C10, 2, FALSE)", result: "Exact match lookup" },
            ],
            "IFERROR": [
                { formula: "=IFERROR(A1/B1, 0)", result: "0 if error" },
            ],
        };

        return examples[funcName] || [];
    }

    getCategoryBadgeClass() {
        const category = this.props.func?.category;
        const classes = {
            "Math": "badge-math",
            "Logical": "badge-logical",
            "Text": "badge-text",
            "Lookup": "badge-lookup",
            "Statistical": "badge-statistical",
            "Date": "badge-date",
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
