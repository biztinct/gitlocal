/** @odoo-module **/
/**
 * "Where am I" — the hub and lens on screen, published for anyone to read.
 *
 * LEARN REFRESH step 1. Since the rail cutover every working screen is a LENS
 * inside a hub, and the action manager only knows the HUB: inside Pay Run the
 * current action is `pb_pay_hub` whether the learner is reading Payslips or
 * Deliver. Everything that needs to know which screen is showing — the helper,
 * Ask Payobook, a walkthrough checking it landed — reads this store instead of
 * guessing from the action.
 *
 * ONE STORE, SEVERAL WRITERS, ONE OWNER AT A TIME.
 *   HubShell and pb_mission's own shell publish the hub and lens they show
 *   (and pb_settings its category). A publish takes ownership; a clear only
 *   succeeds for the owner that published — an action switch mounts the next
 *   hub BEFORE the previous one unmounts, and the old hub's clear must not
 *   wipe what the new one has just said.
 *
 * Plain data only (no recordsets, no components): readers render it and send
 * parts of it over RPC. `lenses` is what the SHELL shows this person, already
 * filtered by the shell's own groups/probe/feature gates, so a reader that
 * lists tabs never has to re-derive who may see what (reuse, don't copy).
 *
 * Nothing here changes what a hub shows or does. The only behaviour offered
 * back is `switchLens`, which calls the owning shell's own lens switch — the
 * same function its rail buttons call.
 */
import { reactive } from "@odoo/owl";

const EMPTY = {
    tag: "",        // the hub's client action tag, e.g. "pb_pay_hub"
    hubKey: "",     // the shell's config key, e.g. "pay"
    hubLabel: "",   // the hub's brand label as the rail shows it
    lens: "",       // the lens (tab) on screen
    lenses: [],     // [{key, label, icon, locked}] the tabs this person sees
    ready: false,   // true once the shell has resolved who may see what
};

export const hubPlace = reactive({
    ...EMPTY,
    // "<tag>:<lens>" -> inner tab key, for a lens that has its own tabs
    // (Pay Run › Adjust › Retro / Proration). Kept per lens so a sub-tab set
    // while the lens mounts survives the shell publishing the lens after it.
    subs: {},
    // An open detail panel that is its own screen to a learner (the contract
    // drawer), or "" — independent of hubs, it can open on any page.
    detail: "",
    // Bumped whenever a NEW shell takes the place over, so a reader that just
    // navigated can tell "the hub I opened has spoken" from "the hub I left
    // has not cleared yet".
    seq: 0,
});

let owner = null;
let switcher = null;
let detailToken = null;

/**
 * Say which hub and lens are on screen. Idempotent; call it whenever the lens,
 * the visible lens list or the access answer changes.
 *
 * @param {object} token   the publishing component (identity only)
 * @param {object} place   {tag, hubKey, hubLabel, lens, lenses, ready, switchTo}
 */
export function publishPlace(token, place) {
    if (!token || !place || !place.tag) {
        return;
    }
    if (owner !== token) {
        hubPlace.subs = {};
        hubPlace.seq += 1;
    }
    owner = token;
    switcher = typeof place.switchTo === "function" ? place.switchTo : null;
    const lenses = (place.lenses || []).map((l) => ({
        key: String(l.key || ""),
        label: String(l.label || l.key || ""),
        icon: String(l.icon || ""),
        locked: !!l.locked,
    }));
    Object.assign(hubPlace, {
        tag: String(place.tag),
        hubKey: String(place.hubKey || ""),
        hubLabel: String(place.hubLabel || ""),
        lens: String(place.lens || ""),
        lenses,
        ready: !!place.ready,
    });
}

/** Forget the place — only if `token` is still the one that published it. */
export function clearPlace(token) {
    if (!token || owner !== token) {
        return;
    }
    owner = null;
    switcher = null;
    Object.assign(hubPlace, { ...EMPTY, lenses: [] });
    hubPlace.subs = {};
}

/** A lens with inner tabs says which one is showing. */
export function setPlaceSub(tag, lens, sub) {
    if (!tag || !lens) {
        return;
    }
    const key = `${tag}:${lens}`;
    if ((hubPlace.subs[key] || "") === (sub || "")) {
        return;
    }
    hubPlace.subs = { ...hubPlace.subs, [key]: sub || "" };
}

/** The inner tab of the lens on screen, or "". */
export function placeSub() {
    return hubPlace.subs[`${hubPlace.tag}:${hubPlace.lens}`] || "";
}

/**
 * A detail panel that is a screen of its own opened; returns the release.
 * Releasing twice, or after another panel took over, does nothing.
 */
export function holdDetail(name) {
    const token = {};
    detailToken = token;
    hubPlace.detail = String(name || "");
    return () => {
        if (detailToken === token) {
            detailToken = null;
            hubPlace.detail = "";
        }
    };
}

/**
 * Ask the shell on screen to show another of its lenses. Returns false when no
 * shell is listening or the lens is not one this person can see — the caller
 * then says so rather than pretending it moved.
 */
export function switchLens(key) {
    if (!switcher || !hubPlace.lenses.some((l) => l.key === key)) {
        return false;
    }
    try {
        switcher(key);
    } catch (e) {
        console.warn("pb_hub: could not switch lens", key, e);
        return false;
    }
    return true;
}
