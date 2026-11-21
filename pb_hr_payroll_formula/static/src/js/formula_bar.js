/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

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
        this.orm = useService("orm");
        this.functions = this.getSupportedFunctions();
        onWillStart(() => this.loadFunctions());

        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
        });
    }

    // WDGAP PR-A — the list comes from the engine's ONE function table
    // (hr.formula.rule.pb_formula_functions). It used to be a hand-kept copy
    // that offered TODAY, NOW, LEFT, IFS … which computed nothing.
    getSupportedFunctions() {
        return [];
    }

    async loadFunctions() {
        try {
            const list = await this.orm.call("hr.formula.rule", "pb_formula_functions", []);
            this.functions = list.map((f) => ({
                name: f.name, category: f.category_label, description: f.help,
                syntax: f.signature, example: f.example,
            }));
        } catch {
            this.functions = [];
        }
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
