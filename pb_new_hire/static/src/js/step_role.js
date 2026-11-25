/** @odoo-module **/
/**
 * Step 2 — Role and place (NEWHIRE P1, P7). P7: the Country of work comes
 * FIRST and leads — the teams and jobs of that country come first in their
 * lists (`places()`), "What this decides" (currency, trial period, letter,
 * papers) follows it at once, and changing it clears a team of another
 * country with Undo. Picking a team then fills the manager and the site
 * (marked "Leads this team" / "Where most of the team works") and names the
 * pay scheme. Never stuck: every team and job stays reachable.
 */
import { Component, useRef, useState, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon, initials, fmtDay, rich } from "./studio_util";

const NEW_JOB = "__new";

export class StepRole extends Component {
    static template = "pb_new_hire.StepRole";
    static props = { api: Object };

    setup() {
        this.icon = icon;
        this.initials = initials;
        this.nh = useState(this.props.api.nh);
        this.ui = useState({ more: Boolean(this.nh.draft.country_id), q: "", open: false, list: [], active: 0, busy: false,
                             otherTeams: false });
        this.pickRef = useRef("pick");
        this.timer = null;
        onWillUnmount(() => clearTimeout(this.timer));
    }

    get d() { return this.nh.draft; }
    get data() { return this.nh.data; }
    err(field) { return this.nh.fieldErr[field] || ""; }
    isAuto(field) { return Boolean(this.nh.auto[field] && this.d[field]); }

    // ------------------------------------------------------------ P7: the country leads
    get places() {
        const p = this.nh.places;
        return p && p.country && p.country === this.d.payroll_country ? p : null;
    }
    get knownCountries() { return (this.data.countries || []).filter((c) => c.known); }
    get otherCountries() { return (this.data.countries || []).filter((c) => !c.known); }
    get countryGroups() { return this.knownCountries.length && this.otherCountries.length; }
    onCountry(ev) { this.props.api.pickCountry(ev.target.value || ""); }
    get countryWhy() {
        const why = this.nh.countryWhy;
        return why === "last" ? _t("Your last choice")
            : why === "most" ? _t("Where most of your people work")
            : why === "team" ? _t("Where this team works")
            : why === "company" ? _t("Your company's country") : "";
    }
    get countryName() { return this.props.api.countryName; }
    /** `{mine, unknown, other}` teams, in the list's own order. Without a
     *  country every team is in one list. */
    get teamGroups() {
        const all = this.data.teams || [];
        const p = this.places;
        if (!p) {
            return { mine: [], unknown: all, other: [], flat: true };
        }
        const mine = new Set(p.teams.mine);
        const other = new Set(p.teams.other);
        return {
            mine: all.filter((t) => mine.has(t.id)),
            other: all.filter((t) => other.has(t.id)),
            unknown: all.filter((t) => !mine.has(t.id) && !other.has(t.id)),
            flat: false,
        };
    }
    get teamInOther() {
        const id = this.d.department_id;
        return Boolean(id && this.teamGroups.other.some((t) => t.id === id));
    }
    get showOtherTeams() { return this.ui.otherTeams || this.teamInOther; }
    get otherTeamsCount() { return this.teamGroups.other.length; }
    toggleOtherTeams() {
        this.ui.otherTeams = !this.showOtherTeams;
        if (this.ui.otherTeams) {
            setTimeout(() => document.getElementById("pbnh-f-department_id")?.focus(), 60);
        }
    }
    get mineLabel() { return _t("Teams in %s", this.countryName); }
    get otherTeamsLabel() {
        return this.showOtherTeams ? _t("Hide teams from other countries")
            : _t("Show teams from other countries (%s)", this.otherTeamsCount);
    }
    get noTeamsHere() {
        const g = this.teamGroups;
        return !g.flat && !g.mine.length;
    }
    get noTeamsLine() { return _t("No team has people working in %s yet.", this.countryName); }
    teamPeople(t) {
        const p = this.places;
        return p ? (p.team_people || {})[String(t.id)] || 0 : 0;
    }
    get notice() { return this.nh.placeNotice; }
    get noticeText() {
        const n = this.notice;
        if (!n) {
            return "";
        }
        return n.cleared_job ? _t("Team and job cleared: %s", n.text) : _t("Team cleared: %s", n.text);
    }
    undo() { this.props.api.undoPlace(); }

    // ------------------------------------------------------------ team / job
    onTeam(ev) {
        const id = Number(ev.target.value) || false;
        this.props.api.pickTeam(id);
    }
    get teamJobs() {
        const id = this.d.department_id;
        return (this.data.jobs || []).filter((j) => id && j.department_id === id);
    }
    /** P7: jobs already held by people working in the country. */
    get countryJobs() {
        const p = this.places;
        if (!p) {
            return [];
        }
        const held = new Set(p.jobs);
        const id = this.d.department_id;
        return (this.data.jobs || []).filter((j) => held.has(j.id) && !(id && j.department_id === id));
    }
    get otherJobs() {
        const id = this.d.department_id;
        const held = new Set((this.places && this.places.jobs) || []);
        return (this.data.jobs || []).filter((j) => (!id || j.department_id !== id) && !held.has(j.id));
    }
    get countryJobsLabel() { return _t("Held by people in %s", this.countryName); }
    get teamLabel() {
        return _t("In %s", this.props.api.teamName || _t("this team"));
    }
    get jobValue() {
        if (this.d.newJob || (!this.d.job_id && this.d.job_title)) {
            return NEW_JOB;
        }
        return this.d.job_id ? String(this.d.job_id) : "";
    }
    onJob(ev) {
        const v = ev.target.value;
        if (v === NEW_JOB) {
            this.props.api.patch({ job_id: false, newJob: true });
            this.props.api.toast(_t("Type the new job title in the box below."), { kind: "info", ms: 3000 });
            return;
        }
        this.props.api.patch({ job_id: Number(v) || false, newJob: false, job_title: "" });
    }
    isJob(j) { return String(j.id) === this.jobValue; }
    onJobTitle(ev) { this.props.api.set("job_title", ev.target.value); }
    get showTitle() { return this.jobValue === NEW_JOB; }

    // ------------------------------------------------------------ country / site / nationality
    onSelect(key, ev) {
        const raw = ev.target.value;
        const value = key === "payroll_country" ? raw : (Number(raw) || false);
        this.props.api.set(key, value);
    }
    get sameAsWork() {
        const c = this.props.api.countryName;
        return c ? _t("Same as the country of work (%s)", c) : _t("Same as the country of work");
    }
    toggleMore() { this.ui.more = !this.ui.more; }

    // ------------------------------------------------------------ the manager picker
    get pickText() { return this.ui.open ? this.ui.q : (this.d.parent_name || ""); }
    onPickFocus() {
        this.ui.open = true;
        this.ui.q = "";
        this.search("");
    }
    onPickInput(ev) {
        this.ui.q = ev.target.value;
        this.ui.open = true;
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.search(this.ui.q), 250);
    }
    async search(q) {
        const seq = (this.seq = (this.seq || 0) + 1);
        this.ui.busy = true;
        try {
            // P7: before typing, the people working in the country come first
            const first = this.places && this.places.managers.length ? this.places.managers : (this.data.managers || []);
            const rows = q ? await this.props.api.findPeople(q) : first;
            if (seq === this.seq) {
                this.ui.list = rows || [];
                this.ui.active = 0;
            }
        } finally {
            if (seq === this.seq) {
                this.ui.busy = false;
            }
        }
    }
    onPickKey(ev) {
        const list = this.ui.list;
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            this.ui.open = true;
            this.ui.active = Math.min(list.length - 1, this.ui.active + 1);
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this.ui.active = Math.max(0, this.ui.active - 1);
        } else if (ev.key === "Enter" && !(ev.metaKey || ev.ctrlKey)) {
            ev.preventDefault();
            if (this.ui.open && list[this.ui.active]) {
                this.choose(list[this.ui.active]);
            }
        } else if (ev.key === "Escape" && this.ui.open) {
            ev.preventDefault();
            ev.stopPropagation();
            this.ui.open = false;
        }
    }
    onPickBlur() {
        // a click on a row lands before the box loses focus (mousedown)
        setTimeout(() => { this.ui.open = false; }, 120);
    }
    choose(p) {
        this.props.api.patch({ parent_id: p.id, parent_name: p.name });
        this.ui.open = false;
    }
    clearManager() {
        this.props.api.patch({ parent_id: false, parent_name: "" });
    }
    personLine(p) { return [p.job, p.team].filter(Boolean).join(" · "); }

    // ------------------------------------------------------------ what this decides
    get dec() { return this.nh.decides; }
    get schemeTile() {
        const dec = this.dec;
        if (!this.d.department_id) {
            return { cls: "", value: _t("Pick a team"), sub: _t("The team decides who pays.") };
        }
        if (!dec) {
            return { cls: "is-busy", value: _t("Working it out"), sub: "" };
        }
        if (!dec.scheme) {
            return { cls: "is-warn", value: _t("No pay scheme yet"), sub: "" };
        }
        return { cls: dec.scheme.match ? "is-set" : "is-warn", value: dec.scheme.name, sub: dec.scheme.why };
    }
    get currencyTile() {
        const cur = this.props.api.currency;
        if (!this.d.payroll_country || !cur) {
            return { cls: "", value: _t("Choose a country first"), sub: "" };
        }
        return { cls: "is-set", value: _t("%(code)s · wages and payslips", { code: cur.name }),
                 sub: _t("Written as %s", cur.symbol) };
    }
    get trialTile() {
        const dec = this.dec;
        if (!this.d.payroll_country) {
            return { cls: "", value: _t("Choose a country first"), sub: "" };
        }
        if (!dec) {
            return { cls: "is-busy", value: _t("Working it out"), sub: "" };
        }
        if (dec.trial) {
            return { cls: "is-set", value: _t("%(n)s months, to %(day)s", { n: dec.trial.months, day: fmtDay(dec.trial.ends) }),
                     sub: dec.trial.policy_name || "" };
        }
        return { cls: "is-set", value: _t("No trial period"), sub: dec.trial_none || "" };
    }
    /** P2: the contract letter that will be used for this country. */
    get letterTile() {
        const dec = this.dec;
        if (!this.d.payroll_country) {
            return { cls: "", value: _t("Choose a country first"), sub: "" };
        }
        if (!dec) {
            return { cls: "is-busy", value: _t("Working it out"), sub: "" };
        }
        const l = dec.letter;
        if (!l || !l.available) {
            return { cls: "is-warn", value: _t("No contract letter"), sub: (l && l.reason) || "" };
        }
        if (!l.own) {
            return { cls: "is-set", value: _t("No letter wording for %s yet", this.props.api.countryName),
                     sub: _t("The general one is used, in %s.", l.language) };
        }
        return { cls: "is-set", value: _t("In %s", l.language), sub: l.name };
    }
    /** P3a: what the country of work asks for (`pb.new.hire.paper`). */
    get papersTile() {
        const dec = this.dec;
        if (!this.d.payroll_country) {
            return { cls: "", value: _t("Choose a country first"), sub: "" };
        }
        if (!dec || !dec.papers) {
            return { cls: "is-busy", value: _t("Working it out"), sub: "" };
        }
        const p = dec.papers;
        if (!p.required && !p.optional) {
            return { cls: "is-warn", value: _t("No papers listed"), sub: _t("Add them in step 5 if you need any.") };
        }
        return {
            cls: "is-set",
            value: _t("%(req)s required, %(opt)s optional", { req: p.required, opt: p.optional }),
            sub: p.first_pay.length ? _t("Before the first pay: %s", p.first_pay.join(", ")) : "",
        };
    }
    get problem() { return this.dec && this.dec.problem; }
    get mismatchCountry() {
        const s = this.dec && this.dec.scheme;
        return s && !s.match && s.country_code ? s : null;
    }
    useSchemeCountry() {
        const s = this.mismatchCountry;
        if (s) {
            this.props.api.pickCountry(s.country_code);
        }
    }
    get useSchemeLabel() {
        const s = this.mismatchCountry;
        return s ? _t("Use %s", s.country_name) : "";
    }
    get heading() {
        return _t("Where will %s work, and as what?", this.props.api.first);
    }
    get fixLine() { return this.dec && this.dec.fix ? rich(this.dec.fix) : ""; }
}
