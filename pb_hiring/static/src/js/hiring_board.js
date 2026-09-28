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
import { Component, markup, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The four screening answers, in the order a screener weighs them. */
/** The four steps a role moves through, in order. A role is at exactly one
 *  (see `stageOf`), which is what lets the step counts add up. */
const JOURNEY_STAGES = [
    { key: "request", title: _t("Request & approve"), sub: _t("Agree the role and budget") },
    { key: "publish", title: _t("Prepare & publish"), sub: _t("Write the advert and open it") },
    { key: "recruit", title: _t("Meet your candidates"), sub: _t("Screen, interview and offer") },
    { key: "joined", title: _t("Welcome aboard"), sub: _t("A smooth first day") },
];

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

/**
 * A3 — THE PATH STRIP, which is the hero of the drawer.
 *
 * Six chips from "we have decided" to "they are here on Monday". Every one of
 * them is a state the SERVER computed and a door: a strip that only drew
 * progress would be a picture, and the thing a recruiter needs from this
 * screen is the next press.
 */
const PATH_ICON = {
    bgv: "shieldCheck",
    documents: "paperclip",
    offer: "scrollText",
    candidate: "user",
    signed: "stamp",
    day_one: "sunrise",
};

/** What each answer on a background-check line looks like. */
const BGV_ICON = {
    pending: "circle",
    ok: "checkCircle",
    flag: "alert",
    na: "minusCircle",
};

export class PbHiringBoard extends Component {
    static template = "pb_hiring.PbHiringBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        // A client action with no control panel names itself, or the trail
        // above anything it opens reads "Unnamed".
        if (!this.props.embedded && this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(_t("Hiring"));
        }
        this.screenOrder = SCREEN_ORDER;
        this.ivFocusKeys = IV_FOCUS;

        this.state = useState({
            loaded: false,
            journey: { stages: [], managers: [], users: [], currencies: [], company_sections: [] },
            journeyFocus: "all", drawerSection: "candidates", stageMove: null, messageForm: null,
            savingRequest: false,
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

            // ---- A3, the offer ----
            // The drawer's second half. `journey` is the path strip and the
            // three panels behind it, all computed on the server: a second
            // opinion written here about where a candidate has got to would
            // only ever disagree with the one that counts.
            offerRows: [],
            offerStates: [],
            bgvResults: [],
            offerKinds: [],
            offerPeriods: [],
            agencies: [],
            covering: [],
            openPanel: "",
            noting: null,
            overriding: null,
            lineForm: null,
            signing: null,
            letter: null,
            coverForm: null,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    screenIcon(tag) { return SCREEN_ICON[tag] || "circle"; }

    /** Two letters for a candidate's badge. A "DEMO " prefix is skipped so
     *  the example people read as people, not as "DS". */
    initials(name) {
        const words = String(name || "").replace(/^DEMO\s+/, "").trim()
            .split(/\s+/).filter(Boolean);
        return ((words[0] || "?")[0] + (words.length > 1
            ? words[words.length - 1][0] : "")).toUpperCase();
    }

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
            if (d.allowed) { this.state.journey = await this.orm.call("pb.hiring", "journey_options", []); }
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
                offerRows: d.offer_rows || [],
                offerStates: d.offer_states || [],
                bgvResults: d.bgv_results || [],
                offerKinds: d.offer_kinds || [],
                offerPeriods: d.offer_periods || [],
                agencies: d.agencies || [],
                covering: d.covering || [],
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
            const jf = this.state.journeyFocus;
            if (jf !== "all" && this.stageOf(r) !== jf) return false;
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

    // ================================================ the four steps
    //
    // A ROLE IS AT EXACTLY ONE STEP, so the step counts add up to the number
    // of live roles and clicking a step never shows a role that another step
    // also shows. The old strip filtered "open" twice ("open, not
    // advertised" AND "open"), which put the same role under two steps.
    //
    // A role that is open but not advertised is still "meeting candidates"
    // once somebody has applied or referrals are open: people are already
    // arriving, so preparing the advert is no longer where it is stuck.
    // Closed and refused roles are at no step; "Show all" still lists them.
    stageOf(r) {
        if (["draft", "submitted", "manager_ok", "hr_ok"].includes(r.state)) return "request";
        if (r.state === "open") {
            return (r.published || r.candidates || r.referral_open) ? "recruit" : "publish";
        }
        if (r.state === "filled") return "joined";
        return "";
    }

    get stages() {
        const rows = this.state.rows;
        return JOURNEY_STAGES.map((st, i) => {
            const at = rows.filter((r) => this.stageOf(r) === st.key);
            return {
                ...st,
                n: String(i + 1).padStart(2, "0"),
                count: at.length,
                countLabel: at.length === 1 ? _t("1 role") : _t("%s roles", at.length),
                waiting: at.filter((r) => r.waiting).length,
                mine: at.filter((r) => r.waiting_mine).length,
            };
        });
    }

    /* LEARN REFRESH step 5 — "Step 3 of 4" as ONE translatable sentence.
       It was built from two template words ("Step" + "of"), which Vietnamese
       read as "Bước 3 của 4"; one string lets it read "Bước 3/4". */
    stepOf(n, total) {
        return _t("Step %(n)s of %(total)s", { n, total });
    }

    /** The request wizard's four tab names, translatable (they were an array
     *  literal inside the template, which no extractor reads). */
    get requestSteps() {
        return [_t("The role"), _t("Responsibilities"), _t("Interview plan"), _t("Budget & review")];
    }

    stageMeta(r) {
        const key = this.stageOf(r);
        const index = JOURNEY_STAGES.findIndex((st) => st.key === key);
        if (index < 0) return null;
        return {
            index, total: JOURNEY_STAGES.length,
            title: JOURNEY_STAGES[index].title,
            marks: JOURNEY_STAGES.map((st, j) => (j < index ? "done" : j === index ? "here" : "")),
        };
    }

    get showingLine() {
        const shown = this.filtered.length;
        const all = this.state.rows.length;
        const st = JOURNEY_STAGES.find((x) => x.key === this.state.journeyFocus);
        if (!st && !this.anyFilter) {
            return { all: true, text: !all ? _t("no roles yet") : all === 1 ? _t("all 1 role") : _t("all %s roles", all) };
        }
        return { all: false, text: _t("%s of %s roles", shown, all), where: st ? st.title : "" };
    }

    showAll() {
        this.state.journeyFocus = "all";
        this.clearFilters();
    }

    // ================================================ quiet numbers
    //
    // One slim line instead of a wall of tiles. A number takes a colour only
    // when a person has to act on it; zero is grey. Every figure is still a
    // filter, exactly as the tiles were.
    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        return [
            { key: "open", n: k.open || 0, label: _t("Open roles"), tone: tone(k.open, "green"), run: () => this.toggleFocus("open") },
            { key: "waiting", n: k.waiting || 0, label: _t("Awaiting sign-off"), tone: tone(k.waiting, "amber"), run: () => this.toggleFocus("waiting") },
            { key: "mine", n: k.waiting_mine || 0, label: _t("Waiting on you"), tone: tone(k.waiting_mine, "amber"), run: () => this.toggleFocus("mine") },
            { key: "cand", n: k.candidates || 0, label: _t("Candidates"), tone: "", run: null },
            { key: "over", n: k.over_budget || 0, label: _t("Over budget"), tone: tone(k.over_budget, "rose"), run: () => this.toggleFocus("over") },
            { key: "iv", n: k.interviews_week || 0, label: _t("Interviews this week"), tone: "", run: () => { this.setTab("interviews"); this.toggleIvFocus("today"); } },
            { key: "late", n: k.feedback_late || 0, label: _t("Opinions late"), tone: tone(k.feedback_late, "rose"), run: () => { this.setTab("interviews"); this.toggleIvFocus("late"); } },
            { key: "offers", n: k.offers_out || 0, label: _t("Offers out"), tone: "", run: null },
            { key: "ref", n: k.referrals || 0, label: _t("Referrals this month"), tone: "", run: null },
            { key: "joined", n: k.filled_month || 0, label: _t("Joined this month"), tone: tone(k.filled_month, "green"), run: null },
        ];
    }

    pressGlance(item) {
        if (!item.run) return;
        this.state.journeyFocus = "all";
        item.run();
    }

    // ================================================ what happens next
    //
    // One sentence and, where the next move is this reader's, the one
    // button that makes it. Every button calls an action the role pop-up
    // already has; nothing here can do what the pop-up could not. Where the
    // next move belongs to somebody else the box says who, with no button.
    nextStep(r) {
        const s = this.state;
        if (r.waiting_mine) {
            return { text: _t("It is waiting for your sign-off"), label: _t("Review approval"), tone: "primary",
                     run: () => this.act("open_requisition", { requisition_id: r.id }, { reload: false }) };
        }
        if (r.state === "draft") {
            return s.canRaise
                ? { text: _t("Finish the request and send it for approval"), label: _t("Send for approval"), tone: "ghost",
                    run: () => this.act("submit", { requisition_id: r.id }) }
                : { text: _t("Still being written") };
        }
        if (["submitted", "manager_ok", "hr_ok"].includes(r.state)) {
            return { text: r.waiting ? _t("Waiting on %s", r.waiting) : _t("Waiting for a sign-off"), tone: "wait" };
        }
        if (r.state === "open") {
            if (!r.recruiter) {
                return s.canAdmin
                    ? { text: _t("Nobody is recruiting it yet"), label: _t("Hiring rules"), tone: "ghost",
                        run: () => this.act("open_rules", {}, { reload: false }) }
                    : { text: _t("Nobody is recruiting it yet"), tone: "wait" };
            }
            if (this.stageOf(r) === "publish") {
                if (!s.canRecruit) return { text: _t("The advert is being prepared") };
                return r.jd_state === "approved"
                    ? { text: _t("The advert is agreed. Put it on the careers page"), label: _t("Advertise it"), tone: "ghost",
                        run: () => this.act("publish", { requisition_id: r.id }) }
                    : { text: _t("Write the advert candidates will read"), label: _t("Write the advert"), tone: "ghost",
                        run: () => this.openAt(r.id, "jd") };
            }
            if (!r.candidates) {
                return (s.canRecruit && !r.referral_open)
                    ? { text: _t("Nobody has applied yet. Let colleagues refer people"), label: _t("Open to referrals"), tone: "ghost",
                        run: () => this.act("toggle_referrals", { requisition_id: r.id }) }
                    : { text: _t("Waiting for the first applicant") };
            }
            return { text: r.candidates === 1 ? _t("1 candidate to look at") : _t("%s candidates to look at", r.candidates),
                     label: _t("Review candidates"), tone: "ghost", run: () => this.openAt(r.id, "candidates") };
        }
        if (r.state === "filled") return { text: _t("Filled. Joining carries on under New joiners"), tone: "done" };
        if (r.state === "refused") return { text: _t("Not approved") };
        return { text: _t("Closed") };
    }

    async openAt(id, section) {
        await this.openDrawer(id);
        if (this.state.drawer) this.state.drawerSection = section;
    }

    async runNext(ev, row) {
        ev.stopPropagation();
        const step = this.nextStep(row);
        if (step.run) await step.run();
    }

    funnelLabel(pl) { return pl.name; }

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
        const changedRole = this.state.drawer?.id !== id;
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call(
                "pb.hiring", "get_requisition", [id]);
            if (changedRole) this.state.drawerSection = this.state.drawer.state === "open" ? "candidates" : "request";
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
        this.state.openPanel = "";
        this.state.lineForm = null;
        this.state.noting = null;
        this.state.overriding = null;
        this.state.signing = null;
        this.state.letter = null;
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
            country_id: "", target_close_date: "", requirements: "",
            step: 0, role_level: "", reporting_manager_id: "", currency_id: this.state.journey.currency_id,
            assignment: false, jd_file: "", jd_filename: "", assignment_file: "", assignment_filename: "",
            interviews: [1,2,3].map(() => ({ owner_id: "", focus: "" })),
        };
    }

    validateRequestStep() {
        const f = this.state.raising;
        let warning = "";
        if (!f.title.trim() || !f.department_id || !f.country_id) warning = "Add the role title, department and country.";
        else if (f.step >= 1 && (!f.reporting_manager_id || !f.role_level.trim() || (!f.requirements.trim() && !f.jd_file))) warning = "Add the reporting manager, role level and a role description or JD attachment.";
        else if (f.step >= 2 && f.interviews.some(r => !r.owner_id || !r.focus.trim())) warning = "Choose an interviewer and focus for each discussion.";
        else if (f.step >= 3 && (!f.target_close_date || !f.currency_id || Number(f.budget_cost) <= 0)) warning = "Add a target closing date and a positive annual budget with its currency.";
        if (warning) { this.notif.add(warning, {type: "warning"}); return false; }
        return true;
    }
    nextRequestStep() { if (this.validateRequestStep()) this.state.raising.step++; }
    async requestUpload(event, kind) {
        const file = event.target.files[0];
        if (!file) return;
        if (file.size > 10 * 1024 * 1024 || !/\.(pdf|docx?)$/i.test(file.name)) {
            this.notif.add("Use a PDF or Word document smaller than 10 MB.", {type: "warning"}); event.target.value = ""; return;
        }
        const data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(",")[1]); reader.onerror = reject; reader.readAsDataURL(file); });
        this.state.raising[kind + "_file"] = data;
        this.state.raising[kind + "_filename"] = file.name;
    }
    chooseJourney(key) { this.state.journeyFocus = this.state.journeyFocus === key ? "all" : key; this.state.focus = ""; this.state.tab = "roles"; }
    startStageMove(candidate) { this.state.stageMove = {applicant_id: candidate.id, name: candidate.name, stage_id: "", reason: "", update_date: ""}; }
    async saveStageMove() { const res = await this.act("journey_stage", {...this.state.stageMove}); if (res) this.state.stageMove = null; }
    startMessage(candidate) { this.state.messageForm = {applicant_id: candidate.id, name: candidate.name, key: "phone", values: {}, preview: null, busy: false}; }
    get messageFields() {
        return this.state.journey.message_fields?.[this.state.messageForm?.key] || [];
    }
    async previewMessage() {
        const f = this.state.messageForm;
        f.preview = await this.act("message_preview", {applicant_id: f.applicant_id, key: f.key, values: {...f.values}}, {reload: false, silent: true});
    }
    async sendMessage() {
        const f = this.state.messageForm;
        if (f.busy) return; f.busy = true;
        const result = await this.act("message_send", {applicant_id: f.applicant_id, key: f.key, values: {...f.values}}, {reload: false});
        f.busy = false; if (result) this.state.messageForm = null;
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
        if (this.state.savingRequest || !this.validateRequestStep()) return;
        this.state.savingRequest = true;
        const res = await this.act("create", { ...form });
        this.state.savingRequest = false;
        if (res) {
            this.state.raising = null;
            if (res.id) { await this.openDrawer(res.id); }
        }
    }

    // ---------------------------------------------------------- the advert
    startJd() {
        const d = this.state.drawer;
        this.state.writingJd = { title: d ? d.title : "", summary: "", body: "", sections: {role: "", duties: "", must: "", nice: "", process: ""} };
    }

    cancelJd() { this.state.writingJd = null; }

    async saveJd() {
        const d = this.state.drawer;
        const form = this.state.writingJd;
        if (!d) { return; }
        const res = await this.act("new_jd", {
            requisition_id: d.id, title: form.title,
            summary: form.summary, body: form.body, sections: {...form.sections},
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

    // =====================================================================
    //  A3 — from "we have decided" to "they are here on Monday"
    // =====================================================================
    pathIcon(key) { return PATH_ICON[key] || "circle"; }

    bgvIcon(result) { return BGV_ICON[result] || "circle"; }

    get journey() {
        const d = this.state.drawer;
        return (d && d.journey) || {};
    }

    get offer() {
        return this.journey.offer || {};
    }

    /** One panel open at a time: three stacked accordions is a drawer nobody
     *  can find the bottom of. Pressing the open one closes it. */
    togglePanel(key) {
        this.state.openPanel = this.state.openPanel === key ? "" : key;
    }

    /** Pressing a chip on the path strip opens the panel behind it, and the
     *  two that are not panels open the record instead. */
    async pressChip(chip) {
        if (chip.key === "day_one" && this.offer.employee_id) {
            await this.act("open_employee", { offer_id: this.offer.id },
                           { reload: false });
            return;
        }
        if (chip.key === "signed" && this.offer.id) {
            this.togglePanel("offer");
            return;
        }
        this.togglePanel(chip.key === "candidate" ? "offer" : chip.key);
    }

    // ------------------------------------------------- the background check
    async startBgv() {
        const d = this.state.drawer;
        if (!d) { return; }
        await this.act("open_bgv", { requisition_id: d.id });
        this.state.openPanel = "bgv";
    }

    async setBgv(item, result) {
        await this.act("set_bgv_item", { item_id: item.id, result,
                                         note: item.note || "" });
    }

    startNote(item) {
        this.state.noting = { item_id: item.id, name: item.name,
                              result: item.result, note: item.note || "" };
    }

    cancelNote() { this.state.noting = null; }

    async saveNote() {
        const form = this.state.noting;
        if (!form) { return; }
        const res = await this.act("set_bgv_item", {
            item_id: form.item_id, result: form.result, note: form.note,
        });
        if (res) { this.state.noting = null; }
    }

    startOverride() {
        const bgv = this.journey.bgv || {};
        this.state.overriding = { bgv_id: bgv.id, note: "" };
    }

    cancelOverride() { this.state.overriding = null; }

    async saveOverride() {
        const form = this.state.overriding;
        if (!form) { return; }
        if (!form.note.trim()) {
            this.notif.add(
                _t("Say why we are going ahead. In a year this sentence is the only thing that will explain the decision."),
                { type: "warning" });
            return;
        }
        const res = await this.act("bgv_override", { ...form });
        if (res) { this.state.overriding = null; }
    }

    // ------------------------------------------------------- the documents
    async askForDocuments() {
        const offer = this.offer;
        if (!offer.id) { return; }
        await this.act("request_documents", { offer_id: offer.id });
        this.state.openPanel = "documents";
    }

    async remindDocuments() {
        await this.act("remind_documents", { offer_id: this.offer.id });
    }

    async copyDocLink() {
        const res = await this.act("copy_doc_link", { offer_id: this.offer.id },
                                   { reload: false, silent: true });
        if (res && res.link) {
            // A STICKY NOTIFICATION AND NOT A CLIPBOARD WRITE: the clipboard
            // API is refused outside a secure context and in a cross-origin
            // frame, and a copy button that silently does nothing is worse
            // than a link somebody can see and select.
            this.notif.add(res.link, { type: "info", sticky: true,
                                       title: _t("Their own link") });
        }
    }

    // ------------------------------------------------------------ the offer
    async draftOffer() {
        const d = this.state.drawer;
        if (!d) { return; }
        const res = await this.act("draft_offer", { requisition_id: d.id });
        if (res) { this.state.openPanel = "offer"; }
    }

    startLine(line) {
        this.state.lineForm = line
            ? { line_id: line.id, name: line.name, kind: line.kind,
                amount: line.amount, period: line.period, note: line.note }
            : { line_id: 0, name: "", kind: "earning", amount: 0,
                period: "monthly", note: "" };
    }

    cancelLine() { this.state.lineForm = null; }

    async saveLine() {
        const form = this.state.lineForm;
        if (!form) { return; }
        if (!form.name.trim()) {
            this.notif.add(
                _t("Say what the line is. A number on its own is a number nobody can check."),
                { type: "warning" });
            return;
        }
        const res = await this.act("offer_line", {
            offer_id: this.offer.id, ...form,
            amount: Number(form.amount) || 0,
        });
        if (res) { this.state.lineForm = null; }
    }

    async removeLine(line) {
        await this.act("offer_line", { offer_id: this.offer.id,
                                       line_id: line.id, remove: true });
    }

    async setOfferField(field, value) {
        await this.act("offer_set", { offer_id: this.offer.id,
                                      [field]: value });
    }

    async previewLetter() {
        const res = await this.act("offer_letter", { offer_id: this.offer.id },
                                   { reload: false, silent: true });
        if (res) {
            this.state.letter = { html: markup(res.html || ""),
                                  id: this.offer.id };
        }
    }

    closeLetter() { this.state.letter = null; }

    async submitOffer() {
        await this.act("submit_offer", { offer_id: this.offer.id });
    }

    async sendOffer(force = false) {
        await this.act("send_offer", { offer_id: this.offer.id, force });
    }

    async openLetterPdf() {
        await this.act("open_letter", { offer_id: this.offer.id },
                       { reload: false });
    }

    async copyOfferLink() {
        const res = await this.act("copy_offer_link",
                                   { offer_id: this.offer.id },
                                   { reload: false, silent: true });
        if (res && res.link) {
            this.notif.add(res.link, { type: "info", sticky: true,
                                       title: _t("Their own link") });
        }
    }

    // ------------------------------------------------------------- signing
    startSigning() {
        this.state.signing = { filename: "", data: "", mimetype: "",
                               signed_on: "" };
    }

    cancelSigning() { this.state.signing = null; }

    /**
     * The signed copy, read in the browser and sent as base64.
     *
     * A FILE INPUT AND NOT A DROP ZONE: this is pressed once per hire, by
     * somebody who has the file open in another window, and a drop zone is a
     * bigger target for a smaller need.
     */
    onSignedFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file || !this.state.signing) { return; }
        if (file.size > 5 * 1024 * 1024) {
            this.notif.add(
                _t("That file is bigger than 5 MB. A scan of a signed letter is usually well under that."),
                { type: "warning" });
            ev.target.value = "";
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const raw = String(reader.result || "");
            this.state.signing.data = raw.slice(raw.indexOf(",") + 1);
            this.state.signing.filename = file.name;
            this.state.signing.mimetype = file.type;
        };
        reader.readAsDataURL(file);
    }

    async saveSigning() {
        const form = this.state.signing;
        if (!form) { return; }
        if (!form.data) {
            this.notif.add(
                _t("Attach the copy they signed. Recording a signature with nothing behind it is the one thing this screen must never let anybody do."),
                { type: "warning" });
            return;
        }
        const res = await this.act("record_signed", {
            offer_id: this.offer.id, ...form,
        });
        if (res) { this.state.signing = null; }
    }

    async closeOffer() {
        await this.act("close_offer", { offer_id: this.offer.id });
    }

    // ----------------------------------------------------------- the agency
    async setAgency(vendorId) {
        const d = this.state.drawer;
        if (!d) { return; }
        await this.act("set_agency", { requisition_id: d.id,
                                       vendor_id: Number(vendorId) || 0 });
    }

    // ------------------------------------------------------------ the cover
    startCover() {
        const today = new Date();
        const back = new Date();
        back.setDate(back.getDate() + 14);
        const pad = (n) => String(n).padStart(2, "0");
        const iso = (w) => `${w.getFullYear()}-${pad(w.getMonth() + 1)}-`
            + `${pad(w.getDate())}`;
        this.state.coverForm = { cover_user_id: "", date_from: iso(today),
                                 date_to: iso(back), reason: "" };
    }

    cancelCover() { this.state.coverForm = null; }

    async saveCover() {
        const form = this.state.coverForm;
        if (!form) { return; }
        if (!form.cover_user_id) {
            this.notif.add(_t("Say who is standing in."), { type: "warning" });
            return;
        }
        if (!form.reason.trim()) {
            this.notif.add(
                _t("Say why. A cover request with no reason is one nobody can agree to in good conscience."),
                { type: "warning" });
            return;
        }
        const res = await this.act("request_cover", { ...form });
        if (res) { this.state.coverForm = null; }
    }

    async openCovers() {
        await this.act("open_covers", {}, { reload: false });
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
