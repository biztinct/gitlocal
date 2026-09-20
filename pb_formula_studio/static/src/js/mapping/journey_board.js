/** @odoo-module **/
/**
 * JOURNEY J5, redesigned by CLEANMAP P2 — the Journey. Only what is mapped,
 * and every card opens.
 *
 *   Files & systems ──▶ Feeds ──▶ Transformations ──▶ Scheme ◀──▶ Payobook Source
 *
 * The programme's showpiece and the owner's original ask: open Mapping and see
 * the whole story of where pay values come from, in one picture, with the
 * problems glowing.
 *
 * Four things it is, and one it is not.
 *
 *   * it is REAL, and now it is ONLY real. Every card on it is the end of a
 *     LINK — a field-level statement this scheme makes about where one
 *     component reads. A connected system nothing here reads has no card at
 *     all, where v1 drew every connector on the database (ledger CM4);
 *   * it OPENS. Clicking a card's body shows the fields inside it and clicking
 *     again closes it, in any mix. The lines follow: two closed cards are one
 *     counted line, an open card beside a closed one gathers its rows onto the
 *     closed card's edge, two open cards draw row to row. There is no
 *     "Details" button and no expand-all — the owner withdrew both;
 *   * it is NAVIGATION, through the small corner icon and nothing else. The
 *     card body toggles and never navigates, which is the whole of the owner's
 *     ruling 5 and 6;
 *   * it is READ-ONLY. There is no gesture on this board that writes. Not one.
 *     Opening a card is client state, remembered in this browser.
 *
 * What it is NOT is analytics. `pb_explorer` owns that.
 *
 * ---------------------------------------------------------------------------
 * The geometry is `mapping_geometry.js` unforked — `wireGeometry` and `clampY`
 * are arithmetic over points and do not care how many columns exist. What
 * changed with P2 is WHAT is measured: `_measure` walks `[data-id]` rather than
 * `body.children`, because a row is two levels down inside its card now, and a
 * line's X always comes from the CARD's rect so every row line leaves the
 * card's border rather than the middle of its text.
 *
 * MJ19 — every string here is ONE literal or is joined with an explicit `+`. A
 * two-line JS string with no operator is idiomatic Python, a SyntaxError in
 * JavaScript, and it takes the whole backend bundle down with a blank page.
 */
import { Component, useState, useRef, onMounted, onWillUnmount, onPatched,
         onWillUpdateProps, useExternalListener } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { wireGeometry, clampY, spreadHubs } from "./mapping_geometry";
import { srcLabel } from "../source_vocab";

/** Pixels of a lane's band reserved so a clamped wire is not flush to the edge. */
const BAND = 10;

/** How long the open/close reveal runs, and how long wires keep re-measuring. */
const REVEAL_MS = 180;

/**
 * The lanes, left to right. `id` is the payload key; the order IS the story,
 * and a lane whose payload list is empty is not drawn at all — it takes no
 * grid column, so the board re-balances instead of leaving a hole (ruling 9).
 */
export const LANES = [
    { id: "systems", icon: "server", label: _t("Files & systems") },
    { id: "feeds", icon: "database", label: _t("Feeds") },
    { id: "transforms", icon: "sigma", label: _t("Transformations") },
    { id: "scheme", icon: "calculator", label: _t("Scheme") },
    { id: "source", icon: "users", label: _t("Payobook Source") },
];

export class JourneyBoard extends Component {
    static template = "pb_formula_studio.JourneyBoard";
    static props = {
        data: { type: Object },
        busy: { type: Boolean, optional: true },
        onOpenDoor: { type: Function },
    };

    setup() {
        this.action = useService("action");
        this.ui = useState({
            q: "",
            hover: "",          // the row or card the pointer/keyboard is on
            pin: "",            // a trace the reader clicked to keep
            open: {},           // card id -> true. An object, for reactivity.
            folded: false,      // the scheme card's "calculated or fixed" line
            geom: [],           // the drawn edges
        });
        this.rootRef = useRef("stage");
        this.qRef = useRef("q");
        this.laneRefs = {};
        for (const lane of LANES) { this.laneRefs[lane.id] = useRef(lane.id); }
        this._raf = null;
        this._until = 0;
        this._recomputes = 0;
        this._index = null;
        this._indexFor = null;
        onMounted(() => {
            this.ui.open = this._loadOpen();
            this._recompute();
            this._ro = new ResizeObserver(() => this._schedule());
            const els = [this.rootRef.el].concat(
                LANES.map((l) => this.laneRefs[l.id].el));
            for (const el of els) { if (el) { this._ro.observe(el); } }
        });
        onWillUnmount(() => {
            if (this._ro) { this._ro.disconnect(); this._ro = null; }
            if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
        });
        onWillUpdateProps((next) => {
            // A different scheme is a different Journey — and a different set
            // of open cards. A trace resolved against the old one points at
            // rows that stop existing this frame (CR9's family).
            if (next.data !== this.props.data) {
                this.ui.hover = "";
                this.ui.pin = "";
                this.ui.folded = false;
                const before = (this.props.data || {}).config || {};
                const after = (next.data || {}).config || {};
                if (before.id !== after.id) {
                    this.ui.open = this._loadOpen(after.id || 0);
                }
            }
        });
        onPatched(() => this._schedule());
        useExternalListener(window, "resize", () => this._schedule());
    }

    ic(n, s = 14) { return ic(n, s); }

    // ==================================================================== data
    get d() { return this.props.data || {}; }
    get counts() { return this.d.counts || {}; }
    get configId() { return (this.d.config || {}).id || 0; }
    get invite() { return this.d.invite || null; }

    /** Only the lanes that have something to say. The Scheme is always one. */
    get lanes() {
        const src = this.d.lanes || {};
        return LANES.filter((l) => (src[l.id] || []).length);
    }

    cardsFor(laneId) { return (this.d.lanes || {})[laneId] || []; }

    /**
     * Rows, cards and neighbours, indexed once per payload.
     *
     * Rebuilt only when `props.data` is a different object, because every
     * hover recomputes a trace out of it and a fresh Map per pointer move on a
     * forty-row board is the sort of cost that only shows up on the owner's
     * laptop.
     */
    get index() {
        if (this._indexFor === this.d && this._index) { return this._index; }
        const rows = new Map();
        const cardOf = new Map();
        const byCard = new Map();
        for (const lane of LANES) {
            for (const c of this.cardsFor(lane.id)) {
                byCard.set(c.id, c);
                for (const r of (c.rows || [])) {
                    rows.set(r.id, r);
                    cardOf.set(r.id, c.id);
                }
                for (const r of (((c.folded || {}).rows) || [])) {
                    rows.set(r.id, r);
                    cardOf.set(r.id, c.id);
                }
            }
        }
        const nb = new Map();
        const push = (a, b) => {
            if (!nb.has(a)) { nb.set(a, []); }
            nb.get(a).push(b);
        };
        for (const l of (this.d.links || [])) { push(l.a, l.b); push(l.b, l.a); }
        this._index = { rows, cardOf, byCard, nb };
        this._indexFor = this.d;
        return this._index;
    }

    // ================================================================== memory
    /**
     * Which cards are open, remembered per scheme in THIS browser.
     *
     * Every read and every write is in a try/catch and the board renders
     * correctly with none of it: a private window, blocked site data or a
     * thumbnail capture all hand back nothing, and the honest answer to that is
     * "everything closed", which is the cold-start state anyway.
     */
    _storeKey(cfgId) { return "pb.journey.open." + (cfgId || this.configId); }

    _loadOpen(cfgId) {
        try {
            const raw = browser.localStorage.getItem(this._storeKey(cfgId));
            const val = raw ? JSON.parse(raw) : null;
            if (val && typeof val === "object" && !Array.isArray(val)) {
                return val;
            }
        } catch (e) {
            // storage unavailable — the board is simply all closed
        }
        return {};
    }

    _saveOpen() {
        try {
            browser.localStorage.setItem(
                this._storeKey(), JSON.stringify(this.ui.open));
        } catch (e) {
            // nothing to do: the open set is a convenience, never state
        }
    }

    // ================================================================== search
    /**
     * The rows a query shows — its matches AND everything they are linked to.
     *
     * J4 settled this on the transformation board and the reason carries to
     * rows: the FLOW is the unit of meaning here, so typing a column's name
     * must not empty the Scheme card and leave the reader looking at three
     * unrelated filtered lists. `null` means "no query", which is a different
     * answer from "an empty set".
     */
    get matches() {
        const q = (this.ui.q || "").trim().toLowerCase();
        if (!q) { return null; }
        const hit = new Set();
        const text = (r) => [r.label, r.tag, r.sub].filter(Boolean)
            .join(" ").toLowerCase();
        for (const [id, r] of this.index.rows) {
            if (text(r).includes(q)) { hit.add(id); }
        }
        for (const lane of LANES) {
            for (const c of this.cardsFor(lane.id)) {
                const ct = [c.label, c.sub].filter(Boolean).join(" ").toLowerCase();
                if (ct.includes(q)) {
                    for (const r of (c.rows || [])) { hit.add(r.id); }
                }
            }
        }
        const out = new Set(hit);
        for (const id of hit) {
            for (const o of (this.index.nb.get(id) || [])) { out.add(o); }
        }
        return out;
    }

    rowsOf(card) {
        const rows = card.rows || [];
        const m = this.matches;
        if (!m) { return rows; }
        return rows.filter((r) => m.has(r.id));
    }

    isOpen(card) {
        if (!card || !(card.rows || []).length) { return false; }
        if (this.matches) { return this.rowsOf(card).length > 0; }
        return !!this.ui.open[card.id];
    }

    onSearch(ev) { this.ui.q = ev.target.value || ""; this._animate(); }
    clearSearch() {
        this.ui.q = "";
        if (this.qRef.el) { this.qRef.el.value = ""; }
        this._animate();
    }

    // ================================================================== chrome
    /**
     * The header sentence. ONE msgid per shape, never assembled from fragments.
     *
     * The attention clause is dropped entirely when there is nothing wrong
     * rather than printed as "0 need attention" — a zero that has to be read
     * before it can be dismissed costs the reader something (W64/W80).
     */
    get headline() {
        const h = this.d.header || {};
        const bits = [
            h.inputs === 1 ? _t("1 needs a source")
                           : _t("%s need a source", h.inputs || 0),
            _t("%s fed", h.fed || 0),
            _t("%s not fed yet", h.unfed || 0),
        ];
        if (h.attention) {
            bits.push(h.attention === 1 ? _t("1 needs attention")
                                        : _t("%s need attention", h.attention));
        }
        return bits.join(" · ");
    }

    get attention() { return (this.d.header || {}).attention || 0; }

    /** Per-lane count line. Describes the VIEW when a search is on (J4's rule). */
    laneCount(laneId) {
        return String(this.cardsFor(laneId).length);
    }

    /** "3 hours ago", from an ISO string. Never "NaN days" (W46). */
    since(iso) {
        if (!iso) { return _t("never synced"); }
        const t = new Date(iso.endsWith("Z") ? iso : iso.replace(" ", "T") + "Z").getTime();
        if (isNaN(t)) { return _t("never synced"); }
        const h = (Date.now() - t) / 3600000;
        if (h < 1) { return _t("synced <1h ago"); }
        if (h < 24) { return _t("synced %sh ago", Math.round(h)); }
        return _t("synced %sd ago", Math.round(h / 24));
    }

    /**
     * The second line of a card.
     *
     * Everything that is not an AGE arrives already worded from the adapter; an
     * age has to be computed against the reader's clock, because a
     * server-rendered "3d ago" is stale the moment it is cached.
     */
    cardSub(c) {
        if (c.kind === "connector") {
            return [this.statusWord(c.status), this.since(c.last_sync), c.sub]
                .filter(Boolean).join(" · ");
        }
        return c.sub || "";
    }

    statusWord(status) {
        return {
            connected: _t("Connected"),
            connecting: _t("Connecting"),
            error: _t("Connection error"),
            disconnected: _t("Not connected"),
        }[status] || "";
    }

    /** The corner icon's tooltip: where it lands, said as a sentence. */
    doorHint(c) {
        const where = {
            api: _t("the System fields tab"),
            transform: _t("the Transformations tab"),
            import: _t("the Spreadsheet tab"),
            employee: _t("the Employee & contract tab"),
        }[((c && c.door) || {}).mode || ""] || "";
        return where ? _t("Opens %s, already on this.", where) : "";
    }

    cardTitle(c) {
        return this.isOpen(c) ? _t("Hide the fields inside this")
                              : _t("Show the fields inside this");
    }

    /** What one row says about itself in a tooltip — the full, unclipped text. */
    rowTitle(r) {
        const bits = [r.label];
        if (r.sub) { bits.push(r.sub); }
        if (r.state === "gone") { bits.push(_t("This source no longer exists.")); }
        if (r.state === "twice") {
            bits.push(_t("Two sources fill this. A pay run reads one of them."));
        }
        return bits.filter(Boolean).join(" — ");
    }

    /** The word for a link's kind, read out of the ONE register (RS6). */
    kindWord(kind) {
        if (kind === "record" || kind === "component" || kind === "reads") {
            return {
                record: _t("Employee record"),
                component: _t("Contract component"),
                reads: _t("Read by a transformation"),
            }[kind];
        }
        return srcLabel(kind) || "";
    }

    /** The scheme card's fed bar — a proportion of a COUNT, never a score. */
    get schemeBar() {
        const c = (this.cardsFor("scheme")[0] || {}).bar || {};
        const total = c.total || 0;
        return { fed: c.fed || 0, unfed: c.unfed || 0,
                 pct: total ? Math.round((c.fed / total) * 1000) / 10 : 0 };
    }

    groupsOf(card) { return card.groups || []; }

    rowsInGroup(card, groupId) {
        return this.rowsOf(card).filter((r) => (r.group || "") === groupId);
    }

    hasUngrouped(card) {
        return this.rowsOf(card).some((r) => !r.group);
    }

    ungrouped(card) { return this.rowsOf(card).filter((r) => !r.group); }

    // =================================================================== trace
    /**
     * Hovering a field lights its whole path and fades the rest (ruling 8).
     *
     * The set is the row's connected component, walked BOTH ways transitively,
     * so a file column lights through its component to the employee field it
     * also writes — one path, three lanes. Recomputed on hover change only; no
     * geometry is recomputed, because nothing moved.
     */
    get trace() {
        const seed = this.ui.pin || this.ui.hover;
        if (!seed) { return null; }
        const start = [];
        if (this.index.rows.has(seed)) {
            start.push(seed);
        } else {
            const card = this.index.byCard.get(seed);
            for (const r of ((card && card.rows) || [])) { start.push(r.id); }
        }
        if (!start.length) { return null; }
        const seen = new Set(start);
        const queue = start.slice();
        while (queue.length) {
            const id = queue.shift();
            for (const o of (this.index.nb.get(id) || [])) {
                if (!seen.has(o)) { seen.add(o); queue.push(o); }
            }
        }
        return seen;
    }

    onRowEnter(row) { this.ui.hover = row.id; }
    onRowLeave() { if (!this.ui.pin) { this.ui.hover = ""; } }
    onCardEnter(card) { this.ui.hover = card.id; }

    pinRow(row, ev) {
        if (ev) { ev.stopPropagation(); }
        this.ui.pin = this.ui.pin === row.id ? "" : row.id;
        this.ui.hover = row.id;
    }

    rowClass(r) {
        const bits = ["jny-row"];
        if (r.state && r.state !== "plain") { bits.push(r.state); }
        if (r.fed === false) { bits.push("nofeed"); }
        const t = this.trace;
        if (t) { bits.push(t.has(r.id) ? "on" : "off"); }
        if (this.ui.pin === r.id) { bits.push("pinned"); }
        return bits.join(" ");
    }

    cardClass(c) {
        const bits = ["jny-card"];
        if (c.dimmed) { bits.push("dim"); }
        if (c.primary) { bits.push("prim"); }
        if (c.tone) { bits.push(c.tone); }
        if (this.isOpen(c)) { bits.push("open"); }
        if (!(c.rows || []).length) { bits.push("flat"); }
        const t = this.trace;
        if (t) {
            const mine = (c.rows || []).some((r) => t.has(r.id));
            bits.push(mine || this.ui.hover === c.id ? "on" : "off");
        }
        return bits.join(" ");
    }

    cardIcon(c) {
        return {
            connector: "plug", file: "table", endpoint: "database",
            transform: "sigma", scheme: "calculator", source: "users",
        }[c.kind] || "gitMerge";
    }

    /**
     * The partner a row reaches, as text — the PHONE's substitute for a line.
     *
     * At 390px the lanes stack, so a curve between them would either run off
     * the screen or force a horizontal scroll. Naming the partner on the row
     * keeps the fact and drops the drawing.
     */
    partnerText(row) {
        const others = this.index.nb.get(row.id) || [];
        if (!others.length) { return ""; }
        const first = this.index.rows.get(others[0]);
        const name = (first && first.label) || "";
        if (!name) { return ""; }
        return others.length > 1
            ? _t("%(name)s +%(more)s", { name, more: others.length - 1 })
            : name;
    }

    // ================================================================ geometry
    _schedule() {
        if (this._raf) { return; }
        this._raf = requestAnimationFrame(() => {
            this._raf = null;
            this._recompute();
            if (Date.now() < this._until) { this._schedule(); }
        });
    }

    /**
     * Keep re-measuring for as long as the reveal runs.
     *
     * A line that snaps to its new place when the rows finish sliding reads as
     * a glitch; a line that travels with them reads as the same object moving.
     * `transitionend` alone is not enough — it fires once, at the END.
     */
    _animate() {
        this._until = Date.now() + REVEAL_MS + 60;
        this._schedule();
    }

    onRevealEnd() { this._schedule(); }

    /**
     * One pass per lane into a Map of id -> {y, left, right} plus the band.
     *
     * P2 — `querySelectorAll('[data-id]')` rather than `body.children`, because
     * a row is two levels down inside its card. Both the card header and the
     * row carry a `data-id`; the Y comes from the element itself and the X from
     * the CARD's rect, so a row's line leaves the card's border rather than the
     * middle of its text, and forty rows leave forty parallel lines.
     *
     * Keys are STRINGS throughout (W146): every id this board mints already is
     * one (`c:3`, `e:11:base`, `scheme`), so the ambiguity cannot arise.
     */
    _measure(body, rb, laneId) {
        if (!body) { return null; }
        const br = body.getBoundingClientRect();
        if (br.width < 8 || br.height < 8) { return null; }
        const map = new Map();
        for (const el of body.querySelectorAll("[data-id]")) {
            const id = el.dataset && el.dataset.id;
            if (!id) { continue; }
            const host = el.closest(".jny-card") || el;
            const cr = host.getBoundingClientRect();
            const r = el.getBoundingClientRect();
            if (r.height < 1) { continue; }
            map.set(id, { y: r.top + r.height / 2 - rb.top,
                          left: cr.left - rb.left,
                          right: cr.right - rb.left });
        }
        return { map, laneId,
                 bandTop: br.top - rb.top + BAND,
                 bandBot: br.bottom - rb.top - BAND };
    }

    /**
     * The edges that are actually drawn, folded out of `links` + what is open.
     *
     *   end(row) = the row itself when its card is open and the row rendered,
     *              its CARD otherwise
     *
     * Links that fold onto the same pair become ONE line carrying a count, and
     * a count badge is drawn only when BOTH ends are cards — when one end is
     * open, the rows themselves are the count and a badge would be repeating
     * what is already on screen.
     */
    get drawn() {
        const rendered = new Set();
        for (const lane of LANES) {
            for (const c of this.cardsFor(lane.id)) {
                if (!this.isOpen(c)) { continue; }
                for (const r of this.rowsOf(c)) { rendered.add(r.id); }
            }
        }
        const endOf = (rid) => {
            const cid = this.index.cardOf.get(rid);
            if (cid === undefined) { return null; }
            return rendered.has(rid) ? rid : cid;
        };
        const by = new Map();
        for (const l of (this.d.links || [])) {
            const a = endOf(l.a);
            const b = endOf(l.b);
            // MAPFIX F1 — an end that does not exist gets NO curve, ever. A
            // suppressed wire is never drawn to a lane edge pretending to be
            // real.
            if (!a || !b || a === b) { continue; }
            const key = [a, b, l.dir, l.dimmed ? 1 : 0].join("|");
            let g = by.get(key);
            if (!g) {
                g = { id: key, a, b, dir: l.dir || "fwd", dimmed: !!l.dimmed,
                      kind: l.kind || "", n: 0, rows: new Set(),
                      ends: !rendered.has(l.a) && !rendered.has(l.b) };
                by.set(key, g);
            }
            g.n++;
            g.rows.add(l.a);
            g.rows.add(l.b);
            if (g.kind !== l.kind) { g.kind = "mixed"; }
        }
        for (const c of (this.d.contains || [])) {
            const key = [c.from, c.to, "contain", 0].join("|");
            if (!this.index.byCard.has(c.from) || !this.index.byCard.has(c.to)) {
                continue;
            }
            by.set(key, { id: key, a: c.from, b: c.to, dir: "fwd", dimmed: false,
                          kind: "contain", n: 0, rows: new Set(), ends: true });
        }
        return [...by.values()];
    }

    _recompute() {
        const root = this.rootRef.el;
        if (!root) { return; }
        const rb = root.getBoundingClientRect();
        const M = {};
        const order = {};
        this.lanes.forEach((l, n) => { order[l.id] = n; });
        for (const lane of LANES) {
            M[lane.id] = this._measure(this.laneRefs[lane.id].el, rb, lane.id);
        }
        const where = new Map();
        for (const lane of LANES) {
            const m = M[lane.id];
            if (!m) { continue; }
            for (const id of m.map.keys()) { where.set(id, lane.id); }
        }
        this._recomputes++;
        const trace = this.trace;
        const geom = [];
        for (const e of this.drawn) {
            const la = where.get(String(e.a));
            const lb = where.get(String(e.b));
            if (!la || !lb || la === lb) { continue; }
            const A = M[la].map.get(String(e.a));
            const B = M[lb].map.get(String(e.b));
            if (!A || !B) { continue; }
            const a = clampY(A.y, M[la].bandTop, M[la].bandBot);
            const b = clampY(B.y, M[lb].bandTop, M[lb].bandBot);
            // The arrow runs from `a` to `b` as the PAYLOAD names them, so a
            // `back` link (the pay run, a contract component) points INTO the
            // scheme instead of out of it. A hidden lane is not a span: the
            // indexes are over the VISIBLE lanes.
            const rtl = order[la] > order[lb];
            const g = wireGeometry(rtl ? A.left : A.right, a.y,
                                   rtl ? B.right : B.left, b.y,
                                   e.dir === "both");
            const span = Math.abs((order[lb] || 0) - (order[la] || 0));
            let lit = 0;
            if (trace) {
                lit = -1;
                for (const rid of e.rows) {
                    if (trace.has(rid)) { lit = 1; break; }
                }
            }
            geom.push({ ...g, id: e.id, kind: e.kind, count: e.n,
                        bidi: e.dir === "both", dimmed: e.dimmed, span,
                        badge: e.ends && e.n > 1,
                        // The RESTING width is the floor, not 1: the inline
                        // `stroke-width` wins over the stylesheet, so a base
                        // of 1 quietly undid the 1.25 the sheet sets and every
                        // single-link line went back to a hairline.
                        width: 1.25 + Math.min(3, Math.log2(Math.max(1, e.n))),
                        lit, docked: a.docked || b.docked });
        }
        // Two counted lines that meet near the same midpoint stack their
        // badges at exactly the same coordinate and the top one wins every
        // hover. `spreadHubs` is the canvas' own fix for that, applied to the
        // badges ALONE so nothing that has no badge is moved off its wire.
        spreadHubs(geom.filter((g) => g.badge), 22, 40, 26);
        this.ui.geom = geom;
    }

    /** WP-6 — what a recompute costs, for anyone profiling from the console. */
    get recomputeCost() { return { n: this._recomputes, edges: this.ui.geom.length }; }

    edgeTitle(g) {
        if (g.kind === "contain") { return _t("This belongs to that system."); }
        if (g.dimmed) {
            return _t("This scheme does not read this connection on a system run.");
        }
        if (!g.count) { return ""; }
        return g.count === 1 ? _t("1 field") : _t("%s fields", g.count);
    }

    // ============================================================= interaction
    /**
     * MF33, third board running. Enter on a focused button fires the button's
     * own click AND falls through to the root handler without this guard.
     */
    onKeydown(ev) {
        const tag = (ev.target && ev.target.tagName) || "";
        if ((ev.key === "Enter" || ev.key === " ")
            && (tag === "BUTTON" || tag === "A")) { return; }
        if (ev.key === "/" && tag !== "INPUT") {
            ev.preventDefault();
            if (this.qRef.el) { this.qRef.el.focus(); }
            return;
        }
        if (ev.key === "Escape") {
            // The ladder, most-nested first. Each rung consumes the key, so one
            // Escape never dismisses two things at once.
            if (this.ui.q) { this.clearSearch(); return; }
            if (this.ui.pin) { this.ui.pin = ""; return; }
            if (this.ui.hover) { this.ui.hover = ""; }
        }
    }

    /**
     * The card BODY opens and closes. It never navigates — ruling 5, and the
     * reversal of what this board used to do.
     */
    toggle(card) {
        if (!(card.rows || []).length) { return; }
        const open = { ...this.ui.open };
        if (open[card.id]) { delete open[card.id]; } else { open[card.id] = true; }
        this.ui.open = open;
        this._saveOpen();
        this._animate();
    }

    toggleFolded() { this.ui.folded = !this.ui.folded; this._animate(); }

    /** The small corner icon, and the ONLY thing on this board that navigates. */
    openDoor(card, ev) {
        if (ev) { ev.stopPropagation(); }
        if (!card || !card.door) { return; }
        this.props.onOpenDoor(card.door);
    }

    openChip(chip, ev) {
        if (ev) { ev.stopPropagation(); }
        if (!chip || !chip.door) { return; }
        this.props.onOpenDoor(chip.door);
    }

    openInvite(door, ev) {
        if (ev) { ev.stopPropagation(); }
        if (!door || !door.door) { return; }
        this.props.onOpenDoor(door.door);
    }

    /**
     * A card's SECONDARY actions — a door out of Mapping altogether.
     *
     * The probe is the `plan_launcher.js:204` pattern: the server can resolve
     * an `ir.actions.client` whose JS never shipped, and opening one of those
     * is a blank screen. A database without `pb_records` renders no button.
     */
    cardActions(card) {
        const actions = (card && card.actions) || [];
        return actions.filter(
            (a) => !a.tag || registry.category("actions").contains(a.tag));
    }

    runAction(action, ev) {
        if (ev) { ev.stopPropagation(); }
        if (!action || !action.xmlid) { return; }
        this.action.doAction(action.xmlid, {
            additionalContext: action.params || {},
            clearBreadcrumbs: false,
        });
    }

    /** The invitation's doors are filtered to the tabs this scheme HAS (SC-4). */
    inviteDoors() {
        const doors = (this.invite && this.invite.doors) || [];
        return doors;
    }
}
