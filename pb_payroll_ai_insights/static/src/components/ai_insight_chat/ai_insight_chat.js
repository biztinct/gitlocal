/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { ChartRenderer } from "../chart_renderer/chart_renderer";
// LEARN REFRESH step 1 — where the user is, as the hubs publish it, and the
// hub door the "Show me" hand-off now goes through (both via pb_learn's
// dependency on pb_hub).
import { hubPlace } from "@pb_hub/js/hub_place";
import { openHub } from "@pb_hub/js/hub_nav";

// LEARNOS Phase 6. A ceiling on one held press, and where the read-aloud
// preference is remembered. Both are browser-side: the recording ceiling is a
// courtesy to the person holding the button, and the server's own gates are
// what decide whether any of this is offered at all.
const MAX_RECORDING_SECONDS = 60;
const TTS_PREF = "payaiReadAloud";

/**
 * AiInsightChat — Floating pill → Centered modal chat for PayAI.
 * Renders as a persistent bottom-right pill that expands into a
 * centered modal with blurred backdrop (inspired by ChatGPT/Intercom).
 */
export class AiInsightChat extends Component {
    static template = "pb_payroll_ai_insights.AiInsightChat";
    static components = { ChartRenderer };
    // LEARN v3. True only for the copy drawn inside the helper drawer.
    static embedded = false;

    setup() {
        // LEARN v3 — ONE HELPER. When pb_learn's helper is installed it is the
        // only floating control, and this chat is its "Ask" tab. The copy
        // mounted in main_components then draws nothing and fetches nothing.
        // Read at setup: every module's assets load before the web client
        // mounts, so the registry is complete by now.
        this.hosted = !this.constructor.embedded
            && registry.category("pb_helper_host").contains("orb");
        this.notification = useService("notification");
        this.actionService = useService("action");
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
            // LEARNOS Phase 6 — voice.
            //
            // `voice.available` decides whether a microphone is DRAWN at all.
            // Not disabled-with-a-tooltip: on a database with no speech
            // provider, or a tenant that never switched voice on, or a user
            // who said no, the honest interface has no microphone in it. The
            // server answers this (`rpc_voice_status`) because both gates
            // live there and the browser's copy is a hint, never the control.
            voice: { available: false, ask: false, consent: "unset", copy: {} },
            voiceAsking: false,     // the consent card is up
            voiceBusy: false,       // transcribing
            voiceHint: "",          // "this is what I heard" — shown once
            voiceError: "",
            ttsOn: false,
        });

        // Voice recording state
        this._mediaRecorder = null;
        this._audioChunks = [];
        this._recordingTimer = null;
        this._recordingStream = null;
        this._keyHeld = false;
        // M2. Set BEFORE the stream is released on unmount, and re-asked by
        // the recorder's own `onstop`: stopping a MediaRecorder fires that
        // callback asynchronously, so a drawer closed mid-recording would
        // otherwise post the audio it was holding after the component that
        // asked for it no longer exists. The flag is the only thing between
        // "the user closed it" and "a recording left the browser".
        this._discarded = false;

        // ERRORS E4-4. The starter questions a person actually clicks. They
        // were bare literals: untranslated in Vietnamese, and — for the third
        // one — offering a Rize employee a tour of a product they have never
        // heard of. `_t` is both fixes; `String(...)` keeps them primitives so
        // the template and the send path treat them as ordinary text.
        this.suggestions = [
            _t("How do I run payroll?"),
            _t("What is a formula config?"),
            _t("Show me around Payobook"),
            _t("Show me salary distribution by department"),
            _t("What is the total headcount?"),
            _t("Compare department payroll costs"),
        ].map(String);

        onMounted(() => {
            if (this.hosted) {
                return;
            }
            // Kept as a promise so a question handed over from the guide is
            // sent AFTER the history lands, not overwritten by it.
            this._historyReady = this._loadHistory();
            this._loadAiIcon();
            this._loadVoiceStatus();
            this._restoreTtsPreference();
        });
        onWillUnmount(() => {
            // ORDER IS THE CONTROL, not the tidy-up. The discard flag and the
            // emptied buffer come FIRST, before the recorder is touched: a
            // recorder still holding the microphone after the component is
            // gone is a live red dot in the tab strip, and a recorder that
            // fires `onstop` on the way out is an audio POST from a drawer
            // nobody has open.
            this._discarded = true;
            this._audioChunks = [];
            this._releaseMicrophone();
            this._stopSpeaking();
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
        // The "check what I heard" hint belongs to the text that has now been
        // sent; leaving it over the empty box would read as a warning about
        // the next thing typed.
        this.state.voiceHint = "";
        this.state.voiceError = "";

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
                args: [text, this.state.sessionId, this._currentScreen()],
                kwargs: {},
            }, { silent: true });  // suppress Odoo's global spinner — we show typing dots

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
            if (this.state.ttsOn) {
                // On the device. See the note above `ttsSupported`.
                this.speak(result.response || "");
            }
        } catch (error) {
            console.error("PayAI error:", error);
            this.state.messages.push({
                role: "assistant",
                content: _t("That did not work. An administrator can check the AI service under PayAI settings."),
                chart: null,
                insights: [],
                timestamp: new Date().toISOString(),
            });
        }

        this.state.isLoading = false;
        this._scrollToBottom();
    }

    // Current cockpit, sent with each message so the AI can answer "how do I do
    // THIS?" relative to where the user is standing.
    //
    // LEARN REFRESH step 1: inside a hub the action is the HUB whichever tab
    // is showing, so the hub and tab the hub itself published ride along —
    // plain labels, as the rail shows them ("Pay Run", "Payslips").
    _currentScreen() {
        try {
            const a = this.actionService.currentController && this.actionService.currentController.action;
            if (!a) return null;
            const screen = { tag: a.tag || "", xml_id: a.xml_id || "", model: a.res_model || "", name: a.name || "" };
            if (hubPlace.tag && a.tag === hubPlace.tag) {
                const lens = (hubPlace.lenses || []).find((l) => l.key === hubPlace.lens);
                screen.hub = hubPlace.hubLabel || "";
                screen.tab = lens ? lens.label : "";
            }
            return screen;
        } catch (e) { return null; }
    }

    // --- The "Show me" button: open the lesson the AI recommended ---
    //
    // ONE shape reaches this method. `_sanitize_action` on the server accepts a
    // legacy `start_tour` envelope and CONVERTS it, then always emits
    // `open_lesson` — so a client-side tour branch could never be entered, and
    // one that existed anyway would be a pb_coach dependency kept alive by a
    // path nothing can reach. The legacy acceptance stays where it can actually
    // be exercised: server-side, where the LLM's output arrives.
    runAction(action) {
        if (!action || action.type !== "open_lesson" || !action.lesson) {
            return;
        }
        this.closePanel();
        // `doAction` is ASYNC — it returns a promise and rejects, it does not
        // throw. A synchronous try/catch around it catches nothing, which is
        // exactly what shipped and what this replaces. The failure is live
        // today: PayAI does not declare pb_learn as a dependency until the
        // deploy-time manifest swap, so on a database without it this click
        // would otherwise surface as an unhandled rejection and no feedback.
        // LEARN REFRESH step 1: the lesson opens inside the Learn hub, on
        // its Lessons tab, so the rail is still there when it finishes.
        // Same deep link, carried as the hub's arrival focus.
        Promise.resolve(
            openHub(this.actionService, {
                xmlid: "pb_learn.action_learn_hub",
                lens: "lessons",
                focus: `lesson:${action.lesson}`,
            })
        ).catch(() => {
            this.notification.add(
                "The guided lessons are not installed on this database.",
                { type: "warning" }
            );
        });
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
        this.notification.add(_t("Chat history cleared"), { type: "info" });
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
            this.notification.add(_t("Chart pinned to dashboard!"), { type: "success" });
        } catch (error) {
            console.error("Pin to dashboard error:", error);
            this.notification.add(_t("Failed to pin chart"), { type: "danger" });
        }
    }

    // ------------------------------------------------------------------
    // VOICE  (LEARNOS Phase 6)
    //
    // HOLD TO TALK, AND THE TRANSCRIPT LANDS IN THE BOX. It does not send.
    // The old flow recorded, transcribed and submitted in one gesture, so the
    // first time anybody saw what had been heard was in the transcript of a
    // question already answered — and on a payroll help box that sentence is
    // often a colleague's name and their pay. Now: hold, speak, release, READ
    // it, then press send like any other question. The server cannot submit
    // either (`rpc_transcribe_voice` returns text and has no send path in it),
    // so this is not a discipline the frontend keeps on its own.
    // ------------------------------------------------------------------

    async _loadVoiceStatus() {
        try {
            const status = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_voice_status",
                args: [], kwargs: {},
            }, { silent: true });
            Object.assign(this.state.voice, status || {});
        } catch {
            // No voice, no microphone drawn. Failing closed is the only
            // acceptable direction for a control that posts audio to a
            // third party.
            this.state.voice.available = false;
            this.state.voice.ask = false;
        }
    }

    get voiceOffered() {
        return !!(this.state.voice.available || this.state.voice.ask);
    }

    get voiceCopy() {
        return this.state.voice.copy || {};
    }

    /** The consent card, once. `ask` is the server's answer to "has this
     *  person been asked", so a decline is remembered and cannot come back
     *  and nag. */
    async answerVoiceConsent(granted) {
        this.state.voiceAsking = false;
        try {
            await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_set_voice_consent",
                args: [!!granted], kwargs: {},
            }, { silent: true });
        } catch (error) {
            console.error("PayAI voice consent error:", error);
            return;
        }
        this.state.voice.consent = granted ? "granted" : "declined";
        this.state.voice.ask = false;
        // A decline takes the microphone away entirely rather than leaving a
        // dead control behind.
        this.state.voice.available = !!granted;
    }

    // --- press and hold -------------------------------------------------
    onMicPointerDown(ev) {
        if (ev && ev.button !== undefined && ev.button !== 0) {
            return;
        }
        this._beginTalk();
    }

    onMicPointerUp() {
        this._endTalk();
    }

    /** THE KEYBOARD IS A FIRST-CLASS GESTURE, not an afterthought: a
     *  press-and-hold control that only answers to a mouse is a control some
     *  people cannot use at all. Space/Enter down starts, up stops, and the
     *  repeat guard stops the operating system's key-repeat from restarting
     *  the recorder forty times a second. */
    onMicKeyDown(ev) {
        if (ev.key !== " " && ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        if (this._keyHeld) {
            return;
        }
        this._keyHeld = true;
        this._beginTalk();
    }

    onMicKeyUp(ev) {
        if (ev.key !== " " && ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        this._keyHeld = false;
        this._endTalk();
    }

    _beginTalk() {
        if (this.state.voiceBusy || this.state.isRecording) {
            return;
        }
        if (this.state.voice.ask) {
            // Never record first and ask afterwards.
            this.state.voiceAsking = true;
            return;
        }
        if (!this.state.voice.available) {
            return;
        }
        this._startRecording();
    }

    _endTalk() {
        if (this.state.isRecording) {
            this._stopRecording();
        }
    }

    async _startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this._recordingStream = stream;
            this._audioChunks = [];
            this._mediaRecorder = new MediaRecorder(stream, {
                mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                    ? 'audio/webm;codecs=opus' : 'audio/webm',
            });

            this._mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) this._audioChunks.push(e.data);
            };

            this._mediaRecorder.onstop = () => {
                this._releaseMicrophone();
                if (this._discarded) {
                    // The drawer went away while this was recording. Nothing
                    // is sent, and the buffer is already empty.
                    this._audioChunks = [];
                    return;
                }
                this._transcribe();
            };

            this._mediaRecorder.start();
            this.state.isRecording = true;
            this.state.recordingDuration = 0;
            this.state.voiceError = "";
            this.state.voiceHint = "";

            this._recordingTimer = setInterval(() => {
                this.state.recordingDuration++;
                // A HARD CEILING. A key that sticks, or a pointer released
                // outside the window, must not leave the microphone open and
                // then post ten minutes of an open-plan office.
                if (this.state.recordingDuration >= MAX_RECORDING_SECONDS) {
                    this._endTalk();
                }
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

    _releaseMicrophone() {
        if (this._recordingStream) {
            this._recordingStream.getTracks().forEach((t) => t.stop());
            this._recordingStream = null;
        }
        if (this._recordingTimer) {
            clearInterval(this._recordingTimer);
            this._recordingTimer = null;
        }
        this.state.isRecording = false;
    }

    /** Audio out, TEXT INTO THE ASK BAR. Nothing is added to the transcript
     *  and nothing is sent — the learner reads what was heard, edits it if
     *  the microphone misheard a name, and presses send. */
    async _transcribe() {
        if (this._discarded || this._audioChunks.length === 0) {
            return;
        }
        const audioBlob = new Blob(this._audioChunks, { type: 'audio/webm' });
        this._audioChunks = [];
        this.state.voiceBusy = true;
        try {
            const base64 = await this._toBase64(audioBlob);
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_transcribe_voice",
                args: [base64], kwargs: {},
            }, { silent: true });
            if (!result || result.error) {
                this.state.voiceError = (result && result.error)
                    || this.voiceCopy.failed || "";
                return;
            }
            const heard = (result.text || "").trim();
            if (!heard) {
                this.state.voiceError = this.voiceCopy.failed || "";
                return;
            }
            // Appended, not replaced: somebody who typed half a question and
            // then spoke the rest meant both halves.
            const existing = this.state.inputText.trim();
            this.state.inputText = existing ? existing + " " + heard : heard;
            this.state.voiceHint = this.voiceCopy.check_hint || "";
            setTimeout(() => {
                const el = this.inputRef.el;
                if (el) {
                    el.focus();
                    el.selectionStart = el.selectionEnd = el.value.length;
                }
            }, 0);
        } catch (error) {
            console.error("PayAI voice error:", error);
            this.state.voiceError = this.voiceCopy.failed || "";
        } finally {
            this.state.voiceBusy = false;
        }
    }

    /** CHUNKED. `String.fromCharCode(...bytes)` spreads one argument per byte,
     *  and a thirty-second recording is a million of them — which is a stack
     *  overflow, not a slow path. */
    async _toBase64(blob) {
        const bytes = new Uint8Array(await blob.arrayBuffer());
        let binary = "";
        for (let i = 0; i < bytes.length; i += 0x8000) {
            binary += String.fromCharCode.apply(
                null, bytes.subarray(i, i + 0x8000));
        }
        return btoa(binary);
    }

    // --- speaking the answer --------------------------------------------
    //
    // THE BROWSER'S OWN SYNTHESISER, not the provider's. A reply that has had
    // its placeholders restored is full of real names; posting it to a
    // speech-synthesis endpoint to be read aloud would re-export exactly what
    // the redaction just protected, on the way BACK. `speechSynthesis` runs
    // on the device, so the answer never leaves the browser — which is what
    // makes "the spoken reply is inside the trust boundary" true rather than
    // merely asserted. Documented as a deviation in the Phase 6 report.

    get ttsSupported() {
        return typeof window !== "undefined" && "speechSynthesis" in window;
    }

    _restoreTtsPreference() {
        try {
            this.state.ttsOn = window.localStorage.getItem(TTS_PREF) === "1";
        } catch {
            this.state.ttsOn = false;
        }
    }

    toggleTts() {
        this.state.ttsOn = !this.state.ttsOn;
        try {
            window.localStorage.setItem(TTS_PREF, this.state.ttsOn ? "1" : "0");
        } catch {
            // A locked-down profile must not break the drawer.
        }
        if (!this.state.ttsOn) {
            this._stopSpeaking();
        }
    }

    speak(text) {
        if (!this.ttsSupported || !text) {
            return;
        }
        try {
            this._stopSpeaking();
            const utterance = new window.SpeechSynthesisUtterance(String(text));
            const lang = (window.odoo?.session_info?.user_context?.lang || "en_US");
            utterance.lang = lang.replace("_", "-");
            window.speechSynthesis.speak(utterance);
        } catch (e) {
            console.warn("PayAI speech synthesis failed:", e);
        }
    }

    _stopSpeaking() {
        try {
            if (this.ttsSupported) {
                window.speechSynthesis.cancel();
            }
        } catch {
            // Nothing to cancel.
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

/**
 * LEARN v3 — the same chat, drawn inside the helper drawer as its "Ask" tab.
 *
 * Every behaviour is the parent's: sending, charts, pinning, the lesson
 * button, voice with its consent card, read-aloud. Only the frame differs —
 * no pill, no backdrop, no centred modal. The drawer sits beside the screen,
 * so the numbers being asked about stay visible.
 *
 * `handoff` is a question the guide could not answer, passed on by the
 * drawer. It is sent once per `id`, after the history has loaded.
 */
export class AiInsightChatEmbedded extends AiInsightChat {
    static template = "pb_payroll_ai_insights.AiInsightChatEmbedded";
    static embedded = true;
    static props = ["close?", "handoff?"];

    setup() {
        super.setup();
        this.state.isOpen = true;
        this._handoffId = null;
        onMounted(() => {
            this._takeHandoff(this.props.handoff);
            setTimeout(() => this.inputRef.el?.focus(), 80);
        });
        onWillUpdateProps((next) => this._takeHandoff(next.handoff));
    }

    async _takeHandoff(handoff) {
        if (!handoff || !handoff.text || handoff.id === this._handoffId) {
            return;
        }
        this._handoffId = handoff.id;
        try {
            await this._historyReady;
        } catch {
            // A history that failed to load still leaves an empty chat to
            // ask in.
        }
        await this.sendSuggestion(handoff.text);
    }

    /** "Show me" opens a lesson, which closes the whole drawer. */
    closePanel() {
        if (this.props.close) {
            this.props.close();
        }
    }

    get welcomeTitle() {
        return _t("Ask about your pay data");
    }

    get welcomeLead() {
        return _t("Numbers, people, trends, or how to do something. Charts appear right here.");
    }

    get placeholder() {
        return _t("Ask about your payroll…");
    }

    get ttsLabel() {
        return this.state.ttsOn ? _t("Read aloud: on") : _t("Read aloud: off");
    }
}

registry.category("pb_helper_tabs").add("ask", {
    Component: AiInsightChatEmbedded,
    // The helper draws the tab only for people who hold one of these; for
    // anyone else every question would fail on the conversation's access rule.
    groups: ["pb_payroll_ai_insights.group_payai_user"],
});
