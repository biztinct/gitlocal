/** @odoo-module **/
/**
 * `pb_pip_board` — the PIP lens on the Lifecycle hub.
 *
 * Journeys answers "what is running", New joiners "who is arriving", Exits
 * "who is leaving" and Probation "whose trial period ends soon". This one
 * answers the question an HR lead asks on a Monday morning: WHICH OF THESE IS
 * ACTUALLY WORKING, and which one is drifting.
 *
 * THE FOUR-STOP RAIL IS THE HERO, the same shape the Probation lens uses, and
 * on purpose: the two boards sit on the same hub and a reader who has learnt
 * one has learnt the other. Asked · Coaching · Plan · Decided.
 *
 * THE OTHER HERO IS THE DRIFT SIGNAL. Adherence is measured against the
 * conversations that should have happened BY NOW rather than against the whole
 * plan, because a plan in week one has held one of six and is not 17% adherent
 * — it is on track. A plan where a third of the conversations that were due
 * have not happened is the single thing on this screen worth acting on today.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO: decide who may see or change
 * anything. `pb.pip._can_read()` is the boundary and it answers an EXPLAINED
 * refusal payload rather than an access dialog; `state.canWrite` only decides
 * whether a control is OFFERED, because an offer the server would refuse is
 * worse than no offer.
 *
 * OWL RESERVES `lt`/`gt`/`lte`/`gte`/`and`/`or`/`not`/`in` AS OPERATORS (R1),
 * so no `t-as` variable in the template is named any of those.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The four stops the rail shows, in order. */
const STAGES = ["asked", "coaching", "plan", "decided"];

/** What each stop is called. Short enough to fit a four-column grid on a
 *  340px card — a label that ellipses has stopped being a label. */
const STAGE_LABEL = {
    asked: _t("Asked"),
    coaching: _t("Coaching"),
    plan: _t("Plan"),
    decided: _t("Decided"),
};

/** Which states have PASSED which stop. */
const STAGE_DONE = {
    asked: ["coaching", "active", "evaluation", "passed", "failed", "terminated"],
    coaching: ["active", "evaluation", "passed", "failed", "terminated"],
    plan: ["evaluation", "passed", "failed", "terminated"],
    decided: ["passed", "failed", "terminated"],
};

/** Which state is sitting ON each stop. */
const STAGE_CURRENT = {
    asked: ["requested"],
    coaching: ["coaching"],
    plan: ["active"],
    decided: ["evaluation"],
};

/** The four standings an objective can be in, and what each is called. */
const OBJ_STATUS = [
    { key: "on_track", label: _t("On track"), cls: "ok" },
    { key: "at_risk", label: _t("At risk"), cls: "warn" },
    { key: "met", label: _t("Met"), cls: "ok" },
    { key: "not_met", label: _t("Not met"), cls: "err" },
];

export class PbPipBoard extends Component {
    static template = "pb_pip.PbPipBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.stages = STAGES;
        this.objStatuses = OBJ_STATUS;

        this.state = useState({
            loaded: false,
            allowed: true,
            why: "",
            canWrite: false,
            isHead: false,
            closedView: false,
            employeeView: true,
            managerSeesOwn: true,
            kpis: {},
            rows: [],
            states: [],
            owners: [],
            companies: [],
            templates: [],
            capped: false,

            // filters
            q: "",
            stateFilter: "all",
            owner: "all",
            driftingOnly: false,

            // the open plan
            drawer: null,
            drawerBusy: false,

            // dialogs — one at a time, each one plain state
            objecting: null,
            starting: null,
            deciding: null,
            settings: false,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    async load() {
        try {
            const d = await this.orm.call("pb.pip", "get_board",
                                          [this.state.closedView]);
            Object.assign(this.state, {
                allowed: d.allowed,
                why: d.why || "",
                canWrite: d.can_write,
                isHead: !!d.is_head,
                employeeView: !!d.employee_view,
                managerSeesOwn: !!d.manager_sees_own,
                kpis: d.kpis || {},
                rows: d.rows || [],
                states: d.states || [],
                owners: d.owners || [],
                companies: d.companies || [],
                templates: d.templates || [],
                capped: !!d.capped,
                loaded: true,
            });
        } catch (e) {
            // Reported, never swallowed into a decoration.
            console.warn("pb_pip: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    async refresh() {
        this.state.loaded = false;
        await this.load();
        if (this.state.drawer) {
            await this.openCase(this.state.drawer.row.id);
        }
    }

    async toggleClosed() {
        this.state.closedView = !this.state.closedView;
        this.state.drawer = null;
        await this.refresh();
    }

    // --------------------------------------------------------------- filters
    get visibleRows() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.stateFilter !== "all"
                && r.state_label !== this.state.stateFilter) {
                return false;
            }
            if (this.state.owner !== "all" && r.owner !== this.state.owner) {
                return false;
            }
            if (this.state.driftingOnly && !this.needsAttention(r)) {
                return false;
            }
            if (!q) { return true; }
            return (r.employee + " " + (r.job || "") + " " + (r.dept || ""))
                .toLowerCase().includes(q);
        });
    }

    /** "Somebody has to do something about this one today." */
    needsAttention(row) {
        return !!(row.drifting || row.overdue || row.at_risk
            || row.state === "evaluation"
            || (row.state === "active" && !row.ack));
    }

    get hasFilters() {
        return this.state.q || this.state.stateFilter !== "all"
            || this.state.owner !== "all" || this.state.driftingOnly;
    }

    clearFilters() {
        Object.assign(this.state, {
            q: "", stateFilter: "all", owner: "all", driftingOnly: false,
        });
    }

    onSearch(ev) { this.state.q = ev.target.value; }
    setState(id) {
        this.state.stateFilter = this.state.stateFilter === id ? "all" : id;
    }
    setOwner(id) { this.state.owner = this.state.owner === id ? "all" : id; }
    toggleDrifting() { this.state.driftingOnly = !this.state.driftingOnly; }

    // ------------------------------------------------------------ the rail
    stageLabel(stage) { return STAGE_LABEL[stage] || stage; }

    stageCls(row, stage) {
        const st = row.state || "";
        if ((STAGE_DONE[stage] || []).includes(st)) { return "done"; }
        if ((STAGE_CURRENT[stage] || []).includes(st)) { return "now"; }
        return "todo";
    }

    stageNote(row, stage) {
        if (stage === "plan" && row.objectives) {
            return row.objectives === 1
                ? _t("1 objective") : row.objectives + " " + _t("objectives");
        }
        if (stage === "decided" && row.verdict_label) {
            return row.verdict_label;
        }
        return "";
    }

    // ------------------------------------------------------------ formatting
    day(value) {
        if (!value) { return "—"; }
        try {
            const d = new Date(value + "T00:00:00");
            return d.toLocaleDateString(undefined,
                { day: "numeric", month: "short" });
        } catch (e) { return value; }
    }

    /** The adherence chip: a sentence, a tone, and never a bare percentage. */
    adherenceChip(row) {
        if (row.state !== "active" || !row.checkins_due) {
            return null;
        }
        const held = row.checkins_done + " " + _t("of") + " "
            + row.checkins_due;
        if (row.drifting) {
            return { cls: "err", text: _t("Conversations are not happening — ")
                + held };
        }
        return { cls: "ok", text: _t("Conversations happening — ") + held };
    }

    // --------------------------------------------------------------- plumbing
    fail(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message)
            || _t("That did not work. Try again in a moment.");
        this.notif.add(msg, { type: "danger" });
    }

    async call(method, args, okMessage) {
        try {
            const res = await this.orm.call("pb.pip", method, args);
            if (okMessage) { this.notif.add(okMessage, { type: "success" }); }
            return res === undefined ? true : res;
        } catch (e) {
            this.fail(e);
            return false;
        }
    }

    // ------------------------------------------------------------- the drawer
    async openCase(caseId) {
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call("pb.pip", "get_case",
                                                    [caseId]);
        } catch (e) {
            this.fail(e);
            this.state.drawer = null;
        } finally {
            this.state.drawerBusy = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    // =====================================================================
    //  COACHING
    // =====================================================================
    async takeUp(row) {
        if (await this.call("take_up", [row.id],
                            _t("Taken up. The first conversation is in your diary in two days, and their manager has been told."))) {
            await this.refresh();
        }
    }

    onCoaching(ev) {
        if (this.state.drawer) { this.state.drawer.coaching = ev.target.value; }
    }

    async saveCoaching() {
        const d = this.state.drawer;
        if (!d) { return; }
        if (await this.call("save_coaching", [d.row.id, d.coaching || ""],
                            _t("Saved."))) {
            await this.refresh();
        }
    }

    async closeAtCoaching(row) {
        const res = await this.call(
            "close_at_coaching", [row.id, false],
            _t("Closed. Nothing was written to their record and nothing was filed — which is the best outcome this screen has."));
        if (res) {
            this.state.drawer = null;
            await this.refresh();
        }
    }

    // =====================================================================
    //  THE OBJECTIVES
    // =====================================================================
    askObjective(row) {
        this.state.objecting = {
            caseId: row.id, who: row.employee,
            name: "", metric: "", target: "", busy: false,
        };
    }

    onObjName(ev) { this.state.objecting.name = ev.target.value; }
    onObjMetric(ev) { this.state.objecting.metric = ev.target.value; }
    onObjTarget(ev) { this.state.objecting.target = ev.target.value; }
    cancelObjective() { this.state.objecting = null; }

    get canSaveObjective() {
        const o = this.state.objecting;
        return !!(o && (o.name || "").trim() && (o.metric || "").trim()
            && !o.busy);
    }

    /** The sentence under the form — ONE expression (R34). */
    get objectiveHint() {
        const o = this.state.objecting;
        if (!o) { return ""; }
        if (!(o.name || "").trim()) {
            return _t("Start with what has to change.");
        }
        if (!(o.metric || "").trim()) {
            return _t("Now say what good looks like. Without it, nobody can pass or fail this on evidence — only on a feeling.");
        }
        return _t("That is something somebody else could actually check.");
    }

    async saveObjective() {
        const o = this.state.objecting;
        if (!o || !this.canSaveObjective) { return; }
        o.busy = true;
        const res = await this.call("add_objective",
                                    [o.caseId, o.name, o.metric, o.target]);
        if (res) {
            this.state.objecting = null;
            await this.refresh();
        } else if (this.state.objecting) {
            this.state.objecting.busy = false;
        }
    }

    async setObjectiveStatus(objective, status) {
        if (await this.call("set_objective_status", [objective.id, status])) {
            await this.refresh();
        }
    }

    async removeObjective(objective) {
        if (await this.call("remove_objective", [objective.id])) {
            await this.refresh();
        }
    }

    // =====================================================================
    //  STARTING THE PLAN — the moment this stops being private
    // =====================================================================
    async askStart(row) {
        this.state.starting = {
            caseId: row.id, who: row.employee, preview: null, busy: true,
        };
        try {
            const preview = await this.orm.call("pb.pip", "start_preview",
                                                [row.id]);
            if (this.state.starting) { this.state.starting.preview = preview; }
        } catch (e) {
            this.fail(e);
            this.state.starting = null;
        } finally {
            if (this.state.starting) { this.state.starting.busy = false; }
        }
    }

    cancelStart() { this.state.starting = null; }

    get startBlocked() {
        const s = this.state.starting;
        return !!(s && s.preview && s.preview.blocked
            && s.preview.blocked.length);
    }

    async confirmStart() {
        const s = this.state.starting;
        if (!s || s.busy || this.startBlocked) { return; }
        s.busy = true;
        const res = await this.call("start_plan", [s.caseId]);
        if (res) {
            this.state.starting = null;
            this.notif.add(
                _t("The plan is running. The check-ins are in the diary and the letter is filed."),
                { type: "success" });
            await this.refresh();
        } else if (this.state.starting) {
            this.state.starting.busy = false;
        }
    }

    // =====================================================================
    //  THE EVALUATION AND THE DECISION
    // =====================================================================
    async askManager(row) {
        const res = await this.call("evaluate", [row.id]);
        if (res) {
            this.notif.add(
                _t("Their manager has a private link asking how each objective went."),
                { type: "success" });
            await this.refresh();
        }
    }

    async askDecide(row) {
        this.state.deciding = {
            caseId: row.id,
            who: row.employee,
            step: 1,
            verdict: "",
            rating: 3,
            note: "",
            statuses: {},
            evaluation: null,
            objectives: [],
            preview: null,
            busy: true,
        };
        try {
            const detail = await this.orm.call("pb.pip", "get_case", [row.id]);
            const d = this.state.deciding;
            if (d) {
                d.evaluation = detail.evaluation || null;
                d.objectives = detail.objectives || [];
                for (const objective of d.objectives) {
                    d.statuses[objective.id] = objective.status;
                }
            }
        } catch (e) {
            this.fail(e);
        } finally {
            if (this.state.deciding) { this.state.deciding.busy = false; }
        }
    }

    cancelDecide() { this.state.deciding = null; }
    decideStep(step) {
        const d = this.state.deciding;
        if (!d) { return; }
        d.step = step;
        if (step !== 3) { d.preview = null; }
    }

    setObjectiveOutcome(objectiveId, status) {
        if (this.state.deciding) {
            this.state.deciding.statuses[objectiveId] = status;
        }
    }

    onDecideNote(ev) { this.state.deciding.note = ev.target.value; }
    onRating(ev) {
        const n = parseInt(ev.target.value, 10);
        this.state.deciding.rating = isNaN(n) ? 3 : Math.max(1, Math.min(5, n));
    }

    /** The score the manager gave against one objective, or nothing. */
    evalScore(objectiveId) {
        const d = this.state.deciding;
        if (!d || !d.evaluation) { return ""; }
        const hit = (d.evaluation.objectives || []).find(
            (o) => o.id === objectiveId);
        return hit ? hit.score : "";
    }

    async pickVerdict(verdict) {
        const d = this.state.deciding;
        if (!d) { return; }
        d.verdict = verdict;
        d.busy = true;
        d.preview = null;
        try {
            d.preview = await this.orm.call("pb.pip", "verdict_preview",
                                            [d.caseId, verdict]);
            d.step = 3;
        } catch (e) {
            this.fail(e);
        } finally {
            if (this.state.deciding) { this.state.deciding.busy = false; }
        }
    }

    async saveDecision() {
        const d = this.state.deciding;
        if (!d || d.busy || !d.verdict) { return; }
        d.busy = true;
        const res = await this.call(
            "save_verdict",
            [d.caseId, d.verdict, d.verdict === "pass" ? d.rating : false,
             d.note || false, d.statuses]);
        if (res) {
            const done = {
                pass: _t("Recorded. They have been told, the check-ins are out of the diary, and nothing was filed."),
                fail: _t("Recorded. Nothing about their leaving has been started — that is a separate button, and there are usually other options."),
            }[d.verdict];
            this.state.deciding = null;
            this.notif.add(done, { type: "success" });
            await this.refresh();
        } else if (this.state.deciding) {
            this.state.deciding.busy = false;
        }
    }

    // =====================================================================
    //  THE EXIT, THE SETTINGS, THE DOORS
    // =====================================================================
    async startExit(row) {
        const act = await this.call("start_exit", [row.id]);
        if (act) {
            this.notif.add(_t("The leaving checklist is open."),
                           { type: "success" });
            this.action.doAction(act);
        }
    }

    async runAutomation() {
        const res = await this.call("run_automation", []);
        if (res) {
            const n = (c, one, many) => c + " " + (c === 1 ? one : many);
            this.notif.add(
                _t("%(missed)s flagged as missed, %(due)s past their end date.",
                   { missed: n(res.missed || 0, _t("check-in"), _t("check-ins")),
                     due: n(res.due || 0, _t("plan"), _t("plans")) }),
                { type: "success" });
            await this.refresh();
        }
    }

    openSettings() { this.state.settings = true; }
    closeSettings() { this.state.settings = false; }

    async setSwitch(name, value) {
        const res = await this.call("set_switch", [name, value]);
        if (res) {
            await this.refresh();
            this.notif.add(
                name === "employee_view"
                    ? (value
                        ? _t("People can now see their own plan and acknowledge it.")
                        : _t("The employee page is off. Nothing is emailed to the person and /my/growth is closed."))
                    : (value
                        ? _t("A manager can see the request they raised.")
                        : _t("A manager can no longer see the request they raised.")),
                { type: "success" });
        }
    }

    async openCaseRecord(row) {
        const act = await this.call("open_case_action", [row.id]);
        if (act) { this.action.doAction(act); }
    }

    async openLetter(letterId) {
        const act = await this.call("open_letter_action", [letterId]);
        if (act) { this.action.doAction(act); }
    }

    async openEmployee(row) {
        const act = await this.call("open_employee_action", [row.employee_id]);
        if (act) { this.action.doAction(act); }
    }

    openTemplates() {
        this.action.doAction("pb_pip.action_pb_pip_template");
    }

    openAll() {
        this.action.doAction("pb_pip.action_pb_pip_case");
    }
}

registry.category("actions").add("pb_pip_board", PbPipBoard);
