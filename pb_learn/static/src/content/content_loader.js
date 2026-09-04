/** @odoo-module **/
/* =============================================================================
   The static content plane, client side.

   Since LEARNOS Phase 1a the learning content is not in the database and is not
   in an RPC payload: it is one generated bilingual asset that the browser
   fetches once per page load and every surface shares.

     loadContent()   the tree, memoised. Stations, missions, glossary, chrome,
                     intents, screens, columns, global_suggest, version.
     composeScreens() the Coach's screen list — the static half from the tree,
                     the runtime half (matchers, own action, live next_step)
                     from learn.runtime.bootstrap().

   WHY A FETCH AND NOT AN ASSET BUNDLE ENTRY
   -----------------------------------------
   Half a megabyte of bilingual prose in web.assets_backend is half a megabyte
   every user of the product parses on every cold load, whether or not they ever
   open the Journey. A fetch is paid by the surfaces that need it, and it is
   paid once: the promise is memoised at module scope, so the Journey, the Coach
   and the live runner mounted on the same page share ONE request.

   `cache: "no-cache"` is deliberate and is not "do not cache". It means
   revalidate: the browser keeps the copy and asks the server whether it is
   still current, so an unchanged file costs a 304 and a deployed change is
   picked up on the next load rather than whenever a max-age happens to lapse.
   A stale content plane is the one failure mode that would be invisible — the
   surfaces would render perfectly, just out of date.

   TREAT THE TREE AS IMMUTABLE. It is one object shared by three components;
   anything that needs to add a key (the Journey merges visibility onto each
   station) must copy first.
   ========================================================================== */

export const CONTENT_URL = "/pb_learn/static/content/learn_content.json";

/* The empty shape, returned when the asset cannot be read. Every consumer then
   renders an empty Journey and an honest Coach rather than throwing on the
   screen it happens to be mounted over. */
const EMPTY = {
    version: "",
    chrome: {},
    stations: [],
    missions: [],
    glossary: [],
    intents: [],
    screens: [],
    columns: [],
    global_suggest: [],
};

let pending = null;

export function loadContent() {
    if (!pending) {
        pending = fetch(CONTENT_URL, { cache: "no-cache" })
            .then((res) => {
                if (!res.ok) {
                    throw new Error(`${res.status} ${res.statusText}`);
                }
                return res.json();
            })
            .then((tree) => Object.assign({}, EMPTY, tree))
            .catch((err) => {
                // Never leave a rejected promise memoised: the next surface to
                // mount would inherit a failure it had no part in and could
                // never retry out of.
                pending = null;
                console.warn("pb_learn: cannot load the content plane", err);
                return EMPTY;
            });
    }
    return pending;
}

/** ONLY for tests and for a deliberate reload. */
export function resetContent() {
    pending = null;
}

/** The Coach's screen list: static content + this session's runtime facts.
 *
 *  The shape is exactly what `learn.intent.coach_bundle` used to return, so
 *  coach.js's three-pass resolver and live_mission.js's deep link read the same
 *  keys they always did. `next_step` comes from the runtime half because it can
 *  carry a {{live:...}} token, which is a database read by definition. */
export function composeScreens(content, runtime) {
    const rt = (runtime && runtime.screens_runtime) || {};
    return (content.screens || []).map((s) => {
        const r = rt[s.key] || {};
        return {
            key: s.key,
            name: s.name,
            blurb: s.blurb || "",
            next_step: r.next_step === undefined ? s.next_step || "" : r.next_step,
            action_tags: r.action_tags || [],
            action_xmlids: r.action_xmlids || [],
            models: r.models || [],
            own_tag: r.own_tag || "",
            own_xmlid: r.own_xmlid || "",
            suggest: s.suggest || [],
        };
    });
}

/** The Journey's station list: static content + whether this reader can
 *  actually reach the screen each station teaches. */
export function composeStations(content, runtime) {
    const rt = (runtime && runtime.visible_stations) || {};
    return (content.stations || []).map((s) =>
        Object.assign({}, s, rt[s.key] || { visible: true, missing: false }));
}
