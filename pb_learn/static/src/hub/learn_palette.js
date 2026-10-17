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
import { _t, translationIsReady } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

import { RT, tx, SP } from "../engine/runtime";
import { loadContent } from "../content/content_loader";
import { LEARN_HUB_XMLID, LESSONS_LENS } from "../engine/places";

const palette = registry.category("pb_hub_palette");
const BASE = 5000;

function restoreLang() {
    try {
        const p = JSON.parse(window.localStorage.getItem("pbLearnPrefs") || "{}");
        // `user.lang` ("vi-VN"): the page's session info is deleted on load on
        // this version, so the old read always fell back to English (ONECHAT OC2).
        const sessionLang = String(user.lang || "").toLowerCase();
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
        // LEARN REFRESH step 3 — the station's own plain words ("currency,
        // exchange rate…") ride in the sublabel, because the palette matches
        // label + sublabel and a lesson must be findable by what it is about,
        // not only by its title.
        const words = s.search ? say(s.search) : howTo;
        palette.add(id, {
            id,
            label: say(s.name),
            sublabel: `${s.kind === "lesson" ? _t("Lesson") : _t("Guide")}${SP}·${SP}${_t("%s min", s.duration_min)}${SP}·${SP}${words}`,
            icon: "bookOpen",
            group,
            // LEARN REFRESH step 1: inside the Learn hub (rail visible),
            // on the Lessons tab, which reads the same focus.
            action: { xmlid: LEARN_HUB_XMLID, lens: LESSONS_LENS, focus: `station:${s.key}` },
            requires: "learn_hub",
        }, { sequence: BASE + (++i) * 10 });
    }
    for (const sc of content.scenarios || []) {
        const id = `learn.scenario.${sc.key}`;
        // A retired walkthrough is off the map and out of every offer
        // (LR21); the search must not offer it either.
        if (palette.contains(id) || sc.retired || !(sc.modes || []).length) {
            continue;
        }
        const mode = (sc.modes || []).includes("watch") ? "watch" : sc.modes[0];
        palette.add(id, {
            id,
            label: say(sc.name),
            sublabel: `${_t("Walkthrough")}${SP}·${SP}${howTo}`,
            icon: "play",
            group,
            action: { xmlid: LEARN_HUB_XMLID, lens: LESSONS_LENS, focus: `scenario:${sc.key}:${mode}` },
            requires: "learn_hub",
        }, { sequence: BASE + (++i) * 10 });
    }
}

// LEARNREV P0 (G16, ledger LR1): the rows' group and sublabels go through
// `_t`, which throws "translations have not been loaded" when called at module
// load — so wait for the localization service's own signal before building
// them. (coach.js registers them again once it has the content; the call is
// idempotent, whichever gets there first wins.)
Promise.all([loadContent(), translationIsReady])
    .then(([content]) => registerLessonRows(content))
    .catch((e) => {
        // No rows; the search works without them.
        console.warn("pb_learn: lesson rows not added to the search", e);
    });
