/** @odoo-module **/
/**
 * Learning › TESTS (LEARNING L5; L0 shipped a stock-list stand-in).
 *
 * HERO MOMENT: the RESULTS DRAWER — a pass-rate ring, the score spread as
 * ten bars that add up to the attempts, and the hardest questions (wrong ÷
 * how many times the question was ASKED, so a question in a pool is never
 * blamed for attempts that did not draw it). Under the ring: how many goes
 * people get and how the questions are drawn ("Each attempt draws 10 of 30"),
 * with "Questions drawn per attempt" to change it.
 *
 * The list: every test with its course, pass mark, goes, how questions are
 * drawn, people and pass rate (grey at zero, quiet board). "New test" opens
 * a small drawer before the editor — name, pass mark, goes, and "Draw N
 * questions per attempt" — and lands in the test editor. "Question bank" and
 * "Open the test editor" keep the stock forms one press away.
 *
 * Reads `pb.training.tests_board` / `test_results`; writes through
 * `pb.training.act` (`create_test`, `set_pool`, `open_test`,
 * `open_questions`).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const RING = 2 * Math.PI * 34;

export class PbTrainingTestsLens extends Component {
    static template = "pb_training.PbTrainingTestsLens";
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            failed: false,
            data: { tests: [] },
            q: "",
            results: null,
            newTest: false,
            form: { name: "", pass_mark: 70, attempts: 3, pool: false, draw: 10 },
            draw: 0,
            busy: false,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        this.state.failed = false;
        try {
            this.state.data = await this.orm.call("pb.training", "tests_board", [this.state.q]);
        } catch (e) {
            console.warn("pb_training: the tests could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() { this.state.loaded = false; await this.load(); }

    get data() { return this.state.data || {}; }
    get allowed() { return this.data.allowed !== false; }
    get tests() { return this.data.tests || []; }

    onSearch(ev) {
        this.state.q = ev.target.value;
        clearTimeout(this._q);
        this._q = setTimeout(() => this.load(), 250);
    }

    rateWords(t) { return (t.pass_rate === null || t.pass_rate === undefined) ? "—" : `${t.pass_rate}%`; }

    peopleWords(n) { return n === 1 ? _t("1 person") : _t("%s people", n); }

    // ------------------------------------------------------------- doors
    async run(verb, payload = {}) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.training", "act", [verb, payload]);
            if (res && res.type) { await this.action.doAction(res); return res; }
            if (res && res.message) { this.notif.add(res.message, { type: "success" }); }
            return res || {};
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That could not be opened."), { type: "danger" });
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    openQuestions() { return this.run("open_questions"); }
    openEditor(id) { return this.run("open_test", { survey_id: id }); }

    // ------------------------------------------------------- results drawer
    async openResults(t) {
        this.state.results = { loading: true, name: t.name };
        try {
            const res = await this.orm.call("pb.training", "test_results", [t.id]);
            this.state.results = res;
            this.state.draw = res.random ? res.drawn : 0;
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("The results could not be read."), { type: "danger" });
            this.state.results = null;
        }
    }

    closeResults() { this.state.results = null; this.load(); }

    get ringDash() {
        const r = this.state.results || {};
        const pct = r.pass_rate || 0;
        return `${(RING * pct) / 100} ${RING}`;
    }

    get histMax() {
        const h = (this.state.results && this.state.results.histogram) || [];
        return Math.max(1, ...h.map((b) => b.n));
    }

    barHeight(b) { return `${Math.round((100 * b.n) / this.histMax)}%`; }

    barClass(b, i) {
        const mark = (this.state.results && this.state.results.pass_mark) || 0;
        return (i + 1) * 10 > mark ? "is-pass" : "is-fail";
    }

    get resultsWords() {
        const r = this.state.results || {};
        if (!r.attempts) { return _t("Nobody has taken it yet."); }
        const a = r.attempts === 1 ? _t("1 attempt") : _t("%s attempts", r.attempts);
        const p = r.people === 1 ? _t("by 1 person") : _t("by %s people", r.people);
        return _t("%(attempts)s %(people)s · average score %(avg)s", { attempts: a, people: p, avg: `${r.avg}%` });
    }

    get atEndWords() { return _t("At the end of %s", this.state.results.course); }

    get rulesWords() {
        const r = this.state.results || {};
        return _t("Pass mark %(mark)s · %(goes)s · %(pool)s", { mark: `${r.pass_mark}%`, goes: r.retake_words, pool: r.pool_words });
    }

    hardWords(hq) {
        return _t("%(pct)s wrong · %(wrong)s of %(asked)s asked", { pct: `${hq.pct}%`, wrong: hq.wrong, asked: hq.asked });
    }

    onDraw(ev) { this.state.draw = Number(ev.target.value) || 0; }

    async savePool() {
        const res = await this.run("set_pool", { survey_id: this.state.results.id, draw: this.state.draw });
        if (res) { await this.openResults({ id: this.state.results.id, name: this.state.results.name }); }
    }

    // ------------------------------------------------------- new test drawer
    openNew() {
        this.state.form = { name: "", pass_mark: 70, attempts: 3, pool: false, draw: 10 };
        this.state.newTest = true;
    }

    closeNew() { this.state.newTest = false; }

    setForm(key, ev, kind = "") {
        let value = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
        if (kind === "num") { value = Number(value) || 0; }
        this.state.form[key] = value;
    }

    get newHint() {
        const f = this.state.form;
        if (!(f.name || "").trim()) { return _t("Give the test a name."); }
        if (f.pass_mark < 1 || f.pass_mark > 100) { return _t("The pass mark is between 1 and 100."); }
        if (f.pool && f.draw < 1) { return _t("Say how many questions each attempt draws."); }
        return "";
    }

    async createTest() {
        if (this.newHint) { return; }
        const f = this.state.form;
        const res = await this.run("create_test", {
            name: f.name, pass_mark: f.pass_mark, attempts: f.attempts, draw: f.pool ? f.draw : 0,
        });
        if (res && res.action) {
            this.closeNew();
            await this.action.doAction(res.action);
        }
    }
}
