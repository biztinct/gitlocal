/** @odoo-module **/
/**
 * `pb_training_numbers` — the Training lens on the Insights hub.
 *
 * TWO RATIOS FIRST AND ONE SENTENCE ABOVE THEM. A training programme is judged
 * on whether people FINISH what they were set and whether they PASS the test
 * at the end, and a screen that opens on a grid of figures makes a reader do
 * the arithmetic the sentence could have done for them (R113).
 *
 * NOTHING HERE RECOMPUTES A NUMBER. The server computes every figure, every
 * ratio and every split; a second opinion written in JavaScript would only
 * ever disagree with the one that counts, and the spreadsheet is built from
 * the same read so it cannot disagree with the screen either.
 *
 * THE EMPTY STATE TEACHES. A range with nothing in it says so in words, with
 * the dates in the sentence, rather than drawing six zeros — a screen of
 * zeros is how a working feature gets reported as broken.
 *
 * Every icon is from the shared `ic()` registry in pb_import_kit — the set is
 * CLOSED and an unknown name renders a plain circle with no error, so a name
 * used here is a name that is in that file.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The ranges somebody actually asks for, in the order they ask for them. */
const RANGES = [
    { key: "30", label: _t("Last 30 days"), days: 30 },
    { key: "90", label: _t("Last 3 months"), days: 90 },
    { key: "180", label: _t("Last 6 months"), days: 180 },
    { key: "365", label: _t("Last year"), days: 365 },
];

export class PbTrainingNumbers extends Component {
    static template = "pb_training.PbTrainingNumbers";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ranges = RANGES;

        this.state = useState({
            loaded: false,
            allowed: true,
            // LEARNING L6: a read that did not come back is not a refusal.
            failed: false,
            empty: true,
            busy: false,
            range: "90",
            from: "",
            to: "",
            custom: false,
            filters: { department_id: 0, channel_id: 0, path_id: 0, reason: "", work_location_id: 0, country_code: "", kind: "" },
            headline: "",
            total: 0,
            tiles: [],
            byDepartment: [],
            byCourse: [],
            byReason: [],
            byCertificate: [],
            // LEARNING L4: initial collections are collections, so a render
            // during an interrupted read never loops over undefined.
            byPath: [],
            sessions: { has_sessions: false, by_kind: [], by_trainer: [], by_course: [] },
            // LEARNING L5
            ratings: { rows: [] },
            didItWork: {},
            courseRequests: { by_state: [], by_kind: [] },
            skills: { rows: [] },
            required: { has_rules: false },
            countryReports: [],
            reporting: "",
            trend: [],
            claims: {},
            lists: { courses: [], departments: [], paths: [], sites: [], countries: [], kinds: [] },
            reasons: [],
            // LEARNING L6
            hours: { by_person_shown: [], by_department: [], by_course: [], kinds: [] },
            cost: { empty: true, budget: null },
            compliance: null,
            effect: { by_course_top: [] },
            countries: [],
            showAllPeople: false,
        });

        onWillStart(async () => {
            this.pickRange("90", { reload: false });
            await this.load();
        });
    }

    ic(n, s = 16) { return ic(n, s); }

    /** A date, as the value a `date` input wants. */
    static iso(when) {
        const pad = (n) => String(n).padStart(2, "0");
        return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-`
            + `${pad(when.getDate())}`;
    }

    pickRange(key, { reload = true } = {}) {
        const row = RANGES.find((r) => r.key === key);
        this.state.range = key;
        this.state.custom = !row;
        if (row) {
            const to = new Date();
            const from = new Date();
            from.setDate(from.getDate() - row.days);
            this.state.from = PbTrainingNumbers.iso(from);
            this.state.to = PbTrainingNumbers.iso(to);
        }
        if (reload) { return this.load(); }
        return null;
    }

    onDate(which, ev) {
        this.state[which] = ev.target.value;
        this.state.custom = true;
        this.state.range = "";
        return this.load();
    }

    /** Only the filters that are actually set — an empty one is not a filter. */
    activeFilters() {
        const f = this.state.filters;
        const out = {};
        if (f.department_id) { out.department_id = Number(f.department_id); }
        if (f.channel_id) { out.channel_id = Number(f.channel_id); }
        if (f.path_id) { out.path_id = Number(f.path_id); }
        if (f.reason) { out.reason = f.reason; }
        if (f.work_location_id) { out.work_location_id = Number(f.work_location_id); }
        if (f.country_code) { out.country_code = f.country_code; }
        if (f.kind) { out.kind = f.kind; }
        return out;
    }

    async setFilter(key, value) {
        // A CHIP THAT IS ALREADY ON IS A CHIP THAT TURNS OFF. Otherwise the
        // only way back to everything is a page reload, which is a dead end.
        this.state.filters[key] =
            String(this.state.filters[key]) === String(value) ? (
                ["reason", "kind", "country_code"].includes(key) ? "" : 0) : value;
        await this.load();
    }

    get anyFilter() {
        return Object.keys(this.activeFilters()).length > 0;
    }

    async clearFilters() {
        this.state.filters.department_id = 0;
        this.state.filters.channel_id = 0;
        this.state.filters.path_id = 0;
        this.state.filters.reason = "";
        this.state.filters.work_location_id = 0;
        this.state.filters.country_code = "";
        this.state.filters.kind = "";
        await this.load();
    }

    async load() {
        this.state.busy = true;
        this.state.failed = false;
        try {
            const d = await this.orm.call(
                "pb.training.analytics", "get_numbers",
                [this.state.from, this.state.to, this.activeFilters()]);
            Object.assign(this.state, {
                allowed: d.allowed !== false,
                empty: !!d.empty,
                headline: d.headline || "",
                total: d.total || 0,
                tiles: d.tiles || [],
                byDepartment: d.by_department || [],
                byCourse: d.by_course || [],
                byReason: d.by_reason || [],
                byPath: d.by_path || [],
                byCertificate: d.by_certificate || [],
                sessions: d.sessions || { has_sessions: false },
                ratings: d.ratings || { rows: [] },
                didItWork: d.did_it_work || {},
                courseRequests: d.course_requests || { by_state: [], by_kind: [] },
                skills: d.skills || { rows: [] },
                required: d.required || { has_rules: false },
                countryReports: d.country_reports || [],
                trend: d.trend || [],
                claims: d.claims || {},
                lists: Object.assign({ courses: [], departments: [], paths: [], sites: [], countries: [], kinds: [] }, d.lists || {}),
                reasons: d.reasons || [],
                hours: d.hours || { by_person_shown: [], by_department: [], by_course: [], kinds: [] },
                cost: d.cost || { empty: true, budget: null },
                compliance: d.compliance || null,
                effect: d.effect || { by_course_top: [] },
                countries: d.countries || [],
                loaded: true,
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.failed = true;
            console.warn("pb_training: the training numbers could not be read",
                         e);
        } finally {
            this.state.busy = false;
        }
    }

    /** The widest bar in a table is 100%; everything else is relative to it. */
    share(rows, value, key = "total") {
        const top = Math.max(...rows.map((r) => Number(r[key] || 0)), 0);
        if (!top) { return 0; }
        return Math.round((Number(value || 0) / top) * 100);
    }

    /** A ratio nobody can answer yet is a dash, never a zero. */
    pct(value) {
        return (value === null || value === undefined) ? "—" : `${value}%`;
    }

    /**
     * The split row's own sentence.
     *
     * "— finished" is what a dash pasted in front of a word looks like, and it
     * reads as a typo rather than as "there is nothing to measure here". A row
     * whose every assignment has more time agreed has no completion ratio at
     * all, and the honest answer is a sentence.
     */
    finishedWord(row) {
        if (row.completion === null || row.completion === undefined) {
            return _t("nothing to measure yet");
        }
        return _t("%s%% finished", row.completion);
    }

    /** "2 late" (LEARNING L3, By path). */
    lateWords(n) { return n === 1 ? _t("1 late") : _t("%s late", n); }

    /** "3 hold it · 1 expires within 30 days · 1 expired" (LEARNING L1). */
    certWords(row) {
        const bits = [row.holders === 1 ? _t("1 holds it") : _t("%s hold it", row.holders)];
        if (row.expiring) {
            bits.push(row.expiring === 1 ? _t("1 expires within 30 days") : _t("%s expire within 30 days", row.expiring));
        }
        if (row.expired) {
            bits.push(row.expired === 1 ? _t("1 expired") : _t("%s expired", row.expired));
        }
        return bits.join(" · ");
    }

    /** The tallest week in the trend is the full height of the chart. */
    trendHeight(value) {
        const top = Math.max(
            ...this.state.trend.map((w) => Math.max(w.set, w.done)), 0);
        if (!top) { return 2; }
        return Math.max(Math.round((Number(value || 0) / top) * 100), 2);
    }

    /** "92% in date · 4 missing" for one row of a required-training split. */
    requiredWords(row) {
        const bits = [row.percent === null || row.percent === undefined
            ? _t("nothing due yet") : _t("%s%% in date", row.percent)];
        if (row.missing) { bits.push(row.missing === 1 ? _t("1 missing") : _t("%s missing", row.missing)); }
        if (row.expiring) { bits.push(row.expiring === 1 ? _t("1 expiring") : _t("%s expiring", row.expiring)); }
        return bits.join(" · ");
    }

    /** LEARNING L2: one country report, as a spreadsheet in the downloads. */
    async countryReport(rep) {
        this.state.reporting = rep.cc;
        try {
            const res = await this.orm.call("pb.training.analytics", "country_report_xlsx", [rep.cc]);
            if (!res || !res.file_b64) { return; }
            const a = document.createElement("a");
            a.href = `data:${res.mimetype};base64,${res.file_b64}`;
            a.download = res.filename || "report.xlsx";
            document.body.appendChild(a);
            a.click();
            a.remove();
            this.notif.add(_t("The spreadsheet is in your downloads."), { type: "success" });
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.reporting = "";
        }
    }

    async download() {
        this.state.busy = true;
        try {
            const res = await this.orm.call(
                "pb.training.analytics", "export_xlsx",
                [this.state.from, this.state.to, this.activeFilters()]);
            if (!res || !res.file_b64) { return; }
            // A DATA URL AND NOT A SERVER ROUTE. The file is built for this
            // reader, from this reader's own company set, and leaving it on
            // the server as an attachment would be a copy of the company's
            // training figures sitting in a table nobody remembers to clear.
            const a = document.createElement("a");
            a.href = `data:${res.mimetype};base64,${res.file_b64}`;
            a.download = res.filename || "training.xlsx";
            document.body.appendChild(a);
            a.click();
            a.remove();
            this.notif.add(_t("The spreadsheet is in your downloads."),
                           { type: "success" });
        } catch (e) {
            const message = (e && e.data && e.data.message)
                || _t("That did not work.");
            this.notif.add(message, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ LEARNING L4
    /** "92%" or a dash when nothing could be counted yet. */
    pct(v) { return v === null || v === undefined ? "—" : `${v}%`; }

    // ---------------------------------------------------- LEARNING L5
    /** "4.3 out of 5 from 17 ratings · 82% would recommend" */
    get ratingsWords() {
        const r = this.state.ratings || {};
        if (!r.count) { return _t("Nobody has rated a course in this period yet."); }
        const bits = [r.count === 1 ? _t("%s out of 5 from 1 rating", r.avg) : _t("%(avg)s out of 5 from %(n)s ratings", { avg: r.avg, n: r.count })];
        if (r.recommend !== null && r.recommend !== undefined) { bits.push(_t("%s%% would recommend the course", r.recommend)); }
        return bits.join(" · ");
    }

    ratingRowWords(row) {
        const bits = [];
        if (row.count) { bits.push(row.count === 1 ? _t("1 rating") : _t("%s ratings", row.count)); }
        if (row.recommend !== null && row.recommend !== undefined) { bits.push(_t("%s%% recommend", row.recommend)); }
        if (row.answered) { bits.push(_t("work changed %s/5", row.effect)); }
        return bits.join(" · ");
    }

    get workWords() {
        const w = this.state.didItWork || {};
        if (!w.answered) {
            return w.waiting ? _t("No manager has answered yet; %s follow-ups are waiting.", w.waiting) : _t("A month after a course, the manager is asked whether the person's work has changed. No answers in this period yet.");
        }
        const bits = [_t("Managers say work changed %s out of 5", w.effect)];
        if (w.used !== null && w.used !== undefined) { bits.push(_t("%s%% used what they learned", w.used)); }
        bits.push(w.answered === 1 ? _t("1 answer") : _t("%s answers", w.answered));
        if (w.waiting) { bits.push(w.waiting === 1 ? _t("1 waiting on a manager") : _t("%s waiting on managers", w.waiting)); }
        return bits.join(" · ");
    }

    get requestsWords() {
        const r = this.state.courseRequests || {};
        if (!r.total) { return _t("Nobody asked to take a course in this period."); }
        const bits = [r.total === 1 ? _t("1 course request") : _t("%s course requests", r.total)];
        if (r.committed_words) { bits.push(_t("%s set aside", r.committed_words)); }
        if (r.claimed_words) { bits.push(_t("%s claimed back", r.claimed_words)); }
        return bits.join(" · ");
    }

    skillRowWords(row) {
        return _t("%(ok)s of %(n)s at the level", { ok: row.ok, n: row.employees });
    }

    share2(list, n) {
        const max = Math.max(1, ...(list || []).map((x) => x.n || 0));
        return Math.round((100 * (n || 0)) / max);
    }

    /** "4 closed sessions · 12 hours of training · 90% attended · 10% did not come" */
    get sessionsWords() {
        const x = this.state.sessions || {};
        return [
            x.sessions === 1 ? _t("1 closed session") : _t("%s closed sessions", x.sessions || 0),
            _t("%s hours of training", x.hours || 0),
            _t("%s attended", this.pct(x.attendance_rate)),
            _t("%s did not come", this.pct(x.no_show_rate)),
        ].join(" · ");
    }

    hoursWords(h) { return _t("%s h", h || 0); }

    // ---------------------------------------------------- LEARNING L6
    async retry() {
        this.state.loaded = false;
        await this.load();
    }

    /** "12 h" for an hours figure, a dash for nothing. */
    hoursOf(h) { return h ? _t("%s h", h) : "—"; }

    get peopleRows() {
        const h = this.state.hours || {};
        return this.state.showAllPeople ? (h.by_person_shown || []) : (h.by_person_shown || []).slice(0, 10);
    }

    get morePeople() {
        const h = this.state.hours || {};
        return Math.max((h.people || 0) - this.peopleRows.length, 0);
    }

    personWords(row) {
        const bits = [];
        if (row.department) { bits.push(row.department); }
        if (row.courses) { bits.push(row.courses === 1 ? _t("1 course") : _t("%s courses", row.courses)); }
        if (row.sessions) { bits.push(row.sessions === 1 ? _t("1 session") : _t("%s sessions", row.sessions)); }
        return bits.join(" · ");
    }

    shareOf(rows, value, key = "hours") {
        const top = Math.max(0, ...(rows || []).map((r) => Number(r[key] || 0)));
        return top ? Math.round((Number(value || 0) / top) * 100) : 0;
    }

    /** The cost lines, one per kind of spend, in words. */
    get costLines() {
        const c = this.state.cost || {};
        if (c.mixed || c.empty) { return []; }
        return [
            { key: "claims", label: _t("Claims agreed"), words: c.claims_agreed_words, n: c.claims_agreed,
              sub: c.paid_count ? _t("%(n)s of %(all)s already paid · %(paid)s", { n: c.paid_count, all: c.claims_count, paid: c.claims_paid_words }) : (c.claims_count === 1 ? _t("1 claim") : _t("%s claims", c.claims_count || 0)) },
            { key: "requests", label: _t("Outside courses agreed"), words: c.requests_approved_words, n: c.requests_approved,
              sub: _t("set aside until the claim comes in") },
            { key: "sessions", label: _t("Sessions"), words: c.sessions_words, n: c.sessions,
              sub: c.sessions_count === 1 ? _t("1 session with a cost") : _t("%s sessions with a cost", c.sessions_count || 0) },
        ];
    }

    get allowanceWords() {
        const c = this.state.cost || {};
        if (c.allowance_used_pct === null || c.allowance_used_pct === undefined) {
            return _t("No training allowance is set for %s.", c.allowance_year || "");
        }
        return _t("%(used)s used of %(total)s in allowances for %(year)s (%(pct)s%%).", { used: c.allowance_used_words, total: c.allowance_total_words, year: c.allowance_year, pct: c.allowance_used_pct });
    }

    get budgetWords() {
        const b = (this.state.cost || {}).budget;
        if (!b) { return ""; }
        return _t("%(line)s: %(spent)s spent of %(budget)s, %(left)s left.", { line: b.line, spent: b.spent_words, budget: b.budget_words, left: b.left_words });
    }

    /** "agreed across 2 of 3 claims · 1 still waiting · 1 already paid" —
     * whole sentences, never a fragment around a number (LN13). */
    get claimWords() {
        const c = this.state.claims || {};
        const bits = [_t("agreed across %(agreed)s of %(n)s claims", { agreed: c.agreed || 0, n: c.claims || 0 })];
        if (c.waiting) { bits.push(c.waiting === 1 ? _t("1 still waiting") : _t("%s still waiting", c.waiting)); }
        if (c.paid) { bits.push(c.paid === 1 ? _t("1 already paid") : _t("%s already paid", c.paid)); }
        return bits.join(" · ");
    }

    /** Compliance splits as tabs inside the Required training section. */
    complianceSplits() {
        const c = this.state.compliance || {};
        return [
            { key: "by_site", label: _t("By site"), rows: c.by_site || [] },
            { key: "by_department", label: _t("By department"), rows: c.by_department || [] },
            { key: "by_country", label: _t("By country"), rows: c.by_country || [] },
            { key: "by_group", label: _t("By safety group"), rows: c.by_group || [] },
        ];
    }

    sessionRowWords(row) {
        const bits = [row.sessions === 1 ? _t("1 session") : _t("%s sessions", row.sessions)];
        bits.push(row.attended === 1 ? _t("1 attended") : _t("%s attended", row.attended));
        if (row.no_show) { bits.push(row.no_show === 1 ? _t("1 did not come") : _t("%s did not come", row.no_show)); }
        return bits.join(" · ");
    }
}

registry.category("actions").add("pb_training_numbers", PbTrainingNumbers);
