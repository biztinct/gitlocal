/** @odoo-module **/
/**
 * PAYAI P1 / ONECHAT OC2 — when the helper drawer hosts the chat, IT answers
 * the ⌘K "Ask PayAI to…" row: open the drawer and send the typed sentence
 * through the drawer's one way in (`openHelper`). The sentence is ROUTED like
 * anything typed into the box — a question gets an answer, an order a plan —
 * and it waits, queued, until the chat has mounted (handover §5.4). There is
 * no tab to switch any more.
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
            if (!this.chat) {
                return false;
            }
            const q = (text || "").trim();
            this.openHelper(q ? { text: q, send: true, origin: "palette" } : {});
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
