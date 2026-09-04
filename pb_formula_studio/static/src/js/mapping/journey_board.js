/** @odoo-module **/
/**
 * JOURNEY J5 — the Journey. Five lanes, and every node is a door.
 *
 *   Systems ──▶ Feeds & files ──▶ Transformations ──▶ Scheme ──▶ Pay run
 *
 * The programme's showpiece and the owner's original ask: open Mapping and see
 * the whole story of where pay values come from, in one picture, with the
 * problems glowing.
 *
 * Three things it is, and one it is not.
 *
 *   * it is REAL. Every number on it is a count `journey_data` took off this
 *     database — components, wires, feed fields, rule outputs, the provenance
 *     of the last processed run. There are no percentages, no liveness bars and
 *     no invented "health scores": scope 5 of the handover says a number that
 *     cannot be defended from the DB is not shown, and the honest consequence is
 *     that some cards say less than a dashboard would;
 *   * it is NAVIGATION. Clicking a node lands on the tab that owns it, already
 *     scoped to the connector/feed/scheme it describes and, where the tab has a
 *     search, already filtered to it. A diagram you cannot click is a poster;
 *   * it is READ-ONLY. There is no gesture on this board that writes. Not one.
 *     That is asserted the only way MF37 accepts — a database diff across the
 *     whole validation session — and it is why every card is a `<button>` whose
 *     only effect is to change which tab you are looking at.
 *
 * What it is NOT is analytics. `pb_explorer` owns that, and a chart here would
 * be a second place the same numbers are told, differently.
 *
 * ---------------------------------------------------------------------------
 * A SIBLING of `MappingCanvas` and of `TransformFlowBoard`, for J4's reason
 * verbatim: the canvas' two-lane contract carries six tabs and five lanes is not
 * a mode of two. The geometry is `mapping_geometry.js` unforked — `wireGeometry`
 * and `clampY` are arithmetic over points and do not care how many columns
 * exist, which is the third phase running to collect on that extraction.
 *
 * Wires render UNDER the cards (`z-index`), the same layering the canvas and the
 * transformation board use. An edge that spans a lane (a feed straight to the
 * scheme, records to the scheme) therefore passes behind the cards between them
 * and is drawn lighter and dashed, so "this jumps a lane" is legible rather than
 * looking like a wire that broke in the middle.
 */
import { Component, useState, useRef, onMounted, onWillUnmount, onPatched,
         onWillUpdateProps, useExternalListener } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { wireGeometry, clampY } from "./mapping_geometry";

/** Pixels of a lane's band reserved so a clamped wire is not flush to the edge. */
const BAND = 10;

/** The lanes, left to right. `id` is the payload key; the order IS the story. */
export const LANES = [
    { id: "systems", icon: "server", label: _t("Systems") },
    { id: "feeds", icon: "database", label: _t("Feeds & files") },
    { id: "transforms", icon: "sigma", label: _t("Transformations") },
    { id: "scheme", icon: "calculator", label: _t("Scheme") },
    { id: "run", icon: "receipt", label: _t("Pay run") },
];

/** Lane id -> index, so an edge can tell adjacent from spanning. */
const LANE_INDEX = {};
LANES.forEach((l, i) => { LANE_INDEX[l.id] = i; });

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
            focus: "",          // the id of the node the pointer/keyboard is on
            geom: [],           // the drawn edges
        });
        this.rootRef = useRef("root");
        this.qRef = useRef("q");
        this.laneRefs = {};
        for (const lane of LANES) { this.laneRefs[lane.id] = useRef(lane.id); }
        this._raf = null;
        this._recomputes = 0;
        onMounted(() => {
            this._recompute();
            this._ro = new ResizeObserver(() => this._schedule());
            const els = [this.rootRef.el].concat(
                LANES.map((l) => this.laneRefs[l.id].el));
            for (const el of els) { if (el) { this._ro.observe(el); } }
        });
        onWillUnmount(() => {
            if (this._ro) { this._ro.disconnect(); }
            if (this._raf) { cancelAnimationFrame(this._raf); }
        });
        onWillUpdateProps((next) => {
            // A different scheme is a different Journey. A search resolved
            // against the old one points at cards that stop existing this frame
            // (CR9's family; both sibling boards do exactly this).
            if (next.data !== this.props.data) {
                this.ui.focus = "";
            }
        });
        onPatched(() => this._schedule());
        useExternalListener(window, "resize", () => this._schedule());
    }

    ic(n, s = 14) { return ic(n, s); }

    // ==================================================================== data
    get d() { return this.props.data || {}; }
    get counts() { return this.d.counts || {}; }
    get lanes() { return LANES; }

    /** Every node of every lane, flat — the tab order, and the search domain. */
    get allNodes() {
        const src = this.d.lanes || {};
        const out = [];
        for (const lane of LANES) {
            for (const n of (src[lane.id] || [])) { out.push(n); }
        }
        return out;
    }

    nodesFor(laneId) {
        const src = (this.d.lanes || {})[laneId] || [];
        return src.filter((n) => this._passes(n));
    }

    /**
     * ONE query, five lanes — and a lane matches THROUGH its neighbours.
     *
     * J4 settled this on the transformation board and the reason carries: the
     * FLOW is the unit of meaning here. Typing a connector's name must not empty
     * the feeds lane, or `/` breaks every wire on the board and the reader is
     * looking at five unrelated filtered lists. So a node matches when its own
     * text matches, when its PARENT matches, or when something it is wired to
     * matches.
     */
    _passes(node) {
        const q = (this.ui.q || "").trim().toLowerCase();
        if (!q) { return true; }
        if (this._text(node).includes(q)) { return true; }
        const parent = this._byId(node.parent);
        if (parent && this._text(parent).includes(q)) { return true; }
        for (const e of (this.d.edges || [])) {
            let other = null;
            if (e.from === node.id) { other = this._byId(e.to); }
            else if (e.to === node.id) { other = this._byId(e.from); }
            if (other && this._text(other).includes(q)) { return true; }
        }
        return false;
    }

    _text(node) {
        return [node.label, node.sub, node.key,
                node.chip && node.chip.label].filter(Boolean).join(" ").toLowerCase();
    }

    _byId(id) {
        if (!id) { return null; }
        return this.allNodes.find((n) => n.id === id) || null;
    }

    // ================================================================== chrome
    /**
     * The header sentence. ONE msgid per shape, never assembled from fragments.
     *
     * `⟨scheme⟩ — N components · N wired · N fallback · N need attention`, with
     * the attention clause dropped entirely when there is nothing wrong rather
     * than printed as "0 need attention" — a zero that has to be read before it
     * can be dismissed is a zero that costs the reader something (W64/W80).
     */
    get headline() {
        const h = this.d.header || {};
        const bits = [
            h.components === 1 ? _t("1 component") : _t("%s components", h.components || 0),
            h.wired === 1 ? _t("1 wired") : _t("%s wired", h.wired || 0),
            h.fallback === 1 ? _t("1 fallback") : _t("%s fallback", h.fallback || 0),
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
        const shown = this.nodesFor(laneId).length;
        const all = ((this.d.lanes || {})[laneId] || []).length;
        if (shown !== all) {
            return _t("%(shown)s of %(all)s", { shown, all });
        }
        return String(all);
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
     * The second line of a card, per kind.
     *
     * Built here rather than on the server for exactly one reason: the AGE has
     * to be computed against the reader's clock, and a server-rendered "3d ago"
     * is stale the moment it is cached. Everything that is not an age arrives
     * already worded from the adapter.
     */
    nodeSub(n) {
        if (n.ghost) { return n.sub || ""; }
        switch (n.kind) {
            case "connector": {
                const bits = [this.statusWord(n.status), this.since(n.last_sync)];
                if (n.wires) {
                    bits.push(n.wires === 1 ? _t("1 wire into this scheme")
                                            : _t("%s wires into this scheme", n.wires));
                }
                return bits.filter(Boolean).join(" · ");
            }
            case "endpoint": {
                const bits = [n.fields === 1 ? _t("1 field") : _t("%s fields", n.fields || 0)];
                bits.push(this.since(n.last_sync));
                return bits.filter(Boolean).join(" · ");
            }
            case "rule": {
                const bits = [];
                if (n.key) { bits.push(n.sub); }
                bits.push(n.reads === 1 ? _t("reads 1 field")
                                        : _t("reads %s fields", n.reads || 0));
                return bits.filter(Boolean).join(" · ");
            }
            case "records":
                return n.countLabel || n.sub || "";
            default:
                return n.sub || "";
        }
    }

    statusWord(status) {
        return {
            connected: _t("Connected"),
            connecting: _t("Connecting"),
            error: _t("Connection error"),
            disconnected: _t("Not connected"),
        }[status] || "";
    }

    /**
     * The whole-sentence tooltip. The PILL says the surprising thing in as few
     * words as will fit; the tooltip carries the explanation — J3's pattern,
     * and the reason no new severity vocabulary was invented for this tab.
     */
    nodeTitle(n) {
        if (n.chip && n.chip.hint) { return n.chip.hint; }
        if (n.ghost) { return n.sub || ""; }
        return this.doorHint(n);
    }

    doorHint(n) {
        const where = {
            api: _t("the System fields tab"),
            transform: _t("the Transformations tab"),
            import: _t("the Spreadsheet tab"),
            employee: _t("the Employee & contract tab"),
        }[(n.door && n.door.mode) || ""] || "";
        return where ? _t("Opens %s, already on this.", where) : "";
    }

    // ---- the scheme lane's component picture --------------------------------
    /**
     * The bars are PROPORTIONS OF A COUNT, not a score.
     *
     * Every segment is a number of components and its width is that number over
     * the total — arithmetic the reader can check by adding up the labels. This
     * is the one place the board draws anything shaped like a chart, and it is
     * allowed because it is a tally of five disjoint, named, defensible counts
     * that sum to the whole.
     */
    get schemeBars() {
        const node = ((this.d.lanes || {}).scheme || [])[0];
        const c = (node && node.counts) || {};
        const total = c.total || 0;
        const rows = [
            { key: "wired", n: c.wired || 0, label: _t("Wired to a source"), tone: "ok" },
            { key: "calculated", n: c.calculated || 0, label: _t("Calculated here"), tone: "calc" },
            { key: "constant", n: c.constant || 0, label: _t("Fixed value"), tone: "calc" },
            { key: "people", n: c.people || 0, label: _t("Read off a record"), tone: "info" },
            { key: "contract", n: c.contract || 0, label: _t("From the contract"), tone: "info" },
            { key: "unfed", n: c.unfed || 0, label: _t("Nothing feeds it"), tone: "warn" },
        ];
        return rows.filter((r) => r.n).map((r) => ({
            ...r, pct: total ? Math.round((r.n / total) * 1000) / 10 : 0,
        }));
    }

    get schemeNode() { return ((this.d.lanes || {}).scheme || [])[0] || null; }

    /** The fallback count, said in the words J-D4 fixed. */
    get fallbackLine() {
        const n = (this.d.header || {}).fallback || 0;
        if (!n) { return ""; }
        return n === 1
            ? _t("1 component can be read back off an employee or contract record "
                 + "when the file or feed leaves it empty.")
            : _t("%s components can be read back off employee or contract records "
                 + "when the file or feed leaves them empty.", n);
    }

    // ---- the pay-run lane ---------------------------------------------------
    get runNode() { return ((this.d.lanes || {}).run || [])[0] || null; }

    /** The by-source tally of the last run — only kinds that actually occurred. */
    get runSources() {
        const n = this.runNode;
        const by = (n && n.agg && n.agg.by_src) || {};
        const words = {
            excel: _t("Spreadsheet"), feed: _t("Connected system"),
            rule: _t("Rule output"), contract_component: _t("Contract component"),
            employee_field: _t("Employee record"), calculated: _t("Calculated"),
            constant: _t("Fixed value"), none: _t("No source"),
        };
        return Object.keys(by)
            .filter((k) => by[k])
            .sort((a, b) => by[b] - by[a])
            .map((k) => ({ key: k, n: by[k], label: words[k] || k }));
    }

    /** The by-`via`-family tally. The buckets are the SERVER's, never invented here. */
    get runBuckets() {
        const n = this.runNode;
        const by = (n && n.agg && n.agg.by_bucket) || {};
        const words = {
            wired: _t("through the wiring"), fallback: _t("fell back"),
            computed: _t("added by an adjustment"), default: _t("used a default"),
        };
        return ["wired", "fallback", "computed", "default"]
            .filter((k) => by[k])
            .map((k) => ({ key: k, n: by[k], label: words[k] }));
    }

    /** "12,480 values across 130 payslips" — and it SAYS when it is a subset. */
    get runScope() {
        const n = this.runNode;
        if (!n || !n.agg) { return ""; }
        const a = n.agg;
        const base = _t("%(values)s values across %(slips)s payslips",
                        { values: a.values, slips: a.slips });
        if (n.capped) {
            return _t("%(base)s — read from the first %(read)s of %(all)s",
                      { base, read: n.read, all: n.payslips });
        }
        return base;
    }

    // ================================================================ geometry
    _schedule() {
        if (this._raf) { return; }
        this._raf = requestAnimationFrame(() => { this._raf = null; this._recompute(); });
    }
    onLaneScroll() { this._schedule(); }

    /**
     * One pass per lane into a Map of id -> {y, left, right} plus the lane band.
     *
     * Keys are STRINGS throughout, which is W146's lesson carried over:
     * `dataset.id` always is one, and `map.has(584)` against a key of `"584"` is
     * a silent miss that reads on screen as a wire whose target was filtered
     * away. Every node id this board mints is already a string (`c:3`, `e:11`,
     * `scheme`), which is deliberate — the ambiguity cannot arise.
     */
    _measure(body, rb, laneId) {
        if (!body) { return null; }
        const br = body.getBoundingClientRect();
        if (br.width < 8 || br.height < 8) { return null; }
        const map = new Map();
        let leftEdge = null, rightEdge = null;
        for (const el of body.children) {
            const id = el.dataset && el.dataset.id;
            if (!id || el.dataset.lane !== laneId) { continue; }
            const r = el.getBoundingClientRect();
            map.set(id, r.top + r.height / 2 - rb.top);
            if (leftEdge === null) {
                leftEdge = r.left - rb.left;
                rightEdge = r.right - rb.left;
            }
        }
        if (leftEdge === null) {
            leftEdge = br.left - rb.left + 12;
            rightEdge = br.right - rb.left - 12;
        }
        return { map, leftEdge, rightEdge,
                 bandTop: br.top - rb.top + BAND,
                 bandBot: br.bottom - rb.top - BAND };
    }

    _recompute() {
        const root = this.rootRef.el;
        if (!root) { return; }
        const rb = root.getBoundingClientRect();
        const M = {};
        for (const lane of LANES) {
            M[lane.id] = this._measure(this.laneRefs[lane.id].el, rb, lane.id);
        }
        // node id -> the lane it was measured in, so an edge can find both ends
        // without the payload having to repeat itself.
        const where = new Map();
        for (const lane of LANES) {
            const m = M[lane.id];
            if (!m) { continue; }
            for (const id of m.map.keys()) { where.set(id, lane.id); }
        }
        this._recomputes++;
        const geom = [];
        for (const e of (this.d.edges || [])) {
            const la = where.get(String(e.from));
            const lb = where.get(String(e.to));
            // An end that is filtered out, or a lane that has not rendered, gets
            // NO curve. MAPFIX F1's rule: a suppressed wire is not drawn to the
            // column edge pretending to be a real one.
            if (!la || !lb || la === lb) { continue; }
            const A = M[la], B = M[lb];
            const ay = A.map.get(String(e.from));
            const by = B.map.get(String(e.to));
            if (ay === undefined || by === undefined) { continue; }
            const a = clampY(ay, A.bandTop, A.bandBot);
            const b = clampY(by, B.bandTop, B.bandBot);
            // left-to-right always: the story only runs one way, and an edge
            // whose payload named its ends the other way round would draw a
            // backwards arrowhead on a picture whose whole point is direction.
            const forward = LANE_INDEX[la] <= LANE_INDEX[lb];
            // J3's `bidi` flag, opt-in and defaulted off exactly as it was
            // written — the records edge is the only one on this board that
            // earns a head at both ends, because it is the only relationship
            // that genuinely runs both ways (J-D4).
            const g = forward
                ? wireGeometry(A.rightEdge, a.y, B.leftEdge, b.y, !!e.bidi)
                : wireGeometry(B.rightEdge, b.y, A.leftEdge, a.y, !!e.bidi);
            const span = Math.abs(LANE_INDEX[lb] - LANE_INDEX[la]);
            geom.push({ ...g, id: e.from + "→" + e.to, kind: e.kind || "",
                        count: e.count || 0, bidi: !!e.bidi,
                        dimmed: !!e.dimmed, span,
                        from: e.from, to: e.to,
                        docked: a.docked || b.docked });
        }
        this.ui.geom = geom;
    }

    /** WP-6 — what a recompute costs, for anyone profiling from the console. */
    get recomputeCost() { return { n: this._recomputes, edges: this.ui.geom.length }; }

    edgeTitle(g) {
        if (g.kind === "contain") { return _t("This belongs to that system."); }
        if (g.kind === "records") {
            return g.count === 1
                ? _t("1 mapped field. It writes the record on import and is read "
                     + "back on a pay run.")
                : _t("%s mapped fields. They write the records on import and are "
                     + "read back on a pay run.", g.count);
        }
        if (g.dimmed) {
            return _t("This scheme does not read this connection on a system run.");
        }
        if (g.kind === "rule") {
            return g.count === 1 ? _t("Feeds 1 component") : _t("Feeds %s components", g.count);
        }
        if (g.kind === "excel") {
            return g.count === 1 ? _t("1 component is bound to a column of this file")
                                 : _t("%s components are bound to columns of this file", g.count);
        }
        return g.count === 1 ? _t("1 wire into this scheme")
                             : _t("%s wires into this scheme", g.count);
    }

    // ================================================================== search
    onSearch(ev) { this.ui.q = ev.target.value || ""; this._schedule(); }
    clearSearch() {
        this.ui.q = "";
        if (this.qRef.el) { this.qRef.el.value = ""; }
        this._schedule();
    }

    /**
     * MF33, third board running.
     *
     * `onKeydown` is bound to the board ROOT, and every node on this board is a
     * `<button>` — so without this guard Enter on a focused node would fire the
     * button's own click AND fall through to the root's handler. Here that would
     * merely open the same door twice, which is harmless and is exactly why the
     * guard is worth writing down: on the canvas the same shape DREW A WIRE, and
     * a rule you only apply where it currently hurts is a rule you will forget
     * on the board where it will. `INPUT` is deliberately absent — Enter in the
     * search box belongs to the search box.
     *
     * Enter opening the focused node's door therefore needs no code at all: the
     * node IS a button, so the platform does it, and it does it with the focus
     * ring, the ARIA role and the Space key already correct (MJ10's family).
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
            if (this.ui.focus) { this.ui.focus = ""; return; }
        }
    }

    // ============================================================= interaction
    /**
     * The only thing any node does. It cannot write; it changes which tab you
     * are looking at and what that tab is scoped to.
     */
    openDoor(node, ev) {
        if (ev) { ev.stopPropagation(); }
        this.ui.focus = node.id;
        if (!node.door) { return; }
        this.props.onOpenDoor(node.door);
    }

    /**
     * A node's SECONDARY actions — a door out of Mapping altogether.
     *
     * `openDoor` can only change which tab you are on, so a screen that lives
     * in another module cannot be one. These are rendered as small buttons
     * BESIDE the node (never inside it: a button inside a button is not valid
     * markup, and the wire geometry reads `body.children`, which is why they
     * are siblings carrying no `data-id`).
     *
     * The probe is the `plan_launcher.js:204` pattern: the server can resolve
     * an `ir.actions.client` whose JS never shipped, and opening one of those
     * is a blank screen. A database without `pb_records` renders no button.
     */
    nodeActions(node) {
        const actions = (node && node.actions) || [];
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

    onNodeFocus(node) { this.ui.focus = node.id; }
    isFocused(id) { return this.ui.focus === id; }

    nodeClass(n) {
        const bits = ["jny-node"];
        if (n.ghost) { bits.push("ghost"); }
        if (n.dimmed) { bits.push("dim"); }
        if (n.tone) { bits.push(n.tone); }
        if (n.primary) { bits.push("prim"); }
        if (this.isFocused(n.id)) { bits.push("on"); }
        return bits.join(" ");
    }

    nodeIcon(n) {
        return {
            connector: "plug", file: "table", records: "users",
            endpoint: "database", sheet: "table", rule: "sigma",
            scheme: "calculator", health: "alert", run: "receipt",
        }[n.kind] || "gitMerge";
    }
}
