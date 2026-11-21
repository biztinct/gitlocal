/** @odoo-module **/
/**
 * `pb_lifecycle_hub` — RETIRED by NAV P2 (2026-10-21), kept as a redirector.
 *
 * The Lifecycle hub held Journeys plus six boards bolted on by other modules.
 * The owner's revised menu (design review §12.4) moved every one of them to
 * the place a person looks for it:
 *
 *     hiring                               → Hiring › Overview (or Talent pool)
 *     newjoiners · probation · exits ·
 *     contracts                            → People › the same tab
 *     pip                                  → Talent › Growth
 *     journeys (or nothing)                → Journeys on its own (Settings › HR)
 *
 * The left-menu entry is switched off (data + migration), but the CLIENT
 * ACTION stays registered, because bookmarks, old links, lesson places and
 * other modules' doors still say `pb_lifecycle_hub`. Zero dead ends (R10):
 * this tag is now a FUNCTION client action — the action service calls it and
 * it opens the new place with the same tab, carrying `pb_back` and `pb_focus`
 * along. Nothing is drawn, so nothing flashes.
 *
 * The new places are named by XMLID string, never imported: this module must
 * not depend on the hubs that took its boards (they depend on it, for
 * LIFECYCLE_GATE). A target that is not installed falls back to Journeys.
 *
 * `LIFECYCLE_GATE` and `LIFECYCLE_LENSES` stay exported: other modules still
 * gate on the lifecycle tiers, and an add-on written before NAV P2 that still
 * registers into the old registry must keep loading without an error.
 */
import { registry } from "@web/core/registry";
import { openHub } from "@pb_hub/js/hub_nav";

/** `pb.journeys._can_read()`'s tiers, verbatim. */
export const LIFECYCLE_GATE = [
    "pb_lifecycle.group_lifecycle_user",
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

/** The pre-NAV-P2 lens registry. Nothing is read from it any more. */
export const LIFECYCLE_LENSES = "pb_lifecycle_lenses";

/** Journeys on its own — where an old link with no tab, or `journeys`, lands. */
export const JOURNEYS_XMLID = "pb_lifecycle.action_pb_journeys";

/**
 * Old lens key → `{ xmlid, lens }` of its new home.
 *
 * Exported so the redirector's mapping can be read (and tested) without
 * driving the web client.
 */
export const LIFECYCLE_REDIRECTS = {
    hiring: { xmlid: "pb_hiring.action_pb_hiring_hub", lens: "overview" },
    newjoiners: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "newjoiners" },
    probation: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "probation" },
    exits: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "exits" },
    contracts: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "contracts" },
    pip: { xmlid: "pb_talent_hub.action_pb_talent_hub", lens: "pip" },
    journeys: { xmlid: JOURNEYS_XMLID, lens: "" },
};

/**
 * Where an arrival context sends the reader.
 *
 * @param {object} ctx  the old action's context (`pb_lens`, `pb_focus`, …)
 * @returns {{xmlid: string, lens: string}}
 */
export function lifecycleTarget(ctx = {}) {
    const asked = ctx.pb_lens || "";
    const hit = LIFECYCLE_REDIRECTS[asked];
    if (!hit) {
        return { xmlid: JOURNEYS_XMLID, lens: "" };
    }
    // RECRUIT P4's ⌘K row used to arrive on Hiring with `pb_focus: "bank"`;
    // the resume bank is its own rail item now.
    if (asked === "hiring" && ctx.pb_focus === "bank") {
        return { xmlid: hit.xmlid, lens: "bank" };
    }
    return hit;
}

/**
 * The redirector. A FUNCTION client action (Odoo 19 `_executeClientAction`
 * awaits it and draws nothing). Never throws past the action service: if the
 * new home is not installed on this database, Journeys opens instead.
 */
async function lifecycleRedirect(env, action) {
    const ctx = (action && action.context) || {};
    const target = lifecycleTarget(ctx);
    const passOn = {};
    for (const key of ["pb_role_id", "pb_back"]) {
        if (ctx[key]) { passOn[key] = ctx[key]; }
    }
    const focus = ctx.pb_focus && ctx.pb_focus !== "bank" ? ctx.pb_focus : undefined;
    const actionService = env.services.action;
    try {
        await openHub(actionService, {
            xmlid: target.xmlid, lens: target.lens || undefined, focus,
            context: passOn,
        });
    } catch (e) {
        if (target.xmlid === JOURNEYS_XMLID) { throw e; }
        console.warn("pb_lifecycle: the new home of this tab is not installed; "
                     + "opening Journeys", target.xmlid, e);
        await openHub(actionService, { xmlid: JOURNEYS_XMLID, context: passOn });
    }
}

registry.category("actions").add("pb_lifecycle_hub", lifecycleRedirect);
