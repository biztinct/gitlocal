/** @odoo-module **/
/* =============================================================================
   Places — where a screen lives since the rail cutover, and the ONE way the
   learning surfaces open it.  (LEARN REFRESH step 1)

   Every working screen is now a TAB (lens) inside one of nine hub pages. The
   content says where each screen lives (`screen.places`, authored in data.js):

       "pb_pay_hub:payslips"            hub action tag : lens key
       "pb_pay_hub:adjust/proration"    … / the lens's own inner tab
       "detail:contract"                a panel that is a screen wherever it opens

   and the nine hub pages carry `screen.hub` — the hub's action xml-id, the
   context key its shell reads a lens from, and its tabs' names and lines.

   THIS FILE OWNS THE STATION → PLACE MAP. Nothing else in pb_learn turns a
   screen into a destination: the helper's "Take me there", the lesson map's
   "Open", the walkthrough engine, the live practice task and the lesson rows
   all come through `openScreen` / `openLearn`, reading the same content.

   The "where am I NOW" half is not here: the hubs publish it themselves
   (`@pb_hub/js/hub_place`), and this file only reads it.
   ========================================================================== */
import { openHub } from "@pb_hub/js/hub_nav";
import { hubPlace, placeSub } from "@pb_hub/js/hub_place";

import { tx, SP } from "./runtime";

/** The Learn hub, and the lens the lesson map is. */
export const LEARN_HUB_XMLID = "pb_learn.action_learn_hub";
export const LESSONS_LENS = "lessons";

/* Which stations this reader can reach — `learn.runtime.bootstrap`'s
   `visible_stations`, set by whichever surface fetched it first (the helper
   or the map). Null until then, and every reader treats null as "unknown",
   never as "no". */
export const learnReach = { stations: null };

export function setReach(stations) {
    if (stations && typeof stations === "object") {
        learnReach.stations = stations;
    }
}

const PLACE = /^([a-z_]+):([a-z_]+)(?:\/([a-z_]+))?$/;

/** "<tag>:<lens>[/<sub>]" → {tag, lens, sub}; "detail:x" → {detail: "x"}. */
export function parsePlace(p) {
    const m = PLACE.exec(p || "");
    if (!m) {
        return null;
    }
    if (m[1] === "detail") {
        return { detail: m[2] };
    }
    return { tag: m[1], lens: m[2], sub: m[3] || "" };
}

/** The hub page (orientation screen) for a hub action tag, or null. */
export function hubScreenOf(screens, tag) {
    return (screens || []).find((s) => s.hub && s.hub.tag === tag) || null;
}

/** The first place a screen can be OPENED at (a hub tab), or null. */
export function navPlace(screen) {
    for (const p of (screen && screen.places) || []) {
        const pl = parsePlace(p);
        if (pl && !pl.detail) {
            return pl;
        }
    }
    return null;
}

/** A screen by key, by a scenario xml-id that means it, or by its own action. */
export function screenForRef(screens, ref) {
    if (!ref) {
        return null;
    }
    const list = screens || [];
    return list.find((s) => s.key === ref)
        || list.find((s) => (s.navs || []).includes(ref))
        || list.find((s) => (s.own_xmlid && s.own_xmlid === ref)
                            || (s.own_tag && s.own_tag === ref))
        || null;
}

/** The screen the published place IS, or null. The helper's first pass.
 *
 *  An open detail panel wins anywhere (it floats over whichever page opened
 *  it). Otherwise the place counts only while the current action is the hub
 *  that published it — the store can lag an action switch by a frame, and a
 *  stale Pay Run place must never ground a screen that is not Pay Run. The
 *  inner tab is tried before the lens, and a lens with no lesson screen lands
 *  on the hub's own page: on a hub the answer is never "nothing". */
export function screenAtPlace(screens, actionTag) {
    const list = screens || [];
    if (hubPlace.detail) {
        const d = list.find((s) => (s.places || []).includes(`detail:${hubPlace.detail}`));
        if (d) {
            return d;
        }
    }
    if (!hubPlace.tag || !actionTag || actionTag !== hubPlace.tag) {
        return null;
    }
    const base = `${hubPlace.tag}:${hubPlace.lens}`;
    const sub = placeSub();
    for (const want of (sub ? [`${base}/${sub}`, base] : [base])) {
        const hit = list.find((s) => (s.places || []).includes(want));
        if (hit) {
            return hit;
        }
    }
    return hubScreenOf(list, hubPlace.tag);
}

/** The words for one tab of one hub, in the helper's language — or "". */
export function tabName(screens, tag, lens) {
    const hs = hubScreenOf(screens, tag);
    const t = hs && hs.hub.tabs && hs.hub.tabs[lens];
    return t ? tx(t.name) : "";
}

/** "Pay Run › Payslips" for a screen that lives in a hub, else its name. */
export function placeLabel(screens, screen) {
    if (!screen) {
        return "";
    }
    const pl = navPlace(screen);
    const hs = pl && hubScreenOf(screens, pl.tag);
    if (hs) {
        const tab = tabName(screens, pl.tag, pl.lens);
        return tab ? `${tx(hs.name)}${SP}›${SP}${tab}` : tx(hs.name);
    }
    return tx(screen.name);
}

/** Can this screen be opened from a lesson at all (a hub tab, or an action)? */
export function canOpen(screen) {
    return !!(screen && (navPlace(screen) || screen.open || screen.own_xmlid
                         || screen.own_tag || (screen.navs || []).length));
}

/** true / false / null (unknown) — can this reader reach the screen at all? */
export function reachable(screen) {
    const st = screen && learnReach.stations && learnReach.stations[screen.key];
    return st ? !!st.visible : null;
}

/** Open a screen where it lives: hub › tab when it is in a hub, else its own
 *  action. `ref` is a screen, a screen key, or a scenario xml-id. Resolves to
 *  `{screen, place}` — `place` is the hub tab asked for, or null. */
export async function openScreen(action, screens, ref) {
    const screen = typeof ref === "object" && ref ? ref : screenForRef(screens, ref);
    const place = navPlace(screen);
    const seq = hubPlace.seq;
    if (place) {
        const hs = hubScreenOf(screens, place.tag);
        await openHub(action, {
            xmlid: hs ? hs.hub.xmlid : undefined,
            tag: hs ? undefined : place.tag,
            lens: place.lens,
            lensKey: hs ? hs.hub.lens_key : undefined,
        });
        return { screen, place, seq };
    }
    const target = (screen && (screen.open || screen.own_xmlid || (screen.navs || [])[0]))
        || (typeof ref === "string" && ref.includes(".") ? ref : "");
    if (target) {
        await action.doAction(target, { clearBreadcrumbs: true });
    } else if (screen && screen.own_tag) {
        await action.doAction({ type: "ir.actions.client", tag: screen.own_tag },
                              { clearBreadcrumbs: true });
    }
    return { screen, place: null, seq };
}

/** Wait for the hub to say where it landed: "here", "elsewhere" (the shell
 *  moved the reader off a tab they cannot open) or "timeout". `seq` is the
 *  store's counter from BEFORE the navigation, so the hub being left can
 *  never answer for the hub being opened. */
export function waitForPlace(place, seq, ms = 6000) {
    const deadline = Date.now() + ms;
    return new Promise((resolve) => {
        const tick = () => {
            if (hubPlace.seq !== seq && hubPlace.tag === place.tag && hubPlace.ready) {
                return resolve(hubPlace.lens === place.lens ? "here" : "elsewhere");
            }
            if (Date.now() > deadline) {
                return resolve("timeout");
            }
            return setTimeout(tick, 100);
        };
        tick();
    });
}

/** The lesson map, inside the Learn hub (rail visible), with an arrival
 *  focus the map reads: "station:<key>", "lesson:<key>",
 *  "scenario:<key>:<mode>", "practice" or "suggest:<key>". */
export function openLearn(action, focus) {
    return openHub(action, {
        xmlid: LEARN_HUB_XMLID,
        lens: LESSONS_LENS,
        focus: focus || undefined,
    });
}
