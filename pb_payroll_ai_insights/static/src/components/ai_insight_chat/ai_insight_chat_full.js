/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { ChartRenderer } from "../chart_renderer/chart_renderer";

/**
 * AiInsightChatFull — Full-page PayAI chat client action.
 * Provides a larger workspace for deep analysis with charts.
 */
export class AiInsightChatFull extends Component {
    static template = "pb_payroll_ai_insights.AiInsightChatFull";
    static components = { ChartRenderer };

    setup() {
        this.notification = useService("notification");
        this.action = useService("action");
        this.chatBodyRef = useRef("chatBody");
        this.inputRef = useRef("chatInput");

        this.state = useState({
            isLoading: false,
            messages: [],
            inputText: "",
            sessionId: null,
            showSuggestions: true,
        });

        this.suggestions = [
            "📊 Show salary distribution by department",
            "👥 What is our total headcount breakdown?",
            "⏰ Overtime costs for the last 3 months",
            "💰 Total payroll cost trend",
            "📈 Compare department payroll costs",
            "🏦 Show deduction breakdown this month",
            "❓ What does CTC stand for?",
            "📧 Draft an email about salary review",
        ];

        onMounted(() => {
            this._loadHistory();
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
        });
    }

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
                content: "Sorry, I encountered an error. Please check PayAI configuration.",
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
        } catch (error) {
            console.error("Clear error:", error);
        }
    }

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
            this.notification.add("Failed to pin chart", { type: "danger" });
        }
    }

    openDashboard() {
        this.action.doAction("pb_payroll_ai_insights.action_payai_dashboard");
    }

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
                    this._scrollToBottom();
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
            return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        } catch {
            return "";
        }
    }
}

// Register as client action
registry.category("actions").add("payai_chat_full", AiInsightChatFull);
