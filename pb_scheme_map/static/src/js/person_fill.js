/** @odoo-module **/
/**
 * PSCHEME P2a — the Mapping board's person drawers.
 *
 *  * `PersonFillDrawer`  "Give everyone their own pay scheme" (the one-time
 *    fill, ledger R3). HERO: one drawer turns "313 people, nobody has their
 *    own pay scheme" into "All 313 people have a pay scheme" — every person
 *    listed with who pays them today, grouped so the safe ones are one press
 *    and only the real questions need a choice; "Undo this fill" stays.
 *  * `TeamSetDrawer`     "Set for everyone in this team…" (ledger R8).
 *  * `MismatchDrawer`    people paid by a scheme of another country (A14).
 *  * `OwnPeoplePanel`    "M have their own" — the names behind the count.
 *
 * Rules kept: icons are cached markup (`psIc`, ledger: OWL markup flicker);
 * every sentence is one `_t()`; no JS globals in templates (NH11); Escape is
 * the board's (one capture listener); every state is designed.
 */
import { Component, onMounted, onWillStart, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { SchemeMapBoard } from "@pb_scheme_map/js/scheme_map_board";
import { psIc, dayWords, monthWords } from "@pb_scheme_map/js/person_scheme";

const BOARD = "pb.scheme.board";
const PAGE = 60;

function errorText(e, fallback) {
    const data = (e && e.data) || (e && e.message && e.message.data);
    return (data && data.message) || fallback || _t("That did not work. Try again.");
}
function num(n) { return Number(n || 0).toLocaleString(); }
function peopleWords(n) {
    return Number(n) === 1 ? _t("1 person") : _t("%s people", num(n));
}

/** Shift-click ticks a range: the rows between the last click and this one
 * take the new state. `list` is the rows as shown, `set` the ticked ids. */
export function tickRange(list, set, lastId, id, on) {
    const ids = list.map((r) => r.id);
    const a = ids.indexOf(lastId);
    const b = ids.indexOf(id);
    if (a < 0 || b < 0) {
        on ? set.add(id) : set.delete(id);
        return;
    }
    for (const x of ids.slice(Math.min(a, b), Math.max(a, b) + 1)) {
        on ? set.add(x) : set.delete(x);
    }
}

// ===================================================================
//  "Give everyone their own pay scheme"
// ===================================================================
export class PersonFillDrawer extends Component {
    static template = "pb_scheme_map.PersonFillDrawer";
    static props = {
        companyId: Number,
        filterIds: { type: Array, optional: true },
        onClose: Function,
        onChanged: { type: Function, optional: true },
    };

    stay() { /* a click inside the drawer is not a click on the scrim */ }

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.ic = psIc;
        this.search = useRef("search");
        this.state = useState({
            loading: true, error: "", plan: null, query: "",
            ticked: new Set(), picks: {}, open: { ready: false, country: false, check: true, choice: true },
            shown: {}, last: {}, busy: false, done: null, confirmUndo: false, undoError: "",
        });
        onWillStart(() => this.load());
        onMounted(() => setTimeout(() => this.search.el && this.search.el.focus(), 80));
    }

    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const plan = await this.orm.call(BOARD, "fill_plan",
                [this.props.companyId, this.props.filterIds || null]);
            this.state.plan = plan;
            const ticked = new Set();
            for (const r of plan.rows) {
                if ((r.group === "ready" || r.group === "country") && r.target_id) {
                    ticked.add(r.id);
                }
            }
            this.state.ticked = ticked;
            this.state.picks = {};
            this.state.shown = {};
        } catch (e) {
            this.state.error = errorText(e, _t("The people could not be read. Try again."));
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------ words
    get p() { return this.state.plan || { rows: [], counts: {}, schemes: {}, teams: {}, countries: {} }; }
    get filtered() { return Boolean(this.props.filterIds && this.props.filterIds.length); }
    get title() { return this.filtered ? _t("Give these people their own pay scheme") : _t("Give everyone their own pay scheme"); }
    scheme(id) { return this.p.schemes[String(id)] || null; }
    schemeName(id) { const s = this.scheme(id); return s ? s.name : ""; }
    teamName(id) { return this.p.teams[String(id)] || _t("No team"); }
    countryName(code) { return code ? (this.p.countries[code] || code) : _t("No Country of work"); }
    get route() { return this.p.lane === "route"; }
    get groups() {
        return [
            { key: "ready", title: _t("Ready"), icon: "checkCircle", tone: "good",
              sub: _t("Paid today by a pay scheme of their Country of work. They keep it.") },
            { key: "country", title: _t("From their Country of work"), icon: "globe", tone: "good",
              sub: _t("Nobody pays them today, and their Country of work has one pay scheme.") },
            { key: "check", title: _t("Check these"), icon: "alert", tone: "warn",
              sub: _t("Paid today by a pay scheme of another country. Keep it, or give them their country's.") },
            { key: "choice", title: _t("Needs your choice"), icon: "helpCircle", tone: "warn",
              sub: _t("Nobody can tell which pay scheme is theirs. Pick one, or fix the reason first.") },
        ];
    }
    count(key) { return (this.p.counts || {})[key] || 0; }
    rowsOf(key) {
        const q = this.state.query.trim().toLowerCase();
        return this.p.rows.filter((r) => r.group === key && (!q || r.name.toLowerCase().includes(q)));
    }
    /** The rows of a group as shown: by country, then team, paged. */
    sections(key) {
        const rows = this.rowsOf(key).slice().sort((a, b) =>
            (a.country || "~").localeCompare(b.country || "~")
            || this.teamName(a.team_id).localeCompare(this.teamName(b.team_id))
            || a.name.localeCompare(b.name));
        const limit = this.state.shown[key] || PAGE;
        const out = [];
        let country = null;
        let team = null;
        for (const r of rows.slice(0, limit)) {
            if (r.country !== country) {
                country = r.country;
                team = null;
                out.push({ kind: "country", key: `c-${key}-${country}`, label: this.countryName(country),
                    n: rows.filter((x) => x.country === country).length, code: country });
            }
            if (r.team_id !== team) {
                team = r.team_id;
                out.push({ kind: "team", key: `t-${key}-${country}-${team}`, label: this.teamName(team),
                    n: rows.filter((x) => x.country === country && x.team_id === team).length });
            }
            out.push({ kind: "row", key: `r-${r.id}`, row: r });
        }
        return out;
    }
    moreIn(key) { return Math.max(0, this.rowsOf(key).length - (this.state.shown[key] || PAGE)); }
    showMore(key) { this.state.shown[key] = (this.state.shown[key] || PAGE) + PAGE * 4; }
    moreLabel(key) { return _t("Show more (%s left)", num(this.moreIn(key))); }
    toggleOpen(key) { this.state.open[key] = !this.state.open[key]; }
    groupCountLabel(key) { return peopleWords(this.count(key)); }

    // ------------------------------------------------------------ choosing
    isTicked(r) { return this.state.ticked.has(r.id); }
    onTick(r, ev) {
        const on = !this.isTicked(r);
        const set = new Set(this.state.ticked);
        if (ev && ev.shiftKey) {
            tickRange(this.rowsOf(r.group), set, this.state.last[r.group], r.id, on);
        } else {
            on ? set.add(r.id) : set.delete(r.id);
        }
        this.state.last[r.group] = r.id;
        this.state.ticked = set;
    }
    groupTicked(key) { return this.rowsOf(key).filter((r) => this.isTicked(r)).length; }
    allTicked(key) { const n = this.rowsOf(key).length; return n > 0 && this.groupTicked(key) === n; }
    tickAll(key) {
        const set = new Set(this.state.ticked);
        const on = !this.allTicked(key);
        for (const r of this.rowsOf(key)) { on ? set.add(r.id) : set.delete(r.id); }
        this.state.ticked = set;
    }
    pickOf(r) { return this.state.picks[r.id] || 0; }
    setPick(r, id) {
        const picks = { ...this.state.picks };
        if (id && r.options.includes(id)) { picks[r.id] = id; } else { delete picks[r.id]; }
        this.state.picks = picks;
    }
    onPickSelect(r, ev) { this.setPick(r, Number(ev.target.value) || 0); }
    /** "Check these": keep today's, or the country's only one. */
    keepToday(r) { this.setPick(r, r.today_id); }
    takeCountry(r) { if (r.country_pick) { this.setPick(r, r.country_pick); } }
    bulkCheck(which) {
        const picks = { ...this.state.picks };
        for (const r of this.rowsOf("check")) {
            const id = which === "today" ? r.today_id : r.country_pick;
            if (id) { picks[r.id] = id; }
        }
        this.state.picks = picks;
    }
    get checkHasCountry() { return this.rowsOf("check").some((r) => r.country_pick); }
    /** Bulk pick per country in "Needs your choice". */
    choiceCountries() {
        const out = {};
        for (const r of this.rowsOf("choice")) {
            if (!r.country || r.reason === "no_scheme") { continue; }
            const c = out[r.country] || (out[r.country] = { code: r.country, n: 0, options: r.options });
            c.n += 1;
        }
        return Object.values(out);
    }
    bulkChoiceLabel(c) { return _t("All %(count)s in %(country)s", { count: num(c.n), country: this.countryName(c.code) }); }
    onBulkChoice(c, ev) {
        const id = Number(ev.target.value) || 0;
        const picks = { ...this.state.picks };
        for (const r of this.rowsOf("choice")) {
            if (r.country !== c.code || r.reason === "no_scheme") { continue; }
            if (id && r.options.includes(id)) { picks[r.id] = id; } else { delete picks[r.id]; }
        }
        this.state.picks = picks;
    }
    reasonLine(r) {
        if (r.reason === "no_country") { return _t("No Country of work yet, so nobody can tell which pay scheme is theirs."); }
        if (r.reason === "other_country") {
            const s = this.scheme(r.today_id);
            return _t("Works in %(country)s and is paid today by %(scheme)s, a pay scheme of %(other)s.",
                { country: this.countryName(r.country), scheme: s ? s.name : "", other: s ? (s.country_name || "") : "" });
        }
        if (r.reason === "several") {
            return _t("%(country)s has %(count)s pay schemes. Pick theirs.",
                { country: this.countryName(r.country), count: r.options.length });
        }
        if (r.reason === "no_scheme") { return _t("No pay scheme for %s yet.", this.countryName(r.country)); }
        return "";
    }
    todayLine(r) {
        return r.today_id ? _t("Paid today by %s", this.schemeName(r.today_id)) : _t("Nobody pays them today");
    }
    advanceLine(r) {
        return r.advance_id ? _t("+ mid-month advance %s", this.schemeName(r.advance_id)) : "";
    }
    noSchemeLine(r) { return _t("No pay scheme for %s yet. Add one", this.countryName(r.country)); }
    fixLabel(r) {
        if (r.fix === "cow") { return this.p.cow_fill ? _t("Fill empty Country of Work") : ""; }
        if (r.fix === "mapping") { return _t("Add a pay scheme"); }
        return "";
    }
    async runFix(r) {
        if (r.fix === "cow") {
            await this.action.doAction("pb_employee_form_tidy.action_pb_cow_fill_wizard", {
                onClose: () => this.load() }).catch(() => {});
            return;
        }
        if (r.fix === "mapping") {
            this.props.onClose();
            this.action.doAction("pb_formula_studio.action_pb_formula_studio", { clearBreadcrumbs: false })
                .catch(() => {});
        }
    }

    // ------------------------------------------------------------ the sum
    /** Mirrors the server's own rule (`_fill_groups`). */
    get chosen() {
        let n = 0;
        for (const r of this.p.rows) {
            const pick = this.state.picks[r.id];
            if (pick && r.options.includes(pick)) { n += 1; }
            else if ((r.group === "ready" || r.group === "country") && r.target_id && this.state.ticked.has(r.id)) { n += 1; }
        }
        return n;
    }
    get stillOpen() { return this.p.without - this.chosen; }
    get sumLine() {
        if (!this.chosen) { return _t("Nobody is ticked yet."); }
        const base = _t("%(people)s will get their own pay scheme from %(date)s.",
            { people: peopleWords(this.chosen), date: this.p.date_words });
        return this.stillOpen > 0
            ? _t("%(base)s %(open)s still follow their team.", { base, open: peopleWords(this.stillOpen) })
            : base;
    }
    get applyLabel() {
        if (this.route) { return _t("Ask for this change"); }
        if (!this.chosen) { return _t("Give their pay scheme"); }
        return this.chosen === 1 ? _t("Give 1 person their pay scheme")
            : _t("Give %s people their pay scheme", num(this.chosen));
    }
    get heroLine() {
        const p = this.p;
        if (!p.people) { return _t("Nobody works in this company yet."); }
        if (!p.without) {
            return p.people === 1 ? _t("1 person has a pay scheme of their own.")
                : _t("All %s people have a pay scheme of their own.", num(p.people));
        }
        if (!p.counts.own) {
            return _t("%s people, and nobody has a pay scheme of their own yet.", num(p.people));
        }
        return _t("%(own)s of %(people)s people have a pay scheme of their own.",
            { own: num(p.counts.own), people: num(p.people) });
    }
    get heroSub() {
        return _t("Each person keeps the pay scheme that pays them today, written down as their own from %s. Nothing changes in anybody's pay.", this.p.date_words);
    }
    get ownLine() { return _t("Already have their own: %s", num(this.count("own"))); }
    keepLabel(r) { return _t("Keep %s", this.schemeName(r.today_id)); }
    get ringOffset() {
        const p = this.p;
        const share = p.people ? (p.counts.own || 0) / p.people : 0;
        return (94.25 * (1 - share)).toFixed(2);
    }
    get canApply() { return !this.state.busy && this.chosen > 0 && !this.p.blocked && this.p.can_propose; }

    async apply() {
        if (!this.canApply) { return; }
        this.state.busy = true;
        const skip = this.p.rows.filter((r) => (r.group === "ready" || r.group === "country")
            && !this.state.ticked.has(r.id)).map((r) => r.id);
        try {
            const answer = await this.orm.call(BOARD, "fill_apply", [this.props.companyId], {
                tick: ["ready", "country"], picks: this.state.picks, skip,
                employee_ids: this.props.filterIds || null,
            });
            if (answer && answer.ok === false) {
                this.state.done = { saved: false, failed: true, line: answer.message };
                return;
            }
            const saved = Boolean(answer && (answer.applied || answer.saved));
            const people = this.p.people;
            const ownAfter = (this.p.counts.own || 0) + (saved ? answer.people : 0);
            this.state.done = {
                saved,
                head: !saved ? _t("Sent for approval")
                    : (ownAfter >= people ? (people === 1 ? _t("1 person has a pay scheme")
                        : _t("All %s people have a pay scheme", num(people)))
                        : _t("%(own)s of %(people)s people have a pay scheme", { own: num(ownAfter), people: num(people) })),
                line: saved
                    ? _t("Their own pay scheme starts on %s. Nobody's pay changes: each person keeps the pay scheme that pays them today.", this.p.date_words)
                    : (answer.message || _t("Sent for approval.")),
            };
            if (this.props.onChanged) { await this.props.onChanged(); }
            if (saved) { await this.load(); }
        } catch (e) {
            this.state.done = { saved: false, failed: true, line: errorText(e) };
        } finally {
            this.state.busy = false;
        }
    }
    again() { this.state.done = null; }

    // ------------------------------------------------------------ undo
    get latest() { return this.p.latest || null; }
    get latestLine() {
        const f = this.latest;
        if (!f) { return ""; }
        return f.state === "undone"
            ? _t("The fill of %(date)s by %(who)s was undone on %(undone)s.", { date: f.date_words, who: f.who, undone: f.undone_words || "" })
            : _t("Last fill: %(date)s by %(who)s, %(people)s.", { date: f.date_words, who: f.who, people: peopleWords(f.people) });
    }
    get undoLine() {
        const u = (this.latest && this.latest.undo) || {};
        const base = _t("Undo takes off the pay schemes this fill gave %s. They go back to their team's usual pay scheme.", peopleWords(u.people || 0));
        if (!u.kept_count) { return base; }
        return _t("%(base)s %(kept)s changed since keep theirs: %(names)s.",
            { base, kept: peopleWords(u.kept_count), names: (u.kept || []).slice(0, 8).join(", ") });
    }
    get canUndo() { return Boolean(this.latest && this.latest.state === "done" && this.p.can_propose && !this.p.blocked); }
    askUndo() { this.state.confirmUndo = true; this.state.undoError = ""; }
    keepFill() { this.state.confirmUndo = false; }
    async undo() {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(BOARD, "fill_undo", [this.latest.id, this.props.companyId]);
            this.state.confirmUndo = false;
            const saved = Boolean(answer && (answer.applied || answer.saved));
            this.state.done = {
                saved, undo: true,
                head: saved ? _t("The fill is undone") : _t("Sent for approval"),
                line: saved ? _t("%s follow their team's usual pay scheme again.", peopleWords(answer.people || 0))
                    : (answer.message || _t("Sent for approval.")),
            };
            if (this.props.onChanged) { await this.props.onChanged(); }
            if (saved) { await this.load(); }
        } catch (e) {
            this.state.undoError = errorText(e);
        } finally {
            this.state.busy = false;
        }
    }
    onQuery(ev) { this.state.query = ev.target.value; }
    onKeydown(ev) {
        if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) { ev.preventDefault(); this.apply(); }
    }
}

// ===================================================================
//  "Set for everyone in this team…"
// ===================================================================
export class TeamSetDrawer extends Component {
    static template = "pb_scheme_map.TeamSetDrawer";
    static props = {
        companyId: Number, departmentId: Number,
        onClose: Function, onChanged: { type: Function, optional: true },
    };

    stay() { /* a click inside the drawer is not a click on the scrim */ }

    setup() {
        this.orm = useService("orm");
        this.ic = psIc;
        this.state = useState({
            loading: true, error: "", plan: null, pick: 0, advance: false, more: false,
            fill: new Set(), move: new Set(), alsoMove: false, moveDate: "",
            last: {}, busy: false, done: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            const plan = await this.orm.call(BOARD, "team_plan", [this.props.departmentId, this.props.companyId]);
            this.state.plan = plan;
            this.state.pick = plan.default_id || (plan.choices[0] && plan.choices[0].id) || 0;
            this.state.moveDate = plan.move_date;
            this.state.advance = this.defaultAdvance(this.state.pick);
            this.retick();
        } catch (e) {
            this.state.error = errorText(e, _t("The team could not be read. Try again."));
        } finally {
            this.state.loading = false;
        }
    }

    get p() { return this.state.plan || { people: [], choices: [] }; }
    get title() { return _t("Set for everyone in %s", this.p.department || "…"); }
    get route() { return this.p.lane === "route"; }
    get picked() { return this.p.choices.find((c) => c.id === this.state.pick) || null; }
    get without() { return this.p.people.filter((r) => !r.own); }
    get having() { return this.p.people.filter((r) => r.own); }
    get lead() {
        return this.p.teams > 1
            ? _t("The people of %(team)s and of %(count)s teams below it that have no usual pay scheme of their own. The team's usual pay scheme stays as it is.", { team: this.p.department, count: this.p.teams - 1 })
            : _t("The people of %s get a pay scheme of their own. The team's usual pay scheme stays as it is.", this.p.department);
    }
    fits(r) {
        const c = this.picked;
        return !(r.country && c && c.country_code && c.country_code !== r.country);
    }
    misfitLine(r) {
        const c = this.picked;
        return _t("Works in %(country)s. %(scheme)s is a pay scheme of %(other)s.",
            { country: this.countryName(r.country), scheme: c ? c.name : "", other: c ? c.country_name : "" });
    }
    /** A new scheme unticks whoever it does not fit; never ticks a mover. */
    retick() {
        const fill = new Set();
        for (const r of this.without) { if (this.fits(r)) { fill.add(r.id); } }
        this.state.fill = fill;
        this.state.move = new Set(this.state.alsoMove ? this.having.filter((r) => this.fits(r) && !this.same(r)).map((r) => r.id) : []);
    }
    same(r) {
        return Boolean(r.own && r.own.config_id === this.state.pick
            && (r.own.advance_id || false) === (this.state.advance || false));
    }

    // ---- cards
    get cards() { return this.state.more ? this.p.choices : this.p.choices.slice(0, 6); }
    get moreCards() { return Math.max(0, this.p.choices.length - 6); }
    get moreCardsLabel() { return this.state.more ? _t("Fewer pay schemes") : _t("Show %s more pay schemes", this.moreCards); }
    toggleMoreCards() { this.state.more = !this.state.more; }
    pickCard(c) {
        if (this.state.pick === c.id) { return; }
        this.state.pick = c.id;
        this.state.advance = this.defaultAdvance(c.id);
        this.retick();
    }
    onCardKey(c, ev) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); this.pickCard(c); return; }
        const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[ev.key];
        if (!step) { return; }
        ev.preventDefault();
        const list = this.cards;
        const at = list.findIndex((x) => x.id === c.id);
        const next = list[(at + step + list.length) % list.length];
        if (next) {
            this.pickCard(next);
            setTimeout(() => {
                const el = document.querySelector(".smp-pf-team .smp-ps-card.is-on");
                if (el) { el.focus(); }
            }, 60);
        }
    }
    meta(c) { return [c.currency, c.kind_words, c.country_name].filter(Boolean).join(" · "); }
    isUsual(c) { return c.id === this.p.usual_id; }

    // ---- the advance (ledger A13 / R7: only a real mid-month scheme)
    advancesFor(id) {
        const list = ((this.p.advances || {})[String(id)] || []).slice();
        const team = this.p.team_advance_id;
        if (team && !list.some((a) => a.id === team)) {
            const card = this.p.choices.find((c) => c.id === id);
            if (card && card.id === this.p.usual_id) {
                list.push({ id: team, name: (this.p.advance_names || {})[String(team)] || "" });
            }
        }
        return list;
    }
    defaultAdvance(id) {
        const list = this.advancesFor(id);
        if (this.p.team_advance_id && list.some((a) => a.id === this.p.team_advance_id)) { return this.p.team_advance_id; }
        return list.length === 1 ? list[0].id : false;
    }
    get advances() { return this.advancesFor(this.state.pick); }
    get oneAdvance() { return this.advances.length === 1 ? this.advances[0] : null; }
    toggleAdvance() {
        const one = this.oneAdvance;
        this.state.advance = this.state.advance ? false : (one ? one.id : false);
        this.retick();
    }
    onAdvanceSelect(ev) { this.state.advance = Number(ev.target.value) || false; this.retick(); }
    get advanceLine() { const one = this.oneAdvance; return one ? _t("Mid-month advance: %s", one.name) : ""; }

    // ---- ticks
    isFill(r) { return this.state.fill.has(r.id); }
    isMove(r) { return this.state.move.has(r.id); }
    onFill(r, ev) {
        const set = new Set(this.state.fill);
        const on = !set.has(r.id);
        if (ev && ev.shiftKey) { tickRange(this.without, set, this.state.last.fill, r.id, on); }
        else { on ? set.add(r.id) : set.delete(r.id); }
        this.state.last.fill = r.id;
        this.state.fill = set;
    }
    onMove(r, ev) {
        if (!this.state.alsoMove || this.same(r)) { return; }
        const set = new Set(this.state.move);
        const on = !set.has(r.id);
        if (ev && ev.shiftKey) { tickRange(this.having, set, this.state.last.move, r.id, on); }
        else { on ? set.add(r.id) : set.delete(r.id); }
        this.state.last.move = r.id;
        this.state.move = set;
    }
    allFill(on) { this.state.fill = new Set(on ? this.without.map((r) => r.id) : []); }
    toggleAlsoMove() {
        this.state.alsoMove = !this.state.alsoMove;
        this.state.move = new Set(this.state.alsoMove ? this.having.filter((r) => this.fits(r) && !this.same(r)).map((r) => r.id) : []);
    }
    onMoveDate(ev) { this.state.moveDate = ev.target.value; }
    get moveCount() { return this.having.filter((r) => this.state.move.has(r.id)).length; }
    get fillCount() { return this.without.filter((r) => this.state.fill.has(r.id)).length; }
    get alsoMoveLabel() { return _t("Also move these %s people", this.having.length); }
    get moveDateLine() {
        const iso = this.state.moveDate;
        if (!iso) { return _t("Pick the first day the new pay scheme pays."); }
        const day = iso.slice(-2);
        return day !== "01"
            ? _t("A change during a month starts with the next pay run. Their current pay scheme still pays %s.", monthWords(iso))
            : _t("First pay run on the new pay scheme: %s.", monthWords(iso));
    }
    get withoutTitle() { return _t("Without a pay scheme (%s)", this.without.length); }
    get havingTitle() { return _t("Already have their own (%s)", this.having.length); }
    get fillFromLine() { return _t("From %s, the first day of this month.", this.p.fill_date_words); }
    get sumLine() {
        const c = this.picked;
        const total = this.fillCount + this.moveCount;
        if (!c || !total) { return _t("Nobody is ticked yet."); }
        const parts = [];
        if (this.fillCount) { parts.push(_t("%(count)s from %(date)s", { count: this.fillCount, date: this.p.fill_date_words })); }
        if (this.moveCount) { parts.push(_t("%(count)s from %(date)s", { count: this.moveCount, date: dayWords(this.state.moveDate) })); }
        return _t("%(people)s will be paid by %(scheme)s: %(when)s.",
            { people: peopleWords(total), scheme: c.name, when: parts.join(", ") });
    }
    get applyLabel() {
        if (this.route) { return _t("Ask for this change"); }
        const n = this.fillCount + this.moveCount;
        return n === 1 ? _t("Set for 1 person") : _t("Set for %s people", n);
    }
    get canApply() {
        return !this.state.busy && this.state.pick && (this.fillCount + this.moveCount) > 0
            && !this.p.blocked && this.p.can_propose && (!this.moveCount || this.state.moveDate);
    }
    async apply() {
        if (!this.canApply) { return; }
        this.state.busy = true;
        try {
            const answer = await this.orm.call(BOARD, "team_apply", [
                this.props.departmentId, this.state.pick, this.state.advance || false,
                [...this.state.fill].filter((id) => this.without.some((r) => r.id === id)),
                [...this.state.move].filter((id) => this.having.some((r) => r.id === id)),
                this.state.moveDate, this.props.companyId]);
            if (answer && answer.ok === false) {
                this.state.done = { saved: false, failed: true, line: answer.message };
                return;
            }
            const saved = Boolean(answer && (answer.applied || answer.saved));
            const n = (answer.filled || 0) + (answer.moved || 0);
            this.state.done = {
                saved,
                head: saved ? _t("Set for %s", peopleWords(n)) : _t("Sent for approval"),
                line: saved ? _t("They are paid by %s. People who were not ticked keep what they had.", this.picked ? this.picked.name : "")
                    : (answer.message || _t("Sent for approval.")),
            };
            if (this.props.onChanged) { await this.props.onChanged(); }
        } catch (e) {
            this.state.done = { saved: false, failed: true, line: errorText(e) };
        } finally {
            this.state.busy = false;
        }
    }
    again() { this.state.done = null; this.load(); }
    onKeydown(ev) {
        if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) { ev.preventDefault(); this.apply(); }
    }
    countryName(code) { return code ? ((this.p.countries || {})[code] || code) : _t("No Country of work"); }
    countryChip(r) { return this.countryName(r.country); }
}

// ===================================================================
//  People paid by a pay scheme of another country
// ===================================================================
export class MismatchDrawer extends Component {
    static template = "pb_scheme_map.MismatchDrawer";
    static props = { companyId: Number, onClose: Function, onChanged: { type: Function, optional: true } };

    stay() { /* a click inside the drawer is not a click on the scrim */ }

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.ic = psIc;
        this.state = useState({ loading: true, error: "", data: null, busy: false, done: null });
        onWillStart(() => this.load());
    }
    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(BOARD, "mismatch_people", [this.props.companyId]);
        } catch (e) {
            this.state.error = errorText(e, _t("The list could not be read. Try again."));
        } finally {
            this.state.loading = false;
        }
    }
    get d() { return this.state.data || { people: [] }; }
    get route() { return this.d.lane === "route"; }
    fitsLine(r) { return _t("Fits their Country of work: %s", r.target); }
    line(r) {
        return _t("Works in %(country)s · paid by %(scheme)s (%(other)s)",
            { country: r.country_name, scheme: r.scheme, other: r.scheme_country_name });
    }
    get groups() { return this.d.groups || []; }
    bulkLabel(g) {
        return this.route ? _t("Ask to change these %s", g.employee_ids.length)
            : _t("Change these %(count)s to %(scheme)s", { count: g.employee_ids.length, scheme: g.target });
    }
    get bulkLine() { return _t("From %s. Each person's mid-month advance stays only when it is of the same country.", this.d.date_words); }
    get canChange() { return this.d.can_propose && !this.d.blocked; }
    openOne(r, ev) {
        const api = registry.category("pb_person_scheme").get("api", null);
        if (!api) { return; }
        api.open(this.dialog, {
            employeeId: r.employee_id, pick: r.target_id, opener: ev && ev.currentTarget,
            onSaved: async () => { await this.load(); if (this.props.onChanged) { await this.props.onChanged(); } },
        });
    }
    async changeAll(g) {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(BOARD, "mismatch_change", [
                g.employee_ids, g.target_id, this.d.date, this.props.companyId]);
            const saved = Boolean(answer && (answer.applied || answer.saved));
            this.state.done = {
                saved, failed: answer && answer.ok === false,
                line: saved ? _t("Changed. Their new pay scheme starts on %s.", this.d.date_words)
                    : (answer.message || _t("Sent for approval.")),
            };
            await this.load();
            if (this.props.onChanged) { await this.props.onChanged(); }
        } catch (e) {
            this.state.done = { saved: false, failed: true, line: errorText(e) };
        } finally {
            this.state.busy = false;
        }
    }
}

// ===================================================================
//  "M have their own" — the names
// ===================================================================
export class OwnPeoplePanel extends Component {
    static template = "pb_scheme_map.OwnPeoplePanel";
    static props = { companyId: Number, departmentId: Number, onClose: Function };
    stay() { /* a click inside the drawer is not a click on the scrim */ }

    setup() {
        this.orm = useService("orm");
        this.ic = psIc;
        this.state = useState({ loading: true, error: "", data: null });
        onWillStart(async () => {
            try {
                this.state.data = await this.orm.call(BOARD, "team_own_people", [this.props.departmentId, this.props.companyId]);
            } catch (e) {
                this.state.error = errorText(e, _t("The names could not be read. Try again."));
            }
            this.state.loading = false;
        });
    }
    get d() { return this.state.data || { people: [] }; }
    get title() { return _t("%s: people with a pay scheme of their own", this.d.department || ""); }
    advanceWords(r) { return _t("+ mid-month advance %s", r.advance); }
    sinceLine(r) { return r.since_words ? _t("From %s", r.since_words) : ""; }
    get moreLine() { return _t("and %s more", this.d.total - this.d.people.length); }
}

SchemeMapBoard.components = {
    ...(SchemeMapBoard.components || {}),
    PersonFillDrawer, TeamSetDrawer, MismatchDrawer, OwnPeoplePanel,
};
