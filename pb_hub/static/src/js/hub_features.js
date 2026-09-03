/** @odoo-module **/
/**
 * The kit's one question: "does this company have that part of the product?"
 *
 * ========================== the dependency runs backwards =====================
 * The answer lives on the customer's database and is read by `pb_tenancy`,
 * which DEPENDS on this kit. So the kit cannot import it. It looks the service
 * up by name at run time instead, and every function below is written to give a
 * sensible answer when it finds nothing:
 *
 *     no service  ->  the Platform Link is not installed here  ->  everything on
 *     empty maps  ->  the platform has never said anything     ->  everything on
 *     unknown key ->  nobody has defined that feature          ->  everything on
 *
 * FAIL OPEN, EVERY TIME, and that is not a shortcut. A switch is a sales
 * decision, not a permission; the thing behind every door keeps its own
 * permissions whatever this file says. The worst case of failing open is that
 * somebody sees a tile they have not bought. The worst case of failing closed
 * is a payroll office whose product disappeared because a setting had not
 * arrived — so the two mistakes are not the same size and the code does not
 * treat them as if they were.
 *
 * ============================== where a key comes from ========================
 * A lens says which feature it belongs to (`feature: "insights"` on its
 * descriptor). The command palette cannot: its rows are declared by a dozen
 * modules that know nothing about any of this, so the map below says which
 * SURFACE belongs to which part of the product, in one place, next to the
 * kit that reads it.
 */
import { session } from "@web/session";

/** The name `pb_tenancy` registers its features service under. */
export const FEATURES_SERVICE = "pb_tenancy_features";

/**
 * Which SURFACE belongs to which part of the product.
 *
 * A surface is named two ways depending on who is naming it — a client action
 * tag (`pb_compliance_hub`) or the XML id of the action that opens it
 * (`pb_compliance_hub.action_pb_compliance_hub`) — and the palette's rows use
 * both, sometimes for the same door. Both spellings are in this one map rather
 * than in two, because a reader asking "is Insights covered?" should get the
 * answer from one place.
 *
 * A surface that is not here belongs to no feature and is never hidden. That
 * default has to be "everybody has this", or every screen added in future
 * would quietly vanish until somebody remembered this file.
 */
export const FEATURE_BY_SURFACE = {
    // ---------------------------------------------------------- Insights
    pb_insights_hub: "insights",
    "pb_insights_hub.action_pb_insights_hub": "insights",
    pb_insights: "insights",
    pb_explorer_cockpit: "insights",
    pb_workforce_insights: "insights",
    // --------------------------------------------------------- Workforce
    // Mission Control and every one of its eight lenses, which all open the
    // same tag.
    pb_workforce: "workforce",
    "pb_mission.action_pb_workforce": "workforce",
    // --------------------------------------------------------- Lifecycle
    pb_lifecycle_hub: "lifecycle",
    "pb_lifecycle.action_pb_lifecycle_hub": "lifecycle",
    "pb_lifecycle.action_journey_template": "lifecycle",
    "pb_lifecycle.action_hr_letter": "lifecycle",
    // -------------------------------------------------------- Compliance
    pb_compliance_hub: "compliance",
    "pb_compliance_hub.action_pb_compliance_hub": "compliance",
    pb_govt_reports: "compliance",
    "pb_govt_reports.action_pb_filing_flow": "compliance",
    pb_audit: "compliance",
    // The two narrow ones inside Compliance, sold on their own.
    pb_bank_ocr: "bank_ocr",
    pb_young_worker: "young_workers",
    // -------------------------------------------------------------- Learn
    learn_journey: "learn",
    "pb_learn.action_learn_journey": "learn",
    // ------------------------------------------- inside the Pay Run mission
    pb_fullfinal: "fullfinal",
    pb_retro: "retro_proration",
    pb_proration: "retro_proration",
};

/**
 * A lens INSIDE a hub that is its own part of the product.
 *
 * `<surface>#<lens>`, and it wins over the hub's own entry: Bank statement
 * scanning is sold separately from Compliance, so the row that deep-links to
 * the Bank tab must disappear when the SCANNING is off, not only when the whole
 * of Compliance is. Where the map says nothing, the hub's own answer stands —
 * which is why every Compliance lens is still hidden when Compliance is off.
 */
export const FEATURE_BY_LENS = {
    "pb_compliance_hub#bank": "bank_ocr",
    "pb_compliance_hub.action_pb_compliance_hub#bank": "bank_ocr",
    "pb_compliance_hub#young": "young_workers",
    "pb_compliance_hub.action_pb_compliance_hub#young": "young_workers",
    "pb_pay_hub#settle": "fullfinal",
    "pb_payhub.action_pb_pay_hub#settle": "fullfinal",
    "pb_pay_hub#adjust": "retro_proration",
    "pb_payhub.action_pb_pay_hub#adjust": "retro_proration",
    "pb_people_hub#plan": "people_plan",
    "pb_people_hub.action_pb_people_hub#plan": "people_plan",
};

/** Everything on. The answer whenever there is nothing to read. */
const OPEN = { shown: true, locked: false, text: "" };

/**
 * The features service, or null.
 *
 * `env.services` is a plain object of everything that started, so a missing
 * service is `undefined` rather than a throw — but the lookup is still wrapped,
 * because a kit function that can take a hub down over a menu is worse than a
 * hub that shows one tile too many.
 */
export function featuresOf(env) {
    try {
        return (env && env.services && env.services[FEATURES_SERVICE]) || null;
    } catch {
        return null;
    }
}

/**
 * (shown, locked, text) for one part of the product.
 *
 * Falls back to `session.pb_tenancy` when the service is absent but the page
 * still carries the answer — which is the case inside a component built before
 * services are reachable, and costs one property read.
 */
export function featureGate(env, key) {
    if (!key) { return OPEN; }
    const api = featuresOf(env);
    if (api) { return api.gate(key); }
    const sess = (session && session.pb_tenancy) || null;
    if (!sess || !sess.features || !(key in sess.features)) { return OPEN; }
    if (sess.features[key]) { return OPEN; }
    const text = (sess.feature_lock_text || {})[key] || "";
    if ((sess.feature_mode || {})[key] === "lock") {
        return { shown: true, locked: true, text };
    }
    return { shown: false, locked: false, text };
}

/** Shorthand for the places that only care whether it is fully on. */
export function featureOn(env, key) {
    const g = featureGate(env, key);
    return g.shown && !g.locked;
}

/**
 * The part of the product ONE palette row's door belongs to, or "".
 *
 * A lens inside a hub is asked about first, because it is the narrower answer:
 * a row that opens the Bank tab of Compliance belongs to Bank statement
 * scanning, and only falls back to Compliance when nobody sells the tab on its
 * own. Both spellings of the door are tried, because rows in this product name
 * their surfaces both ways.
 */
export function featureForAction(action) {
    const a = action || {};
    const doors = [a.tag, a.xmlid].filter(Boolean);
    if (a.lens) {
        for (const d of doors) {
            const key = FEATURE_BY_LENS[`${d}#${a.lens}`];
            if (key) { return key; }
        }
    }
    for (const d of doors) {
        const key = FEATURE_BY_SURFACE[d];
        if (key) { return key; }
    }
    return "";
}

/**
 * The reactive state behind all of this, for a component that wants to repaint
 * when a switch is flipped on the platform. Null when there is nothing to
 * watch, which every caller must cope with.
 */
export function featuresState(env) {
    const api = featuresOf(env);
    return api ? api.state : null;
}
