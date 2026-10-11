/** @odoo-module **/
/**
 * PAYAI P1 — when the helper drawer hosts the chat, IT answers the ⌘K
 * "Ask PayAI to…" row: open the drawer on the Ask tab and hand the text over
 * through the drawer's own hand-off (the same path "Ask about the data" uses).
 */
import { onMounted, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { CoachHost } from "@pb_learn/coach/coach";
import { PAYAI_HOOKS } from "./chat_patch";

patch(CoachHost.prototype, {
    setup() {
        super.setup(...arguments);
        this._payaiOpenHook = (text) => {
            if (!this.askTab) {
                return false;
            }
            const q = (text || "").trim();
            this.state.open = true;
            this.state.moment = null;
            this.state.handoff = q ? { text: q, id: Date.now() } : null;
            this.state.tab = "ask";
            return true;
        };
        onMounted(() => {
            registry.category(PAYAI_HOOKS).add("open", this._payaiOpenHook, { force: true });
        });
        onWillUnmount(() => {
            const hooks = registry.category(PAYAI_HOOKS);
            if (hooks.contains("open") && hooks.get("open") === this._payaiOpenHook) {
                hooks.remove("open");
            }
        });
    },
});
