/** @odoo-module **/
/**
 * <HubShell/> — the workspace every Option-A mission is built from.
 *
 * This is `pb_mission`'s shell with Workforce taken out of it. The geometry, the
 * tokens and the interaction rules are lifted unchanged (a dark #241F52 command
 * bar, a 76px white lens rail of 60px buttons, a full-bleed canvas, an optional
 * 268px right dock) because the point of a kit is that the fifth hub looks like
 * the first one, not that it looks new.
 *
 * What the shell owns:
 *   1. the command bar — brand chip, an optional back chip, a `context` slot for
 *      the hub's own segments, the period tracker, the ⌘K launcher, an optional
 *      cog, the user;
 *   2. the lens rail, which lens is showing, and remembering it per hub;
 *   3. group gating: a lens this persona cannot use is ABSENT, not disabled — an
 *      offer the server would refuse is worse than no offer (W29);
 *   4. arrival routing (`pb_lens` / `pb_focus` / `pb_back`, see hub_nav.js);
 *   5. the canvas box, which is definite-height and creates NO stacking context,
 *      because an embedded cockpit's `position: fixed; z-index: 1050` modal must
 *      still resolve against the root (W20/W37).
 *
 * What it deliberately does NOT own: any data. The shell ships no model, no ACL,
 * no RPC — `user.hasGroup` is the only server round trip in the file, and it is
 * cached by the user service. Everything on screen is handed in by the hub.
 *
 * Binding non-goal for Cycle 1: `pb_mission` is NOT refactored onto this. It
 * keeps its own copy of the shape until a later cycle retires it.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { isMacOS } from "@web/core/browser/feature_detection";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, HUB_LENS_KEY } from "@pb_hub/js/hub_nav";
import { HubTracker } from "@pb_hub/js/hub_tracker";
import { featureGate, featuresState } from "@pb_hub/js/hub_features";
import { HubFeatureOff } from "@pb_hub/js/hub_feature_off";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

/**
 * `pbhub.<config.key>.lens.v1` — namespaced per hub, versioned per shape.
 *
 * Returns null for a hub that declared no key, and the shell then simply does
 * not remember its lens. The alternative — writing `pbhub.undefined.lens.v1` —
 * is worse than not persisting: two keyless hubs would silently share one slot
 * and each would open on the other's last lens.
 */
export function hubLensStorageKey(key) {
    return key ? `pbhub.${key}.lens.v1` : null;
}

export class HubShell extends Component {
    static template = "pb_hub.HubShell";
    static components = { HubBackChip, HubTracker, HubFeatureOff };
    static props = {
        /**
         * The hub's whole definition. ONE object, so a hub declares itself at
         * module level and the shell's props never change identity between
         * renders — a fresh literal per render would recreate every lens on
         * every keystroke elsewhere on the page (the refetch trap P1a fixed
         * twice, W21).
         *
         * {
         *   key:     "pay",                       // localStorage namespace
         *   brand:   { label, icon },
         *   feature?: "insights",                 // the whole hub is one part
         *                                         // of the product; a company
         *                                         // without it gets the "not
         *                                         // switched on" page instead
         *   lenses:  [ { key, icon, label,
         *                groups?: [xmlid],        // absent lens if not granted
         *                feature?: "bank_ocr",    // absent, or locked, if the
         *                                         // company has not got it
         *                Component?,              // omitted = placeholder lens
         *                props?: {},              // merged into the lens props
         *                wantsArrival?: true      // also receive `arrival`
         *              } ],
         *   dock?:    Component,                  // 268px right column
         *   tracker?: { label, stage, total, onClick? },
         *   cog?:     () => {},                   // renders the cog button
         *   defaultLens?: "run",                  // else the first allowed lens
         * }
         */
        config: { type: Object },
        // The client action that opened this hub. Optional and typed, so it is
        // passed as `{}` and never as `null` — a typed optional prop still
        // rejects null (W35).
        action: { type: Object, optional: true },
        slots: { type: Object, optional: true },
        "*": true,
    };

    setup() {
        this.actionService = useService("action");
        this.palette = useService("pb_hub_palette");
        this.dialogService = useService("dialog");

        // WHICH PARTS OF THE PRODUCT THIS COMPANY HAS, WATCHED RATHER THAN
        // READ. `useState` on the Platform Link's own reactive state means the
        // rail repaints on its own when the platform flips a switch — the
        // once-a-minute read that already exists brings the change in, and a
        // tile fades out without anybody reloading anything. Null on a
        // database with no Platform Link, and then everything is simply on.
        // The RETURN VALUE of `useState` is the subscription: a component is
        // registered by the reads it makes through the object it was handed
        // back, and a discarded `useState` watches nothing at all. So the proxy
        // is kept, and `gate()` touches it.
        const feats = featuresState(this.env);
        this._features = feats ? useState(feats) : null;

        // Read ONCE, in setup, from props. Never written back anywhere.
        this.arrival = this._arrival();

        this.state = useState({
            lens: this.arrival.lens || this._restoreLens(),
            // key -> boolean; null while unresolved, which the rail reads as
            // "show everything" so the shell never flashes an empty rail
            allowed: null,
        });

        // lensProps memo (see the getter). Module-level constants would be
        // shared between two hubs on one page; instance fields are not.
        this._propsFor = null;
        this._propsCache = null;
        this._emptyProps = {};

        onWillStart(async () => { await this._resolveAccess(); });
    }

    ic(n, s = 17) { return ic(n, s); }

    // --------------------------------------------------------------- config
    get config() { return this.props.config; }
    get brand() { return this.config.brand || { label: "", icon: "compass" }; }
    get tracker() { return this.config.tracker || null; }
    get back() { return this.arrival.back; }
    get hasCog() { return typeof this.config.cog === "function"; }

    // --------------------------------------------------------------- arrival
    /**
     * What the action that opened this hub asked for (hub_nav.js).
     *
     * `pb_focus` is carried but not acted on by the shell itself in C1: it means
     * "a pinned selection is a FILTER, not a panel to pop over what I was sent to
     * read" (W26), and C1's shell owns no person surface to pop. A lens that
     * wants it declares `wantsArrival` and receives the whole payload.
     */
    _arrival() {
        const ctx = (this.props.action && this.props.action.context) || {};
        const keys = (this.config.lenses || []).map((l) => l.key);
        const asked = ctx[HUB_LENS_KEY];
        const back = ctx.pb_back;
        return {
            lens: keys.includes(asked) ? asked : null,
            focus: ctx.pb_focus || "",
            // a back door with no destination is not a back door
            back: back && (back.tag || back.xmlid) ? back : null,
        };
    }

    _restoreLens() {
        const keys = (this.config.lenses || []).map((l) => l.key);
        const storageKey = hubLensStorageKey(this.config.key);
        try {
            const v = storageKey && window.localStorage.getItem(storageKey);
            if (keys.includes(v)) { return v; }
        } catch { /* private mode */ }
        if (keys.includes(this.config.defaultLens)) { return this.config.defaultLens; }
        return keys[0] || "";
    }

    // ---------------------------------------------------------------- access
    /**
     * Which lenses go on the rail.
     *
     * Same shape and same reasoning as `pb_mission._resolveAccess`: ask the
     * questions the retired rail items asked, so collapsing several doors into
     * one hub cannot advertise a surface whose facade would answer AccessError.
     *
     * Fails OPEN per group — an xmlid that will not resolve means the module is
     * not installed, and treating that as "denied" would hide a lens for the
     * wrong reason. Nothing here is a security boundary; every facade keeps its
     * own (W12).
     */
    async _resolveAccess() {
        const lenses = this.config.lenses || [];
        const names = [...new Set(lenses.flatMap((l) => l.groups || []))];
        const flags = {};
        await Promise.all(names.map(async (g) => {
            try { flags[g] = await user.hasGroup(g); }
            catch (e) {
                console.warn("pb_hub: could not resolve group", g, e);
                flags[g] = true;
            }
        }));
        const allowed = {};
        for (const l of lenses) {
            allowed[l.key] = !(l.groups || []).length
                || l.groups.some((g) => flags[g]);
        }
        this.state.allowed = allowed;
        // Never open on a lens this persona cannot read: a remembered lens or a
        // stale deep link would land them on an error state. A lens the company
        // has not bought counts too — a deep link to a surface that is not
        // switched on must land on the rail's first real lens, not on a padlock
        // somebody has to click their way out of.
        const usable = (l) => allowed[l.key] && this.gate(l.feature).shown
            && !this.gate(l.feature).locked;
        if (!usable({ key: this.state.lens, feature: this._featureOfLens(this.state.lens) })) {
            const first = lenses.find(usable);
            this.state.lens = first ? first.key : this.state.lens;
        }
    }

    // ------------------------------------------------ parts of the product
    //
    // A lens says which part of the product it belongs to; a whole hub may say
    // it too. Everything below asks the same one function, so "hidden" and
    // "shown locked" cannot be decided one way on the rail and another way on
    // the canvas.

    /** (shown, locked, text) for a feature key. Everything on when absent. */
    gate(key) {
        // One read, against the one value that moves when the platform flips a
        // switch — which is what makes a tile fade out inside a minute with
        // nobody reloading anything. Watching a map instead would repaint this
        // hub once a minute for ever, because the maps are replaced on every
        // read whether or not an answer changed.
        if (this._features) { void this._features.features_sig; }
        return featureGate(this.env, key);
    }

    _featureOfLens(key) {
        const def = (this.config.lenses || []).find((l) => l.key === key);
        return (def && def.feature) || "";
    }

    /** The whole hub, when the hub itself is one part of the product. */
    get hubGate() { return this.gate(this.config.feature); }

    /** True when this company simply has not got this hub. */
    get hubOff() {
        const g = this.hubGate;
        return !g.shown || g.locked;
    }

    /**
     * What the canvas says when somebody arrives at a hub their company has
     * not got — typed into the address bar, followed from a bookmark, or sent
     * a link by a colleague at another company.
     *
     * ZERO DEAD ENDS IS THE WHOLE REASON THIS EXISTS. Taking the entry off the
     * rail stops people FINDING the door; it does nothing about the people who
     * already know where it is. Without this they would get an empty workspace
     * or a stack trace; with it they get one sentence and a way back.
     */
    get hubOffText() {
        return this.hubGate.text
            || _t("This part of Payobook is not switched on for your company.");
    }

    // ---------------------------------------------------------------- lenses
    get lenses() {
        const allowed = this.state.allowed;
        return (this.config.lenses || [])
            .filter((l) => !allowed || allowed[l.key])
            // A lens the company has not got is ABSENT when the platform said
            // hide, and still on the rail with a padlock when it said lock.
            .filter((l) => this.gate(l.feature).shown);
    }

    /** True while this rail button should be drawn with a padlock. */
    isLocked(lens) { return this.gate(lens.feature).locked; }

    get lensDef() {
        return (this.config.lenses || []).find((l) => l.key === this.state.lens)
            || null;
    }

    /** The lens on screen is one this company has not got. */
    get lensLocked() {
        const def = this.lensDef;
        return !!def && this.gate(def.feature).locked;
    }

    get lensLockText() {
        const def = this.lensDef;
        return (def && this.gate(def.feature).text)
            || _t("This part of Payobook is not switched on for your company.");
    }

    /**
     * The padlock's own dialog: one sentence, one button, no dead end.
     * Deliberately the same shape the rail answers a locked entry with, so the
     * two surfaces feel like one product.
     */
    openLock(lens) {
        this.dialogService.add(AlertDialog, {
            title: _t("Not switched on for your company"),
            body: this.gate(lens.feature).text
                || _t("This part of Payobook is not switched on for your company."),
            confirmLabel: _t("Got it"),
        });
    }

    /**
     * The props the current lens is mounted with.
     *
     * `embedded: true` is the W17 contract: it suppresses only the chrome the
     * hub already owns (the cockpit's own hero, title and context bar), never
     * its logic and never its facade calls.
     *
     * `arrival` is opt-in (`wantsArrival`) because an unknown prop is a hard
     * validation error in dev mode — a lens receives the deep link only if it
     * has said it reads one.
     */
    get lensProps() {
        const def = this.lensDef;
        if (!def) { return this._emptyProps; }
        // Memoised per lens: a getter that returns a FRESH object on every
        // render makes OWL see the child's props as changed every time the
        // shell repaints, which re-runs the cockpit's onWillUpdateProps fetch
        // for nothing. Stable identity per lens is the same rule the LENSES
        // feature maps in pb_mission are written to.
        if (this._propsFor === def.key) { return this._propsCache; }
        const props = { embedded: true, ...(def.props || {}) };
        if (def.wantsArrival) {
            props.arrival = { lens: this.arrival.lens || "",
                              focus: this.arrival.focus };
        }
        this._propsFor = def.key;
        this._propsCache = props;
        return props;
    }

    setLens(key) {
        const keys = (this.config.lenses || []).map((l) => l.key);
        if (!keys.includes(key)) { return; }
        // A padlock is a door that says why, not a door that does nothing: the
        // click is answered with the sentence rather than swallowed. Checked
        // BEFORE the "already on this lens" test, so clicking the padlock
        // twice tells you twice.
        const def = (this.config.lenses || []).find((l) => l.key === key);
        if (def && this.gate(def.feature).locked) { this.openLock(def); return; }
        if (this.state.lens === key) { return; }
        if (this.state.allowed && !this.state.allowed[key]) { return; }
        this.state.lens = key;
        const storageKey = hubLensStorageKey(this.config.key);
        if (!storageKey) { return; }
        try {
            window.localStorage.setItem(storageKey, key);
        } catch { /* private mode */ }
    }

    // ------------------------------------------------------------ ⌘K palette
    /** "⌘K" on macOS, "Ctrl K" elsewhere — the label must match the key. */
    get paletteHint() { return isMacOS() ? "⌘K" : "Ctrl K"; }

    /**
     * The launcher opens the GLOBAL palette (the service), not a private one.
     * A hub with its own palette would be the thing the yield rule exists to
     * work around; the kit does not create that problem for itself.
     */
    openPalette() { this.palette.open(); }

    // ------------------------------------------------------------------ cog
    openCog() { if (this.hasCog) { this.config.cog(); } }

    // ------------------------------------------------------------------ user
    get userName() { return user.name || ""; }

    get userInitials() {
        return (this.userName || "U").split(" ").filter(Boolean)
            .map((p) => p[0]).join("").slice(0, 2).toUpperCase() || "U";
    }

    get emptyLensLabel() { return _t("This lens has no surface yet."); }
}
