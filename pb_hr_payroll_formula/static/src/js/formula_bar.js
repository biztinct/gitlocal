/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/**
 * FormulaBar - Enhanced formula input with autocomplete and syntax highlighting
 */
export class FormulaBar extends Component {
    static template = "pb_hr_payroll_formula.FormulaBar";
    static props = {
        value: { type: String, optional: true },
        cellReference: { type: String, optional: true },
        rowType: { type: String, optional: true },
        readonly: { type: Boolean, optional: true },
        columns: { type: Array, optional: true },
        onCommit: { type: Function, optional: true },
        onCancel: { type: Function, optional: true },
        onChange: { type: Function, optional: true },
    };

    setup() {
        this.inputRef = useRef("input");

        this.state = useState({
            showAutocomplete: false,
            autocompleteItems: [],
            highlightedIndex: 0,
            showHelp: false,
            currentFunction: null,
            cursorPosition: 0,
        });

        // Supported Excel functions with descriptions
        this.functions = this.getSupportedFunctions();

        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
        });
    }

    getSupportedFunctions() {
        return [
            // Math functions
            { name: "SUM", category: _t("Math"), description: _t("Adds all numbers in a range"), syntax: "SUM(number1, [number2], ...)" },
            { name: "AVERAGE", category: _t("Math"), description: _t("Returns the average of arguments"), syntax: "AVERAGE(number1, [number2], ...)" },
            { name: "MIN", category: _t("Math"), description: _t("Returns the minimum value"), syntax: "MIN(number1, [number2], ...)" },
            { name: "MAX", category: _t("Math"), description: _t("Returns the maximum value"), syntax: "MAX(number1, [number2], ...)" },
            { name: "ABS", category: _t("Math"), description: _t("Returns absolute value"), syntax: "ABS(number)" },
            { name: "ROUND", category: _t("Math"), description: _t("Rounds to specified digits"), syntax: "ROUND(number, num_digits)" },
            { name: "ROUNDUP", category: _t("Math"), description: _t("Rounds up to specified digits"), syntax: "ROUNDUP(number, num_digits)" },
            { name: "ROUNDDOWN", category: _t("Math"), description: _t("Rounds down to specified digits"), syntax: "ROUNDDOWN(number, num_digits)" },
            { name: "CEILING", category: _t("Math"), description: _t("Rounds up to nearest multiple"), syntax: "CEILING(number, significance)" },
            { name: "FLOOR", category: _t("Math"), description: _t("Rounds down to nearest multiple"), syntax: "FLOOR(number, significance)" },
            { name: "POWER", category: _t("Math"), description: _t("Returns number raised to power"), syntax: "POWER(number, power)" },
            { name: "SQRT", category: _t("Math"), description: _t("Returns square root"), syntax: "SQRT(number)" },
            { name: "MOD", category: _t("Math"), description: _t("Returns remainder after division"), syntax: "MOD(number, divisor)" },
            { name: "INT", category: _t("Math"), description: _t("Rounds down to nearest integer"), syntax: "INT(number)" },

            // Logical functions
            { name: "IF", category: _t("Logical"), description: _t("Conditional evaluation"), syntax: "IF(condition, value_if_true, [value_if_false])" },
            { name: "AND", category: _t("Logical"), description: _t("Returns TRUE if all conditions are true"), syntax: "AND(logical1, [logical2], ...)" },
            { name: "OR", category: _t("Logical"), description: _t("Returns TRUE if any condition is true"), syntax: "OR(logical1, [logical2], ...)" },
            { name: "NOT", category: _t("Logical"), description: _t("Reverses the logic"), syntax: "NOT(logical)" },
            { name: "IFERROR", category: _t("Logical"), description: _t("Returns value if no error"), syntax: "IFERROR(value, value_if_error)" },
            { name: "IFS", category: _t("Logical"), description: _t("Multiple conditions"), syntax: "IFS(condition1, value1, [condition2, value2], ...)" },

            // Text functions
            { name: "CONCATENATE", category: _t("Text"), description: _t("Joins text strings"), syntax: "CONCATENATE(text1, [text2], ...)" },
            { name: "LEFT", category: _t("Text"), description: _t("Returns leftmost characters"), syntax: "LEFT(text, [num_chars])" },
            { name: "RIGHT", category: _t("Text"), description: _t("Returns rightmost characters"), syntax: "RIGHT(text, [num_chars])" },
            { name: "MID", category: _t("Text"), description: _t("Returns characters from middle"), syntax: "MID(text, start_num, num_chars)" },
            { name: "LEN", category: _t("Text"), description: _t("Returns length of text"), syntax: "LEN(text)" },
            { name: "UPPER", category: _t("Text"), description: _t("Converts to uppercase"), syntax: "UPPER(text)" },
            { name: "LOWER", category: _t("Text"), description: _t("Converts to lowercase"), syntax: "LOWER(text)" },
            { name: "TRIM", category: _t("Text"), description: _t("Removes extra spaces"), syntax: "TRIM(text)" },

            // Lookup functions
            { name: "VLOOKUP", category: _t("Lookup"), description: _t("Vertical lookup"), syntax: "VLOOKUP(lookup_value, table, col_index, [range_lookup])" },
            { name: "HLOOKUP", category: _t("Lookup"), description: _t("Horizontal lookup"), syntax: "HLOOKUP(lookup_value, table, row_index, [range_lookup])" },
            { name: "INDEX", category: _t("Lookup"), description: _t("Returns value at position"), syntax: "INDEX(array, row_num, [col_num])" },
            { name: "MATCH", category: _t("Lookup"), description: _t("Returns position of value"), syntax: "MATCH(lookup_value, lookup_array, [match_type])" },

            // Statistical functions
            { name: "COUNT", category: _t("Statistical"), description: _t("Counts numbers"), syntax: "COUNT(value1, [value2], ...)" },
            { name: "COUNTA", category: _t("Statistical"), description: _t("Counts non-empty cells"), syntax: "COUNTA(value1, [value2], ...)" },
            { name: "COUNTIF", category: _t("Statistical"), description: _t("Counts cells matching criteria"), syntax: "COUNTIF(range, criteria)" },
            { name: "SUMIF", category: _t("Statistical"), description: _t("Sums cells matching criteria"), syntax: "SUMIF(range, criteria, [sum_range])" },
            { name: "AVERAGEIF", category: _t("Statistical"), description: _t("Averages cells matching criteria"), syntax: "AVERAGEIF(range, criteria, [average_range])" },

            // Date functions
            { name: "TODAY", category: _t("Date"), description: _t("Returns current date"), syntax: "TODAY()" },
            { name: "NOW", category: _t("Date"), description: _t("Returns current date and time"), syntax: "NOW()" },
            { name: "YEAR", category: _t("Date"), description: _t("Returns year from date"), syntax: "YEAR(date)" },
            { name: "MONTH", category: _t("Date"), description: _t("Returns month from date"), syntax: "MONTH(date)" },
            { name: "DAY", category: _t("Date"), description: _t("Returns day from date"), syntax: "DAY(date)" },
        ];
    }

    onInput(ev) {
        const value = ev.target.value;
        this.state.cursorPosition = ev.target.selectionStart;

        if (this.props.onChange) {
            this.props.onChange(value);
        }

        // Check for autocomplete trigger
        this.updateAutocomplete(value);
    }

    onKeyDown(ev) {
        if (this.state.showAutocomplete) {
            switch (ev.key) {
                case "ArrowDown":
                    ev.preventDefault();
                    this.highlightNext();
                    break;
                case "ArrowUp":
                    ev.preventDefault();
                    this.highlightPrevious();
                    break;
                case "Enter":
                    if (this.state.autocompleteItems.length > 0) {
                        ev.preventDefault();
                        this.selectAutocompleteItem(this.state.highlightedIndex);
                    }
                    break;
                case "Escape":
                    ev.preventDefault();
                    this.hideAutocomplete();
                    break;
                case "Tab":
                    if (this.state.autocompleteItems.length > 0) {
                        ev.preventDefault();
                        this.selectAutocompleteItem(this.state.highlightedIndex);
                    }
                    break;
            }
        } else {
            if (ev.key === "Enter") {
                ev.preventDefault();
                if (this.props.onCommit) {
                    this.props.onCommit(ev.target.value);
                }
            } else if (ev.key === "Escape") {
                ev.preventDefault();
                if (this.props.onCancel) {
                    this.props.onCancel();
                }
            }
        }
    }

    updateAutocomplete(value) {
        if (!value.startsWith("=")) {
            this.hideAutocomplete();
            return;
        }

        const cursorPos = this.state.cursorPosition;
        const beforeCursor = value.substring(0, cursorPos);

        // Find the current word being typed
        const match = beforeCursor.match(/([A-Z_][A-Z0-9_]*)$/i);

        if (match && match[1].length >= 1) {
            const searchTerm = match[1].toUpperCase();

            // Search functions
            const matchingFunctions = this.functions.filter(f =>
                f.name.startsWith(searchTerm)
            ).slice(0, 8);

            // Search columns
            const matchingColumns = (this.props.columns || []).filter(c =>
                c.column_letter.startsWith(searchTerm) ||
                c.code.toUpperCase().startsWith(searchTerm) ||
                c.name.toUpperCase().includes(searchTerm)
            ).slice(0, 5).map(c => ({
                type: "column",
                name: c.column_letter,
                code: c.code,
                description: c.name,
            }));

            const items = [
                ...matchingFunctions.map(f => ({ type: "function", ...f })),
                ...matchingColumns,
            ];

            if (items.length > 0) {
                this.state.autocompleteItems = items;
                this.state.highlightedIndex = 0;
                this.state.showAutocomplete = true;
            } else {
                this.hideAutocomplete();
            }
        } else {
            this.hideAutocomplete();
        }
    }

    hideAutocomplete() {
        this.state.showAutocomplete = false;
        this.state.autocompleteItems = [];
        this.state.highlightedIndex = 0;
    }

    highlightNext() {
        if (this.state.highlightedIndex < this.state.autocompleteItems.length - 1) {
            this.state.highlightedIndex++;
        }
    }

    highlightPrevious() {
        if (this.state.highlightedIndex > 0) {
            this.state.highlightedIndex--;
        }
    }

    selectAutocompleteItem(index) {
        const item = this.state.autocompleteItems[index];
        if (!item) return;

        const value = this.props.value || "";
        const cursorPos = this.state.cursorPosition;
        const beforeCursor = value.substring(0, cursorPos);

        // Find and replace the current word
        const match = beforeCursor.match(/([A-Z_][A-Z0-9_]*)$/i);
        if (match) {
            const startPos = cursorPos - match[1].length;
            let insertion = "";

            if (item.type === "function") {
                insertion = item.name + "(";
                this.showFunctionHelp(item);
            } else if (item.type === "column") {
                insertion = item.name + "1";  // Add row reference
            }

            const newValue = value.substring(0, startPos) + insertion + value.substring(cursorPos);

            if (this.props.onChange) {
                this.props.onChange(newValue);
            }

            // Set cursor position after insertion
            setTimeout(() => {
                if (this.inputRef.el) {
                    const newPos = startPos + insertion.length;
                    this.inputRef.el.setSelectionRange(newPos, newPos);
                    this.inputRef.el.focus();
                }
            }, 0);
        }

        this.hideAutocomplete();
    }

    showFunctionHelp(func) {
        this.state.currentFunction = func;
        this.state.showHelp = true;

        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (this.state.currentFunction === func) {
                this.state.showHelp = false;
                this.state.currentFunction = null;
            }
        }, 5000);
    }

    hideFunctionHelp() {
        this.state.showHelp = false;
        this.state.currentFunction = null;
    }

    onCommitClick() {
        if (this.props.onCommit && this.inputRef.el) {
            this.props.onCommit(this.inputRef.el.value);
        }
    }

    onCancelClick() {
        if (this.props.onCancel) {
            this.props.onCancel();
        }
    }
}

export default FormulaBar;
