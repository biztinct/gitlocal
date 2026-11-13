/** @odoo-module **/
/**
 * ORG CHART P2 — changing the chart, live. The editing half of PbOrgChart,
 * installed onto its prototype (`installEdit`) so orgchart.js stays the
 * read-only chart P1 built.
 *
 * Performance rules (ORGCHART_P2 §3.1, ledger G12): on this app a class
 * change or an inserted element anywhere costs a whole-page style check
 * (~150 ms with a big chart). So:
 *   * drag state is DATA ATTRIBUTES (`data-drag`, `data-over`), picks are
 *     `data-pk`, the flash after a move is `data-flash`;
 *   * the ghost card, the drag hint and the quick-action pill are mounted
 *     ONCE with the chart; they show and hide by `data-on`, and they MOVE by
 *     a paused Web Animation whose keyframe is rewritten (`_slide`). Writing
 *     their inline `style` costs ~60 ms of whole-page style work per pointer
 *     move on payobook (657 cards); the animation costs 0.08 ms (G15);
 *   * `elementFromPoint` → closest card is the drop target: nothing is
 *     inserted per pointer move;
 *   * after a write the server's own rows for what it touched are patched
 *     into `this.nodes`, then `buildIndex` + `relayout()` — cards keep their
 *     identity, only the touched ones re-render.
 */
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { deserializeDate } from "@web/core/l10n/dates";
import {
    buildIndex, kidsOf, ancestors, descendants, directCount, isUnloaded,
} from "@pb_orgchart/js/orgchart_layout";

const DRAG_START = 6;      // px of travel before a press becomes a drag
const EDGE = 56;           // px from the canvas edge where dragging pans
const UNDO_KEEP = 20;

/** A person row of the payload → the chart's node (P1 shape). */
export function personNode(p, order) {
    return {
        id: String(p.id), empId: p.id, isRole: false, name: p.name || "", ini: p.ini || "",
        title: p.title || "", dept_id: p.dept_id || false, dept: p.dept || "",
        loc: p.loc || "", type: p.type || "", typeKey: p.type_key || "",
        joined: p.joined || false,
        mgr: p.manager_id ? String(p.manager_id) : null,
        dotted: p.dotted_id ? String(p.dotted_id) : null,
        status: p.status || "", note: p.status_note || "",
        avatar: p.avatar || false, nReports: p.n_reports || 0,
        nTotal: p.n_total || 0, changed: !!p.changed, order,
    };
}

/** A future starter (an accepted offer, time machine P3): a preview card. */
export function starterNode(f, order) {
    return {
        id: f.id, empId: null, isRole: false, future: true, name: f.name || "", ini: f.ini || "",
        title: f.title || "", dept_id: f.dept_id || false, dept: f.dept || "",
        loc: f.loc || "", type: "", typeKey: "", joined: false,
        mgr: f.manager_id ? String(f.manager_id) : null, dotted: null,
        status: "", note: "", avatar: false, nReports: 0, nTotal: 0,
        startLabel: f.start_label || "", order,
    };
}

/** An open-role row of the payload → the chart's node. */
export function roleNode(o, order) {
    return {
        id: o.id, jobId: o.job_id, isRole: true, name: "", ini: "",
        title: o.title || "", dept_id: o.dept_id || false, dept: o.dept || "",
        loc: o.loc || "", type: "", typeKey: "", joined: false,
        mgr: o.manager_id ? String(o.manager_id) : null, dotted: null,
        status: "", note: "", avatar: false, nReports: 0, nTotal: 0,
        count: o.count || 1, hiring: o.hiring || "", reason: o.reason || false,
        reasonLabel: o.reason_label || "", virtual: !!o.virtual, changed: !!o.changed, order,
    };
}

class OcEdit {
    /**
     * Put `el` at transform `tf` without touching its style attribute: one
     * paused, never-ending animation per element whose keyframes are
     * replaced. An inline style write re-checks the whole page's styles on
     * this app (G12/G15); an animation update does not.
     */
    _slide(el, tf) {
        if (!el) { return; }
        this._anims = this._anims || new WeakMap();
        let a = this._anims.get(el);
        if (!a) {
            a = el.animate([{ transform: tf }, { transform: tf }], { duration: 1e9, fill: "forwards" });
            a.pause();
            this._anims.set(el, a);
        } else {
            a.effect.setKeyframes([{ transform: tf }, { transform: tf }]);
        }
    }

    _show(el, on) {
        if (!el) { return; }
        if (on && !el.dataset.on) { el.dataset.on = "1"; }
        if (!on && el.dataset.on) { delete el.dataset.on; }
    }

    _setupEdit() {
        this.picked = new Set();
        this._pkMarked = [];
        this._anchor = null;
        this._press = null;
        this._drag = null;
        this._undo = [];
        this._writing = false;
        this.hist = new Map();
        this._dlgSeq = 0;
        this._pillId = null;
    }

    // ============================================================ facts
    /** May change the chart NOW: HR rights, today, and not a sent plan. In
     *  planning mode the changes go into the plan (P3). */
    get mayWrite() {
        return !!(this.data && this.data.may_write) && !this.state.asOf && !this.planView;
    }

    get canvasView() { return this.state.view === "tree" || this.state.view === "lr"; }

    nodeOf(id) { return (id != null && this.idx && this.idx.byId.get(String(id))) || null; }

    /** "Ash Sohani" for a person, "the open Agronomist role" for a role. */
    who(n) {
        if (!n) { return _t("nobody"); }
        return n.isRole ? _t("the open %(t)s role", { t: n.title }) : n.name;
    }

    mgrOf(n) { return n ? this.nodeOf(this.idx.eff.get(n.id)) : null; }

    /** True when `id` sits anywhere inside `ancId`'s team. */
    isInside(ancId, id) { return ancestors(this.idx, String(id)).some((a) => a.id === String(ancId)); }

    /** Can these people be dropped on `toId`? The server judges again. */
    dropVerdict(ids, toId) {
        const to = this.nodeOf(toId);
        if (!to) { return { ok: false, why: "none", text: "" }; }
        if (to.isRole) {
            return { ok: false, why: "role", text: _t("An open role can't be a manager until someone fills it.") };
        }
        if (to.future) {
            return { ok: false, why: "role", text: _t("%(p)s has not started yet.", { p: to.name }) };
        }
        for (const f of ids) {
            if (this.isInside(f, toId)) {
                return { ok: false, why: "loop",
                         text: _t("Can't do that — %(m)s is inside %(p)s's own team.", { m: to.name, p: this.nodeOf(f).name }) };
            }
        }
        if (ids.every((f) => this.idx.eff.get(f) === to.id)) {
            const text = ids.length === 1
                ? _t("%(p)s already reports to %(m)s.", { p: this.nodeOf(ids[0]).name, m: to.name })
                : _t("They already report to %(m)s.", { m: to.name });
            return { ok: false, why: "same", text };
        }
        return { ok: true };
    }

    // ============================================================ writes
    /**
     * One write RPC: the server's sentence becomes the toast (rose on a
     * refusal), its rows patch the chart, and a success offers Undo.
     * Returns the answer, or null when it was refused.
     */
    async runWrite(method, args, opts = {}) {
        if (this._writing) { return null; }
        this._writing = true;
        this.state.writing = true;
        let res = null;
        try {
            res = await this.orm.call("pb.orgchart", method, args);
        } catch (e) {
            console.warn("pb_orgchart: write failed", e);
            res = { error: _t("That change could not be saved. Nothing was changed — try again.") };
        } finally {
            this._writing = false;
            this.state.writing = false;
        }
        if (!res || res.error) {
            this.notif.add((res && res.error) || _t("That change could not be saved."), { type: "danger" });
            return null;
        }
        await this._afterWrite(res, opts);
        const entry = res.undo ? { undo: res.undo, label: res.label } : null;
        if (opts.undoOf) {
            this.notif.add(_t("Undone: %(l)s", { l: opts.undoOf.label }), { type: "info" });
        } else if (entry) {
            this._undo.push(entry);
            if (this._undo.length > UNDO_KEEP) { this._undo.shift(); }
            const close = this.notif.add(res.label, {
                type: "success",
                // long enough to read the sentence and reach for Undo
                autocloseDelay: 10000,
                buttons: [{ name: _t("Undo"), primary: true, onClick: () => { close(); this.undo(entry); } }],
            });
        } else {
            this.notif.add(res.label, { type: "success" });
        }
        return res;
    }

    async _afterWrite(res, opts) {
        const touched = this.applyRefresh(res.refresh);
        if (opts.clearPicks) { this.pickClear(true); }
        if (opts.open) {
            // dropping on a folded manager opens their team
            const t = this.nodeOf(opts.open);
            if (t && isUnloaded(this.idx, t)) { await this.loadBranch(t); }
            this.collapsed.delete(String(opts.open));
        }
        for (const id of opts.reveal || []) { this._revealIn(String(id)); }
        this._flashIds = (opts.reveal && opts.reveal.length ? opts.reveal : touched).map(String);
        this._pendingReveal = opts.reveal && opts.reveal.length === 1 ? String(opts.reveal[0]) : null;
        this.relayout();
        if (this.state.side && this.state.sideTab === "history") { this.loadHistory(this.state.side); }
    }

    /**
     * Patch the chart with the server's rows (no client-side guessing): a
     * known row is replaced, a new one joins when its manager is on the
     * chart, roles that closed leave. Returns the touched ids.
     */
    applyRefresh(r) {
        if (!r) { return []; }
        const at = new Map(this.nodes.map((n, i) => [n.id, i]));
        const touched = [];
        const put = (node) => {
            const i = at.get(node.id);
            if (i !== undefined) {
                node.order = this.nodes[i].order;
                this.nodes[i] = node;
            } else if (!node.mgr || at.has(node.mgr)) {
                this.nodes.push(node);
                at.set(node.id, this.nodes.length - 1);
            } else {
                return;
            }
            touched.push(node.id);
        };
        for (const p of r.people || []) { put(personNode(p, this._order++)); }
        for (const o of r.open_roles || []) { put(roleNode(o, this._order++)); }
        const gone = new Set(r.gone_roles || []);
        if (gone.size) { this.nodes = this.nodes.filter((n) => !gone.has(n.id)); }
        if (r.counts && this.data) { this.data.counts = { ...this.data.counts, ...r.counts }; }
        this.idx = buildIndex(this.nodes);
        const s = this.state;
        if (s.side && !this.idx.byId.has(s.side)) { s.side = null; }
        if (s.sel && !this.idx.byId.has(s.sel)) { s.sel = null; }
        for (const id of touched) { this.hist.delete(id); }
        for (const id of [...this.picked]) { if (!this.idx.byId.has(id)) { this.picked.delete(id); } }
        s.pickN = this.picked.size;
        return touched;
    }

    async undo(entry) {
        const e = entry || this._undo[this._undo.length - 1];
        if (!e) {
            this.notif.add(_t("Nothing to undo."), { type: "info" });
            return;
        }
        const i = this._undo.indexOf(e);
        if (i >= 0) { this._undo.splice(i, 1); }
        await this.runWrite(e.undo.method, e.undo.args, { undoOf: e });
    }

    // The write actions the dialogs and menus call.
    // In planning mode (P3) each of these becomes a planned change: the
    // same arguments, sent to `plan_add_changes` instead of the live write.
    doMove(id, to, wholeTeam = true) {
        const n = this.nodeOf(id);
        const m = this.nodeOf(to);
        if (this.inPlan) {
            return this.planAdd([{ kind: "move", employee_id: n.empId, to_manager_id: m.empId, whole_team: wholeTeam }],
                                { open: m.id, reveal: [n.id] });
        }
        return this.runWrite("move", [n.empId, m.empId, wholeTeam], { open: m.id, reveal: [n.id] });
    }

    doMoveMany(ids, to) {
        const m = this.nodeOf(to);
        const emps = ids.map((i) => this.nodeOf(i)).filter((n) => n && !n.isRole && n.empId).map((n) => n.empId);
        if (this.inPlan) {
            const moving = emps.filter((e) => this.idx.eff.get(String(e)) !== m.id);
            return this.planAdd(moving.map((e) => ({ kind: "move", employee_id: e, to_manager_id: m.empId })),
                                { open: m.id, clearPicks: true, reveal: [] });
        }
        return this.runWrite("move_many", [emps, m.empId], { open: m.id, clearPicks: true, reveal: [] });
    }

    doMoveRole(id, to) {
        const r = this.nodeOf(id);
        const m = this.nodeOf(to);
        if (this.inPlan) {
            return this.planAdd([{ kind: "move_role", job_id: r.jobId || r.id, to_manager_id: m.empId }],
                                { open: m.id, reveal: [r.id] });
        }
        return this.runWrite("move_role", [r.jobId, m.empId], { open: m.id, reveal: [r.id] });
    }

    doDotted(id, to) {
        const n = this.nodeOf(id);
        const m = to ? this.nodeOf(to) : null;
        if (this.inPlan) {
            return this.planAdd([{ kind: "dotted", employee_id: n.empId, to_manager_id: m ? m.empId : false }],
                                { reveal: [n.id] });
        }
        return this.runWrite("set_dotted", [n.empId, m ? m.empId : false], { reveal: [n.id] });
    }

    doUnassign(id) {
        const n = this.nodeOf(id);
        if (this.inPlan) { return this.planAdd([{ kind: "unassign", employee_id: n.empId }], { reveal: [n.id] }); }
        return this.runWrite("unassign", [n.empId], { reveal: [n.id] });
    }

    doSwap(id) {
        const n = this.nodeOf(id);
        if (this.inPlan) { return this.planAdd([{ kind: "swap", employee_id: n.empId }], { reveal: [n.id] }); }
        return this.runWrite("swap", [n.empId], { reveal: [n.id] });
    }

    doAddRole(mgrId, title, reason) {
        const m = this.nodeOf(mgrId);
        if (this.inPlan) {
            return this.planAdd([{ kind: "new_role", to_manager_id: m.empId, title, reason: reason || false }],
                                { open: m.id });
        }
        return this.runWrite("add_open_role", [m.empId, title, reason || false], { open: m.id });
    }

    doFill(roleId, empId) {
        const r = this.nodeOf(roleId);
        const p = this.nodeOf(empId);
        if (this.inPlan) {
            return this.planAdd([{ kind: "fill_role", job_id: r.jobId || r.id, employee_id: p.empId }],
                                { reveal: [p.id] });
        }
        return this.runWrite("fill_role", [r.jobId, p.empId], { reveal: [p.id] });
    }

    doCloseRole(roleId) {
        const r = this.nodeOf(roleId);
        if (this.inPlan) {
            if (r.virtual) { return this.removeVirtual(r); }
            return this.planAdd([{ kind: "close_role", job_id: r.jobId }], {});
        }
        return this.runWrite("close_role", [r.jobId], {});
    }

    /** The new-employee form, with what the chart knows already filled in. */
    openNewStarter({ mgr, role }) {
        const m = mgr || (role ? this.mgrOf(role) : null);
        this.closeDialog();
        if (!registry.category("actions").contains("pb_onboard_wizard")) {
            this.notif.add(_t("The new-employee form is not available here."), { type: "warning" });
            return;
        }
        this.action.doAction({
            type: "ir.actions.client", tag: "pb_onboard_wizard", name: _t("Add employee"),
            params: { prefill: {
                // P3: only "Fill this role" lowers the role's to-hire count on save
                fill_job_id: role ? role.jobId : false,
                parent_id: m ? m.empId : false,
                parent_name: m ? m.name : "",
                department_id: (role ? role.dept_id : m && m.dept_id) || false,
                department_name: (role ? role.dept : m && m.dept) || "",
                job_id: role ? role.jobId : false,
                job_title: role ? role.title : "",
            } },
        });
    }

    // ============================================================ dialogs
    openDialog(d) {
        this.state.ctx = null;
        this.state.menu = null;
        this.state.dlg = { ...d, seq: ++this._dlgSeq };
    }

    closeDialog() { this.state.dlg = null; }

    openPickMgr() {
        if (!this.picked.size) { return; }
        this.openDialog({ kind: "pickmgr", ids: [...this.picked] });
    }

    // ===================================================== multi-select
    pickToggle(id) {
        id = String(id);
        if (!this.picked.size && this.state.sel && this.state.sel !== id) {
            const cur = this.nodeOf(this.state.sel);
            if (cur && !cur.isRole) { this.picked.add(cur.id); }
        }
        if (this.picked.has(id)) { this.picked.delete(id); } else { this.picked.add(id); }
        this._anchor = id;
        this._pickChanged();
    }

    /** Shift-click: everyone between the last pick and this card, in
     *  reading order (rows, then left to right) — in the lane that is its
     *  grid order. */
    pickRange(id) {
        id = String(id);
        const from = this._anchor || this.state.sel;
        if (!from || from === id) { this.pickToggle(id); return; }
        const order = this.cards.filter((c) => !c.n.isRole)
            .sort((a, b) => (a.y - b.y) || (a.x - b.x)).map((c) => c.id);
        let i = order.indexOf(from);
        let j = order.indexOf(id);
        if (i < 0 || j < 0) { this.pickToggle(id); return; }
        if (i > j) { [i, j] = [j, i]; }
        for (const x of order.slice(i, j + 1)) { this.picked.add(x); }
        this._pickChanged();
    }

    pickLane() {
        for (const n of this.idx.lone) { if (!n.isRole) { this.picked.add(n.id); } }
        this._anchor = null;
        this._pickChanged();
    }

    pickClear(quiet = false) {
        this.picked.clear();
        this._anchor = null;
        this._pickChanged(quiet);
    }

    _pickChanged() {
        this.state.pickN = this.picked.size;
        this._paintPicks();
    }

    get pickLine() {
        const n = this.state.pickN;
        return n === 1 ? _t("1 person selected") : _t("%(n)s people selected", { n: this.fmtInt(n) });
    }

    get laneSelectLabel() {
        const n = this.idx ? this.idx.lone.filter((x) => !x.isRole).length : 0;
        return _t("Select all %(n)s here", { n: this.fmtInt(n) });
    }

    get laneCanSelect() {
        return this.mayWrite && !!this.idx && this.idx.lone.filter((x) => !x.isRole).length > 1;
    }

    /** `data-pk` on every picked card on screen (re-applied after a patch). */
    _paintPicks() {
        for (const el of this._pkMarked) { delete el.dataset.pk; }
        this._pkMarked = [];
        const host = this.nodesRef.el;
        if (!host || !this.picked.size) { return; }
        for (const id of this.picked) {
            const el = host.querySelector(`[data-id="${CSS.escape(id)}"]`);
            if (el) { el.dataset.pk = "1"; this._pkMarked.push(el); }
        }
    }

    // ============================================================ drag
    _cardEl(id) {
        const host = this.nodesRef.el;
        return host ? host.querySelector(`[data-id="${CSS.escape(id)}"]`) : null;
    }

    /** pointerdown on a card: remember it; it becomes a drag after 6 px. */
    _dragPress(e) {
        if (e.button !== 0 || !this.mayWrite || !this.canvasView || this.state.dlg) { return false; }
        const el = e.target.closest && e.target.closest(".pboc-node");
        if (!el || e.target.closest("button") || !this.nodesRef.el || !this.nodesRef.el.contains(el)) { return false; }
        const n = this.nodeOf(el.dataset.id);
        if (!n || n.isRole || n.future) { return false; }
        this._press = { x: e.clientX, y: e.clientY, id: n.id };
        return true;
    }

    _dragMove(e) {
        if (this._drag) { this._dragTrack(e); return true; }
        if (!this._press) { return false; }
        if (Math.hypot(e.clientX - this._press.x, e.clientY - this._press.y) < DRAG_START) { return true; }
        this._dragStart(e);
        return true;
    }

    _dragStart(e) {
        const id = this._press.id;
        const ids = this.picked.has(id) && this.picked.size > 1
            ? [...this.picked].filter((x) => this.idx.byId.has(x)) : [id];
        const n = this.nodeOf(id);
        const root = this.root.el;
        const g = this.ghostRef.el;
        if (!g || !root) { this._press = null; return; }
        const rr = root.getBoundingClientRect();
        // the ghost is mounted once: only its text and inline style change
        g.querySelector(".ga").textContent = n.ini;
        g.querySelector(".ga").style.background = this.colorOf(n);
        g.querySelector(".gn").textContent = n.name;
        g.querySelector(".gt").textContent = n.title || n.dept || "";
        const gc = g.querySelector(".gc");
        gc.textContent = ids.length > 1 ? "+" + (ids.length - 1) : "";
        if (ids.length > 1) { gc.dataset.on = "1"; } else { delete gc.dataset.on; }
        this._show(g, true);
        const marks = [];
        for (const x of ids) {
            const el = this._cardEl(x);
            if (el) { el.dataset.drag = "1"; marks.push(el); }
        }
        this._show(this.hintRef.el, true);
        this._show(this.qaRef.el, false);
        const cv = this.canvasRef.el.getBoundingClientRect();
        this._drag = { ids, over: null, overEl: null, verdict: null, marks, rr, cv,
                       x: e.clientX, y: e.clientY, vx: 0, vy: 0, raf: 0, t0: performance.now(), moves: 0, worst: 0 };
        this._dragTrack(e);
    }

    _dragTrack(e) {
        const d = this._drag;
        const t = performance.now();
        d.x = e.clientX;
        d.y = e.clientY;
        const s = Math.max(0.7, Math.min(1, this.vp.zoom));
        this._slide(this.ghostRef.el,
            `translate(${d.x - d.rr.left + 14}px,${d.y - d.rr.top + 14}px) scale(${s}) rotate(-2deg)`);
        const hit = document.elementFromPoint(d.x, d.y);
        const el = hit && hit.closest ? hit.closest(".pboc-node") : null;
        const id = el && this.nodesRef.el.contains(el) ? el.dataset.id : null;
        const target = id && !d.ids.includes(id) ? id : null;
        if (target !== d.over) {
            if (d.overEl) { delete d.overEl.dataset.over; }
            d.over = target;
            d.overEl = target ? el : null;
            d.verdict = target ? this.dropVerdict(d.ids, target) : null;
            if (target) {
                el.dataset.over = d.verdict.ok ? "ok" : (d.verdict.why === "same" ? "same" : "bad");
            }
        }
        // near an edge of the canvas: the chart pans under the ghost
        const sp = (dist) => (dist < EDGE ? Math.ceil((EDGE - dist) / EDGE * 14) : 0);
        d.vx = sp(d.x - d.cv.left) - sp(d.cv.right - d.x);
        d.vy = sp(d.y - d.cv.top) - sp(d.cv.bottom - d.y);
        if ((d.vx || d.vy) && !d.raf) {
            const step = () => {
                const dd = this._drag;
                if (!dd || (!dd.vx && !dd.vy)) { if (dd) { dd.raf = 0; } return; }
                this.vp.px += dd.vx;
                this.vp.py += dd.vy;
                this.applyTransform(false);
                dd.raf = requestAnimationFrame(step);
            };
            d.raf = requestAnimationFrame(step);
        }
        d.moves++;
        d.worst = Math.max(d.worst, performance.now() - t);
    }

    /** pointerup: a drag ends in the move sheet, a refusal, or nothing. */
    _dragUp() {
        if (!this._drag) { this._press = null; return false; }
        const d = this._drag;
        this._drag = null;
        this._press = null;
        if (d.raf) { cancelAnimationFrame(d.raf); }
        this._show(this.ghostRef.el, false);
        this._show(this.hintRef.el, false);
        for (const el of d.marks) { delete el.dataset.drag; }
        if (d.overEl) { delete d.overEl.dataset.over; }
        // the click that follows a drag must not select the card
        this._dragged = true;
        setTimeout(() => { this._dragged = false; }, 0);
        if (this.root.el) {
            this.root.el.dataset.dragMoves = d.moves;
            this.root.el.dataset.dragWorstMs = d.worst.toFixed(1);
        }
        this._placePill(this._hover || this.state.sel);
        if (!d.over) { return true; }
        const v = d.verdict;
        if (!v.ok) {
            this.notif.add(v.text, { type: v.why === "same" ? "info" : "danger" });
            return true;
        }
        if (d.ids.length > 1) { this.openDialog({ kind: "many", ids: d.ids, to: d.over }); }
        else { this.openDialog({ kind: "move", id: d.ids[0], to: d.over }); }
        return true;
    }

    // ===================================================== quick actions
    /** The one hover pill, moved onto the card under the pointer. */
    _placePill(id) {
        const el = this.qaRef && this.qaRef.el;
        if (!el) { return; }
        const p = id && this.lay && this.lay.pos.get(id);
        const pn = id ? this.nodeOf(id) : null;
        if (!p || this._drag || !this.canvasView || (pn && pn.future)) {
            this._show(el, false);
            this._pillId = null;
            return;
        }
        const n = this.nodeOf(id);
        const role = n && n.isRole ? "1" : "";
        if ((el.dataset.role || "") !== role) { el.dataset.role = role; }
        if (this._pillId !== id || this._pillAt !== p) {
            this._slide(el, `translate(${p.x + p.w - 10}px,${p.y - 14}px) translateX(-100%)`);
            this._pillAt = p;
        }
        this._show(el, true);
        this._pillId = id;
    }

    qaRun(k, ev) {
        const id = this._pillId;
        if (!id) { return; }
        if (k === "open") { this.select(id); return; }
        if (k === "more") {
            const r = ev.currentTarget.getBoundingClientRect();
            this.openCtx(id, r.left, r.bottom + 4);
            return;
        }
        this.act(k, id);
    }

    /** One entry point for every editing action (pill, menu, panel, keys). */
    act(k, id) {
        const n = this.nodeOf(id);
        if (!n || n.future) { return; }
        this.state.ctx = null;
        if (n.virtual && ["fill", "changemgr"].includes(k)) {
            this.notif.add(_t("That role is new in this plan. Take it out of the list of changes instead, or fill it once the plan is live."),
                           { type: "info" });
            return;
        }
        switch (k) {
            case "open": this.select(n.id); break;
            case "addmember": if (this.mayWrite && !n.isRole) { this.openDialog({ kind: "addmember", id: n.id }); } break;
            case "changemgr": if (this.mayWrite) { this.openDialog({ kind: "changemgr", id: n.id }); } break;
            case "dotted": if (this.mayWrite && !n.isRole) { this.openDialog({ kind: "dotted", id: n.id }); } break;
            case "fill": if (this.mayWrite && n.isRole) { this.openDialog({ kind: "fill", id: n.id }); } break;
            case "swap": if (this.mayWrite) { this.doSwap(n.id); } break;
            case "unassign": if (this.mayWrite) { this.doUnassign(n.id); } break;
            case "closerole": if (this.mayWrite) { this.doCloseRole(n.id); } break;
            case "toggle": this.toggle(n); break;
            case "focusteam": this.focusTeam(n.id); break;
            case "record": this.openRecord(n); break;
            case "rmvirtual": this.removeVirtual(n); break;
            case "branchpng": this.exportBranch(n.id); break;
        }
    }

    /** Everyone under this person, the rest folded, fitted to the screen. */
    focusTeam(id) {
        const keep = new Set([id, ...descendants(this.idx, id).map((d) => d.id),
                              ...ancestors(this.idx, id).map((a) => a.id)]);
        for (const n of this.nodes) {
            if (kidsOf(this.idx, n.id).length) {
                if (keep.has(n.id)) { this.collapsed.delete(n.id); } else { this.collapsed.add(n.id); }
            }
        }
        this.state.filters = { dept: null, loc: null, type: null };
        this.state.focus = null;
        this.select(id);
        this.relayout();
        this.notif.add(_t("Showing %(p)s's team. Press E to see everyone again.", { p: this.nodeOf(id).name }), { type: "info" });
    }

    // ===================================================== context menu
    onContextMenu(ev) {
        const el = ev.target.closest(".pboc-node");
        if (!el) { return; }
        const cn = this.nodeOf(el.dataset.id);
        if (cn && cn.future) { ev.preventDefault(); return; }
        ev.preventDefault();
        this.openCtx(el.dataset.id, ev.clientX, ev.clientY);
    }

    openCtx(id, x, y) {
        const root = this.root.el;
        const rr = root ? root.getBoundingClientRect() : { left: 0, top: 0, width: 1200, height: 800 };
        // the menu is placed inside the page root (an ancestor with a
        // transform would make `position: fixed` lie)
        const lx = Math.max(8, Math.min(x - rr.left, rr.width - 310));
        const ly = Math.max(8, Math.min(y - rr.top, rr.height - 470));
        this.state.menu = null;
        this.state.ctx = { id: String(id), x: lx, y: ly };
    }

    get ctxNode() { return this.state.ctx ? this.nodeOf(this.state.ctx.id) : null; }

    get ctxStyle() { const c = this.state.ctx; return c ? `left:${c.x}px;top:${c.y}px` : ""; }

    get ctxRows() {
        const n = this.ctxNode;
        if (!n) { return []; }
        const w = this.mayWrite;
        const m = this.mgrOf(n);
        const team = directCount(this.idx, n) > 0;
        const folded = this.collapsed.has(n.id) || isUnloaded(this.idx, n);
        const rows = [{ k: "open", ic: "eye", label: _t("Open side panel") }];
        if (n.isRole && n.virtual) {
            if (this.inPlan) {
                rows.push({ hr: true, k: "hr0" });
                rows.push({ k: "rmvirtual", ic: "trash", label: _t("Take this role out of the plan"),
                            sub: _t("It was only planned — nothing is lost"), danger: true });
            }
            return rows;
        }
        if (n.isRole) {
            if (w) {
                rows.push({ k: "fill", ic: "userCheck", label: _t("Fill this role"),
                            sub: _t("Someone already here, or a new starter") });
                rows.push({ k: "changemgr", ic: "move", label: _t("Change manager"),
                            sub: _t("Who the role will report to") });
                rows.push({ hr: true, k: "hr1" });
                rows.push({ k: "closerole", ic: "trash", label: _t("Close this open role"),
                            sub: _t("Nobody more to hire for it"), danger: true });
            }
            return rows;
        }
        if (w) {
            rows.push({ k: "addmember", ic: "userPlus", label: _t("Add a team member"),
                        sub: _t("Someone already here, an open role or a new starter") });
            rows.push({ k: "changemgr", ic: "move", label: _t("Change manager") });
            rows.push({ k: "dotted", ic: "ellipsis",
                        label: n.dotted ? _t("Change dotted-line manager") : _t("Add dotted-line manager") });
            if (m && !m.isRole && this.idx.eff.get(m.id)) {
                rows.push({ k: "swap", ic: "arrowUpDown", label: _t("Swap places with %(m)s", { m: m.name }),
                            sub: _t("%(p)s becomes the manager; %(m)s reports to them", { p: n.name, m: m.name }) });
            }
        }
        if (team) {
            rows.push({ k: "toggle", ic: folded ? "expand" : "shrink",
                        label: folded ? _t("Expand team") : _t("Collapse team") });
            rows.push({ k: "focusteam", ic: "target", label: _t("Show only this team"),
                        sub: _t("Everyone under %(p)s, the rest folded", { p: n.name }) });
        }
        rows.push({ k: "record", ic: "external", label: _t("Open employee record") });
        if (team && this.canvasView) {
            rows.push({ k: "branchpng", ic: "image", label: _t("Export this branch as a picture"),
                        sub: _t("%(p)s and everyone under them, as drawn", { p: n.name }) });
        }
        if (w && m) {
            rows.push({ hr: true, k: "hr2" });
            rows.push({ k: "unassign", ic: "userX", label: _t("Remove from %(m)s's team", { m: m.name }),
                        sub: team ? _t("Their own team stays with them") : _t("Moves to the “no manager yet” lane"),
                        danger: true });
        }
        return rows;
    }

    ctxRun(row) {
        const id = this.state.ctx && this.state.ctx.id;
        this.state.ctx = null;
        if (id) { this.act(row.k, id); }
    }

    // ============================================================ history
    async loadHistory(id) {
        const n = this.nodeOf(id);
        if (!n || n.isRole || this.hist.has(n.id)) { return; }
        this.hist.set(n.id, null);
        this.state.histRev++;
        let rows = [];
        try {
            rows = await this.orm.call("pb.orgchart", "get_history", [n.empId]);
        } catch (e) {
            console.warn("pb_orgchart: history failed", e);
        }
        this.hist.set(n.id, rows || []);
        this.state.histRev++;
    }

    get sideHistory() {
        void this.state.histRev;
        const n = this.sideNode;
        return n ? this.hist.get(n.id) : undefined;
    }

    fmtDay(iso) {
        if (!iso) { return ""; }
        try {
            return deserializeDate(iso).toLocaleString({ day: "numeric", month: "short", year: "numeric" });
        } catch {
            return iso;
        }
    }

    histWhen(h) {
        return h.who ? _t("%(d)s · by %(w)s", { d: this.fmtDay(h.when), w: h.who }) : this.fmtDay(h.when);
    }

    get joinedLine() {
        const n = this.sideNode;
        return n && n.joined ? this.fmtDay(n.joined) : "";
    }

    // ================================================ after every draw
    _afterEdit() {
        this._paintPicks();
        this._placePill(this._hover || this.state.sel);
        if (this._pendingReveal && this.worldRef.el) {
            const id = this._pendingReveal;
            this._pendingReveal = null;
            this.ensureVisible(id);
        }
        if (this._flashIds && this._flashIds.length) {
            const els = this._flashIds.map((id) => this._cardEl(id)).filter(Boolean).slice(0, 40);
            this._flashIds = null;
            for (const el of els) { el.dataset.flash = "1"; }
            setTimeout(() => { for (const el of els) { delete el.dataset.flash; } }, 1400);
        }
    }

    /** Pan (with motion) only when the card is off screen. */
    ensureVisible(id) {
        const p = this.lay && this.lay.pos.get(id);
        if (!p) { return; }
        const cv = this._canvasRect();
        const z = this.vp.zoom;
        const x0 = p.x * z + this.vp.px;
        const y0 = p.y * z + this.vp.py;
        const pad = 40;
        if (x0 > pad && y0 > pad && x0 + p.w * z < cv.width - pad && y0 + p.h * z < cv.height - pad) { return; }
        this.centerOn(id);
    }
}

/** Copy OcEdit's methods and getters onto the chart component. */
export function installEdit(Cls) {
    const desc = Object.getOwnPropertyDescriptors(OcEdit.prototype);
    delete desc.constructor;
    Object.defineProperties(Cls.prototype, desc);
}
