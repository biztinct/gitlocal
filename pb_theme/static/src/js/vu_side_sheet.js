/** @odoo-module */
// =============================================================================
// VuSideSheet — OWL component for contextual slide-in panels
// =============================================================================
// Provides a service-based API for opening side sheets programmatically,
// plus a component that can be used in OWL templates.
//
// Service usage:
//   const sideSheet = useService("vu_side_sheet");
//   sideSheet.open({ title: "Assign Staff", ... });
// =============================================================================

import { Component, useState, useRef, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class VuSideSheet extends Component {
    static template = "pb_theme.VuSideSheet";
    static props = {
        title: { type: String, optional: true },
        subtitle: { type: String, optional: true },
        isOpen: { type: Boolean, optional: true },
        onClose: { type: Function, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = {
        title: "Details",
        subtitle: "",
        isOpen: false,
    };

    setup() {
        this.state = useState({
            open: this.props.isOpen || false,
        });

        // Close on Escape key
        useExternalListener(window, "keydown", (ev) => {
            if (ev.key === "Escape" && this.state.open) {
                this.close();
            }
        });
    }

    get isOpen() {
        return this.state.open || this.props.isOpen;
    }

    open() {
        this.state.open = true;
        document.body.classList.add("vu-side-sheet-active");
    }

    close() {
        this.state.open = false;
        document.body.classList.remove("vu-side-sheet-active");
        if (this.props.onClose) {
            this.props.onClose();
        }
    }

    onBackdropClick() {
        this.close();
    }
}

// ---------------------------------------------------------------------------
// Side Sheet Service — for programmatic open/close from any component
// ---------------------------------------------------------------------------
const vuSideSheetService = {
    start() {
        let activeSheet = null;

        return {
            open(sheetComponent) {
                if (activeSheet) {
                    activeSheet.close();
                }
                activeSheet = sheetComponent;
                sheetComponent.open();
            },
            close() {
                if (activeSheet) {
                    activeSheet.close();
                    activeSheet = null;
                }
            },
            get isOpen() {
                return activeSheet?.state?.open || false;
            },
        };
    },
};

registry.category("services").add("vu_side_sheet", vuSideSheetService);
