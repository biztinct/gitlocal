/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { ChartRenderer } from "../chart_renderer/chart_renderer";

/**
 * AiDashboard — AI-configurable dashboard with Gridstack-powered drag & resize.
 */
export class AiDashboard extends Component {
    static template = "pb_payroll_ai_insights.AiDashboard";
    static components = { ChartRenderer };

    setup() {
        this.notification = useService("notification");
        this.action = useService("action");
        this.gridRef = useRef("gridContainer");
        this.grid = null;
        this._saveTimeout = null;

        this.state = useState({
            dashboardId: null,
            dashboardName: "",
            widgets: [],
            isLoading: true,
            copilotText: "",
            isCopilotLoading: false,
        });

        this._gridNeedsInit = false;

        onMounted(async () => {
            await this._loadDashboard();
            // Mark that grid needs init after OWL renders widget DOM
            this._gridNeedsInit = true;
        });

        // onPatched fires AFTER OWL has finished rendering DOM updates.
        // This is where Gridstack can safely find grid-stack-item elements.
        onPatched(() => {
            if (this._gridNeedsInit && this.state.widgets.length > 0) {
                this._gridNeedsInit = false;
                // Small delay to ensure DOM is fully painted
                requestAnimationFrame(() => {
                    setTimeout(() => this._initGridstack(), 50);
                });
            }
        });

        onWillUnmount(() => {
            this._destroyGrid();
            if (this._saveTimeout) {
                clearTimeout(this._saveTimeout);
            }
        });
    }

    // --- Gridstack ---

    _destroyGrid() {
        if (this.grid) {
            this.grid.destroy(false);
            this.grid = null;
        }
    }

    _initGridstack() {
        if (!this.gridRef.el || typeof GridStack === "undefined") {
            console.warn("Gridstack: container or library not available, retrying...");
            setTimeout(() => this._initGridstack(), 200);
            return;
        }

        // Don't re-init if already initialized
        if (this.grid) {
            this._destroyGrid();
        }

        // Initialize Gridstack
        this.grid = GridStack.init({
            column: 12,
            cellHeight: 80,
            margin: 10,
            animate: true,
            float: false,
            resizable: {
                handles: "se,sw",
            },
            draggable: {
                handle: ".payai-widget-header",
            },
            minRow: 1,
        }, this.gridRef.el);

        // Listen for changes (drag end, resize end)
        this.grid.on("change", (event, items) => {
            this._onGridChange(items);
        });

        // On resize, re-render charts inside resized widgets
        this.grid.on("resizestop", (event, el) => {
            // Trigger chart re-render by dispatching a resize event
            setTimeout(() => {
                window.dispatchEvent(new Event("resize"));
            }, 100);
        });
    }

    _onGridChange(items) {
        // Debounce save — don't fire on every pixel
        if (this._saveTimeout) clearTimeout(this._saveTimeout);
        this._saveTimeout = setTimeout(() => {
            this._savePositions();
        }, 800);
    }

    async _savePositions() {
        if (!this.grid) return;

        const items = this.grid.getGridItems();
        const positions = [];

        for (const el of items) {
            const node = el.gridstackNode;
            const widgetId = parseInt(el.getAttribute("data-widget-id"));
            if (node && widgetId) {
                positions.push({
                    id: widgetId,
                    x: node.x,
                    y: node.y,
                    w: node.w,
                    h: node.h,
                });
            }
        }

        if (positions.length === 0) return;

        try {
            await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.dashboard",
                method: "rpc_save_widget_positions",
                args: [positions],
                kwargs: {},
            });
        } catch (error) {
            console.error("Save positions error:", error);
        }
    }

    // --- Dashboard Actions ---

    async _loadDashboard() {
        this.state.isLoading = true;
        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.dashboard",
                method: "rpc_get_dashboard",
                args: [],
                kwargs: {},
            });
            this.state.dashboardId = result.dashboard_id;
            this.state.dashboardName = result.name;
            this.state.widgets = result.widgets || [];
        } catch (error) {
            console.error("Dashboard load error:", error);
        }
        this.state.isLoading = false;
    }

    async removeWidget(widgetId) {
        try {
            // Remove from Gridstack if present
            if (this.grid) {
                const el = this.gridRef.el?.querySelector(`[data-widget-id="${widgetId}"]`);
                if (el) {
                    this.grid.removeWidget(el, false);
                }
            }

            await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.dashboard",
                method: "rpc_remove_widget",
                args: [widgetId],
                kwargs: {},
            });
            this.state.widgets = this.state.widgets.filter(w => w.id !== widgetId);
            this.notification.add("Widget removed", { type: "info" });
        } catch (error) {
            console.error("Remove widget error:", error);
        }
    }

    // --- Copilot Bar ---

    onCopilotInput(ev) {
        this.state.copilotText = ev.target.value;
    }

    onCopilotKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.generateFromCopilot();
        }
    }

    async generateFromCopilot() {
        const text = this.state.copilotText.trim();
        if (!text || this.state.isCopilotLoading) return;

        this.state.isCopilotLoading = true;
        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.dashboard",
                method: "rpc_generate_dashboard",
                args: [text],
                kwargs: {},
            });
            this.state.widgets = result.widgets || [];
            this.state.copilotText = "";
            this.notification.add("Dashboard updated!", { type: "success" });

            // Flag for re-init after OWL re-renders
            this._destroyGrid();
            this._gridNeedsInit = true;
        } catch (error) {
            console.error("Copilot error:", error);
            this.notification.add("Failed to generate. Check AI configuration.", { type: "danger" });
        }
        this.state.isCopilotLoading = false;
    }

    openChat() {
        this.action.doAction("pb_payroll_ai_insights.action_payai_chat_full");
    }

    async refreshDashboard() {
        this._destroyGrid();
        await this._loadDashboard();
        this._gridNeedsInit = true;
        this.notification.add("Dashboard refreshed", { type: "info" });
    }
}

registry.category("actions").add("payai_dashboard", AiDashboard);
