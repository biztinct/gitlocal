/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * GridActions - Action buttons and context menu for grid operations
 */
export class GridActions extends Component {
    static template = "pb_hr_payroll_formula.GridActions";
    static props = {
        configId: { type: Number },
        selectedColumn: { type: Object, optional: true },
        selectedCell: { type: Object, optional: true },
        onRefresh: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
    }

    // ==========================================
    // COLUMN ACTIONS
    // ==========================================

    async addColumn() {
        try {
            await this.orm.call(
                "hr.formula.config",
                "add_rule",
                [this.props.configId]
            );

            this.notification.add(_t("Column added successfully"), {
                type: "success",
            });

            if (this.props.onRefresh) {
                this.props.onRefresh();
            }
        } catch (error) {
            console.error("Failed to add column:", error);
            this.notification.add(_t("Failed to add column"), {
                type: "danger",
            });
        }
    }

    async duplicateColumn() {
        if (!this.props.selectedColumn) {
            this.notification.add(_t("Please select a column first"), {
                type: "warning",
            });
            return;
        }

        try {
            await this.orm.call(
                "hr.formula.rule",
                "copy",
                [this.props.selectedColumn.id]
            );

            this.notification.add(_t("Column duplicated"), {
                type: "success",
            });

            if (this.props.onRefresh) {
                this.props.onRefresh();
            }
        } catch (error) {
            console.error("Failed to duplicate column:", error);
            this.notification.add(_t("Failed to duplicate column"), {
                type: "danger",
            });
        }
    }

    async deleteColumn() {
        if (!this.props.selectedColumn) {
            this.notification.add(_t("Please select a column first"), {
                type: "warning",
            });
            return;
        }

        // Confirm deletion
        const confirmed = await this.confirmAction(
            _t("Delete Column"),
            _t("Are you sure you want to delete column %s (%s)?",
               this.props.selectedColumn.column_letter,
               this.props.selectedColumn.name)
        );

        if (!confirmed) return;

        try {
            await this.orm.unlink(
                "hr.formula.rule",
                [this.props.selectedColumn.id]
            );

            this.notification.add(_t("Column deleted"), {
                type: "success",
            });

            if (this.props.onRefresh) {
                this.props.onRefresh();
            }
        } catch (error) {
            console.error("Failed to delete column:", error);
            this.notification.add(_t("Failed to delete column"), {
                type: "danger",
            });
        }
    }

    openColumnSettings() {
        if (!this.props.selectedColumn) {
            this.notification.add(_t("Please select a column first"), {
                type: "warning",
            });
            return;
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.formula.rule",
            res_id: this.props.selectedColumn.id,
            views: [[false, "form"]],
            target: "new",
        });
    }

    // ==========================================
    // FORMULA ACTIONS
    // ==========================================

    async validateAllFormulas() {
        try {
            const result = await this.orm.call(
                "hr.formula.config",
                "action_validate_formulas",
                [this.props.configId]
            );

            const errorCount = Object.keys(result?.errors || {}).length;

            if (errorCount === 0) {
                this.notification.add(_t("All formulas are valid!"), {
                    type: "success",
                });
            } else {
                this.notification.add(
                    _t("%s formula(s) have errors", errorCount),
                    { type: "warning" }
                );
            }

            if (this.props.onRefresh) {
                this.props.onRefresh();
            }

            return result;
        } catch (error) {
            console.error("Validation failed:", error);
            this.notification.add(_t("Validation failed"), {
                type: "danger",
            });
        }
    }

    async convertAllFormulas() {
        try {
            await this.orm.call(
                "hr.formula.config",
                "action_convert_formulas",
                [this.props.configId]
            );

            this.notification.add(_t("Formulas converted to Python"), {
                type: "success",
            });

            if (this.props.onRefresh) {
                this.props.onRefresh();
            }
        } catch (error) {
            console.error("Conversion failed:", error);
            this.notification.add(_t("Conversion failed"), {
                type: "danger",
            });
        }
    }

    // ==========================================
    // TEST ACTIONS
    // ==========================================

    async runAllTests() {
        try {
            const result = await this.orm.call(
                "hr.formula.config",
                "action_run_tests",
                [this.props.configId]
            );

            if (result?.type === "ir.actions.act_window") {
                this.action.doAction(result);
            }
        } catch (error) {
            console.error("Test execution failed:", error);
            this.notification.add(_t("Test execution failed"), {
                type: "danger",
            });
        }
    }

    openSampleDataWizard() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.formula.sample.data.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_config_id: this.props.configId,
            },
        });
    }

    // ==========================================
    // IMPORT/EXPORT ACTIONS
    // ==========================================

    async exportConfiguration() {
        try {
            const result = await this.orm.call(
                "hr.formula.config",
                "action_export_config",
                [this.props.configId]
            );

            if (result?.url) {
                window.open(result.url, "_blank");
            }

            this.notification.add(_t("Configuration exported"), {
                type: "success",
            });
        } catch (error) {
            console.error("Export failed:", error);
            this.notification.add(_t("Export failed"), {
                type: "danger",
            });
        }
    }

    openImportWizard() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.formula.import.wizard",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_config_id: this.props.configId,
            },
        });
    }

    // ==========================================
    // SYNC ACTIONS
    // ==========================================

    async syncFromConnector() {
        try {
            const result = await this.orm.call(
                "hr.formula.config",
                "action_sync_from_connector",
                [this.props.configId]
            );

            this.notification.add(_t("Sync completed"), {
                type: "success",
            });

            if (this.props.onRefresh) {
                this.props.onRefresh();
            }
        } catch (error) {
            console.error("Sync failed:", error);
            this.notification.add(_t("Sync failed: %s", error.message), {
                type: "danger",
            });
        }
    }

    // ==========================================
    // UTILITY
    // ==========================================

    async confirmAction(title, message) {
        return new Promise((resolve) => {
            // Simple confirmation - in production use proper dialog
            const confirmed = window.confirm(message);
            resolve(confirmed);
        });
    }
}

/**
 * GridContextMenu - Right-click context menu for grid
 */
export class GridContextMenu extends Component {
    static template = "pb_hr_payroll_formula.GridContextMenu";
    static props = {
        x: { type: Number },
        y: { type: Number },
        cellType: { type: String },
        column: { type: Object, optional: true },
        onAction: { type: Function },
        onClose: { type: Function },
    };

    getMenuItems() {
        const items = [];

        if (this.props.cellType === "header") {
            items.push(
                { id: "settings", label: _t("Column Settings"), icon: "fa-cog" },
                { id: "duplicate", label: _t("Duplicate Column"), icon: "fa-copy" },
                { id: "insertLeft", label: _t("Insert Column Left"), icon: "fa-arrow-left" },
                { id: "insertRight", label: _t("Insert Column Right"), icon: "fa-arrow-right" },
                { divider: true },
                { id: "delete", label: _t("Delete Column"), icon: "fa-trash", danger: true }
            );
        } else if (this.props.cellType === "formula") {
            items.push(
                { id: "edit", label: _t("Edit Formula"), icon: "fa-edit" },
                { id: "validate", label: _t("Validate"), icon: "fa-check" },
                { id: "viewDependencies", label: _t("View Dependencies"), icon: "fa-sitemap" },
                { divider: true },
                { id: "clear", label: _t("Clear Formula"), icon: "fa-eraser" }
            );
        } else if (this.props.cellType === "sample") {
            items.push(
                { id: "edit", label: _t("Edit Value"), icon: "fa-edit" },
                { id: "copy", label: _t("Copy"), icon: "fa-copy" },
                { id: "paste", label: _t("Paste"), icon: "fa-paste" }
            );
        }

        return items;
    }

    onItemClick(item) {
        if (item.divider) return;
        this.props.onAction(item.id, this.props.column);
        this.props.onClose();
    }

    getStyle() {
        return `left: ${this.props.x}px; top: ${this.props.y}px;`;
    }
}

export default GridActions;
