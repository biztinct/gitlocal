/** @odoo-module **/
/**
 * New Hire Studio (NEWHIRE P1) — the client action `pb_new_hire_studio`.
 *
 * Three columns, as the design of record: the seven steps with live status on
 * the left, the one question being answered in the centre, "The record so
 * far" on the right. The shell mechanics are the Workforce setup studio's
 * (one `load()`, sequence-guarded replies, the `api` object handed to every
 * step, the step in the URL — WS4 — and the studio's own toast).
 *
 * The difference: NOTHING is saved before Send. The hire lives in ONE
 * reactive `draft` in this component; step status is worked out here from it
 * (the design's rules); every server reply that depends on it — what the team
 * decides, the usual answers, the pay hint, "already an employee?" — is asked
 * again when its inputs change, and a late reply never wins. The draft is
 * mirrored to sessionStorage (per company and user) so an accidental reload
 * keeps it; it is cleared on a successful Send and on "Add another person".
 */
import { Component, onMounted, onWillStart, onWillUnmount, useExternalListener, useRef, useState, useEffect } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { router } from "@web/core/browser/router";
import { useSetupAction } from "@web/search/action_hook";
import { HubBackChip, hubBack, goBack } from "@pb_hub/js/hub_nav";
import { MODEL, ACTION_XMLID, icon, errorText, isAccessError, firstName, fmtDay, money, deepClone,
         weekNameOf, siteNameOf, ownMissingOf, docGapsOf, docTallyOf, docItemsOf, docChoiceOf } from "./studio_util";
import { StepWho } from "./step_who";
import { StepRole } from "./step_role";
import { StepPay } from "./step_pay";
import { StepSoon } from "./step_soon";
import { StepSched } from "./step_sched";
import { StepWelcome } from "./step_welcome";
import { StepDocs } from "./step_docs";
import { StepCheck } from "./step_check";
import { RecordPanel } from "./record_panel";

const STEP_KEYS = ["who", "role", "pay", "sched", "docs", "welcome", "check"];
const SOON = [];
const TOAST_MS = 7000;
const EMPLOYEES = { label: _t("People"), xmlid: "pb_people_hub.action_pb_people_hub", lens: "employees", context: {} };
const JOINERS_XMLID = "pb_onboarding.action_pb_onboarding_board";
const SETUP_XMLID = "pb_workforce_setup.action_setup_studio";

/**
 * P2: every draft key added since P1, declared ONCE — its blank value and how
 * it is sent (`null` = kept on the screen only). The server lists the same
 * keys in `DRAFT_KEYS` (studio.py); one table per language is as far as a
 * single declaration goes.
 */
const P2_KEYS = {
    type_id: [false, (d) => d.type_id || false],
    week_id: [false, (d) => d.week_id || false],
    late_group: ["worker", (d) => d.late_group || "worker"],
    clock_on: [false, (d) => Boolean(d.clock_on)],
    clock_code: ["", (d) => (d.clock_on ? String(d.clock_code || "").trim() : "")],
    login_mode: ["", (d) => d.login_mode || ""],
    buddy_id: [false, (d) => (d.open_case !== false ? d.buddy_id || false : false)],
    buddy_name: ["", null],
    equipment: [null, (d) => (d.open_case !== false && Array.isArray(d.equipment) ? [...d.equipment] : null)],
    letter: [true, (d) => d.letter !== false],
    open_case: [true, (d) => d.open_case !== false],
    own: [{}, (d) => ({ ...(d.own || {}) })],
    // P3a — step 5: the answer per item, what was typed, and the names and
    // dates of the files (their content lives in `nh.files`, memory only)
    items: [{}, (d) => ({ ...(d.items || {}) })],
    have: [{}, (d) => ({ ...(d.have || {}) })],
    file_meta: [{}, null],
    // P3b — step 5's reminders switch
    remind: [true, (d) => d.remind !== false],
};
/** Changing one of these re-builds step 6's options and its timeline. */
const WELCOME_INPUTS = ["name", "date_start", "work_email", "personal", "department_id", "payroll_country", "parent_id",
    "country_id", "contract_kind", "trial_on", "clock_on", "clock_code", "login_mode", "buddy_id",
    "equipment", "open_case"];

function stepList() {
    return [
        { key: "who", n: 1, req: true, title: _t("Who is joining"), next: _t("Next: role and place") },
        { key: "role", n: 2, req: true, title: _t("Role and place"), next: _t("Next: contract and pay") },
        { key: "pay", n: 3, req: true, title: _t("Contract and pay"), next: _t("Next: schedule and time off") },
        { key: "sched", n: 4, title: _t("Schedule and time off"), next: _t("Next: details and documents") },
        { key: "docs", n: 5, title: _t("Details and documents"), next: _t("Next: welcome and first day") },
        { key: "welcome", n: 6, title: _t("Welcome and first day"), next: _t("Next: check and add") },
        { key: "check", n: 7, title: _t("Check and add"), next: "" },
    ];
}

function blankDraft(today) {
    return {
        name: "", date_start: today || "", work_email: "", personal: "",
        department_id: false, job_id: false, job_title: "", newJob: false,
        payroll_country: "", parent_id: false, parent_name: "", work_location_id: false,
        country_id: false, wage: null, contract_kind: "permanent", date_end: "", trial_on: true,
        usual: {}, pb_scale_pin_reason: "", fill_job_id: false,
        ...Object.fromEntries(Object.entries(P2_KEYS).map(([k, [blank]]) => [k, deepClone(blank)])),
    };
}

export class NewHireStudio extends Component {
    static template = "pb_new_hire.Studio";
    static components = { HubBackChip, StepWho, StepRole, StepPay, StepSoon, StepSched, StepDocs, StepWelcome, StepCheck, RecordPanel };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.icon = icon;
        this.root = useRef("root");
        this.steps = stepList();
        this.back = hubBack(this.props);
        const asked = this.initialStep();
        this.nh = useState({
            loading: true, error: "", denied: "", data: null,
            step: asked || "who", moving: false,
            draft: blankDraft(""),
            auto: {},           // field -> true while it holds the team's suggestion
            touched: {},        // field -> true once the person chose it (never overwritten)
            seen: { who: true },
            fieldErr: {},       // field -> sentence (from Send, or a quick check)
            decides: null, decidesBusy: false,
            teamScheme: null,
            usual: { configId: 0, rows: null, busy: false },
            hint: null,
            dup: null,
            cats: null,         // step 3: contract categories
            sched: null,        // step 4: schedule_options()
            clockCheck: null,   // step 4: check_clock()
            welcome: null,      // step 6: welcome_options() (and its timeline)
            docs: null,         // step 5: details_options()
            files: {},          // step 5: {item key: {name, mime, size, data}} — memory only
            sending: false, result: null, refusal: null,
            dialog: null, toast: null,
        });
        this.seq = {};
        this.timers = {};
        const studio = this;
        this.api = {
            get nh() { return studio.nh; },
            set: (key, value, opts) => this.set(key, value, opts),
            patch: (values, opts) => this.patch(values, opts),
            go: (key, field) => this.go(key, field),
            next: () => this.next(),
            pickTeam: (id) => this.pickTeam(id),
            setUsual: (code, amount) => this.setUsual(code, amount),
            resetUsual: (code) => this.resetUsual(code),
            findPeople: (q) => this.orm.call(MODEL, "find_people", [q, 20]),
            findBuddies: (q) => this.orm.call(MODEL, "find_buddies", [q, 12]),
            setOwn: (name, value) => this.setOwn(name, value),
            initEquipment: () => this.initEquipment(),
            openWorkforceSetup: () => this.openWorkforceSetup(),
            seeJoiners: () => this.seeJoiners(),
            orm: this.orm,
            // P3b — the welcome link of an added person
            inviteCard: (employeeId) => this.orm.call("pb.new.hire.invite", "card", [employeeId]),
            copyLink: (employeeId) => this.orm.call("pb.new.hire.invite", "copy_link", [employeeId]),
            setChoice: (key, choice) => this.setChoices({ [key]: choice }),
            setChoices: (map) => this.setChoices(map),
            setHave: (name, value) => this.setHave(name, value),
            setFile: (key, file) => this.setFile(key, file),
            setFileDate: (key, which, value) => this.setFileDate(key, which, value),
            refreshDocs: () => this.refreshDocs(),
            refreshDecides: () => this.refreshDecides(),
            send: () => this.send(),
            withdraw: () => this.withdraw(),
            again: () => this.again(),
            openRecord: () => this.openRecord(),
            backToEmployees: () => this.backToEmployees(),
            toast: (msg, opts) => this.toast(msg, opts),
            status: (key) => this.status(key),
            stepMeta: (key) => this.steps.find((s) => s.key === key),
            get ready() { return studio.ready; },
            get sendable() { return studio.sendable; },
            get currency() { return studio.currency; },
            get first() { return studio.first; },
            get teamName() { return studio.teamName; },
            get jobName() { return studio.jobName; },
            get countryName() { return studio.countryName; },
            get scaleFound() { return studio.scaleFound; },
            get sendFiles() { return studio.sendFiles; },
        };
        if (asked) {
            this.props.updateActionState?.({ step: this.nh.step });
        }
        useSetupAction({ beforeLeave: (opts) => this.beforeLeave(opts) });
        onWillStart(() => this.load());
        onMounted(() => this.askPrefill());

        useExternalListener(window, "keydown", (ev) => this.onKey(ev), { capture: true });
        // first run (mount): the first empty field; after that, on every step
        // change, the new question's heading
        useEffect(() => {
            this.focusHeading(Boolean(this.mounted));
            this.mounted = true;
        }, () => [this.nh.step, !!this.nh.result]);
        // the leave dialog: focus "Stay here", the safe answer
        useEffect((open) => {
            if (open) {
                this.root.el?.querySelector(".pbnh-dlg .pbnh-btn--pri")?.focus();
            }
        }, () => [!!this.nh.dialog]);
        onWillUnmount(() => {
            Object.values(this.timers).forEach((t) => clearTimeout(t));
            clearTimeout(this.toastTimer);
        });
    }

    // ------------------------------------------------------------ the URL
    initialStep() {
        const cur = router.current || {};
        const mine = [this.props.action?.id, this.props.action?.xml_id, this.props.action?.path, ACTION_XMLID]
            .filter(Boolean).map(String);
        if (cur.step && STEP_KEYS.includes(cur.step) && mine.includes(String(cur.action))) {
            return cur.step;
        }
        const ctx = this.props.action?.context || {};
        return STEP_KEYS.includes(ctx.pb_nh_step) ? ctx.pb_nh_step : null;
    }

    get prefill() {
        const a = this.props.action || {};
        return (a.params && a.params.prefill) || (a.context && a.context.pb_nh_prefill) || null;
    }

    // ------------------------------------------------------------ storage
    get storeKey() {
        const d = this.nh.data;
        return d ? `pb_nh_draft:${d.company.id}:${d.user.id}` : "";
    }
    persist() {
        if (!this.storeKey || this.nh.result) {
            return;
        }
        try {
            const nh = this.nh;
            sessionStorage.setItem(this.storeKey, JSON.stringify({
                draft: nh.draft, auto: nh.auto, touched: nh.touched, seen: nh.seen, step: nh.step,
            }));
        } catch {
            // private window or blocked storage: the draft simply lives in memory
        }
    }
    readStore() {
        try {
            const raw = sessionStorage.getItem(this.storeKey);
            return raw ? JSON.parse(raw) : null;
        } catch {
            return null;
        }
    }
    clearStore() {
        try {
            sessionStorage.removeItem(this.storeKey);
        } catch {
            // nothing kept, nothing to clear
        }
    }

    // ------------------------------------------------------------ data
    async load() {
        const nh = this.nh;
        nh.loading = true;
        nh.error = "";
        nh.denied = "";
        try {
            const data = await this.orm.call(MODEL, "load", [this.prefill || false]);
            nh.data = data;
            let draft = Object.assign(blankDraft(data.today), data.draft || {});
            let kept = this.readStore();
            if (this.prefill && kept && kept.draft && String(kept.draft.name || "").trim()) {
                // P2 (fix c): an unsent hire is never replaced without asking.
                // Carry on is the safe answer, so the kept hire shows first;
                // the question is asked once the screen is up (onMounted).
                this.prefillChoice = { data: deepClone(data.draft || {}), name: String(kept.draft.name).trim(),
                                       role: this.prefillRole(data) };
                draft = blankDraft(data.today);
                data.draft = { date_start: data.today, payroll_country: (data.draft || {}).payroll_country || "" };
            } else if (this.prefill) {
                kept = null;
                this.clearStore();
            }
            if (kept && kept.draft && kept.draft.name !== undefined) {
                Object.assign(draft, kept.draft);
                nh.auto = kept.auto || {};
                nh.touched = kept.touched || {};
                nh.seen = kept.seen || { who: true };
                if (!this.initialStep() && STEP_KEYS.includes(kept.step)) {
                    nh.step = kept.step;
                    this.props.updateActionState?.({ step: nh.step });
                }
                if (draft.name && !this.prefillChoice) {
                    this.toast(_t("Your unsent hire was kept, so you can carry on where you left off."), {
                        kind: "info",
                        action: { label: _t("Start again"), run: () => this.again(true) },
                    });
                }
            }
            nh.draft = draft;
            if (!kept) {
                // what the org chart sent is the person's choice, never overwritten
                for (const k of ["department_id", "job_id", "job_title", "parent_id"]) {
                    if ((data.draft || {})[k]) {
                        nh.touched[k] = true;
                    }
                }
            }
            if (!nh.step || nh.step === "who") {
                this.focusAfter = draft.name ? null : "name";
            }
            if (draft.department_id && !kept) {
                // the org chart sent a team: suggest from it as a pick would
                await this.pickTeam(draft.department_id, { initial: true });
            } else {
                this.refreshAll();
            }
            this.refreshCats();
            this.refreshSched();
            this.checkClock();
            this.refreshDocs();
        } catch (e) {
            if (isAccessError(e)) {
                nh.denied = errorText(e);
            } else {
                nh.error = errorText(e);
            }
        } finally {
            nh.loading = false;
        }
    }

    retry() {
        this.nh.data = null;
        this.load();
    }

    /** Ask the server again, and let only the newest reply land. */
    async ask(key, method, args, apply) {
        const seq = (this.seq[key] = (this.seq[key] || 0) + 1);
        try {
            const res = await this.orm.silent.call(MODEL, method, args);
            if (seq === this.seq[key]) {
                apply(res);
            }
        } catch (e) {
            if (seq === this.seq[key]) {
                apply(null, e);
            }
        }
    }
    later(key, ms, fn) {
        clearTimeout(this.timers[key]);
        this.timers[key] = setTimeout(fn, ms);
    }

    refreshAll() {
        this.refreshDecides();
        this.refreshHint();
        this.checkPerson();
        this.refreshWelcome();
    }

    /** P2 (fix c): the org chart sent a new role while an unsent hire was
     *  kept. Ask; "Carry on" (the safe answer, Esc) keeps what is there. */
    async askPrefill() {
        const choice = this.prefillChoice;
        if (!choice) {
            return;
        }
        this.prefillChoice = null;
        const start = await this.ask_({
            title: _t("Carry on with %s?", choice.name),
            body: _t("You have an unsent hire for %(name)s. Carry on with it, or start %(role)s from the org chart instead.",
                     { name: choice.name, role: choice.role }),
            ok: _t("Start %s", choice.role),
            cancel: _t("Carry on with %s", choice.name),
        });
        if (!start) {
            return;
        }
        const nh = this.nh;
        this.clearStore();
        nh.auto = {};
        nh.touched = {};
        nh.seen = { who: true };
        nh.fieldErr = {};
        nh.decides = null;
        nh.usual = { configId: 0, rows: null, busy: false };
        nh.draft = Object.assign(blankDraft(nh.data.today), choice.data);
        for (const k of ["department_id", "job_id", "job_title", "parent_id"]) {
            if (choice.data[k]) {
                nh.touched[k] = true;
            }
        }
        nh.data.draft = choice.data;
        if (nh.step !== "who") {
            this.go("who", "name");
        } else {
            this.focusAfter = "name";
            this.focusHeading(false);
        }
        if (nh.draft.department_id) {
            await this.pickTeam(nh.draft.department_id, { initial: true });
        } else {
            this.refreshAll();
        }
        this.refreshCats();
        this.refreshSched();
        this.refreshDocs();
    }

    /** The org chart's role, in words, for the "carry on?" question. */
    prefillRole(data) {
        const pre = this.prefill || {};
        const job = (data.jobs || []).find((j) => j.id === pre.job_id);
        const team = (data.teams || []).find((t) => t.id === pre.department_id);
        return (job && job.name) || pre.job_title || (team && team.name) || _t("the new role");
    }

    // ------------------------------------------------------------ P2: steps 3, 4, 6
    refreshCats() {
        const d = this.nh.draft;
        if (!d.payroll_country) {
            this.nh.cats = null;
            return;
        }
        return this.ask("cats", "contract_categories", [d.payroll_country, d.contract_kind], (rows) => {
            const cats = rows || [];
            this.nh.cats = cats;
            if (!this.nh.touched.type_id || !cats.some((c) => c.id === this.nh.draft.type_id)) {
                const pick = cats.length === 1 ? cats[0] : cats.find((c) => c.suggested);
                this.patch({ type_id: pick ? pick.id : false }, { auto: true });
            }
        });
    }

    refreshSched() {
        const d = this.nh.draft;
        return this.ask("sched", "schedule_options", [d.department_id || false, d.payroll_country || false,
                                                       d.date_start || false, d.name || ""], (res) => {
            if (!res) {
                return;
            }
            const nh = this.nh;
            nh.sched = res;
            const take = {};
            const weeks = res.weeks || [];
            if (!nh.touched.week_id || !weeks.some((w) => w.id === nh.draft.week_id)) {
                const team = weeks.find((w) => w.team_default);
                take.week_id = team ? team.id : false;
            }
            if (!nh.touched.clock_on) {
                take.clock_on = Boolean(res.clock && res.clock_usual);
            }
            this.patch(take, { auto: true });
        });
    }

    refreshWelcome() {
        this.later("welcome", 120, () => {
            const d = this.nh.draft;
            if (!d.department_id && !d.payroll_country) {
                return;
            }
            // a sign-in the screen picked by itself is re-picked by the server
            // (a work email typed later makes the invitation the default)
            const draft = { ...this.sendDraft, login_mode: this.nh.touched.login_mode ? d.login_mode : "" };
            return this.ask("welcome", "welcome_options", [draft], (res) => {
                if (!res) {
                    return;
                }
                const nh = this.nh;
                nh.welcome = res;
                const chosen = res.login && res.login.chosen;
                if (chosen && chosen !== nh.draft.login_mode
                        && (!nh.touched.login_mode || !res.login.modes.some((m) => m.key === nh.draft.login_mode && m.available))) {
                    this.patch({ login_mode: chosen }, { auto: true });
                }
                if (res.letter && !res.letter.available && nh.draft.letter !== false && !nh.touched.letter) {
                    nh.draft.letter = true;   // shown off, sent as "not available" by the server
                }
            });
        });
    }

    /** P3a: step 5's list for the country of work. */
    refreshDocs() {
        const d = this.nh.draft;
        if (!d.payroll_country) {
            this.nh.docs = null;
            return;
        }
        this.later("docs", 150, () => this.ask("docs", "details_options",
            [{ payroll_country: d.payroll_country, name: d.name || "" }], (res) => {
                if (res) {
                    this.nh.docs = res;
                }
            }));
    }
    setChoices(map) {
        const items = { ...(this.nh.draft.items || {}) };
        for (const [key, choice] of Object.entries(map)) {
            items[key] = choice;
            delete this.nh.fieldErr[`doc-${key}`];
        }
        this.patch({ items });
    }
    setHave(name, value) {
        const have = { ...(this.nh.draft.have || {}) };
        if (value === "" || value === null || value === undefined) {
            delete have[name];
        } else {
            have[name] = value;
        }
        delete this.nh.fieldErr[`have-${name}`];
        this.patch({ have });
    }
    setFile(key, file) {
        const nh = this.nh;
        const meta = { ...(nh.draft.file_meta || {}) };
        if (file) {
            nh.files[key] = file;
            meta[key] = { ...(meta[key] || {}), name: file.name, size: file.size };
        } else {
            // the dates typed for the paper stay; only the file goes
            delete nh.files[key];
            const { name, size, ...dates } = meta[key] || {};
            meta[key] = dates;
        }
        delete nh.fieldErr[`file-${key}`];
        this.patch({ file_meta: meta });
    }
    setFileDate(key, which, value) {
        const meta = { ...(this.nh.draft.file_meta || {}) };
        meta[key] = { ...(meta[key] || {}), [which]: value || "" };
        delete this.nh.fieldErr[`file-${key}`];
        this.patch({ file_meta: meta });
    }
    /** The files of rows answered "I have it", as `send` takes them. */
    get sendFiles() {
        const nh = this.nh;
        const out = [];
        for (const item of docItemsOf(nh)) {
            const f = nh.files[item.key];
            if (!item.upload || !f || docChoiceOf(nh, item) !== "have") {
                continue;
            }
            const meta = (nh.draft.file_meta || {})[item.key] || {};
            out.push({ key: item.key, name: f.name, mime: f.mime, data: f.data,
                       issue_date: meta.issue_date || false, expiry_date: meta.expiry_date || false });
        }
        return out;
    }
    get docGaps() { return docGapsOf(this.nh); }

    checkClock() {
        const d = this.nh.draft;
        const code = String(d.clock_code || "").trim();
        if (!d.clock_on || !code) {
            this.nh.clockCheck = null;
            return;
        }
        this.later("clock", 350, () => this.ask("clock", "check_clock", [code], (res) => {
            this.nh.clockCheck = res || null;
        }));
    }

    /** The first time step 6 shows, the chips stand for what will be asked:
     *  the categories every joiner gets. */
    initEquipment() {
        const nh = this.nh;
        if (nh.step !== "welcome" || nh.draft.equipment !== null || !nh.welcome) {
            return;
        }
        const usual = (nh.welcome.equipment || []).filter((c) => c.usual).map((c) => c.id);
        this.patch({ equipment: usual }, { auto: true });
    }

    setOwn(name, value) {
        const own = { ...(this.nh.draft.own || {}) };
        if (value === "" || value === null || value === undefined) {
            delete own[name];
        } else {
            own[name] = value;
        }
        delete this.nh.fieldErr[`own-${name}`];
        this.patch({ own });
    }

    /** Required own fields of this country still empty (they block Send). */
    get ownMissing() { return ownMissingOf(this.nh); }
    get weekName() { return weekNameOf(this.nh); }
    async openWorkforceSetup() {
        try {
            await this.action.doAction(SETUP_XMLID);
        } catch (e) {
            this.toast(errorText(e), { kind: "error" });
        }
    }
    async seeJoiners() {
        try {
            await this.action.doAction(JOINERS_XMLID);
        } catch (e) {
            this.toast(errorText(e), { kind: "error" });
        }
    }

    refreshDecides() {
        const d = this.nh.draft;
        if (!d.department_id && !d.payroll_country) {
            this.nh.decides = null;
            return;
        }
        this.nh.decidesBusy = true;
        return this.ask("decides", "decides", [d.department_id || false, d.payroll_country || false,
                                                 d.date_start || false, d.contract_kind], (res, err) => {
            this.nh.decidesBusy = false;
            if (err) {
                this.toast(errorText(err), { kind: "error" });
                return;
            }
            this.nh.decides = res;
            const scheme = res && res.scheme;
            this.loadUsual(scheme ? scheme.id : 0);
        });
    }

    loadUsual(configId) {
        const u = this.nh.usual;
        if (configId === u.configId && u.rows) {
            return;
        }
        if (configId !== u.configId && u.configId) {
            // another scheme has other usual answers: the choices made for the
            // old one do not carry over
            this.nh.draft.usual = {};
        }
        u.configId = configId;
        if (!configId) {
            u.rows = [];
            return;
        }
        u.busy = true;
        return this.ask("usual", "usual_answers", [configId], (rows) => {
            u.busy = false;
            u.rows = rows || [];
        });
    }

    refreshHint() {
        const d = this.nh.draft;
        if (!d.job_id) {
            this.nh.hint = null;
            return;
        }
        return this.ask("hint", "pay_hint", [d.job_id, d.date_start || false,
                                              d.wage === null ? false : d.wage, d.payroll_country || false],
            (res) => { this.nh.hint = res || null; });
    }

    checkPerson() {
        const d = this.nh.draft;
        if (String(d.name || "").trim().length < 3 && !d.work_email) {
            this.nh.dup = null;
            return;
        }
        this.later("dup", 400, () => this.ask("dup", "check_person", [d.name || "", d.work_email || ""],
            (res) => { this.nh.dup = res || null; }));
    }

    // ------------------------------------------------------------ editing
    set(key, value, opts = {}) {
        this.patch({ [key]: value }, opts);
    }

    patch(values, { auto = false } = {}) {
        const nh = this.nh;
        const d = nh.draft;
        const changed = [];
        for (const [key, value] of Object.entries(values)) {
            if (d[key] !== value) {
                d[key] = value;
                changed.push(key);
            }
            if (auto) {
                if (value) {
                    nh.auto[key] = true;
                } else {
                    delete nh.auto[key];
                }
            } else {
                delete nh.auto[key];
                nh.touched[key] = true;
            }
            delete nh.fieldErr[key];
        }
        if (!changed.length) {
            return;
        }
        nh.refusal = null;
        this.persist();
        const has = (...keys) => keys.some((k) => changed.includes(k));
        if (has("department_id", "payroll_country", "date_start", "contract_kind")) {
            this.refreshDecides();
        }
        if (has("job_id", "date_start", "payroll_country")) {
            this.refreshHint();
        } else if (has("wage")) {
            this.later("hint", 350, () => this.refreshHint());
        }
        if (has("name", "work_email")) {
            this.checkPerson();
        }
        if (has("payroll_country", "contract_kind")) {
            this.refreshCats();
        }
        if (has("department_id", "payroll_country", "date_start", "name")) {
            this.refreshSched();
        }
        if (has("payroll_country", "name")) {
            this.refreshDocs();
        }
        if (has("clock_on", "clock_code")) {
            this.checkClock();
        }
        if (has(...WELCOME_INPUTS)) {
            this.refreshWelcome();
        }
    }

    /** The hero moment: a team suggests its manager, site and country —
     *  only where the person has not typed their own — and the tiles of
     *  "What this decides" fill in. */
    async pickTeam(id, { initial = false } = {}) {
        const nh = this.nh;
        const d = nh.draft;
        if (!initial) {
            this.patch({ department_id: id || false });
            // a job of another team no longer fits
            const job = (nh.data.jobs || []).find((j) => j.id === d.job_id);
            if (job && job.department_id && job.department_id !== id) {
                this.patch({ job_id: false });
            }
        }
        if (!id) {
            return;
        }
        const seq = (this.seq.team = (this.seq.team || 0) + 1);
        let res;
        try {
            res = await this.orm.silent.call(MODEL, "team_defaults", [id]);
        } catch (e) {
            this.toast(errorText(e), { kind: "error" });
            return;
        }
        if (seq !== this.seq.team || nh.draft.department_id !== id) {
            return;
        }
        nh.teamScheme = res.scheme || null;
        const take = {};
        if (!nh.touched.parent_id) {
            take.parent_id = res.manager_id || false;
            take.parent_name = res.manager_name || "";
        }
        if (!nh.touched.work_location_id) {
            take.work_location_id = res.site_id || false;
        }
        if (res.country_code && !nh.touched.payroll_country) {
            take.payroll_country = res.country_code;
        }
        this.patch(take, { auto: true });
        delete nh.auto.parent_name;
        this.persist();
        this.refreshAll();
    }

    setUsual(code, amount) {
        const row = (this.nh.usual.rows || []).find((r) => r.code === code);
        if (!row) {
            return;
        }
        const usual = { ...this.nh.draft.usual };
        if (amount === null || Math.abs(Number(amount) - row.value) < 1e-9) {
            delete usual[code];
        } else {
            usual[code] = Number(amount);
        }
        this.patch({ usual });
    }
    resetUsual(code) {
        const usual = { ...this.nh.draft.usual };
        delete usual[code];
        this.patch({ usual });
    }

    // ------------------------------------------------------------ the steps
    get data() { return this.nh.data; }
    get first() { return firstName(this.nh.draft.name) || _t("the new person"); }
    get team() { return (this.data?.teams || []).find((t) => t.id === this.nh.draft.department_id) || null; }
    get teamName() { return this.team ? this.team.name : ""; }
    get jobName() {
        const d = this.nh.draft;
        const job = (this.data?.jobs || []).find((j) => j.id === d.job_id);
        return job ? job.name : (d.job_title || "").trim();
    }
    get countryName() {
        const c = (this.data?.countries || []).find((x) => x.code === this.nh.draft.payroll_country);
        return c ? c.name : "";
    }
    get currency() {
        const dec = this.nh.decides;
        if (dec && dec.currency) {
            return dec.currency;
        }
        return (this.data?.currencies || {})[this.nh.draft.payroll_country] || null;
    }
    get scaleFound() {
        const s = this.nh.hint && this.nh.hint.scale;
        return Boolean(s && s.found && s.amount);
    }
    get whoReady() {
        const d = this.nh.draft;
        return Boolean(String(d.name || "").trim() && d.date_start);
    }
    get roleReady() {
        const d = this.nh.draft;
        return Boolean(d.department_id && d.payroll_country && (d.job_id || String(d.job_title || "").trim()));
    }
    get payReady() {
        const d = this.nh.draft;
        const wageOk = (d.wage !== null && d.wage > 0) || this.scaleFound;
        const endOk = d.contract_kind !== "fixed" || (d.date_end && d.date_end > d.date_start);
        return Boolean(wageOk && endOk);
    }
    get ready() { return this.whoReady && this.roleReady && this.payReady; }
    /** P2: required own fields block Send (not "Skip to the end"). */
    get sendable() { return this.ready && !this.ownMissing.length && !this.docGaps.length; }

    status(key) {
        const nh = this.nh;
        const d = nh.draft;
        if (key === "who") {
            return this.whoReady
                ? { state: "done", text: _t("%(name)s, starts %(day)s", { name: String(d.name).trim(), day: fmtDay(d.date_start) }) }
                : { state: "warn", text: _t("Name and first day needed") };
        }
        if (key === "role") {
            if (!this.roleReady) {
                return { state: "warn", text: _t("Team, job and country needed") };
            }
            return nh.seen.role
                ? { state: "done", text: _t("%(job)s, %(country)s", { job: this.jobName, country: this.countryName }) }
                : { state: "todo", text: _t("Suggested. Check it") };
        }
        if (key === "pay") {
            if (!this.payReady) {
                return { state: "warn", text: d.contract_kind === "fixed" && !d.date_end && (d.wage > 0 || this.scaleFound)
                    ? _t("End date needed") : _t("Wage needed") };
            }
            const wage = d.wage > 0 ? _t("%s a month", money(d.wage, this.currency)) : _t("From the pay scale");
            return nh.seen.pay ? { state: "done", text: wage } : { state: "todo", text: _t("Suggested. Check it") };
        }
        if (key === "sched") {
            const clash = nh.clockCheck && nh.clockCheck.ok === false;
            if (clash) {
                return { state: "warn", text: _t("Clock number taken") };
            }
            const text = this.weekName || _t("Company's usual hours");
            return nh.seen.sched ? { state: "done", text } : { state: "todo", text: _t("Team defaults are ready") };
        }
        if (key === "docs") {
            if (!d.payroll_country) {
                return { state: "todo", text: _t("Needs the country of work") };
            }
            if (!nh.docs) {
                return { state: "todo", text: _t("Working it out") };
            }
            const gaps = this.docGaps;
            if (gaps.length) {
                return { state: "warn", text: gaps.length === 1 ? _t("Finish: %s", gaps[0].label)
                    : _t("%s rows to finish", gaps.length) };
            }
            const t = docTallyOf(nh);
            const text = _t("%(ask)s for %(first)s, %(have)s with you", { ask: t.ask, first: this.first, have: t.have });
            return nh.seen.docs ? { state: "done", text } : { state: "todo", text };
        }
        if (key === "welcome") {
            const missing = this.ownMissing.length;
            if (missing) {
                return { state: "warn", text: missing === 1 ? _t("1 of your own fields is needed")
                    : _t("%s of your own fields are needed", missing) };
            }
            const w = nh.welcome;
            const has = Boolean(w && w.case && w.case.available && nh.draft.open_case !== false);
            const text = has ? _t("Checklist ready") : _t("No checklist");
            return nh.seen.welcome ? { state: "done", text } : { state: "todo", text: has ? _t("Checklist is ready") : text };
        }
        if (SOON.includes(key)) {
            return { state: "soon", text: _t("Arrives next") };
        }
        if (nh.result) {
            return { state: "done", text: nh.result.applied ? _t("Added") : _t("Sent for approval") };
        }
        return { state: "todo", text: _t("Last step") };
    }
    stepClass(step) {
        const st = this.status(step.key).state;
        return `pbnh-step is-${st}${step.key === this.nh.step ? " is-cur" : ""}`;
    }
    get doneCount() {
        return this.steps.filter((s) => this.status(s.key).state === "done").length;
    }
    get progressLine() {
        return _t("%(done)s of %(total)s steps done", { done: this.doneCount, total: this.steps.length });
    }
    get progressStyle() {
        return `width:${(this.doneCount / this.steps.length) * 100}%`;
    }
    get current() { return this.steps.find((s) => s.key === this.nh.step) || this.steps[0]; }
    get prevStep() { return this.steps[this.current.n - 2] || null; }
    get nextStep() { return this.steps[this.current.n] || null; }

    async go(key, field = false) {
        const nh = this.nh;
        if (nh.moving || !STEP_KEYS.includes(key)) {
            return;
        }
        nh.seen[nh.step] = true;
        if (key !== nh.step) {
            nh.step = key;
            nh.seen[key] = true;
            this.props.updateActionState?.({ step: key });
            this.persist();
            const smooth = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
            this.root.el?.scrollTo({ top: 0, behavior: smooth });
        }
        if (field) {
            this.focusAfter = field;
        }
    }
    next() {
        if (this.nextStep) {
            this.go(this.nextStep.key);
        }
    }
    skipToEnd() {
        if (this.ready) {
            this.go("check");
        }
    }

    /** After a step change the heading takes focus (screen readers read the
     *  new question); "Change" from the check list focuses its field. */
    focusHeading(changed) {
        const el = this.root.el;
        if (!el) {
            return;
        }
        requestAnimationFrame(() => {
            if (this.focusAfter) {
                const target = el.querySelector(`#pbnh-f-${this.focusAfter}`);
                this.focusAfter = null;
                if (target) {
                    target.focus();
                    target.scrollIntoView?.({ block: "center" });
                    return;
                }
            }
            if (changed) {
                el.querySelector(".pbnh-stage h1")?.focus({ preventScroll: true });
            }
        });
    }

    // ------------------------------------------------------------ keyboard
    onKey(ev) {
        const nh = this.nh;
        if (!this.root.el) {
            return;
        }
        if (ev.key === "Escape" && nh.dialog) {
            ev.preventDefault();
            ev.stopPropagation();
            this.closeDialog(false);
            return;
        }
        if (nh.dialog || nh.loading || !nh.data) {
            return;
        }
        const t = ev.target;
        if (!this.root.el.contains(t)) {
            return;
        }
        if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
            ev.preventDefault();
            this.primary();
            return;
        }
        if (ev.key === "Enter" && t.tagName === "INPUT" && !["checkbox", "radio", "button", "submit"].includes(t.type)
                && !t.closest(".pbnh-pick")) {
            ev.preventDefault();
            const stage = this.root.el.querySelector(".pbnh-stage");
            const items = [...stage.querySelectorAll("input:not([disabled]), select:not([disabled])")]
                .filter((n) => n.offsetParent !== null);
            const i = items.indexOf(t);
            if (i >= 0 && i < items.length - 1) {
                items[i + 1].focus();
            } else {
                this.primary();
            }
        }
    }
    /** The step's one solid button. */
    primary() {
        const nh = this.nh;
        if (nh.result) {
            return;
        }
        if (nh.step === "check") {
            this.send();
        } else {
            this.next();
        }
    }

    // ------------------------------------------------------------ sending
    get sendDraft() {
        const d = this.nh.draft;
        const p2 = {};
        for (const [key, [, send]] of Object.entries(P2_KEYS)) {
            if (send) {
                p2[key] = send(d);
            }
        }
        return {
            ...p2,
            name: d.name, date_start: d.date_start, work_email: d.work_email, personal: d.personal,
            department_id: d.department_id, job_id: d.job_id || false,
            job_title: d.job_id ? "" : d.job_title, payroll_country: d.payroll_country,
            parent_id: d.parent_id || false, work_location_id: d.work_location_id || false,
            country_id: d.country_id || false, wage: d.wage === null ? "" : d.wage,
            contract_kind: d.contract_kind, date_end: d.contract_kind === "fixed" ? d.date_end : "",
            trial_on: d.trial_on, usual: Object.entries(d.usual || {}).map(([code, amount]) => ({ code, amount })),
            pb_scale_pin_reason: d.pb_scale_pin_reason || "", fill_job_id: d.fill_job_id || false,
        };
    }

    async send() {
        const nh = this.nh;
        if (nh.sending || nh.result || !this.sendable || nh.data?.approval?.problem) {
            return;
        }
        nh.sending = true;
        nh.refusal = null;
        try {
            const res = await this.orm.call(MODEL, "send", [this.sendDraft, this.sendFiles]);
            if (res && res.ok === false) {
                nh.refusal = res;
                if (res.field) {
                    nh.fieldErr[res.field] = res.message;
                }
                if (res.step && res.step !== "check") {
                    this.go(res.step, res.field);
                    this.toast(res.message, { kind: "error" });
                }
                return;
            }
            if (res && (res.applied || res.pending)) {
                nh.result = res;
                this.clearStore();
                this.root.el?.scrollTo({ top: 0, behavior: "auto" });
                return;
            }
            // proposed, but neither waiting nor carried out (the engine said why)
            nh.refusal = { message: (res && (res.block_note || res.message)) || _t("The hire could not be sent. Try again in a moment.") };
        } catch (e) {
            nh.refusal = { message: errorText(e) };
        } finally {
            nh.sending = false;
        }
    }

    async withdraw() {
        const nh = this.nh;
        const res = nh.result;
        if (!res || !res.proposal_id || nh.sending) {
            return;
        }
        nh.sending = true;
        try {
            const out = await this.orm.call(MODEL, "withdraw", [res.proposal_id, _t("Withdrawn to change it.")]);
            if (!out.ok) {
                this.toast(out.message, { kind: "error" });
                return;
            }
            nh.result = null;
            this.persist();
            this.go("check");
            this.toast(_t("Withdrawn. Change what you need, then send it again."), { kind: "info" });
        } catch (e) {
            this.toast(errorText(e), { kind: "error" });
        } finally {
            nh.sending = false;
        }
    }

    again(fromToast = false) {
        const nh = this.nh;
        this.clearStore();
        nh.result = null;
        nh.refusal = null;
        nh.fieldErr = {};
        nh.auto = {};
        nh.touched = {};
        nh.seen = { who: true };
        nh.decides = null;
        nh.teamScheme = null;
        nh.hint = null;
        nh.dup = null;
        nh.usual = { configId: 0, rows: null, busy: false };
        nh.welcome = null;
        nh.clockCheck = null;
        nh.files = {};
        nh.draft = Object.assign(blankDraft(nh.data.today), { payroll_country: nh.data.draft.payroll_country || "" });
        this.refreshCats();
        this.refreshSched();
        this.refreshDocs();
        if (fromToast) {
            this.closeToast();
        }
        if (nh.step === "who") {
            this.focusAfter = "name";
            this.focusHeading(false);
        } else {
            this.go("who", "name");
        }
    }

    openRecord() {
        const res = this.nh.result;
        if (!res || !res.employee_id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.client", tag: "pb_people", name: _t("Employees"),
            params: { emp: res.employee_id },
        });
    }

    backToEmployees() {
        if (!goBack(this.action, this.back.fromStack ? EMPLOYEES : this.back)) {
            this.action.doAction(EMPLOYEES.xmlid);
        }
    }

    // ------------------------------------------------------------ leaving
    async beforeLeave({ forceLeave } = {}) {
        const nh = this.nh;
        if (forceLeave || nh.result || !String(nh.draft.name || "").trim()) {
            return true;
        }
        const leave = await this.ask_({
            title: _t("Leave without adding %s?", String(nh.draft.name).trim()),
            body: _t("Nothing has been sent yet. If you leave, what you typed here is cleared."),
            ok: _t("Leave"), cancel: _t("Stay here"),
        });
        if (leave) {
            this.clearStore();
        }
        return leave;
    }
    ask_(dialog) {
        return new Promise((resolve) => {
            this.nh.dialog = { ...dialog, resolve };
        });
    }
    closeDialog(answer) {
        const dlg = this.nh.dialog;
        this.nh.dialog = null;
        dlg?.resolve(answer);
    }

    // ------------------------------------------------------------ the toast
    toast(msg, opts = {}) {
        clearTimeout(this.toastTimer);
        const id = (this.toastSeq = (this.toastSeq || 0) + 1);
        this.nh.toast = { id, msg: String(msg || ""), kind: opts.kind || "ok", action: opts.action || null };
        this.toastTimer = setTimeout(() => {
            if (this.nh.toast && this.nh.toast.id === id) {
                this.nh.toast = null;
            }
        }, opts.ms || TOAST_MS);
    }
    get toastIcon() {
        const kind = this.nh.toast?.kind;
        return kind === "error" ? "triangleAlert" : kind === "info" ? "info" : "checkCircle";
    }
    onToastAction() {
        const t = this.nh.toast;
        this.closeToast();
        t?.action?.run();
    }
    closeToast() {
        clearTimeout(this.toastTimer);
        this.nh.toast = null;
    }

    get skeletonRows() { return [1, 2, 3, 4, 5, 6, 7]; }
    get skipTitle() { return this.ready ? _t("Go straight to Check and add") : _t("Finish the three required steps first"); }
    get noTeams() { return this.data && !(this.data.teams || []).length; }
    async openTeams() {
        try {
            await this.action.doAction("hr.hr_department_kanban_action");
        } catch (e) {
            this.toast(errorText(e), { kind: "error" });
        }
    }
    clone(v) { return deepClone(v); }
}

registry.category("actions").add("pb_new_hire_studio", NewHireStudio);
