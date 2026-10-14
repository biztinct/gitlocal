/** @odoo-module **/
/**
 * PAYAI P1 — the chat learns to draw and answer PayAI cards.
 *
 * Patches the existing chat (both the floating pill and the helper drawer's
 * one chat inherit these methods) rather than rewriting it:
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
import { Component, markup, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { rpc, RPCError } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { openHub } from "@pb_hub/js/hub_nav";
import { useService } from "@web/core/utils/hooks";
import { AiInsightChat, moneyOfCard } from "@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat";
import { runPayroll, stashPrefill } from "@pb_payrun_wizard/js/run_driver";

export const PAYAI_HOOKS = "pb_payai";

/* ONECHAT OC2 — the ⌘K doors are registered once per page load and per
   conversation, not on every open of the drawer: a re-open costs one status
   call, no doors call (handover §5.1). The key is the rows themselves, so a
   person whose doors changed (a role lent) registers again. */
const DOORS = { key: "" };

/**
 * P3:crit-7 — what to say when a task call did not come back with a card.
 *
 *  - The server ANSWERED with an error (an RPCError: an access refusal, a
 *    check that raised, an engine fault). The request's transaction was rolled
 *    back and the engine never commits on its own, so nothing was done: say
 *    so, with the server's own reason when it is one written for people
 *    (an `odoo.exceptions.*` message), never a raw technical one.
 *  - No answer at all (connection lost, request aborted, or the card could
 *    not be drawn after the reply). For a typed approve / send back / turn
 *    down the decision may already be recorded and cannot be taken back, so
 *    say only what is known; pressing again is safe because the server
 *    answers a finished task with what already happened.
 *  - Anything else keeps the plain "Nothing was done" wording.
 */
export function payaiCallFailedText(error, method, card) {
    const answered = Boolean(error) && (error instanceof RPCError
        || error.name === "RPC_ERROR" || error.type === "server");
    if (answered) {
        const data = error.data || {};
        const reason = String(data.name || error.exceptionName || "").startsWith("odoo.exceptions.")
            ? String(data.message || error.message || "").trim() : "";
        return reason
            ? _t("Nothing was done. %s", reason)
            : _t("That did not go through on the server. Nothing was done; try again in a moment.");
    }
    if (method === "rpc_confirm_task" && card && card.tier === "decide") {
        return _t("I could not hear back from the server, so I cannot tell yet whether it went through. Press the button again to see what happened. It will not be done twice.");
    }
    return _t("That did not reach the server. Nothing was done; try again in a moment.");
}

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
    keyboard: '<path d="M10 8h.01"/><path d="M12 12h.01"/><path d="M14 8h.01"/><path d="M16 12h.01"/><path d="M18 8h.01"/><path d="M6 8h.01"/><path d="M7 16h10"/><path d="M8 12h.01"/><rect width="20" height="16" x="2" y="4" rx="2"/>',
    usercheck: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/>',
    cornerleft: '<polyline points="9 14 4 9 9 4"/><path d="M20 20v-7a4 4 0 0 0-4-4H4"/>',
    circlex: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    bell: '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/>',
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

/**
 * P3 — the typed-word confirm, the Red card's hero. The word is shown in the
 * hint, the box takes focus the moment the card arrives, the button lights the
 * instant the word matches (trimmed, any case) and Enter submits. The SERVER
 * checks the word again: this only spares a round trip. A wrong word comes
 * back as an inline hint under the box, never a toast.
 */
// Python's whitespace (`str.isspace`, what the server's `split()` cuts on) —
// NOT JS `\s`, which also counts U+FEFF and misses U+001C–001F and U+0085.
const PY_SPACE = /[\t\n\v\f\r\x1c-\x1f \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/u;

export function normWord(word) {
    // P4: marks fold away too ("duyet" = "DUYỆT"). FIX-1 (P4:vi-13): the
    // SERVER's rule, step for step (`runner._norm_word` → `resolve.fold`):
    // NFKD (full-width "ＤＵＹỆＴ" is "duyet"), every mark dropped, lower-case
    // (a dotless "ı" stays itself, as it does there), đ → d, then Python's
    // whitespace split. The server drops combining-class marks only; `\p{M}`
    // drops those and a few spacing marks no confirm word contains, so the
    // button can never stay dark for a word the server would take. The
    // shared table `tests/js/word_fold_cases.json` pins both sides.
    return String(word || "").normalize("NFKD").replace(/\p{M}/gu, "")
        .toLowerCase().replace(/đ/g, "d")
        .split(PY_SPACE).filter(Boolean).join(" ");
}

/** P4 — the typed word matches any word the card accepts (the person's own
 *  language is the one shown; English and Vietnamese both count). */
export function wordMatches(typed, act) {
    const said = normWord(typed);
    if (!said) { return false; }
    const words = (act && act.words && act.words.length) ? act.words : [act && act.word];
    return words.some((w) => normWord(w) === said);
}

export class PayaiTypedConfirm extends Component {
    static template = "pb_payai_actions.TypedConfirm";
    static props = { act: Object, card: Object, onSubmit: Function };

    setup() {
        const note = this.props.act.note;
        this.state = useState({ word: "", note: (note && note.value) || "" });
        this.wordRef = useRef("word");
        this.uid = `payai-typed-${this.props.card.task_id || 0}`;
        onMounted(() => {
            // Only a live plan takes focus: a card redrawn from history (its
            // ten minutes gone) never steals the cursor from the box.
            const until = Date.parse(String(this.props.card.expires_iso || "").replace(" ", "T"));
            const live = Number.isNaN(until) || until > Date.now();
            if (live && this.wordRef.el && !this.props.card.superseded) {
                this.wordRef.el.focus({ preventScroll: true });
            }
        });
    }

    get ok() { return wordMatches(this.state.word, this.props.act); }
    get typedSome() { return this.state.word.trim().length > 0; }
    icon(name) { return svg(name); }

    onInput(ev) {
        this.state.word = ev.target.value;
        if (this.props.card.typed_error) { this.props.card.typed_error = ""; }
    }

    onKey(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.submit();
        }
    }

    submit() {
        if (!this.ok || this.props.card.busy) {
            if (!this.ok && this.typedSome) {
                this.props.card.typed_error = _t("That is not the word yet. Type %s.", this.props.act.word);
            }
            return;
        }
        this.props.onSubmit(this.state.word, this.state.note);
    }
}

AiInsightChat.components = { ...AiInsightChat.components, PayaiCountdown, PayaiTypedConfirm };

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

/**
 * FIX-1b — where a ⌘K row leads, by identifier only (its action's tag, xmlid,
 * lens, focus). The server's one deny-list (`gate.door_denied`) matches on it
 * as well as on the row id, so a door into Settings › Access and delegations
 * is never stored, however a module names its row. Never a destination: a
 * door still opens only through `pb_hub_palette.run(id)` (PA19).
 */
function doorTarget(row) {
    let action = (row && row.action) || null;
    if (!action) {
        try {
            const reg = registry.category("pb_hub_palette");
            const raw = reg.content && reg.content[String(row.id || "")];
            action = (raw && raw[1] && raw[1].action) || null;
        } catch {
            action = null;
        }
    }
    if (!action || typeof action !== "object") { return {}; }
    const out = {};
    for (const key of ["tag", "xmlid", "lens", "focus"]) {
        if (typeof action[key] === "string" && action[key]) { out[key] = action[key]; }
    }
    return out;
}

function svg(name) {
    const body = ICONS[name] || ICONS.info;
    return markup(`<svg class="payai-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`);
}

patch(AiInsightChat.prototype, {
    setup() {
        super.setup(...arguments);
        this._payaiOrm = useService("orm");
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
            const doors = rows.filter((r) => !r.anyQuery).map((r) => ({
                id: r.id, label: String(r.label || ""), sublabel: String(r.sublabel || ""),
                group: String(r.group || ""), groups: r.groups || [],
                restricted: !!r.restricted, kind: doorKind(r), target: doorTarget(r),
            }));
            const key = `${this.state.sessionId || ""}|${JSON.stringify(doors)}`;
            if (this.constructor.embedded && this.state.sessionId && DOORS.key === key) {
                return;
            }
            const out = await rpc("/web/dataset/call_kw", {
                model: "payroll.ai.conversation",
                method: "rpc_register_doors",
                args: [this.state.sessionId, doors],
                kwargs: {},
            }, { silent: true });
            if (this.constructor.embedded) {
                DOORS.key = `${(out && out.session_id) || this.state.sessionId || ""}|${JSON.stringify(doors)}`;
            }
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
            if (fresh.card.speak) { this._payaiSpeak(fresh.card.speak, fresh.id, fresh.card); }
            if (fresh.card.drive) { this._payaiDrive(fresh); }
        }
        return out;
    },

    /** ONECHAT OC2 — what rides along with a send. A card chip's answer
     *  (`resolve`) wins and travels alone. Otherwise `voice: true` only when
     *  THIS send is spoken (the words heard into an empty box, sent as heard
     *  — the chat's `_takeSpoken`; never a chip, never a hand-off: ledger
     *  OC7), and `ask_only: true` when the router said the sentence is a
     *  question, so PayAI answers it and never plans it (OC10). */
    _extraSendKwargs(opts) {
        const resolve = this._payaiResolve;
        this._payaiResolve = null;
        if (resolve) {
            return { resolve };
        }
        const o = opts && typeof opts === "object" ? opts : {};
        const out = { ...super._extraSendKwargs(...arguments) };
        if (o.spoken) { out.voice = true; }
        if (o.askOnly) { out.ask_only = true; }
        return out;
    },

    /** Clear conversation: the doors go with the conversation they were
     *  registered on, so the next open registers them again. */
    async clearHistory() {
        DOORS.key = "";
        return super.clearHistory(...arguments);
    },

    /** A send that answers a PayAI card never goes through the router: a
     *  router would read "Cancel" or a person's name as a new question
     *  (OC-R4). */
    _bypassRouter() {
        return Boolean(this._payaiResolve) || super._bypassRouter(...arguments);
    },

    /** The plan's own read-back (only ever on a spoken request). ONECHAT
     *  OC3: through the chat's one `speak`, so it gets the same filter (no
     *  amounts, no vendor name), the voice of its own language and the Stop
     *  control on its card. The card's own money rows (`value`, `figures`)
     *  are withheld word for word, whatever their format. */
    _payaiSpeak(text, turnId, card) {
        try {
            if (typeof window !== "undefined" && window.speechSynthesis) {
                window.speechSynthesis.cancel();
            }
        } catch {
            // nothing to stop
        }
        this.speak(String(text || ""), turnId, { money: moneyOfCard(card) });
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
            } else if (newer && m.card.task_id && acts.some((a) => a.id === "do"
                       || a.id === "cancel" || a.id === "typed")) {
                // An older plan or question (P3-W5: questions carry Cancel
                // too) is closed on the server; its buttons go with it.
                m.card.actions = acts.filter((a) => !["do", "cancel", "typed"].includes(a.id));
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
            if (card.tier === "decide" && card.state === "planned") { return "bad"; }
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
                // begin() answers false (never throws) for a key it does not
                // know: say so instead of a button that silently does nothing.
                Promise.resolve(scenario.begin(act.scenario || "sc_payrun", act.mode || "watch"))
                    .then((ok) => { if (ok === false) { this._payaiDoorFailed(); } })
                    .catch(() => this._payaiDoorFailed());
            } else {
                this._payaiDoorFailed();
            }
        } else if (act.id === "followup" && msg.card && msg.card.task_id && !auto) {
            // PayAI is still answering: nothing is sent and nothing is kept
            // for later — the next typed sentence must never go out as this
            // card's answer. The button stays pressable.
            if (this.state.isLoading) { return; }
            const resolve = {
                task_id: msg.card.task_id, slot: act.slot, value: act.value, action: act.action,
            };
            this._payaiResolve = resolve;
            return Promise.resolve(this.sendSuggestion(act.label)).then(() => {
                if (this._payaiResolve === resolve) { this._payaiResolve = null; }
            });
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

    /** P3 — the typed word (and the approver's optional note) go to the
     *  server, which checks the word, the seat and the plan all over again. */
    payaiTypedAct(card) {
        return (card.actions || []).find((a) => a.id === "typed") || null;
    },

    async payaiTypedDo(msg, word, note) {
        if (!msg.card || msg.card.busy) { return; }
        msg.card.busy = true;
        msg.card.typed_error = "";
        await this._payaiTaskCall(msg, "rpc_confirm_task", ["typed", word, note || ""]);
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
            this.notification.add(payaiCallFailedText(e, method, msg.card), { type: "warning" });
        }
    },

    _payaiApply(msg, card) {
        if (!card) {
            if (msg.card) { msg.card.busy = false; }
            return;
        }
        if (card.inline && msg.card && card.task_id === msg.card.task_id) {
            // P3 — a wrong word: the hint goes under the box on THIS card.
            msg.card.busy = false;
            msg.card.typed_error = ((card.notes || [])[0] || {}).text || card.title || "";
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
        const card = msg.card;
        if (this.payaiChipOff(card, chip)) { return; }
        // P3:crit-6 — a Remind chip is answered by a one-off note BELOW the
        // card and the card's offer stays open: each holder is a chip of its
        // own and only the one tapped is used up. Any other chip answers the
        // card once, so one pick still closes them all.
        const several = card.chip_action === "remind";
        if (several) {
            card.picked_values = [...(card.picked_values || []), chip.value];
        } else {
            card.picked = chip.value;
        }
        const resolve = {
            task_id: card.task_id,
            slot: card.chip_slot,
            value: chip.value,
            action: card.chip_action || undefined,
        };
        this._payaiResolve = resolve;
        const before = this.state.messages.length;
        return Promise.resolve(this.sendSuggestion(chip.label)).then(() => {
            // Not sent (the chat was busy): the answer must not ride along
            // with whatever the person types next.
            if (this._payaiResolve === resolve) { this._payaiResolve = null; }
            // No card came back (the connection dropped): the chip is
            // pressable again instead of dead for good.
            if (this.state.messages.slice(before).some((m) => m.card)) { return; }
            if (several) {
                card.picked_values = (card.picked_values || []).filter((v) => v !== chip.value);
            } else if (card.picked === chip.value) {
                card.picked = false;
            }
        });
    },

    /** The chip was used: Remind chips one by one, any other chip all at once. */
    payaiChipOff(card, chip) {
        if (card.chip_action === "remind") {
            return (card.picked_values || []).includes(chip.value);
        }
        return Boolean(card.picked);
    },

    payaiChipOn(card, chip) {
        if (!chip.value) { return false; }
        return card.picked === chip.value || (card.picked_values || []).includes(chip.value);
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
