/** @odoo-module **/
/**
 * Learning's mission row in the global ⌘K palette (LEARNING L0).
 *
 * Sequence 168: the mission block runs in rail order — Talent 165, Learning
 * 168, Help 170. Everybody may open it (the entry has no groups), so the row
 * carries `base.group_user` only. The old words keep finding it (R10): people
 * typed "training" and "talent" to reach the Training tab before.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

registry.category("pb_hub_palette").add("learninghub", {
    id: "learninghub",
    label: _t("Learning"),
    sublabel: _t("Courses, tests and certificates"),
    icon: "graduationCap",
    groups: ["base.group_user"],
    requires: "pb_learning_hub",
    action: { xmlid: "pb_learning_hub.action_pb_learning_hub" },
    keywords: ["training", "learn", "courses", "đào tạo", "học tập", "talent"],
}, { sequence: 168 });
