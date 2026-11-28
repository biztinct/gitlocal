/** @odoo-module **/
/**
 * People › JOBS — how the organisation is laid out (WDGAP S8-C).
 *
 * Four parts, picked from one quiet step row:
 *   Jobs          the filter panel over every job: level, team, people,
 *                 people to hire, pay band (when Pay is installed), paused;
 *                 a row opens the job page (level, description, pause).
 *   Levels        the named ladder, set once, in order.
 *   Cost centres  the list, what contracts carry that is not on it yet,
 *                 the team's usual one, and "Move people … from <date>".
 *   Hiring pause  per company, team or role, with the reason people read.
 *
 * The server decides who may do what (`pb.org.structure`); this screen only
 * hides presses the server would refuse. Every icon comes from the shared
 * `ic()` registry, no emoji.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const FACADE = "pb.org.structure";
const PAGE = 60;

export class PbOrgJobs extends Component {
    static template = "pb_org_structure.PbOrgJobs";
    static components = { PbFilterLayout };
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ic = ic;
        this.state = useState({
            loaded: false, allowed: true, head: {}, tab: "jobs",
            rows: [], total: 0, listLoaded: false, loadingMore: false,
            job: null, jobBusy: false, jobForm: {}, pauseAsk: null,
            levelForm: { id: 0, name: "", description: "", company_id: 0 },
            cc: null, ccForm: { id: 0, code: "", name: "", note: "", company_id: 0 },
            move: { cost_centre_id: 0, who: "team", department_id: 0, people: [],
                    query: "", found: [], date: "", note: "", preview: null },
            pauses: null, busy: false,
        });
        this.kit = useFilterKit({
            model: FACADE,
            noun: _t("jobs"),
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => {
            await this.loadHead();
            // A palette row may ask for one part ("cost" / "pause" / "levels").
            const focus = (this.props.arrival && this.props.arrival.focus)
                || (this.props.action && this.props.action.context
                    && this.props.action.context.pb_focus) || "";
            if (["levels", "cost", "pause"].includes(focus) && this.state.allowed) {
                await this.qStepPick(focus);
            }
        });
    }

    // ------------------------------------------------------------ loading
    async loadHead() {
        try {
            const head = await this.orm.call(FACADE, "get_head", []);
            this.state.allowed = head.allowed !== false;
            this.state.head = head;
            if (!this.state.move.date) { this.state.move.date = head.today || ""; }
        } catch (e) {
            this.state.allowed = false;
        }
        this.state.loaded = true;
    }

    async loadPage({ more = false } = {}) {
        if (this.kit.failed) { this.state.listLoaded = true; return; }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call(FACADE, "get_job_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.total = d.total;
            this.state.listLoaded = true;
        } catch (e) {
            this.fail(e);
            this.state.listLoaded = true;
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    get hasMore() { return this.state.rows.length < this.state.total; }

    fail(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message)
            || _t("That did not work. Try again in a moment.");
        this.notif.add(msg, { type: "warning" });
    }
    say(msg) { this.notif.add(msg, { type: "success" }); }

    async call(method, args = [], kwargs = {}) {
        this.state.busy = true;
        try {
            return await this.orm.call(FACADE, method, args, kwargs);
        } catch (e) {
            this.fail(e);
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------- whole sentences (PRD-3)
    nContracts(n) { return _t("Contracts: %s", n); }
    nJobs(n) { return _t("Jobs: %s", n); }
    nOpenRoles(n) { return _t("Roles with somebody to hire: %s", n); }
    companyOnly(name) { return _t("%s only", name); }
    fromDate(d) { return _t("from %s", d); }
    pausedWith(name) { return _t("Paused with %s", name); }
    get previewLine() {
        const p = this.state.move.preview || {};
        const cc = this.moveCostCentre;
        return _t("People who move to %(code)s from %(date)s: %(n)s.",
                  { n: p.moving || 0, code: (cc && cc.code) || "", date: p.from || "" });
    }
    get alreadyLine() {
        return _t("Already there: %s.", (this.state.move.preview || {}).already || 0);
    }

    // --------------------------------------------------------------- steps
    get k() { return this.state.head.kpis || {}; }
    get canManage() { return !!this.state.head.can_manage; }
    get canPause() { return !!this.state.head.can_pause; }
    get multiCompany() { return (this.state.head.companies || []).length > 1; }

    get steps() {
        const k = this.k;
        const t = this.state.tab;
        const paused = (k.paused_roles || 0);
        return [
            { key: "jobs", n: k.jobs || 0, title: _t("Jobs"), on: t === "jobs",
              countLabel: "", count: k.jobs || 0,
              sub: k.no_level ? _t("%s without a level", k.no_level) : _t("Every job has a level"),
              flag: "", flagTone: "" },
            { key: "levels", n: k.levels || 0, title: _t("Levels"), on: t === "levels",
              countLabel: "", count: k.levels || 0,
              sub: k.levels ? _t("lowest first") : _t("None set yet"), flag: "", flagTone: "" },
            { key: "cost", n: k.cost_centres || 0, title: _t("Cost centres"), on: t === "cost",
              countLabel: "", count: k.cost_centres || 0,
              sub: k.scheduled ? _t("Changes waiting for their date: %s", k.scheduled) : _t("on the list"),
              flag: k.unlisted ? _t("Contracts not on the list: %s", k.unlisted) : "",
              flagTone: "amber" },
            { key: "pause", n: paused, title: _t("Hiring pause"), on: t === "pause",
              countLabel: "", count: paused,
              sub: paused ? _t("roles paused") : _t("Hiring is open everywhere"),
              flag: paused ? _t("Paused") : "", flagTone: "amber" },
        ];
    }
    async qStepPick(key) {
        this.state.tab = key;
        if (key === "cost" && !this.state.cc) { await this.loadCost(); }
        if (key === "pause" && !this.state.pauses) { await this.loadPauses(); }
    }

    // ---------------------------------------------------------------- jobs
    get searchHint() { return _t("Find a job, a team or a level"); }
    get emptyKind() {
        if (!this.state.listLoaded || this.state.rows.length) { return ""; }
        if (!this.kit.total && !this.kit.search) { return "none"; }
        return "filters";
    }
    async openJob(id) {
        this.state.jobBusy = true;
        try {
            const job = await this.orm.call(FACADE, "get_job", [id]);
            this.state.job = job;
            this.state.jobForm = { level_id: job.level_id || 0, description: job.description || "" };
            this.state.pauseAsk = null;
        } catch (e) {
            this.fail(e);
        } finally {
            this.state.jobBusy = false;
        }
    }
    closeJob() { this.state.job = null; this.state.pauseAsk = null; }
    async saveJob() {
        const job = this.state.job;
        const res = await this.call("save_job", [job.id, {
            level_id: Number(this.state.jobForm.level_id) || false,
            description: this.state.jobForm.description,
        }]);
        if (res) {
            this.state.job = res;
            this.say(_t("Saved."));
            await this.loadHead();
            await this.loadPage();
        }
    }
    onJobKey(ev, row) {
        if (ev.key === "Enter") { ev.preventDefault(); this.openJob(row.id); }
    }

    // -------------------------------------------------------------- levels
    get levels() { return this.state.head.levels || []; }
    editLevel(lv) {
        this.state.levelForm = { id: lv.id, name: lv.name, description: lv.description,
                                 company_id: lv.company_id || 0 };
    }
    resetLevel() { this.state.levelForm = { id: 0, name: "", description: "", company_id: 0 }; }
    async saveLevel() {
        const f = this.state.levelForm;
        const rows = await this.call("save_level", [{
            id: f.id || false, name: f.name, description: f.description,
            company_id: Number(f.company_id) || false }]);
        if (rows) { this.state.head.levels = rows; this.resetLevel(); await this.loadHead(); }
    }
    async moveLevel(lv, step) {
        const rows = await this.call("move_level", [lv.id, step]);
        if (rows) { this.state.head.levels = rows; }
    }
    async archiveLevel(lv) {
        const rows = await this.call("archive_level", [lv.id]);
        if (rows) { this.state.head.levels = rows; await this.loadHead(); }
    }

    // -------------------------------------------------------- cost centres
    async loadCost() {
        const cc = await this.call("get_cost_centres");
        if (cc) { this.state.cc = cc; }
    }
    editCost(row) {
        this.state.ccForm = { id: row.id, code: row.code, name: row.name, note: row.note,
                              company_id: row.company_id };
    }
    resetCost() { this.state.ccForm = { id: 0, code: "", name: "", note: "", company_id: 0 }; }
    async saveCost() {
        const f = this.state.ccForm;
        const cc = await this.call("save_cost_centre", [{
            id: f.id || false, code: f.code, name: f.name, note: f.note,
            company_id: Number(f.company_id) || false }]);
        if (cc) { this.state.cc = cc; this.resetCost(); await this.loadHead(); }
    }
    async toggleCost(row) {
        const cc = await this.call("set_cost_centre_active", [row.id, !row.active]);
        if (cc) { this.state.cc = cc; await this.loadHead(); }
    }
    async makeList() {
        const cc = await this.call("make_list_from_contracts");
        if (cc) {
            this.state.cc = cc;
            this.say(_t("Added to the list: %s. No contract was changed.", cc.made || 0));
            await this.loadHead();
        }
    }
    async setTeamCost(team, ev) {
        const cc = await this.call("set_team_cost_centre", [team.id, Number(ev.target.value) || false]);
        if (cc) { this.state.cc = cc; }
    }
    costChoices(companyId) {
        const rows = (this.state.cc && this.state.cc.rows) || [];
        return rows.filter((r) => r.active && (!companyId || r.company_id === companyId));
    }
    get moveCostCentre() {
        const id = Number(this.state.move.cost_centre_id);
        return ((this.state.cc && this.state.cc.rows) || []).find((r) => r.id === id) || null;
    }
    get moveTeams() {
        const cc = this.moveCostCentre;
        const teams = (this.state.cc && this.state.cc.teams) || [];
        return cc ? teams.filter((t) => t.company_id === cc.company_id) : teams;
    }
    setMove(key, value) {
        this.state.move[key] = value;
        this.state.move.preview = null;
    }
    async findPeople(ev) {
        const q = ev.target.value;
        this.state.move.query = q;
        const cc = this.moveCostCentre;
        if ((q || "").trim().length < 2) { this.state.move.found = []; return; }
        try {
            this.state.move.found = await this.orm.call(FACADE, "search_people", [q],
                { company_id: cc ? cc.company_id : false });
        } catch (e) { this.state.move.found = []; }
    }
    addPerson(p) {
        if (!this.state.move.people.find((x) => x.id === p.id)) {
            this.state.move.people.push(p);
        }
        this.state.move.found = [];
        this.state.move.query = "";
        this.state.move.preview = null;
    }
    removePerson(p) {
        this.state.move.people = this.state.move.people.filter((x) => x.id !== p.id);
        this.state.move.preview = null;
    }
    moveArgs() {
        const m = this.state.move;
        return {
            employee_ids: m.who === "people" ? m.people.map((p) => p.id) : false,
            department_id: m.who === "team" ? (Number(m.department_id) || false) : false,
        };
    }
    async previewMove() {
        const m = this.state.move;
        const res = await this.call("preview_move", [Number(m.cost_centre_id) || false, m.date], this.moveArgs());
        if (res) { this.state.move.preview = res; }
    }
    async confirmMove() {
        const m = this.state.move;
        const res = await this.call("move_people", [Number(m.cost_centre_id) || false, m.date],
            Object.assign(this.moveArgs(), { note: m.note }));
        if (res) {
            this.state.cc = res;
            this.say(res.waiting
                ? _t("Changes waiting for their date: %s. They are made on the day.", res.waiting)
                : _t("People moved: %s.", res.moved || 0));
            Object.assign(this.state.move, { people: [], preview: null, note: "" });
            await this.loadHead();
        }
    }
    async cancelMove(mv) {
        const res = await this.call("cancel_move", [mv.id]);
        if (res) { this.state.cc = res; await this.loadHead(); }
    }

    // --------------------------------------------------------------- pause
    get showCompanies() {
        const cos = (this.state.pauses && this.state.pauses.companies) || [];
        return cos.length > 1 || cos.some((c) => c.paused);
    }
    async loadPauses() {
        const p = await this.call("get_pauses");
        if (p) { this.state.pauses = p; }
    }
    askPause(kind, rec) {
        this.state.pauseAsk = { kind, id: rec.id, name: rec.name, reason: "" };
    }
    cancelPause() { this.state.pauseAsk = null; }
    async confirmPause() {
        const a = this.state.pauseAsk;
        const p = await this.call("set_pause", [a.kind, a.id, true, a.reason]);
        if (p) { await this.afterPause(p, _t("Hiring paused for %s.", a.name)); }
    }
    async restart(kind, rec) {
        const p = await this.call("set_pause", [kind, rec.id, false]);
        if (p) { await this.afterPause(p, _t("Hiring restarted for %s.", rec.name)); }
    }
    async afterPause(p, msg) {
        this.state.pauses = p;
        this.state.pauseAsk = null;
        this.say(msg);
        await this.loadHead();
        if (this.state.job) { await this.openJob(this.state.job.id); }
        if (this.kit.loaded) { await this.loadPage(); }
    }
    isAsking(kind, id) {
        const a = this.state.pauseAsk;
        return !!a && a.kind === kind && a.id === id;
    }
}

registry.category("actions").add("pb_org_jobs", PbOrgJobs);
