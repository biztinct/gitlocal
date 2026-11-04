/** @odoo-module **/
/**
 * ORG CHART P1 + P2 — People › Org chart. P1 drew it read-only; P2's
 * editing half (drag, multi-select, dialogs, menus, undo, history) lives in
 * orgchart_edit.js and orgchart_dialog.js and is installed onto this class.
 *
 * The product version of docs/design/org-chart-poc (the spec). One payload
 * (`pb.orgchart.get_chart`), everything else client-side: layout, numbers that
 * focus, filters, search, the four views, pan/zoom/minimap, the side panel.
 *
 * Rendering notes (ORGCHART_P1 §3.2):
 *  * The tree index and positions live OUTSIDE `useState` (`this.idx`,
 *    `this.lay`); `state.rev` is bumped when they change. Hover, selection and
 *    filters only change classes.
 *  * Pan and zoom never touch reactive state: the world's transform, the zoom
 *    percentage and the minimap viewport are written straight to the DOM, so
 *    a pan of 60 events a second re-renders nothing.
 *  * Icons come from one cache (`icon()`): a NEW markup per render re-inserts
 *    its DOM on every redraw (memory "OWL markup flicker"), and a hover
 *    re-renders every card.
 *  * Edges are real <path> elements in the template (no markup string), keyed
 *    by the layout revision so they fade in after the cards glide.
 */
import { Component, useState, useRef, onWillStart, onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";
import {
    buildIndex, layout, bounds, edges, kidsOf, ancestors, descendants,
    directCount, totalCount, isUnloaded, colorOf, cardSize, edgePath,
    LOC_COLORS, TYPE_COLORS, TENURE, daysSince,
} from "@pb_orgchart/js/orgchart_layout";
import { installEdit, personNode, roleNode, starterNode } from "@pb_orgchart/js/orgchart_edit";
import { installPlan } from "@pb_orgchart/js/orgchart_plan";
import { installExport, takeArrival } from "@pb_orgchart/js/orgchart_export";
import { PbOcDialog } from "@pb_orgchart/js/orgchart_dialog";

const ICONS = new Map();
/** One markup object per (icon, size), for ever. */
function icon(name, size = 16) {
    const k = name + ":" + size;
    let m = ICONS.get(k);
    if (!m) { m = ic(name, size); ICONS.set(k, m); }
    return m;
}

const MIN_FIT = 0.42;     // G3: never shrink below readable
const WIDE = 10;
const BIG_DRAW = 400;     // fold more when a first draw would exceed this
// P4 — the virtual canvas: above VIRT_MIN cards only the ones whose box is
// within MARGIN screen pixels of the viewport are mounted; the rest are drawn
// as one skeleton <path> under the cards, so the shape is there while panning.
const VIRT_MIN = 150;
const MARGIN = 400;
const VIS_IDLE = 140;     // ms after the last pan/zoom move: re-work what is mounted
const GLIDE_MS = 350;

/**
 * One card. Its own component so that a page of 650 cards re-renders only the
 * cards whose props changed (OWL skips a child whose props are equal): a
 * selection redraws two cards, a filter redraws the ones it dims.
 */
export class PbOcCard extends Component {
    static template = "pb_orgchart.Card";
    static props = ["c", "cls", "flags", "st", "color", "busy", "lr", "api"];

    icon(n, s = 16) { return icon(n, s); }

    avatarStyle(n) { return n.isRole ? "" : `background:${this.props.color}`; }
}

export class PbOrgChart extends Component {
    static template = "pb_orgchart.PbOrgChart";
    static components = { HubBackChip, PbOcCard, PbOcDialog };
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.root = useRef("root");
        this.canvasRef = useRef("canvas");
        this.worldRef = useRef("world");
        this.pctRef = useRef("pct");
        this.vpRef = useRef("vp");
        this.searchRef = useRef("search");
        this.nodesRef = useRef("nodes");
        this.hiRef = useRef("hi");
        this.ghostRef = useRef("ghost");
        this.hintRef = useRef("draghint");
        this.qaRef = useRef("qa");
        this._hover = null;
        this._marked = [];
        // ONE object for the cards' callbacks, made once: a card re-renders
        // only when its props change, and a fresh arrow per render would be
        // a change on every card every time.
        this.api = {
            select: (id) => this.select(id),
            toggle: (c) => this.toggle(c),
            hover: (id) => this.onHover(id),
            click: (c, ev) => this.onCardClick(c, ev),
            dbl: (c) => this.onCardDbl(c),
            nameOf: (n) => this.nameOf(n),
            deptDot: (n) => this.deptDot(n),
            isMe: (n) => this.isMe(n),
            toggleTitle: (c) => this.toggleTitle(c),
            cardLabel: (n) => this.cardLabel(n),
            fmtInt: (n) => this.fmtInt(n),
        };
        this.back = this.props.embedded ? null : hubBack(this.props);

        this.state = useState({
            loaded: false, failed: false, rev: 0,
            view: "tree", compact: false, colorBy: "dept", levels: 0,
            filters: { dept: null, loc: null, type: null },
            focus: null, q: "", sugg: -1,
            sel: null, side: null, sideTab: "team",
            menu: null, laneOpen: false, branchBusy: null,
            drawerEmpId: null, nomgrDismissed: false,
            // P2: the open dialog, the right-click menu, how many cards are
            // picked, a write in flight, the history cache's revision
            dlg: null, ctx: null, pickN: 0, writing: false, histRev: 0,
            // P3: the plan on screen (the server's plan payload), the redo
            // depth, the time machine (days from today) and the Plans menu
            plan: null, redoN: 0, asOf: 0, asOfDraft: 0, timeBusy: false, plans: null,
            // P4: an export in flight ("png" | "csv"), the PDF print view, the
            // virtual canvas's revision (bumped when the mounted set changes)
            exporting: null, printPdf: false, visRev: 0,
        });
        this._setupEdit();
        this._setupPlan();
        this.data = null;
        this.nodes = [];
        this.idx = null;
        this.lay = null;
        this.edgeList = [];
        this.cards = [];
        this.collapsed = new Set();
        this.vp = { zoom: 1, px: 0, py: 0 };
        this.firstDraw = true;
        this.today = new Date(new Date().toDateString());
        this.perf = { payloadMs: 0, layoutMs: 0, renderMs: 0 };
        this._t0 = 0;
        this._pendingFit = false;
        // P4: what a ⌘K row or a shared link asked for — applied once
        this._arrival = takeArrival(this.props.arrival);
        this._vis = null;
        this._visT = 0;
        this._worldTf = "";
        this._glide = null;

        onWillStart(() => this.load());
        onMounted(() => {
            this._bind();
            this._afterDraw();
            if (this.root.el) { this.root.el.focus({ preventScroll: true }); }
            if (this._arrival) { this._arrivalAfterLoad(); }
        });
        onPatched(() => this._afterDraw());
        onWillUnmount(() => this._unbind());
    }

    // ================================================================ data
    /**
     * Read the chart. `keep` (P3): a redraw of the same chart — a plan's
     * projection after a change, another day in the time machine — keeps
     * what was folded, the view and the opened teams.
     */
    async load(opts = {}) {
        const keep = !!(opts.keep && this.data);
        this.state.failed = false;
        if (!keep && !this.data && this._arrival) { this._arrivalBeforeLoad(); }
        const t = performance.now();
        let d = null;
        try {
            d = await this.orm.call("pb.orgchart", "get_chart", [], this.chartKw());
        } catch (e) {
            console.warn("pb_orgchart: chart failed", e);
            d = null;
        }
        if (!keep && d && d.error && (this.state.plan || this.state.asOf) && !opts.retried) {
            // a shared link named a plan this reader may not open: say so and
            // show today's chart instead of an error page
            this.notif.add(d.error, { type: "warning" });
            this.state.plan = null;
            this.state.asOf = 0;
            this.state.asOfDraft = 0;
            if (this._arrival) { this._arrival.plan = null; this._arrival.asOf = null; }
            return this.load({ retried: true });
        }
        if (!d || d.error) {
            if (keep) {
                // the plan or the day could not be drawn: say so, keep the chart
                this.notif.add((d && d.error) || _t("The chart could not be loaded. Try again."), { type: "danger" });
                if (this.state.plan && d && d.error) { this.state.plan = null; if (this.state.side === "__changes") { this.state.side = null; } }
                return;
            }
            this.state.failed = true;
            this.state.loaded = true;
            return;
        }
        this.data = d;
        this.perf.payloadMs = Math.round(performance.now() - t);
        if (d.plan) { this.state.plan = d.plan; }
        this.deptColor = new Map((d.departments || []).map((x) => [x.id, x.color]));
        this.nodes = [];
        this._order = 0;
        this._ingest(d.people || [], d.open_roles || [], d.starters || []);
        this.idx = buildIndex(this.nodes);
        if (keep) {
            for (const id of [...this.collapsed]) { if (!this.idx.byId.has(id)) { this.collapsed.delete(id); } }
            const s = this.state;
            if (s.sel && !this.idx.byId.has(s.sel)) { s.sel = null; }
            if (s.side && s.side !== "__changes" && !this.idx.byId.has(s.side)) { s.side = null; }
            this.hist.clear();
        } else {
            this._initialFold();
            this.firstDraw = true;
            this._pendingFit = true;
        }
        this.relayout();
        this.state.loaded = true;
    }

    _ingest(people, roles, starters = []) {
        const have = new Set(this.nodes.map((n) => n.id));
        for (const p of people) {
            const id = String(p.id);
            if (have.has(id)) { continue; }
            this.nodes.push(personNode(p, this._order++));
            have.add(id);
        }
        for (const o of roles) {
            if (have.has(o.id)) { continue; }
            this.nodes.push(roleNode(o, this._order++));
            have.add(o.id);
        }
        for (const f of starters) {
            if (have.has(f.id)) { continue; }
            this.nodes.push(starterNode(f, this._order++));
            have.add(f.id);
        }
    }

    /** Start folded like the best tools do (POC applyScenario). */
    _initialFold() {
        const idx = this.idx;
        for (const n of this.nodes) {
            if (idx.depth.get(n.id) >= 2 && kidsOf(idx, n.id).length >= 4) { this.collapsed.add(n.id); }
        }
        // A big company: fold until the first draw is a screen, not a city.
        for (const minDepth of [1, 0]) {
            if (this._countDrawn() <= BIG_DRAW) { break; }
            for (const n of this.nodes) {
                if (idx.depth.get(n.id) >= minDepth && kidsOf(idx, n.id).length) { this.collapsed.add(n.id); }
            }
        }
    }

    _countDrawn() {
        const idx = this.idx;
        let c = 0;
        const walk = (n) => {
            c++;
            if (this.collapsed.has(n.id)) { return; }
            for (const k of kidsOf(idx, n.id)) { walk(k); }
        };
        for (const t of idx.trees) { walk(t); }
        return c + Math.min(idx.lone.length, 20);
    }

    async loadBranch(n) {
        if (this.state.branchBusy) { return; }
        this.state.branchBusy = n.id;
        try {
            const kw = this.chartKw();
            delete kw.expand;
            const b = await this.orm.call("pb.orgchart", "get_branch", [n.empId], kw);
            this._branches.add(n.empId);
            this._ingest(b.people || [], b.open_roles || []);
            this.idx = buildIndex(this.nodes);
            // the new team opens one level; its own teams start folded
            for (const k of descendants(this.idx, n.id)) {
                if (kidsOf(this.idx, k.id).length) { this.collapsed.add(k.id); }
            }
            if (b.truncated) {
                this.notif.add(_t("This team is very large — the nearest people are shown."), { type: "info" });
            }
        } catch (e) {
            console.warn("pb_orgchart: branch failed", e);
            this.notif.add(_t("That team could not be loaded. Try again."), { type: "danger" });
        } finally {
            this.state.branchBusy = null;
        }
    }

    // ============================================================== layout
    relayout() {
        const t = performance.now();
        this._t0 = t;
        const s = this.state;
        if (!this.idx) { return; }
        if (s.view === "tree" || s.view === "lr") {
            this.lay = layout(this.idx, {
                view: s.view, compact: s.compact, levels: s.levels,
                collapsed: this.collapsed, laneOpen: s.laneOpen,
                laneFirst: s.focus ? new Set(this.nodes.filter((n) => this.emphasised(n)).map((n) => n.id)) : null,
            });
            this.edgeList = edges(this.idx, this.lay, s.view === "lr");
            // P3: a dashed rose line from where each person a plan moves used to sit
            for (const g of (this.data && this.data.ghost_edges) || []) {
                const a = this.lay.pos.get(String(g.from_manager_id));
                const b = this.lay.pos.get(String(g.emp_id));
                if (a && b) {
                    this.edgeList.push({ id: "g:" + g.emp_id, from: String(g.from_manager_id),
                                         d: edgePath(a, b, s.view === "lr", true), ghost: true });
                }
            }
            this._buildCards();
        }
        this.perf.layoutMs = Math.round(performance.now() - t);
        s.rev++;
    }

    _buildCards() {
        const idx = this.idx;
        const lay = this.lay;
        const out = [];
        const prev = this._cardMap || new Map();
        for (const [id, p] of lay.pos) {
            if (id === lay.moreId) { continue; }
            const n = idx.byId.get(id);
            if (!n) { continue; }
            const direct = directCount(idx, n);
            const total = totalCount(idx, n);
            const tags = [];
            if (n.isRole) { tags.push({ k: "role", cls: n.virtual ? "p" : "amber", ic: "briefcase", text: n.hiring || _t("Open role") }); }
            if (n.future) { tags.push({ k: "fut", cls: "blue", ic: "calendar", text: n.startLabel }); }
            if (n.status === "new") { tags.push({ k: "new", cls: "green", ic: "star", text: this.joinedAgo(n) }); }
            if (n.status === "leave") { tags.push({ k: "leave", cls: "amber", ic: "plane", text: _t("On leave") }); }
            if (n.status === "leaving") { tags.push({ k: "leaving", cls: "rose", ic: "userX", text: _t("Leaving") }); }
            if (n.dotted) { tags.push({ k: "dot", cls: "blue", ic: "ellipsis", text: _t("Dotted line") }); }
            if (direct >= WIDE) {
                tags.push({ k: "wide", cls: "amber", ic: "triangleAlert",
                            text: _t("%(n)s direct reports", { n: direct }) });
            } else if (!n.isRole && direct) {
                tags.push({ k: "team", cls: "", ic: "users",
                            text: total > direct ? _t("%(d)s direct · %(t)s total", { d: direct, t: total })
                                                 : _t("%(d)s direct", { d: direct }) });
            }
            const folded = this.collapsed.has(id) || isUnloaded(idx, n);
            // the same card object when nothing about it moved: its props are
            // then equal and OWL does not re-render it
            const sig = [p.x, p.y, p.w, p.h, !!p.stack, !!p.lane, folded, direct, total, !!n.changed,
                         tags.map((t) => t.k + t.text).join(",")].join("|");
            const old = prev.get(id);
            if (old && old.sig === sig && old.n === n) { out.push(old); continue; }
            out.push({
                id, n, sig, x: p.x, y: p.y, w: p.w, h: p.h, stk: !!p.stack, lane: !!p.lane,
                tags, direct, total, hasTeam: direct > 0, folded,
                delay: this.firstDraw ? Math.min(60 * (idx.depth.get(id) || 0) + (p.lane ? 120 : 0), 480) : 0,
            });
        }
        this.cards = out;
        this._cardMap = new Map(out.map((c) => [c.id, c]));
        // a redraw of a big chart mounts what the current view shows at once
        // (the render that follows picks it up; no second render)
        if (this.virtual && this._vis) { this._updateVisible(true); }
    }

    // ======================================================= virtual canvas
    /** True when the chart is big enough to mount only what is in view. */
    get virtual() { return this.cards.length > VIRT_MIN; }

    /** The cards that are mounted: all of them on a small chart. */
    get visibleCards() {
        void this.state.visRev;
        if (!this.virtual) { return this.cards; }
        // the first draw of a big chart: the skeleton only, until the canvas
        // has a size and the view has been fitted (then `_updateVisible`)
        if (!this._vis) { return []; }
        const key = this.state.rev + ":" + this.state.visRev;
        if (this._visKey !== key) {
            this._visKey = key;
            this._visList = this.cards.filter((c) => this._vis.has(c.id));
        }
        return this._visList;
    }

    /** One <path> with every card's box: the shape while cards mount. */
    get skeletonD() {
        if (!this.virtual) { return ""; }
        if (this._skRev !== this.state.rev) {
            this._skRev = this.state.rev;
            this._skD = this.cards.map((c) => `M${c.x} ${c.y}h${c.w}v${c.h}h${-c.w}z`).join("");
        }
        return this._skD;
    }

    /**
     * Work out which cards should be mounted for the current viewport (plus
     * MARGIN px each side), and re-render only when that set changed. Called
     * after a draw and VIS_IDLE ms after the last pan or zoom move — never per
     * frame: mounting is a DOM insertion, which on this app re-checks the whole
     * page's styles (G12).
     */
    _updateVisible(silent = false) {
        clearTimeout(this._visT);
        if (!this.lay || !this.canvasView || !this.canvasRef.el) { return; }
        if (!this.virtual) {
            if (this._vis) { this._vis = null; this.state.visRev++; }
            return;
        }
        const cv = this._canvasRect();
        const z = this.vp.zoom || 1;
        const x0 = (-this.vp.px - MARGIN) / z;
        const y0 = (-this.vp.py - MARGIN) / z;
        const x1 = (cv.width - this.vp.px + MARGIN) / z;
        const y1 = (cv.height - this.vp.py + MARGIN) / z;
        const keep = new Set();
        for (const c of this.cards) {
            if (c.x + c.w >= x0 && c.x <= x1 && c.y + c.h >= y0 && c.y <= y1) { keep.add(c.id); }
        }
        // whoever is selected, hovered or picked stays mounted (keyboard
        // travel, the pill, the pick marks)
        for (const id of [this.state.sel, this._hover, ...(this.picked || [])]) {
            if (id && this._cardMap && this._cardMap.has(id)) { keep.add(id); }
        }
        const old = this._vis;
        let same = !!old && old.size === keep.size;
        if (same) { for (const id of keep) { if (!old.has(id)) { same = false; break; } } }
        if (same) { return; }
        this._vis = keep;
        if (!silent) { this.state.visRev++; }
        if (this.root.el) { this.root.el.dataset.mounted = keep.size; }
    }

    _visLater() {
        if (!this.virtual) { return; }
        clearTimeout(this._visT);
        this._visT = setTimeout(() => this._updateVisible(), VIS_IDLE);
    }

    get moreTile() {
        const lay = this.lay;
        if (!lay || !lay.moreId) { return null; }
        const p = lay.pos.get(lay.moreId);
        return { x: p.x, y: p.y, w: p.w, h: p.h, n: p.more };
    }

    get worldSize() {
        if (this._wsRev !== this.state.rev) {
            const b = bounds(this.lay.pos, this.lay.lane);
            this._ws = { w: b.x + b.w + 400, h: b.y + b.h + 400 };
            this._wsRev = this.state.rev;
        }
        return this._ws;
    }

    // ============================================================ emphasis
    /** The hovered (or selected) person and their managers — memoised per
     *  render key, because every card asks for it. */
    get pathIds() {
        const hl = this._hover || this.state.sel;
        const key = hl + ":" + this.state.rev;
        if (this._pathKey === key) { return this._path; }
        this._pathKey = key;
        this._path = (!hl || !this.idx || !this.idx.byId.has(hl)) ? null
            : new Set([hl, ...ancestors(this.idx, hl).map((a) => a.id)]);
        return this._path;
    }

    get anyFilter() {
        const s = this.state;
        return !!(s.filters.dept || s.filters.loc || s.filters.type || s.q.length > 1 || s.focus);
    }

    matches(n) {
        const f = this.state.filters;
        if (n.isRole) { return !f.type; }
        if (f.dept && n.dept_id !== f.dept) { return false; }
        if (f.loc && n.loc !== f.loc) { return false; }
        if (f.type && n.typeKey !== f.type) { return false; }
        return true;
    }

    hitsQuery(n, q) {
        return ((n.isRole ? _t("Open role") : n.name) + " " + n.title + " " + n.dept).toLowerCase().includes(q);
    }

    emphasised(n) {
        const s = this.state;
        if (s.q.length > 1 && !this.hitsQuery(n, s.q.toLowerCase())) { return false; }
        if (!this.matches(n)) { return false; }
        const idx = this.idx;
        switch (s.focus) {
            case "open": return n.isRole;
            case "nomgr": return idx.loneSet.has(n.id) && !n.isRole;
            case "dotted": return !!n.dotted || this.nodes.some((x) => x.dotted === n.id);
            case "wide": return directCount(idx, n) >= WIDE;
            case "new": return n.status === "new";
            default: return true;
        }
    }

    /**
     * The card's LOOK (classes) and its STATE (a data attribute) are kept
     * apart on purpose. On this app any class change anywhere costs a
     * whole-page style check (~130 ms with a big chart: 646 `:has()` rules,
     * G12); an attribute change costs ~0.1 ms. Selection, dimming and the
     * hover chain therefore never touch a class.
     */
    cardClass(c) {
        const cls = ["pboc-node"];
        if (this.state.compact) { cls.push("compact"); }
        if (c.n.isRole) { cls.push("open"); }
        if (this.isMe(c.n)) { cls.push("me"); }
        if (c.stk) { cls.push("stk"); }
        cls.push("pboc-in");
        return cls.join(" ");
    }

    cardState(c) {
        const st = [];
        if (this.state.sel === c.id) { st.push("sel"); }
        if (c.n.changed) { st.push("chg"); }
        if (c.n.future) { st.push("fut"); }
        if (this.anyFilter && !this.emphasised(c.n)) { st.push("dim"); }
        return st.join(" ");
    }

    cardStyle(c) {
        let st = `transform:translate(${c.x}px,${c.y}px);width:${c.w}px;min-height:${c.h}px;`;
        if (c.delay) { st += `animation-delay:${c.delay}ms;`; }
        return st;
    }

    isMe(n) {
        return !!(this.data && this.data.me && n.empId === this.data.me);
    }

    /**
     * The chain to the top, painted straight onto the page (the POC's way):
     * hover never re-renders a card. `hl` marks the cards, the paths go into
     * an SVG group the template leaves empty. Re-applied after every patch.
     */
    _paintPath() {
        for (const el of this._marked) { delete el.dataset.hl; }
        this._marked = [];
        const host = this.nodesRef.el;
        const g = this.hiRef.el;
        const path = this.pathIds;
        if (g) {
            // a pool of <path>s whose `d` is rewritten: an attribute change is
            // ~free here, an inserted element re-checks the page's styles (G12)
            const ds = path ? this.edgeList
                .filter((e) => !e.dot && path.has(e.id) && path.has(e.from)).map((e) => e.d) : [];
            while (g.childNodes.length < ds.length) {
                const el = document.createElementNS("http://www.w3.org/2000/svg", "path");
                el.setAttribute("class", "hi");
                g.appendChild(el);
            }
            g.childNodes.forEach((el, i) => {
                const d = ds[i] || "M0,0";
                if (el.getAttribute("d") !== d) { el.setAttribute("d", d); }
                const vis = i < ds.length ? "visible" : "hidden";
                if (el.getAttribute("visibility") !== vis) { el.setAttribute("visibility", vis); }
            });
        }
        if (!host || !path) { return; }
        for (const id of path) {
            const el = host.querySelector(`[data-id="${CSS.escape(id)}"]`);
            if (el) { el.dataset.hl = "1"; this._marked.push(el); }
        }
    }

    // ============================================================= colours
    get colorCtx() {
        return {
            colorBy: this.state.colorBy, deptColor: this.deptColor,
            locations: (this.data && this.data.locations) || [], today: this.today,
        };
    }

    colorOf(n) { return colorOf(n, this.colorCtx); }

    avatarStyle(n) {
        if (n.isRole) { return ""; }
        return `background:${this.colorOf(n)}`;
    }

    deptDot(n) { return `background:${this.deptColor.get(n.dept_id) || "#64748B"}`; }

    get legendItems() {
        const s = this.state;
        const d = this.data || {};
        if (s.colorBy === "loc") {
            return (d.locations || []).slice(0, 10).map((l, i) => ({ k: l, label: l, color: LOC_COLORS[i] }));
        }
        if (s.colorBy === "type") {
            return [["fulltime", _t("Full-time")], ["parttime", _t("Part-time")],
                    ["contractor", _t("Contractor")], ["trainee", _t("Trainee")]]
                .map(([k, l]) => ({ k, label: l, color: TYPE_COLORS[k] }));
        }
        if (s.colorBy === "tenure") {
            const labels = [_t("Under 3 months"), _t("Under a year"), _t("1–3 years"), _t("3+ years")];
            return TENURE.map((t, i) => ({ k: "t" + i, label: labels[i], color: t.color }));
        }
        return (d.departments || []).slice(0, 12).map((x) => ({ k: "d" + x.id, label: x.name, color: x.color }));
    }

    // ================================================================ text
    plural(n, one, many) { return n === 1 ? one : many; }

    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    get counts() { return (this.data && this.data.counts) || {}; }

    get headline() {
        const c = this.counts;
        const people = c.people === 1 ? _t("1 person") : _t("%(n)s people", { n: this.fmtInt(c.people) });
        const teams = c.teams === 1 ? _t("1 team") : _t("%(n)s teams", { n: this.fmtInt(c.teams) });
        return _t("%(people)s across %(teams)s", { people, teams });
    }

    get subline() {
        const c = this.counts;
        const lv = c.levels === 1 ? _t("1 level deep") : _t("%(n)s levels deep", { n: c.levels || 0 });
        const op = c.open === 1 ? _t("1 open role") : _t("%(n)s open roles", { n: this.fmtInt(c.open) });
        return _t("%(levels)s · %(open)s · updates itself whenever an employee record changes",
                  { levels: lv, open: op });
    }

    get kpis() {
        const c = this.counts;
        const k = (key, tone, ico, val, label) => ({ key, tone: val ? tone : "slate", ic: ico, val, label, zero: !val });
        return [
            k("open", "amber", "briefcase", c.open || 0, c.open === 1 ? _t("open role") : _t("open roles")),
            k("nomgr", "rose", "userX", c.no_manager || 0, _t("no manager yet")),
            k("wide", "amber", "triangleAlert", c.wide || 0, c.wide === 1 ? _t("wide team (10+)") : _t("wide teams (10+)")),
            k("dotted", "blue", "ellipsis", c.dotted || 0, _t("dotted lines")),
            k("new", "green", "star", c.new || 0, _t("new this month")),
        ];
    }

    get avgSpan() { return (this.counts.avg_span || 0).toFixed(1); }

    get focusHint() {
        return {
            open: _t("Showing only open roles"),
            nomgr: _t("Showing only people without a manager"),
            dotted: _t("Showing only dotted-line reports"),
            wide: _t("Showing only managers with 10 or more direct reports"),
            new: _t("Showing only people who joined recently"),
        }[this.state.focus] || "";
    }

    get truncatedLine() {
        const d = this.data;
        if (!d || !d.truncated) { return ""; }
        const total = this.fmtInt(this.counts.people);
        return d.shown_levels === 1
            ? _t("Showing the top level of %(n)s people — open a team to load it", { n: total })
            : _t("Showing the top %(l)s levels of %(n)s people — open a team to load it", { l: d.shown_levels, n: total });
    }

    get nobodyManaged() {
        return !!(this.idx && !this.idx.trees.length && this.idx.lone.length > 1);
    }

    get bigLane() {
        return !!(this.idx && this.idx.lone.filter((n) => !n.isRole).length > 10);
    }

    get laneHint() {
        const n = this.idx ? this.idx.lone.filter((x) => !x.isRole).length : 0;
        return _t("%(n)s people have no manager yet", { n: this.fmtInt(n) });
    }

    get laneTitle() {
        return this.mayWrite
            ? _t("No manager yet · drag onto a manager, or pick several")
            : _t("No manager yet · set a manager on the employee record");
    }

    moreLabel(n) { return _t("+%(n)s more", { n: this.fmtInt(n) }); }

    tenure(n) {
        const d = daysSince(n.joined, this.today);
        if (d === null) { return "—"; }
        if (d < 30) { return d === 1 ? _t("1 day") : _t("%(n)s days", { n: Math.max(d, 0) }); }
        if (d < 365) { const m = Math.round(d / 30); return m === 1 ? _t("1 month") : _t("%(n)s months", { n: m }); }
        return _t("%(n)s years", { n: (d / 365).toFixed(1) });
    }

    joinedAgo(n) { return _t("Joined %(t)s ago", { t: this.tenure(n) }); }

    nameOf(n) { return n.isRole ? _t("Open role") : n.name; }

    cardLabel(n) {
        return n.isRole ? _t("Open role: %(t)s", { t: n.title }) : `${n.name}, ${n.title}`;
    }

    toggleTitle(c) { return c.folded ? _t("Expand team (Space)") : _t("Collapse team (Space)"); }

    // ============================================================== chips
    get colorLabel() {
        return { dept: _t("Colour: team"), loc: _t("Colour: location"),
                 type: _t("Colour: employment"), tenure: _t("Colour: time with us") }[this.state.colorBy];
    }

    get chipLabels() {
        return { dept: _t("Team"), loc: _t("Location"), type: _t("Employment") };
    }

    dismissNomgr() { this.state.nomgrDismissed = true; }

    get levelsLabel() {
        return this.state.levels ? _t("%(n)s levels", { n: this.state.levels }) : _t("All levels");
    }

    chipValue(key) {
        const f = this.state.filters;
        if (key === "dept") {
            const d = f.dept && (this.data.departments || []).find((x) => x.id === f.dept);
            return d ? d.name : "";
        }
        if (key === "type") { return f.type ? (this.typeOptions.find((t) => t.k === f.type) || {}).label || "" : ""; }
        return f[key] || "";
    }

    get deptOptions() {
        const count = new Map();
        for (const n of this.nodes) { if (!n.isRole) { count.set(n.dept_id, (count.get(n.dept_id) || 0) + 1); } }
        return (this.data.departments || [])
            .map((d) => ({ k: d.id, label: d.name, n: count.get(d.id) || 0, color: d.color }))
            .filter((d) => d.n)
            .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label));
    }

    get locOptions() {
        const count = new Map();
        for (const n of this.nodes) { if (!n.isRole && n.loc) { count.set(n.loc, (count.get(n.loc) || 0) + 1); } }
        return [...count.entries()].map(([k, n]) => ({ k, label: k, n })).sort((a, b) => b.n - a.n);
    }

    get typeOptions() {
        const label = { fulltime: _t("Full-time"), parttime: _t("Part-time"),
                        contractor: _t("Contractor"), trainee: _t("Trainee") };
        const count = new Map();
        for (const n of this.nodes) { if (!n.isRole && n.typeKey) { count.set(n.typeKey, (count.get(n.typeKey) || 0) + 1); } }
        return Object.keys(label).filter((k) => count.get(k)).map((k) => ({ k, label: label[k], n: count.get(k) }));
    }

    get colorOptions() {
        return [["dept", _t("Team")], ["loc", _t("Location")], ["type", _t("Employment type")], ["tenure", _t("Time with us")]]
            .map(([k, l]) => ({ k, label: l }));
    }

    get levelOptions() {
        return [[0, _t("All levels")], [2, _t("2 levels · leadership")], [3, _t("3 levels · leads")], [4, _t("4 levels")]]
            .map(([k, l]) => ({ k, label: l }));
    }

    get viewOptions() {
        return [
            { k: "tree", ic: "network", label: _t("Top-down"), title: _t("Classic chart") },
            { k: "lr", ic: "listTree", label: _t("Sideways"), title: _t("Left to right — good for deep teams") },
            { k: "teams", ic: "layoutGrid", label: _t("Teams"), title: _t("Who is in each team") },
            { k: "list", ic: "list", label: _t("List"), title: _t("Indented list") },
        ];
    }

    get shortcuts() {
        return [
            ["↑ ↓ ← →", _t("Move between people")], ["Enter", _t("Open the side panel")],
            ["Space", _t("Expand or collapse")], ["/", _t("Search")], ["F", _t("Fit to screen")],
            ["E / C", _t("Expand all / collapse")], ["+ / −", _t("Zoom in / out")], ["Esc", _t("Close")],
        ].concat(this.mayWrite ? [
            ["M", _t("Change manager")], ["A", _t("Add a team member")],
            ["⌘ / Ctrl click", _t("Pick several people")],
        ] : []).concat(this.inPlan ? [["⌘Z / ⇧⌘Z", _t("Undo / redo a planned change")]]
            : this.mayWrite ? [["⌘ / Ctrl Z", _t("Undo the last change")]] : []);
    }

    // ============================================================ actions
    toggleMenu(key) { this.state.menu = this.state.menu === key ? null : key; }

    setFilter(key, val) {
        const f = this.state.filters;
        f[key] = f[key] === val ? null : val;
        this.state.menu = null;
    }

    clearFilter(key, ev) {
        if (ev) { ev.stopPropagation(); }
        this.state.filters[key] = null;
        this.state.menu = null;
    }

    setColor(k) { this.state.colorBy = k; this.state.menu = null; }

    setLevels(k) {
        this.state.levels = k;
        this.state.menu = null;
        this._relayoutAndFit();
    }

    setView(v) {
        this.state.view = v;
        this.state.menu = null;
        if (v === "tree" || v === "lr") { this._relayoutAndFit(); } else { this.relayout(); }
    }

    toggleCompact() {
        this.state.compact = !this.state.compact;
        this._relayoutAndFit();
    }

    _relayoutAndFit() {
        this._pendingFit = true;
        this.relayout();
    }

    setFocus(key) {
        const s = this.state;
        // grey at zero: a number with nothing behind it filters nothing
        const k = this.kpis.find((x) => x.key === key);
        if (k && k.zero && s.focus !== key) { return; }
        s.focus = s.focus === key ? null : key;
        s.menu = null;
        if (!s.focus) {
            // the lane was opened for this focus: fold it again
            if (this._laneByFocus && s.laneOpen) { s.laneOpen = false; this._relayoutAndFit(); }
            this._laneByFocus = false;
            return;
        }
        if (s.view !== "tree" && s.view !== "lr" && s.focus === "nomgr") { s.view = "tree"; }
        // Unfold whatever hides what the number counts: folded branches, and
        // the lane when any of them waits there behind "+N more".
        let opened = 0;
        for (const n of this.nodes) {
            if (!this.emphasised(n)) { continue; }
            if (this.idx.loneSet.has(n.id)) { this._laneByFocus = true; s.laneOpen = true; }
            if (opened < 200) {
                for (const a of ancestors(this.idx, n.id)) { this.collapsed.delete(a.id); }
                opened++;
            }
        }
        // a few lit cards: the view fits to them, not to the whole chart
        this._fitToLit = true;
        this._relayoutAndFit();
    }

    onSearchInput(ev) {
        this.state.q = ev.target.value;
        this.state.sugg = -1;
    }

    get suggestions() {
        const q = this.state.q.trim().toLowerCase();
        if (q.length < 2) { return null; }
        return this.nodes.filter((n) => this.hitsQuery(n, q)).slice(0, 8);
    }

    get noMatchText() {
        return _t("Nobody called “%(q)s”. Try a title or a team.", { q: this.state.q });
    }

    onSearchKey(ev) {
        const hits = this.suggestions || [];
        if (ev.key === "ArrowDown") { this.state.sugg = Math.min(hits.length - 1, this.state.sugg + 1); ev.preventDefault(); }
        else if (ev.key === "ArrowUp") { this.state.sugg = Math.max(0, this.state.sugg - 1); ev.preventDefault(); }
        else if (ev.key === "Enter" && hits[Math.max(0, this.state.sugg)]) { this.jump(hits[Math.max(0, this.state.sugg)].id); }
        else if (ev.key === "Escape") { this.state.q = ""; ev.target.blur(); this.root.el && this.root.el.focus({ preventScroll: true }); }
    }

    jump(id) {
        const s = this.state;
        s.q = "";
        s.sugg = -1;
        if (s.view !== "tree" && s.view !== "lr") { s.view = "tree"; }
        this.select(id);
        if (this.root.el) { this.root.el.focus({ preventScroll: true }); }
    }

    _revealIn(id) {
        let changed = false;
        for (const a of ancestors(this.idx, id)) {
            if (this.collapsed.has(a.id)) { this.collapsed.delete(a.id); changed = true; }
        }
        if (this.idx.loneSet.has(id) && !this.lay?.pos.has(id)) { this.state.laneOpen = true; changed = true; }
        const d = this.idx.depth.get(id) || 0;
        if (this.state.levels && d + 1 > this.state.levels) { this.state.levels = 0; changed = true; }
        return changed;
    }

    select(id) {
        const s = this.state;
        if (!this.idx.byId.has(id)) { return; }
        if (this.idx.byId.get(id).future) { return; }   // a starter's card is a preview
        s.menu = null;
        s.sel = id;
        s.side = id;
        const sn = this.idx.byId.get(id);
        if (s.sideTab === "history") {
            if (sn.isRole) { s.sideTab = "team"; } else { this.loadHistory(id); }
        }
        const moved = this._revealIn(id);
        if (moved) { this.relayout(); }
        if (s.view === "tree" || s.view === "lr") { this._pendingCenter = id; }
    }

    closeSide() { this.state.side = null; this.state.sel = null; }

    async toggle(c) {
        const n = c.n || c;
        if (isUnloaded(this.idx, n)) {
            await this.loadBranch(n);
            this.collapsed.delete(n.id);
        } else if (this.collapsed.has(n.id)) {
            this.collapsed.delete(n.id);
        } else {
            this.collapsed.add(n.id);
        }
        this.state.menu = null;
        this.relayout();
    }

    expandAll() {
        this.collapsed.clear();
        this.state.levels = 0;
        this._relayoutAndFit();
    }

    collapseAll() {
        for (const n of this.nodes) {
            if (this.idx.depth.get(n.id) >= 1 && kidsOf(this.idx, n.id).length) { this.collapsed.add(n.id); }
        }
        this._relayoutAndFit();
    }

    openLane() { this.state.laneOpen = true; this.relayout(); }

    foldLane() { this.state.laneOpen = false; this.relayout(); }

    findMe() {
        const me = this.data && this.data.me;
        if (!me) { return; }
        const s = this.state;
        if (s.view !== "tree" && s.view !== "lr") { s.view = "tree"; }
        this.select(String(me));
    }

    setSideTab(t) {
        this.state.sideTab = t;
        if (t === "history") { this.loadHistory(this.state.side); }
    }

    onHover(id) {
        if (this._hover !== id) { this._hover = id; this._paintPath(); this._placePill(id); }
    }

    onLeave() {
        if (this._hover) { this._hover = null; this._paintPath(); this._placePill(this.state.sel); }
    }

    onCardClick(c, ev) {
        if (this._dragged) { return; }
        if (ev && ev.target.closest("button")) { return; }
        // ⌘/Ctrl-click and Shift-click pick several people (P2)
        if (ev && this.mayWrite && !c.n.isRole && (ev.metaKey || ev.ctrlKey)) { this.pickToggle(c.id); return; }
        if (ev && this.mayWrite && !c.n.isRole && ev.shiftKey) { this.pickRange(c.id); return; }
        if (this.picked.size) { this.pickClear(); }
        this._anchor = c.id;
        this.select(c.id);
    }

    onCardDbl(c) { if (c.hasTeam) { this.toggle(c); } }

    // ---- side panel data
    get sideNode() {
        const id = this.state.side;
        return id && id !== "__changes" && this.idx ? this.idx.byId.get(id) || null : null;
    }

    get showChangesPanel() { return this.state.side === "__changes" && !!this.state.plan; }

    get sideChain() { return this.sideNode ? ancestors(this.idx, this.sideNode.id).reverse() : []; }

    get sideTeam() { return this.sideNode ? kidsOf(this.idx, this.sideNode.id) : []; }

    get sidePeers() {
        const n = this.sideNode;
        if (!n) { return []; }
        const m = this.idx.eff.get(n.id);
        return m ? kidsOf(this.idx, m).filter((x) => x.id !== n.id) : [];
    }

    get sideFacts() {
        const n = this.sideNode;
        if (!n) { return []; }
        const m = this.idx.eff.get(n.id);
        const mgr = m ? this.idx.byId.get(m) : null;
        const dot = n.dotted ? this.idx.byId.get(n.dotted) : null;
        const lv = (this.idx.depth.get(n.id) || 0) + 1;
        return [
            { k: "mgr", label: _t("Reports to"), val: mgr ? this.nameOf(mgr) : "—" },
            { k: "dot", label: _t("Also reports to"), val: dot ? dot.name : "—" },
            { k: "team", label: _t("Team size"),
              val: _t("%(d)s direct · %(t)s total", { d: directCount(this.idx, n), t: totalCount(this.idx, n) }) },
            { k: "lvl", label: _t("Level"), val: _t("%(n)s of %(m)s", { n: lv, m: Math.max(this.counts.levels || 1, lv) }) },
            n.isRole
                ? { k: "why", label: _t("Why it is open"), val: n.reasonLabel || "—" }
                : { k: "with", label: _t("With us"), val: this.tenure(n) },
            n.isRole
                ? { k: "count", label: _t("To hire"), val: String(n.count || 1) }
                : { k: "type", label: _t("Employment"), val: n.type || "—" },
        ];
    }

    get sideReadOnlyLine() {
        if (this.state.asOf) { return _t("Go back to today to make changes."); }
        if (this.planView) { return _t("This plan has been sent — it can't be changed here."); }
        return _t("Ask an HR user to change who reports to whom.");
    }

    get sideNoTeamText() {
        const n = this.sideNode;
        return n ? _t("Nobody reports to %(n)s yet.", { n: this.nameOf(n) }) : "";
    }

    get sideNoPeersText() {
        const n = this.sideNode;
        if (!n) { return ""; }
        const m = this.idx.eff.get(n.id);
        if (!m) { return _t("Top of the chart — no peers."); }
        return _t("No peers — the only one reporting to %(m)s.", { m: this.nameOf(this.idx.byId.get(m)) });
    }

    teamTabLabel(n) { return _t("Team (%(n)s)", { n }); }

    // ---- the employee record
    get drawerCmp() {
        const r = registry.category("pb_people_drawer");
        return r.contains("employee_360") ? r.get("employee_360") : null;
    }

    get drawerProps() {
        return { empId: this.state.drawerEmpId, onClose: () => { this.state.drawerEmpId = null; } };
    }

    openRecord(n) {
        if (!n || n.isRole || !n.empId) { return; }
        if (this.drawerCmp) { this.state.drawerEmpId = n.empId; return; }
        this.action.doAction({ type: "ir.actions.client", tag: "pb_employee_detail",
                               name: _t("Employee"), params: { emp_id: n.empId } });
    }

    openEmployees() {
        openHub(this.action, { xmlid: "pb_people_hub.action_pb_people_hub", lens: "employees" });
    }

    // ---- export / print
    printChart() {
        this.state.menu = null;
        setTimeout(() => window.print(), 50);
    }

    retry() {
        this.state.loaded = false;
        this.load();
    }

    // ======================================================= list + teams
    get listRows() {
        void this.state.rev;
        if (!this.idx) { return []; }
        const rows = [];
        const walk = (n, d) => {
            rows.push({ n, d, direct: directCount(this.idx, n), total: totalCount(this.idx, n),
                        folded: this.collapsed.has(n.id) || isUnloaded(this.idx, n) });
            if (this.collapsed.has(n.id)) { return; }
            for (const k of kidsOf(this.idx, n.id)) { walk(k, d + 1); }
        };
        const trees = this.idx.trees.slice().sort((a, b) => totalCount(this.idx, b) - totalCount(this.idx, a));
        for (const t of trees) { walk(t, 0); }
        for (const l of this.idx.lone) { walk(l, 0); }
        return rows;
    }

    listMgr(n) {
        const m = this.idx.eff.get(n.id);
        return m ? this.nameOf(this.idx.byId.get(m)) : "";
    }

    /** No manager and no team: the "no manager yet" lane. */
    isLone(n) { return !!(this.idx && this.idx.loneSet.has(n.id)); }

    rowStyle(r) { return `padding-left:${r.d * 22}px`; }

    rowDim(n) { return this.anyFilter && !this.emphasised(n); }

    get teamGroups() {
        void this.state.rev;
        if (!this.idx) { return []; }
        const by = new Map();
        for (const n of this.nodes) {
            const k = n.dept_id || 0;
            if (!by.has(k)) { by.set(k, []); }
            by.get(k).push(n);
        }
        const out = [];
        for (const [k, list] of by) {
            const ids = new Set(list.map((x) => x.id));
            list.sort((a, b) => (this.idx.depth.get(a.id) - this.idx.depth.get(b.id)) || a.order - b.order);
            const lead = list.find((p) => !p.isRole && !ids.has(this.idx.eff.get(p.id)) && directCount(this.idx, p) > 0)
                || null;
            const people = list.filter((p) => !p.isRole).length;
            const open = list.length - people;
            out.push({
                k, name: k ? (list[0].dept || _t("Team")) : _t("No team"), color: this.deptColor.get(k) || "#64748B",
                list, lead, sub: open ? _t("%(p)s people · %(o)s open", { p: people, o: open }) : _t("%(p)s people", { p: people }),
                people,
            });
        }
        return out.sort((a, b) => b.people - a.people);
    }

    leadNote(g, n) { return g.lead === n ? _t(" · leads the team") : ""; }

    // ========================================================= pan & zoom
    /** The canvas box, measured once per draw or resize — never per pan frame
     *  (a measure right after a move forces the page's style work). */
    _canvasRect() {
        const el = this.canvasRef.el;
        if (!el) { return { width: 800, height: 600, left: 0, top: 0 }; }
        if (!this._cvRect || this._cvEl !== el) {
            this._cvRect = el.getBoundingClientRect();
            this._cvEl = el;
        }
        return this._cvRect;
    }

    /**
     * Move the world. P4: never an inline style — a paused Web Animation whose
     * keyframes are rewritten (P2's ghost trick, G15): an inline transform
     * re-checked the page's styles on every pan frame (42 ms at 657 cards,
     * 70 ms at 1,500). A glide (`anim`) is a short animation played over the
     * paused one and dropped when it ends.
     */
    applyTransform(anim) {
        const w = this.worldRef.el;
        if (!w) { return; }
        const tf = `translate(${this.vp.px}px,${this.vp.py}px) scale(${this.vp.zoom})`;
        if (this._glide) {
            if (!anim) { this._glide.cancel(); this._glide = null; }
        }
        if (anim && this._worldTf && this._worldTf !== tf && this._worldEl === w) {
            let from = this._worldTf;
            if (this._glide) {
                try { from = getComputedStyle(w).transform; } catch { /* keep the last one */ }
                this._glide.cancel();
            }
            const g = w.animate([{ transform: from }, { transform: tf }],
                                { duration: GLIDE_MS, easing: "cubic-bezier(.2,.8,.2,1)" });
            this._glide = g;
            g.onfinish = () => { if (this._glide === g) { this._glide = null; g.cancel(); } };
        }
        if (this._worldTf !== tf || this._worldEl !== w) {
            this._slide(w, tf);
            this._worldTf = tf;
            this._worldEl = w;
        }
        const pct = Math.round(this.vp.zoom * 100) + "%";
        if (this.pctRef.el && this.pctRef.el.textContent !== pct) { this.pctRef.el.textContent = pct; }
        this._drawViewport();
        this._visLater();
    }

    fit(anim = true) {
        if (!this.lay) { return; }
        const b = bounds(this.lay.pos, this.lay.lane);
        const cv = this._canvasRect();
        // Never shrink below readable (G3); centre on the top and let people pan.
        const want = Math.min((cv.width - 60) / b.w, (cv.height - 120) / b.h);
        const z = Math.min(1.1, Math.max(MIN_FIT, want));
        this.vp.zoom = z;
        const top = this.idx.trees.length
            ? this.idx.trees.slice().sort((a, b2) => totalCount(this.idx, b2) - totalCount(this.idx, a))[0] : null;
        const rp = top && this.lay.pos.get(top.id);
        if (want < MIN_FIT && rp && this.idx.trees.length === 1) {
            // one big tree: its top in the middle, people pan down
            this.vp.px = cv.width / 2 - (rp.x + rp.w / 2) * z;
            this.vp.py = 36 - b.y * z;
        } else if (want < MIN_FIT) {
            // many teams side by side: start reading at the top left
            this.vp.px = 30 - b.x * z;
            this.vp.py = 36 - b.y * z;
        } else {
            this.vp.px = (cv.width - b.w * z) / 2 - b.x * z;
            this.vp.py = 36 - b.y * z;
        }
        this.applyTransform(anim);
    }

    /** Fit the view to a handful of cards (a focus that lit only a few). */
    fitTo(cards) {
        const cv = this._canvasRect();
        const x0 = Math.min(...cards.map((c) => c.x));
        const y0 = Math.min(...cards.map((c) => c.y));
        const x1 = Math.max(...cards.map((c) => c.x + c.w));
        const y1 = Math.max(...cards.map((c) => c.y + c.h));
        const want = Math.min((cv.width - 120) / (x1 - x0), (cv.height - 160) / (y1 - y0));
        const z = Math.min(1, Math.max(MIN_FIT, want));
        this.vp.zoom = z;
        this.vp.px = cv.width / 2 - ((x0 + x1) / 2) * z;
        this.vp.py = cv.height / 2 - ((y0 + y1) / 2) * z;
        this.applyTransform(true);
    }

    centerOn(id, anim = true) {
        const p = this.lay && this.lay.pos.get(id);
        if (!p) { return; }
        const cv = this._canvasRect();
        if (this.vp.zoom < 0.6) { this.vp.zoom = 0.9; }
        const off = this.state.side && window.innerWidth <= 1500 ? 190 : 0;
        this.vp.px = cv.width / 2 - off - (p.x + p.w / 2) * this.vp.zoom;
        this.vp.py = cv.height / 2 - (p.y + p.h / 2) * this.vp.zoom - 40;
        this.applyTransform(anim);
    }

    zoomAt(f, cx, cy) {
        const z = Math.min(2.5, Math.max(0.12, this.vp.zoom * f));
        const cv = this._canvasRect();
        cx = cx ?? cv.width / 2;
        cy = cy ?? cv.height / 2;
        this.vp.px = cx - (cx - this.vp.px) * (z / this.vp.zoom);
        this.vp.py = cy - (cy - this.vp.py) * (z / this.vp.zoom);
        this.vp.zoom = z;
        this.applyTransform(false);
    }

    zoomIn() { this.zoomAt(1.2); }

    zoomOut() { this.zoomAt(1 / 1.2); }

    zoomReset() { this.vp.zoom = 1; this.applyTransform(true); }

    get minimap() {
        if (!this.lay) { return null; }
        if (this._mmRev === this.state.rev) { return this._mm; }
        this._mmRev = this.state.rev;
        this._mm = this._buildMinimap();
        return this._mm;
    }

    _buildMinimap() {
        const b = bounds(this.lay.pos, this.lay.lane);
        const pad = 40;
        const rects = [];
        for (const [id, p] of this.lay.pos) {
            const n = this.idx.byId.get(id);
            rects.push({ id, x: p.x, y: p.y, w: p.w, h: p.h, op: !!(n && n.isRole) });
        }
        return { vb: `${b.x - pad} ${b.y - pad} ${b.w + pad * 2} ${b.h + pad * 2}`, rects, b, pad };
    }

    _drawViewport() {
        const r = this.vpRef.el;
        if (!r) { return; }
        const cv = this._canvasRect();
        const z = this.vp.zoom;
        r.setAttribute("x", -this.vp.px / z);
        r.setAttribute("y", -this.vp.py / z);
        r.setAttribute("width", cv.width / z);
        r.setAttribute("height", cv.height / z);
    }

    onMinimapClick(ev) {
        const mm = ev.currentTarget;
        const mmap = this.minimap;
        if (!mmap) { return; }
        const r = mm.getBoundingClientRect();
        const { b, pad } = mmap;
        const bw = b.w + pad * 2;
        const bh = b.h + pad * 2;
        const s = Math.max(bw / r.width, bh / r.height);
        const wx = b.x - pad + (ev.clientX - r.left) * s - (r.width * s - bw) / 2;
        const wy = b.y - pad + (ev.clientY - r.top) * s - (r.height * s - bh) / 2;
        const cv = this._canvasRect();
        this.vp.px = cv.width / 2 - wx * this.vp.zoom;
        this.vp.py = cv.height / 2 - wy * this.vp.zoom;
        this.applyTransform(true);
    }

    _afterDraw() {
        this._cvRect = null;
        if (this.state.loaded && this._t0) {
            this.perf.renderMs = Math.round(performance.now() - this._t0);
            this._t0 = 0;
            if (this.root.el) {
                this.root.el.dataset.layoutMs = this.perf.layoutMs;
                this.root.el.dataset.renderMs = this.perf.renderMs;
                this.root.el.dataset.payloadMs = this.perf.payloadMs;
                this.root.el.dataset.cards = this.cards.length;
            }
        }
        if (this._pendingFit && this.worldRef.el) {
            this._pendingFit = false;
            const lit = this._fitToLit ? this.cards.filter((c) => !this.cardState(c).includes("dim")) : [];
            this._fitToLit = false;
            if (lit.length && lit.length <= 40 && lit.length < this.cards.length) { this.fitTo(lit); }
            else { this.fit(!this.firstDraw); }
            if (this.firstDraw) { setTimeout(() => { this.firstDraw = false; }, 900); }
        } else {
            this.applyTransform(false);
        }
        this._paintPath();
        this._afterEdit();
        if (this._pendingCenter && this.worldRef.el) {
            const id = this._pendingCenter;
            this._pendingCenter = null;
            this.centerOn(id);
        }
        this._updateVisible();
    }

    // ===================================================== global listeners
    _bind() {
        const root = this.root.el;
        if (!root) { return; }
        this._onWheel = (e) => {
            const cv = e.target.closest && e.target.closest(".pboc-canvas");
            if (!cv || !this.worldRef.el) { return; }
            if (e.target.closest(".pboc-menu, .pboc-sugg")) { return; }
            e.preventDefault();
            const r = cv.getBoundingClientRect();
            if (e.ctrlKey || e.metaKey) {
                this.zoomAt(e.deltaY < 0 ? 1.1 : 0.9, e.clientX - r.left, e.clientY - r.top);
            } else {
                this.vp.px -= e.deltaX;
                this.vp.py -= e.deltaY;
                this.applyTransform(false);
            }
        };
        this._onDown = (e) => {
            if (!e.target.closest(".pboc-cw")) {
                if (this.state.menu) { this.state.menu = null; }
            }
            if (this.state.ctx && !e.target.closest(".pboc-ctx")) { this.state.ctx = null; }
            if (this._dragPress(e)) { return; }
            const cv = e.target.closest(".pboc-canvas");
            if (!cv || !this.worldRef.el || e.button !== 0) { return; }
            if (e.target.closest(".pboc-node, .pboc-float, button, .pboc-more, .pboc-lane-act")) { return; }
            this._pan = { x: e.clientX, y: e.clientY, px: this.vp.px, py: this.vp.py, moved: false };
            cv.dataset.grab = "1";
        };
        this._onMove = (e) => {
            if (this._dragMove(e)) { return; }
            if (!this._pan) { return; }
            const dx = e.clientX - this._pan.x;
            const dy = e.clientY - this._pan.y;
            if (Math.abs(dx) + Math.abs(dy) > 3) { this._pan.moved = true; }
            this.vp.px = this._pan.px + dx;
            this.vp.py = this._pan.py + dy;
            this.applyTransform(false);
        };
        this._onUp = () => {
            if (this._dragUp()) { return; }
            if (!this._pan) { return; }
            this._pan = null;
            const cv = this.canvasRef.el;
            if (cv) { delete cv.dataset.grab; }
        };
        this._onKey = (e) => this.onKey(e);
        this._onResize = () => { this._cvRect = null; this._drawViewport(); this._visLater(); };
        root.addEventListener("wheel", this._onWheel, { passive: false });
        root.addEventListener("keydown", this._onKey);
        document.addEventListener("pointerdown", this._onDown, true);
        window.addEventListener("pointermove", this._onMove);
        window.addEventListener("pointerup", this._onUp);
        window.addEventListener("resize", this._onResize);
    }

    _unbind() {
        const root = this.root.el;
        if (root) {
            root.removeEventListener("wheel", this._onWheel, { passive: false });
            root.removeEventListener("keydown", this._onKey);
        }
        document.removeEventListener("pointerdown", this._onDown, true);
        window.removeEventListener("pointermove", this._onMove);
        window.removeEventListener("pointerup", this._onUp);
        window.removeEventListener("resize", this._onResize);
        clearTimeout(this._visT);
        if (this._glide) { this._glide.cancel(); this._glide = null; }
    }

    onKey(e) {
        const s = this.state;
        if (!s.loaded || s.failed || s.drawerEmpId) { return; }
        const typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement && document.activeElement.tagName);
        if (e.key === "Escape") {
            if (s.dlg) { s.dlg = null; }
            else if (s.ctx) { s.ctx = null; }
            else if (s.menu) { s.menu = null; }
            else if (s.pickN) { this.pickClear(); }
            else if (s.q) { s.q = ""; }
            else { s.side = null; s.sel = null; }
            return;
        }
        if (s.dlg) { return; }
        if (!typing && (e.metaKey || e.ctrlKey) && (e.key === "z" || e.key === "Z")) {
            if (this.inPlan) {
                e.preventDefault();
                if (e.shiftKey) { this.planRedo(); } else { this.planUndo(); }
            } else if (this.mayWrite && !e.shiftKey) { e.preventDefault(); this.undo(); }
            return;
        }
        if (typing || e.metaKey || e.ctrlKey || e.altKey) { return; }
        const canvas = s.view === "tree" || s.view === "lr";
        if (e.key === "/") { e.preventDefault(); if (this.searchRef.el) { this.searchRef.el.focus(); } return; }
        if ((e.key === "f" || e.key === "F") && canvas) { this.fit(); return; }
        if (e.key === "e" || e.key === "E") { this.expandAll(); return; }
        if (e.key === "c" || e.key === "C") { this.collapseAll(); return; }
        if ((e.key === "+" || e.key === "=") && canvas) { this.zoomIn(); return; }
        if ((e.key === "-" || e.key === "−") && canvas) { this.zoomOut(); return; }
        const cur = s.sel ? this.idx.byId.get(s.sel) : null;
        if (e.key === "Enter" && cur) { s.side = cur.id; return; }
        if ((e.key === "m" || e.key === "M") && cur && this.mayWrite) { e.preventDefault(); this.act("changemgr", cur.id); return; }
        if ((e.key === "a" || e.key === "A") && cur && this.mayWrite && !cur.isRole) { e.preventDefault(); this.act("addmember", cur.id); return; }
        if (e.key === " " && cur) { e.preventDefault(); if (directCount(this.idx, cur)) { this.toggle(cur); } return; }
        if (e.key.startsWith("Arrow")) {
            e.preventDefault();
            if (!cur) {
                const r = this.idx.trees[0] || this.idx.roots[0];
                if (r) { this.select(r.id); }
                return;
            }
            const lr = s.view === "lr";
            const up = lr ? "ArrowLeft" : "ArrowUp";
            const down = lr ? "ArrowRight" : "ArrowDown";
            const next = lr ? "ArrowDown" : "ArrowRight";
            const prev = lr ? "ArrowUp" : "ArrowLeft";
            let t = null;
            const m = this.idx.eff.get(cur.id);
            if (e.key === up && m) { t = m; }
            if (e.key === down) {
                if (isUnloaded(this.idx, cur)) { this.toggle(cur); return; }
                this.collapsed.delete(cur.id);
                const k = kidsOf(this.idx, cur.id)[0];
                t = k ? k.id : null;
            }
            if (e.key === next || e.key === prev) {
                const sib = m ? kidsOf(this.idx, m) : this.idx.trees.concat(this.idx.lone);
                const i = sib.findIndex((x) => x.id === cur.id);
                const o = sib[i + (e.key === next ? 1 : -1)];
                t = o ? o.id : null;
            }
            if (t) {
                const keepSide = !!s.side;
                this.select(t);
                if (!keepSide) { s.side = null; }
            }
        }
    }

    // ================================================================ misc
    icon(n, s = 16) { return icon(n, s); }

    get cardW() { return cardSize(this.state.compact).w; }
}

installEdit(PbOrgChart);
installPlan(PbOrgChart);
installExport(PbOrgChart);

registry.category("actions").add("pb_orgchart", PbOrgChart);
