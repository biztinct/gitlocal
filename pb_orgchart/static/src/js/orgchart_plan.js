/** @odoo-module **/
/**
 * ORG CHART P3 — planning mode, the time machine and "Suggest a chart",
 * installed onto PbOrgChart (`installPlan`) beside P2's editing half.
 *
 *  * PLANNING MODE. "Plan changes" opens (or makes) the person's draft plan
 *    on the server (`plan_open`). While it is open every P2 action (drag,
 *    sheets, menus, bulk set-manager) becomes `plan_add_changes` instead of
 *    the live write, and the chart is redrawn from `get_chart(plan_id)` — the
 *    server's projection: amber outlines on the people who change, a dashed
 *    rose line from where each moved person used to sit, new open roles as
 *    dashed cards. Undo takes the last change (or the last batch) out on the
 *    server and keeps it here for Redo.
 *  * TIME MACHINE. A slider from a year ago to 90 days ahead; the chart is
 *    fetched for that day 250 ms after the slider stops (`get_chart(as_of)`).
 *    Away from today nothing can be changed.
 *  * The two never run together: the time machine is off in planning mode,
 *    "Plan changes" is hidden while looking at another day.
 */
import { _t } from "@web/core/l10n/translation";
import { isUnloaded } from "@pb_orgchart/js/orgchart_layout";

const { DateTime } = luxon;
const TIME_DEBOUNCE = 250;

const KIND_IC = {
    move: "move", dotted: "ellipsis", unassign: "userX", swap: "arrowUpDown",
    new_role: "briefcase", move_role: "move", fill_role: "userCheck", close_role: "trash",
};
const KIND_TONE = { fill_role: "green", new_role: "p", unassign: "rose", close_role: "rose" };

class OcPlan {
    _setupPlan() {
        this._branches = new Set();
        this._redo = [];
        this._timeT = 0;
    }

    // ============================================================ facts
    /** A draft plan of mine is open: actions go into it. */
    get inPlan() { return !!(this.state.plan && this.state.plan.editable); }

    /** Someone's sent plan is on screen, read-only. */
    get planView() { return !!(this.state.plan && !this.state.plan.editable); }

    get timeTravel() { return !!this.state.asOf; }

    /** The keyword arguments of every chart read. */
    chartKw() {
        const kw = {};
        if (this.state.plan) { kw.plan_id = this.state.plan.plan_id; }
        else if (this.state.asOf) { kw.as_of = this.asOfIso(this.state.asOf); }
        if (this._branches.size) { kw.expand = [...this._branches]; }
        return kw;
    }

    asOfIso(days) { return DateTime.local().startOf("day").plus({ days }).toISODate(); }

    fmtDayOffset(days) {
        return DateTime.local().startOf("day").plus({ days })
            .toLocaleString({ day: "numeric", month: "short", year: "numeric" });
    }

    get planChanges() { return (this.state.plan && this.state.plan.changes) || []; }

    get planN() { return this.state.plan ? this.state.plan.n || 0 : 0; }

    get myDraft() { return (this.data && this.data.my_draft) || null; }

    // ===================================================== planning mode
    async startPlan() {
        if (this.state.asOf) { return; }
        const res = await this._planCall("plan_open", []);
        if (!res) { return; }
        this.pickClear(true);
        this.state.plan = res;
        this.state.side = "__changes";
        this.state.sel = null;
        this._redo = [];
        this.state.redoN = 0;
        await this.load({ keep: true });
    }

    /** Open a plan from the Plans menu: mine and still a draft = resume. */
    async openPlan(p) {
        this.state.menu = null;
        if (this.state.asOf) { this.state.asOf = 0; this.state.asOfDraft = 0; }
        this.state.plan = { plan_id: p.id, editable: p.mine && p.state === "draft", n: p.n };
        this.state.side = "__changes";
        this._redo = [];
        this.state.redoN = 0;
        await this.load({ keep: true });
    }

    async leavePlan(quiet = false) {
        this.state.plan = null;
        if (this.state.side === "__changes") { this.state.side = null; }
        this._redo = [];
        this.state.redoN = 0;
        await this.load({ keep: true });
        if (!quiet) { this.notif.add(_t("Back to the live chart."), { type: "info" }); }
    }

    showChanges() { this.state.side = "__changes"; this.state.sel = null; }

    /** One plan RPC: busy flag, a sentence on refusal, the answer or null. */
    async _planCall(method, args) {
        if (this._writing) { return null; }
        this._writing = true;
        this.state.writing = true;
        let res = null;
        try {
            res = await this.orm.call("pb.orgchart", method, args);
        } catch (e) {
            console.warn("pb_orgchart: plan call failed", e);
            res = { error: _t("That could not be saved. Nothing was changed — try again.") };
        } finally {
            this._writing = false;
            this.state.writing = false;
        }
        if (!res || res.error) {
            this.notif.add((res && res.error) || _t("That could not be saved."), { type: "danger" });
            return null;
        }
        return res;
    }

    /**
     * Add changes to the open plan and redraw the projection. `opts` as
     * P2's writes: `open` (a manager whose team to unfold), `reveal`
     * (people to bring on screen and flash), `clearPicks`.
     */
    async planAdd(changes, opts = {}, keepRedo = false) {
        if (!this.inPlan) { return null; }
        const res = await this._planCall("plan_add_changes", [this.state.plan.plan_id, changes]);
        if (!res) { return null; }
        if (!keepRedo) { this._redo = []; this.state.redoN = 0; }
        this.state.plan = res;
        if (opts.clearPicks) { this.pickClear(true); }
        await this._reloadAfter(opts);
        return res;
    }

    async _reloadAfter(opts = {}) {
        await this.load({ keep: true });
        if (opts.open) {
            const t = this.nodeOf(opts.open);
            if (t && isUnloaded(this.idx, t)) { await this.loadBranch(t); }
            this.collapsed.delete(String(opts.open));
        }
        for (const id of opts.reveal || []) { if (this.nodeOf(id)) { this._revealIn(String(id)); } }
        const ids = (opts.reveal || []).map(String).filter((id) => this.nodeOf(id));
        this._flashIds = ids;
        this._pendingReveal = ids.length === 1 ? ids[0] : null;
        this.relayout();
    }

    async planUndo() {
        if (!this.inPlan) { return; }
        if (!this.planN) { this.notif.add(_t("Nothing to undo."), { type: "info" }); return; }
        const res = await this._planCall("plan_undo", [this.state.plan.plan_id]);
        if (!res) { return; }
        this._redo.push(res.redo || []);
        this.state.redoN = this._redo.length;
        this.state.plan = res;
        await this._reloadAfter({});
        this.notif.add(_t("Undone: %(l)s", { l: res.label }), { type: "info" });
    }

    async planRedo() {
        if (!this.inPlan || !this._redo.length) { return; }
        const batch = this._redo.pop();
        this.state.redoN = this._redo.length;
        const res = await this.planAdd(batch, {}, true);
        if (!res) { this._redo.push(batch); this.state.redoN = this._redo.length; }
    }

    async planRemove(ch) {
        if (!this.inPlan) { return; }
        const res = await this._planCall("plan_remove_change", [this.state.plan.plan_id, ch.id]);
        if (!res) { return; }
        this.state.plan = res;
        await this._reloadAfter({});
    }

    /** A new open role that only exists in the plan: take its change out. */
    async removeVirtual(n) {
        const cid = parseInt(String(n.id).replace("plan-", ""), 10);
        const ch = this.planChanges.find((c) => c.id === cid);
        if (ch) { await this.planRemove(ch); }
    }

    openPublish() {
        if (!this.inPlan || !this.planN) { return; }
        this.openDialog({ kind: "publish" });
    }

    async planSubmit(vals) {
        const res = await this._planCall("plan_submit", [this.state.plan.plan_id, vals]);
        if (!res) { return null; }
        this.state.plan = null;
        if (this.state.side === "__changes") { this.state.side = null; }
        this._redo = [];
        this.state.redoN = 0;
        await this.load({ keep: true });
        this.notif.add(res.label, { type: "success", autocloseDelay: 8000 });
        return res;
    }

    askDiscard() {
        if (!this.inPlan) { return; }
        if (!this.planN) { this.planDiscard(); return; }
        this.openDialog({ kind: "discard" });
    }

    async planDiscard() {
        const res = await this._planCall("plan_discard", [this.state.plan.plan_id]);
        if (!res) { return null; }
        await this.leavePlan(true);
        this.notif.add(res.label, { type: "info" });
        return res;
    }

    // ------------------------------------------------- the Plans menu
    async togglePlans() {
        const open = this.state.menu !== "plans";
        this.state.menu = open ? "plans" : null;
        if (!open) { return; }
        this.state.plans = null;
        try {
            this.state.plans = await this.orm.call("pb.orgchart", "plans_list", []);
        } catch (e) {
            console.warn("pb_orgchart: plans failed", e);
            this.state.plans = [];
        }
    }

    planPillTone(p) {
        return { draft: "p", pending: "amber", approved: "blue", applied: "green", refused: "rose" }[p.state] || "";
    }

    planRowSub(p) {
        const n = p.n === 1 ? _t("1 change") : _t("%(n)s changes", { n: p.n });
        const who = p.mine ? "" : " · " + _t("by %(u)s", { u: p.user });
        const when = p.effective_label ? " · " + _t("goes live %(d)s", { d: p.effective_label }) : "";
        const err = p.errors ? " · " + _t("%(n)s could not be made", { n: p.errors }) : "";
        return n + who + (p.state === "draft" ? "" : when) + err;
    }

    get draftLine() {
        const d = this.myDraft;
        if (!d) { return ""; }
        return d.n === 1 ? _t("You have a draft with 1 change") : _t("You have a draft with %(n)s changes", { n: d.n });
    }

    resumeDraft() {
        const d = this.myDraft;
        if (d) { this.openPlan({ id: d.id, mine: true, state: "draft", n: d.n }); }
    }

    // ----------------------------------------------- the changes panel
    changeIc(c) { return KIND_IC[c.kind] || "move"; }

    changeTone(c) { return KIND_TONE[c.kind] || ""; }

    get planBarText() {
        const n = this.planN;
        if (!n) { return _t("Drag people around, add roles, try things."); }
        return n === 1
            ? _t("1 change so far — the amber outline marks who moved, a dashed red line shows where they came from.")
            : _t("%(n)s changes so far — amber outlines mark who moved, a dashed red line shows where they came from.", { n });
    }

    get planViewText() {
        const p = this.state.plan;
        if (!p || !p.name) { return ""; }
        return p.effective_label
            ? _t("“%(n)s” · %(s)s · goes live %(d)s. This is how the chart looks with it.",
                 { n: p.name, s: p.state_label, d: p.effective_label })
            : _t("“%(n)s” · %(s)s.", { n: p.name, s: p.state_label });
    }

    get effectLines() {
        const p = this.state.plan;
        const e = (p && p.effect) || {};
        const out = [];
        out.push(e.people === 1 ? _t("1 person moves or changes.") : _t("%(n)s people move or change.", { n: e.people || 0 }));
        if (e.new_roles) {
            out.push(e.new_roles === 1 ? _t("1 new open role for Hiring.") : _t("%(n)s new open roles for Hiring.", { n: e.new_roles }));
        }
        if (e.closed_roles) {
            out.push(e.closed_roles === 1 ? _t("1 open role closed.") : _t("%(n)s open roles closed.", { n: e.closed_roles }));
        }
        out.push(_t("Managers with 10+ direct reports after the plan: %(a)s (today %(b)s).",
                    { a: e.wide_after || 0, b: e.wide_before || 0 }));
        if (e.crosses_teams) { out.push(_t("Someone moves to a manager in another team — their team stays as it is.")); }
        return out;
    }

    get planEmptyText() {
        return _t("Drag anyone onto a new manager, or use the buttons on a card. Changes stack here; nothing is real until you publish.");
    }

    // ===================================================== time machine
    get timeLabel() {
        const d = this.state.asOf;
        if (!d) { return _t("Today"); }
        return d < 0 ? (d === -1 ? _t("1 day ago") : _t("%(n)s days ago", { n: -d }))
                     : (d === 1 ? _t("In 1 day") : _t("In %(n)s days", { n: d }));
    }

    get timeDraftDate() {
        return this.state.asOfDraft ? this.fmtDayOffset(this.state.asOfDraft) : _t("Today");
    }

    get timeTone() { const d = this.state.asOfDraft; return d < 0 ? "past" : d > 0 ? "future" : ""; }

    get timeBanner() {
        return _t("You are looking at %(d)s. Go back to today to make changes.", { d: this.fmtDayOffset(this.state.asOf) });
    }

    toggleTime() {
        if (this.state.plan) { return; }
        this.state.asOfDraft = this.state.asOf;
        this.toggleMenu("time");
    }

    onTimeInput(ev) {
        this.state.asOfDraft = parseInt(ev.target.value, 10) || 0;
        clearTimeout(this._timeT);
        this._timeT = setTimeout(() => this.setAsOf(this.state.asOfDraft), TIME_DEBOUNCE);
    }

    async setAsOf(days) {
        clearTimeout(this._timeT);
        if (this.state.plan) { return; }
        days = Math.max(-365, Math.min(90, days || 0));
        this.state.asOfDraft = days;
        if (days === this.state.asOf) { return; }
        this.state.asOf = days;
        this.pickClear(true);
        this.state.ctx = null;
        this.state.timeBusy = true;
        try {
            await this.load({ keep: true });
        } finally {
            this.state.timeBusy = false;
        }
    }

    backToToday() { this.state.menu = null; this.setAsOf(0); }

    // ====================================================== suggest
    openSuggest() {
        this.state.menu = null;
        this.state.nomgrDismissed = true;
        this.openDialog({ kind: "suggest" });
    }

    async useSuggestion() {
        if (this.state.asOf) { await this.setAsOf(0); }
        const res = await this._planCall("plan_use_suggestion", []);
        if (!res) { return null; }
        this.pickClear(true);
        this.state.plan = res;
        this.state.side = "__changes";
        this._redo = [];
        this.state.redoN = 0;
        this.state.laneOpen = false;
        await this.load({ keep: true });
        this._pendingFit = true;
        this.relayout();
        this.notif.add(res.label, { type: "success" });
        return res;
    }

    get canSuggest() {
        return !!(this.data && this.data.may_write) && !this.state.asOf && !this.planView
            && !!this.idx && this.idx.lone.filter((x) => !x.isRole).length > 1;
    }
}

/** Copy OcPlan's methods and getters onto the chart component. */
export function installPlan(Cls) {
    const desc = Object.getOwnPropertyDescriptors(OcPlan.prototype);
    delete desc.constructor;
    Object.defineProperties(Cls.prototype, desc);
}
