/** @odoo-module **/
/**
 * The doors into Conduct cases.
 *
 *   1. A Talent tab ("Conduct"), registered into the hub's soft registry.
 *      Goals 10, Growth 20, Conduct 30, Praise 40.
 *   2. ⌘K rows in the 2760 block (growth plans hold 2700-2730).
 *
 * THE GATE IS THIS MODULE'S OWN TWO GROUPS — no HR, lifecycle, payroll or
 * administrator group (owner ruling P3). The server's `pb.conduct.can_open`
 * answers the same question, so the tab is offered exactly when the board
 * would open.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { TALENT_LENSES } from "@pb_talent_hub/js/talent_hub";
import { PbConductBoard } from "@pb_conduct/js/conduct_board";

export const CONDUCT_GATE = [
    "pb_conduct.group_conduct_user",
    "pb_conduct.group_conduct_head",
];

registry.category(TALENT_LENSES).add("conduct", {
    key: "conduct",
    icon: "scale",
    label: _t("Conduct"),
    title: _t("Conduct cases"),
    Component: PbConductBoard,
    groups: CONDUCT_GATE,
    probe: { model: "pb.conduct", method: "can_open" },
    feature: "lifecycle",
}, { sequence: 30 });

const palette = registry.category("pb_hub_palette");

palette.add("conduct_board", {
    id: "conduct_board",
    label: _t("Conduct cases"),
    sublabel: _t("Talent"),
    icon: "scale",
    groups: CONDUCT_GATE,
    probe: { model: "pb.conduct", method: "can_open" },
    requires: "pb_conduct_board",
    action: { xmlid: "pb_talent_hub.action_pb_talent_hub", lens: "conduct" },
    keywords: ["disciplinary", "warning", "hearing", "kỷ luật", "cảnh cáo", "teguran", "disiplin"],
}, { sequence: 2760 });

palette.add("conduct_reasons", {
    id: "conduct_reasons",
    label: _t("Conduct case reasons"),
    sublabel: _t("Conduct cases"),
    icon: "tag",
    groups: ["pb_conduct.group_conduct_head"],
    requires: "pb_conduct_board",
    action: { xmlid: "pb_conduct.action_pb_conduct_reason" },
}, { sequence: 2770 });
