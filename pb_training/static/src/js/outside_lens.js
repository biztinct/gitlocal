/** @odoo-module **/
/**
 * Learning › Courses › OUTSIDE (LEARNING L5) — the outside-course catalogue,
 * our own list (owner decision LD6): courses a college, a licensing body or
 * an online school runs, with the provider, the link, the cost and the hours.
 *
 * HERO MOMENT: the catalogue as cards — what it is, who runs it, what it
 * costs in words ("3,000,000 ₫", "Free"), the hours, the rating ("4.3 · 17
 * ratings") and an amber "2 waiting" when somebody has asked and nobody has
 * decided. A card opens the COURSE PAGE: who asked and where each request is,
 * claims against it, what people said, and the skills it gives. "Put someone
 * on it" agrees a request on a person's behalf (the allowance still applies).
 *
 * Reuses the Sessions tab's look (`.pbss-*`) so the two inner tabs read as
 * one screen. Reads `pb.training.outside_board` / `outside_page` /
 * `outside_lists` / `skill_lists`; writes through `pb.training.act`.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

function blankCourse() {
    return { id: 0, name: "", provider: "", url: "", cost: 0, hours: 0, blurb: "",
             kind: "online", issues_certificate: false, validity_months: 0,
             country_id: 0, job_ids: [] };
}

export class PbOutsideLens extends Component {
    static template = "pb_training.PbOutsideLens";
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            failed: false,
            data: { rows: [], kpis: {} },
            f: { kind: "", job_id: 0, q: "", archived: false },
            lists: { kinds: [], jobs: [], countries: [] },
            page: null,
            drawer: "",
            form: blankCourse(),
            put: { term: "", rows: [], picked: [], why: "" },
            grant: { type_id: 0, skill_id: 0, level_id: 0 },
            skillTypes: [],
            busy: false,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        this.state.failed = false;
        try {
            const [data, lists] = await Promise.all([
                this.orm.call("pb.training", "outside_board", [{ ...this.state.f }]),
                this.state.lists.kinds.length ? Promise.resolve(this.state.lists)
                    : this.orm.call("pb.training", "outside_lists", []),
            ]);
            this.state.data = data || { rows: [], kpis: {} };
            if (lists && lists.allowed !== false) { this.state.lists = lists; }
        } catch (e) {
            console.warn("pb_training: the outside courses could not be read", e);
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
    get page() { return this.state.page; }

    get glance() {
        const k = this.kpis;
        const tone = (v, t) => (v ? t : "");
        return [
            { key: "courses", n: k.courses || 0, label: _t("Outside courses"), tone: "", run: null },
            { key: "waiting", n: k.waiting || 0, label: _t("Requests waiting for a decision"), tone: tone(k.waiting, "amber"), run: null },
            { key: "taken", n: k.taken || 0, label: _t("Taken this year"), tone: tone(k.taken, "green"), run: null },
            { key: "archived", n: k.archived || 0, label: _t("Archived"), tone: "", run: () => this.toggleArchived() },
        ];
    }

    get anyFilter() {
        const f = this.state.f;
        return !!(f.kind || f.job_id || f.q || f.archived);
    }

    setKind(key) {
        this.state.f.kind = this.state.f.kind === key ? "" : key;
        this.load();
    }

    onJob(ev) { this.state.f.job_id = Number(ev.target.value) || 0; this.load(); }

    onSearch(ev) {
        this.state.f.q = ev.target.value;
        clearTimeout(this._q);
        this._q = setTimeout(() => this.load(), 250);
    }

    toggleArchived() { this.state.f.archived = !this.state.f.archived; this.load(); }

    clearFilters() {
        Object.assign(this.state.f, { kind: "", job_id: 0, q: "", archived: false });
        this.load();
    }

    // ------------------------------------------------------------- doors
    async act(verb, payload) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.training", "act", [verb, payload]);
            if (res && res.message) { this.notif.add(res.message, { type: "success" }); }
            return res || {};
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- the page
    async openPage(id) {
        this.state.page = { loading: true, id };
        try {
            this.state.page = await this.orm.call("pb.training", "outside_page", [id]);
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That course could not be opened."), { type: "danger" });
            this.state.page = null;
        }
    }

    closePage() { this.state.page = null; this.load(); }

    stateClass(row) {
        if (row.state === "submitted" || row.state === "draft") { return "is-warn"; }
        if (row.state === "refused" || row.state === "cancelled") { return "is-bad"; }
        if (row.state === "approved") { return "is-go"; }
        return "is-ok";
    }

    async archive(active) {
        const res = await this.act("archive_outside", { outside_course_id: this.page.id, active });
        if (res) { await this.openPage(this.page.id); }
    }

    // ------------------------------------------------------- the course drawer
    newCourse() { this.state.form = blankCourse(); this.state.drawer = "course"; }

    editCourse() {
        const p = this.page;
        this.state.form = {
            id: p.id, name: p.name, provider: p.provider, url: p.url, cost: p.cost,
            hours: p.hours, blurb: p.blurb, kind: p.kind, issues_certificate: p.issues_certificate,
            validity_months: p.validity_months, country_id: p.country_id || 0,
            job_ids: (p.job_ids || []).slice(),
        };
        this.state.drawer = "course";
    }

    closeDrawer() { this.state.drawer = ""; }

    setField(key, ev, kind = "") {
        let value = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
        if (kind === "num") { value = Number(value) || 0; }
        this.state.form[key] = value;
    }

    toggleJob(id) {
        const at = this.state.form.job_ids.indexOf(id);
        if (at === -1) { this.state.form.job_ids.push(id); } else { this.state.form.job_ids.splice(at, 1); }
    }

    get courseHint() {
        if (!(this.state.form.name || "").trim()) { return _t("Give it the name the provider uses."); }
        if (this.state.form.cost < 0 || this.state.form.hours < 0) { return _t("Cost and hours cannot be below zero."); }
        return "";
    }

    async saveCourse() {
        if (this.courseHint) { return; }
        const res = await this.act("save_outside", { ...this.state.form });
        if (res) {
            this.state.drawer = "";
            if (this.page) { await this.openPage(res.id || this.page.id); } else { await this.load(); }
        }
    }

    // ------------------------------------------------------- put someone on it
    async openPut(card) {
        this.state.put = { course: card, term: "", rows: [], picked: [], why: "" };
        this.state.drawer = "put";
        await this.searchPeople();
    }

    async searchPeople() {
        try {
            this.state.put.rows = await this.orm.call("pb.training", "search_people", [this.state.put.term, 0]);
        } catch (e) {
            console.warn("pb_training: the people search failed", e);
            this.state.put.rows = [];
        }
    }

    onPutTerm(ev) {
        this.state.put.term = ev.target.value;
        clearTimeout(this._p);
        this._p = setTimeout(() => this.searchPeople(), 220);
    }

    togglePick(id) {
        const list = this.state.put.picked;
        const at = list.indexOf(id);
        if (at === -1) { list.push(id); } else { list.splice(at, 1); }
    }

    get pickedWord() {
        const n = this.state.put.picked.length;
        if (!n) { return _t("Nobody picked yet"); }
        return n === 1 ? _t("1 person picked") : _t("%s people picked", n);
    }

    get pageScoreWords() {
        const p = this.page || {};
        const r = p.ratings || {};
        return (r.recommend_pct === null || r.recommend_pct === undefined) ? p.rating_words
            : _t("%(words)s · %(pct)s%% would recommend it", { words: p.rating_words, pct: r.recommend_pct });
    }

    get putNote() {
        return _t("%s · agreed by you now, set aside from each person's allowance", (this.state.put.course || {}).cost_words || "");
    }

    get spendWords() { return _t("Agreed this year: %s", this.kpis.spend); }

    onWhy(ev) { this.state.put.why = ev.target.value; }

    waitingWords(n) { return n === 1 ? _t("1 waiting") : _t("%s waiting", n); }

    takenWords(oc) {
        return _t("%(taken)s taken · %(asked)s asked", { taken: oc.taken_count || 0, asked: oc.requests_count || 0 });
    }

    async confirmPut() {
        if (!this.state.put.picked.length) { return; }
        const res = await this.act("put_on_outside", {
            outside_course_id: this.state.put.course.id,
            employee_ids: this.state.put.picked.slice(),
            why: this.state.put.why,
        });
        if (res) {
            this.state.drawer = "";
            if (this.page) { await this.openPage(this.page.id); } else { await this.load(); }
        }
    }

    // ------------------------------------------------------- skills it gives
    async openGrant() {
        if (!this.state.skillTypes.length) {
            try {
                this.state.skillTypes = (await this.orm.call("pb.training", "skill_lists", [])).types || [];
            } catch (e) {
                this.state.skillTypes = [];
            }
        }
        const first = this.state.skillTypes[0];
        this.state.grant = { type_id: first ? first.id : 0, skill_id: 0, level_id: 0 };
        this.state.drawer = "grant";
    }

    get grantType() { return this.state.skillTypes.find((t) => t.id === this.state.grant.type_id) || { skills: [], levels: [] }; }

    onGrant(key, ev) {
        this.state.grant[key] = Number(ev.target.value) || 0;
        if (key === "type_id") { this.state.grant.skill_id = 0; this.state.grant.level_id = 0; }
    }

    async saveGrant() {
        const g = this.state.grant;
        if (!g.skill_id || !g.level_id) { return; }
        const res = await this.act("save_grant", { outside_course_id: this.page.id, skill_id: g.skill_id, skill_level_id: g.level_id });
        if (res) { this.state.drawer = ""; await this.openPage(this.page.id); }
    }

    async dropGrant(id) {
        const res = await this.act("drop_grant", { grant_id: id });
        if (res) { await this.openPage(this.page.id); }
    }

    openLink(url) { if (url) { window.open(url, "_blank", "noopener"); } }
}
