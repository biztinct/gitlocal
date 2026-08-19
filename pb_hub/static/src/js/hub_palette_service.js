/** @odoo-module **/
/**
 * `pb_hub_palette` — the global ⌘K, and the rule that makes it global SAFELY.
 *
 * ================================ why a service ================================
 * The handover offered `main_components` or the `pb_sidebar` webclient patch. It
 * is neither, and the reason is W43: a floating panel that must paint above a
 * cockpit's `position: fixed; z-index: 1050` modal belongs in the OVERLAY
 * container, which is already a sibling of the whole action host. Once the
 * palette lives there, an always-mounted `main_components` root would exist only
 * to hold one boolean and one hotkey registration — and a service holds both
 * without rendering anything. `pb_mission` already opens its palette exactly this
 * way; this is the same mechanism with the host taken out.
 *
 * ============================== the yield rule ================================
 * Two surfaces already own ⌘K: Mission Control (its Workforce palette) and
 * Formula Studio (its Command Center; ⌘⇧K is that module's older text palette).
 * Both must keep it, with no second overlay behind theirs.
 *
 * Odoo's hotkey service dispatches a hotkey to exactly ONE registration —
 * `dispatch()` builds the candidate list newest-first (`registrations.values()`
 * reversed) and calls `candidates.shift()`. So the mechanism could have been
 * left implicit: this service starts before any component mounts, so it is the
 * OLDEST registration, and a component's `useHotkey("control+k")` is always
 * newer and always wins. That is true, and it is not written down anywhere near
 * the code that depends on it, which makes it a coincidence rather than a rule.
 *
 * So the yield is EXPLICIT as well: this registration carries an `isAvailable`
 * that returns false whenever any selector in the `pb_hub_palette_yield`
 * registry is on the page. A candidate that fails `isAvailable` is filtered out
 * before the winner is picked, so the local palette wins by DECLARATION and not
 * by mount order — and a future surface with its own ⌘K adds one line to that
 * registry instead of discovering this file.
 *
 * Note what it does NOT do: it never calls `preventDefault` itself and never
 * inspects `event.defaultPrevented`. The hotkey service owns that — it
 * `preventDefault`s only after a registration has been dispatched, and neither
 * existing palette sees the raw event at all.
 *
 * `bypassEditableProtection` is on, matching both existing palettes: ⌘K carries
 * its modifier, so it cannot be confused with typing, and a shortcut that only
 * works when no field is focused is a shortcut nobody learns. Without `global`,
 * the registration is bound to the default UI active element — so ⌘K is inert
 * while a modal owns the UI, which is the same answer Mission Control gives.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { HubPalette } from "@pb_hub/js/hub_palette";
import { openHub } from "@pb_hub/js/hub_nav";

/**
 * CSS selectors for surfaces that own ⌘K themselves. Seeded with the two that
 * do today; a third adds itself here rather than editing this file's logic.
 */
const yieldRegistry = registry.category("pb_hub_palette_yield");
// Mission Control's workspace root (`pb_mission.xml`: `<div class="pbim pbms">`)
yieldRegistry.add("pb_mission", ".pbms");
// Formula Studio's root (`studio.xml`: `<div class="pbfs">`); it owns ⌘K for the
// Command Center and ⌘⇧K for the older text palette.
yieldRegistry.add("pb_formula_studio", ".pbfs");

/** True when a surface that owns ⌘K is on screen. */
export function localPaletteOwnerOnScreen() {
    const selectors = yieldRegistry.getAll();
    if (!selectors.length) { return false; }
    return !!document.querySelector(selectors.join(", "));
}

export const hubPaletteService = {
    dependencies: ["overlay", "hotkey", "action", "notification", "orm", "dialog"],

    start(env, { overlay, hotkey, action: actionService, notification, orm, dialog }) {
        // The overlay's own remove(), while the palette is up; null when it is
        // not. Keeping the handle is what stops ⌘K opening a second panel on top
        // of the first (W43).
        let removeOverlay = null;
        // True between the ⌘K and the overlay actually being added. The first
        // open awaits a real `has_group` round trip, and two presses inside that
        // window would both pass the `removeOverlay` check and mount two panels.
        let opening = false;
        // group xmlid -> Promise<boolean>. `user.hasGroup` is itself cached, but
        // caching the promise means one palette open is one pass, not one pass
        // per entry that names the same group.
        const groupCache = new Map();

        function hasGroup(xmlid) {
            if (!groupCache.has(xmlid)) {
                // Fails OPEN: an xmlid that will not resolve means the module is
                // not installed, and its entry is dropped by the availability
                // check below anyway. Reading that as "denied" would hide a
                // surface for the wrong reason (pb_mission's precedent).
                groupCache.set(xmlid, user.hasGroup(xmlid).catch((e) => {
                    console.warn("pb_hub: could not resolve group", xmlid, e);
                    return true;
                }));
            }
            return groupCache.get(xmlid);
        }

        // ------------------------------------------------------ restrictions
        //
        // The rail can LOCK a door: `pb.sidebar.section.restricted` (and
        // `.item.restricted`, which only bites on a GATED item — W106) makes
        // `get_sidebar_data` serve the entry with a padlock, refuse the click
        // and answer with an upsell dialog. pb_demo uses it to fence off
        // configuration on demo databases.
        //
        // The palette bypassed all of that, because it never asked. After the
        // Cycle-5 cutover the lock lives on the SYSTEM section, whose one item
        // claims Formula Engine, Structures, Statutory and Integrations through
        // its match matrix — so a demo persona who could not open any of them
        // from the rail could open all four with ⌘K.
        //
        // So the palette asks the SAME server call the rail renders from and
        // builds a set of locked action refs out of it. Consequences worth
        // stating, because each is load-bearing:
        //
        //  * on a database where nothing is restricted the set is EMPTY and
        //    every code path below is a no-op — production behaviour is
        //    byte-identical, which is the requirement;
        //  * an administrator is never locked: `get_sidebar_data` computes
        //    `sec_locked = restricted AND NOT is_admin` server-side, so the set
        //    an admin receives is empty for the same reason the rail shows them
        //    no padlock. The palette does not re-decide that anywhere;
        //  * a LOCKED ITEM is served with its action refs nulled, so only its
        //    match_* claims can be harvested — which is right: the refs it no
        //    longer ships are refs the palette must not resolve either;
        //  * it FAILS OPEN. A database without pb_sidebar, or a call that
        //    errors, leaves the set empty and every row navigating. A palette
        //    that locked rows because a lookup failed would hide the product
        //    from the people who paid for it, which is a far worse failure than
        //    the one it is guarding against.
        //
        // Fetched once per palette open, not once per keystroke: the answer is
        // a property of the session, and the panel is already awaiting a
        // has_group round trip before it mounts.
        let lockedRefs = null;          // Map<ref, reason> | null (= not fetched)

        async function loadRestrictions() {
            const locked = new Map();
            try {
                const sections = await orm.call(
                    "pb.sidebar.item", "get_sidebar_data", []);
                for (const section of sections || []) {
                    const secReason = section.restricted
                        ? (section.restriction_reason || "") : "";
                    const walk = (item) => {
                        const reason = item.restricted
                            ? (item.restriction_reason || secReason) : secReason;
                        if (reason) {
                            for (const ref of [item.action_tag, item.action_xmlid,
                                               ...(item.match_action_tags || []),
                                               ...(item.match_action_xmlids || [])]) {
                                if (ref) { locked.set(ref, reason); }
                            }
                        }
                        for (const child of item.children || []) { walk(child); }
                    };
                    for (const item of section.items || []) { walk(item); }
                }
            } catch (e) {
                // W40: narrows nothing, hides nothing, and says so out loud.
                console.warn("pb_hub: palette could not read the rail's "
                             + "restrictions; every row stays open", e);
            }
            lockedRefs = locked;
            return locked;
        }

        /** The upsell text for this entry, or "" when it is not locked. */
        function restrictionFor(entry) {
            if (!lockedRefs || !lockedRefs.size) { return ""; }
            const a = entry.action || {};
            return lockedRefs.get(a.tag) || lockedRefs.get(a.xmlid) || "";
        }

        /**
         * Is the surface behind this entry actually on this database?
         *
         * A palette row that opens nothing is worse than no row (W29/W44). Every
         * entry that targets a CLIENT ACTION is checked against the actions
         * registry, which is the honest client-side answer: a module that is not
         * installed did not ship its JS, so its tag is simply not there. An
         * entry that targets an xmlid names a `requires` tag from the same module
         * to be probed the same way.
         */
        function isPresent(entry) {
            const actions = registry.category("actions");
            const a = entry.action || {};
            if (a.tag) { return actions.contains(a.tag); }
            if (entry.requires) { return actions.contains(entry.requires); }
            return true;
        }

        /** The rows this persona may see, in registry (sequence) order. */
        async function resolveEntries() {
            if (lockedRefs === null) { await loadRestrictions(); }
            const all = registry.category("pb_hub_palette").getAll()
                .filter(isPresent);
            const flags = await Promise.all(all.map(async (e) => {
                const groups = e.groups || [];
                if (!groups.length) { return true; }
                const answers = await Promise.all(groups.map(hasGroup));
                return answers.some(Boolean);
            }));
            return all.filter((_e, i) => flags[i]).map((e) => ({
                id: e.id,
                label: e.label,
                sublabel: e.sublabel || "",
                icon: e.icon || "chevron",
                // "" on every unrestricted database, which is every database
                // except a demo one — the row then renders exactly as before.
                restricted: restrictionFor(e),
                // Passed through UNCHANGED, including undefined: the palette
                // groups its rows into a Map keyed by this value, and `_t()`
                // returns a new String subclass every call — defaulting here to
                // a fresh "Surfaces" would give an entry that omitted `group`
                // its own heading, next to the shared one. The component owns
                // the default so there is exactly one of it.
                group: e.group,
            }));
        }

        function run(id) {
            const entry = registry.category("pb_hub_palette").getAll()
                .find((e) => e.id === id);
            if (!entry) { return; }
            const a = entry.action || {};
            // Restriction parity with the rail. The rail answers a click on a
            // locked door with an upsell dialog and no navigation
            // (`pb_sidebar.js::toggleSection` / `onItemClick`); the palette must
            // answer the same click the same way, or the lock is a decoration
            // on one surface and absent on the other — which is exactly the gap
            // Cycle 5 left when it moved pb_demo's lock up to the SYSTEM
            // section and the four Setup cockpits stayed reachable by ⌘K.
            const lock = restrictionFor(entry);
            if (lock) {
                dialog.add(AlertDialog, {
                    title: _t("Available in the full platform"),
                    body: lock,
                    confirmLabel: _t("Got it"),
                });
                return;
            }
            try {
                openHub(actionService, {
                    tag: a.tag, xmlid: a.xmlid, lens: a.lens, lensKey: a.lensKey,
                });
            } catch (e) {
                // W40: the catch narrows nothing and hides nothing. It reports,
                // and it leaves the palette's other rows working.
                console.warn("pb_hub: palette entry failed to open", id, e);
                notification.add(_t("%s could not be opened.", entry.label),
                                 { type: "danger" });
            }
        }

        async function open() {
            if (removeOverlay || opening) { return; }   // ⌘K is not a toggle
            opening = true;
            try {
                const entries = await resolveEntries();
                if (removeOverlay) { return; }
                removeOverlay = overlay.add(HubPalette, {
                    entries,
                    onRun: run,
                    onClose: close,
                }, {
                    onRemove: () => { removeOverlay = null; },
                });
            } finally {
                opening = false;
            }
        }

        function close() {
            if (removeOverlay) { removeOverlay(); }
            removeOverlay = null;
        }

        hotkey.add("control+k", () => open(), {
            bypassEditableProtection: true,
            isAvailable: () => !localPaletteOwnerOnScreen(),
        });

        return { open, close, get isOpen() { return !!removeOverlay; } };
    },
};

registry.category("services").add("pb_hub_palette", hubPaletteService);
