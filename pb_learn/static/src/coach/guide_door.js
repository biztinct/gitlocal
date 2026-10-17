/** @odoo-module **/
/* =============================================================================
   LEARNREV P3 — the drawer's door for surfaces that are not the drawer.

   The Library (journey.js) and the ⌘K field rows (learn_palette.js) need to
   say "open this screen with its Guide docked, This screen open" or "ask PayAI
   this". They cannot import coach.js (it imports them), and the drawer is the
   one component that survives the navigation an open does — so the drawer
   registers itself here on mount and these surfaces call through.

   `guideAt(screenKey, {section, field})` resolves to what happened:
   "here" (the screen opened and the Guide is showing), "unreachable" (this
   person cannot open that screen: the caller shows its outline instead),
   "elsewhere" (the hub moved them off that tab), "missing" (no such screen)
   or "nodrawer" (no drawer mounted: nothing was opened).
   ========================================================================== */
export const helperDoor = { guideAt: null, ask: null };

export function guideAt(screenKey, opts = {}) {
    if (typeof helperDoor.guideAt !== "function") {
        return Promise.resolve("nodrawer");
    }
    return Promise.resolve(helperDoor.guideAt(screenKey, opts)).catch(() => "missing");
}

/** Open the drawer with `text` in the composer (never sent). */
export function askHelper(text) {
    if (typeof helperDoor.ask !== "function") {
        return false;
    }
    helperDoor.ask(String(text || ""));
    return true;
}
