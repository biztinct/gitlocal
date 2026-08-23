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
import { _t } from "@web/core/l10n/translation";
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
        // COLROLES P3 — three additions, all generic and all opt-in, so every board
        // that does not pass them renders exactly as it did.
        //
        // `groupFilter` is a PARENT-OWNED display filter over the left column's
        // `group` key. It deliberately runs through `_passes` rather than trimming
        // `props.leftItems` before they arrive: an end hidden by a filter docks on
        // the column edge and is counted, where an item missing from the list
        // entirely counts as `gone` and reads as a broken wire (C5's whole lesson).
        groupFilter: { type: String, optional: true },
        // (item) — a card the adapter marked `meta.wirable === false` was clicked.
        onLeftBlocked: { type: Function, optional: true },
        // (item) — the card's `meta.action` was pressed.
        onLeftAction: { type: Function, optional: true },
        // () — the column's "clear" verb must be able to clear a filter it does not
        // own, or "clear" stops meaning clear (W153).
        onClearGroupFilter: { type: Function, optional: true },
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
            // C7 — the arrival ring, per COLUMN rather than one at a time. The
            // whole point of the new gesture is that both ends answer at once;
            // a single `{side, id}` could only ever light one of them.
            flash: { left: null, right: null },
            // C7 — "one end of this wire is behind a filter". An affordance,
            // not a silent filter-clear: the user asked to SEE the wire, and
            // throwing away the search they typed to do it is a second, larger
            // surprise. `{id, sides:[…]}` or null.
            reveal: null,
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
            // MAPFIX D3 — the card's action MENU. One open at a time, anchored to
            // the trigger that opened it:
            // `{id, kind, side, trigger, label, acts, values, total, x, y, flip}`.
            // MAPFIX E1 — `kind` is why there is still only one of these. The
            // right column's value list is the SAME popover with a different body
            // and a different trigger to hand focus back to; a second
            // implementation would be a second set of placement bugs (MF27).
            menu: null,
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
        this.menuRef = useRef("menu");
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
                this.ui.reveal = null;
            }
            // COLROLES P3, CR9's family — a parent-owned display filter changes what
            // is about to render, and focus/arming resolved against the OLD list are
            // then pointing at a card that stops existing this frame. Relocate them
            // here, before the render, exactly as GridStudio does for the lens.
            if (next.groupFilter !== this.props.groupFilter) {
                this.ui.armedLeft = null;
                if (this.ui.focusSide === "left") { this.ui.focusId = null; }
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
        } else if (cmd.kind === "armLeft" && cmd.leftId != null) {
            // MAPFIX B2 — "Send to a field instead…" is not a write. It is a
            // request to DRAW, so it arms the card the host names and puts the
            // cursor where the answer is: the right column's search box. Doing the
            // write on the card's behalf would pick the destination for the user,
            // which is the one thing this verb must not do.
            this.ui.armedLeft = cmd.leftId;
            this.ui.focusSide = "right";
            // MAPFIX D1 — `focusId` is shared by both columns, and it is a LEFT id
            // at this exact moment. Dropping it is what stops the next Enter from
            // resolving to a card on the other side of the board.
            this.ui.focusId = null;
            this.ui.selWire = null;
            requestAnimationFrame(() => {
                const el = this.rqRef.el;
                if (el) { el.focus(); el.select(); }
            });
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
        this._qt[side] = setTimeout(() => {
            this.ui.qa[side] = this.ui.q[side];
            // Typing in a column's search box IS working in that column, so the
            // focus ring belongs there. Without this, typing in the right box
            // while `focusSide` was still "left" left Enter acting on a left card
            // the reader was not looking at — the same class of mismatch as D1,
            // one step further back.
            this.ui.focusSide = side;
            // MAPFIX D1 — keep the focus ring on a card that is still on screen.
            // Enter acts on the focused card of the focused side, so a focus left
            // pointing at a row the search has just hidden would make Enter act on
            // the top hit with nothing on screen saying so. Relocating here paints
            // the card Enter is about to use, which is the honest version of the
            // "type, then press Enter" gesture the search box invites.
            this._relocateFocus(side);
        }, 120);
    }
    _relocateFocus(side) {
        if (this.ui.focusSide !== side) { return; }
        const view = side === "left" ? this.leftView : this.rightView;
        const still = view.some((i) => String(i.id) === String(this.ui.focusId));
        if (still) { return; }
        this.ui.focusId = view.length ? view[0].id : null;
    }
    clearSearch(side) {
        if (this._qt[side]) { clearTimeout(this._qt[side]); }
        this.ui.q[side] = ""; this.ui.qa[side] = "";
    }
    onSearchKey(side, ev) {
        // MAPFIX D2 — this used to be `stopPropagation(); clearSearch(side)`
        // unconditionally, so Escape inside a search box could never reach the
        // canvas handler that disarms a component. "Send to a field instead…"
        // puts the cursor in this very box and the banner promises "Esc to
        // cancel" — the one flow in which the promise was impossible to keep.
        // The ladder in `_escape` decides; the search is one of its rungs.
        if (ev.key === "Escape") { this._escape(ev, side); }
    }
    /**
     * What Escape means, in one place, in priority order.
     *
     * It has to be one place because Escape arrives from four DOM nodes (the two
     * search inputs, the menu, the canvas root) and "the banner says Esc cancels"
     * is a promise about the KEY, not about where the cursor happens to be.
     *
     *   1. an open card menu closes (and hands focus back to its trigger);
     *   2. an open transform popover closes;
     *   3. an ARMED component disarms — this is the promise on the banner, and
     *      it outranks the search box because the banner is what is on screen;
     *   4. a search box with text in it clears;
     *   5. a selected wire deselects, with its reveal bar.
     *
     * Returns true when it consumed the key, so the caller can stop it there
     * rather than letting a second handler act on the same press.
     */
    _escape(ev, side = null) {
        let done = true;
        if (this.ui.menu) {
            this.closeItemMenu(true);
        } else if (this.ui.tfOpen) {
            this.closeTransform();
        } else if (this.ui.armedLeft != null) {
            // the wire preview, the drop hints and the banner are all rendered
            // off `armedLeft`; the reveal bar is a claim about a filter that the
            // cancelled gesture no longer needs.
            this.ui.armedLeft = null;
            this.ui.reveal = null;
        } else if (side && (this.ui.q[side] || this.ui.qa[side])) {
            this.clearSearch(side);
        } else if (!side && (this.ui.q.left || this.ui.q.right)) {
            // Escape from a card or the board background still clears a search —
            // there is exactly one column filtered in practice, and clearing it
            // is what the reader expects the key to do once nothing is armed.
            this.clearSearch(this.ui.q.right ? "right" : "left");
        } else if (this.ui.selWire) {
            this.ui.selWire = null;
            this.ui.reveal = null;
        } else {
            done = false;
        }
        if (done && ev) { ev.preventDefault(); ev.stopPropagation(); }
        return done;
    }
    setFilter(side, v) { this.ui.f[side] = this.ui.f[side] === v ? "all" : v; }
    clearFilters(side) {
        this.clearSearch(side); this.ui.f[side] = "all";
        if (side === "left" && this.props.groupFilter && this.props.onClearGroupFilter) {
            this.props.onClearGroupFilter();
        }
        // A reveal bar is a claim about a filter. Drop the half of the claim
        // this clear just made false, and the whole bar when nothing is left
        // for it to say — a warning that outlives its cause is the thing that
        // teaches readers to stop reading warnings (W153).
        const r = this.ui.reveal;
        if (r) {
            const sides = r.sides.filter((s) => s !== side);
            this.ui.reveal = sides.length ? { ...r, sides } : null;
        }
    }
    hasFilter(side) {
        if (side === "left" && this.props.groupFilter) { return true; }
        return this.ui.f[side] !== "all" || !!this.ui.qa[side];
    }

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
        // COLROLES P3 — the host's lane filter. Left column only: the right column's
        // groups are destinations, and hiding one would hide the very card the
        // filtered left cards need to be wired to.
        if (side === "left" && this.props.groupFilter
                && (it.group || "") !== this.props.groupFilter) {
            return false;
        }
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

    /**
     * Where this card came from — Integrations Cycle 6.
     *
     * `null` for a field the connector has actually delivered, and that
     * silence is deliberate: the common case must not be decorated, or the
     * chips stop meaning "read me". Four things can need saying:
     *
     *   expected  the vendor's catalogue says this feed delivers it, and it
     *             has not been seen yet because nothing has synced;
     *   computed  Payobook itself produces it, from a transformation rule;
     *   not sent  a catalogue field the feed HAS run and did not carry — real
     *             drift, and the only one of the four that is a warning;
     *   Payobook field  the last-resort layer, saying so out loud. This is the
     *             chip whose absence was the whole defect: 206 `hr.employee`
     *             columns printed under "FROM — ZOHO PEOPLE (ABM)". The chip
     *             names THIS product, not the platform underneath it (C7 WP-1):
     *             the reader is being told the field is one of ours rather than
     *             one of the vendor's, and the engine's name is not part of
     *             that sentence.
     *
     * Adapters that predate this send no `prov` at all, and `undefined` falls
     * through to `null` — every other board renders exactly as it did.
     */
    provChip(it) {
        if (!it || !it.prov) { return null; }
        if (it.drift) {
            return { label: "not sent", tone: "warn",
                     hint: "This feed has synced, and did not carry this field. "
                           + "It may have been renamed or switched off at the source." };
        }
        if (it.prov === "catalog") {
            return it.provKind === "computed"
                ? { label: "computed", tone: "calc",
                    hint: it.note || "Payobook computes this from the records this feed returns." }
                : { label: "expected", tone: "exp",
                    hint: it.note
                          ? `Expected from the vendor's catalogue. ${it.note}`
                          : "Expected from the vendor's catalogue. The first sync will confirm it." };
        }
        if (it.prov === "odoo") {
            return { label: "Payobook field", tone: "odoo",
                     hint: "This is one of Payobook's own employee fields, not a "
                           + "field this source has told us about." };
        }
        if (it.prov === "mapping") {
            return { label: "mapped elsewhere", tone: "odoo",
                     hint: "Shown because a mapping names it. It arrives on another "
                           + "feed, or on none this board knows about." };
        }
        return null;
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

    /**
     * ===================== C7 — one gesture brings BOTH ends home ===========
     *
     * Cycle 5 put a `‹` and a `›` on every hub: press one, that column scrolls
     * to that end. Two controls, two presses, and after the first one the other
     * end had usually left the screen — so the reader never actually saw the
     * connection, only its two halves in sequence.
     *
     * Double-clicking the wire (or its hub) scrolls BOTH columns at once and
     * flashes BOTH cards, which is the only way a two-hundred-row board can
     * answer "where does this go?" in one frame. The arrows are gone; the pill
     * is smaller for it, and it now carries only meaning (the transform glyph,
     * or a confidence and its two verbs) rather than navigation.
     *
     * `←`/`→` still walk to a single end from the keyboard — that gesture was
     * never the problem, and losing it would cost the one-ended case nothing
     * was wrong with.
     */
    centreBoth(g, ev) {
        if (ev) { ev.stopPropagation(); ev.preventDefault(); }
        if (!g) { return; }
        this.ui.selWire = g.id;
        // Read the CURRENT geometry rather than the object the template closed
        // over: between the render and the double-click a filter may have moved
        // an end behind it, and acting on a stale `hiddenL` would scroll to a
        // card that is no longer in the list.
        const cur = this.ui.geom.find((x) => x.id === g.id) || g;
        const hidden = [];
        if (cur.hiddenL) { hidden.push("left"); }
        if (cur.hiddenR) { hidden.push("right"); }
        // An end behind a filter cannot be scrolled to, and clearing the
        // filter without being asked would throw away a search the user typed.
        // Say so, offer the clear — and still centre the end that IS reachable,
        // so the gesture is never a no-op (W40: never grey out in silence).
        this.ui.reveal = hidden.length ? { id: g.id, sides: hidden } : null;
        this._centre(cur, { left: !cur.hiddenL, right: !cur.hiddenR });
    }

    /** The reveal bar's verb: drop the filters that hide an end, then centre. */
    revealBoth() {
        const r = this.ui.reveal;
        if (!r) { return; }
        for (const side of r.sides) { this.clearFilters(side); }
        this.ui.reveal = null;
        // One frame for the just-cleared columns to render their rows, then a
        // second recompute so `ui.geom` knows the ends are anchorable again.
        requestAnimationFrame(() => {
            this._recompute();
            const g = this.ui.geom.find((x) => x.id === r.id);
            if (g) { this._centre(g, { left: true, right: true }); }
        });
    }
    dismissReveal() { this.ui.reveal = null; }

    /**
     * Scroll each requested column so its end of this wire sits in the middle,
     * and ring both cards.
     *
     * Deliberately NOT `scrollIntoView` — see `jumpTo`. `Math.max(0, …)` and
     * the browser's own clamp at the bottom are what make an end near a list
     * boundary scroll AS CLOSE AS IT CAN rather than refusing: the card is then
     * not centred, but it is on screen, and it still flashes.
     */
    _centre(g, want) {
        const flash = { left: null, right: null };
        const go = () => {
            for (const side of ["left", "right"]) {
                if (!want[side]) { continue; }
                const body = side === "left" ? this.lbodyRef.el : this.rbodyRef.el;
                const id = side === "left" ? g.leftId : g.rightId;
                const el = this._itemEl(body, id);
                if (!body || !el) { continue; }
                const top = el.offsetTop - (body.clientHeight - el.offsetHeight) / 2;
                body.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
                flash[side] = id;
            }
            this.ui.flash = flash;
            if (this._flashTimer) { clearTimeout(this._flashTimer); }
            this._flashTimer = setTimeout(
                () => { this.ui.flash = { left: null, right: null }; }, 950);
        };
        requestAnimationFrame(go);
    }

    /** What the reveal bar says. One sentence, one msgid (W80). */
    get revealText() {
        const r = this.ui.reveal;
        if (!r) { return ""; }
        if (r.sides.length === 2) {
            return "Both ends of this wire are hidden by the column filters.";
        }
        return r.sides[0] === "left"
            ? "The source end of this wire is hidden by this column's filter."
            : "The target end of this wire is hidden by this column's filter.";
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
        this.ui.selWire = g.id;
        // A DOCK CHIP's target is a wire the reader cannot see an end of, and
        // the chip's own label already says "hidden by filter" — so pressing it
        // IS the request to clear. That is a different sentence from the wire
        // gesture, which asks to see a connection and gets the reveal bar
        // instead (C7).
        if (side === "left" ? g.hiddenL : g.hiddenR) { this.clearFilters(side); }
        // one frame, so a just-cleared filter has rendered its rows first
        this._centre(g, { left: side === "left", right: side === "right" });
    }
    isFlashing(side, id) {
        const f = this.ui.flash;
        return !!(f && f[side] != null && String(f[side]) === String(id));
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
    /**
     * The same for the RIGHT column — COLROLES P3.
     *
     * It exists because the employee board's right column stopped being one list.
     * The four bank cards are not fields of anything; they are the parts of a record
     * this board assembles, and printing them among two hundred field names without
     * a heading is exactly the "Unassigned looks like Employees" failure the left
     * grouping was built to prevent.
     */
    rightGroupHead(items, i) {
        const g = (items[i] || {}).group || "";
        if (!g) { return ""; }
        const prev = i > 0 ? (items[i - 1].group || "") : "";
        return g === prev ? "" : g;
    }

    // ---- per-item badges and actions (COLROLES P3) ---------------------
    /** `{label, tone, hint}` for a card the adapter has annotated, else null. */
    badge(it) {
        const m = it && it.meta;
        if (!m || !m.badge) { return null; }
        return { label: m.badge, tone: m.badgeTone || "", hint: m.badgeHint || "" };
    }
    /** A card is wirable unless the adapter says otherwise (absent ⇒ true). */
    isWirable(it) {
        return !(it && it.meta && it.meta.wirable === false);
    }
    itemAction(it) {
        return (this.props.onLeftAction && it && it.meta && it.meta.action) || null;
    }
    /**
     * The verbs a card offers — MAPFIX B2.
     *
     * Phase 3 gave a card ONE verb, because a card had one thing it could become.
     * A column now has three or four possible destinations and the board's job is
     * to make each of them a click rather than a piece of knowledge, so the adapter
     * sends a list. `meta.action` is still honoured on its own: the Mapping Studio
     * and every other adapter that predates this renders exactly as it did.
     */
    itemActions(it) {
        if (!this.props.onLeftAction || !it || !it.meta) { return []; }
        if (Array.isArray(it.meta.actions)) { return it.meta.actions; }
        return it.meta.action ? [it.meta.action] : [];
    }
    runItemAction(it, act, ev) {
        if (ev) { ev.stopPropagation(); }
        if (this.props.onLeftAction) { this.props.onLeftAction(it, act); }
    }
    /**
     * A note the adapter attached to a card — MAPFIX D4/D5.
     *
     * Generic on purpose: the canvas knows nothing about selections or many2one
     * fields, only that a card may carry one short sentence about what it will
     * ACCEPT, a longer one for its tooltip, and a tone. Every board that sends
     * none renders exactly as it did.
     */
    note(it) {
        const n = it && it.meta && it.meta.note;
        if (!n || !n.text) { return null; }
        return { text: n.text, title: n.title || n.text, tone: n.tone || "" };
    }
    /**
     * The full list behind a TRUNCATED note — MAPFIX E1.
     *
     * The adapter sends `values` only when the inline text actually hid
     * something, so "has values" and "is truncated" are the same condition on
     * both sides of the wire, and a note that already shows everything stays
     * inert text. An affordance that opens a list of what you are already
     * reading is worse than none.
     */
    noteValues(it) {
        const n = it && it.meta && it.meta.note;
        const v = n && n.values;
        return Array.isArray(v) && v.length ? v : null;
    }
    noteMenuLabel(it) {
        const n = (it && it.meta && it.meta.note) || {};
        return _t("Show all %(n)s values for %(label)s",
                  { n: n.total || (n.values || []).length, label: (it && it.label) || "" });
    }
    /**
     * The one sentence under the value list. ONE `_t` call rather than a
     * template with numbers interpolated between text nodes — a translator
     * handed "Showing the first" and "of" as separate strings cannot put them
     * back together in a language that orders them differently.
     */
    valuesFooter() {
        const m = this.ui.menu || {};
        const shown = (m.values || []).length;
        const hint = _t("The code beside a value is what the file must contain.");
        if ((m.total || shown) > shown) {
            return _t("%(hint)s Showing the first %(shown)s of %(total)s.",
                      { hint, shown, total: m.total });
        }
        return hint;
    }
    isNoteOpen(it) {
        return !!(this.ui.menu && this.ui.menu.kind === "values"
                  && it && String(this.ui.menu.id) === String(it.id));
    }
    /**
     * Open the value list in the popover Phase D already built.
     *
     * The `stopPropagation` is the whole test case. This note lives INSIDE a
     * card whose `t-on-click` is `clickRight(it.id)`, and `clickRight` draws a
     * wire whenever a left card is armed — so without it, reading what a
     * destination accepts would MAP a column to it. Reading is not writing, and
     * on this board the two are one pixel apart.
     */
    toggleNoteMenu(it, ev) {
        if (ev) { ev.stopPropagation(); ev.preventDefault(); }
        if (this.isNoteOpen(it)) { this.closeItemMenu(); return; }
        const values = this.noteValues(it);
        if (!values) { return; }
        const n = it.meta.note;
        this._openMenu(ev, {
            id: it.id, kind: "values", side: "right", trigger: ".mc-item-note",
            label: it.label || "", acts: [], values,
            total: n.total || values.length,
        });
    }

    // ---- MAPFIX D3 — the card's actions, in a menu ----------------------
    /**
     * Why a MENU and not three pills on the card.
     *
     * Phase B put three verbs on a ~300px card. In the flow they reserved their
     * width even at `opacity: 0` and squeezed the name to one character (MF13);
     * lifted out of the flow they stopped doing that and started COVERING the
     * name and code instead, which is the defect this phase was called on. Both
     * failures are the same failure: an affordance whose width depends on how
     * many verbs there happen to be cannot share a line with the text.
     *
     * So the card carries ONE trigger of a FIXED width, in the flow, where it can
     * be measured and where the label simply ellipsises beside it — the name and
     * the code are legible in every state, hover included, which is the only
     * thing that can be asserted from a bounding box. The trigger is always
     * present (dimmed at rest): hover-only discovery has now proved fragile
     * twice, and a permanently-visible 14px glyph is a fraction of the clutter
     * three labelled pills were.
     *
     * The menu itself hangs OUTSIDE `.mc-board`, like the transform popover and
     * for the same reason — the board clips, and a menu cut in half is worse
     * than no menu.
     */
    itemActionsLabel(it) {
        return _t("Actions for %s", (it && it.label) || "");
    }
    isMenuOpen(it) {
        return !!(this.ui.menu && (this.ui.menu.kind || "actions") === "actions"
                  && it && String(this.ui.menu.id) === String(it.id));
    }
    toggleItemMenu(it, ev) {
        if (ev) { ev.stopPropagation(); ev.preventDefault(); }
        if (this.isMenuOpen(it)) { this.closeItemMenu(); return; }
        const acts = this.itemActions(it);
        if (!acts.length) { return; }
        this._openMenu(ev, { id: it.id, kind: "actions", side: "left",
                             trigger: ".mc-item-more", label: it.label || "", acts });
    }
    /**
     * ONE popover, two payloads — MAPFIX E1.
     *
     * The value list does not get a second popover implementation. It gets THIS
     * one: the same `ui.menu` state, the same scrim, the same anchoring and the
     * same measure-then-place (MF27), differing only in what the body renders
     * and which trigger focus goes back to. A second implementation would be a
     * second set of placement bugs, and the first set took a live screenshot to
     * find.
     */
    _openMenu(ev, spec) {
        const root = this.rootRef.el;
        const btn = ev && ev.currentTarget;
        const W = 264;
        let anchor = { top: 12, bottom: 12, right: W + 12 };
        if (root && btn) {
            const rb = root.getBoundingClientRect();
            const r = btn.getBoundingClientRect();
            anchor = { top: r.top - rb.top, bottom: r.bottom - rb.top,
                       right: r.right - rb.left };
        }
        this.ui.menu = {
            kind: "actions", side: "left", trigger: ".mc-item-more", acts: [],
            ...spec, anchor,
            x: Math.max(8, anchor.right - W), y: anchor.bottom + 6, flip: false,
        };
        // The final placement needs the menu's REAL height, and a hint of three
        // sentences is a third taller than an estimate says. So: render, measure,
        // then correct — two frames, because OWL patches on the first one.
        requestAnimationFrame(() => requestAnimationFrame(() => this._placeMenu()));
    }
    /** Measure the rendered menu, keep it inside the board, focus its first row. */
    _placeMenu() {
        const el = this.menuRef.el, root = this.rootRef.el;
        if (!el || !root || !this.ui.menu) { return; }
        const a = this.ui.menu.anchor;
        const rb = root.getBoundingClientRect();
        const h = el.offsetHeight, w = el.offsetWidth;
        let y = a.bottom + 6, flip = false;
        if (y + h > rb.height - 8) {
            // above the trigger if there is room there, otherwise as low as the
            // board allows — never off the bottom, and never clipped by the
            // overlay's own footer bar.
            flip = a.top - h - 6 >= 8;
            y = flip ? a.top - h - 6 : Math.max(8, rb.height - 8 - h);
        }
        this.ui.menu = { ...this.ui.menu, flip,
                         x: Math.max(8, Math.min(rb.width - w - 8, a.right - w)), y };
        // A menu that opens with focus left behind is a menu the keyboard cannot
        // use — and this affordance had to be keyboard-reachable by design. The
        // value list has no rows to focus, so the scroller itself takes it: that
        // is what makes Page-Down and Escape work from inside the popover.
        const first = el.querySelector(".mc-menu__i") || el.querySelector(".mc-menu__vals");
        if (first) { first.focus(); }
    }
    closeItemMenu(restoreFocus = false) {
        const menu = this.ui.menu;
        this.ui.menu = null;
        if (!restoreFocus || !menu || menu.id == null) { return; }
        requestAnimationFrame(() => {
            const body = menu.side === "right" ? this.rbodyRef.el : this.lbodyRef.el;
            const card = this._itemEl(body, menu.id);
            const btn = card && card.querySelector(menu.trigger || ".mc-item-more");
            if (btn) { btn.focus(); }
        });
    }
    runMenuAction(act) {
        const menu = this.ui.menu;
        // A value row is not a verb. Nothing in the template calls this for the
        // value list, and this line is what keeps that true if something later does.
        if (!menu || menu.kind === "values") { return; }
        const it = this.props.leftItems.find((x) => String(x.id) === String(menu.id));
        this.closeItemMenu();
        if (it && this.props.onLeftAction) { this.props.onLeftAction(it, act); }
    }
    /** ↑/↓ walk the rows, Home/End jump; Escape is handled by `_escape`. */
    onMenuKeydown(ev) {
        // MAPFIX E1 — the VALUE list has no rows to walk, it has a scroller. Give
        // it the keys a scroller is expected to answer, and stop them there: the
        // board's own handler `preventDefault`s ArrowUp/Down (to move the focus
        // ring), so without this a 120-value list could not be read with the
        // keyboard at all while the ring wandered behind an open dialog.
        if (this.ui.menu && this.ui.menu.kind === "values") {
            const box = this.menuRef.el && this.menuRef.el.querySelector(".mc-menu__vals");
            if (!box) { return; }
            const step = { ArrowDown: 40, ArrowUp: -40,
                           PageDown: box.clientHeight - 24, PageUp: -(box.clientHeight - 24) };
            if (ev.key in step) { box.scrollTop += step[ev.key]; }
            else if (ev.key === "Home") { box.scrollTop = 0; }
            else if (ev.key === "End") { box.scrollTop = box.scrollHeight; }
            else { return; }
            ev.preventDefault(); ev.stopPropagation();
            return;
        }
        if (!/^(ArrowDown|ArrowUp|Home|End)$/.test(ev.key)) { return; }
        const rows = Array.from(
            (this.menuRef.el && this.menuRef.el.querySelectorAll(".mc-menu__i")) || []);
        if (!rows.length) { return; }
        ev.preventDefault(); ev.stopPropagation();
        const at = rows.indexOf(document.activeElement);
        let next = 0;
        if (ev.key === "ArrowDown") { next = (at + 1 + rows.length) % rows.length; }
        else if (ev.key === "ArrowUp") { next = (at - 1 + rows.length) % rows.length; }
        else if (ev.key === "End") { next = rows.length - 1; }
        rows[next].focus();
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
        this.ui.focusSide = "left"; this.ui.focusId = id;
        if (!this.props.canEdit) { return; }
        // COLROLES P3 — a card the adapter marked non-wirable ANSWERS rather than
        // doing nothing. Arming it would let the next right-click draw a wire the
        // server is going to refuse, which is a worse lie than the refusal.
        const it = this.props.leftItems.find((x) => String(x.id) === String(id));
        if (it && !this.isWirable(it)) {
            this.ui.armedLeft = null;
            if (this.props.onLeftBlocked) { this.props.onLeftBlocked(it); }
            return;
        }
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
        // MAPFIX D2 — Escape is answered FIRST and by one ladder, wherever the
        // cursor is. It used to be two `case "Escape"` branches buried below,
        // both of them unreachable from the search box.
        if (ev.key === "Escape") { this._escape(ev, null); return; }
        // MAPFIX E1 — a key that belongs to a CONTROL belongs to that control.
        //
        // This handler is bound to the board ROOT, so every keystroke inside it
        // arrives here — including Enter on a focused BUTTON. Enter on a button
        // fires the button's own click, and it ALSO reached `case "Enter"` below,
        // which acts on whichever card the focus ring is on: it armed a column,
        // and with a column already armed it DREW A WIRE. So a keyboard reader
        // opening a value list to check a code would have mapped something on the
        // way in — the same defect E1 guards against on the mouse side, one input
        // device over. Found live, on the ⋮ trigger's twin (MF33).
        //
        // Two rungs, because one was not enough. An OPEN popover owns every key
        // it receives — `.mc-menu__vals` is a scrolling DIV, which the tag test
        // below cannot see, so Enter inside the value list still reached
        // `case "Enter"` and drew the wire the popover exists to avoid; and the
        // board's own ArrowUp/Down `preventDefault` stopped the list scrolling at
        // all. Escape is answered ABOVE this, so the ladder still closes it.
        //
        // INPUT is deliberately NOT in the tag list: "type in the search box,
        // press Enter to wire the top hit" is a gesture the board promises, and
        // `_relocateFocus` exists to keep it honest (MF25).
        if (this.ui.menu && ev.target && ev.target.closest
                && ev.target.closest(".mc-menu")) {
            return;
        }
        if ((ev.key === "Enter" || ev.key === " ")
                && /^(BUTTON|A)$/.test(ev.target.tagName)) {
            return;
        }
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
            // C7 — Enter is the keyboard twin of the double-click, so the
            // gesture is not mouse-only. The transform editor moves to `t`,
            // which it has to: with the `‹ ›` zones gone, Enter is the only key
            // that can mean "show me this wire" and a gesture reachable by
            // exactly one input device is not reachable.
            if (g && ev.key === "Enter") {
                this.centreBoth(g, ev); return;
            }
            if (g && (ev.key === "t" || ev.key === "T") && g.transform) {
                ev.preventDefault(); ev.stopPropagation();
                this.openTransform(g); return;
            }
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
            // MAPFIX D1 — the CRASH.
            //
            // `ui.focusId` is ONE value shared by both columns. The arrow keys
            // above always resolved it through the focused side's list (falling
            // back to index 0); Enter read it RAW. So with `focusSide === "right"`
            // — which "Send to a field instead…" sets, before putting the cursor
            // in the right column's search box — and `focusId` still holding a
            // LEFT id, Enter called `clickRight(<hr.formula.rule id>)` and sent an
            // integer where the server expects an `f:model:field` spec. It crashed
            // on `.startswith` (the server end is fixed too, defence in depth).
            //
            // Resolving through the list is the whole fix and it is the smaller
            // one: splitting focus into `focusLeftId`/`focusRightId` would touch
            // the template, `_relocateForLens`, both `onWillUpdateProps` branches
            // and every reader of `ui.focusId`, to remove a mismatch that cannot
            // survive this line anyway. `list` is the arrow keys' own, so Enter can
            // now only ever act on a card of the focused side that is on screen —
            // the same card the template is painting `.focus`.
            case "Enter": {
                ev.preventDefault();
                // Resolved STRICTLY — no fall back to index 0 the way the arrows
                // do. Moving a focus ring onto the first row is harmless; drawing
                // a wire to the first row because nothing was focused is a write
                // the reader never asked for. Nothing focused ⇒ Enter does
                // nothing, and `_relocateFocus` is what puts a real focus on the
                // top search hit so the gesture still completes.
                const at = list.findIndex((i) => String(i.id) === String(this.ui.focusId));
                if (at === -1) { break; }
                const it = list[at];
                if (this.ui.focusSide === "left") { this.clickLeft(it.id); }
                else { this.clickRight(it.id); }
                break;
            }
            default: return;
        }
        ev.stopPropagation();
    }
}
