/** @odoo-module **/
/**
 * `pb_hiring_board` — the Hiring lens on the Lifecycle hub.
 *
 * Journeys answers "what is running", New joiners "who is arriving", Exits
 * "who is leaving". This one comes BEFORE all of them in the story and so it
 * sits first on the rail: WHO ARE WE TRYING TO HIRE, AND WHAT IS STUCK.
 *
 * THE ORDER IS THE HERO. The board is not sorted by date; it is sorted by
 * what needs a person. Anything waiting on the reader's own signature comes
 * first, then anything over budget, then an open role with nobody recruiting
 * it, then the rest by age. A hiring board sorted newest-first hides the
 * request that has been stuck for a fortnight, which is the only one that
 * matters.
 *
 * THE DRAWER IS THE OTHER HALF. One request, everything about it: the money,
 * the advert versions, the adverts prepared per job board, the referrals, and
 * the candidates with the four screening answers inline. Every door it opens
 * is a server-built action, because a second opinion written in JavaScript
 * about what a person may do would only ever disagree with the one that
 * counts.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO: decide who may change anything.
 * `pb.hiring._require_recruit()` / `_require_write()` and the record rules are
 * the boundary; `state.canRecruit` and `state.canWrite` only decide whether a
 * control is OFFERED, because an offer the server would refuse is worse than
 * no offer. The two tiers are different work and not one permission: adverts,
 * job boards and screening are the RECRUITER's; agreeing, closing and filling
 * a role are the hiring MANAGER's.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The four screening answers, in the order a screener weighs them. */
const SCREEN_ORDER = ["shortlisted", "future_fit", "other_role", "rejected"];

const SCREEN_ICON = {
    shortlisted: "checkCircle",
    future_fit: "bookOpen",
    other_role: "arrowLeftRight",
    rejected: "xCircle",
};

const BUDGET_ICON = { within: "checkCircle", over: "alert", unknown: "info" };

/** How an interview is happening, drawn rather than spelled out. */
const MODE_ICON = { in_person: "mapPin", video: "monitor", phone: "smartphone" };

/**
 * The four questions the Interviews tab answers, in the order somebody asks
 * them. "Late" is last and is the only one that is ever red: it is the only
 * one where a person outside the company is waiting.
 */
const IV_FOCUS = ["today", "week", "awaiting", "late"];

/** A recommendation is stored 1-4; this is what each number looks like. */
const VERDICT_ICON = {
    strong_yes: "smilePlus", yes: "smile", no: "meh", strong_no: "frown",
};

export class PbHiringBoard extends Component {
    static template = "pb_hiring.PbHiringBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.screenOrder = SCREEN_ORDER;
        this.ivFocusKeys = IV_FOCUS;

        this.state = useState({
            loaded: false,
            allowed: true,
            canWrite: false,
            canRecruit: false,
            canAdmin: false,
            canRaise: false,
            kpis: {},
            rows: [],
            departments: [],
            countries: [],
            recruiters: [],
            states: [],
            roleTypes: [],
            budgetStates: [],
            screenTags: [],
            ruleCount: 0,
            total: 0,
            capped: false,

            // filters
            q: "",
            dept: "all",
            country: "all",
            stage: "all",
            recruiter: "all",
            focus: "",

            // the open request
            drawer: null,
            drawerBusy: false,

            // one dialog at a time, each one plain state
            raising: null,
            writingJd: null,
            moving: null,

            // ---- A2, the interview loop ----
            // The board has TWO questions and they are not the same
            // question: "which roles are we trying to fill" and "what is
            // happening this week". A single list that tried to answer both
            // would answer neither.
            tab: "roles",
            interviews: [],
            interviewStates: [],
            modes: [],
            stepKinds: [],
            noShowReasons: [],
            delayKinds: [],
            decisions: [],
            recommendations: [],
            ivFocus: "",
            ivQ: "",
            scheduling: null,
            rescheduling: null,
            noShowing: null,
            debriefing: null,
            rejecting: null,
            panelQ: "",
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    screenIcon(tag) { return SCREEN_ICON[tag] || "circle"; }

    /** The word for a screening answer, from the SERVER's own list — never a
     *  second copy in JavaScript that would drift out of step. */
    screenLabel(tag) {
        const row = (this.state.screenTags || []).find((t) => t.key === tag);
        return row ? row.label : tag;
    }

    budgetIcon(status) { return BUDGET_ICON[status] || "info"; }

    // ------------------------------------------------------------------ read
    async load() {
        try {
            const d = await this.orm.call("pb.hiring", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                canRecruit: d.can_recruit,
                canAdmin: d.can_admin,
                canRaise: d.can_raise,
                kpis: d.kpis || {},
                rows: d.rows || [],
                departments: d.departments || [],
                countries: d.countries || [],
                recruiters: d.recruiters || [],
                states: d.states || [],
                roleTypes: d.role_types || [],
                budgetStates: d.budget_states || [],
                screenTags: d.screen_tags || [],
                ruleCount: d.rule_count || 0,
                total: d.total || 0,
                capped: !!d.capped,
                interviews: d.interviews || [],
                interviewStates: d.interview_states || [],
                modes: d.modes || [],
                stepKinds: d.step_kinds || [],
                noShowReasons: d.no_show_reasons || [],
                delayKinds: d.delay_kinds || [],
                decisions: d.decisions || [],
                recommendations: d.recommendations || [],
                loaded: true,
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.allowed = false;
            console.warn("pb_hiring: the board could not be read", e);
        }
    }

    async refresh() {
        this.state.loaded = false;
        await this.load();
        if (this.state.drawer) {
            await this.openDrawer(this.state.drawer.id);
        }
    }

    // --------------------------------------------------------------- filters
    get filtered() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.dept !== "all"
                && String(r.department_id) !== String(this.state.dept)) {
                return false;
            }
            if (this.state.country !== "all"
                && String(r.country_id) !== String(this.state.country)) {
                return false;
            }
            if (this.state.stage !== "all" && r.state !== this.state.stage) {
                return false;
            }
            if (this.state.recruiter !== "all"
                && String(r.recruiter_id) !== String(this.state.recruiter)) {
                return false;
            }
            if (this.state.focus === "waiting" && !r.waiting) { return false; }
            if (this.state.focus === "mine" && !r.waiting_mine) { return false; }
            if (this.state.focus === "over" && r.budget_status !== "over") {
                return false;
            }
            if (this.state.focus === "open" && r.state !== "open") {
                return false;
            }
            if (q) {
                const hay = [r.title, r.name, r.department, r.location,
                             r.recruiter, r.requested_by]
                    .join(" ").toLowerCase();
                if (!hay.includes(q)) { return false; }
            }
            return true;
        });
    }

    get anyFilter() {
        return !!(this.state.q || this.state.focus
                  || this.state.dept !== "all" || this.state.country !== "all"
                  || this.state.stage !== "all"
                  || this.state.recruiter !== "all");
    }

    clearFilters() {
        Object.assign(this.state, {
            q: "", focus: "", dept: "all", country: "all", stage: "all",
            recruiter: "all",
        });
    }

    toggleFocus(key) {
        this.state.focus = this.state.focus === key ? "" : key;
    }

    // ---------------------------------------------------------------- drawer
    async openDrawer(id) {
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call(
                "pb.hiring", "get_requisition", [id]);
        } catch (e) {
            this.fail(e);
        } finally {
            this.state.drawerBusy = false;
        }
    }

    closeDrawer() {
        this.state.drawer = null;
        this.state.writingJd = null;
        this.state.moving = null;
    }

    // ------------------------------------------------------------------ acts
    async act(verb, payload, { reload = true, silent = false } = {}) {
        try {
            const res = await this.orm.call("pb.hiring", "act",
                                            [verb, payload || {}]);
            if (res && res.type === "ir.actions.act_window") {
                await this.action.doAction(res);
                return res;
            }
            if (res && res.note && !silent) {
                this.notif.add(res.note, { type: "success" });
            }
            if (reload) { await this.refresh(); }
            return res;
        } catch (e) {
            this.fail(e);
            return null;
        }
    }

    fail(e) {
        const message = (e && e.data && e.data.message)
            || (e && e.message) || _t("That did not work.");
        this.notif.add(message, { type: "danger" });
    }

    // ------------------------------------------------------- raise a request
    startRaise() {
        this.state.raising = {
            title: "", role_type: "new_role", department_id: "",
            headcount: 1, budget_cost: 0, location: "",
            country_id: "", target_start_date: "", requirements: "",
        };
    }

    cancelRaise() { this.state.raising = null; }

    async saveRaise() {
        const form = this.state.raising;
        if (!form.title || !form.department_id) {
            this.notif.add(
                _t("A hiring request needs a role name and the part of the business it is for."),
                { type: "warning" });
            return;
        }
        const res = await this.act("create", { ...form });
        if (res) {
            this.state.raising = null;
            if (res.id) { await this.openDrawer(res.id); }
        }
    }

    // ---------------------------------------------------------- the advert
    startJd() {
        const d = this.state.drawer;
        this.state.writingJd = { title: d ? d.title : "", summary: "", body: "" };
    }

    cancelJd() { this.state.writingJd = null; }

    async saveJd() {
        const d = this.state.drawer;
        const form = this.state.writingJd;
        if (!d) { return; }
        const res = await this.act("new_jd", {
            requisition_id: d.id, title: form.title,
            summary: form.summary, body: form.body,
        });
        if (res) { this.state.writingJd = null; }
    }

    // -------------------------------------------------------- the screening
    async screen(applicant, tag) {
        if (tag === "other_role") {
            this.state.moving = { applicant_id: applicant.id,
                                  name: applicant.name, job_id: "" };
            return;
        }
        await this.act("screen", { applicant_id: applicant.id, tag });
    }

    cancelMove() { this.state.moving = null; }

    async saveMove() {
        const move = this.state.moving;
        if (!move || !move.job_id) {
            this.notif.add(_t("Pick the role they are better suited to."),
                           { type: "warning" });
            return;
        }
        const res = await this.act("screen", {
            applicant_id: move.applicant_id, tag: "other_role",
            job_id: Number(move.job_id),
        });
        if (res) { this.state.moving = null; }
    }

    // =====================================================================
    //  A2 — the interviews
    // =====================================================================
    modeIcon(mode) { return MODE_ICON[mode] || "calendar"; }

    verdictIcon(avg) {
        if (!avg) { return "circle"; }
        if (avg >= 3.5) { return VERDICT_ICON.strong_yes; }
        if (avg >= 2.5) { return VERDICT_ICON.yes; }
        if (avg >= 1.5) { return VERDICT_ICON.no; }
        return VERDICT_ICON.strong_no;
    }

    /** The words for a focus chip, so the server keeps no second copy. */
    ivFocusLabel(key) {
        return {
            today: _t("Today"),
            week: _t("This week"),
            awaiting: _t("Waiting on an opinion"),
            late: _t("Late"),
        }[key] || key;
    }

    ivFocusCount(key) {
        if (key === "late") {
            return this.state.interviews.filter((i) => i.feedback_late).length;
        }
        return this.state.interviews.filter((i) => i.bucket === key).length;
    }

    get filteredInterviews() {
        const q = (this.state.ivQ || "").trim().toLowerCase();
        return this.state.interviews.filter((i) => {
            if (this.state.ivFocus === "late" && !i.feedback_late) {
                return false;
            }
            if (this.state.ivFocus && this.state.ivFocus !== "late"
                && i.bucket !== this.state.ivFocus) {
                return false;
            }
            if (q) {
                const hay = [i.candidate, i.role, i.recruiter,
                             (i.panel || []).join(" ")]
                    .join(" ").toLowerCase();
                if (!hay.includes(q)) { return false; }
            }
            return true;
        });
    }

    toggleIvFocus(key) {
        this.state.ivFocus = this.state.ivFocus === key ? "" : key;
    }

    setTab(tab) { this.state.tab = tab; }

    /**
     * Tomorrow at ten, as the value a `datetime-local` input wants.
     *
     * A scheduling dialog that opens empty is a dialog where the first thing
     * anybody does is type today's date badly. Tomorrow at ten is almost
     * never right and is always close, which is the useful kind of default.
     */
    defaultStart() {
        const when = new Date();
        when.setDate(when.getDate() + 1);
        when.setHours(10, 0, 0, 0);
        const pad = (n) => String(n).padStart(2, "0");
        return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-`
            + `${pad(when.getDate())}T${pad(when.getHours())}:`
            + `${pad(when.getMinutes())}`;
    }

    /**
     * A `datetime-local` value is the reader's own wall clock; the server
     * stores naive UTC. Converting here rather than on the server is what
     * makes "ten o'clock" mean ten o'clock to the person who typed it.
     */
    toServerTime(local) {
        if (!local) { return ""; }
        const when = new Date(local);
        if (isNaN(when.getTime())) { return ""; }
        const pad = (n) => String(n).padStart(2, "0");
        return `${when.getUTCFullYear()}-${pad(when.getUTCMonth() + 1)}-`
            + `${pad(when.getUTCDate())} ${pad(when.getUTCHours())}:`
            + `${pad(when.getUTCMinutes())}:00`;
    }

    /** A stored naive-UTC string, back on the reader's own clock. */
    localWhen(stored) {
        if (!stored) { return ""; }
        const when = new Date(`${String(stored).replace(" ", "T")}Z`);
        if (isNaN(when.getTime())) { return String(stored); }
        return when.toLocaleString(undefined, {
            day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
        });
    }

    // --------------------------------------------------------- arranging one
    startSchedule(candidate) {
        const d = this.state.drawer;
        this.state.panelQ = "";
        this.state.scheduling = {
            applicant_id: candidate.id,
            name: candidate.name,
            requisition_id: d ? d.id : 0,
            step_id: "",
            start: this.defaultStart(),
            duration_minutes: 45,
            mode: "in_person",
            location: "",
            panel: [],
        };
    }

    cancelSchedule() { this.state.scheduling = null; }

    get panelChoices() {
        const d = this.state.drawer;
        const people = (d && d.panel_people) || [];
        const q = (this.state.panelQ || "").trim().toLowerCase();
        if (!q) { return people.slice(0, 40); }
        // Folded on the server so an accent cannot hide a colleague (R78).
        return people.filter((p) => p.fold.includes(q)
                             || p.name.toLowerCase().includes(q)).slice(0, 40);
    }

    onPanel(id) {
        const form = this.state.scheduling || this.state.rescheduling;
        return !!form && form.panel.includes(id);
    }

    togglePanel(id) {
        const form = this.state.scheduling || this.state.rescheduling;
        if (!form) { return; }
        const at = form.panel.indexOf(id);
        if (at === -1) { form.panel.push(id); } else { form.panel.splice(at, 1); }
    }

    panelName(id) {
        const d = this.state.drawer;
        const hit = ((d && d.panel_people) || []).find((p) => p.id === id);
        return hit ? hit.name : "";
    }

    async saveSchedule() {
        const form = this.state.scheduling;
        if (!form) { return; }
        if (!form.panel.length) {
            this.notif.add(
                _t("Say who is on the panel — nobody can give an opinion on a conversation they were not in."),
                { type: "warning" });
            return;
        }
        const start = this.toServerTime(form.start);
        if (!start) {
            this.notif.add(_t("Say when it is."), { type: "warning" });
            return;
        }
        const res = await this.act("schedule", {
            applicant_id: form.applicant_id,
            requisition_id: form.requisition_id,
            step_id: form.step_id || false,
            start,
            duration_minutes: Number(form.duration_minutes) || 45,
            mode: form.mode,
            location: form.location,
            panel_employee_ids: form.panel,
        });
        if (res) { this.state.scheduling = null; }
    }

    // ----------------------------------------------------------- moving one
    startReschedule(interview) {
        this.state.panelQ = "";
        this.state.rescheduling = {
            interview_id: interview.id,
            name: interview.candidate,
            was: interview.start,
            start: this.defaultStart(),
            duration_minutes: 45,
            mode: interview.mode || "in_person",
            location: interview.location || "",
            reason: "",
            delay_kind: "",
            panel: [],
        };
    }

    cancelReschedule() { this.state.rescheduling = null; }

    async saveReschedule() {
        const form = this.state.rescheduling;
        if (!form) { return; }
        if (!form.reason.trim()) {
            this.notif.add(
                _t("Say why it is moving. In six weeks nobody will remember, and this is the only place the answer will be."),
                { type: "warning" });
            return;
        }
        if (!form.delay_kind) {
            this.notif.add(
                _t("Say whose side moved it. It is not about blame — it is the only way anybody can answer why hiring here takes as long as it does."),
                { type: "warning" });
            return;
        }
        const start = this.toServerTime(form.start);
        if (!start) {
            this.notif.add(_t("Say when it is moving to."), { type: "warning" });
            return;
        }
        const res = await this.act("reschedule", {
            interview_id: form.interview_id,
            start,
            duration_minutes: Number(form.duration_minutes) || 45,
            mode: form.mode,
            location: form.location,
            reason: form.reason,
            delay_kind: form.delay_kind,
        });
        if (res) { this.state.rescheduling = null; }
    }

    // --------------------------------------------------------- nobody came
    startNoShow(interview) {
        this.state.noShowing = {
            interview_id: interview.id,
            name: interview.candidate,
            by: "",
            note: "",
        };
    }

    cancelNoShow() { this.state.noShowing = null; }

    async saveNoShow() {
        const form = this.state.noShowing;
        if (!form) { return; }
        if (!form.by) {
            this.notif.add(
                _t("Say who did not come — the candidate, or somebody on our side."),
                { type: "warning" });
            return;
        }
        const res = await this.act("no_show", { ...form });
        if (res) { this.state.noShowing = null; }
    }

    // ------------------------------------------------------------ the debrief
    startDebrief(interview) {
        this.state.debriefing = {
            interview_id: interview.id,
            name: interview.candidate,
            notes: interview.decision ? "" : "",
            decision: interview.decision || "",
        };
    }

    cancelDebrief() { this.state.debriefing = null; }

    async saveDebrief() {
        const form = this.state.debriefing;
        if (!form) { return; }
        if (!form.decision) {
            this.notif.add(
                _t("Say what was decided: we want them, keep them warm, or not this time."),
                { type: "warning" });
            return;
        }
        const res = await this.act("debrief", { ...form });
        if (res) { this.state.debriefing = null; }
    }

    // ------------------------------------------------------- the two answers
    async nextRound(candidate, stepId) {
        await this.act("next_round", {
            applicant_id: candidate.id, step_id: stepId || false,
        });
    }

    startReject(candidate) {
        this.state.rejecting = {
            applicant_id: candidate.id,
            name: candidate.name,
            reason_id: "",
        };
    }

    cancelReject() { this.state.rejecting = null; }

    async saveReject() {
        const form = this.state.rejecting;
        if (!form) { return; }
        const res = await this.act("reject", {
            applicant_id: form.applicant_id,
            reason_id: form.reason_id || false,
        });
        if (res) { this.state.rejecting = null; }
    }

    async markDone(interview) {
        await this.act("mark_done", { interview_id: interview.id });
    }

    async copyFeedbackLink(feedbackId) {
        const res = await this.act("copy_feedback_link",
                                   { feedback_id: feedbackId },
                                   { reload: false, silent: true });
        if (res && res.link) {
            // A STICKY NOTIFICATION AND NOT A CLIPBOARD WRITE. The clipboard
            // API is refused outside a secure context and in a cross-origin
            // frame, and a copy button that silently does nothing is worse
            // than a link somebody can see and select.
            this.notif.add(res.link, {
                type: "info", sticky: true, title: _t("Their own link"),
            });
        }
    }

    // ------------------------------------------------------------ the words
    /**
     * "1 role" and "3 roles", never "1 role(s)" (R46). Both words are passed
     * whole so the sentence can be translated as a sentence.
     */
    counted(n, one, many) { return n === 1 ? one : many; }

    daysWords(n) {
        if (!n) { return _t("opened today"); }
        if (n === 1) { return _t("open for a day"); }
        return _t("open for %s days", n);
    }

    money(amount, currency) {
        const n = Number(amount || 0);
        return `${n.toLocaleString()} ${currency || ""}`.trim();
    }
}

registry.category("actions").add("pb_hiring_board", PbHiringBoard);
