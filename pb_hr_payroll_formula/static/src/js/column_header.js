/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

/**
 * ColumnHeader - Draggable column header with actions
 */
export class ColumnHeader extends Component {
    static template = "pb_hr_payroll_formula.ColumnHeader";
    static props = {
        column: { type: Object },
        index: { type: Number },
        isDragSource: { type: Boolean, optional: true },
        isDropTarget: { type: Boolean, optional: true },
        readonly: { type: Boolean, optional: true },
        onDragStart: { type: Function, optional: true },
        onDragEnd: { type: Function, optional: true },
        onSettings: { type: Function, optional: true },
        onDelete: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            showActions: false,
            isDragging: false,
        });
    }

    onMouseEnter() {
        this.state.showActions = true;
    }

    onMouseLeave() {
        this.state.showActions = false;
    }

    onDragStart(ev) {
        if (this.props.readonly) {
            ev.preventDefault();
            return;
        }

        this.state.isDragging = true;
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", this.props.index.toString());

        if (this.props.onDragStart) {
            this.props.onDragStart(ev, this.props.index);
        }
    }

    onDragEnd(ev) {
        this.state.isDragging = false;

        if (this.props.onDragEnd) {
            this.props.onDragEnd(ev);
        }
    }

    onSettingsClick(ev) {
        ev.stopPropagation();
        if (this.props.onSettings) {
            this.props.onSettings(this.props.index);
        }
    }

    onDeleteClick(ev) {
        ev.stopPropagation();
        if (this.props.onDelete) {
            this.props.onDelete(this.props.index);
        }
    }

    getColumnTypeIcon() {
        switch (this.props.column.column_type) {
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

    getHeaderClass() {
        const classes = ["column-header"];

        if (this.state.isDragging || this.props.isDragSource) {
            classes.push("dragging");
        }

        if (this.props.isDropTarget) {
            classes.push("drop-target");
        }

        if (!this.props.column.is_valid) {
            classes.push("has-error");
        }

        classes.push(`column-${this.props.column.column_type}`);

        return classes.join(" ");
    }
}

/**
 * ColumnResizer - Handle for resizing column width
 */
export class ColumnResizer extends Component {
    static template = "pb_hr_payroll_formula.ColumnResizer";
    static props = {
        columnIndex: { type: Number },
        onResize: { type: Function },
    };

    setup() {
        this.state = useState({
            isResizing: false,
            startX: 0,
            startWidth: 0,
        });
    }

    onMouseDown(ev) {
        ev.preventDefault();
        ev.stopPropagation();

        this.state.isResizing = true;
        this.state.startX = ev.clientX;

        // Get current column width
        const header = ev.target.closest("th");
        this.state.startWidth = header ? header.offsetWidth : 120;

        document.addEventListener("mousemove", this.onMouseMove);
        document.addEventListener("mouseup", this.onMouseUp);
    }

    onMouseMove = (ev) => {
        if (!this.state.isResizing) return;

        const delta = ev.clientX - this.state.startX;
        const newWidth = Math.max(60, this.state.startWidth + delta);

        this.props.onResize(this.props.columnIndex, newWidth);
    };

    onMouseUp = () => {
        this.state.isResizing = false;
        document.removeEventListener("mousemove", this.onMouseMove);
        document.removeEventListener("mouseup", this.onMouseUp);
    };
}

export default ColumnHeader;
