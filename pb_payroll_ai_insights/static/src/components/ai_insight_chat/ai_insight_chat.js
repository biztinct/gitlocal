/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { ChartRenderer } from "../chart_renderer/chart_renderer";

/**
 * AiInsightChat — Floating pill → Centered modal chat for PayAI.
 * Renders as a persistent bottom-right pill that expands into a
 * centered modal with blurred backdrop (inspired by ChatGPT/Intercom).
 */
export class AiInsightChat extends Component {
    static template = "pb_payroll_ai_insights.AiInsightChat";
    static components = { ChartRenderer };

    setup() {
        this.notification = useService("notification");
        this.coach = useService("pb_coach");
        this.chatBodyRef = useRef("chatBody");
        this.inputRef = useRef("chatInput");

        this.state = useState({
            isOpen: false,
            isLoading: false,
            messages: [],
            inputText: "",
            sessionId: null,
            showSuggestions: true,
            aiIconUrl: false,
            isRecording: false,
            recordingDuration: 0,
        });

        // Voice recording state
        this._mediaRecorder = null;
        this._audioChunks = [];
        this._recordingTimer = null;

        this.suggestions = [
            "How do I run payroll?",
            "What is a formula config?",
            "Show me around Payobook",
            "Show me salary distribution by department",
            "What is the total headcount?",
            "Compare department payroll costs",
        ];

        onMounted(() => {
            this._loadHistory();
            this._loadAiIcon();
        });
    }

    // --- UI Actions ---

    togglePanel() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen && this.inputRef.el) {
            setTimeout(() => this.inputRef.el?.focus(), 300);
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
                drillDownModel: result.drilldown_model || "",
                intent: result.intent || "",
                action: result.action || null,
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

    // --- Coach action (launch a guided tour the AI recommended) ---
    runAction(action) {
        if (!action || action.type !== "start_tour" || !this.coach) return;
        this.closePanel();
        this.coach.start(action.tour, { mode: "interactive" });
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
            this.notification.add("Chart pinned to dashboard!", { type: "success" });
        } catch (error) {
            console.error("Pin to dashboard error:", error);
            this.notification.add("Failed to pin chart", { type: "danger" });
        }
    }

    // --- Voice Recording ---

    async toggleVoiceRecording() {
        if (this.state.isRecording) {
            this._stopRecording();
        } else {
            await this._startRecording();
        }
    }

    async _startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this._audioChunks = [];
            this._mediaRecorder = new MediaRecorder(stream, {
                mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                    ? 'audio/webm;codecs=opus' : 'audio/webm',
            });

            this._mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) this._audioChunks.push(e.data);
            };

            this._mediaRecorder.onstop = () => {
                // Stop all tracks
                stream.getTracks().forEach(t => t.stop());
                this._sendVoiceMessage();
            };

            this._mediaRecorder.start();
            this.state.isRecording = true;
            this.state.recordingDuration = 0;

            // Timer for visual feedback
            this._recordingTimer = setInterval(() => {
                this.state.recordingDuration++;
            }, 1000);
        } catch (err) {
            console.error("Microphone access denied:", err);
            this.notification.add(
                "Microphone access denied. Please allow microphone in browser settings.",
                { type: "warning" }
            );
        }
    }

    _stopRecording() {
        if (this._mediaRecorder && this._mediaRecorder.state === 'recording') {
            this._mediaRecorder.stop();
        }
        this.state.isRecording = false;
        if (this._recordingTimer) {
            clearInterval(this._recordingTimer);
            this._recordingTimer = null;
        }
    }

    async _sendVoiceMessage() {
        if (this._audioChunks.length === 0) return;

        const audioBlob = new Blob(this._audioChunks, { type: 'audio/webm' });
        this._audioChunks = [];

        // Convert to base64
        const arrayBuffer = await audioBlob.arrayBuffer();
        const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));

        // Show "Transcribing..." message
        this.state.messages.push({
            role: "user",
            content: "🎙️ Voice message (transcribing...)",
            chart: null,
            insights: [],
            isVoice: true,
            timestamp: new Date().toISOString(),
        });
        this.state.showSuggestions = false;
        this.state.isLoading = true;
        this._scrollToBottom();

        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_send_voice_message",
                args: [base64, this.state.sessionId, true],
                kwargs: {},
            });

            if (result.error) {
                // Update the user message to show error
                const lastUserMsg = this.state.messages[this.state.messages.length - 1];
                if (lastUserMsg) lastUserMsg.content = "🎙️ " + result.error;
                this.state.isLoading = false;
                return;
            }

            this.state.sessionId = result.session_id;

            // Update the user message with transcribed text
            const userMsg = this.state.messages[this.state.messages.length - 1];
            if (userMsg) {
                userMsg.content = "🎙️ " + (result.transcribed_text || "Voice message");
            }

            // Add assistant response
            this.state.messages.push({
                role: "assistant",
                content: result.response || "",
                chart: result.chart || null,
                insights: result.insights || [],
                followUpQuestions: result.follow_up_questions || [],
                drillDownModel: result.drilldown_model || "",
                intent: result.intent || "",
                action: result.action || null,
                hasTts: !!result.tts_audio,
                ttsAudio: result.tts_audio || null,
                timestamp: new Date().toISOString(),
            });

            // Auto-play TTS if available
            if (result.tts_audio) {
                this._playTtsAudio(result.tts_audio);
            }
        } catch (error) {
            console.error("PayAI voice error:", error);
            this.state.messages.push({
                role: "assistant",
                content: "Sorry, voice processing failed. Please try typing your question.",
                chart: null,
                insights: [],
                timestamp: new Date().toISOString(),
            });
        }

        this.state.isLoading = false;
        this._scrollToBottom();
    }

    _playTtsAudio(base64Audio) {
        try {
            const audioBytes = Uint8Array.from(atob(base64Audio), c => c.charCodeAt(0));
            const blob = new Blob([audioBytes], { type: 'audio/mp3' });
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.play().catch(e => console.warn("TTS autoplay blocked:", e));
            audio.onended = () => URL.revokeObjectURL(url);
        } catch (e) {
            console.warn("TTS playback error:", e);
        }
    }

    playMessageAudio(msg) {
        if (msg.ttsAudio) {
            this._playTtsAudio(msg.ttsAudio);
        }
    }

    formatRecordingTime() {
        const s = this.state.recordingDuration;
        const mins = Math.floor(s / 60);
        const secs = s % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // --- Helpers ---

    async _loadAiIcon() {
        try {
            const iconUrl = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.config",
                method: "rpc_get_ai_icon_url",
                args: [],
                kwargs: {},
            });
            if (iconUrl) {
                this.state.aiIconUrl = iconUrl;
            }
        } catch (error) {
            // Silently fail — will use fallback FA icon
            console.debug("No custom AI icon configured");
        }
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
