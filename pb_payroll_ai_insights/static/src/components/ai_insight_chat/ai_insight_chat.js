/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { ChartRenderer } from "../chart_renderer/chart_renderer";

/**
 * AiInsightChat — Floating pill + slide-out chat panel for PayAI.
 * Renders as a persistent bottom-right pill that expands into a chat panel.
 * Charts are rendered inline in chat messages using ChartRenderer.
 */
export class AiInsightChat extends Component {
    static template = "pb_payroll_ai_insights.AiInsightChat";
    static components = { ChartRenderer };

    setup() {
        this.notification = useService("notification");
        this.chatBodyRef = useRef("chatBody");
        this.inputRef = useRef("chatInput");

        this.state = useState({
            isOpen: false,
            isLoading: false,
            messages: [],
            inputText: "",
            sessionId: null,
            showSuggestions: true,
        });

        this.suggestions = [
            "Show me salary distribution by department",
            "What is the total headcount?",
            "Overtime costs this month",
            "Compare department payroll costs",
            "What does CTC stand for?",
        ];

        onMounted(() => {
            this._loadHistory();
        });
    }

    // --- UI Actions ---

    togglePanel() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen && this.inputRef.el) {
            setTimeout(() => this.inputRef.el?.focus(), 200);
        }
    }

    closePanel() {
        this.state.isOpen = false;
    }

    // --- Message Handling ---

    onInputKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    onInputChange(ev) {
        this.state.inputText = ev.target.value;
    }

    async sendSuggestion(text) {
        this.state.inputText = text;
        this.state.showSuggestions = false;
        await this.sendMessage();
    }

    async sendMessage() {
        const text = this.state.inputText.trim();
        if (!text || this.state.isLoading) return;

        // Add user message
        this.state.messages.push({
            role: "user",
            content: text,
            chart: null,
            insights: [],
            timestamp: new Date().toISOString(),
        });
        this.state.inputText = "";
        this.state.showSuggestions = false;
        this.state.isLoading = true;
        this._scrollToBottom();

        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_send_message",
                args: [text, this.state.sessionId],
                kwargs: {},
            });

            this.state.sessionId = result.session_id;

            // Add assistant message
            this.state.messages.push({
                role: "assistant",
                content: result.response || "",
                chart: result.chart || null,
                insights: result.insights || [],
                followUpQuestions: result.follow_up_questions || [],
                intent: result.intent || "",
                timestamp: new Date().toISOString(),
            });
        } catch (error) {
            console.error("PayAI error:", error);
            this.state.messages.push({
                role: "assistant",
                content: "I'm sorry, I encountered an error. Please check that PayAI is configured correctly in Settings.",
                chart: null,
                insights: [],
                timestamp: new Date().toISOString(),
            });
        }

        this.state.isLoading = false;
        this._scrollToBottom();
    }

    async clearHistory() {
        try {
            await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_clear_history",
                args: [this.state.sessionId],
                kwargs: {},
            });
            this.state.messages = [];
            this.state.sessionId = null;
            this.state.showSuggestions = true;
            this.notification.add("Chat history cleared", { type: "info" });
        } catch (error) {
            console.error("Clear history error:", error);
        }
    }

    // --- Pin to Dashboard ---

    async pinToDashboard(chartConfig) {
        if (!chartConfig) return;
        try {
            await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.dashboard",
                method: "rpc_add_widget",
                args: [chartConfig],
                kwargs: {},
            });
            this.notification.add("Chart pinned to dashboard! 📌", { type: "success" });
        } catch (error) {
            console.error("Pin to dashboard error:", error);
            this.notification.add("Failed to pin chart", { type: "danger" });
        }
    }

    // --- Helpers ---

    async _loadHistory() {
        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_get_history",
                args: [this.state.sessionId],
                kwargs: {},
            });
            if (result.session_id) {
                this.state.sessionId = result.session_id;
                this.state.messages = result.messages || [];
                if (this.state.messages.length > 0) {
                    this.state.showSuggestions = false;
                }
            }
        } catch (error) {
            console.error("Load history error:", error);
        }
    }

    _scrollToBottom() {
        setTimeout(() => {
            if (this.chatBodyRef.el) {
                this.chatBodyRef.el.scrollTop = this.chatBodyRef.el.scrollHeight;
            }
        }, 100);
    }

    formatTimestamp(ts) {
        if (!ts) return "";
        try {
            const d = new Date(ts);
            return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        } catch {
            return "";
        }
    }
}

// Register as a systray item (floating pill)
registry.category("main_components").add("AiInsightChat", {
    Component: AiInsightChat,
});
