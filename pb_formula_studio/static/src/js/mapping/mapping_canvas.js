/** @odoo-module **/
// F10 — Unified Mapping Canvas.
// A payroll-AGNOSTIC two-column wiring board. It knows nothing about payroll:
// it renders `leftItems`/`rightItems`, draws `wires` between them as SVG
// bezier paths, and calls back on user intent. Every mapping surface (cycle,
// API field, import column, employee→scheme) is just a different adapter that
// supplies these props and implements the callbacks against its own model.
//
// Integrations Cycle 5 rebuilt the WIRE half of it, against a real 200×40
// board. Four things changed and they are all consequences of one another:
//
//   * the scroll listener moved onto `.mc-col-body`. It had been on the parent
//     `.mc-col`, and `scroll` does not bubble — so geometry was never
//     recomputed while a column moved. Every "wire flying off the screen" in
//     the owner's screenshots is a line drawn to where a card USED to be;
//   * the board clips, and every endpoint is CLAMPED into its column's visible
//     band. A wire may end on the edge of a column; it may never leave the
//     board and it may never point at a card that is not there;
//   * parked endpoints aggregate into counted DOCK CHIPS, so a connection that
//     is out of view still says so — silently dropping it (which is what the
//     previous version did) is the failure mode this codebase punishes hardest;
//   * the three overlapping midpoint badges became ONE three-zone hub:
//     ◀ jump to source │ the transform │ jump to target ▶.
//
// The curve itself is the Formula Engine's dependency-arrow form (control
// points sharing their endpoint's Y, hand-placed triangular head) re-expressed
// in `mapping_geometry.js`. That module is pure and unit-tested; nothing here
// does arithmetic that could be done there.
import { Component, useState, useRef, onMounted, onWillUnmount, onPatched,
         onWillUpdateProps, useExternalListener } from "@odoo/owl";
import { ic } from "@pb_import_kit/js/import_icons";
import { aggregateDocks, clampY, itemMatches, spreadHubs, wireGeometry }
    from "./mapping_geometry";

/** How many wires may carry a travelling highlight before it becomes noise. */
const FLOW_LIMIT = 60;
/** Inset of the clamp band from a column's top and bottom edge. */
const BAND = 8;

export class MappingCanvas extends Component {
    static template = "pb_formula_studio.MappingCanvas";
    static props = {
        leftItems: Array,          // [{id, label, sublabel, sample, group, meta}]
        rightItems: Array,
        wires: Array,              // [{id, leftId, rightId, state, confidence, reason, kind, ref}]
        leftTitle: { type: String, optional: true },
        rightTitle: { type: String, optional: true },
        canEdit: { type: Boolean, optional: true },
        busy: { type: Boolean, optional: true },
        onAccept: { type: Function, optional: true },   // (wire)
        onReject: { type: Function, optional: true },   // (wire)
        onDelete: { type: Function, optional: true },   // (wire)
        onDraw: { type: Function, optional: true },     // (leftId, rightId)
        onTransformPreview: { type: Function, optional: true },  // (ref, draft) → Promise
        onTransformSave: { type: Function, optional: true },     // (ref, vals) → Promise
        onRemoveRight: { type: Function, optional: true },       // (rightId) — remove an UNWIRED right item
        // C5 — one-shot orders from the host's story bar. `{token, kind}`; the
        // token is what makes a repeated click repeat the effect. Optional, so
        // the Formula Studio overlay never has to know it exists.
        command: { type: Object, optional: true },
    };

    setup() {
        this.ui = useState({
            armedLeft: null,      // a left item id awaiting a right click (draw mode)
            hoverWire: null,
            hoverItem: null,      // {side, id} — the card the pointer is on
            selWire: null,        // the wire whose hub stays open
            flash: null,          // {side, id} — the arrival ring after a jump
            focusSide: "left",
            focusId: null,
            geom: [],             // [{...wire, d, head, hx, hy, dockL, dockR}]
            docks: [],            // aggregated parked endpoints, per column edge
            gone: 0,              // wires whose card is not in the list AT ALL
            pulse: false,         // the story bar's "flash every wire"
            // C5 — per-column search + filter. Column state, not host state:
            // the overlay host gets it for free and cannot forget to pass it.
            q: { left: "", right: "" },      // what is typed
            qa: { left: "", right: "" },     // what is applied (120ms behind)
            f: { left: "all", right: "all" },
            hoverCol: "",                    // which column "/" would focus
            // W62 — transform popover (API wires only)
            tfOpen: null,         // open wire id, or null
            tfPy: false,          // the open wire is a read-only python transform
            tfDraft: {},          // {transformation_type, transformation_value, transformation_decimals}
            tfPreview: {},        // {sample, result, error, loading}
            tfSaving: false,
        });
        this.rootRef = useRef("root");
        this.lbodyRef = useRef("lbody");
        this.rbodyRef = useRef("rbody");
        this.lqRef = useRef("lq");
        this.rqRef = useRef("rq");
        this._raf = null;
        this._recomputes = 0;     // T1 — what the coalescing test asserts
        this._cost = 0;           // ms of the last recompute (WP-6 reporting)
        this._qt = {};            // per-column search debounce timers
        this._dockCursor = {};    // which docked endpoint the next click visits
        this._flashTimer = null;
        this._pulseTimer = null;
        this._cmdToken = (this.props.command && this.props.command.token) || 0;
        this._tfRef = null;       // mapping ref of the open transform popover
        this._tfToken = 0;        // C8 supersede token for the debounced preview
        this._tfTimer = null;
        this._recompute = this._recompute.bind(this);
        onMounted(() => {
            this._recompute();
            this._ro = new ResizeObserver(() => this._schedule());
            // The ROOT alone never reports a column growing a scrollbar or a
            // filtered list changing height — observe both scrollers too.
            for (const el of [this.rootRef.el, this.lbodyRef.el, this.rbodyRef.el]) {
                if (el) { this._ro.observe(el); }
            }
        });
        onWillUnmount(() => {
            if (this._ro) { this._ro.disconnect(); }
            if (this._raf) { cancelAnimationFrame(this._raf); }
            if (this._tfTimer) { clearTimeout(this._tfTimer); }
            if (this._flashTimer) { clearTimeout(this._flashTimer); }
            if (this._pulseTimer) { clearTimeout(this._pulseTimer); }
            for (const t of Object.values(this._qt)) { clearTimeout(t); }
        });
        onWillUpdateProps((next) => {
            this._fsKey = null;
            // A different connector, feed or scheme is a different board: a
            // filter left over from the last one would hide rows the user never
            // chose to hide (W117's shape — never absorb a context change).
            if (next.leftTitle !== this.props.leftTitle
                || next.rightTitle !== this.props.rightTitle) {
                this.resetQuery("left");
                this.resetQuery("right");
                this.ui.selWire = null;
            }
            this._runCommand(next.command);
        });
        onPatched(() => this._schedule());
        useExternalListener(window, "resize", () => this._schedule());
    }

    /** Lucide, from the shared registry — never a hand-rolled path (W2). */
    ic(n, s = 14) { return ic(n, s); }

    // ---- geometry -----------------------------------------------------
    _schedule() {
        if (this._raf) { return; }
        this._raf = requestAnimationFrame(() => { this._raf = null; this._recompute(); });
    }
    onColScroll() { this._schedule(); }

    /**
     * One pass over a column, not two selector queries per wire.
     *
     * The old recompute ran `root.querySelector('.mc-item[data-id="…"]')` twice
     * for every wire — 2N attribute-selector walks of the whole subtree per
     * frame, with the id interpolated unescaped (an id containing a quote threw).
     * This walks each column's children ONCE into a Map and the rest of the
     * recompute is arithmetic. It also returns the column's band, so clamping
     * has somewhere to clamp to.
     *
     * `null` means "not anchorable": a hidden host or a mid-transition rect
     * whose numbers would sweep a line across the screen (the reference
     * renderer's `anchorable` guard, and the same lesson).
     */
    _measure(body, rb, side) {
        if (!body) { return null; }
        const br = body.getBoundingClientRect();
        if (br.width < 8 || br.height < 8) { return null; }
        const map = new Map();
        const bandTop = br.top - rb.top + BAND;
        const bandBot = br.bottom - rb.top - BAND;
        let edge = null;
        let firstVisibleId = null;
        // NOTE the keys are STRINGS. `dataset.id` always is, and the adapters
        // disagree about the type of an item id — the API board's left ids are
        // strings (`f:account_number`) and its right ids are integers (`183`).
        // The old code hid this by interpolating into a CSS attribute selector,
        // which stringifies; a Map does not, and `map.has(183)` against a key
        // of `"183"` is a silent miss that reads on screen as "this wire's
        // target has been filtered away". Everything below goes through
        // `String()` (Integrations C5, W146).
        for (const el of body.children) {
            const id = el.dataset && el.dataset.id;
            if (!id || el.dataset.side !== side) { continue; }   // group headers
            const r = el.getBoundingClientRect();
            const cy = r.top + r.height / 2 - rb.top;
            map.set(id, cy);
            if (edge === null) {
                edge = side === "left" ? (r.right - rb.left) : (r.left - rb.left);
            }
            if (firstVisibleId === null && cy >= bandTop) { firstVisibleId = id; }
        }
        if (edge === null) {
            // an empty or fully filtered-out column still has to anchor its wires
            edge = side === "left" ? (br.right - rb.left - 14) : (br.left - rb.left + 14);
        }
        return { map, edge, bandTop, bandBot, firstVisibleId };
    }

    /** Full-list index maps, rebuilt only when the props arrays change. */
    _indexes() {
        if (this._idxSrcL !== this.props.leftItems) {
            this._idxSrcL = this.props.leftItems;
            this._idxL = new Map(this.props.leftItems.map((i, n) => [String(i.id), n]));
        }
        if (this._idxSrcR !== this.props.rightItems) {
            this._idxSrcR = this.props.rightItems;
            this._idxR = new Map(this.props.rightItems.map((i, n) => [String(i.id), n]));
        }
        return { L: this._idxL, R: this._idxR };
    }

    /**
     * Which edge a card hidden by a FILTER should dock on.
     *
     * It has no rect to read, so the honest answer comes from its position in
     * the unfiltered list relative to the first card currently in view: before
     * it means up, after it means down. A guess would be a lie, and this is not
     * a guess — it is where the card would be if the filter were cleared.
     */
    _hiddenDir(idx, id, firstVisibleId) {
        if (!idx.has(id)) { return 1; }
        const mine = idx.get(id);
        const first = firstVisibleId != null && idx.has(firstVisibleId)
            ? idx.get(firstVisibleId) : 0;
        return mine < first ? -1 : 1;
    }

    _recompute() {
        this._recomputes++;
        const t0 = performance.now();
        const root = this.rootRef.el;
        if (!root) { return; }
        const rb = root.getBoundingClientRect();
        if (rb.width < 20 || rb.height < 20) { return; }   // mid-transition host
        const L = this._measure(this.lbodyRef.el, rb, "left");
        const R = this._measure(this.rbodyRef.el, rb, "right");
        if (!L || !R) { this.ui.geom = []; this.ui.docks = []; return; }
        const { L: iL, R: iR } = this._indexes();

        const geom = [];
        let gone = 0;
        const sx = L.edge + 4, tx = R.edge - 4;
        for (const w of this.props.wires) {
            const lk = String(w.leftId), rk = String(w.rightId);
            const hasL = L.map.has(lk), hasR = R.map.has(rk);
            // genuinely absent from the LIST (not merely filtered out): the one
            // case where there is no card to point at. Counted, then surfaced —
            // never swallowed the way `continue` used to swallow it.
            if ((!hasL && !iL.has(lk)) || (!hasR && !iR.has(rk))) {
                gone++;
                continue;
            }
            let y1, dockL, rawL;
            if (hasL) {
                rawL = L.map.get(lk);
                const c = clampY(rawL, L.bandTop, L.bandBot);
                y1 = c.y; dockL = c.docked;
            } else {
                dockL = this._hiddenDir(iL, lk, L.firstVisibleId);
                y1 = dockL < 0 ? L.bandTop : L.bandBot;
                rawL = dockL < 0 ? -1e6 : 1e6;
            }
            let y2, dockR, rawR;
            if (hasR) {
                rawR = R.map.get(rk);
                const c = clampY(rawR, R.bandTop, R.bandBot);
                y2 = c.y; dockR = c.docked;
            } else {
                dockR = this._hiddenDir(iR, rk, R.firstVisibleId);
                y2 = dockR < 0 ? R.bandTop : R.bandBot;
                rawR = dockR < 0 ? -1e6 : 1e6;
            }
            const g = wireGeometry(sx, y1, tx, y2);
            geom.push({
                ...w,
                d: g.d, head: g.head, hx: g.hx, hy: g.hy,
                sx, tx, y1, y2, rawL, rawR,
                dockL, dockR, hiddenL: !hasL, hiddenR: !hasR,
                err: !!(w.transform && w.transform.error),
            });
        }
        spreadHubs(geom);

        const docks = aggregateDocks(geom).map((d) => {
            const col = d.side === "left" ? L : R;
            // nearest first, so the first click lands on the endpoint just past
            // the edge rather than on whichever wire happened to be listed first
            const key = d.side === "left" ? "rawL" : "rawR";
            const edgeY = d.dir < 0 ? col.bandTop : col.bandBot;
            const byId = new Map(geom.map((g) => [g.id, g]));
            d.ids.sort((a, b) => Math.abs(byId.get(a)[key] - edgeY)
                               - Math.abs(byId.get(b)[key] - edgeY));
            return { ...d, x: col.edge, y: d.dir < 0 ? col.bandTop : col.bandBot };
        });

        // Assigning `ui.geom` unconditionally is a RENDER LOOP: a new array is
        // always "changed", the patch schedules another recompute, and the
        // board burns a frame forever doing nothing. (It always did — it was
        // survivable at 6 wires and is not at 200×40.) Write only when a number
        // a human could see has actually moved.
        const sig = geom.map((g) => `${g.id}~${g.d}~${g.hy.toFixed(1)}~${g.dockL}${g.dockR}~${g.state}`).join("|")
            + "#" + docks.map((d) => `${d.key}:${d.count}:${d.filtered}`).join(",")
            + "#" + gone;
        this._cost = performance.now() - t0;
        if (sig === this._sig) { return; }
        this._sig = sig;
        this.ui.geom = geom;
        this.ui.docks = docks;
        this.ui.gone = gone;
    }

    /** WP-6 — what a recompute costs, for anyone profiling from the console. */
    get recomputeCost() { return { ms: this._cost, n: this._recomputes, wires: this.ui.geom.length }; }

    // ---- the host's story-bar commands ---------------------------------
    _runCommand(cmd) {
        if (!cmd || !cmd.token || cmd.token === this._cmdToken) { return; }
        this._cmdToken = cmd.token;
        if (cmd.kind === "pulse") {
            this.ui.pulse = true;
            if (this._pulseTimer) { clearTimeout(this._pulseTimer); }
            this._pulseTimer = setTimeout(() => { this.ui.pulse = false; }, 1050);
        } else if (cmd.kind === "suggested") {
            this.ui.f.left = "suggested";
            this.ui.f.right = "suggested";
            this.ui.q.left = ""; this.ui.qa.left = "";
            this.ui.q.right = ""; this.ui.qa.right = "";
        }
    }

    // ---- search + filter (WP-4) ----------------------------------------
    resetQuery(side) {
        if (this._qt[side]) { clearTimeout(this._qt[side]); }
        this.ui.q[side] = ""; this.ui.qa[side] = ""; this.ui.f[side] = "all";
    }
    onSearch(side, ev) {
        this.ui.q[side] = ev.target.value || "";
        if (this._qt[side]) { clearTimeout(this._qt[side]); }
        this._qt[side] = setTimeout(() => { this.ui.qa[side] = this.ui.q[side]; }, 120);
    }
    clearSearch(side) {
        if (this._qt[side]) { clearTimeout(this._qt[side]); }
        this.ui.q[side] = ""; this.ui.qa[side] = "";
    }
    onSearchKey(side, ev) {
        if (ev.key === "Escape") { ev.stopPropagation(); this.clearSearch(side); }
    }
    setFilter(side, v) { this.ui.f[side] = this.ui.f[side] === v ? "all" : v; }
    clearFilters(side) { this.clearSearch(side); this.ui.f[side] = "all"; }
    hasFilter(side) { return this.ui.f[side] !== "all" || !!this.ui.qa[side]; }

    /** Which left ids carry a suggestion — computed once per wires array. */
    _sugSets() {
        if (this._sugSrc !== this.props.wires) {
            this._sugSrc = this.props.wires;
            this._sugL = new Set(); this._sugR = new Set();
            this._wiredL = new Set(); this._wiredR = new Set();
            this._accL = new Set(); this._accR = new Set();
            for (const w of this.props.wires) {
                this._wiredL.add(w.leftId); this._wiredR.add(w.rightId);
                if (w.state === "suggested") { this._sugL.add(w.leftId); this._sugR.add(w.rightId); }
                if (w.state === "accepted") { this._accL.add(w.leftId); this._accR.add(w.rightId); }
            }
        }
        return this;
    }
    get hasSuggestions() { this._sugSets(); return this._sugL.size > 0; }

    _passes(side, it) {
        this._sugSets();
        const f = this.ui.f[side];
        if (f !== "all") {
            const acc = side === "left" ? this._accL : this._accR;
            const wired = side === "left" ? this._wiredL : this._wiredR;
            const sug = side === "left" ? this._sugL : this._sugR;
            if (f === "mapped" && !acc.has(it.id)) { return false; }
            if (f === "unmapped" && wired.has(it.id)) { return false; }
            if (f === "suggested" && !sug.has(it.id)) { return false; }
        }
        return itemMatches(it, this.ui.qa[side]);
    }

    get leftView() {
        if (!this.hasFilter("left")) { return this.props.leftItems; }
        return this.props.leftItems.filter((it) => this._passes("left", it));
    }
    get rightView() {
        if (!this.hasFilter("right")) { return this.props.rightItems; }
        return this.props.rightItems.filter((it) => this._passes("right", it));
    }
    /** "12 of 200" while filtering, plain "200" otherwise. */
    countLabel(side) {
        const all = side === "left" ? this.props.leftItems.length : this.props.rightItems.length;
        if (!this.hasFilter(side)) { return String(all); }
        const shown = side === "left" ? this.leftView.length : this.rightView.length;
        return `${shown} of ${all}`;
    }
    /** How many wires this column's filter is currently hiding an end of. */
    hiddenWires(side) {
        return this.ui.geom.filter((g) => (side === "left" ? g.hiddenL : g.hiddenR)).length;
    }
    searchPlaceholder(side) {
        const n = side === "left" ? this.props.leftItems.length : this.props.rightItems.length;
        return side === "left" ? `Search ${n} fields…` : `Search ${n} columns…`;
    }
    filterChips(side) {
        const chips = [{ v: "all", l: "All" }, { v: "mapped", l: "Mapped" },
                       { v: "unmapped", l: "Unmapped" }];
        if (this.hasSuggestions) { chips.push({ v: "suggested", l: "Suggested" }); }
        return chips;
    }

    // ---- hover coupling (WP-3) -----------------------------------------
    /**
     * What is lit, and therefore what is dimmed.
     *
     * Recomputed only when the pointer or the selection actually moves — an
     * OWL getter is read once per item per render, and this is O(wires) each
     * time it is genuinely invalidated rather than O(items × wires) always.
     */
    get focusSet() {
        const u = this.ui;
        const hi = u.hoverItem;
        const key = [u.selWire, u.hoverWire, hi && hi.side, hi && hi.id,
                     this.props.wires.length].join("|");
        if (this._fsKey === key) { return this._fs; }
        const wires = new Set(), left = new Set(), right = new Set();
        const take = (w) => { wires.add(w.id); left.add(w.leftId); right.add(w.rightId); };
        for (const w of this.props.wires) {
            if (w.id === u.selWire || w.id === u.hoverWire) { take(w); }
            else if (hi && (hi.side === "left" ? w.leftId : w.rightId) === hi.id) { take(w); }
        }
        if (hi) { (hi.side === "left" ? left : right).add(hi.id); }
        this._fs = { on: wires.size > 0 || !!hi, wires, left, right };
        this._fsKey = key;
        return this._fs;
    }
    itemTone(side, id) {
        const f = this.focusSet;
        if (!f.on) { return ""; }
        return (side === "left" ? f.left : f.right).has(id) ? "lit" : "dim";
    }
    wireTone(g) {
        const f = this.focusSet;
        if (!f.on) { return ""; }
        return f.wires.has(g.id) ? "hot" : "dim";
    }
    enterItem(side, id) { this.ui.hoverItem = { side, id }; }
    leaveItem() { this.ui.hoverItem = null; }
    enterWire(id) { this.ui.hoverWire = id; }
    leaveWire() { this.ui.hoverWire = null; }
    /** Travelling highlights are a flourish; past ~60 wires they are static. */
    get flowing() {
        return this.ui.geom.length > 0 && this.ui.geom.length <= FLOW_LIMIT && !this.props.busy;
    }
    flowDur(i) { return (7.5 + (i % 9) * 0.7).toFixed(1) + "s"; }

    // ---- the wire hub (WP-2) -------------------------------------------
    hubVisible(g) {
        // suggestions are the board's call to action and stay put; everything
        // else appears under the pointer or when the wire is selected, because
        // fifty pills at rest is the clutter this cycle was called to remove
        return g.state === "suggested"
            || this.ui.selWire === g.id
            || this.ui.hoverWire === g.id
            || this.focusSet.wires.has(g.id);
    }
    selectWire(g, ev) {
        if (ev) { ev.stopPropagation(); }
        this.ui.selWire = this.ui.selWire === g.id ? null : g.id;
    }
    /** Double-click on the wire ITSELF: whichever end you clicked nearer. */
    wireDblClick(g, ev) {
        const rb = this.rootRef.el.getBoundingClientRect();
        const x = ev.clientX - rb.left;
        this.jumpTo(Math.abs(x - g.sx) <= Math.abs(x - g.tx) ? "left" : "right", g);
    }
    _itemEl(body, id) {
        if (!body) { return null; }
        const key = String(id);        // `dataset.id` is always a string (W146)
        for (const el of body.children) {
            if (el.dataset && el.dataset.id === key) { return el; }
        }
        return null;
    }
    /**
     * Go to one end of a wire, and say you arrived.
     *
     * Deliberately NOT `scrollIntoView`: that walks up to every scrollable
     * ancestor, and the Formula Engine paid for exactly that once already
     * (`_panelOnCanvas`) when it displaced a whole workspace to "reveal" an
     * off-canvas panel. Scrolling the column's own body by arithmetic can
     * displace nothing else on the screen.
     */
    jumpTo(side, g) {
        const id = side === "left" ? g.leftId : g.rightId;
        this.ui.selWire = g.id;
        // an end hidden by this column's own filter is unreachable until the
        // filter goes — clearing it is what the user meant by asking to go there
        if (side === "left" ? g.hiddenL : g.hiddenR) { this.clearFilters(side); }
        const go = () => {
            const body = side === "left" ? this.lbodyRef.el : this.rbodyRef.el;
            const el = this._itemEl(body, id);
            if (!body || !el) { return; }
            const top = el.offsetTop - (body.clientHeight - el.offsetHeight) / 2;
            body.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
            this.ui.flash = { side, id };
            if (this._flashTimer) { clearTimeout(this._flashTimer); }
            this._flashTimer = setTimeout(() => { this.ui.flash = null; }, 950);
        };
        // one frame, so a just-cleared filter has rendered its rows first
        requestAnimationFrame(go);
    }
    isFlashing(side, id) {
        const f = this.ui.flash;
        return !!(f && f.side === side && f.id === id);
    }

    // ---- dock chips (WP-1.4) -------------------------------------------
    /**
     * What a dock chip says.
     *
     * The composition has to be ALL of one kind before the chip may name that
     * kind; a mixed pile is "N wires", because "51 suggested" over 50 accepted
     * mappings and one suggestion is a sentence the board cannot support.
     */
    dockLabel(d) {
        const where = d.dir < 0 ? "above" : "below";
        if (d.filtered === d.count) { return `${d.count} hidden by filter ${where}`; }
        if (d.sug === d.count) { return `${d.count} suggested ${where}`; }
        if (d.sug === 0) { return `${d.count} mapped ${where}`; }
        return `${d.count} wires ${where}`;
    }
    clickDock(d) {
        if (!d.ids.length) { return; }
        const i = (this._dockCursor[d.key] || 0) % d.ids.length;
        this._dockCursor[d.key] = i + 1;
        const g = this.ui.geom.find((x) => x.id === d.ids[i]);
        if (g) { this.jumpTo(d.side, g); }
    }

    // ---- optional left-column grouping (Integrations Cycle 2) ---------
    /**
     * The group header to draw ABOVE left item `i`, or "".
     *
     * Opt-in and additive: an item with no `group` renders exactly as it did
     * before, so the Formula Studio overlay is byte-identical on every adapter
     * that does not send one. The Mapping Studio sends the feed's name, because
     * a board that mixes one connector's feeds with the mappings drawn before
     * feeds existed has to say which is which — a list where "Unassigned" looks
     * like "Employees" is a list that has lost the distinction it was built to
     * make.
     *
     * C5: it reads the FILTERED list, so a search that leaves one field under a
     * feed still shows that feed's name above it.
     */
    leftGroupHead(items, i) {
        const g = (items[i] || {}).group || "";
        if (!g) { return ""; }
        const prev = i > 0 ? (items[i - 1].group || "") : "";
        return g === prev ? "" : g;
    }

    // ---- wire lookups -------------------------------------------------
    wiresForLeft(id) { return this.props.wires.filter(w => w.leftId === id); }
    wiresForRight(id) { return this.props.wires.filter(w => w.rightId === id); }
    isLeftWired(id) { this._sugSets(); return this._wiredL.has(id); }
    isRightWired(id) { this._sugSets(); return this._wiredR.has(id); }
    leftHasAccepted(id) { this._sugSets(); return this._accL.has(id); }
    rightHasAccepted(id) { this._sugSets(); return this._accR.has(id); }

    // ---- draw interaction (click-arm-left → click-right) --------------
    clickLeft(id) {
        if (!this.props.canEdit) { this.ui.focusSide = "left"; this.ui.focusId = id; return; }
        this.ui.focusSide = "left"; this.ui.focusId = id;
        this.ui.armedLeft = (this.ui.armedLeft === id) ? null : id;
    }
    clickRight(id) {
        this.ui.focusSide = "right"; this.ui.focusId = id;
        if (this.ui.armedLeft != null && this.props.canEdit && this.props.onDraw) {
            this.props.onDraw(this.ui.armedLeft, id);
            this.ui.armedLeft = null;
        }
    }
    isArmed(id) { return this.ui.armedLeft === id; }

    // ---- wire actions --------------------------------------------------
    accept(w) { if (this.props.onAccept) this.props.onAccept(w); }
    reject(w) { if (this.props.onReject) this.props.onReject(w); }
    del(w) { if (this.props.onDelete) this.props.onDelete(w); }
    // remove a right item from the board (adapter decides what that means).
    // The template only renders the ✕ on UNWIRED items, so this never unmaps.
    removeRight(id, ev) { if (ev) ev.stopPropagation(); if (this.props.onRemoveRight) this.props.onRemoveRight(id); }
    confidencePct(w) { return Math.round((w.confidence || 0) * 100); }

    // ---- W62 transforms on the wire (API adapter only) ----------------
    // Cycle wires never carry `.transform`, so none of this ever renders for
    // them (D-I1: cycle canvas is byte-identical — no transform affordances).
    _num(x) { const s = String(x ?? ""); return s.indexOf(".") >= 0 ? s.replace(/\.?0+$/, "") : s; }
    // D-I2 badge vocabulary
    transformGlyph(tf) {
        if (!tf) return "=";
        switch (tf.type) {
            case "multiply": return "×" + this._num(tf.value);
            case "divide": return "÷" + this._num(tf.value);
            case "add": return "+" + this._num(tf.value);
            case "subtract": return "−" + this._num(tf.value);   // U+2212 minus
            case "round": return "≈" + this._num(tf.decimals);   // ≈
            case "abs": return "|x|";
            case "default_if_empty": return "?" + this._num(tf.value);
            case "python": return "ƒ";                            // ƒ
            default: return "=";
        }
    }
    // tfDraft uses the record field names; transformGlyph wants {type,value,decimals}
    get tfDraftGlyph() {
        const d = this.ui.tfDraft;
        return this.transformGlyph({ type: d.transformation_type,
                                     value: d.transformation_value,
                                     decimals: d.transformation_decimals });
    }
    get tfNeedsValue() {
        return ["multiply", "divide", "add", "subtract", "default_if_empty"]
            .includes(this.ui.tfDraft.transformation_type);
    }
    get tfNeedsDecimals() { return this.ui.tfDraft.transformation_type === "round"; }
    /**
     * Where the popover hangs — kept inside the board on purpose.
     *
     * The board CLIPS now (WP-1.2). The popover lives OUTSIDE that clip, as a
     * sibling, so it can never be cut in half; what it still has to do is stay
     * on screen, which on a wire docked at the very top or the far right it
     * would not. So the anchor is clamped to a half-width margin and the
     * popover flips above its wire when there is no room below it.
     */
    get tfAnchor() {
        const g = this.ui.geom.find(x => x.id === this.ui.tfOpen);
        const el = this.rootRef.el;
        const w = el ? el.clientWidth : 0, h = el ? el.clientHeight : 0;
        if (!g) { return { x: w / 2, y: h / 2, flip: false }; }
        const HALF = 158, POP = 250;
        return {
            x: w ? Math.max(HALF, Math.min(w - HALF, g.hx)) : g.hx,
            y: g.hy,
            flip: h > 0 && g.hy + POP > h,
        };
    }
    get tfTypeOptions() {
        return [
            { v: "direct", l: "Direct copy" },
            { v: "multiply", l: "Multiply by" },
            { v: "divide", l: "Divide by" },
            { v: "add", l: "Add" },
            { v: "subtract", l: "Subtract" },
            { v: "round", l: "Round to decimals" },
            { v: "abs", l: "Absolute value" },
            { v: "default_if_empty", l: "Default if empty" },
        ];
    }
    openTransform(g) {
        if (!g || !g.transform) return;
        this.ui.selWire = g.id;
        this.ui.tfOpen = g.id;
        this._tfRef = g.ref;
        this.ui.tfPy = !!g.transform.python;
        this.ui.tfDraft = {
            transformation_type: g.transform.type || "direct",
            transformation_value: g.transform.value ?? 0,
            transformation_decimals: g.transform.decimals ?? 2,
        };
        this.ui.tfPreview = {
            sample: g.transform.sample, result: null,
            error: g.transform.error ? (g.transform.error_msg || "This Python transform last failed — it fell back to the default value.") : null,
            loading: false,
        };
        this.ui.tfSaving = false;
        if (this.props.canEdit && !this.ui.tfPy) this._tfPreview();
    }
    closeTransform() {
        this.ui.tfOpen = null;
        this._tfToken++;                       // supersede any in-flight preview
        if (this._tfTimer) { clearTimeout(this._tfTimer); this._tfTimer = null; }
    }
    // C8 — 260 ms debounce + monotonic supersede token (never stack previews)
    _tfPreview() {
        if (!this.props.onTransformPreview) return;
        if (this._tfTimer) clearTimeout(this._tfTimer);
        const token = ++this._tfToken;
        this.ui.tfPreview = { ...this.ui.tfPreview, loading: true };
        this._tfTimer = setTimeout(async () => {
            const draft = {
                transformation_type: this.ui.tfDraft.transformation_type,
                transformation_value: parseFloat(this.ui.tfDraft.transformation_value) || 0,
                transformation_decimals: parseInt(this.ui.tfDraft.transformation_decimals, 10) || 0,
            };
            let res;
            try { res = await this.props.onTransformPreview(this._tfRef, draft); }
            catch (e) { res = { ok: false, error: "Preview failed" }; }
            if (token !== this._tfToken) return;      // superseded — drop
            this.ui.tfPreview = (res && res.ok)
                ? { sample: res.sample, result: res.result, error: null, loading: false }
                : { sample: this.ui.tfPreview.sample, result: null,
                    error: (res && (res.error || res.msg)) || "Preview failed", loading: false };
        }, 260);
    }
    onDraftType(ev) { this.ui.tfDraft.transformation_type = ev.target.value; this._tfPreview(); }
    onDraftValue(ev) { this.ui.tfDraft.transformation_value = ev.target.value; this._tfPreview(); }
    onDraftDecimals(ev) { this.ui.tfDraft.transformation_decimals = ev.target.value; this._tfPreview(); }
    async saveTransform() {
        if (!this.props.canEdit || this.ui.tfPy || !this.props.onTransformSave) return;
        this.ui.tfSaving = true;
        const vals = {
            transformation_type: this.ui.tfDraft.transformation_type,
            transformation_value: parseFloat(this.ui.tfDraft.transformation_value) || 0,
            transformation_decimals: parseInt(this.ui.tfDraft.transformation_decimals, 10) || 0,
        };
        let res;
        try { res = await this.props.onTransformSave(this._tfRef, vals); }
        catch (e) { res = { ok: false, msg: "Save failed" }; }
        this.ui.tfSaving = false;
        if (res && res.ok === false) {
            this.ui.tfPreview = { ...this.ui.tfPreview, error: res.msg || "Save failed" };
            return;
        }
        this.closeTransform();     // parent reloads the board → badge re-renders
    }

    // ---- keyboard -------------------------------------------------------
    // item focus → Enter arms → Enter on the other side draws; plus the wire
    // layer: `w` walks the wires, ←/→ jump to that wire's two ends, `/` puts
    // the cursor in the search box of the column under the pointer.
    onKeydown(ev) {
        if (ev.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(ev.target.tagName)) {
            const ref = (this.ui.hoverCol === "right" ? this.rqRef : this.lqRef).el;
            if (ref) { ev.preventDefault(); ref.focus(); ref.select(); return; }
        }
        if (this.ui.selWire) {
            const g = this.ui.geom.find((x) => x.id === this.ui.selWire);
            if (g && (ev.key === "ArrowLeft" || ev.key === "ArrowRight")) {
                ev.preventDefault(); ev.stopPropagation();
                this.jumpTo(ev.key === "ArrowLeft" ? "left" : "right", g);
                return;
            }
            if (g && ev.key === "Enter" && g.transform) {
                ev.preventDefault(); ev.stopPropagation();
                this.openTransform(g); return;
            }
            if (ev.key === "Escape") { this.ui.selWire = null; ev.stopPropagation(); return; }
        }
        if (ev.key === "w" || ev.key === "W") {
            const list = this.ui.geom;
            if (!list.length) { return; }
            const at = list.findIndex((x) => x.id === this.ui.selWire);
            const step = ev.shiftKey ? -1 : 1;
            const next = list[(at + step + list.length + (at < 0 ? 1 : 0)) % list.length];
            this.ui.selWire = next ? next.id : null;
            ev.preventDefault(); ev.stopPropagation();
            return;
        }
        const list = this.ui.focusSide === "left" ? this.leftView : this.rightView;
        if (!list.length) return;
        let idx = list.findIndex(i => i.id === this.ui.focusId);
        if (idx === -1) idx = 0;
        const set = (i) => { this.ui.focusId = list[Math.max(0, Math.min(list.length - 1, i))].id; };
        switch (ev.key) {
            case "ArrowDown": ev.preventDefault(); set(idx + 1); break;
            case "ArrowUp": ev.preventDefault(); set(idx - 1); break;
            case "ArrowRight": case "ArrowLeft":
                ev.preventDefault();
                this.ui.focusSide = this.ui.focusSide === "left" ? "right" : "left";
                { const l2 = this.ui.focusSide === "left" ? this.leftView : this.rightView;
                  this.ui.focusId = (l2[0] || {}).id ?? null; }
                break;
            case "Enter":
                ev.preventDefault();
                if (this.ui.focusSide === "left") this.clickLeft(this.ui.focusId);
                else this.clickRight(this.ui.focusId);
                break;
            case "Escape": this.ui.armedLeft = null; break;
            default: return;
        }
        ev.stopPropagation();
    }
}
