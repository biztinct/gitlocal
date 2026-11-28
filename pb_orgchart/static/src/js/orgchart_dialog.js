/** @odoo-module **/
/**
 * ORG CHART P2 — the in-page dialogs (POC `dialogHtml()`): the move sheet,
 * moving several people, change manager, set a manager for the picked
 * people, dotted line, add a team member, fill a role.
 *
 * Its own component with its own state, so typing in a picker re-renders
 * the dialog and nothing else. The picker draws a FIXED set of rows keyed
 * by position: a keystroke rewrites their text in place instead of
 * inserting new rows (an insertion re-checks the whole page's styles on
 * this app, ledger G12).
 */
import { Component, useState, useRef, onMounted } from "@odoo/owl";
const { DateTime } = luxon;
import { _t } from "@web/core/l10n/translation";
import { ancestors, descendants, kidsOf, directCount } from "@pb_orgchart/js/orgchart_layout";

const SLOTS = 40;
const WIDE = 10;

export class PbOcDialog extends Component {
    static template = "pb_orgchart.Dialog";
    static props = ["dlg", "chart"];

    setup() {
        const d = this.props.dlg;
        this.state = useState({
            q: "", sel: null, busy: false,
            mode: "existing", only: false, title: "", reason: "growth",
            // P3: the publish dialog's fields, the suggestion
            pname: "", pdate: "", pnote: "", sug: null, sugFailed: false,
            // P4: who approves the person's leave and expenses today (move sheet)
            appr: null,
        });
        if (d.kind === "move") { this.loadApprovers(); }
        if (d.kind === "publish") {
            const pl = this.chart.state.plan || {};
            this.state.pname = pl.name || "";
            this.state.pdate = pl.effective_date || DateTime.local().toISODate();
            this.state.pnote = pl.note || "";
        }
        if (d.kind === "dotted") {
            const n = this.chart.nodeOf(d.id);
            this.state.sel = (n && n.dotted) || null;
        }
        this.qRef = useRef("q");
        this.titleRef = useRef("title");
        onMounted(() => {
            const el = this.qRef.el || this.titleRef.el;
            if (el) { el.focus({ preventScroll: true }); }
            if (d.kind === "suggest") { this.loadSuggestion(); }
        });
    }

    get chart() { return this.props.chart; }
    get d() { return this.props.dlg; }
    get idx() { return this.chart.idx; }
    icon(n, s = 16) { return this.chart.icon(n, s); }
    node(id) { return this.chart.nodeOf(id); }
    who(n) { return this.chart.who(n); }

    // ---------------------------------------------------------- subjects
    get p() { return this.node(this.d.id); }
    get m() { return this.node(this.d.to); }
    get many() { return (this.d.ids || []).map((i) => this.node(i)).filter(Boolean); }
    teamOf(n) { return n ? descendants(this.idx, n.id).length : 0; }
    oldMgr(n) { return this.chart.mgrOf(n); }

    // ---------------------------------------------------------- header
    get head() {
        const d = this.d;
        const p = this.p;
        const m = this.m;
        switch (d.kind) {
            case "move": return {
                ic: "move", title: _t("Move %(p)s under %(m)s?", { p: p.name, m: m.name }),
                sub: _t("%(a)s → reports to %(b)s", { a: p.title || p.name, b: m.title || m.name }) };
            case "many": return {
                ic: "users", title: _t("Move %(n)s people under %(m)s?", { n: this.many.length, m: m.name }),
                sub: _t("They will all report to %(m)s", { m: m.name }) };
            case "changemgr": {
                const old = this.oldMgr(p);
                if (p.isRole) {
                    return { ic: "move", title: _t("Who should the %(t)s role report to?", { t: p.title }),
                             sub: old ? _t("Under %(m)s today", { m: old.name }) : _t("No manager yet") };
                }
                return { ic: "move", title: _t("Who should %(p)s report to?", { p: p.name }),
                         sub: old ? _t("%(t)s · reports to %(m)s today", { t: p.title || p.dept, m: old.name })
                                  : _t("%(t)s · has no manager today", { t: p.title || p.dept }) };
            }
            case "pickmgr": return {
                ic: "users", title: _t("Who should these %(n)s people report to?", { n: this.many.length }),
                sub: _t("Pick their manager. Anyone who reports to them comes along.") };
            case "dotted": {
                const solid = this.oldMgr(p);
                return { ic: "ellipsis",
                         title: p.dotted ? _t("Change the dotted-line manager for %(p)s", { p: p.name })
                                         : _t("Add a dotted-line manager for %(p)s", { p: p.name }),
                         sub: _t("A second person they also report to — for projects or a matrix team. The solid line stays with %(m)s.",
                                 { m: solid ? solid.name : _t("nobody") }) };
            }
            case "addmember": {
                const k = kidsOf(this.idx, p.id).length;
                return { ic: "userPlus", title: _t("Add someone to %(p)s's team", { p: p.name }),
                         sub: k === 1 ? _t("%(t)s · 1 direct report today", { t: p.title || p.dept })
                                      : _t("%(t)s · %(n)s direct reports today", { t: p.title || p.dept, n: k }) };
            }
            case "fill": {
                const mg = this.oldMgr(p);
                return { ic: "userCheck", title: _t("Fill the %(t)s role", { t: p.title }),
                         sub: _t("Reports to %(m)s · %(d)s", { m: mg ? mg.name : _t("nobody yet"), d: p.dept || "—" }) };
            }
            case "publish": {
                const n = this.chart.planN;
                return { ic: "send", title: n === 1 ? _t("Publish 1 planned change?") : _t("Publish %(n)s planned changes?", { n }),
                         sub: _t("Everything below goes live together") };
            }
            case "discard": {
                const n = this.chart.planN;
                return { ic: "trash", title: _t("Discard this plan?"),
                         sub: n === 1 ? _t("The 1 planned change is thrown away. Nothing on the real chart changes.")
                                      : _t("The %(n)s planned changes are thrown away. Nothing on the real chart changes.", { n }) };
            }
            case "suggest": return {
                ic: "wand", title: _t("Suggested chart"),
                sub: _t("Worked out from your team records. Nothing is saved until you press Use it.") };
        }
        return { ic: "info", title: "", sub: "" };
    }

    // ---------------------------------------------------------- move sheet
    get moveTeam() { return this.teamOf(this.p); }

    get optTeam() {
        const p = this.p;
        const t = this.moveTeam;
        return t ? {
            b: t === 1 ? _t("Move %(p)s and their team (1 person)", { p: p.name })
                       : _t("Move %(p)s and their whole team (%(n)s people)", { p: p.name, n: t }),
            s: _t("Everyone who reports to %(p)s comes along. The usual choice.", { p: p.name }),
        } : {
            b: _t("Move %(p)s", { p: p.name }),
            s: _t("Nobody reports to %(p)s, so only they move.", { p: p.name }),
        };
    }

    get optOnly() {
        const p = this.p;
        const old = this.oldMgr(p);
        const k = kidsOf(this.idx, p.id).filter((x) => !x.isRole).length;
        return {
            b: _t("Move only %(p)s", { p: p.name }),
            s: old ? (k === 1 ? _t("Their 1 report stays with %(m)s.", { m: old.name })
                              : _t("Their %(n)s reports stay with %(m)s.", { n: k, m: old.name }))
                   : _t("Their reports will have no manager."),
        };
    }

    /** "What changes", in one sentence a line — only what is true. */
    get impact() {
        const out = [];
        const m = this.m;
        const people = this.d.kind === "many" ? this.many : [this.p];
        if (this.d.kind === "move") {
            const p = this.p;
            const old = this.oldMgr(p);
            out.push({ k: "to", t: old ? _t("%(p)s will report to %(m)s instead of %(o)s.", { p: p.name, m: m.name, o: old.name })
                                       : _t("%(p)s will report to %(m)s.", { p: p.name, m: m.name }) });
            if (p.dept_id && m.dept_id && p.dept_id !== m.dept_id) {
                out.push({ k: "team", t: _t("%(p)s stays in the %(d)s team; %(m)s is in %(md)s. Change the team on the employee record if it should follow.",
                                            { p: p.name, d: p.dept, m: m.name, md: m.dept }) });
            }
        } else {
            const withTeams = people.filter((x) => kidsOf(this.idx, x.id).length).length;
            if (withTeams) {
                out.push({ k: "teams", t: withTeams === 1 ? _t("1 of them has a team — it comes along.")
                                                          : _t("%(n)s of them have a team — each comes along.", { n: withTeams }) });
            }
        }
        const after = kidsOf(this.idx, m.id).length + people.filter((x) => this.idx.eff.get(x.id) !== m.id).length;
        if (after >= WIDE) {
            out.push({ k: "wide", warn: true, t: _t("%(m)s will have %(n)s direct reports — that is a wide span.", { m: m.name, n: after }) });
        }
        out.push({ k: "keep", t: this.approversLine });
        out.push({ k: "rec", t: _t("It is recorded on each employee record — the History tab shows who changed it and when.") });
        return out;
    }

    /** Owner ruling 3 (2026-11-05): a move changes the manager ONLY. Say who
     *  keeps approving, by name when the record says. */
    async loadApprovers() {
        const p = this.p;
        if (!p || !p.empId) { return; }
        try {
            this.state.appr = await this.chart.orm.call("pb.orgchart", "approvers_of", [p.empId]);
        } catch (e) {
            console.warn("pb_orgchart: approvers unknown", e);
        }
    }

    get approversLine() {
        const a = this.d.kind === "move" ? this.state.appr || {} : {};
        const leave = a.leave || "";
        const exp = a.expense || "";
        if (leave && exp === leave) {
            return _t("Leave and expense approvals stay with %(a)s — change them on the employee record if they should move.", { a: leave });
        }
        if (leave && exp) {
            return _t("Leave approvals stay with %(a)s and expense approvals with %(b)s — change them on the employee record if they should move.", { a: leave, b: exp });
        }
        if (leave) {
            return _t("Leave approvals stay with %(a)s, and expense approvals with whoever approves them now — change them on the employee record if they should move.", { a: leave });
        }
        return _t("Leave and expense approvals stay with whoever approves them now — change them on the employee record if they should move.");
    }

    get manyNames() {
        const list = this.many;
        const show = list.slice(0, 6).map((n) => n.name).join(", ");
        return list.length > 6 ? _t("%(names)s and %(n)s more", { names: show, n: list.length - 6 }) : show;
    }

    // ---------------------------------------------------------- picker
    get candidates() {
        const d = this.d;
        const p = this.p;
        const all = this.chart.nodes.filter((x) => !x.isRole);
        const inside = (anc, id) => ancestors(this.idx, id).some((a) => a.id === anc);
        switch (d.kind) {
            case "changemgr":
                if (p.isRole) { return all.filter((x) => x.id !== p.mgr); }
                return all.filter((x) => x.id !== p.id && !inside(p.id, x.id) && x.id !== this.idx.eff.get(p.id));
            case "pickmgr": {
                const ids = new Set(d.ids);
                return all.filter((x) => !ids.has(x.id) && !d.ids.some((i) => inside(i, x.id)));
            }
            case "dotted":
                return all.filter((x) => x.id !== p.id && x.id !== this.idx.eff.get(p.id));
            case "addmember":
                return all.filter((x) => x.id !== p.id && this.idx.eff.get(x.id) !== p.id
                    && !inside(p.id, x.id) && !inside(x.id, p.id));
            case "fill":
                return all.filter((x) => x.id !== p.mgr && !(p.mgr && inside(x.id, p.mgr)));
        }
        return [];
    }

    get showPicker() {
        const k = this.d.kind;
        return ["changemgr", "pickmgr", "dotted"].includes(k)
            || ((k === "addmember" || k === "fill") && this.state.mode === "existing");
    }

    get hits() {
        const q = this.state.q.trim().toLowerCase();
        const list = this.candidates;
        const out = [];
        for (const n of list) {
            if (!q || (n.name + " " + n.title + " " + n.dept).toLowerCase().includes(q)) {
                out.push(n);
                if (out.length >= SLOTS) { break; }
            }
        }
        return out;
    }

    /** SLOTS rows, always: a keystroke rewrites them in place. */
    get slots() {
        const h = this.hits;
        const rows = [];
        for (let i = 0; i < SLOTS; i++) { rows.push({ i, n: h[i] || null }); }
        return rows;
    }

    get noMatch() { return !this.hits.length; }

    get truncatedNote() {
        return this.chart.data && this.chart.data.truncated
            ? _t("Only people shown on the chart are listed — open a team to pick someone inside it.") : "";
    }

    rowStyle(r) { return r.n ? "" : "display:none"; }
    avStyle(n) { return n ? `background:${this.chart.colorOf(n)}` : ""; }
    rowSub(n) {
        if (!n) { return ""; }
        const k = directCount(this.idx, n);
        const base = [n.title, n.dept].filter(Boolean).join(" · ");
        return k ? _t("%(b)s · %(n)s reports", { b: base, n: k }) : base;
    }
    rowOn(n) { return !!(n && this.state.sel === n.id); }

    onQ(ev) { this.state.q = ev.target.value; }
    pick(n) { if (n) { this.state.sel = n.id; } }
    setMode(m) { this.state.mode = m; this.state.sel = null; }
    setOnly(v) { this.state.only = v; }
    onTitle(ev) { this.state.title = ev.target.value; }
    onReason(ev) { this.state.reason = ev.target.value; }

    get reasons() {
        return [["growth", _t("Growth — new position")], ["backfill", _t("Backfill — someone is leaving")],
                ["cover", _t("Cover for leave")]];
    }

    // ---------------------------------------------------------- P3: publish
    get plan() { return this.chart.state.plan || {}; }
    changeIc(c) { return this.chart.changeIc(c); }
    changeTone(c) { return this.chart.changeTone(c); }
    onPname(ev) { this.state.pname = ev.target.value; }
    onPdate(ev) { this.state.pdate = ev.target.value; }
    onPnote(ev) { this.state.pnote = ev.target.value; }
    get todayIso() { return DateTime.local().toISODate(); }

    get pdateLabel() {
        const d = this.state.pdate ? DateTime.fromISO(this.state.pdate) : null;
        return d && d.isValid ? d.toLocaleString({ day: "numeric", month: "long", year: "numeric" }) : "";
    }

    get beforeLive() {
        const ap = this.plan.approver || {};
        const n = this.chart.planN;
        const out = [];
        if (ap.fast) {
            out.push(_t("No approval is needed for org chart changes here, so they are made as soon as you send them."));
        } else {
            out.push(n === 1 ? _t("Your approver, %(a)s, gets one request covering this change.", { a: ap.line || _t("the HR team") })
                             : _t("Your approver, %(a)s, gets one request covering all %(n)s.", { a: ap.line || _t("the HR team"), n }));
        }
        const when = this.state.pdate && this.state.pdate > this.todayIso
            ? _t("Once approved, the changes are made on the employee records on %(d)s.", { d: this.pdateLabel })
            : _t("Once approved, the changes are made on the employee records straight away.");
        out.push(when);
        out.push(_t("Leave and expense approvals stay with whoever approves them now. Each move shows on the person's History tab."));
        return out;
    }

    get publishBad() { return this.chart.planChanges.filter((c) => c.stale).length; }

    // ---------------------------------------------------------- P3: suggest
    async loadSuggestion() {
        try {
            this.state.sug = await this.chart.orm.call("pb.orgchart", "suggest_chart", []);
        } catch (e) {
            console.warn("pb_orgchart: suggestion failed", e);
            this.state.sugFailed = true;
        }
    }

    get sugLines() {
        const s = this.state.sug && this.state.sug.summary;
        if (!s) { return []; }
        const out = [];
        out.push(s.no_manager === 1 ? _t("1 person has no manager yet.") : _t("%(n)s people have no manager yet.", { n: this.chart.fmtInt(s.no_manager) }));
        if (s.by_team) {
            out.push(s.by_team === 1 ? _t("1 gets the manager of their own team (from the team record).")
                                     : _t("%(n)s get the manager of their own team (from the team record).", { n: this.chart.fmtInt(s.by_team) }));
        }
        if (s.by_parent) {
            out.push(s.by_parent === 1 ? _t("1 gets the manager of the team above theirs.")
                                       : _t("%(n)s get the manager of the team above theirs.", { n: this.chart.fmtInt(s.by_parent) }));
        }
        if (s.to_top) {
            out.push(s.to_top === 1 ? _t("1 team lead reports to the top of the company.")
                                    : _t("%(n)s team leads report to the top of the company.", { n: this.chart.fmtInt(s.to_top) }));
        }
        out.push(s.top_line);
        out.push(_t("%(a)s of %(b)s people get a manager. %(c)s left over.",
                    { a: this.chart.fmtInt(s.placed), b: this.chart.fmtInt(s.no_manager), c: this.chart.fmtInt(s.left_out) }));
        return out;
    }

    get sugReasons() { return (this.state.sug && this.state.sug.summary.reasons) || []; }

    get sugPreview() { return ((this.state.sug && this.state.sug.changes) || []).slice(0, 6); }

    get sugMore() {
        const n = ((this.state.sug && this.state.sug.changes) || []).length - 6;
        return n > 0 ? _t("and %(n)s more", { n: this.chart.fmtInt(n) }) : "";
    }

    // ---------------------------------------------------------- footer
    get okLabel() {
        const d = this.d;
        const s = this.state;
        switch (d.kind) {
            case "move": return this.chart.inPlan ? _t("Add to plan") : _t("Move now");
            case "many": return this.chart.inPlan ? _t("Add to plan") : _t("Move %(n)s people", { n: this.many.length });
            case "changemgr": return this.p.isRole ? _t("Move the role") : _t("Continue");
            case "pickmgr": return _t("Move %(n)s people", { n: this.many.length });
            case "dotted": return _t("Save dotted line");
            case "addmember": return s.mode === "hire" ? _t("Open the form") : s.mode === "role" ? _t("Add the role") : _t("Add to team");
            case "fill": return s.mode === "hire" ? _t("Open the form") : _t("Fill the role");
            case "publish": return _t("Send for approval");
            case "discard": return _t("Discard plan");
            case "suggest": return _t("Use it");
        }
        return _t("OK");
    }

    get okDisabled() {
        const d = this.d;
        const s = this.state;
        if (s.busy) { return true; }
        if (d.kind === "move" || d.kind === "many" || d.kind === "discard") { return false; }
        if (d.kind === "publish") { return !s.pname.trim() || !s.pdate || s.pdate < this.todayIso || !!this.publishBad; }
        if (d.kind === "suggest") { return !(s.sug && s.sug.summary.placed); }
        if (d.kind === "addmember" && s.mode === "role") { return !s.title.trim(); }
        if ((d.kind === "addmember" || d.kind === "fill") && s.mode === "hire") { return false; }
        if (d.kind === "dotted") { return !s.sel || s.sel === this.p.dotted; }
        return !s.sel;
    }

    get liveNote() {
        return this.chart.inPlan ? _t("Goes into your planned changes — nothing moves until you publish.")
                                 : _t("Takes effect straight away. Undo is one tap in the message that appears.");
    }

    get cancelLabel() {
        return { publish: _t("Keep planning"), discard: _t("Keep planning"), suggest: _t("Not now") }[this.d.kind] || _t("Cancel");
    }

    close() { if (!this.state.busy) { this.chart.closeDialog(); } }

    async run(fn) {
        this.state.busy = true;
        let ok = null;
        try { ok = await fn(); } finally { this.state.busy = false; }
        if (ok) { this.chart.closeDialog(); }
    }

    confirm() {
        if (this.okDisabled) { return; }
        const d = this.d;
        const s = this.state;
        const c = this.chart;
        switch (d.kind) {
            case "move": return this.run(() => c.doMove(d.id, d.to, !s.only));
            case "many": return this.run(() => c.doMoveMany(d.ids, d.to));
            case "changemgr":
                if (this.p.isRole) { return this.run(() => c.doMoveRole(d.id, s.sel)); }
                c.openDialog({ kind: "move", id: d.id, to: s.sel });
                return;
            case "pickmgr": return this.run(() => c.doMoveMany(d.ids, s.sel));
            case "dotted": return this.run(() => c.doDotted(d.id, s.sel));
            case "addmember":
                if (s.mode === "hire") { c.openNewStarter({ mgr: this.p }); return; }
                if (s.mode === "role") { return this.run(() => c.doAddRole(d.id, s.title.trim(), s.reason)); }
                return this.run(() => c.doMove(s.sel, d.id, true));
            case "fill":
                if (s.mode === "hire") { c.openNewStarter({ role: this.p }); return; }
                return this.run(() => c.doFill(d.id, s.sel));
            case "publish":
                return this.run(() => c.planSubmit({ name: s.pname.trim(), effective_date: s.pdate, note: s.pnote }));
            case "discard": return this.run(() => c.planDiscard());
            case "suggest": return this.run(() => c.useSuggestion());
        }
    }

    removeDotted() { return this.run(() => this.chart.doDotted(this.d.id, false)); }

    onKey(ev) {
        if (ev.key === "Enter" && ev.target.tagName !== "SELECT" && ev.target.tagName !== "TEXTAREA") {
            if (this.showPicker && !this.state.sel && this.hits.length === 1) { this.state.sel = this.hits[0].id; }
            if (!this.okDisabled) { ev.preventDefault(); this.confirm(); }
        }
    }
}
