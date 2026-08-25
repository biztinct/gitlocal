/** @odoo-module **/
/**
 * JOURNEY J4 — the three-lane transformation flow.
 *
 *     feed fields  ──read──▶  transformation rule  ──feeds──▶  scheme component
 *
 * This is a NEW component and not a `MappingCanvas` with a third column bolted
 * on, and the reason is the same one J1 recorded when it refused to fork the
 * canvas in the other direction: the canvas' two-lane contract is load-bearing
 * for five tabs, four of which have nothing to do with rules. Teaching it about a
 * middle lane would mean every one of those boards carrying a concept it can
 * never render — and the first bug in the new code would arrive on all five.
 *
 * What IS shared is everything that should be. The geometry is
 * `mapping_geometry.js`, unchanged and unforked: `wireGeometry`, `clampY`,
 * `aggregateDocks`, `spreadHubs` and `itemMatches` are arithmetic over points and
 * they do not care how many columns exist — which is precisely why they were
 * extracted into a pure kernel two cycles ago, and this is the first phase to
 * collect on it. The card chrome, the chips, the dashed-amber warn styling and
 * the dock chips are shared through SCSS (`.tfb` re-uses `mapping.scss`'s
 * vocabulary), not through copied markup.
 *
 * The asymmetry between the two wire sets is deliberate and is the phase's
 * central design decision:
 *
 *   * a rule → component edge is a REAL row — an `hr.integration.field.mapping`
 *     whose `source_field` is an output key, or a `('rule', key)` binding on the
 *     component. It can be drawn and (when it is a wire, not a binding) removed,
 *     through the EXISTING `api_mapping_create` / `api_mapping_delete` adapters.
 *     J4 added no write path of its own;
 *   * a field → rule edge is a DERIVED fact. It is `consumed_field_paths`, which
 *     is computed from the rule's own filter/value/formula spec. There is no row
 *     to create and nothing a drag could write. So these edges are READ-ONLY, and
 *     the board says where they ARE edited (the Rule Composer) rather than
 *     offering a gesture that would have to fail.
 */
import { Component, useState, useRef, onMounted, onWillUnmount, onPatched,
         onWillUpdateProps, useExternalListener } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { wireGeometry, clampY, aggregateDocks, spreadHubs,
         itemMatches } from "./mapping_geometry";

/** Pixels of a lane's band reserved so a clamped wire is not flush to the edge. */
const BAND = 10;

export class TransformFlowBoard extends Component {
    static template = "pb_formula_studio.TransformFlowBoard";
    static props = {
        data: { type: Object },
        configName: { type: String, optional: true },
        canEdit: { type: Boolean, optional: true },
        busy: { type: Boolean, optional: true },
        onOpenRule: { type: Function },
        onDraw: { type: Function },
        onDelete: { type: Function },
        onLineage: { type: Function, optional: true },
        // JOURNEY J5 — the pre-filter a Journey door arrives with. Optional and
        // read ONCE, at mount, into the board's own search: after that the box
        // belongs to the reader, and a prop that kept re-imposing itself would
        // make the search un-clearable for as long as the tab was open.
        focus: { type: String, optional: true },
    };

    setup() {
        this.ui = useState({
            q: this.props.focus || "",
            // the armed rule OUTPUT, waiting for a component to land on. The
            // board's only write gesture, and it is two clicks rather than a
            // drag for the reason the canvas is: a drag over a 250-card column
            // that scrolls is a gesture most people lose halfway through.
            armed: null,
            // what a sealed component said when it refused the wire
            sealedSay: "",
            focus: { lane: "", id: null },
            selWire: null,
            hoverWire: null,
            menu: null,          // {kind:'lineage'|'verbs', ruleId, x, y}
            geom: [], reads: [], docks: [],
        });
        this.rootRef = useRef("root");
        this.qRef = useRef("q");
        this.bodyRefs = { left: useRef("lbody"), mid: useRef("mbody"),
                          right: useRef("rbody") };
        this._raf = null;
        this._recomputes = 0;
        this._recompute = this._recompute.bind(this);
        onMounted(() => {
            this._recompute();
            this._ro = new ResizeObserver(() => this._schedule());
            for (const el of [this.rootRef.el, this.bodyRefs.left.el,
                              this.bodyRefs.mid.el, this.bodyRefs.right.el]) {
                if (el) { this._ro.observe(el); }
            }
        });
        onWillUnmount(() => {
            if (this._ro) { this._ro.disconnect(); }
            if (this._raf) { cancelAnimationFrame(this._raf); }
        });
        onWillUpdateProps((next) => {
            // A different connector or scheme is a different board. A search and
            // an armed output resolved against the old one point at cards that
            // stop existing this frame (CR9's family, and MappingCanvas does the
            // same thing at its own `onWillUpdateProps`).
            if (next.data !== this.props.data) {
                this.ui.armed = null;
                this.ui.selWire = null;
                this.ui.menu = null;
                this.ui.focus = { lane: "", id: null };
            }
        });
        onPatched(() => this._schedule());
        useExternalListener(window, "resize", () => this._schedule());
        // A click anywhere that is not a menu closes the menu. Bound to the
        // window rather than to a scrim so the board underneath stays live.
        useExternalListener(window, "click", () => { this.ui.menu = null; });
    }

    ic(n, s = 14) { return ic(n, s); }

    // ================================================================== data
    get d() { return this.props.data || {}; }
    get counts() { return this.d.counts || {}; }

    get leftView() {
        return (this.d.left || []).filter((f) => this._passes(f));
    }
    get midView() {
        return (this.d.rules || []).filter((r) => this._passesRule(r));
    }
    get rightView() {
        return (this.d.right || []).filter((i) => this._passes(i));
    }

    /**
     * How many of the components ON SCREEN are fed by a rule.
     *
     * The other two lane counts describe the VIEW ("1 field read", "1 rule"), so
     * a third that describes the whole board reads as a contradiction the moment
     * anybody types in the search box — three numbers in a row, two of which
     * answer one question and one of which answers another.
     */
    get fedShown() {
        const fed = new Set((this.d.wires || []).map((w) => String(w.rightId)));
        return this.rightView.filter((i) => fed.has(String(i.id))).length;
    }

    /**
     * ONE query, three lanes — and a lane matches THROUGH its neighbours.
     *
     * Typing `OTHRS150` should not empty the left lane just because no FIELD is
     * called that. The flow is the unit of meaning here: a field stays when a
     * rule that reads it matches, and a component stays when a rule that feeds it
     * matches. Otherwise `/` would break every wire on the board and the reader
     * would be looking at three unrelated filtered lists.
     */
    _passes(item) {
        const q = (this.ui.q || "").trim();
        if (!q) { return true; }
        if (itemMatches(item, q)) { return true; }
        return this._relatedRules(item).some((r) => this._ruleMatches(r, q));
    }

    /**
     * A rule matches through its own lanes, symmetrically.
     *
     * The first cut only asked whether the RULE matched, and the asymmetry was a
     * real defect rather than a tidiness point: searching the name of a field
     * showed the field on its own, with the rule that reads it filtered away and
     * therefore with its read edge suppressed. The reader typed the name of a
     * thing and got a card with a dock chip where its explanation should be.
     * A flow is the unit of meaning on this board in BOTH directions.
     */
    _passesRule(r) {
        const q = (this.ui.q || "").trim();
        if (!q) { return true; }
        if (this._ruleMatches(r, q)) { return true; }
        const left = this.d.left || [];
        const reads = new Set((this.d.reads || [])
            .filter((e) => e.ruleId === r.id).map((e) => String(e.leftId)));
        if (left.some((f) => reads.has(String(f.id)) && itemMatches(f, q))) {
            return true;
        }
        const right = this.d.right || [];
        const feeds = new Set((this.d.wires || [])
            .filter((w) => w.ruleId === r.id).map((w) => String(w.rightId)));
        return right.some((i) => feeds.has(String(i.id)) && itemMatches(i, q));
    }
    _ruleMatches(r, q) {
        return itemMatches({ label: r.label, sublabel: r.key,
                             sample: r.summary, group: r.kind }, q);
    }
    _relatedRules(item) {
        const rules = this.d.rules || [];
        const id = String(item.id);
        const readIds = new Set((this.d.reads || [])
            .filter((e) => String(e.leftId) === id).map((e) => e.ruleId));
        const feedIds = new Set((this.d.wires || [])
            .filter((w) => String(w.rightId) === id).map((w) => w.ruleId));
        return rules.filter((r) => readIds.has(r.id) || feedIds.has(r.id));
    }

    // ================================================================ chrome
    ruleTone(r) {
        if (!r.active) { return "off"; }
        return { severed: "sev", unread: "warn", drift: "drift" }[r.health] || "";
    }

    /** The pill — short, with the whole sentence in the tooltip (J3's pattern). */
    ruleChip(r) {
        if (r.health === "severed") {
            return { label: _t("Lost target"), cls: "tfb-chip sev",
                     hint: _t("A wire from this rule points at a component that is no longer there. "
                              + "Reconnect it from the mapping board.") };
        }
        if (r.health === "unread") {
            return { label: _t("Unread output"), cls: "tfb-chip warn",
                     hint: _t("This rule computes “%s” and no pay component takes it. "
                              + "Wire its output to a component, or the work it does is thrown away.",
                              r.key) };
        }
        if (r.health === "drift") {
            return { label: _t("Field not seen"), cls: "tfb-chip drift",
                     hint: _t("This rule reads a field this system is not known to deliver. "
                              + "It may have been renamed at the source.") };
        }
        return null;
    }

    feedsLabel(r) {
        if (!r.feeds || !r.feeds.length) { return _t("Nothing reads this rule's output."); }
        return _t("Feeds: %s", r.feeds.join(", "));
    }

    /** The read lane's hover sentence — J4's non-goal, said out loud (case 8). */
    get readsHint() {
        return _t("Which fields a rule reads is part of the rule itself — "
                  + "open the rule to change it. These lines cannot be drawn or cut here.");
    }

    hasLineage(r) { return !!(r.lineage && (r.lineage.summary || r.lineage.reads)); }

    /**
     * A component the SCHEME produces cannot be fed from here.
     *
     * Read off `meta.wirable`, which is the adapter's own verdict and the same
     * flag the canvas seals on — not off a second rule written here. S5's lesson:
     * a sealed card has to ANSWER on the board, not only on the server, or a
     * click that clears the armed rule and says nothing reads as the board being
     * broken rather than as the component being produced.
     */
    isSealed(item) {
        return !!(item && item.meta && item.meta.wirable === false);
    }

    // ============================================================== geometry
    _schedule() {
        if (this._raf) { return; }
        this._raf = requestAnimationFrame(() => { this._raf = null; this._recompute(); });
    }
    onLaneScroll() { this._schedule(); }

    /**
     * One pass per lane into a Map of id → centre-Y, plus the lane's band.
     *
     * Straight out of `MappingCanvas._measure`, including the reason the keys are
     * STRINGS: `dataset.id` always is, and the adapters disagree about the type of
     * an item id — the left lane's ids are strings (`f:OT_Type`) and the right
     * lane's are integers (`584`). `map.has(584)` against a key of `"584"` is a
     * silent miss that reads on screen as a wire whose target was filtered away
     * (W146). Everything below goes through `String()`.
     */
    _measure(body, rb, lane) {
        if (!body) { return null; }
        const br = body.getBoundingClientRect();
        if (br.width < 8 || br.height < 8) { return null; }
        const map = new Map();
        let leftEdge = null, rightEdge = null;
        for (const el of body.children) {
            const id = el.dataset && el.dataset.id;
            if (!id || el.dataset.lane !== lane) { continue; }   // group headers
            const r = el.getBoundingClientRect();
            map.set(id, r.top + r.height / 2 - rb.top);
            if (leftEdge === null) {
                leftEdge = r.left - rb.left;
                rightEdge = r.right - rb.left;
            }
        }
        if (leftEdge === null) {
            leftEdge = br.left - rb.left + 14;
            rightEdge = br.right - rb.left - 14;
        }
        return { map, leftEdge, rightEdge,
                 bandTop: br.top - rb.top + BAND,
                 bandBot: br.bottom - rb.top - BAND };
    }

    _recompute() {
        const root = this.rootRef.el;
        if (!root) { return; }
        const rb = root.getBoundingClientRect();
        const L = this._measure(this.bodyRefs.left.el, rb, "left");
        const M = this._measure(this.bodyRefs.mid.el, rb, "mid");
        const R = this._measure(this.bodyRefs.right.el, rb, "right");
        this._recomputes++;
        const reads = [], geom = [], suppressed = [];
        if (L && M) {
            for (const e of this.d.reads || []) {
                const sy = L.map.get(String(e.leftId));
                const ty = M.map.get(String(e.ruleId));
                if (sy === undefined || ty === undefined) {
                    // filtered out at one end — it gets a dock chip and no curve,
                    // which is MAPFIX F1's rule (a suppressed wire must be counted
                    // somewhere or it reads as a lost one)
                    suppressed.push({ id: e.id,
                                      hiddenL: sy === undefined, hiddenR: ty === undefined,
                                      dockL: sy === undefined ? -1 : 0,
                                      dockR: ty === undefined ? -1 : 0 });
                    continue;
                }
                const a = clampY(sy, L.bandTop, L.bandBot);
                const b = clampY(ty, M.bandTop, M.bandBot);
                const g = wireGeometry(L.rightEdge, a.y, M.leftEdge, b.y);
                reads.push({ ...g, id: e.id, ruleId: e.ruleId, leftId: e.leftId,
                             dockL: a.docked, dockR: b.docked });
            }
        }
        if (M && R) {
            for (const w of this.d.wires || []) {
                const sy = M.map.get(String(w.ruleId));
                const ty = R.map.get(String(w.rightId));
                if (sy === undefined || ty === undefined) {
                    suppressed.push({ id: w.id, state: w.state,
                                      hiddenL: sy === undefined, hiddenR: ty === undefined,
                                      dockL: sy === undefined ? -1 : 0,
                                      dockR: ty === undefined ? -1 : 0 });
                    continue;
                }
                const a = clampY(sy, M.bandTop, M.bandBot);
                const b = clampY(ty, R.bandTop, R.bandBot);
                const g = wireGeometry(M.rightEdge, a.y, R.leftEdge, b.y);
                geom.push({ ...g, id: w.id, ref: w.ref, bind: w.bind,
                            ruleId: w.ruleId, rightId: w.rightId,
                            severed: w.severed, state: w.state,
                            dockL: a.docked, dockR: b.docked });
            }
        }
        spreadHubs(geom);
        this.ui.reads = reads;
        this.ui.geom = geom;
        this.ui.docks = aggregateDocks(geom, suppressed);
    }

    // =============================================================== search
    onSearch(ev) { this.ui.q = ev.target.value || ""; this._schedule(); }
    clearSearch() {
        this.ui.q = "";
        if (this.qRef.el) { this.qRef.el.value = ""; }
        this._schedule();
    }

    /**
     * MF33, one input device over.
     *
     * `onKeydown` is bound to the board ROOT, so without this guard Enter on a
     * focused `<button>` fires the button's own click AND falls through to the
     * board's own Enter — which arms an output, and with an output already armed
     * DRAWS A WIRE. That is exactly the trap MAPFIX E found on the canvas: the
     * keyboard route into a control mapped something on the way in. `INPUT` is
     * deliberately absent from the guard: Enter in the search box is the board's
     * own promise.
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
            if (this.ui.menu) { this.ui.menu = null; return; }
            if (this.ui.armed) { this.cancelArm(); return; }
            if (this.ui.selWire) { this.ui.selWire = null; return; }
            if (this.ui.q) { this.clearSearch(); return; }
        }
    }

    // ============================================================ interaction
    /** The whole card is the door into the composer — J4's mission, literally. */
    openRule(id, ev) {
        if (ev) { ev.stopPropagation(); }
        this.ui.menu = null;
        this.props.onOpenRule(id);
    }

    toggleVerbs(r, ev) {
        ev.stopPropagation();
        const root = this.rootRef.el;
        const btn = ev.currentTarget;
        if (this.ui.menu && this.ui.menu.ruleId === r.id
            && this.ui.menu.kind === "verbs") {
            this.ui.menu = null;
            return;
        }
        const rb = root.getBoundingClientRect();
        const b = btn.getBoundingClientRect();
        this.ui.menu = { kind: "verbs", ruleId: r.id, rule: r,
                         x: b.right - rb.left, y: b.bottom - rb.top + 4 };
    }

    openLineage(r, ev) {
        ev.stopPropagation();
        const root = this.rootRef.el;
        const b = ev.currentTarget.getBoundingClientRect();
        const rb = root.getBoundingClientRect();
        this.ui.menu = { kind: "lineage", ruleId: r.id, rule: r,
                         x: b.right - rb.left, y: b.bottom - rb.top + 4 };
    }

    /** Arm this rule's output. The next component click lands the wire. */
    armOutput(r, ev) {
        if (ev) { ev.stopPropagation(); }
        this.ui.menu = null;
        if (!this.props.canEdit) { return; }
        this.ui.sealedSay = "";
        this.ui.armed = this.ui.armed === r.id ? null : r.id;
    }

    isArmed(id) { return this.ui.armed === id; }

    cancelArm() { this.ui.armed = null; this.ui.sealedSay = ""; }

    clickRule(r, ev) {
        if (this.ui.armed) { this.armOutput(r, ev); return; }
        this.openRule(r.id, ev);
    }

    /**
     * A component click — and the ONLY thing on this board that can write.
     *
     * With nothing armed it is a no-op that moves a focus ring, which is MF37's
     * safe shape: a gesture that cannot write while nothing is armed is a gesture
     * a probe can exercise without a database diff.
     */
    clickComponent(item, ev) {
        if (ev) { ev.stopPropagation(); }
        this.ui.focus = { lane: "right", id: item.id };
        const ruleId = this.ui.armed;
        if (!ruleId || !this.props.canEdit) { return; }
        if (this.isSealed(item)) {
            // the armed rule is KEPT: the user picked the wrong card, not the
            // wrong verb, and disarming here would make them start again
            this.ui.sealedSay = (item.meta && item.meta.badgeHint) || "";
            return;
        }
        const rule = (this.d.rules || []).find((r) => r.id === ruleId);
        this.ui.armed = null;
        if (!rule || !rule.key) { return; }
        this.props.onDraw(rule.key, item.id);
    }

    selectWire(g, ev) {
        ev.stopPropagation();
        this.ui.selWire = this.ui.selWire === g.id ? null : g.id;
    }
    enterWire(id) { this.ui.hoverWire = id; }
    leaveWire() { this.ui.hoverWire = null; }

    get selectedWire() {
        return this.ui.geom.find((g) => g.id === this.ui.selWire) || null;
    }

    /**
     * Cut a rule → component edge.
     *
     * Only a real MAPPING can be cut here. A `('rule', key)` binding is a field on
     * the component, not a row of its own, and the place a component's chosen
     * source is changed is the component — offering a scissors here would put a
     * second, differently-shaped door onto one decision (S6's lesson).
     */
    removeWire(g, ev) {
        if (ev) { ev.stopPropagation(); }
        this.ui.selWire = null;
        if (!g || g.bind || !g.ref) { return; }
        this.props.onDelete(g.ref);
    }

    wireTitle(g) {
        if (g.bind) {
            return _t("This component is set to read this rule's output. "
                      + "Change it on the component itself.");
        }
        if (g.severed) {
            return _t("This wire's component is no longer on the scheme.");
        }
        return _t("This rule's output feeds this component.");
    }

    // ---- dock chips -----------------------------------------------------
    dockLabel(d) {
        const dir = d.dir < 0 ? _t("above") : _t("below");
        if (d.filtered) {
            return _t("%(n)s hidden by the search %(dir)s", { n: d.filtered, dir });
        }
        return _t("%(n)s %(dir)s", { n: d.count, dir });
    }
}
