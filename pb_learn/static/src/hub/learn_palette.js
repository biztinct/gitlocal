/** @odoo-module **/
/**
 * LEARN v3 — lessons and walkthroughs in the ⌘K search.
 *
 * The search that finds screens also finds "how to" help: every station on
 * the lesson map and every walkthrough, in the learner's language. A row
 * opens the lesson map on that station, or starts the walkthrough, through
 * the hub's own arrival key (`pb_focus`), which journey.js reads.
 *
 * Registered after the content plane loads, at sequence 5000+, so the rows
 * sit below every surface in an empty search and only surface when typed
 * for. Ungated, like the Learn rail item: a lesson never hides itself from
 * the person it would teach.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

import { RT, tx, SP } from "../engine/runtime";
import { loadContent } from "../content/content_loader";

const palette = registry.category("pb_hub_palette");
const BASE = 5000;

function restoreLang() {
    try {
        const p = JSON.parse(window.localStorage.getItem("pbLearnPrefs") || "{}");
        const sessionLang = window.odoo?.session_info?.user_context?.lang || "";
        return p.lang || (sessionLang.startsWith("vi") ? "vi" : "en");
    } catch {
        return "en";
    }
}

/** Add the rows. Idempotent; called at load and again by the helper once it
 *  has the content, so the rows exist whichever gets there first. */
export function registerLessonRows(content) {
    const lang = RT.lang && RT.lang !== "en" ? RT.lang : restoreLang();
    const say = (v) => {
        const prev = RT.lang;
        RT.lang = lang;
        try {
            return tx(v);
        } finally {
            RT.lang = prev;
        }
    };
    const group = _t("Learn");
    const howTo = _t("how to");
    let i = 0;
    for (const s of (content.stations || []).slice().sort((a, b) => a.sequence - b.sequence)) {
        const id = `learn.station.${s.key}`;
        if (palette.contains(id)) {
            continue;
        }
        palette.add(id, {
            id,
            label: say(s.name),
            sublabel: `${s.kind === "lesson" ? _t("Lesson") : _t("Guide")}${SP}·${SP}${s.duration_min}${SP}min${SP}·${SP}${howTo}`,
            icon: "bookOpen",
            group,
            action: { xmlid: "pb_learn.action_learn_journey", focus: `station:${s.key}` },
            requires: "learn_journey",
        }, { sequence: BASE + (++i) * 10 });
    }
    for (const sc of content.scenarios || []) {
        const id = `learn.scenario.${sc.key}`;
        if (palette.contains(id) || !(sc.modes || []).length) {
            continue;
        }
        const mode = (sc.modes || []).includes("watch") ? "watch" : sc.modes[0];
        palette.add(id, {
            id,
            label: say(sc.name),
            sublabel: `${_t("Walkthrough")}${SP}·${SP}${howTo}`,
            icon: "play",
            group,
            action: { xmlid: "pb_learn.action_learn_journey", focus: `scenario:${sc.key}:${mode}` },
            requires: "learn_journey",
        }, { sequence: BASE + (++i) * 10 });
    }
}

loadContent().then(registerLessonRows).catch((e) => {
    // No rows; the search works without them.
    console.warn("pb_learn: lesson rows not added to the search", e);
});
