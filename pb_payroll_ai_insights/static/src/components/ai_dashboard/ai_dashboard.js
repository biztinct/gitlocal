/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { ChartRenderer } from "../chart_renderer/chart_renderer";

/**
 * AiDashboard — AI-configurable dashboard with chart widget grid.
 * Users can add charts from chat, remove widgets, and generate dashboards via AI.
 */
export class AiDashboard extends Component {
    static template = "pb_payroll_ai_insights.AiDashboard";
    static components = { ChartRenderer };

    setup() {
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            dashboardId: null,
            dashboardName: "",
            widgets: [],
            isLoading: true,
            copilotText: "",
            isCopilotLoading: false,
        });

        onMounted(() => {
            this._loadDashboard();
        });
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
            this.notification.add("Dashboard updated! ✨", { type: "success" });
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
        await this._loadDashboard();
        this.notification.add("Dashboard refreshed", { type: "info" });
    }
}

registry.category("actions").add("payai_dashboard", AiDashboard);
