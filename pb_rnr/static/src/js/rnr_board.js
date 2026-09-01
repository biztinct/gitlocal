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
 * FOUR NUMBERS, FOUR PLACES A PIECE OF PRAISE CAN BE: written this month,
 * waiting on a manager, waiting on HR, paid for this quarter.
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

export class PbRnrBoard extends Component {
    static template = "pb_rnr.PbRnrBoard";
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
            kpis: {},
            values: [],
            cycles: [],
            states: [],
            celebrations: [],
            celebrationTotal: 0,
            switches: {},
            currency: "",
            capped: false,

            // filters
            q: "",
            stateFilter: "all",
            valueFilter: 0,

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

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        try {
            const data = await this.orm.call("pb.rnr", "get_board", []);
            Object.assign(this.state, {
                allowed: data.allowed,
                why: data.why || "",
                canWrite: data.can_write,
                canReview: data.can_review,
                rows: data.rows || [],
                kpis: data.kpis || {},
                values: data.values || [],
                cycles: data.cycles || [],
                states: data.states || [],
                celebrations: data.celebrations || [],
                celebrationTotal: data.celebration_total || 0,
                switches: data.switches || {},
                currency: data.currency || "",
                capped: data.capped,
            });
        } catch (e) {
            console.warn("pb_rnr: the recognition board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The recognition board could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async refresh() { await this.load(); }

    // ------------------------------------------------------------- filters
    get visibleRows() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.stateFilter !== "all"
                && r.state !== this.state.stateFilter) { return false; }
            if (this.state.valueFilter
                && r.value_id !== this.state.valueFilter) { return false; }
            if (!q) { return true; }
            return (r.nominee || "").toLowerCase().includes(q)
                || (r.nominator || "").toLowerCase().includes(q)
                || (r.story || "").toLowerCase().includes(q);
        });
    }

    onSearch(ev) { this.state.q = ev.target.value; }
    setStateFilter(key) { this.state.stateFilter = key; }
    setValueFilter(id) {
        this.state.valueFilter = this.state.valueFilter === id ? 0 : id;
    }

    /** ONE expression, so the whitespace between the pieces survives (R34). */
    get countLine() {
        const shown = this.visibleRows.length;
        const total = this.state.rows.length;
        if (shown === total) {
            return total === 1 ? _t("1 story") : _t("%s stories", total);
        }
        return _t("%s of %s stories", shown, total);
    }

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
            await this.load();
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
            await this.load();
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
            await this.load();
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
            await this.load();
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
