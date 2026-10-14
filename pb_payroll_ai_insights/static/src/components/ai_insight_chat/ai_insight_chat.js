/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount, onWillUpdateProps, toRaw } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
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

/* ONECHAT OC2 — the marks only Vietnamese text carries. Read-aloud picks its
   voice from the text it is about to read, not from the page (§6.5): a
   Vietnamese answer is read by a Vietnamese voice whatever the pill says. */
const VI_MARKS = /[ăâđêôơưàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ]/i;

/* The kinds of turn the one chat records as a content-free marker in the
   person's conversation (`rpc_note_turn`, ONECHAT OC1). Mirrors the server's
   NOTE_KINDS; a history row with one of them is drawn as a marker. */
export const NOTE_KINDS = ["guide", "composed", "explain", "practice", "choose", "miss",
                           "capability", "note", "smalltalk"];

/** A plain options object — never an event. `t-on-click="sendMessage"`
 *  hands the handler the click event, which must not be read as options. */
function isOpts(o) {
    return !!o && typeof o === "object" && Object.getPrototypeOf(o) === Object.prototype;
}

/** A history row the helper wrote (a marker), or null. */
export function markerOf(row) {
    const card = row && row.card;
    const kind = card && card.kind;
    if (row && (row.intent === "helper_note"
            || (kind && NOTE_KINDS.includes(kind) && !card.task_id && !card.actions))) {
        return {
            role: "assistant", kind: "marker", mkind: kind || "note",
            key: (card && card.key) || "", label: row.content || "",
            content: row.content || "", card: null, chart: null, insights: [],
            timestamp: row.timestamp || "",
        };
    }
    return null;
}

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
        // ONECHAT OC2 — WHERE THE WORDS IN THE BOX CAME FROM (§6.3). A send
        // is "spoken" only when the text sent is exactly what was heard into
        // an EMPTY box: any edit, or typing before speaking, makes it typed.
        // Provenance, not a sticky flag — the old flag rode along with
        // whatever was sent next, a chip included (ledger OC7).
        this._heard = null;
        this._boxBeforeRecording = "";
        // Escape / Cancel while recording: the recorder's `onstop` drops the
        // audio instead of sending it for transcription.
        this._recCancelled = false;

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
        // LEARN REFRESH step 5 — refreshed across the app: running, signing,
        // paying out, a part-month payslip, a leaver, and the tour.
        this.suggestions = [
            _t("How do I run payroll?"),
            _t("Who approves my pay run?"),
            _t("How do I send the bank file and payslips?"),
            _t("Why is a first payslip smaller?"),
            _t("How do I settle someone who is leaving?"),
            _t("Show me around Payobook"),
        ].map(String);

        onMounted(() => {
            if (this.hosted) {
                return;
            }
            this._onMountLoad();
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

    /** What a mount fetches. The pill: history, icon, voice status. The
     *  helper drawer's copy overrides it (one status call, history only on
     *  the first open of a page). Kept as a promise so a question handed
     *  over is sent AFTER the history lands, not overwritten by it. */
    _onMountLoad() {
        this._historyReady = this._loadHistory();
        this._loadAiIcon();
        this._loadVoiceStatus();
        this._restoreTtsPreference();
    }

    /** A chrome string. The pill has only its own `_t` copy; the helper
     *  drawer's chat reads the helper's, in the pill's language. */
    t(key, fallback) {
        return String(fallback || "");
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
        if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
            ev.preventDefault();
            this.submitComposer();
        }
    }

    onInputChange(ev) {
        this.state.inputText = ev.target.value;
        // Any edit by hand — even retyping the very same words — makes the
        // next send TYPED (§6.3): a spoken go-ahead must be exactly what was
        // heard, untouched.
        this._heard = null;
    }

    async sendSuggestion(text) {
        this.state.inputText = text;
        this.state.showSuggestions = false;
        await this.sendMessage();
    }

    /** The box's own Send (and Enter). THE ONLY CALLER of `_takeSpoken`:
     *  a chip, a suggestion or a hand-off is never spoken. The helper
     *  drawer's copy overrides this with the router. */
    async submitComposer() {
        const text = this.state.inputText.trim();
        if (!text || this.state.isLoading) {
            return;
        }
        return this.sendMessage({ spoken: this._takeSpoken(text) });
    }

    /** Spoken = the text sent is exactly what was heard into an empty box.
     *  Asked once per send; the answer is used up either way. */
    _takeSpoken(text) {
        const heard = this._heard;
        this._heard = null;
        return heard !== null && String(text || "").trim() === String(heard).trim();
    }

    /** ONECHAT OC2 — ONE ENTRY POINT, with options:
     *    {text?, spoken?, askOnly?, fallbackKey?, pushPerson? = true, extraChips?}
     *  Called with none it is exactly the old send — the box's text, the old
     *  busy guard — so every PayAI card chip and hand-off (`sendSuggestion`)
     *  keeps working unchanged. `text` sends that text without reading or
     *  clearing the box; `pushPerson: false` means the composer already drew
     *  the person's turn; `_fromComposer` means the composer holds the busy
     *  flag itself (route + answer + marker), so it is neither checked nor
     *  cleared here. */
    async sendMessage(opts) {
        const o = isOpts(opts) ? opts : {};
        const own = typeof o.text === "string";
        const text = (own ? o.text : this.state.inputText).trim();
        if (!text) return;
        if (!o._fromComposer && this.state.isLoading) return;
        // The "check what I heard" hint belongs to the text that has now been
        // sent; leaving it over the empty box would read as a warning about
        // the next thing typed.
        this.state.voiceHint = "";
        this.state.voiceError = "";

        if (o.pushPerson !== false) {
            this._pushMessage({
                role: "user",
                content: text,
                spoken: !!o.spoken,
                chart: null,
                insights: [],
                timestamp: new Date().toISOString(),
            });
        }
        if (!own) {
            this.state.inputText = "";
        }
        this.state.showSuggestions = false;
        this.state.isLoading = true;
        this._scrollToBottom(true);

        try {
            const result = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_send_message",
                args: [text, this.state.sessionId, this._currentScreen()],
                // PAYAI P1 — a chip answering a PayAI card rides along here
                // (`pb_payai_actions` fills it; plain questions send nothing).
                // ONECHAT OC2 — and the reader's language (the helper's pill).
                kwargs: { ...this._extraSendKwargs(o), ...this._rpcContext() },
            }, { silent: true });  // suppress Odoo's global spinner — we show typing dots

            this.state.sessionId = result.session_id;

            // ONECHAT OC2 — PayAI could not answer, and the router knew the
            // guide's answer to this: show that instead of an error.
            if (!(result.intent === "error" && o.fallbackKey
                    && await this._fallbackAnswer(o.fallbackKey))) {
                this._pushMessage({
                    role: "assistant",
                    content: result.response || "",
                    chart: result.chart || null,
                    insights: result.insights || [],
                    followUpQuestions: result.follow_up_questions || [],
                    drillDownModel: result.drilldown_model || "",
                    intent: result.intent || "",
                    action: result.action || null,
                    // PAYAI P1 — the command card (open / show / refuse / ask).
                    card: result.card || null,
                    fresh: !!result.card,
                    // ONECHAT OC2 — "Explain how instead", under the card.
                    extra: o.extraChips && o.extraChips.length ? o.extraChips : null,
                    timestamp: new Date().toISOString(),
                });
                if (this.state.ttsOn) {
                    // On the device. See the note above `ttsSupported`.
                    this.speak(this._readable(result));
                }
            }
        } catch (error) {
            console.error("PayAI error:", error);
            if (!(o.fallbackKey && await this._fallbackAnswer(o.fallbackKey))) {
                this._pushMessage({
                    role: "assistant",
                    content: _t("That did not work. An administrator can check the AI service under PayAI settings."),
                    chart: null,
                    insights: [],
                    timestamp: new Date().toISOString(),
                });
            }
        }

        if (!o._fromComposer) {
            this.state.isLoading = false;
        }
        this._scrollToBottom();
    }

    /** One message into the stream. The helper drawer's copy stamps it. */
    _pushMessage(msg) {
        this.state.messages.push(msg);
        return msg;
    }

    /** The guide's answer in place of a PayAI error. The pill has no guide. */
    async _fallbackAnswer() {
        return false;
    }

    /** What read-aloud says for a reply. Pay figures are NOT read aloud
     *  (owner decision Q2): a data answer says only that they are on screen. */
    _readable(result) {
        const r = result || {};
        if (r.intent === "payroll_data" || r.chart || (r.insights || []).length) {
            return this.t("figuresOnScreen", _t("Here are the figures you asked for — they are on screen."));
        }
        return String(r.response || "").replace(/[*_#`>|]+/g, "");
    }

    /** Extra keyword arguments for `rpc_send_message`. None by default;
     *  `pb_payai_actions` patches this to send a chip's answer, the spoken
     *  flag and `ask_only` (a base database never sees either kwarg). */
    _extraSendKwargs() {
        return {};
    }

    /** The reader's language for the server (`env.lang`). The pill sends
     *  none, as before; the helper drawer's copy sends its pill's. */
    _rpcContext() {
        return {};
    }

    /** True when the next send answers a PayAI card and must not be routed
     *  (pb_payai_actions: a pending `_payaiResolve`). */
    _bypassRouter() {
        return false;
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
        if (!action) {
            return;
        }
        // LEARN REFRESH step 2: a walkthrough of the real screens, in Watch
        // mode — the second shape the server's whitelist emits.
        if (action.type === "open_walkthrough" && action.walkthrough) {
            this.closePanel();
            Promise.resolve(
                openHub(this.actionService, {
                    xmlid: "pb_learn.action_learn_hub",
                    lens: "lessons",
                    focus: `scenario:${action.walkthrough}:watch`,
                })
            ).catch(() => {
                this.notification.add(_t("The guided lessons are not installed on this database."),
                                      { type: "warning" });
            });
            return;
        }
        if (action.type !== "open_lesson" || !action.lesson) {
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
                _t("The guided lessons are not installed on this database."),
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
                args: [], kwargs: this._rpcContext(),
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
                if (this._recCancelled) {
                    // Escape or Cancel: this recording is dropped, not sent.
                    this._recCancelled = false;
                    this._audioChunks = [];
                    return;
                }
                if (this._discarded) {
                    // The drawer went away while this was recording. Nothing
                    // is sent, and the buffer is already empty.
                    this._audioChunks = [];
                    return;
                }
                this._transcribe();
            };

            // What was in the box when the person started speaking decides
            // whether the words that come back are "spoken" (§6.3).
            this._boxBeforeRecording = this.state.inputText;
            this._recCancelled = false;
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

    /** Escape while recording, or Cancel: stop, and send nothing. */
    cancelRecording() {
        if (!this.state.isRecording) {
            return;
        }
        this._recCancelled = true;
        this._audioChunks = [];
        this._stopRecording();
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
                args: [base64], kwargs: this._rpcContext(),
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
            // then spoke the rest meant both halves — and that mixed text is
            // TYPED. Only words heard into an empty box are spoken (§6.3).
            const before = String(this._boxBeforeRecording || "").trim();
            const existing = this.state.inputText.trim();
            this.state.inputText = existing ? existing + " " + heard : heard;
            this._heard = before || existing ? null : heard;
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
            // From the TEXT, not the page: the old read of the page's session
            // info found nothing on this version, so every answer was read
            // in English (ledger OC5).
            utterance.lang = VI_MARKS.test(String(text)) ? "vi-VN" : "en-US";
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
                // ONECHAT OC2 — a row the helper wrote (a marker) is drawn as
                // a marker, and its card is dropped so the PayAI card
                // template never sees it (ledger OC29).
                this.state.messages = (result.messages || []).map((m) => markerOf(m) || m);
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

/* ONECHAT OC2 — the one chat's memory for the page's life. Closing the
   drawer unmounts the chat (that is what discards a recording in progress),
   so the turns are kept HERE and given back on the next open — guide answers
   in full, not as markers. Only a fresh page load reads the history, and
   only then do guide answers come back as markers ("From the guide: …"). */
const PAGE = { sessionId: null, turns: null, status: null };
let TURN_SEQ = 0;
const PRACTICE_BEAT_MS = 600;

/** For tests: forget the page's memory, as a reload would. */
export function _resetPageMemory() {
    PAGE.sessionId = null;
    PAGE.turns = null;
    PAGE.status = null;
}

function rawOf(x) {
    try {
        return (typeof toRaw === "function" && toRaw(x)) || x;
    } catch {
        return x;
    }
}

/**
 * ONECHAT OC2 — THE ONE CHAT, drawn inside the helper drawer.
 *
 * One stream, one composer. Every sentence the person types (or speaks, then
 * sends) goes to the server's router first (`learn.helper.route`), which says
 * where it belongs; this component draws the answer that comes back in the
 * same card frame, whoever wrote it:
 *
 *   payai     → PayAI's own send, unchanged (`sendMessage`, the same RPC,
 *               the same kwargs, plus `ask_only` for a question);
 *   guide / explain / practice / choose / note / miss → a helper turn, drawn
 *               by the drawer's `helper.turnHTML`, and ONE content-free
 *               marker in the person's conversation (`rpc_note_turn`), so
 *               the thread survives a reload and a later spoken "go ahead"
 *               knows the plan is no longer the last thing shown (OC-R3).
 *
 * NEVER THE ROUTER: anything answering a PayAI card (a chip, a pencil, a
 * typed word, a hand-off with a resolve). Those go straight to
 * `sendMessage` / `sendSuggestion`, as they always have (OC-R4).
 *
 * Props: `helper` (from the drawer: guide, context card, practice doors —
 * one object, never re-created), `lang` (the pill: what re-renders past
 * turns in the other language), `screen` / `place` (where the person is),
 * `close`. `handoff` is the retired Ask-tab hand-off, still accepted.
 */
export class AiInsightChatEmbedded extends AiInsightChat {
    static template = "pb_payroll_ai_insights.AiInsightChatEmbedded";
    static embedded = true;
    static props = ["helper?", "lang?", "screen?", "place?", "close?", "handoff?"];

    setup() {
        super.setup();
        this.state.isOpen = true;
        this.state.status = { can_act: false, can_answer: false, voice_go_ahead: false };
        this.state.awayFromBottom = false;
        this._handoffId = null;
        this._ready = Promise.resolve();
        this.api = this._makeApi();
        onMounted(() => {
            // The drawer's queue (the moment card's Explain, ⌘K) waits for
            // the history: a turn pushed before it lands would be overwritten.
            Promise.resolve(this._historyReady).catch(() => {}).then(() => {
                if (this.props.helper && !this._discarded) {
                    this.props.helper.attach(this.api);
                }
                this._noteScreen(this.props.screen);
            });
            this._takeHandoff(this.props.handoff);
            setTimeout(() => this.inputRef.el?.focus(), 80);
        });
        onWillUpdateProps((next) => {
            this._takeHandoff(next.handoff);
            if ((next.screen || "") !== (this.props.screen || "")) {
                this._noteScreen(next.screen);
            }
        });
        onWillUnmount(() => {
            if (this.props.helper) {
                this.props.helper.detach(this.api);
            }
            PAGE.turns = rawOf(this.state.messages);
            PAGE.sessionId = this.state.sessionId;
        });
    }

    // ------------------------------------------------------------- mount
    /** One status call; the history only on the first open of a page. */
    _onMountLoad() {
        this._restoreTtsPreference();
        const restored = PAGE.turns && PAGE.turns.length ? PAGE.turns : null;
        if (restored) {
            // Given back, not new: nothing fades in again on a re-open.
            for (const m of restored) {
                m.isNew = false;
            }
            this.state.sessionId = PAGE.sessionId;
            this.state.messages = restored;
            this.state.showSuggestions = false;
        }
        if (PAGE.status) {
            this._applyStatus(PAGE.status);
        }
        const status = this._loadHelperStatus();
        this._historyReady = restored ? status : Promise.all([status, this._loadHistory()]);
        this._ready = this._historyReady;
    }

    /** The history, with every row given an id: a marker's "Show again"
     *  and a card's chips find their turn by it. */
    async _loadHistory() {
        await super._loadHistory();
        for (const m of this.state.messages) {
            if (!m.id) {
                m.id = this._turnId();
            }
        }
    }

    async _loadHelperStatus() {
        try {
            const status = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_helper_status",
                args: [this.state.sessionId || PAGE.sessionId || null],
                kwargs: this._rpcContext(),
            }, { silent: true });
            PAGE.status = status || {};
            this._applyStatus(PAGE.status);
        } catch {
            // No status: no microphone, the guide still answers, PayAI is
            // tried as before. Failing closed for the microphone is the only
            // acceptable direction for a control that posts audio.
            this.state.voice.available = false;
            this.state.voice.ask = false;
        }
    }

    _applyStatus(status) {
        const st = status || {};
        if (st.session_id && !this.state.sessionId) {
            this.state.sessionId = st.session_id;
        }
        Object.assign(this.state.voice, st.voice || {});
        this.state.status = {
            can_act: !!st.can_act,
            can_answer: !!st.can_answer,
            voice_go_ahead: !!st.voice_go_ahead,
        };
        if (st.icon_url) {
            this.state.aiIconUrl = st.icon_url;
        }
    }

    // ------------------------------------------------------------- words
    t(key, fallback) {
        const h = this.props.helper;
        const v = h ? h.T(key, this.props.lang) : "";
        return v && v !== key ? v : String(fallback || key);
    }

    pick(pair) {
        const h = this.props.helper;
        if (!pair) {
            return "";
        }
        if (typeof pair === "string") {
            return pair;
        }
        return h ? h.text(pair, this.props.lang) : (pair[this.props.lang] || pair.en || "");
    }

    _rpcContext() {
        const lang = this.props.lang === "vi" ? "vi_VN" : (this.props.lang === "en" ? "en_US" : null);
        if (!lang) {
            return {};
        }
        return { context: { ...((user && user.context) || {}), lang } };
    }

    get placeholder() {
        if (!this.props.helper) {
            return _t("Ask about your payroll…");
        }
        return this.state.status.can_act ? this.t("askAny") : this.t("askAnyNoAct");
    }

    get bannerText() {
        return this.state.status.can_act ? this.t("honestAct") : this.t("honestAsk");
    }

    get ttsLabel() {
        return this.t("readAloud", _t("Read answers aloud"));
    }

    // ---------------------------------------------------------- the stream
    _turnId() {
        TURN_SEQ += 1;
        return `c${TURN_SEQ}`;
    }

    _pushMessage(msg) {
        msg.id = msg.id || this._turnId();
        msg.screen = msg.screen === undefined ? (this.props.screen || null) : msg.screen;
        msg.isNew = true;
        this.state.messages.push(msg);
        this._scrollToBottom();
        return this.state.messages[this.state.messages.length - 1];
    }

    /** A turn the helper writes (guide, note, practice, choose, consent,
     *  context, marker). Role "assistant", no card — the PayAI card
     *  template never sees it. */
    _pushHelper(turn) {
        return this._pushMessage(Object.assign({
            role: "assistant", content: "", card: null, chart: null, insights: [],
        }, turn));
    }

    findTurn(id) {
        return this.state.messages.find((m) => m.id === id) || null;
    }

    /** Draw a helper turn through the drawer's renderer (one visual
     *  language with the guide-only stream). Reads `lang` so a flip
     *  re-renders every past turn from the payload it holds. */
    helperTurn(msg) {
        return this.props.helper.turnHTML(msg, this.props.lang, { canAct: this.state.status.can_act });
    }

    contextCard() {
        void this.props.screen;
        void this.props.place;
        return this.props.helper.contextHTML(this.props.lang, { canAct: this.state.status.can_act });
    }

    extraChips(msg) {
        return this.props.helper.chipsHTML(msg.extra, this.props.lang);
    }

    /** "From your pay data" over a PayAI figures answer. */
    sourceLabel(msg) {
        if (msg.role !== "assistant" || msg.card || msg.kind) {
            return "";
        }
        return msg.intent === "payroll_data" || msg.chart ? this.t("fromPayData", _t("From your pay data")) : "";
    }

    /** "Practise this" under a PayAI answer that opens a walkthrough which
     *  can be practised. */
    practiseFor(msg) {
        const a = msg && msg.action;
        if (!this.props.helper || !a || a.type !== "open_walkthrough" || !a.walkthrough) {
            return null;
        }
        return this.props.helper.practiseChip({ try: a.walkthrough });
    }

    /** The screen moved while the conversation has turns: say where we are
     *  now, as the newest item (it collapses once something is sent). */
    _noteScreen(screen) {
        const msgs = this.state.messages;
        if (!msgs.length || !this.props.helper) {
            return;
        }
        const last = msgs[msgs.length - 1];
        if (last.kind === "context" && last.live) {
            last.screen = screen || null;
            last.label = this.props.helper.screenLabelPair();
            return;
        }
        const lastScreen = [...msgs].reverse().find((m) => m.screen !== undefined);
        if (lastScreen && (lastScreen.screen || "") === (screen || "")) {
            return;
        }
        this._pushHelper({ kind: "context", live: true, screen: screen || null,
                           label: this.props.helper.screenLabelPair() });
    }

    /** Sending collapses a live context card to a one-line divider; on an
     *  empty stream the first send leaves a divider naming the screen. */
    _collapseContext() {
        const h = this.props.helper;
        if (!h) {
            return;
        }
        let live = false;
        for (const m of this.state.messages) {
            if (m.kind === "context" && m.live) {
                m.live = false;
                m.label = h.screenLabelPair();
                live = true;
            }
        }
        if (!live && !this.state.messages.length) {
            this._pushHelper({ kind: "context", live: false, label: h.screenLabelPair() });
        }
    }

    // ------------------------------------------------------------ markers
    /** ONE content-free marker for a non-PayAI turn (OC-R3): a kind and a
     *  key, never the question and never any text from this browser. */
    async _marker(kind, key, sourceKind) {
        try {
            const out = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_note_turn",
                args: [this.state.sessionId || null, kind, key || null, sourceKind || null,
                       this.props.screen || null],
                kwargs: this._rpcContext(),
            }, { silent: true });
            if (out && out.session_id) {
                this.state.sessionId = out.session_id;
            }
        } catch (e) {
            // A marker that failed loses only the reload copy of this turn.
            console.warn("PayAI: could not record the helper's turn", e);
        }
    }

    /** Which marker a guide answer gets. */
    async _markGuide(answer) {
        if (!answer) {
            return;
        }
        if (!answer.matched) {
            return this._marker("miss", "noAnswer");
        }
        if (answer.source_kind === "composed") {
            return this._marker("composed", null, "composed");
        }
        if (answer.source_kind === "capability" || answer.key === "capability") {
            return this._marker("capability");
        }
        if (answer.source_kind === "screen") {
            return this._marker("explain", answer.key, "screen");
        }
        return this._marker("guide", answer.key, answer.source_kind || null);
    }

    // ------------------------------------------------------------ sending
    /** The box's Send / Enter: the router decides where it goes. */
    async submitComposer() {
        const text = this.state.inputText.trim();
        if (!text || this.state.isLoading) {
            return;
        }
        if (this._bypassRouter() || !this.props.helper) {
            return this.sendMessage({ spoken: this._takeSpoken(text) });
        }
        const spoken = this._takeSpoken(text);
        this.state.inputText = "";
        this._resizeBox();
        await this._routeAndDispatch(text, { spoken });
    }

    /** A sentence from a chip, a suggestion or ⌘K: routed exactly as if
     *  typed, never spoken — unless it answers a PayAI card. */
    async sendText(text, opts = {}) {
        const t = String(text || "").trim();
        if (!t) {
            return;
        }
        if (this._bypassRouter() || !this.props.helper) {
            return this.sendSuggestion(t);
        }
        if (this.state.isLoading) {
            return;
        }
        await this._routeAndDispatch(t, { spoken: false, origin: opts.origin || "chip" });
    }

    async _route(text) {
        const orm = this.env.services && this.env.services.orm;
        const kwargs = {
            screen_key: this.props.screen || null,
            lang: this.props.lang || "en",
            session_id: this.state.sessionId || null,
        };
        if (orm) {
            return orm.call("learn.helper", "route", [text], kwargs);
        }
        return rpc("/web/dataset/call_kw", {
            model: "learn.helper", method: "route", args: [text],
            kwargs: { ...kwargs, ...this._rpcContext() },
        }, { silent: true });
    }

    async _routeAndDispatch(text, { spoken }) {
        this._collapseContext();
        this._pushMessage({ role: "user", content: text, spoken: !!spoken,
                            chart: null, insights: [], timestamp: new Date().toISOString() });
        this.state.isLoading = true;
        this.state.voiceHint = "";
        this.state.voiceError = "";
        this._scrollToBottom(true);
        try {
            let r = null;
            try {
                r = await this._route(text);
            } catch (e) {
                console.warn("PayAI: the router did not answer", e);
            }
            await this._dispatch(text, r, { spoken });
        } finally {
            this.state.isLoading = false;
            this._scrollToBottom();
        }
    }

    /** THE DISPATCH TABLE — the only place a route value is read. */
    async _dispatch(text, r, { spoken }) {
        const h = this.props.helper;
        if (!r || !r.route) {
            this._pushHelper({ kind: "note", note: h.pair("routeFailed") });
            return;
        }
        switch (r.route) {
            case "payai":
                await this.sendMessage({
                    text, spoken, askOnly: !!r.ask_only, fallbackKey: r.fallback_key || null,
                    extraChips: r.extra_chips || null, pushPerson: false, _fromComposer: true,
                });
                return;
            case "guide":
                this._pushHelper({ kind: "guide", answer: r.answer, lead: r.lead || null,
                                   extra: r.extra_chips || null });
                await h.onGuideAnswer(text, r.answer);
                await this._markGuide(r.answer);
                return;
            case "explain":
                await this._pushGuide(await h.explain(), { kind: "explain" });
                return;
            case "practice":
                await this._practiceRoute(r);
                return;
            case "choose":
                this._pushHelper({ kind: "choose", note: r.note || h.pair("whichMeant"),
                                   choices: r.choices || [] });
                await this._marker("choose", (r.note && r.note.key) || "whichMeant");
                return;
            case "miss":
                if (r.note) {
                    this._pushHelper({ kind: "note", note: r.note, suggest: r.suggest || [] });
                } else {
                    this._pushHelper({ kind: "guide", answer: r.answer || { matched: false, suggest: r.suggest || [] } });
                }
                await h.onGuideAnswer(text, r.answer || { matched: false });
                await this._marker("miss", (r.note && r.note.key) || "noAnswer");
                return;
            case "note":
            default: {
                this._pushHelper({ kind: "note", note: r.note || h.pair("smalltalk"), suggest: r.suggest || [] });
                // A note ABOUT the plan card ("Tap Do it…") must not make the
                // plan "not the last thing I showed you" (OC-R3).
                if (r.why !== "tap_card") {
                    await this._marker(r.why === "smalltalk" ? "smalltalk" : "note",
                                       (r.note && r.note.key) || "smalltalk");
                }
            }
        }
    }

    async _practiceRoute(r) {
        const p = r.practice || {};
        if (r.answer) {
            this._pushHelper({ kind: "guide", answer: r.answer });
        }
        this._pushHelper({ kind: "practice", practice: p, note: r.note || null });
        await this._marker("practice", p.key || null);
        // Try starts after a beat; a walkthrough with nothing to practise
        // waits for its own Watch button (the note says why).
        if (p.key && (p.mode === "try" || !r.note)) {
            this._startLater(p.key, p.mode || "try");
        }
    }

    _startLater(key, mode) {
        setTimeout(() => {
            if (this.props.helper) {
                this.props.helper.startPractice(key, mode);
            }
        }, PRACTICE_BEAT_MS);
    }

    /** "Practise this", from a guide answer, a PayAI answer or a chip. */
    async practise(key, mode) {
        const h = this.props.helper;
        if (!h) {
            return;
        }
        this._pushHelper({ kind: "practice", practice: { key, mode: mode || "try",
                                                          name: h.scenarioName(key) || "" } });
        await this._marker("practice", key);
        this._startLater(key, mode || "try");
    }

    async _pushGuide(answer, opts = {}) {
        const h = this.props.helper;
        if (!answer) {
            this._pushHelper({ kind: "note", note: h.pair("coachNoScreen") });
            await this._marker("note", "coachNoScreen");
            return;
        }
        this._pushHelper({ kind: "guide", answer });
        await this._markGuide(answer);
    }

    async _fallbackAnswer(key) {
        const h = this.props.helper;
        if (!h || !key) {
            return false;
        }
        const answer = await h.answerFor(key);
        if (!answer || !answer.matched) {
            return false;
        }
        this._pushHelper({ kind: "guide", answer });
        await this._markGuide(answer);
        return true;
    }

    // --------------------------------------------------------------- api
    /** What the drawer may ask of this chat (`helper.attach`). */
    _makeApi() {
        const ready = (fn) => Promise.resolve(this._ready).catch(() => {}).then(fn);
        return {
            pushGuide: (answer, opts) => ready(() => this._pushGuide(answer, opts)),
            pushNote: (note) => ready(() => this._pushHelper({ kind: "note", note })),
            pushTurn: (turn) => this._pushHelper(Object.assign({}, turn)),
            sendText: (text, opts) => ready(() => this.sendText(text, opts)),
            sendDirect: ({ text, askOnly }) => ready(() => (this.state.isLoading ? null
                : this.sendMessage({ text, askOnly: !!askOnly }))),
            practise: (key, mode) => this.practise(key, mode),
            findTurn: (id) => this.findTurn(id),
            dropTurns: (kind) => {
                this.state.messages = this.state.messages.filter((m) => m.kind !== kind);
            },
            isEmpty: () => !this.state.messages.length,
            focus: () => this.inputRef.el && this.inputRef.el.focus(),
            setDraft: (text) => {
                this.state.inputText = String(text || "");
            },
            clear: () => this.clearHistory(),
            toggleReadAloud: () => this.toggleTts(),
            readAloudOn: () => !!this.state.ttsOn,
            ttsSupported: () => this.ttsSupported,
            voiceDeclined: () => !!(this.state.voice.consent === "declined"
                && this.state.voice.switch_on && this.state.voice.provider_ready),
            reopenVoiceConsent: () => {
                this.state.voiceAsking = true;
            },
            cancelRecording: () => this.cancelRecording(),
            isRecording: () => !!this.state.isRecording,
        };
    }

    async clearHistory() {
        if (!this.state.sessionId) {
            this.state.messages = [];
            PAGE.turns = null;
            return;
        }
        await super.clearHistory();
        PAGE.turns = null;
        PAGE.sessionId = null;
    }

    // ------------------------------------------------------------- input
    onInputChange(ev) {
        super.onInputChange(ev);
        this._resizeBox(ev.target);
    }

    /** One to five lines, then it scrolls. */
    _resizeBox(el) {
        const box = el || this.inputRef.el;
        if (!box || !box.style) {
            return;
        }
        box.style.height = "auto";
        box.style.height = `${Math.min(box.scrollHeight || 0, 120)}px`;
    }

    // ------------------------------------------------------------ scroll
    /** Sticks to the bottom while the person is there; when they have
     *  scrolled up to read, a "Jump to latest" pill appears instead. */
    _scrollToBottom(force) {
        setTimeout(() => {
            const el = this.chatBodyRef.el;
            if (!el) {
                return;
            }
            if (force || !this.state.awayFromBottom) {
                el.scrollTop = el.scrollHeight;
                this.state.awayFromBottom = false;
            }
        }, 60);
    }

    onBodyScroll(ev) {
        const el = ev.target;
        this.state.awayFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight > 80;
    }

    jumpToLatest() {
        this.state.awayFromBottom = false;
        this._scrollToBottom(true);
    }

    // ----------------------------------------------------------- hand-off
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
}

const ONE_CHAT = {
    Component: AiInsightChatEmbedded,
    // The drawer draws the chat only for people who hold one of these; for
    // anyone else every question would fail on the conversation's access
    // rule, and the drawer draws its guide-only stream instead.
    groups: ["pb_payroll_ai_insights.group_payai_user"],
};
registry.category("pb_helper_chat").add("main", ONE_CHAT);
// The old seam's name, for one release: a drawer bundle that still reads
// `pb_helper_tabs/ask` finds the same chat. Remove with the drawer's shim.
registry.category("pb_helper_tabs").add("ask", ONE_CHAT);
