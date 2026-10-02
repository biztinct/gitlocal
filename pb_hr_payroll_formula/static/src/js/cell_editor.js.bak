/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";

/**
 * CellEditor - Inline cell editing component
 */
export class CellEditor extends Component {
    static template = "pb_hr_payroll_formula.CellEditor";
    static props = {
        value: { type: [String, Number], optional: true },
        type: { type: String, optional: true }, // 'text', 'number', 'formula'
        format: { type: String, optional: true },
        onCommit: { type: Function },
        onCancel: { type: Function },
    };

    setup() {
        this.inputRef = useRef("input");

        this.state = useState({
            value: this.props.value || "",
            isValid: true,
            error: null,
        });

        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
                this.inputRef.el.select();
            }
        });
    }

    onInput(ev) {
        this.state.value = ev.target.value;
        this.validate();
    }

    onKeyDown(ev) {
        switch (ev.key) {
            case "Enter":
                ev.preventDefault();
                this.commit();
                break;
            case "Escape":
                ev.preventDefault();
                this.cancel();
                break;
            case "Tab":
                ev.preventDefault();
                this.commit();
                break;
        }
    }

    onBlur() {
        // Small delay to allow button clicks to register
        setTimeout(() => {
            if (document.activeElement !== this.inputRef.el) {
                this.commit();
            }
        }, 100);
    }

    validate() {
        const value = this.state.value;
        const type = this.props.type || "text";

        if (type === "number") {
            const num = parseFloat(value);
            if (isNaN(num) && value !== "") {
                this.state.isValid = false;
                this.state.error = "Invalid number";
                return false;
            }
        } else if (type === "formula") {
            if (value && !value.startsWith("=")) {
                this.state.isValid = false;
                this.state.error = "Formula must start with '='";
                return false;
            }

            // Basic syntax check
            if (value) {
                const openParens = (value.match(/\(/g) || []).length;
                const closeParens = (value.match(/\)/g) || []).length;
                if (openParens !== closeParens) {
                    this.state.isValid = false;
                    this.state.error = "Unbalanced parentheses";
                    return false;
                }
            }
        }

        this.state.isValid = true;
        this.state.error = null;
        return true;
    }

    commit() {
        if (this.validate()) {
            this.props.onCommit(this.state.value);
        }
    }

    cancel() {
        this.props.onCancel();
    }

    getInputType() {
        const type = this.props.type || "text";
        if (type === "number") {
            return "number";
        }
        return "text";
    }

    getInputClass() {
        const classes = ["cell-editor-input"];

        if (this.props.type === "formula") {
            classes.push("formula-input");
        }

        if (!this.state.isValid) {
            classes.push("invalid");
        }

        return classes.join(" ");
    }
}

/**
 * NumericEditor - Specialized editor for numeric values
 */
export class NumericEditor extends CellEditor {
    static template = "pb_hr_payroll_formula.NumericEditor";

    setup() {
        super.setup();

        this.state.step = this.getStep();
        this.state.min = this.props.min;
        this.state.max = this.props.max;
    }

    getStep() {
        const format = this.props.format || "number";
        switch (format) {
            case "percentage":
                return 0.01;
            case "integer":
                return 1;
            case "currency":
            default:
                return 0.01;
        }
    }

    formatValue(value) {
        const num = parseFloat(value);
        if (isNaN(num)) return "";

        const format = this.props.format || "number";
        switch (format) {
            case "percentage":
                return (num * 100).toFixed(2);
            case "integer":
                return Math.round(num).toString();
            case "currency":
                return num.toFixed(2);
            default:
                return num.toString();
        }
    }

    parseValue(value) {
        const num = parseFloat(value);
        if (isNaN(num)) return 0;

        const format = this.props.format || "number";
        if (format === "percentage") {
            return num / 100;
        }
        return num;
    }

    increment() {
        const current = parseFloat(this.state.value) || 0;
        this.state.value = (current + this.state.step).toString();
        this.validate();
    }

    decrement() {
        const current = parseFloat(this.state.value) || 0;
        this.state.value = (current - this.state.step).toString();
        this.validate();
    }
}

/**
 * FormulaEditor - Specialized editor for formula cells
 */
export class FormulaEditor extends CellEditor {
    static template = "pb_hr_payroll_formula.FormulaEditor";
    static props = {
        ...CellEditor.props,
        columns: { type: Array, optional: true },
    };

    setup() {
        super.setup();

        this.state.showSuggestions = false;
        this.state.suggestions = [];
        this.state.selectedSuggestion = 0;
    }

    onInput(ev) {
        super.onInput(ev);
        this.updateSuggestions();
    }

    onKeyDown(ev) {
        if (this.state.showSuggestions) {
            switch (ev.key) {
                case "ArrowDown":
                    ev.preventDefault();
                    this.selectNextSuggestion();
                    return;
                case "ArrowUp":
                    ev.preventDefault();
                    this.selectPreviousSuggestion();
                    return;
                case "Tab":
                case "Enter":
                    if (this.state.suggestions.length > 0) {
                        ev.preventDefault();
                        this.applySuggestion(this.state.selectedSuggestion);
                        return;
                    }
                    break;
            }
        }

        super.onKeyDown(ev);
    }

    updateSuggestions() {
        const value = this.state.value;
        if (!value.startsWith("=")) {
            this.hideSuggestions();
            return;
        }

        const cursorPos = this.inputRef.el?.selectionStart || value.length;
        const beforeCursor = value.substring(1, cursorPos);

        // Find current word
        const wordMatch = beforeCursor.match(/([A-Z_][A-Z0-9_]*)$/i);
        if (!wordMatch || wordMatch[1].length < 1) {
            this.hideSuggestions();
            return;
        }

        const searchTerm = wordMatch[1].toUpperCase();

        // Get column suggestions
        const columns = this.props.columns || [];
        const suggestions = columns
            .filter(c =>
                c.column_letter.startsWith(searchTerm) ||
                c.code.toUpperCase().startsWith(searchTerm)
            )
            .slice(0, 6)
            .map(c => ({
                label: `${c.column_letter} (${c.code})`,
                value: c.column_letter,
                description: c.name,
            }));

        if (suggestions.length > 0) {
            this.state.suggestions = suggestions;
            this.state.selectedSuggestion = 0;
            this.state.showSuggestions = true;
        } else {
            this.hideSuggestions();
        }
    }

    hideSuggestions() {
        this.state.showSuggestions = false;
        this.state.suggestions = [];
        this.state.selectedSuggestion = 0;
    }

    selectNextSuggestion() {
        if (this.state.selectedSuggestion < this.state.suggestions.length - 1) {
            this.state.selectedSuggestion++;
        }
    }

    selectPreviousSuggestion() {
        if (this.state.selectedSuggestion > 0) {
            this.state.selectedSuggestion--;
        }
    }

    applySuggestion(index) {
        const suggestion = this.state.suggestions[index];
        if (!suggestion) return;

        const value = this.state.value;
        const cursorPos = this.inputRef.el?.selectionStart || value.length;
        const beforeCursor = value.substring(0, cursorPos);

        // Find and replace current word
        const wordMatch = beforeCursor.match(/([A-Z_][A-Z0-9_]*)$/i);
        if (wordMatch) {
            const startPos = cursorPos - wordMatch[1].length;
            const insertion = suggestion.value + "1"; // Add row reference

            this.state.value =
                value.substring(0, startPos) +
                insertion +
                value.substring(cursorPos);

            // Move cursor
            setTimeout(() => {
                if (this.inputRef.el) {
                    const newPos = startPos + insertion.length;
                    this.inputRef.el.setSelectionRange(newPos, newPos);
                }
            }, 0);
        }

        this.hideSuggestions();
        this.validate();
    }
}

export default CellEditor;
