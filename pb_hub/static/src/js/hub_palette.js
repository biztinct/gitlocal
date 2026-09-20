/** @odoo-module **/
/**
 * <HubPalette/> — the product-wide ⌘K.
 *
 * Cloned from `pb_wf_kit`'s `<WfCommandPalette/>` (same metrics, same keyboard
 * contract, `.pbhub-pal-*` class names) with one difference of substance: the
 * Workforce palette searches PEOPLE as well, because it lives inside a workspace
 * that has a person surface to open them in. This one navigates. Its rows are
 * SURFACES, and it is handed them already resolved and already gated — the
 * component knows nothing about groups, tags or registries (W6: the kit renders
 * and calls back).
 *
 * It is mounted through the Odoo OVERLAY service by `pb_hub_palette`, which puts
 * it in `.o-overlay-container`, a sibling of the whole action host. That is
 * W43's "win by LOCATION, not by z-index": the palette has to paint above a
 * cockpit's `position: fixed; z-index: 1050` modal, and doing that from inside a
 * workspace would mean stacking shell chrome above 1050 — exactly the fight W37
 * exists to prevent. The consequence is that its markup renders OUTSIDE every
 * `.pbim` root, so every `--pbim-*` here resolves to its FALLBACK; the SCSS is
 * written with the correct hexes for that reason (W14).
 */
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** Keyboard-first means a short list: past ~12 rows the arrow keys stop paying. */
export const MAX_ROWS = 12;
const RECENTS_KEY = "pbhub.palette.recents.v1";
const RECENTS_MAX = 4;

// Shared, not per-call: `_t()` returns a NEW String subclass every time, and
// the grouped render keys a Map by this value — a fresh object per row would
// render one heading per row.
const GROUP_RECENT = _t("Recent");
/**
 * The heading an entry gets when it names none, EXPORTED so that it is the only
 * "Surfaces" in the product.
 *
 * `hub_palette_entries.js` re-exports it as `G_SURFACES`, which is what the seed
 * rows carry. Before Cycle 5 the two were separate `_t("Surfaces")` calls, and
 * `_t()` returns a NEW String subclass every time: the grouped render keys a Map
 * by this value, so a row that named the shared constant and a row that fell
 * through to this default landed in two buckets and the palette drew the word
 * SURFACES twice. Invisible while every hub row sorted to the bottom; visible
 * the moment Cycle 5's promotion interleaved them with the seed rows.
 */
export const GROUP_DEFAULT = _t("Surfaces");

export class HubPalette extends Component {
    static template = "pb_hub.HubPalette";
    static props = {
        // [{ id, label, sublabel?, icon, group, restricted }] — already gated
        // by the service. `restricted` is the UPSELL TEXT when the rail shows
        // this door with a padlock, and "" otherwise; the row renders a lock
        // and the service answers the click with a dialog rather than a
        // navigation. It is "" on every database where nothing is restricted,
        // which is every database except a demo one.
        entries: { type: Array },
        onRun: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.state = useState({
            q: "",
            active: 0,
            recents: this._loadRecents(),
        });
        this.inputRef = useRef("input");
        onMounted(() => { if (this.inputRef.el) { this.inputRef.el.focus(); } });
    }

    ic(n, s = 14) { return ic(n, s); }

    // ------------------------------------------------------------- the rows
    /**
     * ONE flat, ordered list is the single source of truth for BOTH the keyboard
     * index and the grouped render. Sorting the render separately from the index
     * is how a highlight starts jumping between sections (the failure the wf
     * palette's `groups` getter was written to avoid).
     */
    get rows() {
        const q = this.state.q.trim().toLowerCase();
        const byId = new Map(this.props.entries.map((e) => [e.id, e]));
        const out = [];
        const seen = new Set();

        // Recents lead the empty state — the palette's job on open is to be
        // faster than the rail, and what you did last is the best guess there is.
        if (!q) {
            for (const id of this.state.recents) {
                const e = byId.get(id);
                // an entry this persona lost access to must not come back
                // through the recents list
                if (e && !seen.has(e.id)) {
                    out.push({ ...e, group: GROUP_RECENT });
                    seen.add(e.id);
                }
            }
        }

        for (const e of this.props.entries) {
            if (seen.has(e.id)) { continue; }
            if (q && !this._matches(e, q)) { continue; }
            out.push(e);
            if (out.length >= MAX_ROWS) { break; }
        }
        return out.slice(0, MAX_ROWS);
    }

    /**
     * Substring over label + sublabel, both folded to lower case.
     *
     * Deliberately not fuzzy: these labels are the SAME words that are on the
     * rail, so a user types what they can see. A fuzzy matcher's job is to
     * forgive typing errors in names you cannot see, and it buys that at the
     * price of surprising rankings.
     */
    _matches(entry, q) {
        return `${entry.label} ${entry.sublabel || ""}`.toLowerCase().includes(q);
    }

    /** The same rows, grouped for rendering, each carrying its FLAT index. */
    get groups() {
        const map = new Map();
        this.rows.forEach((row, idx) => {
            const name = row.group || GROUP_DEFAULT;
            if (!map.has(name)) { map.set(name, []); }
            map.get(name).push({ row, idx });
        });
        return [...map.entries()].map(([name, items]) => ({ name, items }));
    }

    get count() { return this.rows.length; }

    // ------------------------------------------------------------- keyboard
    onInput(ev) {
        this.state.q = ev.target.value;
        this.state.active = 0;
    }

    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.onClose();
            return;
        }
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this.state.active = this.count ? (this.state.active + 1) % this.count : 0;
            return;
        }
        if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this.state.active = this.count
                ? (this.state.active - 1 + this.count) % this.count : 0;
            return;
        }
        if (ev.key === "Enter") {
            ev.preventDefault();
            const row = this.rows[this.state.active];
            if (row) { this.run(row); }
        }
    }

    setActive(idx) { this.state.active = idx; }

    // ------------------------------------------------------------ execution
    /**
     * Every outcome closes the palette, and every outcome is a CLICK (or an
     * Enter, which is the same event chain). Nothing here runs from a lifecycle
     * hook — the palette's only lifecycle work is focusing its input (W21).
     */
    run(row) {
        this._remember(row.id);
        this.props.onRun(row.id);
        this.props.onClose();
    }

    // -------------------------------------------------------------- recents
    _loadRecents() {
        try {
            const raw = window.localStorage.getItem(RECENTS_KEY);
            const v = raw ? JSON.parse(raw) : null;
            return Array.isArray(v) ? v.slice(0, RECENTS_MAX) : [];
        } catch { return []; }
    }

    _remember(id) {
        const next = [id, ...this.state.recents.filter((x) => x !== id)]
            .slice(0, RECENTS_MAX);
        this.state.recents = next;
        try {
            window.localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
        } catch { /* private mode */ }
    }
}
