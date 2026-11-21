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

import { RT, T, tx, SP } from "../engine/runtime";
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

/** LEARNREV P5a (LR51) — one field can sit on two screens (Pay role: the
 *  Component treatment board AND Mapping's inspector). The palette breaks a
 *  tie by row order, so the screen whose OWN authored search words name the
 *  column — the field's home — goes first, exactly as the Library's search
 *  ranks it. A stable partition: everything else keeps its order. */
export function homeFirst(rows, content) {
    const fold = (s) => String(s || "").toLowerCase().normalize("NFD")
        .replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/\s+/g, " ").trim();
    const words = new Map();
    for (const s of (content && content.stations) || []) {
        const sw = s.search;
        const list = [].concat(sw && sw.en ? sw.en : [], sw && sw.vi ? sw.vi : [],
            Array.isArray(sw) ? sw : []);
        words.set(s.key, fold(list.join(" ")));
    }
    const isHome = (r) => {
        const hay = words.get(r && r.screen) || "";
        return !!hay && [r.column, ...(r.columns || [])].some((c) => {
            const f = fold(c);
            return f && hay.includes(f);
        });
    };
    const list = (rows || []).filter(Boolean);
    return [...list.filter(isHome), ...list.filter((r) => !isHome(r))];
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
    const group = _t("Help");
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

/** LEARNREV P3 (S5) — every field card in the ⌘K search: "Pay role" with
 *  "Field on Component treatment" under it. `rows` is `learn.guide.rpc_index`
 *  (content/field_index.js) in the drawer's language; `open(screen, field)`
 *  opens that screen with the Guide's Fields row expanded (the drawer's own
 *  door). Idempotent, like the lesson rows.
 *
 *  `door: false` — these rows are the palette's and the Library's only. They
 *  are NOT handed to PayAI as screens it may open (the PayAI door list is
 *  "the screens", and a field is not one), so PayAI's answers do not move. */
export function registerFieldRows(rows, open, content) {
    const group = _t("Help");
    let i = 0;
    for (const r of homeFirst(rows, content)) {
        if (!r || !r.screen || !r.key) {
            continue;
        }
        const id = `learn.field.${r.screen}.${r.key}`;
        if (palette.contains(id)) {
            continue;
        }
        const other = (r.columns || []).filter((c) => c && c !== r.column);
        palette.add(id, {
            id,
            label: r.column,
            // The other language's spelling rides at the end, so a column is
            // found by either name; the line says what the field is.
            sublabel: [T("libFieldOn").replace("{screen}", r.screen_name || r.screen),
                       r.line, ...other].filter(Boolean).join(`${SP}·${SP}`),
            icon: "info",
            group,
            door: false,
            onRun: () => {
                if (typeof open === "function") {
                    open(r.screen, r.key);
                }
            },
        }, { sequence: BASE + 4000 + (++i) * 10 });
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
