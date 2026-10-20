/** @odoo-module **/
/**
 * Talent's mission row in the global ⌘K palette (NAV P2).
 *
 * Sequence 175: the mission block runs in rail order and Talent sits just
 * above Learn (170 is Learn's own row, kept). The old words people used for
 * these boards keep finding it (R10).
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

registry.category("pb_hub_palette").add("talenthub", {
    id: "talenthub",
    label: _t("Talent"),
    sublabel: _t("Goals, growth, training and praise"),
    icon: "graduationCap",
    // Mirrors the menu entry's permission lane (rule 1 of the palette seeds).
    groups: ["hr.group_hr_user", "base.group_system"],
    requires: "pb_talent_hub",
    action: { xmlid: "pb_talent_hub.action_pb_talent_hub" },
    keywords: ["praise", "goals", "training", "growth plans", "pip",
               "recognition", "khen ngợi", "mục tiêu", "đào tạo", "phát triển"],
}, { sequence: 165 });
