import { registry } from "@web/core/registry";

/**
 * VU Form Engine — per-model hero enrichment registry.
 *
 * Any module can refine how the auto-synthesized hero renders for one model:
 *
 *   registry.category("vu_form_hero").add("health.fieldservice.order", {
 *       titleField: "display_name",   // overrides title-field heuristics
 *       statusField: "state",         // overrides status-field heuristics
 *       disabled: false,              // true = stock rendering for this model
 *   });
 *
 * Fields are only ever read from record.data already loaded by the view —
 * the engine never fetches extra fields.
 */
export const vuFormHeroRegistry = registry.category("vu_form_hero");

// Keyword → lucide icon for section (group) titles. First match wins.
const ICON_RULES = [
    [/address|location|catchment|map|geo/i, "map-pin"],
    [/invoice|billing|payment|price|pricing|financ|charge|amount|accounting|tax/i, "credit-card"],
    [/schedul|date|time|planning|recurr|appointment/i, "calendar"],
    [/duration|timer/i, "clock"],
    [/staff|team|assign|employee|member/i, "users"],
    [/client|contact|customer|patient|personal|partner|identity/i, "user"],
    [/service|clinical|medical|treatment|diagnos|health|care/i, "stethoscope"],
    [/phone|communication|sms|email|zalo|messag/i, "phone"],
    [/setting|config|technical|advanced|integration/i, "settings"],
    [/require|checklist|compliance|consent/i, "clipboard-check"],
    [/company|facility|branch|organi|department/i, "building"],
    [/delivery|logistic|transport|dispatch/i, "truck"],
    [/kpi|performance|score|metric/i, "gauge"],
    [/goal|target|outcome|objective/i, "target"],
    [/history|log|audit|track/i, "history"],
    [/note|description|remark|term|comment|detail/i, "file-text"],
    [/other|misc|more|info/i, "info"],
];

/**
 * @param {string} title group/section title from the view arch
 * @returns {string} lucide icon slug (must exist in vu_icons.scss)
 */
export function vuIconForSection(title) {
    for (const [re, icon] of ICON_RULES) {
        if (re.test(title || "")) {
            return icon;
        }
    }
    return "layout-grid";
}
