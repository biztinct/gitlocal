/** @odoo-module **/
/**
 * `pb_shift_patterns` — the Patterns lens of Mission Control (and its own page).
 *
 * A rota that repeats is set ONCE: the cycle (each day a shift or off), the
 * teams (each starts the cycle some days after Team A) and the people in each
 * team. "Make drafts" then fills the next weeks with DRAFT shifts, checked the
 * way Copy week checks them, and says what it could not fill and why. Nothing
 * is published: the planner checks the Schedule and presses Publish there.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in (UPDATES G60).
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`): a NEW markup()
 *      per render re-inserts the SVG on every patch (OWL markup flicker).
 * R3 — every sentence a person reads is a `_t()` literal, a template text on
 *      one line (PRD-3), or comes from the server already translated.
 * R4 — the server decides: `can_edit` hides the doors a reader may not use,
 *      and every call is gated again on the server.
 */
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit, pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";
import { openHub } from "@pb_hub/js/hub_nav";

const MODEL = "pb.shift.patterns";
const PAGE = 40;
const LETTERS = "ABCDEFGH";
const WEEK_CHOICES = [1, 2, 4, 6, 8, 12];
const CYCLE_CHOICES = [7, 14, 21, 28, 8];
const GLANCE_FILTERS = {
    nobody: { use: ["nobody"] },
};
const PREVIEW_DAYS = 14;
const ARRIVALS_SEEN = new WeakSet();

/** ISO "2026-12-07" -> a UTC Date, so day maths never meets a clock change. */
function toDate(iso) {
    const [y, m, d] = (iso || "").split("-").map(Number);
    return new Date(Date.UTC(y || 1970, (m || 1) - 1, d || 1));
}
function toIso(dt) { return dt.toISOString().slice(0, 10); }
function addDays(iso, n) { const d = toDate(iso); d.setUTCDate(d.getUTCDate() + n); return toIso(d); }
function daysBetween(a, b) { return Math.round((toDate(b) - toDate(a)) / 86400000); }
function mondayOf(iso) { const d = toDate(iso); return addDays(iso, -((d.getUTCDay() + 6) % 7)); }
function mod(n, m) { return ((n % m) + m) % m; }

export class PbShiftPatterns extends Component {
    static template = "pb_shift_patterns.PbShiftPatterns";
    static components = { PbFilterLayout, WfDrawer };
    static props = ["*"];

    get searchLabel() { return _t("Find a pattern, a department or a person…"); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.state = useState({
            loaded: false, allowed: true, why: "", canEdit: false,
            kpis: {}, total: 0, templates: [], departments: [], archived: [],
            today: "", thisMonday: "", maxWeeks: 12, maxCycle: 56, maxTeams: 8,
            rows: [], listTotal: 0, listLoaded: false, listError: false, loadingMore: false,
            showArchived: false,
            edit: null,
            make: null,
        });
        this.kit = useFilterKit({
            model: MODEL,
            noun: _t("patterns"),
            onChange: () => this.loadPage(),
        });
        this._peopleSeq = 0;
        this._peopleTimer = null;
        onWillStart(async () => {
            await this.load();
            if (!this.state.allowed) { this.state.listLoaded = true; }
        });
        onMounted(() => this._arrival(0));
    }

    /**
     * ⌘K "Make shifts from a pattern" arrives with pb_focus = "make". The
     * action service makes the new action "current" only after the screen
     * has mounted, so this looks a few times, briefly. Consumed once per
     * action: switching lens and back must not pop the panel up again.
     */
    _arrival(tries) {
        const act = this.action.currentController?.action;
        const ctx = act?.context || {};
        if (act && ctx.pb_focus === "make") {
            if (!ARRIVALS_SEEN.has(act)) {
                ARRIVALS_SEEN.add(act);
                if (this.state.canEdit && this.state.total) { this.openMake(); }
            }
            return;
        }
        if (tries < 10) { setTimeout(() => this._arrival(tries + 1), 100); }
    }

    icon(name, size = 16) { return pbfIcon(name, size); }
    fmtInt(n) { return Number(n || 0).toLocaleString(); }

    // ================================================================ board
    async load() {
        try {
            const d = await this.orm.call(MODEL, "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed !== false, why: d.why || "",
                canEdit: !!d.can_edit, kpis: d.kpis || {}, total: d.total || 0,
                templates: d.templates || [], departments: d.departments || [],
                archived: d.archived || [], today: d.today || "",
                thisMonday: d.this_monday || "", maxWeeks: d.max_weeks || 12,
                maxCycle: d.max_cycle || 56, maxTeams: d.max_teams || 8,
                companyId: d.company_id || false,
            });
        } catch (e) {
            console.warn("pb_shift_patterns: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The patterns could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) { this.state.listLoaded = true; return; }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call(MODEL, "get_page", [], this.kit.kw({
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            }));
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.listTotal = d.total;
            this.state.listLoaded = true;
            this.state.listError = false;
        } catch (e) {
            if (!this.kit.isCurrent(q.seq)) { return; }
            console.error("pb_shift_patterns: the patterns could not load", e);
            if (!more) { this.state.listError = true; this.state.listLoaded = true; }
            this.notif.add(_t("The patterns could not load. Check your connection, then press Try again."),
                           { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    retry() { this.state.listError = false; this.state.listLoaded = false; this.kit.refresh(); }
    get hasMore() { return this.state.rows.length < this.state.listTotal; }
    async refresh() {
        const before = this.state.total;
        await this.load();
        // a pattern made or archived changes what the panel and its
        // "of N" are judged on: lay the kit out again, not only recount
        if (before !== this.state.total) { await this.kit.load(); } else { await this.kit.refresh(); }
    }

    get headline() {
        const k = this.state.kpis || {};
        if (!k.patterns) { return _t("No patterns yet."); }
        if (k.drafts) {
            return _t("%(n)s draft shifts made from patterns are waiting to be published.",
                      { n: this.fmtInt(k.drafts) });
        }
        if (k.patterns === 1) {
            return _t("1 pattern, %(n)s people on it. Nothing waiting to be published.",
                      { n: this.fmtInt(k.people) });
        }
        return _t("%(p)s patterns, %(n)s people on them. Nothing waiting to be published.",
                  { p: this.fmtInt(k.patterns), n: this.fmtInt(k.people) });
    }

    get glance() {
        const k = this.state.kpis || {};
        return [
            { key: "patterns", n: k.patterns || 0, label: _t("patterns"), tone: "", run: null },
            { key: "people", n: k.people || 0, label: _t("people on a pattern"), tone: "", run: null },
            { key: "drafts", n: k.drafts || 0, label: _t("drafts to publish"),
              tone: k.drafts ? "amber" : "", run: k.drafts ? () => this.openSchedule() : null },
            { key: "nobody", n: k.nobody || 0, label: _t("with nobody yet"),
              tone: k.nobody ? "amber" : "",
              run: () => this.kit.toggleFilters(GLANCE_FILTERS.nobody) },
        ];
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        return this.kit.isExactly(GLANCE_FILTERS.nobody) ? "nobody" : "";
    }

    tone(color) { return "t" + (Math.abs(Number(color) || 0) % 8); }
    template(id) { return this.state.templates.find((t) => t.id === id) || null; }

    needLabel(rw) {
        if (rw.need === "cycle") { return _t("No working days yet"); }
        if (rw.need === "people") { return _t("Nobody on it yet"); }
        return "";
    }
    teamsLabel(rw) {
        return rw.teams === 1 ? _t("1 team") : _t("%(n)s teams", { n: rw.teams });
    }
    peopleLabel(rw) {
        return rw.people === 1 ? _t("1 person") : _t("%(n)s people", { n: this.fmtInt(rw.people) });
    }
    madeLabel(rw) {
        return rw.made_to_label ? _t("Drafts made up to %(d)s", { d: rw.made_to_label })
            : _t("No drafts made yet");
    }

    openSchedule() {
        openHub(this.action, { xmlid: "pb_mission.action_pb_workforce",
                               lens: "schedule", lensKey: "pb_shell_lens" });
    }

    // ================================================================ edit
    blankForm() {
        return {
            id: 0, name: "", department_id: false, start_date: this.state.thisMonday,
            cycle_days: 14, work_on_holidays: false, note: "",
            slots: new Array(14).fill(false),
            teams: [{ key: "k0", name: _t("Team A"), offset: 0 }],
            members: [],
            drafts: 0, published: 0, made_to_label: "",
        };
    }

    newPattern(preset = "") {
        const form = this.blankForm();
        if (preset) { this.applyPreset(form, preset); }
        this.state.edit = { form, busy: false, brush: this.defaultBrush(), peopleQuery: "",
                            peopleRows: [], peopleTeam: form.teams[0].key, peopleBusy: false,
                            error: "", isNew: true };
    }

    defaultBrush() {
        const t = this.state.templates[0];
        return t ? t.id : "off";
    }

    pickTemplate(kind) {
        const list = this.state.templates;
        return (list.find((t) => t.shift_type === kind) || list[kind === "night" ? 1 : 0]
                || list[0] || {}).id || false;
    }

    applyPreset(form, preset) {
        const day = this.pickTemplate("morning");
        const night = this.pickTemplate("night");
        if (preset === "swap") {
            form.name = _t("Days and nights, swap weekly");
            form.cycle_days = 14;
            form.slots = new Array(14).fill(false);
            for (const i of [0, 1, 2, 3, 4]) { form.slots[i] = day; form.slots[i + 7] = night; }
            form.teams = [{ key: "k0", name: _t("Team A"), offset: 0 },
                          { key: "k1", name: _t("Team B"), offset: 7 }];
        } else if (preset === "four") {
            form.name = _t("4 on, 4 off");
            form.cycle_days = 8;
            form.slots = [day, day, night, night, false, false, false, false];
            form.teams = [0, 2, 4, 6].map((o, i) => ({
                key: "k" + i, name: _t("Team %(l)s", { l: LETTERS[i] }), offset: o }));
        } else {
            form.name = _t("Weekdays");
            form.cycle_days = 7;
            form.slots = [day, day, day, day, day, false, false];
        }
    }

    async openPattern(id) {
        try {
            const d = await this.orm.call(MODEL, "get_pattern", [id]);
            const slots = new Array(d.cycle_days).fill(false);
            for (const s of d.slots) { if (s.day < d.cycle_days) { slots[s.day] = s.template_id; } }
            const form = {
                id: d.id, name: d.name, department_id: d.department_id,
                start_date: d.start_date, cycle_days: d.cycle_days,
                work_on_holidays: d.work_on_holidays, note: d.note,
                slots, teams: d.teams, members: d.members,
                drafts: d.drafts, published: d.published, made_to_label: d.made_to_label,
            };
            this.state.edit = { form, busy: false, brush: this.defaultBrush(), peopleQuery: "",
                                peopleRows: [], peopleTeam: (d.teams[0] || {}).key || "",
                                peopleBusy: false, error: "", isNew: false };
        } catch (e) {
            console.warn("pb_shift_patterns: the pattern could not open", e);
            this.notif.add(e?.data?.message || _t("The pattern could not be opened."),
                           { type: "warning" });
            this.refresh();
        }
    }

    closeEdit() { this.state.edit = null; }
    makeFromEdit() {
        const id = this.state.edit?.form.id;
        this.closeEdit();
        if (id) { this.openMake([id]); }
    }
    get offLabel() { return _t("Off"); }
    get makeTitle() { return _t("Make draft shifts"); }
    get makeSubtitle() {
        return _t("Nothing is published. You check the drafts in the Schedule, then publish them there.");
    }

    get editTitle() {
        const e = this.state.edit;
        if (!e) { return ""; }
        return e.isNew ? _t("New pattern") : (e.form.name || _t("Pattern"));
    }
    get editSubtitle() {
        const e = this.state.edit;
        if (!e) { return ""; }
        return this.state.canEdit ? _t("Set the cycle once. Each team follows it from its own start.")
            : _t("You can look at this pattern. Attendance managers change it.");
    }

    setCycle(n) {
        const f = this.state.edit.form;
        n = Math.max(1, Math.min(this.state.maxCycle, parseInt(n, 10) || 1));
        const slots = new Array(n).fill(false);
        for (let i = 0; i < n; i++) { slots[i] = f.slots[i % Math.max(1, f.slots.length)] || false; }
        if (n < f.slots.length) { for (let i = 0; i < n; i++) { slots[i] = f.slots[i] || false; } }
        f.slots = slots;
        f.cycle_days = n;
        for (const t of f.teams) { t.offset = mod(t.offset || 0, n); }
    }

    cycleLabel(n) {
        if (n % 7 === 0) {
            return n === 7 ? _t("1 week") : _t("%(n)s weeks", { n: n / 7 });
        }
        return _t("%(n)s days", { n });
    }

    get cycleWeeks() {
        const f = this.state.edit.form;
        const out = [];
        for (let w = 0; w * 7 < f.cycle_days; w++) {
            const cells = [];
            for (let i = w * 7; i < Math.min(f.cycle_days, w * 7 + 7); i++) {
                const iso = addDays(f.start_date || this.state.thisMonday, i);
                const t = this.template(f.slots[i]);
                cells.push({
                    i, n: i + 1,
                    weekday: toDate(iso).toLocaleDateString(undefined, { weekday: "short", timeZone: "UTC" }),
                    t,
                });
            }
            out.push({ w, cells });
        }
        return out;
    }

    paint(i) {
        if (!this.state.canEdit) { return; }
        const e = this.state.edit;
        e.form.slots[i] = e.brush === "off" ? false : e.brush;
    }
    setBrush(id) { this.state.edit.brush = id; }
    fillWeekdays() {
        const e = this.state.edit;
        if (e.brush === "off") { return; }
        const start = toDate(e.form.start_date || this.state.thisMonday);
        for (let i = 0; i < e.form.cycle_days; i++) {
            const d = new Date(start); d.setUTCDate(d.getUTCDate() + i);
            const wd = (d.getUTCDay() + 6) % 7;
            if (wd < 5) { e.form.slots[i] = e.brush; }
        }
    }
    clearCycle() { const f = this.state.edit.form; f.slots = new Array(f.cycle_days).fill(false); }

    get workingDays() { return this.state.edit.form.slots.filter(Boolean).length; }

    // ------------------------------------------------------------ teams
    addTeam() {
        const f = this.state.edit.form;
        if (f.teams.length >= this.state.maxTeams) { return; }
        const i = f.teams.length;
        f.teams.push({ key: "n" + Date.now(), name: _t("Team %(l)s", { l: LETTERS[i] }), offset: 0 });
        this.spaceTeams();
    }
    removeTeam(key) {
        const f = this.state.edit.form;
        if (f.teams.length <= 1) { return; }
        f.teams = f.teams.filter((t) => t.key !== key);
        for (const m of f.members) { if (m.team_key === key) { m.team_key = f.teams[0].key; } }
        if (this.state.edit.peopleTeam === key) { this.state.edit.peopleTeam = f.teams[0].key; }
    }
    spaceTeams() {
        const f = this.state.edit.form;
        const n = f.teams.length;
        f.teams.forEach((t, i) => { t.offset = Math.round((i * f.cycle_days) / n) % f.cycle_days; });
    }
    setOffset(t, v) {
        const f = this.state.edit.form;
        t.offset = mod(parseInt(v, 10) || 0, f.cycle_days);
    }
    teamCount(key) { return this.state.edit.form.members.filter((m) => m.team_key === key).length; }
    teamMembers(key) { return this.state.edit.form.members.filter((m) => m.team_key === key); }
    teamName(key) { return (this.state.edit.form.teams.find((t) => t.key === key) || {}).name || ""; }

    /** Two weeks from today (or day 1) for every team — the rota at a glance. */
    get previewRows() {
        const f = this.state.edit.form;
        const from = (f.start_date && f.start_date > this.state.today) ? f.start_date
            : mondayOf(this.state.today || f.start_date);
        const days = [];
        for (let i = 0; i < PREVIEW_DAYS; i++) {
            const iso = addDays(from, i);
            const d = toDate(iso);
            days.push({ iso, day: d.getUTCDate(),
                        weekday: d.toLocaleDateString(undefined, { weekday: "narrow", timeZone: "UTC" }),
                        weekend: [0, 6].includes(d.getUTCDay()) });
        }
        const rows = f.teams.map((t) => ({
            key: t.key, name: t.name, people: this.teamCount(t.key),
            cells: days.map((dy) => {
                const idx = mod(daysBetween(f.start_date || from, dy.iso) - (t.offset || 0), f.cycle_days);
                return { iso: dy.iso, t: this.template(f.slots[idx]), weekend: dy.weekend };
            }),
        }));
        return { days, rows };
    }

    // ------------------------------------------------------------ people
    onPeopleInput(ev) {
        this.state.edit.peopleQuery = ev.target.value;
        clearTimeout(this._peopleTimer);
        this._peopleTimer = setTimeout(() => this.findPeople(), 220);
    }
    async findPeople() {
        const e = this.state.edit;
        if (!e) { return; }
        const seq = ++this._peopleSeq;
        e.peopleBusy = true;
        try {
            const rows = await this.orm.call(MODEL, "find_people", [e.peopleQuery || "", 12]);
            if (seq !== this._peopleSeq || !this.state.edit) { return; }
            e.peopleRows = rows;
        } catch (err) {
            console.warn("pb_shift_patterns: people search failed", err);
        } finally {
            if (seq === this._peopleSeq && this.state.edit) { e.peopleBusy = false; }
        }
    }
    isMember(id) { return this.state.edit.form.members.some((m) => m.employee_id === id); }
    addPerson(p) {
        const e = this.state.edit;
        if (this.isMember(p.employee_id)) { return; }
        e.form.members.push({ ...p, team_key: e.peopleTeam || e.form.teams[0].key,
                              date_from: "", date_to: "" });
    }
    removePerson(m) {
        const f = this.state.edit.form;
        f.members = f.members.filter((x) => x !== m);
    }
    moveTeam(m, key) { m.team_key = key; }

    // ------------------------------------------------------------ save
    async save() {
        const e = this.state.edit;
        if (!e || e.busy) { return; }
        const f = e.form;
        e.busy = true;
        e.error = "";
        const vals = {
            name: f.name, department_id: f.department_id || false, start_date: f.start_date,
            cycle_days: f.cycle_days, work_on_holidays: f.work_on_holidays, note: f.note,
            slots: f.slots.map((tid, day) => ({ day, template_id: tid || false })).filter((s) => s.template_id),
            teams: f.teams.map((t) => ({ key: t.key, name: t.name, offset: t.offset })),
            members: f.members.map((m) => ({ employee_id: m.employee_id, team_key: m.team_key,
                                              date_from: m.date_from || false, date_to: m.date_to || false })),
        };
        try {
            await this.orm.call(MODEL, "save_pattern", [vals, f.id || false]);
            this.notif.add(_t("Pattern saved."), { type: "success" });
            this.state.edit = null;
            await this.refresh();
        } catch (err) {
            e.error = err?.data?.message || _t("The pattern could not be saved.");
        } finally {
            if (this.state.edit) { e.busy = false; }
        }
    }

    async archive(archive = true, id = 0) {
        const pid = id || this.state.edit?.form.id;
        if (!pid) { return; }
        try {
            await this.orm.call(MODEL, "archive_pattern", [pid, archive]);
            this.notif.add(archive ? _t("Pattern archived. Shifts it made are kept.")
                : _t("Pattern restored."), { type: "success" });
            this.state.edit = null;
            await this.refresh();
        } catch (err) {
            this.notif.add(err?.data?.message || _t("That did not work."), { type: "warning" });
        }
    }

    async clearDrafts() {
        const e = this.state.edit;
        if (!e || !e.form.id) { return; }
        try {
            const res = await this.orm.call(MODEL, "clear_drafts", [e.form.id]);
            this.notif.add(_t("%(n)s unpublished drafts removed. Shifts changed by hand and published shifts are kept.",
                              { n: res.removed }), { type: "success" });
            e.form.drafts = res.kept_edited;
            await this.refresh();
        } catch (err) {
            this.notif.add(err?.data?.message || _t("That did not work."), { type: "warning" });
        }
    }

    // ================================================================ make drafts
    openMake(ids = null) {
        const start = this.state.thisMonday ? addDays(this.state.thisMonday, 7) : "";
        const picked = {};
        for (const id of ids || []) { picked[id] = true; }
        // no ids = every pattern that can be filled, read when the list is
        // there (an arrival from ⌘K can come before the list has loaded)
        this.state.make = { picked, auto: !ids, start, weeks: 4, busy: false,
                            preview: null, result: null, error: "" };
    }
    closeMake() { this.state.make = null; }
    get usableIds() { return this.state.rows.filter((r) => !r.need).map((r) => r.id); }
    isPicked(id) {
        const m = this.state.make;
        return m.auto ? this.usableIds.includes(id) : !!m.picked[id];
    }
    togglePick(id) {
        const m = this.state.make;
        if (m.auto) {
            m.picked = {};
            for (const x of this.usableIds) { m.picked[x] = true; }
            m.auto = false;
        }
        m.picked[id] = !m.picked[id];
        m.preview = null;
    }
    get pickedIds() {
        const m = this.state.make;
        if (!m) { return []; }
        return m.auto ? this.usableIds : Object.keys(m.picked).filter((k) => m.picked[k]).map(Number);
    }
    setWeeks(n) { this.state.make.weeks = n; this.state.make.preview = null; }
    setStart(ev) { this.state.make.start = ev.target.value ? mondayOf(ev.target.value) : ""; this.state.make.preview = null; }
    get weekChoices() { return WEEK_CHOICES.filter((n) => n <= this.state.maxWeeks); }
    get cycleChoices() { return CYCLE_CHOICES.filter((n) => n <= this.state.maxCycle); }

    async check() {
        const m = this.state.make;
        if (!m || m.busy || !this.pickedIds.length) { return; }
        m.busy = true; m.error = "";
        try {
            m.preview = await this.orm.call(MODEL, "preview", [this.pickedIds, m.start, m.weeks]);
        } catch (err) {
            m.error = err?.data?.message || _t("The check could not run.");
        } finally {
            m.busy = false;
        }
    }

    async makeDrafts() {
        const m = this.state.make;
        if (!m || m.busy || !this.pickedIds.length) { return; }
        m.busy = true; m.error = "";
        try {
            m.result = await this.orm.call(MODEL, "make_drafts", [this.pickedIds, m.start, m.weeks]);
            m.preview = null;
            await this.refresh();
        } catch (err) {
            m.error = err?.data?.message || _t("The drafts could not be made.");
        } finally {
            m.busy = false;
        }
    }

    // ------------------------------------------------------------ sentences
    // One msgid per sentence (PRD-3 / W80.2): a translator cannot reorder
    // fragments split around a number.
    reportHeadline(r) {
        return _t("%(n)s draft shifts for %(p)s people", { n: this.fmtInt(r.created), p: this.fmtInt(r.people) });
    }
    doneTitle(r) { return _t("%(n)s draft shifts made", { n: this.fmtInt(r.created) }); }
    listedNote(r) { return _t("The first %(n)s are listed.", { n: this.fmtInt(r.skipped.length) }); }
    get cycleSummary() {
        const f = this.state.edit.form;
        return _t("%(n)s working days in %(cycle)s", { n: this.workingDays, cycle: this.cycleLabel(f.cycle_days) });
    }
    alsoOnLabel(names, capital = false) {
        const list = (names || []).join(", ");
        return capital ? _t("Also on %(names)s", { names: list }) : _t("on %(names)s", { names: list });
    }
    draftsLabel(n) { return _t("%(n)s drafts to publish", { n: this.fmtInt(n) }); }
    countPeople(n) { return n === 1 ? _t("1 person") : _t("%(n)s people", { n: this.fmtInt(n) }); }
    get onPatternLabel() {
        return _t("%(n)s on this pattern", { n: this.fmtInt(this.state.edit.form.members.length) });
    }
    weekChoiceLabel(n) { return n === 1 ? _t("1 week") : _t("%(n)s weeks", { n }); }

    reasonLabel(code) {
        return {
            leave_approved: _t("On approved leave"),
            holiday: _t("Public holiday"),
            overlap: _t("Already has a shift"),
            young_worker_night: _t("Night work not allowed"),
            ot_ceiling: _t("Near the overtime limit"),
            refused: _t("Refused"),
        }[code] || _t("Other");
    }
    reasonChips(rep) {
        return Object.entries(rep.counts || {}).map(([code, n]) => ({ code, n, label: this.reasonLabel(code) }));
    }
    dayLabel(iso) {
        return toDate(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric",
                                                           month: "short", timeZone: "UTC" });
    }
}

registry.category("actions").add("pb_shift_patterns", PbShiftPatterns);
