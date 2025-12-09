/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * ExcelFormulaGrid - State-of-the-art Excel-like grid component
 *
 * Features:
 * - Excel-style column letters (A, B, C...Z, AA, AB)
 * - Drag-and-drop column reordering
 * - Formula bar with syntax highlighting
 * - Cell editing with autocomplete
 * - Light/Dark theme support
 * - Sample data row visualization
 * - Real-time formula validation
 */
export class ExcelFormulaGrid extends Component {
    static template = "pb_hr_payroll_formula.ExcelFormulaGrid";
    static props = {
        value: { type: Object, optional: true },
        record: { type: Object, optional: true },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            columns: [],
            sampleRows: [],
            selectedCell: null,
            selectedColumnIndex: null,
            formulaBarValue: "",
            isDragging: false,
            dragSourceIndex: null,
            dropTargetIndex: null,
            isEditing: false,
            editingCell: null,
            zoom: 100,
            theme: "light",
            showGridlines: true,
            showFormulaBar: true,
            frozenColumns: 1,
            isLoading: true,
            validationErrors: {},
            configId: null,
        });

        this.gridRef = useRef("grid");
        this.formulaBarRef = useRef("formulaBar");

        onMounted(() => this.initializeGrid());
        onWillUnmount(() => this.cleanup());

        useEffect(
            () => {
                if (this.props.record?.resId) {
                    this.loadGridData(this.props.record.resId);
                }
            },
            () => [this.props.record?.resId]
        );
    }

    // ==========================================
    // INITIALIZATION
    // ==========================================

    async initializeGrid() {
        this.state.isLoading = true;
        try {
            if (this.props.record?.resId) {
                await this.loadGridData(this.props.record.resId);
            }
            this.setupKeyboardShortcuts();
        } catch (error) {
            console.error("Grid initialization error:", error);
            this.notification.add(_t("Failed to initialize grid"), { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    async loadGridData(configId) {
        this.state.configId = configId;
        try {
            const data = await this.orm.call(
                "hr.formula.config",
                "get_grid_data",
                [configId]
            );

            this.state.columns = data.columns || [];
            this.state.sampleRows = data.sample_rows || [];
            this.state.theme = data.theme || "light";
            this.state.showFormulaBar = data.show_formula_bar !== false;

        } catch (error) {
            console.error("Failed to load grid data:", error);
            throw error;
        }
    }

    cleanup() {
        document.removeEventListener("keydown", this.handleGlobalKeyDown);
    }

    setupKeyboardShortcuts() {
        this.handleGlobalKeyDown = this.handleGlobalKeyDown.bind(this);
        document.addEventListener("keydown", this.handleGlobalKeyDown);
    }

    // ==========================================
    // COLUMN LETTER UTILITIES
    // ==========================================

    getColumnLetter(index) {
        let letter = "";
        let i = index;
        while (i >= 0) {
            letter = String.fromCharCode((i % 26) + 65) + letter;
            i = Math.floor(i / 26) - 1;
        }
        return letter;
    }

    letterToIndex(letter) {
        let result = 0;
        for (let i = 0; i < letter.length; i++) {
            result = result * 26 + (letter.charCodeAt(i) - 64);
        }
        return result - 1;
    }

    // ==========================================
    // CELL SELECTION
    // ==========================================

    onCellClick(columnIndex, rowType, rowIndex = null) {
        this.state.selectedColumnIndex = columnIndex;
        this.state.selectedCell = {
            column: columnIndex,
            rowType: rowType,
            rowIndex: rowIndex,
        };

        // Update formula bar
        if (rowType === "formula") {
            const column = this.state.columns[columnIndex];
            this.state.formulaBarValue = column?.excel_formula || "";
        } else if (rowType === "sample" && rowIndex !== null) {
            const sample = this.state.sampleRows[rowIndex];
            const column = this.state.columns[columnIndex];
            const value = sample?.values?.[column?.code] || "";
            this.state.formulaBarValue = String(value);
        } else {
            this.state.formulaBarValue = "";
        }
    }

    isCellSelected(columnIndex, rowType, rowIndex = null) {
        const sel = this.state.selectedCell;
        if (!sel) return false;
        return (
            sel.column === columnIndex &&
            sel.rowType === rowType &&
            sel.rowIndex === rowIndex
        );
    }

    // ==========================================
    // CELL EDITING
    // ==========================================

    onCellDoubleClick(columnIndex, rowType, rowIndex = null) {
        if (this.props.readonly) return;

        this.state.isEditing = true;
        this.state.editingCell = {
            column: columnIndex,
            rowType: rowType,
            rowIndex: rowIndex,
        };
    }

    onCellKeyDown(ev, columnIndex, rowType, rowIndex = null) {
        if (ev.key === "Enter" && !this.state.isEditing) {
            this.onCellDoubleClick(columnIndex, rowType, rowIndex);
            ev.preventDefault();
        } else if (ev.key === "Escape" && this.state.isEditing) {
            this.cancelEditing();
            ev.preventDefault();
        } else if (ev.key === "Tab") {
            this.moveSelection(ev.shiftKey ? -1 : 1);
            ev.preventDefault();
        } else if (ev.key === "ArrowRight") {
            this.moveSelection(1);
            ev.preventDefault();
        } else if (ev.key === "ArrowLeft") {
            this.moveSelection(-1);
            ev.preventDefault();
        }
    }

    moveSelection(direction) {
        if (this.state.selectedColumnIndex === null) return;

        const newIndex = this.state.selectedColumnIndex + direction;
        if (newIndex >= 0 && newIndex < this.state.columns.length) {
            this.onCellClick(newIndex, this.state.selectedCell?.rowType || "label");
        }
    }

    async commitEditing(newValue) {
        if (!this.state.editingCell) return;

        const { column, rowType, rowIndex } = this.state.editingCell;
        const columnData = this.state.columns[column];

        try {
            if (rowType === "formula") {
                await this.saveFormula(columnData.id, newValue);
                columnData.excel_formula = newValue;
            } else if (rowType === "label") {
                await this.saveColumnName(columnData.id, newValue);
                columnData.name = newValue;
            }

            this.state.isEditing = false;
            this.state.editingCell = null;

            // Trigger validation
            await this.validateFormulas();

        } catch (error) {
            console.error("Failed to save:", error);
            this.notification.add(_t("Failed to save changes"), { type: "danger" });
        }
    }

    cancelEditing() {
        this.state.isEditing = false;
        this.state.editingCell = null;
    }

    // ==========================================
    // FORMULA BAR
    // ==========================================

    onFormulaBarInput(ev) {
        this.state.formulaBarValue = ev.target.value;
    }

    async onFormulaBarKeyDown(ev) {
        if (ev.key === "Enter") {
            await this.commitFormulaBarValue();
            ev.preventDefault();
        } else if (ev.key === "Escape") {
            this.revertFormulaBarValue();
            ev.preventDefault();
        }
    }

    async commitFormulaBarValue() {
        const sel = this.state.selectedCell;
        if (!sel || sel.rowType !== "formula") return;

        const columnData = this.state.columns[sel.column];
        if (!columnData) return;

        try {
            await this.saveFormula(columnData.id, this.state.formulaBarValue);
            columnData.excel_formula = this.state.formulaBarValue;
            await this.validateFormulas();
            this.notification.add(_t("Formula saved"), { type: "success" });
        } catch (error) {
            console.error("Failed to save formula:", error);
            this.notification.add(_t("Failed to save formula"), { type: "danger" });
        }
    }

    revertFormulaBarValue() {
        const sel = this.state.selectedCell;
        if (!sel || sel.rowType !== "formula") return;

        const columnData = this.state.columns[sel.column];
        this.state.formulaBarValue = columnData?.excel_formula || "";
    }

    // ==========================================
    // DRAG AND DROP
    // ==========================================

    onColumnDragStart(ev, columnIndex) {
        if (this.props.readonly) return;

        this.state.isDragging = true;
        this.state.dragSourceIndex = columnIndex;

        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", columnIndex.toString());

        // Add visual feedback
        ev.target.classList.add("dragging");
    }

    onColumnDragOver(ev, targetIndex) {
        if (!this.state.isDragging) return;

        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";

        if (targetIndex !== this.state.dragSourceIndex) {
            this.state.dropTargetIndex = targetIndex;
        }
    }

    onColumnDragEnter(ev, targetIndex) {
        if (!this.state.isDragging) return;
        ev.preventDefault();
    }

    onColumnDragLeave(ev) {
        // Only clear if leaving the grid entirely
        if (!ev.relatedTarget?.closest(".excel-grid-header")) {
            this.state.dropTargetIndex = null;
        }
    }

    async onColumnDrop(ev, targetIndex) {
        ev.preventDefault();

        if (!this.state.isDragging || this.state.dragSourceIndex === null) return;

        const sourceIndex = this.state.dragSourceIndex;

        if (sourceIndex !== targetIndex) {
            await this.reorderColumns(sourceIndex, targetIndex);
        }

        this.resetDragState();
    }

    onColumnDragEnd(ev) {
        ev.target.classList.remove("dragging");
        this.resetDragState();
    }

    resetDragState() {
        this.state.isDragging = false;
        this.state.dragSourceIndex = null;
        this.state.dropTargetIndex = null;
    }

    async reorderColumns(fromIndex, toIndex) {
        try {
            // Reorder locally first for instant feedback
            const columns = [...this.state.columns];
            const [movedColumn] = columns.splice(fromIndex, 1);
            columns.splice(toIndex, 0, movedColumn);

            // Update sequences
            columns.forEach((col, idx) => {
                col.sequence = idx * 10;
                col.column_letter = this.getColumnLetter(idx);
            });

            this.state.columns = columns;

            // Save to server
            await this.orm.call(
                "hr.formula.config",
                "reorder_columns",
                [this.state.configId, fromIndex, toIndex]
            );

            this.notification.add(_t("Columns reordered"), { type: "success" });

            // Refresh to get updated formula references
            await this.loadGridData(this.state.configId);

        } catch (error) {
            console.error("Failed to reorder columns:", error);
            this.notification.add(_t("Failed to reorder columns"), { type: "danger" });
            // Reload to restore original order
            await this.loadGridData(this.state.configId);
        }
    }

    // ==========================================
    // DATA OPERATIONS
    // ==========================================

    async saveFormula(ruleId, formula) {
        await this.orm.write("hr.formula.rule", [ruleId], {
            excel_formula: formula,
        });
    }

    async saveColumnName(ruleId, name) {
        await this.orm.write("hr.formula.rule", [ruleId], {
            name: name,
        });
    }

    async validateFormulas() {
        try {
            const result = await this.orm.call(
                "hr.formula.config",
                "action_validate_formulas",
                [this.state.configId]
            );

            this.state.validationErrors = result?.errors || {};

            // Update column validation status
            this.state.columns.forEach(col => {
                col.is_valid = !this.state.validationErrors[col.code];
                col.validation_message = this.state.validationErrors[col.code] || "";
            });

        } catch (error) {
            console.error("Validation failed:", error);
        }
    }

    async runTests() {
        try {
            const result = await this.orm.call(
                "hr.formula.config",
                "action_run_tests",
                [this.state.configId]
            );

            if (result?.type === "ir.actions.act_window") {
                this.action.doAction(result);
            }
        } catch (error) {
            console.error("Test execution failed:", error);
            this.notification.add(_t("Test execution failed"), { type: "danger" });
        }
    }

    // ==========================================
    // KEYBOARD SHORTCUTS
    // ==========================================

    handleGlobalKeyDown(ev) {
        // Only handle when grid is focused
        if (!this.gridRef.el?.contains(document.activeElement)) return;

        if (ev.ctrlKey || ev.metaKey) {
            switch (ev.key) {
                case "s":
                    this.commitFormulaBarValue();
                    ev.preventDefault();
                    break;
                case "z":
                    // TODO: Implement undo
                    ev.preventDefault();
                    break;
            }
        }
    }

    // ==========================================
    // UI HELPERS
    // ==========================================

    getColumnTypeIcon(type) {
        switch (type) {
            case "input":
                return "fa-sign-in";
            case "formula":
                return "fa-calculator";
            case "constant":
                return "fa-lock";
            default:
                return "fa-question";
        }
    }

    getColumnTypeClass(type) {
        switch (type) {
            case "input":
                return "column-input";
            case "formula":
                return "column-formula";
            case "constant":
                return "column-constant";
            default:
                return "";
        }
    }

    formatCellValue(value, format) {
        if (value === null || value === undefined) return "";

        const numValue = parseFloat(value);
        if (isNaN(numValue)) return value;

        switch (format) {
            case "currency":
                return new Intl.NumberFormat("en-US", {
                    style: "decimal",
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                }).format(numValue);
            case "percentage":
                return (numValue * 100).toFixed(2) + "%";
            case "integer":
                return Math.round(numValue).toLocaleString();
            default:
                return numValue.toLocaleString();
        }
    }

    toggleTheme() {
        this.state.theme = this.state.theme === "light" ? "dark" : "light";
    }

    zoomIn() {
        if (this.state.zoom < 150) {
            this.state.zoom += 10;
        }
    }

    zoomOut() {
        if (this.state.zoom > 50) {
            this.state.zoom -= 10;
        }
    }

    // ==========================================
    // ACTIONS
    // ==========================================

    async addColumn() {
        try {
            await this.orm.call(
                "hr.formula.config",
                "add_rule",
                [this.state.configId]
            );
            await this.loadGridData(this.state.configId);
            this.notification.add(_t("Column added"), { type: "success" });
        } catch (error) {
            console.error("Failed to add column:", error);
            this.notification.add(_t("Failed to add column"), { type: "danger" });
        }
    }

    async deleteColumn(columnIndex) {
        const column = this.state.columns[columnIndex];
        if (!column) return;

        try {
            await this.orm.unlink("hr.formula.rule", [column.id]);
            await this.loadGridData(this.state.configId);
            this.notification.add(_t("Column deleted"), { type: "success" });
        } catch (error) {
            console.error("Failed to delete column:", error);
            this.notification.add(_t("Failed to delete column"), { type: "danger" });
        }
    }

    openColumnSettings(columnIndex) {
        const column = this.state.columns[columnIndex];
        if (!column) return;

        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.formula.rule",
            res_id: column.id,
            views: [[false, "form"]],
            target: "new",
        });
    }
}

// Register the component as a field widget
registry.category("fields").add("excel_formula_grid", {
    component: ExcelFormulaGrid,
    supportedTypes: ["text", "char"],
});

export default ExcelFormulaGrid;
