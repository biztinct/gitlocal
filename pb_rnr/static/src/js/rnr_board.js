/** @odoo-module **/
/**
 * `pb_rnr_board` — the Praise lens on the People hub.
 *
 * THE HERO IS THE ROLL-UP. Choosing a quarter's winners from a ranked table of
 * who colleagues actually named — with the money consequence written out in a
 * sentence before anything is saved — is the thing this module exists for.
 * Everything else on the screen keeps praise moving so that the table is worth
 * reading when the quarter ends.
 *
 * THE QUIET BOARD: one slim line of numbers (written this month, waiting on a
 * manager, waiting on HR, not this time, paid for this quarter) and the four
 * numbered steps a story moves through, each story at exactly one step.
 *
 * EVERY SWITCH SAYS WHICH WAY IT IS SET. A send that is off and does not say so
 * is reported as broken (R54), so the strip under the numbers prints all four
 * rather than leaving somebody to wonder why their test email never came.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in.
 * R2 — every sentence is ONE expression; JavaScript has no implicit string
 * concatenation and a stray one kills the whole backend asset bundle.
 * R51 — the mood-board preview is server-built HTML and is wrapped ONCE with
 * `markup()`, which is the only place this module opens that hatch.
 */
import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const PAGE = 60;
// The strip's four steps as filters on the panel's "Where it is" section.
const STEP_FILTERS = {
    draft: { step: ["draft"] },
    submitted: { step: ["submitted"] },
    manager: { step: ["manager"] },
    decided: { step: ["done", "refused"] },
};

export class PbRnrBoard extends Component {
    static template = "pb_rnr.PbRnrBoard";
    static components = { PbFilterLayout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            allowed: true,
            why: "",
            canWrite: false,
            canReview: false,
            rows: [],
            total: 0,
            stepCounts: {},
            listLoaded: false,
            loadingMore: false,
            quarterStart: "",
            kpis: {},
            values: [],
            cycles: [],
            states: [],
            celebrations: [],
            celebrationTotal: 0,
            switches: {},
            currency: "",

            // the new-praise dialog
            creating: false,
            draft: { nominee_id: 0, nominee: "", value_id: 0, story: "",
                     public: true },
            people: [],
            searching: false,

            // the review dialog
            reviewing: null,
            history: [],
            reviewAmount: "",
            reviewNote: "",

            // the roll-up
            rolling: false,
            rollup: null,
            picks: {},
            confirming: false,

            // the mood board
            digest: null,
            digestHtml: null,

            busy: false,
        });

        // The shared filter panel (pb_filter_kit): it owns the filters, the
        // counts and the views; this board only loads a page for kit.query.
        this.kit = useFilterKit({
            model: "pb.rnr",
            noun: _t("stories"),
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        try {
            const data = await this.orm.call("pb.rnr", "get_head", []);
            Object.assign(this.state, {
                allowed: data.allowed,
                why: data.why || "",
                canWrite: data.can_write,
                canReview: data.can_review,
                kpis: data.kpis || {},
                quarterStart: data.quarter_start || "",
                values: data.values || [],
                cycles: data.cycles || [],
                states: data.states || [],
                celebrations: data.celebrations || [],
                celebrationTotal: data.celebration_total || 0,
                switches: data.switches || {},
                currency: data.currency || "",
            });
        } catch (e) {
            console.warn("pb_rnr: the recognition board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The recognition board could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    /** One page of stories for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.rnr", "get_praise_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.total = d.total;
            if (!more) { this.state.stepCounts = d.steps || {}; }
            this.state.listLoaded = true;
        } catch (e) {
            if (this.kit.isCurrent(q.seq)) {
                console.warn("pb_rnr: the stories could not be listed", e);
                this.notif.add(_t("The stories could not be listed. Try again in a moment."), { type: "danger" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }

    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }
    get hasMore() { return this.state.rows.length < this.state.total; }
    get nextPage() { return Math.min(PAGE, this.state.total - this.state.rows.length); }
    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    /** The numbers, the counts and the list, in place. */
    async refresh() {
        await Promise.all([this.load(), this.kit.refresh()]);
    }

    get visibleRows() { return this.state.rows; }

    get filtered() {
        return Boolean(this.kit.activeCount || this.kit.search);
    }

    // ------------------------------------------------ the quiet board
    //
    // The Hiring look: one slim line of numbers and a numbered strip of the
    // steps a story moves through. A story is at EXACTLY one step: "Decided"
    // holds both what was agreed and what was turned down. The step counts
    // follow the panel's other filters (counted on the server); pressing a
    // step ticks it in the panel's "Where it is" section.
    get stepDefs() {
        return [
            { key: "draft", title: _t("Being written") },
            { key: "submitted", title: _t("With their manager") },
            { key: "manager", title: _t("With HR") },
            { key: "decided", title: _t("Decided") },
        ];
    }

    get steps() {
        const counts = this.state.stepCounts || {};
        const lit = this.litStep;
        return this.stepDefs.map((st, i) => {
            const count = counts[st.key] || 0;
            return {
                ...st,
                n: String(i + 1).padStart(2, "0"),
                count,
                countLabel: count === 1 ? _t("1 story") : _t("%s stories", count),
                sub: "",
                flag: "",
                on: lit === st.key,
            };
        });
    }

    /** The step whose filter is exactly the panel's "Where it is" state. */
    get litStep() {
        const cur = this.kit.values("step").map(String).sort().join(",");
        for (const [key, f] of Object.entries(STEP_FILTERS)) {
            if ([...f.step].sort().join(",") === cur) { return key; }
        }
        return "";
    }

    pickStep(key) {
        const f = STEP_FILTERS[key];
        if (!f) { return; }
        if (this.litStep === key) {
            const next = { ...this.kit.filters };
            delete next.step;
            this.kit.setFilters(next, { search: this.kit.search });
        } else {
            this.kit.setFilters({ ...this.kit.filters, step: [...f.step] }, { search: this.kit.search });
        }
    }

    get glanceFilters() {
        return {
            month: { written: { preset: "this_month" } },
            submitted: { step: ["submitted"] },
            manager: { step: ["manager"] },
            refused: { step: ["refused"] },
            awarded: this.state.quarterStart
                ? { outcome: ["awarded"], decided: { from: this.state.quarterStart } }
                : null,
        };
    }

    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const f = this.glanceFilters;
        const pick = (id) => (f[id] ? () => this.kit.toggleFilters(f[id]) : null);
        return [
            { key: "month", n: k.this_month || 0, label: _t("Written this month"), tone: "", run: pick("month") },
            { key: "submitted", n: k.with_manager || 0, label: _t("Waiting on a manager"), tone: tone(k.with_manager, "amber"), run: pick("submitted") },
            { key: "manager", n: k.with_hr || 0, label: _t("Waiting on HR"), tone: tone(k.with_hr, "amber"), run: pick("manager") },
            { key: "refused", n: k.refused || 0, label: _t("Not this time"), tone: "", run: pick("refused") },
            { key: "awarded", n: k.awarded_qtd || 0, label: _t("Given money this quarter"), tone: tone(k.awarded_qtd, "green"), run: pick("awarded") },
        ];
    }

    /** Which figure is lit: the one whose filters are exactly what is on. */
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(this.glanceFilters)) {
            if (f && this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    showAll() { this.kit.toggleFilters({}); }

    /** What the switches are, said in words rather than as a row of dots. */
    get switchLine() {
        const sw = this.state.switches || {};
        if (sw.digest_test) {
            return _t("The monthly email is going to %s and to nobody else.",
                      sw.digest_test);
        }
        if (sw.digest) { return _t("The monthly email goes to everybody."); }
        return _t("The monthly email is switched off — nothing is sent to anybody.");
    }

    get celebrationLine() {
        // The TRUE count, never the length of the capped strip beside it.
        const n = this.state.celebrationTotal;
        if (!n) { return _t("Nobody is celebrating in the next two weeks."); }
        return n === 1
            ? _t("1 birthday or work anniversary in the next two weeks")
            : _t("%s birthdays and work anniversaries in the next two weeks", n);
    }

    // ---------------------------------------------------------- new praise
    openCreate() {
        this.state.draft = { nominee_id: 0, nominee: "", value_id: 0,
                             story: "", public: true };
        this.state.people = [];
        this.state.creating = true;
    }

    closeCreate() { this.state.creating = false; }

    onDraft(field, ev) {
        this.state.draft[field] = field === "public"
            ? ev.target.checked : ev.target.value;
    }

    pickValue(value) { this.state.draft.value_id = value.id; }

    async onPersonSearch(ev) {
        const term = ev.target.value;
        this.state.draft.nominee = term;
        this.state.draft.nominee_id = 0;
        if (!term || term.length < 2) { this.state.people = []; return; }
        this.state.searching = true;
        try {
            this.state.people = await this.orm.call(
                "pb.rnr", "employee_options", [term]);
        } catch (e) {
            this.state.people = [];
        } finally {
            this.state.searching = false;
        }
    }

    pickPerson(person) {
        this.state.draft.nominee_id = person.id;
        this.state.draft.nominee = person.name;
        this.state.people = [];
    }

    async confirmCreate() {
        const d = this.state.draft;
        if (!d.nominee_id) {
            this.notif.add(_t("Pick the colleague you want to thank."),
                           { type: "warning" });
            return;
        }
        if (!d.value_id) {
            this.notif.add(_t("Pick the value this is an example of."),
                           { type: "warning" });
            return;
        }
        if (!(d.story || "").trim()) {
            this.notif.add(_t("Write what actually happened."),
                           { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("pb.rnr", "nominate", [{
                nominee_id: d.nominee_id,
                value_id: d.value_id,
                story: d.story,
                public: d.public,
            }]);
            this.state.creating = false;
            await this.refresh();
            this.notif.add(_t("Sent. It has gone to their manager."),
                           { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be sent.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- review
    async openReview(row) {
        this.state.reviewing = row;
        this.state.reviewAmount = row.amount ? String(row.amount) : "";
        this.state.reviewNote = "";
        this.state.history = [];
        try {
            this.state.history = await this.orm.call(
                "pb.rnr", "nominee_history", [row.nominee_id]);
        } catch (e) {
            this.state.history = [];
        }
    }

    closeReview() { this.state.reviewing = null; }

    onReviewField(field, ev) { this.state[field] = ev.target.value; }

    async doAgree() {
        const row = this.state.reviewing;
        await this._move(() => this.orm.call(
            "pb.rnr", "manager_agree", [row.id, this.state.reviewNote || false]),
            _t("Agreed. It has gone to HR."));
    }

    async doRecognise() {
        const row = this.state.reviewing;
        const amount = parseFloat(this.state.reviewAmount) || 0;
        await this._move(() => this.orm.call(
            "pb.rnr", "recognise",
            [row.id, amount, this.state.reviewNote || false]),
            amount
                ? _t("Recognised, and an award has been raised. It still has to be approved by the pay team and put into a pay run by hand.")
                : _t("Recognised. It is on the wall."));
    }

    async doDecline() {
        const row = this.state.reviewing;
        await this._move(() => this.orm.call(
            "pb.rnr", "decline", [row.id, this.state.reviewNote || false]),
            _t("Noted. It is not shown anywhere."));
    }

    async _move(fn, ok) {
        this.state.busy = true;
        try {
            await fn();
            this.state.reviewing = null;
            await this.refresh();
            this.notif.add(ok, { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ roll-up
    async openRollup() {
        this.state.rolling = true;
        this.state.rollup = null;
        this.state.picks = {};
        this.state.confirming = false;
        this.state.busy = true;
        try {
            this.state.rollup = await this.orm.call(
                "pb.rnr", "cycle_rollup", [false]);
        } catch (e) {
            this.state.rollup = { ok: false, rows: [],
                                  problem: this._msg(e, _t("Nothing could be read.")) };
        } finally {
            this.state.busy = false;
        }
    }

    closeRollup() {
        this.state.rolling = false;
        this.state.confirming = false;
    }

    togglePick(row) {
        const picks = { ...this.state.picks };
        if (picks[row.nomination_id]) {
            delete picks[row.nomination_id];
        } else {
            picks[row.nomination_id] = { amount: "" , name: row.employee };
        }
        this.state.picks = picks;
    }

    isPicked(row) { return Boolean(this.state.picks[row.nomination_id]); }

    onPickAmount(row, ev) {
        const picks = { ...this.state.picks };
        if (!picks[row.nomination_id]) { return; }
        picks[row.nomination_id] = { ...picks[row.nomination_id],
                                     amount: ev.target.value };
        this.state.picks = picks;
    }

    pickAmount(row) {
        const pick = this.state.picks[row.nomination_id];
        return pick ? pick.amount : "";
    }

    get pickList() {
        return Object.keys(this.state.picks).map((key) => ({
            nomination_id: parseInt(key, 10),
            name: this.state.picks[key].name,
            amount: parseFloat(this.state.picks[key].amount) || 0,
        }));
    }

    get pickTotal() {
        return this.pickList.reduce((sum, p) => sum + p.amount, 0);
    }

    /** The confirmation, in words. ONE expression per sentence (R2/R34). */
    get pickSentence() {
        const picks = this.pickList;
        const n = picks.length;
        const money = this.pickTotal;
        const who = n === 1 ? _t("1 person") : _t("%s people", n);
        if (!money) {
            return _t("%s will be recorded as chosen for this quarter. No money is involved.", who);
        }
        return _t(
            "%(who)s will be recorded as chosen for this quarter, and %(money)s %(cur)s of awards will be raised. Nothing is paid until the pay team approves each award and puts it into a pay run by hand.",
            { who: who, money: money.toLocaleString(),
              cur: (this.state.rollup && this.state.rollup.currency) || "" });
    }

    askConfirm() {
        if (!this.pickList.length) {
            this.notif.add(_t("Pick at least one person first."),
                           { type: "warning" });
            return;
        }
        this.state.confirming = true;
    }

    cancelConfirm() { this.state.confirming = false; }

    async confirmPicks() {
        this.state.busy = true;
        try {
            const cycle = this.state.rollup.cycle;
            const res = await this.orm.call(
                "pb.rnr", "pick_winners", [cycle.id, this.pickList]);
            this.state.rolling = false;
            this.state.confirming = false;
            await this.refresh();
            this.notif.add(res.msg || _t("Done."), { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("Nothing was recorded.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // -------------------------------------------------------- the mood board
    async openDigest() {
        this.state.busy = true;
        this.state.digest = null;
        this.state.digestHtml = null;
        try {
            const data = await this.orm.call("pb.rnr", "digest_preview", [false]);
            this.state.digest = data;
            // R51 — server-built HTML, escaped by QWeb on the way out, wrapped
            // once here. The only place this module does this.
            this.state.digestHtml = markup(data.html || "");
        } catch (e) {
            this.notif.add(this._msg(e, _t("The monthly email could not be built.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    closeDigest() { this.state.digest = null; this.state.digestHtml = null; }

    async sendDigest() {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.rnr", "digest_send", [false, true]);
            this.notif.add(res.msg || _t("Done."),
                           { type: res.ok ? "success" : "warning" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("Nothing was sent.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async runCelebrations() {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.rnr", "run_celebrations", []);
            const today = res.today || {};
            const msg = today.enabled
                ? _t("%s congratulated today.", today.sent || 0)
                : _t("Congratulations are switched off. %s would have been sent today.", today.would || 0);
            this.notif.add(msg, { type: "info" });
            await this.refresh();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be run.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- plumbing
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) {
            return e.message.data.message;
        }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }

    money(row) {
        const n = Number(row.amount || 0);
        if (!n) { return ""; }
        return `${n.toLocaleString()} ${row.currency || this.state.currency || ""}`.trim();
    }

    openAll() { this.action.doAction("pb_rnr.action_pb_rnr_nomination"); }
    openValues() { this.action.doAction("pb_rnr.action_pb_company_value"); }
}

registry.category("actions").add("pb_rnr_board", PbRnrBoard);
