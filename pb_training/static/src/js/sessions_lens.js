/** @odoo-module **/
/**
 * Learning › Courses › SESSIONS (LEARNING L4) — training in a room or on
 * site.
 *
 * HERO MOMENT: the WEEK STRIP — seven columns from today, a dot per session,
 * today ringed; press a day to see only that day's sessions. Under it the four
 * quiet numbers (this week · seats free · waiting · did not come in 30 days)
 * and "N to close" when a session ended and nobody closed it.
 *
 * Session cards: course, kind chip, when / where, trainer, "12 of 20 seats ·
 * 3 waiting", state chip (amber when full with people waiting or waiting to be
 * closed, rose when cancelled). A card opens the SESSION PAGE: header, the
 * people with per-row Mark attended / Did not come / Remove, Book people,
 * Send the invitations, Start the session, Close the session, Cancel, the
 * attendance spreadsheet and the printable sign-in sheet with its QR code.
 *
 * "Start the session" opens the ATTENDANCE SCREEN: full screen, the big QR,
 * the course and time, "14 of 20 here" (asks every 10 seconds), the roster
 * ticking itself as people scan, a tick per row, "Everyone is here" and
 * "Close the session".
 *
 * Reads `pb.training.sessions_board` / `session_page` / `session_lists` /
 * `attendance_poll`; writes through `pb.training.act`.
 */
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { PbToolboxDrawer, fromServerUtc, toLocalInput, toServerUtc } from "@pb_training/js/toolbox_drawer";

/** The context key Courses reads a Sessions filter from (Overview's chip). */
export const SESSION_STATE_KEY = "pb_training_session_state";
/** The context key Courses reads a session to open from (the course drawer). */
export const SESSION_OPEN_KEY = "pb_training_session_open";

const POLL_MS = 10000;

function blankSession() {
    const start = new Date();
    start.setDate(start.getDate() + 7);
    start.setHours(9, 0, 0, 0);
    return { id: 0, channel_id: 0, new_course: "", kind: "classroom",
             start: toLocalInput(start), minutes: 120, place: "", join_url: "",
             trainer_id: 0, trainer_name: "", seats: 20, hours: 0, cost: 0 };
}

function blankBook() {
    return { mode: "people", picked: [], department_id: 0, job_id: 0 };
}

export class PbSessionsLens extends Component {
    static template = "pb_training.PbSessionsLens";
    static components = { PbToolboxDrawer };
    static props = {
        embedded: { type: Boolean, optional: true },
        startState: { type: String, optional: true },
        startSession: { type: Number, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            failed: false,
            data: { upcoming: [], past: [], week: [], kpis: {} },
            f: { day: "", state: this.props.startState === "to_close" ? "to_close" : "", q: "" },
            page: null,
            lists: null,
            drawer: "",
            form: blankSession(),
            courseMode: "course",
            trainerTerm: "",
            trainers: [],
            book: blankBook(),
            people: [],
            peopleTerm: "",
            saving: false,
            acting: "",
            screen: null,
        });
        onWillStart(async () => {
            await this.load();
            if (this.props.startSession) { await this.openSession(this.props.startSession); }
        });
        onWillUnmount(() => this.stopPoll());
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        this.state.failed = false;
        try {
            this.state.data = await this.orm.call("pb.training", "sessions_board", [{ ...this.state.f }]);
        } catch (e) {
            console.warn("pb_training: the sessions could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() { this.state.loaded = false; await this.load(); }

    get data() { return this.state.data || {}; }
    get allowed() { return this.data.allowed !== false; }
    get kpis() { return this.data.kpis || {}; }
    get week() { return this.data.week || []; }
    get upcoming() { return this.data.upcoming || []; }
    get past() { return this.data.past || []; }

    get glance() {
        const k = this.kpis;
        const tone = (v, t) => (v ? t : "");
        return [
            { key: "this_week", n: k.this_week || 0, label: _t("Sessions in the next 7 days"), tone: "", run: null },
            { key: "seats_free", n: k.seats_free || 0, label: _t("Seats still free"), tone: "", run: null },
            { key: "waiting", n: k.waiting || 0, label: _t("Waiting for a seat"), tone: tone(k.waiting, "amber"), run: null },
            { key: "no_shows", n: k.no_shows_30d || 0, label: _t("Did not come, last 30 days"), tone: tone(k.no_shows_30d, "rose"), run: null },
            { key: "to_close", n: k.to_close || 0, label: _t("Ended, still to close"), tone: tone(k.to_close, "amber"), run: () => this.toggleToClose() },
        ];
    }

    dots(day) { return Array.from({ length: Math.min(day.count, 4) }, (_v, i) => i); }

    pickDay(day) {
        this.state.f.day = this.state.f.day === day.date ? "" : day.date;
        this.state.f.state = "";
        this.load();
    }

    toggleToClose() {
        this.state.f.state = this.state.f.state === "to_close" ? "" : "to_close";
        this.state.f.day = "";
        this.load();
    }

    onSearch(ev) {
        this.state.f.q = ev.target.value;
        clearTimeout(this._qTimer);
        this._qTimer = setTimeout(() => this.load(), 250);
    }

    clearFilters() {
        this.state.f = { day: "", state: "", q: "" };
        this.load();
    }

    get anyFilter() { const f = this.state.f; return !!(f.day || f.state || f.q); }

    dayLabel(date) {
        const day = this.week.find((d) => d.date === date);
        return day ? `${day.weekday} ${day.day}` : date;
    }

    stateClass(card) {
        if (card.state === "cancelled") { return "is-bad"; }
        if (card.to_close) { return "is-warn"; }
        if (card.state === "closed") { return "is-ok"; }
        if (card.state === "held") { return "is-go"; }
        return "";
    }

    attClass(row) {
        return { attended: "is-ok", no_show: "is-bad", waitlisted: "is-warn", booked: "is-go" }[row.state] || "";
    }

    // ------------------------------------------------------------- one session
    async openSession(id) {
        this.state.page = { id, loading: true };
        await this.loadPage(id);
    }

    async loadPage(id) {
        const sid = id || (this.state.page && this.state.page.id);
        if (!sid) { return; }
        try {
            this.state.page = await this.orm.call("pb.training", "session_page", [sid]);
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That session could not be read just now."), { type: "danger" });
            this.state.page = null;
        }
    }

    closePage() { this.state.page = null; this.load(); }

    get page() { return this.state.page; }

    async act(verb, payload, key = verb) {
        this.state.acting = key;
        try {
            const res = await this.orm.call("pb.training", "act", [verb, payload]);
            if (res && res.message) { this.notif.add(res.message, { type: res.type || "success" }); }
            return res || {};
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
            return null;
        } finally {
            this.state.acting = "";
        }
    }

    async pageVerb(verb) {
        const res = await this.act(verb, { session_id: this.page.id });
        if (res) { await this.loadPage(); }
        return res;
    }

    async mark(row, state) {
        const res = await this.act("mark_attendance", { attendance_id: row.id, state }, `row${row.id}`);
        if (res) {
            if (this.state.screen) { await this.poll(); } else { await this.loadPage(); }
        }
    }

    async remove(row) {
        const res = await this.act("remove_booking", { attendance_id: row.id }, `row${row.id}`);
        if (res) { await this.loadPage(); }
    }

    async downloadSheet() {
        const res = await this.act("attendance_xlsx", { session_id: this.page.id }, "xlsx");
        if (res && res.file_b64) {
            const link = document.createElement("a");
            link.href = `data:${res.mimetype};base64,${res.file_b64}`;
            link.download = res.filename || "attendance.xlsx";
            document.body.appendChild(link);
            link.click();
            link.remove();
        }
    }

    printSheet() { window.open(this.page.pdf_url, "_blank", "noopener"); }

    // ------------------------------------------------------------- the attendance screen
    async startScreen() {
        if (this.page.can_start) {
            const res = await this.act("start_session", { session_id: this.page.id }, "start");
            if (!res) { return; }
            await this.loadPage();
        }
        this.state.screen = { here: 0, expected: 0, here_words: "", roster: [] };
        await this.poll();
        this.stopPoll();
        this._poll = setInterval(() => this.poll(), POLL_MS);
    }

    async poll() {
        if (!this.page) { return; }
        try {
            const d = await this.orm.call("pb.training", "attendance_poll", [this.page.id]);
            if (this.state.screen) { this.state.screen = d; }
        } catch (e) {
            console.warn("pb_training: the attendance count could not be read", e);
        }
    }

    stopPoll() { if (this._poll) { clearInterval(this._poll); this._poll = null; } }

    async closeScreen() {
        this.stopPoll();
        this.state.screen = null;
        await this.loadPage();
    }

    async everyoneHere() {
        const res = await this.act("everyone_here", { session_id: this.page.id }, "all");
        if (res) { await this.poll(); }
    }

    async closeFromScreen() {
        const res = await this.act("close_session", { session_id: this.page.id }, "close");
        if (res) { await this.closeScreen(); }
    }

    get screenPercent() {
        const s = this.state.screen || {};
        return s.expected ? Math.round((100 * s.here) / s.expected) : 0;
    }

    // ------------------------------------------------------------- lists
    async ensureLists() {
        if (!this.state.lists) {
            try {
                this.state.lists = await this.orm.call("pb.training", "session_lists", []);
            } catch (e) {
                console.warn("pb_training: the session lists could not be read", e);
                this.state.lists = { courses: [], kinds: [], departments: [], jobs: [] };
            }
        }
        return this.state.lists;
    }

    get lists() { return this.state.lists || { courses: [], kinds: [], departments: [], jobs: [] }; }

    // ------------------------------------------------------------- the session drawer
    async newSession(channelId = 0) {
        await this.ensureLists();
        const form = blankSession();
        if (channelId) { form.channel_id = channelId; }
        const course = this.lists.courses.find((c) => c.id === form.channel_id);
        if (course && course.hours) { form.minutes = Math.round(course.hours * 60); }
        Object.assign(this.state, { drawer: "session", form, courseMode: this.lists.courses.length ? "course" : "new",
                                    trainerTerm: "", trainers: [] });
    }

    async editSession() {
        await this.ensureLists();
        const v = this.page.values || {};
        Object.assign(this.state, {
            drawer: "session", courseMode: "course",
            form: Object.assign(blankSession(), v, { start: fromServerUtc(v.start), new_course: "" }),
            trainerTerm: this.page.trainer || "", trainers: [],
        });
    }

    closeDrawer() { this.state.drawer = ""; }

    setField(field, ev, kind = "text") {
        let value = ev.target.value;
        if (kind === "int") { value = Number(value) || 0; }
        if (kind === "float") { value = Number(value) || 0; }
        this.state.form[field] = value;
        if (field === "channel_id") {
            const course = this.lists.courses.find((c) => c.id === value);
            if (course && course.hours && !this.state.form.id) { this.state.form.minutes = Math.round(course.hours * 60); }
        }
    }

    setCourseMode(mode) { this.state.courseMode = mode; }

    async onTrainerTerm(ev) {
        this.state.trainerTerm = ev.target.value;
        this.state.form.trainer_id = 0;
        this.state.form.trainer_name = ev.target.value;
        clearTimeout(this._tTimer);
        this._tTimer = setTimeout(async () => {
            if (!this.state.trainerTerm.trim()) { this.state.trainers = []; return; }
            try {
                this.state.trainers = (await this.orm.call("pb.training", "session_people", [this.state.trainerTerm])).slice(0, 8);
            } catch (e) {
                this.state.trainers = [];
            }
        }, 220);
    }

    pickTrainer(emp) {
        this.state.form.trainer_id = emp.id;
        this.state.form.trainer_name = "";
        this.state.trainerTerm = emp.name;
        this.state.trainers = [];
    }

    get sessionHint() {
        const f = this.state.form;
        if (this.state.courseMode === "course" && !f.channel_id) { return _t("Pick the course this session is for."); }
        if (this.state.courseMode === "new" && !f.new_course.trim()) { return _t("Name the new classroom course."); }
        if (!f.start) { return _t("Say when the session starts."); }
        return "";
    }

    get canSaveSession() { return !this.sessionHint && !this.state.saving; }

    async saveSession() {
        if (!this.canSaveSession) { return; }
        const f = this.state.form;
        const payload = Object.assign({}, f, {
            start: toServerUtc(f.start),
            channel_id: this.state.courseMode === "course" ? f.channel_id : 0,
            new_course: this.state.courseMode === "new" ? f.new_course : "",
        });
        this.state.saving = true;
        try {
            const res = await this.orm.call("pb.training", "act", ["save_session", payload]);
            this.notif.add((res && res.message) || _t("Saved."), { type: "success" });
            this.state.drawer = "";
            this.state.lists = null;
            await this.load();
            if (res && res.id) { await this.openSession(res.id); }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    // ------------------------------------------------------------- the book drawer
    async openBook() {
        await this.ensureLists();
        Object.assign(this.state, { drawer: "book", book: blankBook(), peopleTerm: "", people: [] });
        await this.searchPeople();
    }

    setBookMode(mode) { this.state.book.mode = mode; }

    setBook(field, ev) { this.state.book[field] = Number(ev.target.value) || 0; }

    async searchPeople() {
        try {
            this.state.people = await this.orm.call("pb.training", "session_people", [this.state.peopleTerm]);
        } catch (e) {
            console.warn("pb_training: the people search failed", e);
            this.state.people = [];
        }
    }

    onPeopleTerm(ev) {
        this.state.peopleTerm = ev.target.value;
        clearTimeout(this._pTimer);
        this._pTimer = setTimeout(() => this.searchPeople(), 220);
    }

    isPicked(emp) { return this.state.book.picked.some((p) => p.id === emp.id); }

    togglePerson(emp) {
        const list = this.state.book.picked;
        const at = list.findIndex((p) => p.id === emp.id);
        if (at >= 0) { list.splice(at, 1); } else { list.push({ id: emp.id, name: emp.name }); }
    }

    get canBook() {
        const b = this.state.book;
        if (this.state.saving) { return false; }
        if (b.mode === "people") { return b.picked.length > 0; }
        if (b.mode === "department") { return !!b.department_id; }
        if (b.mode === "job") { return !!b.job_id; }
        return b.mode === "on_course";
    }

    async saveBook() {
        if (!this.canBook) { return; }
        const b = this.state.book;
        const payload = { session_id: this.page.id };
        if (b.mode === "people") { payload.employee_ids = b.picked.map((p) => p.id); }
        if (b.mode === "department") { payload.department_id = b.department_id; }
        if (b.mode === "job") { payload.job_id = b.job_id; }
        if (b.mode === "on_course") { payload.on_course = true; }
        this.state.saving = true;
        try {
            const res = await this.orm.call("pb.training", "act", ["book_session", payload]);
            this.notif.add((res && res.message) || _t("Done."), { type: (res && res.type) || "success" });
            this.state.drawer = "";
            await this.loadPage();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    // ------------------------------------------------------------- the toolbox drawer
    openToolbox() { this.state.drawer = "toolbox"; }

    async afterToolbox() { await this.load(); }
}
