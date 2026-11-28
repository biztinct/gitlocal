/** @odoo-module **/
/**
 * Employee voice's doors: the Talent › Voice tab, two ⌘K rows and a
 * Settings card (category key `voice`, FACTS §5 — each S9 phase owns its
 * own key). Every door names an XMLID, never a bare tag. Icons from the
 * shared `ic()` registry; no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { TALENT_LENSES } from "@pb_talent_hub/js/talent_hub";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { PbVoiceBoard } from "@pb_voice/js/voice_board";

/** `pb.voice.round._voice_is_hr()`, verbatim. */
export const VOICE_GATE = ["hr.group_hr_user", "base.group_system"];

registry.category(TALENT_LENSES).add("voice", {
    key: "voice",
    icon: "messageSquare",
    label: _t("Voice"),
    title: _t("Employee voice"),
    Component: PbVoiceBoard,
    props: { embedded: true },
    groups: VOICE_GATE,
    probe: { model: "pb.voice.round", method: "can_open" },
    feature: "lifecycle",
}, { sequence: 50 });

const HUB_XMLID = "pb_talent_hub.action_pb_talent_hub";
const palette = registry.category("pb_hub_palette");

// 2900 block: S9-C (pip took 2700; count the seed file before adding more).
palette.add("voice_board", {
    id: "voice_board",
    label: _t("Employee surveys"),
    sublabel: _t("Talent"),
    icon: "messageSquare",
    groups: VOICE_GATE,
    probe: { model: "pb.voice.round", method: "can_open" },
    requires: "pb_voice_board",
    action: { xmlid: HUB_XMLID, lens: "voice" },
    keywords: ["survey", "engagement", "voice", "enps", "khảo sát", "survei"],
}, { sequence: 2900 });

palette.add("voice_library", {
    id: "voice_library",
    label: _t("Survey question library"),
    sublabel: _t("Employee voice"),
    icon: "bookOpen",
    groups: VOICE_GATE,
    requires: "pb_voice_board",
    action: { xmlid: "pb_voice.action_pb_voice_library" },
}, { sequence: 2910 });

registry.category(SETTINGS_CATEGORIES).add("voice", {
    key: "voice",
    group: "hr",
    icon: "messageSquare",
    label: _t("Employee surveys"),
    blurb: _t("The ready-made questions HR can add to a survey, in every "
              + "language this system uses."),
    groups: VOICE_GATE,
    cards: [{
        id: "voice_library",
        xmlid: "pb_voice.action_pb_voice_library",
        icon: "bookOpen",
        label: _t("Question library"),
        sub: _t("Switch questions off, change their words, or add your own."),
    }, {
        id: "voice_actions",
        xmlid: "pb_voice.action_pb_voice_action",
        icon: "listChecks",
        label: _t("Action plans"),
        sub: _t("What the company said it would do after each survey."),
    }],
}, { sequence: 60 });
