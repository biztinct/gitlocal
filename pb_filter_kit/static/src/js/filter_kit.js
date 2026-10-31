/** @odoo-module **/
/**
 * The filter panel's browser half: one reactive model per list.
 *
 *     this.kit = useFilterKit({
 *         model: "pb.people",          // inherits pb.filter.mixin on the server
 *         onChange: (kit) => this.loadPage(kit),   // load the list for kit.query
 *     });
 *
 * and in the template wrap the list in <PbFilterLayout kit="kit">…</PbFilterLayout>.
 *
 * The model owns the filter state, the counts beside every value, the views
 * (built-in and saved), the panel's own state (open, pinned, folded sections)
 * and the link that reopens the list exactly as it is. The screen only loads
 * its rows for `kit.query` and drops a reply whose `seq` is no longer current.
 *
 * Remembered per person: whether the panel is open, what is pinned, which
 * sections are folded, the sort (browser storage). Remembered per browser
 * tab: the filters themselves, so going to a record and back keeps them.
 */
import { markRaw, markup, onWillStart, onWillUnmount, useExternalListener, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { IC } from "@pb_import_kit/js/import_icons";

const LIST_TYPES = new Set(["many2one", "selection", "char", "choice"]);
const NARROW = "(max-width: 900px)";
const URL_PARAM = "pbf";

// ------------------------------------------------------------------ icons
// A few glyphs the shared kit does not carry yet (Lucide, same stroke style).
const EXTRA = {
    panelLeft: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
    pin: '<path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>',
    arrowUpDown: '<path d="m21 16-4 4-4-4"/><path d="M17 20V4"/><path d="m3 8 4-4 4 4"/><path d="M7 4v16"/>',
    usersRound: '<path d="M18 21a8 8 0 0 0-16 0"/><circle cx="10" cy="8" r="5"/><path d="M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"/>',
    bookmark: '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
};
const ICON_CACHE = new Map();
/**
 * Cached markup: handing OWL the SAME object every render keeps it from
 * re-inserting the SVG on each patch (the PayAI mic flicker, 2026-10-16).
 */
export function pbfIcon(name, size = 16) {
    const key = name + ":" + size;
    let m = ICON_CACHE.get(key);
    if (!m) {
        const body = EXTRA[name] || IC[name] || IC.filter;
        m = markup(
            `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" ` +
            `stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`
        );
        ICON_CACHE.set(key, m);
    }
    return m;
}

// --------------------------------------------------------------- storage
function readJSON(kind, key) {
    try {
        const s = kind === "local" ? browser.localStorage : browser.sessionStorage;
        const raw = s && s.getItem(key);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}
function writeJSON(kind, key, value) {
    try {
        const s = kind === "local" ? browser.localStorage : browser.sessionStorage;
        if (s) {
            s.setItem(key, JSON.stringify(value));
        }
    } catch {
        // private window or full storage: the panel still works, it just forgets
    }
}

// --------------------------------------------------------------- filters
/** Canonical form: no empty sections, list values in a stable order. */
export function normFilters(filters) {
    const out = {};
    for (const key of Object.keys(filters || {}).sort()) {
        const v = filters[key];
        if (Array.isArray(v)) {
            if (v.length) {
                out[key] = [...v].sort((a, b) => String(a).localeCompare(String(b)));
            }
        } else if (v && typeof v === "object") {
            const o = {};
            for (const k of Object.keys(v).sort()) {
                if (v[k] !== null && v[k] !== undefined && v[k] !== "") {
                    o[k] = v[k];
                }
            }
            if (Object.keys(o).length) {
                out[key] = o;
            }
        }
    }
    return out;
}
export function sameFilters(a, b) {
    return JSON.stringify(normFilters(a)) === JSON.stringify(normFilters(b));
}
function clone(v) {
    return JSON.parse(JSON.stringify(v || {}));
}
function b64encode(obj) {
    const bytes = new TextEncoder().encode(JSON.stringify(obj));
    let bin = "";
    bytes.forEach((b) => (bin += String.fromCharCode(b)));
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function b64decode(str) {
    const bin = atob(str.replace(/-/g, "+").replace(/_/g, "/"));
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
}

const DATE_LABELS = () => ({
    this_month: _t("This month"),
    last_month: _t("Last month"),
    last_90: _t("Last 90 days"),
    this_year: _t("This year"),
    last_year: _t("Last year"),
    passed: _t("Already passed"),
    next_30: _t("Next 30 days"),
    next_90: _t("Next 90 days"),
    later: _t("Later than 90 days"),
});

export function fmtCount(n) {
    if (n === null || n === undefined) {
        return "";
    }
    return Number(n).toLocaleString("en-US");
}

// ================================================================= model
export class FilterKit {
    constructor({ orm, notification, model, onChange, noun, ctx, initial }) {
        // services stay raw: the model is reactive, they must not become so
        this.orm = markRaw(orm);
        this.notification = markRaw(notification);
        this.model = model;
        this.onChange = onChange;
        this.noun = noun || _t("records");
        // `ctx` rides on every call as context.pbf_ctx: a screen showing
        // several record types under one action picks its model/spec from it
        this.ctx = ctx || null;
        // `initial` = filters a door handed in (a link, "open this person's
        // row", a figure pressed elsewhere); it beats the URL and the tab memory
        this.initial = initial || null;
        this.refusal = "";

        this.loaded = false;
        this.failed = false;
        this.busy = false;
        this.screen = "";
        this.sections = [];
        this.groups = [];
        this.sorts = [];
        this.views = [];
        this.extra = {};
        this.total = 0;
        this.matched = null;

        this.filters = {};
        this.search = "";
        this.sort = "";
        this.viewKey = "";

        this.counts = {};
        this.labels = {};
        this.loadingKeys = {};
        this.seq = 0;

        this.ui = {
            panel: true,
            narrow: false,
            pinned: null,
            closed: {},
            find: "",
            findHits: {},
            showAll: {},
            mini: {},
            custom: {},
            flash: null,
        };
        this._timers = {};
    }

    // ------------------------------------------------------------ keys
    get _prefKey() {
        return `pbf:prefs:${this.screen}:${user.userId}`;
    }
    get _sessKey() {
        return `pbf:state:${this.screen}:${user.userId}`;
    }

    /** kwargs for a kit call, with the screen's ctx when it has one */
    _kw(extra = {}) {
        const kw = { ...extra };
        if (this.ctx) {
            kw.context = { pbf_ctx: this.ctx };
        }
        return kw;
    }

    // ----------------------------------------------------------- load
    async load() {
        let layout;
        try {
            layout = await this.orm.call(this.model, "pbf_layout", [], this._kw());
        } catch (e) {
            console.error("pb_filter_kit: the filter panel could not load", e);
            this.failed = true;
            this.loaded = true;
            if (this.onChange) {
                await this.onChange(this);
            }
            return;
        }
        if (layout && layout.refused) {
            // the screen shows its own refusal; the panel stays out of the way
            this.refusal = String(layout.refused);
            this.failed = true;
            this.loaded = true;
            if (this.onChange) {
                await this.onChange(this);
            }
            return;
        }
        this.screen = layout.screen;
        this.sections = layout.sections || [];
        this.groups = layout.groups || [];
        this.sorts = layout.sorts || [];
        this.views = layout.views || [];
        this.extra = layout.extra || {};
        this.total = layout.total || 0;

        const prefs = readJSON("local", this._prefKey) || {};
        this.ui.narrow = this._isNarrow();
        this.ui.panel = this.ui.narrow ? false : prefs.panel !== false;
        const known = new Set(this.sections.map((s) => s.key));
        this.ui.pinned = Array.isArray(prefs.pinned) ? prefs.pinned.filter((k) => known.has(k)) : null;
        this.ui.closed = prefs.closed && typeof prefs.closed === "object" ? prefs.closed : {};
        this.sort = this.sorts.some((s) => s.key === prefs.sort) ? prefs.sort : (this.sorts[0] || {}).key || "";

        const start = this.initial || this._readUrl() || readJSON("session", this._sessKey);
        this.initial = null;
        if (start && typeof start === "object") {
            this.filters = normFilters(start.filters || {});
            this.search = typeof start.search === "string" ? start.search : "";
            const v = this.views.find((x) => x.key === start.viewKey);
            this.viewKey = v ? v.key : "";
            this._matchView();
        } else if (this.views.length) {
            this.viewKey = this.views[0].key;
            this.filters = normFilters(this.views[0].filters);
            this.search = this.views[0].search || "";
        }
        this.loaded = true;
        await this.refresh();
    }

    _isNarrow() {
        try {
            return browser.matchMedia(NARROW).matches;
        } catch {
            return false;
        }
    }
    onResize() {
        const narrow = this._isNarrow();
        if (narrow !== this.ui.narrow) {
            this.ui.narrow = narrow;
            if (narrow) {
                this.ui.panel = false;
            }
        }
    }

    _readUrl() {
        try {
            const raw = new URLSearchParams(browser.location.search).get(URL_PARAM);
            if (!raw) {
                return null;
            }
            const data = b64decode(raw);
            return data && data.s === this.screen ? { filters: data.f, search: data.q, viewKey: data.v } : null;
        } catch {
            return null;
        }
    }

    // ------------------------------------------------------- refreshing
    /** What the screen should load right now. Hand `seq` back to isCurrent(). */
    get query() {
        return { filters: clone(this.filters), search: this.search, sort: this.sort, seq: this.seq };
    }
    isCurrent(seq) {
        return seq === this.seq;
    }

    _countKeys() {
        const keys = new Set(Object.keys(this.filters));
        for (const s of this.sections) {
            if (this.isOpen(s.key) && (s.shown || this.isActive(s.key))) {
                keys.add(s.key);
            }
        }
        return [...keys];
    }

    async refresh({ countsOnly = false } = {}) {
        const seq = ++this.seq;
        this.busy = true;
        const keys = this._countKeys();
        const tasks = [
            this.failed
                ? Promise.resolve(null)
                : this.orm.call(this.model, "pbf_counts", [], this._kw({
                      filters: this.filters,
                      search: this.search,
                      keys,
                  })),
        ];
        if (!countsOnly && this.onChange) {
            tasks.push(this.onChange(this));
        }
        try {
            const [res] = await Promise.all(tasks);
            if (seq !== this.seq || !res) {
                return;
            }
            // sections not recounted keep their numbers but are marked stale,
            // so opening one asks again
            const fresh = {};
            for (const [k, v] of Object.entries(this.counts)) {
                fresh[k] = keys.includes(k) ? v : { ...v, stale: true };
            }
            for (const [k, v] of Object.entries(res.sections || {})) {
                fresh[k] = v;
                this._remember(k, v);
            }
            this.counts = fresh;
            this.matched = res.matched;
        } catch (e) {
            if (seq === this.seq) {
                console.error("pb_filter_kit: refresh failed", e);
                this.notification.add(_t("The list could not be refreshed. Try again in a moment."), {
                    type: "warning",
                });
            }
        } finally {
            if (seq === this.seq) {
                this.busy = false;
            }
        }
    }

    async fetchSection(key) {
        if (this.failed || this.loadingKeys[key]) {
            return;
        }
        this.loadingKeys[key] = true;
        const seq = this.seq;
        try {
            const res = await this.orm.call(this.model, "pbf_counts", [], this._kw({
                filters: this.filters,
                search: this.search,
                keys: [key],
            }));
            if (seq === this.seq && res.sections && res.sections[key]) {
                this.counts = { ...this.counts, [key]: res.sections[key] };
                this._remember(key, res.sections[key]);
            }
        } catch (e) {
            console.error("pb_filter_kit: section counts failed", e);
        } finally {
            delete this.loadingKeys[key];
        }
    }

    _remember(key, payload) {
        const map = this.labels[key] || {};
        for (const row of payload.values || []) {
            map[String(row.v)] = row.label;
        }
        for (const row of payload.presets || []) {
            map["preset:" + row.v] = row.label;
        }
        this.labels[key] = map;
    }

    _schedule(delay = 140, opts = {}) {
        clearTimeout(this._timers.refresh);
        this._timers.refresh = setTimeout(() => this.refresh(opts), delay);
    }

    _changed({ delay = 140, keepView = false } = {}) {
        this.filters = normFilters(this.filters);
        if (!keepView) {
            this._matchView();
        }
        writeJSON("session", this._sessKey, {
            filters: this.filters,
            search: this.search,
            viewKey: this.viewKey,
        });
        this._schedule(delay);
    }

    /** If the filters now equal a view exactly, that view's tab lights up. */
    _matchView() {
        const cur = this.currentView;
        if (cur && sameFilters(cur.filters, this.filters) && (cur.search || "") === this.search) {
            return;
        }
        const hit = this.views.find((v) => sameFilters(v.filters, this.filters) && (v.search || "") === this.search);
        if (hit) {
            this.viewKey = hit.key;
        }
    }

    _savePrefs() {
        writeJSON("local", this._prefKey, {
            panel: this.ui.panel,
            pinned: this.ui.pinned,
            closed: this.ui.closed,
            sort: this.sort,
        });
    }

    // ------------------------------------------------------ the sections
    section(key) {
        return this.sections.find((s) => s.key === key);
    }
    get panelSections() {
        return this.sections.filter((s) => s.shown || this.isActive(s.key));
    }
    isActive(key) {
        const v = this.filters[key];
        return Array.isArray(v) ? v.length > 0 : !!(v && Object.keys(v).length);
    }
    values(key) {
        return Array.isArray(this.filters[key]) ? this.filters[key] : [];
    }
    isOn(key, value) {
        return this.values(key).some((v) => String(v) === String(value));
    }
    get activeCount() {
        return Object.keys(this.filters).filter((k) => this.isActive(k)).length;
    }
    isPinned(key) {
        if (this.ui.pinned) {
            return this.ui.pinned.includes(key);
        }
        const s = this.section(key);
        return !!(s && s.pinned);
    }
    isOpen(key) {
        if (this.ui.find.trim()) {
            return true;
        }
        if (key in this.ui.closed) {
            return !this.ui.closed[key];
        }
        return this.isPinned(key) || this.isActive(key);
    }

    toggle(key, value) {
        const cur = this.values(key);
        const on = cur.some((v) => String(v) === String(value));
        this.filters = { ...this.filters, [key]: on ? cur.filter((v) => String(v) !== String(value)) : [...cur, value] };
        this._changed();
    }
    only(key, value) {
        this.filters = { ...this.filters, [key]: [value] };
        this._changed();
    }
    setPreset(key, preset) {
        const cur = this.filters[key];
        const same = cur && cur.preset === preset;
        this.ui.custom = { ...this.ui.custom, [key]: false };
        this.filters = { ...this.filters, [key]: same ? {} : { preset } };
        this._changed();
    }
    setRange(key, from, to) {
        this.filters = { ...this.filters, [key]: { from: from || "", to: to || "" } };
        this._changed({ delay: 300 });
    }
    setNumber(key, min, max) {
        const num = (v) => (v === "" || v === null || v === undefined || isNaN(Number(v)) ? "" : Number(v));
        this.filters = { ...this.filters, [key]: { min: num(min), max: num(max) } };
        this._changed({ delay: 450 });
    }
    clear(key) {
        const next = { ...this.filters };
        delete next[key];
        this.filters = next;
        this.ui.custom = { ...this.ui.custom, [key]: false };
        this._changed();
    }
    clearAll() {
        this.filters = {};
        this.search = "";
        this.ui.custom = {};
        this._changed();
    }
    setSearch(q, now = false) {
        this.search = q || "";
        this._changed({ delay: now ? 0 : 260 });
    }
    setSort(key) {
        this.sort = key;
        this._savePrefs();
        this._schedule(0);
    }
    /** For figures that filter (the quiet numbers): press = exactly these
     * filters; press again = back to everyone. */
    isExactly(filters) {
        return !this.search && sameFilters(this.filters, filters);
    }
    toggleFilters(filters) {
        if (this.isExactly(filters) && Object.keys(normFilters(filters)).length) {
            this.useView(this.views.length ? this.views[0].key : "");
            if (!this.views.length) {
                this.clearAll();
            }
            return;
        }
        this.filters = normFilters(clone(filters));
        this.search = "";
        // a pressed figure is its own state: the tab lights only when a view
        // matches exactly, never the previously lit one with a dot (W2 K1)
        this.viewKey = "";
        this._changed();
    }

    /** Set the filters outright (a door, a link, a figure pressed elsewhere). */
    setFilters(filters, { search = "", viewKey = "" } = {}) {
        this.filters = normFilters(clone(filters || {}));
        this.search = search || "";
        this.viewKey = this.views.some((v) => v.key === viewKey) ? viewKey : "";
        this.ui.custom = {};
        this._changed();
    }
    /** Point the same panel at another record type (a tab switch on a screen
     * with several): everything resets and loads again. */
    async reconfigure({ model, ctx, noun, initial } = {}) {
        if (model) {
            this.model = model;
        }
        this.ctx = ctx === undefined ? this.ctx : ctx || null;
        if (noun) {
            this.noun = noun;
        }
        this.initial = initial || null;
        this.seq++;
        Object.assign(this, {
            loaded: false, failed: false, refusal: "", sections: [], views: [], sorts: [],
            filters: {}, search: "", viewKey: "", counts: {}, labels: {}, matched: null,
        });
        this.ui.find = "";
        this.ui.findHits = {};
        this.ui.showAll = {};
        this.ui.mini = {};
        this.ui.custom = {};
        await this.load();
    }

    // ------------------------------------------------------------ panel
    togglePanel(force) {
        this.ui.panel = typeof force === "boolean" ? force : !this.ui.panel;
        if (!this.ui.narrow) {
            this._savePrefs();
        }
        if (this.ui.panel) {
            this._fillOpenSections();
        }
    }
    toggleSection(key) {
        const open = this.isOpen(key);
        this.ui.closed = { ...this.ui.closed, [key]: open };
        this._savePrefs();
        if (!open) {
            this._fillSection(key);
        }
    }
    togglePin(key) {
        const base = this.ui.pinned || this.sections.filter((s) => s.pinned).map((s) => s.key);
        this.ui.pinned = base.includes(key) ? base.filter((k) => k !== key) : [...base, key];
        this._savePrefs();
    }
    showAll(key, on = true) {
        this.ui.showAll = { ...this.ui.showAll, [key]: on };
    }
    setMini(key, q) {
        this.ui.mini = { ...this.ui.mini, [key]: q };
    }
    setCustom(key, on) {
        this.ui.custom = { ...this.ui.custom, [key]: on };
    }
    _fillSection(key) {
        const c = this.counts[key];
        if (!c || c.stale) {
            this.fetchSection(key);
        }
    }
    _fillOpenSections() {
        for (const s of this.panelSections) {
            if (this.isOpen(s.key)) {
                this._fillSection(s.key);
            }
        }
    }
    /** A chip pressed: open the panel at its section and make it glow. */
    jumpTo(key) {
        this.ui.find = "";
        this.ui.closed = { ...this.ui.closed, [key]: false };
        this.togglePanel(true);
        this._fillSection(key);
        this.ui.flash = key;
        clearTimeout(this._timers.flash);
        this._timers.flash = setTimeout(() => {
            this.ui.flash = null;
        }, 1400);
    }

    // ------------------------------------------------------- find a filter
    setFind(q) {
        this.ui.find = q || "";
        clearTimeout(this._timers.find);
        const term = this.ui.find.trim().toLowerCase();
        if (!term) {
            this.ui.findHits = {};
            return;
        }
        this._timers.find = setTimeout(() => this._findOnServer(term), 260);
        this._fillOpenSections();
    }
    async _findOnServer(term) {
        // only the long sections hold more values than the panel was sent
        const long = this.panelSections.filter((s) => (this.counts[s.key] || {}).more);
        const hits = {};
        await Promise.all(
            long.map(async (s) => {
                try {
                    hits[s.key] = await this.orm.call(this.model, "pbf_find_values", [s.key, term], this._kw({
                        filters: this.filters,
                        search: this.search,
                    }));
                    this._remember(s.key, { values: hits[s.key] });
                } catch {
                    hits[s.key] = [];
                }
            })
        );
        if (this.ui.find.trim().toLowerCase() === term) {
            this.ui.findHits = hits;
        }
    }
    /** Rows a section shows, given the panel's find box and its own mini search. */
    rowsFor(key) {
        const s = this.section(key);
        const c = this.counts[key] || {};
        let rows = c.values || [];
        const term = (this.ui.find.trim() || "").toLowerCase();
        const mini = (this.ui.mini[key] || "").trim().toLowerCase();
        if (term && s && !s.label.toLowerCase().includes(term)) {
            const extra = (this.ui.findHits[key] || []).filter((h) => !rows.some((r) => String(r.v) === String(h.v)));
            rows = [...rows, ...extra].filter((r) => (r.label || "").toLowerCase().includes(term));
        }
        if (mini) {
            rows = rows.filter((r) => (r.label || "").toLowerCase().includes(mini));
        }
        return rows;
    }
    /** Does this section answer the find box (by its name or by a value)? */
    matchesFind(s) {
        const term = this.ui.find.trim().toLowerCase();
        if (!term) {
            return true;
        }
        if (s.label.toLowerCase().includes(term)) {
            return true;
        }
        if (LIST_TYPES.has(s.type)) {
            return this.rowsFor(s.key).length > 0;
        }
        if (s.type === "date") {
            return ((this.counts[s.key] || {}).presets || []).some((p) => (p.label || "").toLowerCase().includes(term));
        }
        return false;
    }
    /** Enter in the find box ticks the first value it found. */
    pickFirstFound() {
        for (const s of this.panelSections) {
            if (!LIST_TYPES.has(s.type) || s.label.toLowerCase().includes(this.ui.find.trim().toLowerCase())) {
                continue;
            }
            const row = this.rowsFor(s.key)[0];
            if (row) {
                this.toggle(s.key, row.v);
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------ chips
    summary(key) {
        const s = this.section(key);
        const v = this.filters[key];
        if (!s || v === undefined) {
            return "";
        }
        const map = this.labels[key] || {};
        if (Array.isArray(v)) {
            const names = v.map((x) => map[String(x)] || (x === false ? s.none_label || _t("Not set") : String(x)));
            return names.length <= 2 ? names.join(", ") : `${names.slice(0, 2).join(", ")} +${names.length - 2}`;
        }
        if (s.type === "date") {
            if (v.preset) {
                return map["preset:" + v.preset] || (v.preset === "none" ? s.none_label : DATE_LABELS()[v.preset]) || v.preset;
            }
            const d = (iso) => {
                try {
                    return luxon.DateTime.fromISO(iso).toFormat("d LLL yyyy");
                } catch {
                    return iso;
                }
            };
            if (v.from && v.to) {
                return `${d(v.from)} – ${d(v.to)}`;
            }
            return v.from ? _t("From %s", d(v.from)) : _t("Until %s", d(v.to));
        }
        if (s.type === "number") {
            const f = (n) => this.fmtNumber(n, s.unit);
            if (v.min !== undefined && v.max !== undefined) {
                return `${f(v.min)} – ${f(v.max)}`;
            }
            return v.min !== undefined ? _t("%s or more", f(v.min)) : _t("Up to %s", f(v.max));
        }
        return "";
    }
    get chips() {
        return this.sections
            .filter((s) => this.isActive(s.key))
            .map((s) => ({ key: s.key, label: s.label, icon: s.icon, text: this.summary(s.key) }));
    }
    fmtNumber(n, unit) {
        if (n === null || n === undefined || n === "") {
            return "";
        }
        const v = Number(n);
        if (unit === "money") {
            const cur = this.extra.currency || "";
            const a = Math.abs(v);
            if (a >= 1e9) {
                return cur + (v / 1e9).toFixed(1).replace(/\.0$/, "") + "B";
            }
            if (a >= 1e6) {
                return cur + (v / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
            }
            if (a >= 1e4) {
                return cur + Math.round(v / 1e3) + "K";
            }
            return cur + Math.round(v).toLocaleString("en-US");
        }
        return v.toLocaleString("en-US");
    }

    // ------------------------------------------------------------ views
    get currentView() {
        return this.views.find((v) => v.key === this.viewKey) || null;
    }
    get dirty() {
        const v = this.currentView;
        if (!v) {
            return this.activeCount > 0 || !!this.search;
        }
        return !sameFilters(v.filters, this.filters) || (v.search || "") !== this.search;
    }
    useView(key) {
        const v = this.views.find((x) => x.key === key);
        if (!v) {
            return;
        }
        this.viewKey = key;
        this.filters = normFilters(clone(v.filters));
        this.search = v.search || "";
        this.ui.custom = {};
        this._changed({ delay: 0, keepView: true });
    }
    resetView() {
        if (this.currentView) {
            this.useView(this.viewKey);
        } else {
            this.clearAll();
        }
    }
    async saveView(name, shared) {
        try {
            const p = await this.orm.call("pb.filter.view", "pbf_save", [this.screen, name], {
                filters: this.filters,
                search: this.search,
                shared: !!shared,
            });
            p.n = this.matched;
            this.views = [...this.views, p];
            this.viewKey = p.key;
            this._changed({ delay: 0, keepView: true });
            this.notification.add(
                shared ? _t("View saved and shared with everyone.") : _t("View saved. Only you can see it."),
                { type: "success" }
            );
            return true;
        } catch (e) {
            this._fail(e, _t("The view could not be saved."));
            return false;
        }
    }
    async updateView() {
        const v = this.currentView;
        if (!v || !v.mine) {
            return;
        }
        try {
            const p = await this.orm.call("pb.filter.view", "pbf_update", [[v.id], { filters: this.filters, search: this.search }]);
            this._replaceView({ ...p, n: this.matched });
            this.notification.add(_t("Changes saved to “%s”.", p.label), { type: "success" });
        } catch (e) {
            this._fail(e, _t("The changes could not be saved."));
        }
    }
    async renameView(key, name) {
        const v = this.views.find((x) => x.key === key);
        if (!v || !v.mine) {
            return false;
        }
        try {
            const p = await this.orm.call("pb.filter.view", "pbf_update", [[v.id], { name }]);
            this._replaceView({ ...p, n: v.n });
            return true;
        } catch (e) {
            this._fail(e, _t("The view could not be renamed."));
            return false;
        }
    }
    async shareView(key, shared) {
        const v = this.views.find((x) => x.key === key);
        if (!v || !v.mine) {
            return;
        }
        try {
            const p = await this.orm.call("pb.filter.view", "pbf_update", [[v.id], { shared: !!shared }]);
            this._replaceView({ ...p, n: v.n });
            this.notification.add(
                shared ? _t("Everyone who uses this list can now see “%s”.", p.label) : _t("“%s” is private again.", p.label),
                { type: "success" }
            );
        } catch (e) {
            this._fail(e, _t("Sharing could not be changed."));
        }
    }
    async deleteView(key) {
        const v = this.views.find((x) => x.key === key);
        if (!v || !v.mine) {
            return;
        }
        try {
            await this.orm.call("pb.filter.view", "pbf_delete", [[v.id]]);
            this.views = this.views.filter((x) => x.key !== key);
            if (this.viewKey === key) {
                this.viewKey = "";
                this._matchView();
            }
            this.notification.add(_t("View “%s” deleted.", v.label), { type: "success" });
        } catch (e) {
            this._fail(e, _t("The view could not be deleted."));
        }
    }
    _replaceView(p) {
        this.views = this.views.map((x) => (x.key === p.key ? p : x));
    }
    _fail(e, message) {
        console.error("pb_filter_kit:", e);
        const detail = e && e.data && e.data.message;
        this.notification.add(detail || message, { type: "danger" });
    }

    // ------------------------------------------------------------- link
    get link() {
        const url = new URL(browser.location.href);
        url.searchParams.set(
            URL_PARAM,
            b64encode({ s: this.screen, f: this.filters, q: this.search, v: this.viewKey })
        );
        return url.toString();
    }
    async copyLink() {
        const link = this.link;
        try {
            await browser.navigator.clipboard.writeText(link);
            this.notification.add(_t("Link copied. Anyone who opens it sees this list filtered the same way."), {
                type: "success",
            });
        } catch {
            this.notification.add(link, { title: _t("Copy this link"), type: "info", sticky: true });
        }
    }

    destroy() {
        for (const t of Object.values(this._timers)) {
            clearTimeout(t);
        }
    }
}

/**
 * Hook: build, load and tidy up one FilterKit for this component.
 * @param {{model: string, onChange: (kit: FilterKit) => Promise, noun?: string}} opts
 */
export function useFilterKit(opts) {
    const orm = useService("orm");
    const notification = useService("notification");
    const kit = useState(new FilterKit({ orm, notification, ...opts }));
    onWillStart(() => kit.load());
    useExternalListener(window, "resize", () => kit.onResize());
    onWillUnmount(() => kit.destroy());
    return kit;
}
