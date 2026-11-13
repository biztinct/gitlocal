/** @odoo-module **/
/**
 * PAYAI P1 — the "PayAI can act" card in the Settings hub. The hub's soft
 * registry (`pb_settings_category`) takes whole categories; a category with
 * one card opens that card directly.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

registry.category("pb_settings_category").add("payai_can_act", {
    key: "payai_can_act",
    icon: "sparkles",
    label: _t("PayAI can act"),
    blurb: _t("What PayAI may do for people when they ask it in words: look, prepare, decide."),
    groups: ["base.group_system"],
    cards: [
        { id: "payai_can_act", xmlid: "pb_payai_actions.action_payai_can_act", icon: "sparkles",
          label: _t("PayAI can act"),
          sub: _t("Switch what PayAI may do here, by kind: look, prepare, decide.") },
    ],
}, { sequence: 60 });
