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
import { markup, onMounted, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { openHub } from "@pb_hub/js/hub_nav";
import { AiInsightChat } from "@pb_payroll_ai_insights/components/ai_insight_chat/ai_insight_chat";

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
};

function svg(name) {
    const body = ICONS[name] || ICONS.info;
    return markup(`<svg class="payai-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`);
}

patch(AiInsightChat.prototype, {
    setup() {
        super.setup(...arguments);
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
                    restricted: !!r.restricted,
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
            this._payaiAutoRun(fresh);
        }
        return out;
    },

    _extraSendKwargs() {
        const resolve = this._payaiResolve;
        this._payaiResolve = null;
        return resolve ? { resolve } : super._extraSendKwargs(...arguments);
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
        } else if (act.id === "followup" && msg.card && msg.card.task_id && !auto) {
            this._payaiResolve = {
                task_id: msg.card.task_id, slot: act.slot, value: act.value, action: act.action,
            };
            this.sendSuggestion(act.label);
        }
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
