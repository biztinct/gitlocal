/** @odoo-module **/

import { Component, useState, onWillStart, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class AiCoachingChatWidget extends Component {
    static template = "hr_development_ai.AiCoachingChatWidget";
    static props = {
        record: { type: Object, optional: true },
        fieldName: { type: String, optional: true },
        orm: { type: Object, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.chatEndRef = useRef("chatEnd");

        this.state = useState({
            messages: [],
            inputMessage: "",
            isLoading: false,
            isExpanded: false,
        });

        onWillStart(async () => {
            await this.loadChatHistory();
        });

        onMounted(() => {
            this.scrollToBottom();
        });
    }

    /**
     * Get the field value (transcript)
     */
    get value() {
        const fieldName = this.props.fieldName || 'ai_transcript';
        return this.props.record?.data?.[fieldName] || "";
    }

    /**
     * Get record ID
     */
    get recordId() {
        return this.props.record?.resId || this.props.record?.data?.id || null;
    }

    /**
     * Get model name
     */
    get modelName() {
        return this.props.record?.resModel || 'hr.coaching.session';
    }

    get supportsSummary() {
        return this.modelName === 'hr.coaching.session';
    }

    /**
     * Load chat history from ai_transcript field
     */
    async loadChatHistory() {
        const transcript = this.value;
        if (!transcript) {
            return;
        }

        try {
            // Try to parse as JSON first (legacy format)
            const parsed = JSON.parse(transcript);
            this.state.messages = parsed.messages || [];
        } catch (e) {
            // Parse formatted text back into messages
            if (transcript.trim()) {
                const separator = '─────────────────────';
                const blocks = transcript.split(separator).map(b => b.trim()).filter(Boolean);
                const messages = [];
                for (const block of blocks) {
                    if (block.startsWith('👤 You:') || block.startsWith('👤 You:\n')) {
                        messages.push({
                            role: 'user',
                            content: block.replace(/^👤 You:\n?/, '').trim(),
                            timestamp: new Date().toISOString()
                        });
                    } else if (block.startsWith('🤖 AI Coach:') || block.startsWith('🤖 AI Coach:\n')) {
                        messages.push({
                            role: 'assistant',
                            content: block.replace(/^🤖 AI Coach:\n?/, '').trim(),
                            timestamp: new Date().toISOString()
                        });
                    } else {
                        // Fallback - treat as assistant message
                        messages.push({
                            role: 'assistant',
                            content: block,
                            timestamp: new Date().toISOString()
                        });
                    }
                }
                this.state.messages = messages.length > 0 ? messages : [{
                    role: 'assistant',
                    content: transcript,
                    timestamp: new Date().toISOString()
                }];
            }
        }
    }

    /**
     * Send message to AI
     */
    async sendMessage() {
        if (!this.state.inputMessage.trim() || this.state.isLoading) {
            return;
        }

        let recordId = this.recordId;
        if (!recordId) {
            if (!this.props.record) {
                this.notification.add('Cannot send message: No record available', { type: 'danger' });
                return;
            }

            try {
                await this.props.record.update({
                    user_message: this.state.inputMessage.trim(),
                });
                const saved = await this.props.record.save({ reload: false });
                if (!saved) {
                    this.notification.add('Cannot send message: Please fill required fields first', { type: 'warning' });
                    return;
                }
                recordId = this.recordId;
            } catch (error) {
                console.error('Failed to save record before sending message:', error);
                this.notification.add('Cannot send message: Please fill required fields first', { type: 'warning' });
                return;
            }
        }

        const userMessage = {
            role: 'user',
            content: this.state.inputMessage.trim(),
            timestamp: new Date().toISOString()
        };

        this.state.messages.push(userMessage);
        const messageContent = this.state.inputMessage;
        this.state.inputMessage = "";
        this.state.isLoading = true;

        setTimeout(() => this.scrollToBottom(), 100);

        try {
            const result = await this.orm.call(
                this.modelName,
                'action_send_ai_message',
                [recordId],
                {
                    message: messageContent
                }
            );

            const assistantMessage = {
                role: 'assistant',
                content: result.response || 'No response received',
                timestamp: new Date().toISOString()
            };

            this.state.messages.push(assistantMessage);

            // Save updated transcript
            await this.saveTranscript();

            setTimeout(() => this.scrollToBottom(), 100);
        } catch (error) {
            console.error('Error sending message:', error);
            this.notification.add(
                'Failed to send message to AI coach. Please try again.',
                { type: 'danger' }
            );
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Save transcript back to record
     */
    async saveTranscript() {
        if (!this.props.record) {
            console.warn('Cannot save transcript: No record');
            return;
        }

        const fieldName = this.props.fieldName || 'ai_transcript';
        const transcript = this.formatTranscript(this.state.messages);

        // Update the field value and persist
        await this.props.record.update({
            [fieldName]: transcript
        });
        if (this.props.record.save) {
            await this.props.record.save({ reload: true });
        }
    }

    /**
     * Format messages array into readable text
     */
    formatTranscript(messages) {
        if (!messages || !messages.length) return '';
        const lines = messages.map(msg => {
            if (msg.role === 'user') {
                return `👤 You:\n${msg.content}`;
            } else if (msg.role === 'assistant') {
                return `🤖 AI Coach:\n${msg.content}`;
            }
            return `${msg.role}:\n${msg.content}`;
        });
        return lines.join('\n\n─────────────────────\n\n');
    }

    /**
     * Generate AI summary
     */
    async generateSummary() {
        if (!this.supportsSummary) {
            this.notification.add('Summary is not available for this session.', { type: 'warning' });
            return;
        }

        const recordId = this.recordId;
        if (!recordId) {
            this.notification.add('Cannot generate summary: No record ID', { type: 'danger' });
            return;
        }

        this.state.isLoading = true;
        try {
            const result = await this.orm.call(
                this.modelName,
                'action_generate_ai_summary',
                [recordId]
            );

            this.notification.add(
                result.message || 'Summary generated successfully',
                { type: 'success' }
            );

            // Reload the record to show updated summary
            if (this.props.record?.load) {
                await this.props.record.load();
            }
        } catch (error) {
            console.error('Error generating summary:', error);
            this.notification.add(
                'Failed to generate summary. Please try again.',
                { type: 'danger' }
            );
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Handle Enter key in input
     */
    onKeydown(ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    /**
     * Toggle expanded view
     */
    toggleExpanded() {
        this.state.isExpanded = !this.state.isExpanded;
        setTimeout(() => this.scrollToBottom(), 100);
    }

    /**
     * Scroll chat to bottom
     */
    scrollToBottom() {
        if (this.chatEndRef.el) {
            this.chatEndRef.el.scrollIntoView({ behavior: 'smooth' });
        }
    }

    /**
     * Format timestamp for display
     */
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * Clear chat history
     */
    async clearChat() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            this.state.messages = [];
            await this.saveTranscript();
            this.notification.add('Chat history cleared', { type: 'info' });
        }
    }
}

// Widget is registered through ai_coaching_form_widget.js
