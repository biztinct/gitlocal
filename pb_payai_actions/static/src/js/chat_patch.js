/** @odoo-module **/
/**
 * PAYAI P1 — the chat learns to draw and answer PayAI cards.
 *
 * Patches the existing chat (both the floating pill and the helper drawer's
 * Ask tab inherit these methods) rather than rewriting it:
 *
 *  - on mount, it sends the person's own ⌘K rows to their conversation
 *    (`rpc_register_doors`), so "open the runs board" resolves against the
 *    doors THIS person has, and nothing else;
 *  - a card's door runs through the very code path ⌘K uses
 *    (`pb_hub_palette.run(id)`) or `openHub` with the target the server built;
 *  - a chip answers its card by `task_id` (`rpc_send_message(…, resolve)`);
 *  - the floating pill registers an "open with this text" hook for the
 *    ⌘K "Ask PayAI to…" row.
 *
 * The client never decides a tier or a right: it draws what it is given.
 */
import { Component, markup, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { openHub } from "@pb_hub/js/hub_nav";
import { useService } from "@web/core/utils/hooks";
import { AiInsightChat } from "@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat";
import { runPayroll, stashPrefill } from "@pb_payrun_wizard/js/run_driver";

export const PAYAI_HOOKS = "pb_payai";

// Lucide (ISC) — the shapes the cards use. Stroke icons, currentColor.
const ICONS = {
    check: '<path d="M20 6 9 17l-5-5"/>',
    eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    ban: '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    sparkles: '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    scroll: '<path d="M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
    panel: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
    message: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    play: '<polygon points="6 3 20 12 6 21 6 3"/>',
    undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11"/>',
    send: '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
    pencil: '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
    file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    book: '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    loader: '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    volume: '<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/><path d="M16 9a5 5 0 0 1 0 6"/>',
};

/**
 * P2 — the undo countdown ("9:59 left"). Its own little component so the
 * whole chat is not re-rendered every second; the SERVER decides what is too
 * late, this only shows the time.
 */
export class PayaiCountdown extends Component {
    static template = "pb_payai_actions.Countdown";
    static props = { until: String, onExpire: { type: Function, optional: true } };

    setup() {
        this.state = useState({ now: Date.now() });
        onMounted(() => {
            this._timer = setInterval(() => this._tick(), 1000);
            this._tick();
        });
        onWillUnmount(() => clearInterval(this._timer));
    }

    _tick() {
        this.state.now = Date.now();
        // design-5: at 0:00 the offer ends — stop ticking and tell the card
        // once, so it stops showing a button the server would refuse.
        if (this.seconds <= 0 && !this._expired) {
            this._expired = true;
            clearInterval(this._timer);
            if (this.props.onExpire) { this.props.onExpire(); }
        }
    }

    get seconds() {
        // The server sends "YYYY-MM-DD HH:MM:SSZ"; the space form is not
        // ISO 8601 and some browsers (Safari) parse it as NaN, which would
        // read "0:00 left" for the whole window.
        const end = Date.parse(String(this.props.until || "").replace(" ", "T"));
        return Math.max(0, Math.floor(((Number.isNaN(end) ? 0 : end) - this.state.now) / 1000));
    }

    get left() {
        const s = this.seconds;
        return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    }
}

AiInsightChat.components = { ...AiInsightChat.components, PayaiCountdown };

/**
 * P2-F1 — what kind of door a ⌘K row is, for RANKING only (the server never
 * builds anything but navigation out of a row, PA19). The registry's own
 * sequence blocks say it: missions sit under 1000, hub lenses in the 1000s,
 * the legacy deep links from 2000 up, the Learn rows from 5000.
 */
function doorKind(row) {
    const id = String(row.id || "");
    let seq = null;
    let action = {};
    try {
        const reg = registry.category("pb_hub_palette");
        const raw = reg.content && reg.content[id];
        if (raw) {
            seq = raw[0];
            action = (raw[1] && raw[1].action) || {};
        }
    } catch {
        // ranking falls back to the server's guess from the id
    }
    if (id.startsWith("learn.") || (seq !== null && seq >= 5000)) { return "learn"; }
    if (seq === null) { return ""; }
    if (seq >= 2000) { return "link"; }
    if (seq >= 1000 || action.lens) { return "lens"; }
    return "mission";
}

function svg(name) {
    const body = ICONS[name] || ICONS.info;
    return markup(`<svg class="payai-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`);
}

patch(AiInsightChat.prototype, {
    setup() {
        super.setup(...arguments);
        this._payaiOrm = useService("orm");
        this._payaiVoice = false;
        this._payaiResolve = null;
        this._payaiDoorsReady = Promise.resolve();
        this._payaiOpenHook = null;
        onMounted(() => {
            if (this.hosted) {
                return;
            }
            this._payaiDoorsReady = this._payaiRegisterDoors();
            if (!this.constructor.embedded) {
                // The floating pill answers the ⌘K "Ask PayAI to…" row. When the
                // helper drawer hosts the chat, its own hook (coach_patch.js) is
                // the one registered, because this copy never mounts content.
                this._payaiOpenHook = (text) => this.payaiOpenWith(text);
                registry.category(PAYAI_HOOKS).add("open", this._payaiOpenHook, { force: true });
            }
        });
        onWillUnmount(() => {
            const hooks = registry.category(PAYAI_HOOKS);
            if (this._payaiOpenHook && hooks.contains("open")
                    && hooks.get("open") === this._payaiOpenHook) {
                hooks.remove("open");
            }
        });
    },

    // ---------------------------------------------------------------- doors
    _payaiPalette() {
        return (this.env.services || {}).pb_hub_palette || null;
    },

    async _payaiRegisterDoors() {
        try {
            await this._historyReady;
        } catch {
            // an empty chat still has doors to register
        }
        const palette = this._payaiPalette();
        if (!palette || typeof palette.entries !== "function") {
            return;
        }
        try {
            const rows = await palette.entries();
            const out = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_register_doors",
                args: [this.state.sessionId, rows.filter((r) => !r.anyQuery).map((r) => ({
                    id: r.id, label: String(r.label || ""), sublabel: String(r.sublabel || ""),
                    group: String(r.group || ""), groups: r.groups || [],
                    restricted: !!r.restricted, kind: doorKind(r),
                }))],
                kwargs: {},
            }, { silent: true });
            if (out && out.session_id && !this.state.sessionId) {
                this.state.sessionId = out.session_id;
            }
        } catch (e) {
            // No doors: "open …" answers that it cannot see the screens list.
            console.warn("PayAI: could not register screens", e);
        }
    },

    async sendMessage() {
        try {
            await this._payaiDoorsReady;
        } catch {
            // never block a question on the doors
        }
        const before = this.state.messages.length;
        const out = await super.sendMessage(...arguments);
        const fresh = this.state.messages.slice(before).find((m) => m.card && m.fresh);
        if (fresh) {
            fresh.fresh = false;
            this._payaiSupersede(fresh);
            this._payaiAutoRun(fresh);
            if (fresh.card.speak) { this._payaiSpeak(fresh.card.speak); }
            if (fresh.card.drive) { this._payaiDrive(fresh); }
        }
        return out;
    },

    _extraSendKwargs() {
        const resolve = this._payaiResolve;
        const voice = this._payaiVoice;
        this._payaiResolve = null;
        this._payaiVoice = false;
        const out = resolve ? { resolve } : { ...super._extraSendKwargs(...arguments) };
        if (voice) { out.voice = true; }
        return out;
    },

    /** P2 — the box was filled by voice: the send that follows is spoken. */
    async _transcribe() {
        const before = this.state.inputText;
        const out = await super._transcribe(...arguments);
        if (this.state.inputText && this.state.inputText !== before) {
            this._payaiVoice = true;
        }
        return out;
    },

    _payaiSpeak(text) {
        try {
            if (typeof window !== "undefined" && window.speechSynthesis) {
                window.speechSynthesis.cancel();
            }
        } catch {
            // nothing to stop
        }
        this.speak(String(text || ""));
    },

    /** A newer card for the same request: the older one stops offering buttons.
     *  A newer request (another task's card): an older plan stops offering
     *  Do it / Cancel — the server has already expired it (one open plan per
     *  person). Its "Open in the screen instead" door stays. */
    _payaiSupersede(msg) {
        const id = msg.card && msg.card.task_id;
        if (!id) { return; }
        const newer = !msg.card.transient;
        for (const m of this.state.messages) {
            if (m === msg || !m.card) { continue; }
            const acts = m.card.actions || [];
            if (!acts.length) { continue; }
            if (m.card.task_id === id) {
                // A one-off note answering this plan leaves its Do it alone.
                if (!newer) { continue; }
                m.card.actions = [];
                m.card.superseded = true;
            } else if (newer && m.card.task_id && acts.some((a) => a.id === "do")) {
                m.card.actions = acts.filter((a) => a.id !== "do" && a.id !== "cancel");
                m.card.superseded = true;
            }
        }
    },

    // ------------------------------------------------------------- the card
    payaiSvg(name) { return svg(name); },

    payaiCompact(card) {
        // Green "done" with nothing but a door: one line, like the design.
        return card.kind === "done"
            && !(card.result || []).length && !(card.notes || []).length
            && !(card.groups || []).length && !(card.chips || []).length
            && !(card.slots || []).length;
    },

    payaiTone(card) {
        if (card.kind === "plan") {
            if (card.state === "done") { return "ok"; }
            if (card.state === "failed") { return "bad"; }
            if (card.state === "undone") { return "neutral"; }
            return "warn";
        }
        if (card.kind === "cancelled") { return "neutral"; }
        if (card.kind === "done") { return "ok"; }
        if (card.kind === "clarify") { return "brand"; }
        if (card.kind === "blocked") { return "warn"; }
        if (card.kind === "refused") {
            return card.tier === "never" ? "neutral" : "bad";
        }
        return "brand";
    },

    payaiIcon(card) {
        if (card.kind === "clarify") { return "help"; }
        if (card.kind === "blocked") { return "alert"; }
        if (card.kind === "refused") { return card.tier === "never" ? "ban" : "lock"; }
        if ((card.groups || []).length) { return "sparkles"; }
        if ((card.actions || []).some((a) => a.id === "download")) { return "download"; }
        if ((card.result || []).length) { return "eye"; }
        return "check";
    },

    payaiNoteIcon(tone) {
        return { ok: "check", warn: "alert", bad: "lock", info: "info" }[tone] || "info";
    },

    payaiActIcon(act) {
        if (act.icon && ICONS[act.icon]) { return act.icon; }
        if (act.id === "do") { return "play"; }
        if (act.id === "cancel") { return "x"; }
        if (act.id === "prefill") { return "panel"; }
        if (act.id === "learn") { return "book"; }
        if (act.id === "download" || act.action === "download_run_excel") { return "download"; }
        if (act.id === "ask") { return "message"; }
        return "arrow";
    },

    payaiOrigin(origin) {
        return {
            said: _t("you said"), chose: _t("you chose"),
            assumed: _t("assumed"), default: _t("default"),
        }[origin] || "";
    },

    // -------------------------------------------------------------- actions
    _payaiAutoRun(msg) {
        for (const act of msg.card.actions || []) {
            if (act.auto) {
                this.payaiAct(msg, act, { auto: true });
                return;
            }
        }
    },

    payaiAct(msg, act, { auto = false } = {}) {
        if (!act) { return; }
        if (act.id === "door") {
            this._payaiRunDoor(act);
        } else if (act.id === "download" && typeof act.url === "string"
                   && act.url.startsWith("/web/content/")) {
            this.actionService.doAction({ type: "ir.actions.act_url", url: act.url, target: "self" });
        } else if (act.id === "ask" && act.text) {
            this.payaiAsk(act.text);
        } else if (act.id === "do" && !auto) {
            this.payaiDo(msg);
        } else if (act.id === "cancel" && !auto) {
            this._payaiTaskCall(msg, "rpc_cancel_task");
        } else if (act.id === "prefill" && !auto) {
            // "Open in the screen instead": the run the SERVER planned, filled
            // in on the screen; the person still presses every button there.
            stashPrefill(act.prefill || null);
            this._payaiRunDoor({ ...act, hub: { ...(act.hub || {}),
                context: { ...((act.hub || {}).context || {}), pb_payai_prefill: act.prefill || {} } } });
        } else if (act.id === "learn" && !auto) {
            const scenario = (this.env.services || {})["learn.scenario"];
            if (scenario && typeof scenario.begin === "function") {
                if (!this.constructor.embedded) { this.closePanel(); }
                Promise.resolve(scenario.begin(act.scenario || "payrun", act.mode || "watch"))
                    .catch(() => this._payaiDoorFailed());
            } else {
                this._payaiDoorFailed();
            }
        } else if (act.id === "followup" && msg.card && msg.card.task_id && !auto) {
            this._payaiResolve = {
                task_id: msg.card.task_id, slot: act.slot, value: act.value, action: act.action,
            };
            this.sendSuggestion(act.label);
        }
    },

    // ------------------------------------------------------------ P2 Amber
    async _payaiRpc(method, args) {
        return rpc("/web/dataset/call_kw", {
            model: "payroll.ai.conversation", method, args, kwargs: {},
        }, { silent: true });
    },

    /** Do it → the server re-checks everything, then answers with the card
     *  that replaces this one (running, result, refusal or a fresh plan). */
    async payaiDo(msg) {
        if (!msg.card || msg.card.busy) { return; }
        msg.card.busy = true;
        await this._payaiTaskCall(msg, "rpc_confirm_task", ["tap"]);
    },

    /** design-5: the countdown hit 0:00. Only hides the button — the server
     *  stays the judge of what is too late. */
    payaiUndoExpired(msg) {
        if (!msg.card || !msg.card.undo || !msg.card.undo.can) { return; }
        msg.card.undo = { ...msg.card.undo, can: false, label: "",
            note: _t("The ten minutes are up. It can still be changed on the screen.") };
    },

    payaiUndo(msg) {
        if (!msg.card || msg.card.busy) { return; }
        msg.card.busy = true;
        this._payaiTaskCall(msg, "rpc_task_undo");
    },

    async _payaiTaskCall(msg, method, extra = []) {
        const taskId = msg.card && msg.card.task_id;
        if (!taskId) { return; }
        try {
            const out = await this._payaiRpc(method, [taskId, ...extra]);
            this._payaiApply(msg, out && out.card);
        } catch (e) {
            if (msg.card) { msg.card.busy = false; }
            this.notification.add(
                _t("That did not reach the server. Nothing was done; try again in a moment."),
                { type: "warning" });
        }
    },

    _payaiApply(msg, card) {
        if (!card) {
            if (msg.card) { msg.card.busy = false; }
            return;
        }
        let target = msg;
        if (card.transient || card.task_id !== msg.card.task_id) {
            // A one-off answer, or a fresh plan for a new request: it goes
            // BELOW. A fresh plan retires the old card's buttons.
            if (!card.transient) {
                msg.card = { ...msg.card, actions: [], superseded: true, busy: false };
            } else {
                msg.card.busy = false;
            }
            this.state.messages.push({
                role: "assistant", content: card.title || "", chart: null, insights: [],
                card, timestamp: new Date().toISOString(),
            });
            target = this.state.messages[this.state.messages.length - 1];
            this._scrollToBottom();
        } else {
            msg.card = card;
            target = msg;
        }
        if (card.drive) { this._payaiDrive(target); }
        this._payaiAutoRun(target);
    },

    /**
     * Run payroll, driven from here exactly as the wizard drives it — the
     * shared run driver, the same calls in the same order — with the progress
     * drawn on the card. The browser stays open, as with the wizard.
     */
    async _payaiDrive(msg) {
        const card = msg.card;
        const drive = card && card.drive;
        if (!drive || card._driving) { return; }
        card._driving = true;
        const vals = { ...(drive.vals || {}) };
        delete card.drive;
        const taskId = card.task_id;
        const seen = { done: 0, total: (card.progress && card.progress.total) || 0 };
        let info;
        let runId = 0;
        // Progress calls are not awaited mid-run, but all must settle before
        // the result call so none lands after it (a late one would reopen
        // the finished task on the server).
        const pending = [];
        try {
            const res = await runPayroll(this._payaiOrm, vals, {
                onStep: (label) => {
                    if (msg.card.progress) { msg.card.progress = { ...msg.card.progress, label }; }
                },
                onProgress: (p) => {
                    if (!p) { return; }
                    msg.card.progress = { ...(msg.card.progress || {}), done: p.done, total: p.total };
                    if (p.phase === "compute") {
                        seen.done = p.done;
                        seen.total = p.total;
                        pending.push(this._payaiRpc("rpc_task_progress", [taskId, p.done, p.total]).catch(() => {}));
                    }
                },
            });
            runId = res.run_id || 0;
            info = { stage: res.stage, done: seen.done, total: seen.total,
                     exceptions: (res.exceptions || []).length };
        } catch (e) {
            info = { stage: "error", done: seen.done, total: seen.total,
                     error: String((e && (e.data && e.data.message)) || (e && e.message) || e) };
        }
        await Promise.allSettled(pending);
        try {
            const out = await this._payaiRpc("rpc_task_result", [taskId, runId, info]);
            if (out && out.card) { msg.card = out.card; }
        } catch {
            msg.card = { ...msg.card, state: "failed", notes: [{ tone: "warn",
                text: _t("I lost touch with the server at the end. Open the Runs board to see the run.") }] };
        }
        this._scrollToBottom();
    },

    payaiPct(card) {
        const p = card.progress || {};
        if (!p.total) { return card.state === "done" ? 100 : 4; }
        return Math.max(2, Math.min(100, Math.round((p.done / p.total) * 100)));
    },

    payaiNum(n) { return Number(n || 0).toLocaleString(); },

    payaiCardIcon(card) {
        if (card.kind === "plan") {
            if (card.state === "running") { return "loader"; }
            if (card.state === "undone") { return "undo"; }
            if (card.state === "failed") { return "alert"; }
            return card.icon || "play";
        }
        if (card.kind === "cancelled") { return "x"; }
        return this.payaiIcon(card);
    },

    _payaiRunDoor(act) {
        const palette = this._payaiPalette();
        // The floating pill steps aside so the screen it opened is visible;
        // the drawer sits beside the screen and stays.
        if (!this.constructor.embedded) {
            this.closePanel();
        }
        try {
            if (act.hub && (act.hub.tag || act.hub.xmlid)) {
                Promise.resolve(openHub(this.actionService, {
                    tag: act.hub.tag, xmlid: act.hub.xmlid,
                    lens: act.hub.lens, focus: act.hub.focus,
                    context: act.hub.context || {},
                })).catch(() => this._payaiDoorFailed());
            } else if (palette && typeof palette.run === "function" && act.door_id) {
                palette.run(act.door_id);
            }
        } catch {
            this._payaiDoorFailed();
        }
    },

    _payaiDoorFailed() {
        this.notification.add(_t("That screen could not be opened. Try it from the left menu."),
                              { type: "warning" });
    },

    payaiAsk(text) {
        if (!text || this.state.isLoading) { return; }
        this.sendSuggestion(String(text));
    },

    /** The pencil beside a plan slot: ask the server to ask that slot again.
     *  Only the slot's key travels; the server checks it drew that pencil. */
    payaiEditLabel(slot) { return _t("Change %s", slot.label); },

    payaiEdit(msg, slot) {
        if (!msg.card || !msg.card.task_id || this.state.isLoading) { return; }
        this._payaiResolve = { task_id: msg.card.task_id, slot: slot.key, action: "reask" };
        this.sendSuggestion(this.payaiEditLabel(slot));
    },

    payaiPick(msg, chip) {
        if (!msg.card || this.state.isLoading) { return; }
        if (chip.ask) {
            this.payaiAsk(chip.ask);
            return;
        }
        if (msg.card.picked) { return; }
        msg.card.picked = chip.value;
        this._payaiResolve = {
            task_id: msg.card.task_id,
            slot: msg.card.chip_slot,
            value: chip.value,
            action: msg.card.chip_action || undefined,
        };
        this.sendSuggestion(chip.label);
    },

    /** ⌘K "Ask PayAI to…" — open the pill and send the typed text. */
    payaiOpenWith(text) {
        this.state.isOpen = true;
        const q = (text || "").trim();
        if (q) {
            Promise.resolve(this._historyReady).catch(() => {}).then(() => this.sendSuggestion(q));
        } else {
            setTimeout(() => this.inputRef.el && this.inputRef.el.focus(), 300);
        }
    },
});
