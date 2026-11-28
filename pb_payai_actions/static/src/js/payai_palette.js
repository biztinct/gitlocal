/** @odoo-module **/
/**
 * PAYAI P1 — "Ask PayAI to…" in ⌘K. Shown under the matches whenever
 * something is typed; pressing it opens PayAI with the typed sentence.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PAYAI_HOOKS } from "./chat_patch";

registry.category("pb_hub_palette").add("payai_ask", {
    id: "payai_ask",
    label: _t("Ask PayAI to…"),
    sublabel: "",
    icon: "sparkles",
    group: _t("PayAI"),
    groups: ["pb_payroll_ai_insights.group_payai_user"],
    anyQuery: true,
    onRun: (query) => {
        const hooks = registry.category(PAYAI_HOOKS);
        if (hooks.contains("open")) {
            hooks.get("open")(query || "");
        }
    },
}, { sequence: 90 });
