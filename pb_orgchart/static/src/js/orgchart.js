/** @odoo-module **/
/**
 * ORG CHART P1 — People › Org chart, read-only.
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
    directCount, totalCount, isUnloaded, colorOf, cardSize,
    LOC_COLORS, TYPE_COLORS, TENURE, daysSince,
} from "@pb_orgchart/js/orgchart_layout";

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
    static components = { HubBackChip, PbOcCard };
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
        });
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

        onWillStart(() => this.load());
        onMounted(() => {
            this._bind();
            this._afterDraw();
            if (this.root.el) { this.root.el.focus({ preventScroll: true }); }
        });
        onPatched(() => this._afterDraw());
        onWillUnmount(() => this._unbind());
    }

    // ================================================================ data
    async load() {
        this.state.failed = false;
        const t = performance.now();
        try {
            this.data = await this.orm.call("pb.orgchart", "get_chart", []);
        } catch (e) {
            console.warn("pb_orgchart: chart failed", e);
            this.state.failed = true;
            this.state.loaded = true;
            return;
        }
        this.perf.payloadMs = Math.round(performance.now() - t);
        const d = this.data;
        this.deptColor = new Map((d.departments || []).map((x) => [x.id, x.color]));
        this.nodes = [];
        this._ingest(d.people || [], d.open_roles || []);
        this.idx = buildIndex(this.nodes);
        this._initialFold();
        this.firstDraw = true;
        this._pendingFit = true;
        this.relayout();
        this.state.loaded = true;
    }

    _ingest(people, roles) {
        const have = new Set(this.nodes.map((n) => n.id));
        let order = this.nodes.length;
        for (const p of people) {
            const id = String(p.id);
            if (have.has(id)) { continue; }
            this.nodes.push({
                id, empId: p.id, isRole: false, name: p.name || "", ini: p.ini || "",
                title: p.title || "", dept_id: p.dept_id || false, dept: p.dept || "",
                loc: p.loc || "", type: p.type || "", typeKey: p.type_key || "",
                joined: p.joined || false,
                mgr: p.manager_id ? String(p.manager_id) : null,
                dotted: p.dotted_id ? String(p.dotted_id) : null,
                status: p.status || "", note: p.status_note || "",
                avatar: p.avatar || false, nReports: p.n_reports || 0,
                nTotal: p.n_total || 0, order: order++,
            });
            have.add(id);
        }
        for (const o of roles) {
            if (have.has(o.id)) { continue; }
            this.nodes.push({
                id: o.id, jobId: o.job_id, isRole: true, name: "", ini: "",
                title: o.title || "", dept_id: o.dept_id || false, dept: o.dept || "",
                loc: o.loc || "", type: "", typeKey: "", joined: false,
                mgr: o.manager_id ? String(o.manager_id) : null, dotted: null,
                status: "", note: "", avatar: false, nReports: 0, nTotal: 0,
                count: o.count || 1, hiring: o.hiring || "", order: order++,
            });
            have.add(o.id);
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
            const b = await this.orm.call("pb.orgchart", "get_branch", [n.empId]);
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
            });
            this.edgeList = edges(this.idx, this.lay, s.view === "lr");
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
            if (n.isRole) { tags.push({ k: "role", cls: "amber", ic: "briefcase", text: n.hiring || _t("Open role") }); }
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
            const sig = [p.x, p.y, p.w, p.h, !!p.stack, !!p.lane, folded, direct, total,
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
            g.innerHTML = path ? this.edgeList
                .filter((e) => !e.dot && path.has(e.id) && path.has(e.from))
                .map((e) => `<path class="hi" d="${e.d}"/>`).join("") : "";
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
        return !!(this.idx && this.idx.trees.length && this.idx.lone.filter((n) => !n.isRole).length > 10);
    }

    get laneHint() {
        const n = this.idx ? this.idx.lone.filter((x) => !x.isRole).length : 0;
        return _t("%(n)s people have no manager yet", { n: this.fmtInt(n) });
    }

    get laneTitle() {
        return _t("No manager yet · set a manager on the employee record");
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
        ];
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
        s.menu = null;
        s.sel = id;
        s.side = id;
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

    setSideTab(t) { this.state.sideTab = t; }

    onHover(id) { if (this._hover !== id) { this._hover = id; this._paintPath(); } }

    onLeave() { if (this._hover) { this._hover = null; this._paintPath(); } }

    onCardClick(c, ev) {
        if (this._dragged) { return; }
        if (ev && ev.target.closest("button")) { return; }
        this.select(c.id);
    }

    onCardDbl(c) { if (c.hasTeam) { this.toggle(c); } }

    // ---- side panel data
    get sideNode() {
        const id = this.state.side;
        return id && this.idx ? this.idx.byId.get(id) || null : null;
    }

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
            { k: "with", label: _t("With us"), val: n.isRole ? "—" : this.tenure(n) },
            { k: "type", label: _t("Employment"), val: n.isRole ? "—" : (n.type || "—") },
        ];
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
    exportCsv() {
        this.state.menu = null;
        const esc = (v) => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
        const head = [_t("Name"), _t("Title"), _t("Team"), _t("Reports to"), _t("Location"), _t("Employment"), _t("Joined")];
        const lines = [head.map(esc).join(",")];
        const rows = this.nodes.slice().sort((a, b) =>
            (this.idx.depth.get(a.id) - this.idx.depth.get(b.id)) || a.order - b.order);
        for (const n of rows) {
            const m = this.idx.eff.get(n.id);
            const mgr = m ? this.idx.byId.get(m) : null;
            lines.push([this.nameOf(n), n.title, n.dept, mgr ? this.nameOf(mgr) : "", n.loc,
                        n.isRole ? "" : n.type, n.joined || ""].map(esc).join(","));
        }
        const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const d = new Date();
        const day = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        a.download = `org-chart-${day}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        this.notif.add(_t("Spreadsheet saved with %(n)s rows.", { n: this.fmtInt(rows.length) }), { type: "success" });
    }

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
    _canvasRect() {
        const el = this.canvasRef.el;
        return el ? el.getBoundingClientRect() : { width: 800, height: 600, left: 0, top: 0 };
    }

    applyTransform(anim) {
        const w = this.worldRef.el;
        if (!w) { return; }
        if (anim) { w.dataset.anim = "1"; } else if (w.dataset.anim) { delete w.dataset.anim; }
        w.style.transform = `translate(${this.vp.px}px,${this.vp.py}px) scale(${this.vp.zoom})`;
        if (this.pctRef.el) { this.pctRef.el.textContent = Math.round(this.vp.zoom * 100) + "%"; }
        this._drawViewport();
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
            this.fit(!this.firstDraw);
            if (this.firstDraw) { setTimeout(() => { this.firstDraw = false; }, 900); }
        } else {
            this.applyTransform(false);
        }
        this._paintPath();
        if (this._pendingCenter && this.worldRef.el) {
            const id = this._pendingCenter;
            this._pendingCenter = null;
            this.centerOn(id);
        }
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
            const cv = e.target.closest(".pboc-canvas");
            if (!cv || !this.worldRef.el || e.button !== 0) { return; }
            if (e.target.closest(".pboc-node, .pboc-float, button, .pboc-more, .pboc-lane-act")) { return; }
            this._pan = { x: e.clientX, y: e.clientY, px: this.vp.px, py: this.vp.py, moved: false };
            cv.dataset.grab = "1";
        };
        this._onMove = (e) => {
            if (!this._pan) { return; }
            const dx = e.clientX - this._pan.x;
            const dy = e.clientY - this._pan.y;
            if (Math.abs(dx) + Math.abs(dy) > 3) { this._pan.moved = true; }
            this.vp.px = this._pan.px + dx;
            this.vp.py = this._pan.py + dy;
            this.applyTransform(false);
        };
        this._onUp = () => {
            if (!this._pan) { return; }
            this._pan = null;
            const cv = this.canvasRef.el;
            if (cv) { delete cv.dataset.grab; }
        };
        this._onKey = (e) => this.onKey(e);
        this._onResize = () => this._drawViewport();
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
    }

    onKey(e) {
        const s = this.state;
        if (!s.loaded || s.failed || s.drawerEmpId) { return; }
        const typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement && document.activeElement.tagName);
        if (e.key === "Escape") {
            if (s.menu) { s.menu = null; }
            else if (s.q) { s.q = ""; }
            else { s.side = null; s.sel = null; }
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

registry.category("actions").add("pb_orgchart", PbOrgChart);
