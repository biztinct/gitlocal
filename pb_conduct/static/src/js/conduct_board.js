/** @odoo-module **/
/**
 * `pb_conduct_board` — the Conduct tab of Talent (and its own page).
 *
 * THE QUESTION THIS BOARD ANSWERS: which cases are open, which one is waiting
 * on HR, and what comes next. A row is one case; the drawer is the whole case
 * (what happened, the hearing, the decision, the letters, notes, files, the
 * person's earlier cases and the history), with the country notes and the
 * "check with your adviser" line at the top.
 *
 * ONLY NAMED PEOPLE (owner ruling P3). The server answers an explained
 * refusal to anybody else and sends no data; this board just shows it.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in (UPDATES G60).
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`).
 * R3 — every sentence is a `_t()` literal, a one-line template text, or
 *      comes from the server already translated (PRD-3).
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit, pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const PAGE = 60;
const GLANCE_FILTERS = {
    open: { where: ["concern", "hearing", "decision", "letter"] },
    hearing: { where: ["hearing"] },
    decision: { where: ["decision"] },
    letter: { where: ["letter"] },
};

function blankDraft() {
    return { employee_id: 0, employee: "", reason_id: 0, incident_date: "", summary: "", raised_by: "" };
}

export class PbConductBoard extends Component {
    static template = "pb_conduct.PbConductBoard";
    static components = { PbFilterLayout };
    static props = ["*"];

    get stepsLabel() { return _t("Where every case is"); }
    get searchLabel() { return _t("Find a person, a reference or a word…"); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false, allowed: true, why: "", isHead: false,
            kpis: {}, total: 0, reasons: [], outcomes: [], noteKinds: [], validMonths: {},
            rows: [], listTotal: 0, listLoaded: false, listError: false,
            loadingMore: false, stepCounts: {},
            item: null, itemBusy: false, act: null,
            note: { kind: "investigation", body: "" },
            editLetter: null,
            creating: false, draft: blankDraft(), people: [], busy: false,
            setupOpen: false,
        });
        this.kit = useFilterKit({
            model: "pb.conduct",
            noun: _t("cases"),
            onChange: () => this.loadPage(),
        });
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        onWillStart(async () => { await this.load(); });
    }

    icon(name, size = 16) { return pbfIcon(name, size); }

    // ------------------------------------------------------------ loading
    async load() {
        try {
            const d = await this.orm.call("pb.conduct", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed !== false,
                why: d.why || "",
                isHead: !!d.is_head,
                kpis: d.kpis || {},
                total: d.total || 0,
                reasons: d.reasons || [],
                outcomes: d.outcomes || [],
                noteKinds: d.note_kinds || [],
                validMonths: d.valid_months || {},
            });
        } catch (e) {
            console.warn("pb_conduct: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The cases could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.conduct", "get_cases_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.listTotal = d.total;
            if (d.steps) { this.state.stepCounts = d.steps; }
            this.state.listLoaded = true;
            this.state.listError = false;
        } catch (e) {
            if (!this.kit.isCurrent(q.seq)) { return; }
            console.error("pb_conduct: the cases could not load", e);
            if (!more) {
                this.state.listError = true;
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    retry() {
        this.state.listError = false;
        this.state.listLoaded = false;
        this.kit.refresh();
    }
    get hasMore() { return this.state.rows.length < this.state.listTotal; }
    get nextPage() { return Math.min(PAGE, this.state.listTotal - this.state.rows.length); }
    fmtInt(n) { return Number(n || 0).toLocaleString(); }
    async refresh() { await Promise.all([this.load(), this.kit.refresh()]); }

    // --------------------------------------------------------- the quiet board
    get stepDefs() {
        return [
            { key: "concern", title: _t("Concern") },
            { key: "hearing", title: _t("Hearing") },
            { key: "decision", title: _t("Decision") },
            { key: "letter", title: _t("Letter") },
            { key: "closed", title: _t("Closed") },
        ];
    }
    _casesLabel(n) { return n === 1 ? _t("1 case") : _t("%s cases", this.fmtInt(n)); }
    get steps() {
        const counts = this.state.stepCounts || {};
        return this.stepDefs.map((st, i) => {
            const count = counts[st.key] || 0;
            let flag = "";
            if (st.key === "decision" && count) {
                flag = count === 1 ? _t("1 waiting for a decision") : _t("%s waiting for a decision", count);
            } else if (st.key === "letter" && count) {
                flag = count === 1 ? _t("1 letter to issue") : _t("%s letters to issue", count);
            }
            return {
                ...st, n: String(i + 1).padStart(2, "0"), count,
                countLabel: this._casesLabel(count), sub: "", flag, flagTone: "",
                on: this.kit.loaded && this.kit.isOn("where", st.key),
            };
        });
    }
    pickStep(key) {
        const kit = this.kit;
        if (kit.isOn("where", key) && !kit.isExactly({ where: [key] })) {
            kit.toggle("where", key);
            return;
        }
        kit.toggleFilters({ where: [key] });
    }
    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const pick = (id) => () => this.kit.toggleFilters(GLANCE_FILTERS[id]);
        return [
            { key: "open", n: k.open || 0, label: _t("open cases"), tone: "", run: pick("open") },
            { key: "hearing", n: k.hearings_soon || 0, label: _t("hearings in the next 7 days"), tone: tone(k.hearings_soon, "blue"), run: pick("hearing") },
            { key: "decision", n: k.to_decide || 0, label: _t("waiting for a decision"), tone: tone(k.to_decide, "amber"), run: pick("decision") },
            { key: "letter", n: k.letters || 0, label: _t("letters to issue"), tone: tone(k.letters, "amber"), run: pick("letter") },
            { key: "replies", n: k.replies || 0, label: _t("replies from employees to read"), tone: tone(k.replies, "rose"), run: null },
            { key: "live", n: k.live || 0, label: _t("warnings still valid"), tone: "", run: null },
        ];
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    // ------------------------------------------------------------ the drawer
    async openCase(row) {
        this.state.act = null;
        this.state.editLetter = null;
        this.state.itemBusy = true;
        if (!this.state.item || this.state.item.id !== row.id) {
            this.state.item = { ...row, loading: true };
            this.state.note = { kind: "investigation", body: "" };
        }
        try {
            this.state.item = await this.orm.call("pb.conduct", "get_case", [row.id]);
        } catch (e) {
            this.notif.add(this._msg(e, _t("This case could not be opened.")), { type: "danger" });
            this.state.item = null;
        } finally {
            this.state.itemBusy = false;
        }
    }
    closeCase() { this.state.item = null; this.state.act = null; this.state.editLetter = null; }
    get currentNotes() { return ((this.state.item && this.state.item.country_notes) || []).filter((n) => n.current); }
    get otherNotes() { return ((this.state.item && this.state.item.country_notes) || []).filter((n) => !n.current); }

    startAct(verb) {
        const it = this.state.item || {};
        const act = { verb, hearing_date: "", place: it.hearing_place || "", attendees: it.hearing_attendees || "",
                      held_on: "", minutes: "", why: "", outcome: "", summary: "", valid_until: "" };
        if (verb === "plan_hearing" && it.hearing_date_raw) {
            // stored in UTC; the input shows the reader's own clock
            const d = new Date(it.hearing_date_raw.replace(" ", "T") + "Z");
            const pad = (n) => String(n).padStart(2, "0");
            act.hearing_date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        }
        this.state.act = act;
    }
    cancelAct() { this.state.act = null; }
    onAct(field, ev) {
        this.state.act[field] = ev.target.value;
        if (field === "outcome") { this.state.act.valid_until = this._defaultValid(ev.target.value); }
    }
    _defaultValid(outcome) {
        const months = (this.state.validMonths || {})[outcome];
        if (!months) { return ""; }
        const d = new Date();
        d.setMonth(d.getMonth() + months);
        return d.toISOString().slice(0, 10);
    }
    get isWarning() { return this.state.act && ["verbal", "written", "final"].includes(this.state.act.outcome); }
    get actTitle() {
        const verb = this.state.act && this.state.act.verb;
        return {
            plan_hearing: _t("Plan the hearing"),
            hearing_held: _t("Record the hearing"),
            skip_hearing: _t("Go to a decision without a hearing"),
            decide: _t("Record the decision"),
            close: _t("Close the case"),
        }[verb] || "";
    }
    get actHelp() {
        const verb = this.state.act && this.state.act.verb;
        return {
            plan_hearing: _t("Tell the employee in good time and in writing. Prepare an invitation letter from this case once the date is set."),
            hearing_held: _t("The minutes stay with the case. They are never put in the employee's documents and the employee does not see them."),
            skip_hearing: _t("Only when no hearing is needed, for example when you decide to take no action."),
            decide: _t("The decision letter is prepared from it. Check it, then issue it: only then can the employee read it."),
            close: _t("A closed case stays here and in the person's history. You can open it again."),
        }[verb] || "";
    }
    async doAct() {
        const a = this.state.act;
        if (!a) { return; }
        const args = {};
        if (a.verb === "plan_hearing") {
            if (!a.hearing_date) { this.notif.add(_t("Choose the date and time of the hearing."), { type: "warning" }); return; }
            const utc = new Date(a.hearing_date).toISOString().slice(0, 19).replace("T", " ");
            Object.assign(args, { hearing_date: utc, place: a.place, attendees: a.attendees });
        } else if (a.verb === "hearing_held") {
            Object.assign(args, { held_on: a.held_on, minutes: a.minutes });
        } else if (a.verb === "skip_hearing" || a.verb === "close") {
            if (!a.why.trim()) { this.notif.add(_t("Say why, in a few words."), { type: "warning" }); return; }
            args.why = a.why;
        } else if (a.verb === "decide") {
            if (!a.outcome) { this.notif.add(_t("Choose what was decided."), { type: "warning" }); return; }
            if (!a.summary.trim()) { this.notif.add(_t("Write the decision in a few sentences. It goes in the letter."), { type: "warning" }); return; }
            Object.assign(args, { outcome: a.outcome, summary: a.summary, valid_until: this.isWarning ? a.valid_until : "" });
        }
        await this.move(a.verb, args);
    }
    async move(verb, args = {}) {
        const it = this.state.item;
        if (!it) { return; }
        this.state.itemBusy = true;
        try {
            const res = await this.orm.call("pb.conduct", "move", [it.id, verb, args]);
            this.state.act = null;
            this.notif.add(res.msg || _t("Done."), { type: "success" });
            await this.openCase({ id: it.id });
            await this.refresh();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")), { type: "danger" });
        } finally {
            this.state.itemBusy = false;
        }
    }

    // notes, files, letters
    onNote(field, ev) { this.state.note[field] = ev.target.value; }
    async addNote() {
        const it = this.state.item;
        if (!it || !this.state.note.body.trim()) {
            this.notif.add(_t("Write the note first."), { type: "warning" });
            return;
        }
        await this._call("add_note", [it.id, this.state.note.kind, this.state.note.body]);
        this.state.note = { kind: this.state.note.kind, body: "" };
    }
    async onFile(ev) {
        const it = this.state.item;
        const file = ev.target.files && ev.target.files[0];
        if (!it || !file) { return; }
        if (file.size > 10 * 1024 * 1024) {
            this.notif.add(_t("The file is larger than 10 MB."), { type: "warning" });
            return;
        }
        const data = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
        ev.target.value = "";
        await this._call("add_file", [it.id, file.name, data]);
    }
    startEditLetter(l) { this.state.editLetter = { id: l.id, title: l.title, body: l.body }; }
    cancelEditLetter() { this.state.editLetter = null; }
    onLetter(field, ev) { this.state.editLetter[field] = ev.target.value; }
    async saveLetter() {
        const e = this.state.editLetter;
        if (!e) { return; }
        if (await this._call("save_letter", [e.id, e.title, e.body])) { this.state.editLetter = null; }
    }
    async issueLetter(l) { await this._call("issue_letter", [l.id], true); }
    async deleteLetter(l) { await this._call("delete_letter", [l.id], true); }
    async replySeen(l) { await this._call("reply_seen", [l.id], true); }
    async _call(method, args, board = false) {
        const it = this.state.item;
        this.state.itemBusy = true;
        try {
            const res = await this.orm.call("pb.conduct", method, args);
            if (res && res.msg) { this.notif.add(res.msg, { type: "success" }); }
            if (it) { await this.openCase({ id: it.id }); }
            if (board) { await this.refresh(); }
            return true;
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")), { type: "danger" });
            return false;
        } finally {
            this.state.itemBusy = false;
        }
    }

    // ----------------------------------------------------------- new case
    openCreate() {
        this.state.draft = blankDraft();
        if (this.state.reasons.length) { this.state.draft.reason_id = this.state.reasons[0].id; }
        this.state.people = [];
        this.state.creating = true;
    }
    closeCreate() { this.state.creating = false; }
    onDraft(field, ev) {
        const v = ev.target.value;
        this.state.draft[field] = field === "reason_id" ? parseInt(v || "0", 10) : v;
    }
    async onPersonSearch(ev) {
        const term = ev.target.value;
        this.state.draft.employee = term;
        this.state.draft.employee_id = 0;
        if (!term || term.length < 2) { this.state.people = []; return; }
        try {
            this.state.people = await this.orm.call("pb.conduct", "employee_options", [term]);
        } catch {
            this.state.people = [];
        }
    }
    pickPerson(p) {
        Object.assign(this.state.draft, { employee_id: p.id, employee: p.name });
        this.state.people = [];
    }
    async confirmCreate() {
        const d = this.state.draft;
        if (!d.employee_id) { this.notif.add(_t("Pick who the case is about."), { type: "warning" }); return; }
        if (!d.summary.trim()) { this.notif.add(_t("Write what happened, in a few sentences."), { type: "warning" }); return; }
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.conduct", "create_case", [{
                employee_id: d.employee_id, reason_id: d.reason_id, summary: d.summary,
                incident_date: d.incident_date || false, raised_by: d.raised_by,
            }]);
            this.state.creating = false;
            await this.refresh();
            this.notif.add(_t("Case opened. Only the people named for conduct cases can see it."), { type: "success" });
            await this.openCase({ id: res.id });
        } catch (e) {
            this.notif.add(this._msg(e, _t("The case could not be opened.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ set up
    toggleSetup() { this.state.setupOpen = !this.state.setupOpen; }
    async openSetup(which) {
        this.state.setupOpen = false;
        try {
            const action = await this.orm.call("pb.conduct", "setup_action", [which]);
            await this.action.doAction(action);
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be opened.")), { type: "danger" });
        }
    }
    async openAccess() {
        this.state.setupOpen = false;
        try {
            await this.action.doAction("biz_access.action_pb_access_board");
        } catch {
            this.notif.add(_t("The Access screen could not be opened."), { type: "warning" });
        }
    }

    // ------------------------------------------------------------ plumbing
    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.act) { this.state.act = null; return; }
        if (this.state.editLetter) { this.state.editLetter = null; return; }
        if (this.state.creating) { this.state.creating = false; return; }
        if (this.state.setupOpen) { this.state.setupOpen = false; return; }
        if (this.state.item) { this.closeCase(); }
    }
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) { return e.message.data.message; }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_conduct_board", PbConductBoard);
