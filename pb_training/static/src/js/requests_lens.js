/** @odoo-module **/
/**
 * Learning › Claims › REQUESTS (LEARNING L5) — every course request, problem
 * first.
 *
 * HERO MOMENT: one sentence over four numbered steps — "3 requests are
 * waiting for a decision · 2 agreed and not taken yet · 4,500,000 ₫ set
 * aside" — Waiting · Agreed · Taken or claimed back · Closed (QuietSteps: a
 * request is at exactly one step; the counts add up to every request).
 * Each row: who, what (ours / outside / something else), the cost, who it is
 * waiting on, why, and the doors — Agree / Turn down (the press runs as YOU
 * and the approval engine checks the seat is yours), Mark as taken for an
 * agreed outside course, Open. "Put someone on a course" agrees one on a
 * person's behalf (the allowance still applies).
 *
 * Reads `pb.training.requests_board`; writes through `pb.training.act`.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbRequestsLens extends Component {
    static template = "pb_training.PbRequestsLens";
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            failed: false,
            data: { rows: [], steps: {}, kpis: {}, kinds: [] },
            f: { step: "", kind: "", q: "" },
            refuse: null,
            refuseNote: "",
            drawer: false,
            put: this.blankPut(),
            people: [],
            courses: [],
            outside: [],
            busy: false,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    blankPut() {
        return { kind: "outside", channel_id: 0, outside_course_id: 0, course_name: "",
                 provider: "", url: "", amount: 0, why: "", term: "", picked: [] };
    }

    async load() {
        this.state.failed = false;
        try {
            this.state.data = await this.orm.call("pb.training", "requests_board", [{ ...this.state.f }]);
        } catch (e) {
            console.warn("pb_training: the course requests could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() { this.state.loaded = false; await this.load(); }

    get data() { return this.state.data || {}; }
    get allowed() { return this.data.allowed !== false; }
    get rows() { return this.data.rows || []; }
    get kpis() { return this.data.kpis || {}; }

    get stepDefs() {
        return [
            { key: "waiting", title: _t("Waiting for a decision") },
            { key: "agreed", title: _t("Agreed, not taken yet") },
            { key: "done", title: _t("Taken or claimed back") },
            { key: "closed", title: _t("Turned down or cancelled") },
        ];
    }

    get steps() {
        const s = this.data.steps || {};
        return this.stepDefs.map((st, i) => ({
            ...st,
            n: String(i + 1).padStart(2, "0"),
            count: s[st.key] || 0,
            countLabel: (s[st.key] || 0) === 1 ? _t("1 request") : _t("%s requests", s[st.key] || 0),
            sub: "",
            flag: st.key === "waiting" && s.waiting ? (s.waiting === 1 ? _t("1 needs a decision") : _t("%s need a decision", s.waiting)) : "",
            on: this.state.f.step === st.key,
        }));
    }

    pickStep(key) {
        this.state.f.step = this.state.f.step === key ? "" : key;
        this.load();
    }

    stepPicker() { return (key) => this.pickStep(key); }

    get showing() {
        const d = this.data;
        const f = this.state.f;
        if (!f.step && !f.kind && !(f.q || "").trim()) {
            return { all: true, text: !(this.kpis.total) ? _t("No requests yet")
                : this.kpis.total === 1 ? _t("Showing the 1 request · press a step to narrow it")
                : _t("Showing all %s requests · press a step to narrow it", this.kpis.total) };
        }
        return { all: false, text: _t("Showing %s of %s requests", d.matching || 0, this.kpis.total || 0) };
    }

    get claimedWords() { return _t("Claimed back this year: %s", this.kpis.claimed_words); }

    putByWords(row) { return _t("Put on by %s", row.put_on_by); }

    get capWords() {
        return _t("Showing the first %(shown)s of %(all)s — narrow it with a step or a search.", { shown: this.data.shown, all: this.data.matching });
    }

    setKind(key) { this.state.f.kind = this.state.f.kind === key ? "" : key; this.load(); }

    onSearch(ev) {
        this.state.f.q = ev.target.value;
        clearTimeout(this._q);
        this._q = setTimeout(() => this.load(), 250);
    }

    showAll() { Object.assign(this.state.f, { step: "", kind: "", q: "" }); this.load(); }

    stateClass(row) {
        if (row.state === "submitted" || row.state === "draft") { return "is-warn"; }
        if (row.state === "refused" || row.state === "cancelled") { return "is-bad"; }
        if (row.state === "approved") { return "is-go"; }
        return "is-ok";
    }

    kindIcon(row) { return { ours: "bookOpen", outside: "graduationCap", other: "link" }[row.kind] || "bookOpen"; }

    // ------------------------------------------------------------- doors
    async act(verb, payload) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.training", "act", [verb, payload]);
            if (res && res.type) { await this.action.doAction(res); return res; }
            if (res && res.message) { this.notif.add(res.message, { type: "success" }); }
            await this.load();
            return res || {};
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    approve(row) { return this.act("approve_request", { request_id: row.id }); }
    markTaken(row) { return this.act("mark_taken", { request_id: row.id }); }
    openRequest(row) { return this.act("open_request", { request_id: row.id }); }

    openRefuse(row) { this.state.refuse = row; this.state.refuseNote = ""; }
    closeRefuse() { this.state.refuse = null; }
    onRefuseNote(ev) { this.state.refuseNote = ev.target.value; }

    async confirmRefuse() {
        if (!this.state.refuseNote.trim()) { return; }
        const res = await this.act("refuse_request", { request_id: this.state.refuse.id, note: this.state.refuseNote });
        if (res) { this.closeRefuse(); }
    }

    // ------------------------------------------------- put someone on a course
    async openPut() {
        this.state.put = this.blankPut();
        this.state.drawer = true;
        try {
            const [board, outside] = await Promise.all([
                this.orm.call("pb.training", "get_board", []),
                this.orm.call("pb.training", "outside_board", [{}]),
            ]);
            this.state.courses = (board.courses || []).map((c) => ({ id: c.id, name: c.name }));
            this.state.outside = (outside.rows || []).map((c) => ({ id: c.id, name: c.name, cost_words: c.cost_words }));
            if (!this.state.outside.length) { this.state.put.kind = "ours"; }
        } catch (e) {
            console.warn("pb_training: the course lists could not be read", e);
        }
        await this.searchPeople();
    }

    closePut() { this.state.drawer = false; }

    setPut(key, ev, kind = "") {
        let value = ev.target.value;
        if (kind === "num") { value = Number(value) || 0; }
        this.state.put[key] = value;
    }

    setPutKind(kind) { this.state.put.kind = kind; }

    async searchPeople() {
        try {
            this.state.people = await this.orm.call("pb.training", "search_people", [this.state.put.term, 0]);
        } catch (e) {
            this.state.people = [];
        }
    }

    onPeopleTerm(ev) {
        this.state.put.term = ev.target.value;
        clearTimeout(this._p);
        this._p = setTimeout(() => this.searchPeople(), 220);
    }

    togglePick(id) {
        const list = this.state.put.picked;
        const at = list.indexOf(id);
        if (at === -1) { list.push(id); } else { list.splice(at, 1); }
    }

    get putHint() {
        const p = this.state.put;
        if (!p.picked.length) { return _t("Pick at least one person."); }
        if (p.kind === "ours" && !p.channel_id) { return _t("Pick which of our courses."); }
        if (p.kind === "outside" && !p.outside_course_id) { return _t("Pick the outside course."); }
        if (p.kind === "other" && !(p.course_name || "").trim()) { return _t("Say what the course is called."); }
        return "";
    }

    async confirmPut() {
        if (this.putHint) { return; }
        const p = this.state.put;
        const res = await this.act("put_on_course", {
            kind: p.kind, employee_ids: p.picked.slice(), why: p.why,
            channel_id: Number(p.channel_id) || 0, outside_course_id: Number(p.outside_course_id) || 0,
            course_name: p.course_name, provider: p.provider, url: p.url, amount: p.amount,
        });
        if (res) { this.closePut(); }
    }
}
