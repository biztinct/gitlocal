/** @odoo-module **/
/**
 * Updates — the review grid. The hero moment of the whole flow.
 *
 * One plain sentence ("This file will make 31 changes for 19 people. 2 cells
 * need your attention.") over a person × column grid in the FILE's row order:
 * before struck through above the new value, colour by what will happen, and
 * every cell that will not go in is something you can sort out right here —
 * type a different value (the desk judges it again), or leave it out. Rows that
 * match nobody sit in their own band above the grid; one can be bound to the
 * right person by hand, or skipped.
 *
 * Nothing on this screen writes. The grid's verdicts are the Records Desk's
 * (`pb.records.desk.preview_changes`, through `pb.updates.desk.recheck`), and
 * Apply re-evaluates everything on the server again.
 *
 * Three small components, because each owns state the grid must not re-render
 * for: the fix row owns its draft (typing in it would otherwise redraw 3,000
 * cells per key), the person finder owns its search, and the grid owns the rest.
 * The counting is plain functions over the review object, exported so the
 * sentences and the button label can be asserted without a server.
 */
import { Component, markup, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { grouped } from "@pb_records/js/records_review";

/** Rows drawn at once; "Show more" adds this many again. */
export const PAGE_ROWS = 150;

const ICONS = {};
/** Lucide glyphs this screen needs that the shared kit does not carry yet
 *  (same 24-unit grid, same stroke): `eraser` marks a value a file CLEARs. */
const LOCAL_GLYPHS = {
    // UPDATES P3a — the personal-details lane (Lucide `user-round`).
    userRound: '<circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/>',
    eraser: '<path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/><path d="M22 21H7"/><path d="m5 11 9 9"/>',
};
/** One markup object per icon and size, reused on every render (OWL t-out
 *  re-inserts a NEW markup every redraw — memory: owl-markup-flicker). */
export function icon(name, size = 16) {
    const key = `${name}:${size}`;
    if (!ICONS[key]) {
        ICONS[key] = LOCAL_GLYPHS[name]
            ? markup(`<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${LOCAL_GLYPHS[name]}</svg>`)
            : ic(name, size);
    }
    return ICONS[key];
}

/** One count, in the right number. Never "1 changes". */
export function plural(count, one, many) {
    return count === 1 ? one : many.replace("%s", grouped(count));
}

// ---------------------------------------------------------------------------
//  UPDATES P2c — when a row's changes start
// ---------------------------------------------------------------------------
/** "1 Dec 2026" in the reader's language, from `YYYY-MM-DD`. */
export function dayLabel(iso) {
    if (!iso) { return ""; }
    const day = luxon.DateTime.fromISO(iso);
    return day.isValid ? day.toFormat("d LLL yyyy") : iso;
}

/** The catalogue groups a future date holds back by default. */
export const DATED_GROUPS = ["contract", "component"];

/**
 * A row's start: its own date from the file, else the file's default, else
 * today. `{date, kind, error}` — `kind` is today · past · future · error.
 */
export function rowStart(rv, row) {
    const own = row.start || {};
    // A row whose own date cannot be read: its dated values are refused (the
    // server's rule), and what is left of it takes the default, like any row
    // without a date of its own. `error` says so for the Starts cell.
    const mine = own.error ? "" : own.date;
    const date = mine || rv.defaultStart || "";
    const error = own.error || "";
    if (!date || date === rv.today) { return { date: "", kind: "today", own: !!mine, error }; }
    return { date, kind: date < rv.today ? "past" : "future", own: !!mine, error };
}

/** Does this review show the "Starts" column? */
export function showsStarts(rv) {
    return !!(rv.dated || rv.defaultStart);
}

/**
 * Where each value Apply would send lands: `{now, later: {date: n},
 * past: {date: n}, dates}` — the server's own grouping
 * (`pb.updates.desk._split_by_start`), counted on screen for the summary.
 */
export function startBuckets(rv, scope = "pay") {
    const out = { now: 0, later: {}, past: {}, dates: new Set() };
    const groups = Object.fromEntries((rv.columns || []).map((c) => [c.field_id, c.group]));
    for (const row of rv.rows || []) {
        const start = rowStart(rv, row);
        for (const [fieldId, cell] of Object.entries(row.cells || {})) {
            if (cellKind(cell) !== "change") { continue; }
            if (start.kind === "future") {
                if (scope !== "all" && !DATED_GROUPS.includes(groups[fieldId])) {
                    out.now += 1;
                    continue;
                }
                out.later[start.date] = (out.later[start.date] || 0) + 1;
                out.dates.add(start.date);
            } else if (start.kind === "past") {
                out.past[start.date] = (out.past[start.date] || 0) + 1;
                out.dates.add(start.date);
            } else {
                out.now += 1;
            }
        }
    }
    return out;
}

/** What a cell will do: change · fix · left · same · dup · off · blank.
 *  `off` is a pay item that is not in the person's pay scheme: greyed, never
 *  sent, never a problem (UPDATES P2b). */
export function cellKind(cell) {
    if (!cell) { return "blank"; }
    if (cell.status === "off_scheme") { return "off"; }
    if (cell.left) { return "left"; }
    if (cell.status === "dup") { return "dup"; }
    if (cell.status === "ok") { return "change"; }
    if (cell.status === "refused") { return "fix"; }
    return "same";
}

/**
 * Every number the review screen says, from the review object alone.
 *
 * `changes` and `people` are what Apply would send; `attention` is cells that
 * still need a fix plus rows that match nobody and are not skipped; `leftOut`
 * is every value in the file that will NOT go in (refused, left out, or on a
 * row that matched nobody) — the honest third count on the Apply step.
 */
/** UPDATES P3a — the three lanes one file is split into, in order. */
export const LANES = ["details", "pay", "bank"];
export const LANE_ICON = { details: "userRound", pay: "banknote", bank: "landmark" };
export function laneLabel(lane) {
    return {
        details: _t("Personal details"),
        pay: _t("Pay and contract"),
        bank: _t("Bank details"),
    }[lane] || "";
}
/** What each lane does in one short phrase, for the legend. */
export function laneHint(lane) {
    return {
        details: _t("Change at once where your company allows it"),
        pay: _t("Follow your company's approval route"),
        bank: _t("Always need a second person"),
    }[lane] || "";
}

/** `{details: n, pay: n, bank: n}` — values that will change, per lane. */
export function laneCounts(rv) {
    const out = { details: 0, pay: 0, bank: 0 };
    const laneOf = {};
    for (const c of rv.columns || []) { laneOf[c.field_id] = c.lane; }
    for (const row of rv.rows || []) {
        for (const [fid, cell] of Object.entries(row.cells || {})) {
            const lane = laneOf[fid];
            if (lane && cellKind(cell) === "change") { out[lane] += 1; }
        }
    }
    return out;
}

export function reviewCounts(rv) {
    const out = { changes: 0, people: 0, cells: 0, rowsOpen: 0, attention: 0,
                  leftOut: 0, offScheme: 0, cleared: 0,
                  rows: { all: 0, chg: 0, att: 0, same: 0, off: 0, later: 0, past: 0 } };
    const people = new Set();
    for (const row of rv.rows || []) {
        if (showsStarts(rv)) {
            const kind = rowStart(rv, row).kind;
            if (kind === "future") { out.rows.later += 1; }
            if (kind === "past") { out.rows.past += 1; }
        }
        let hasChange = false;
        let hasFix = false;
        let hasOff = false;
        for (const cell of Object.values(row.cells || {})) {
            const kind = cellKind(cell);
            if (kind === "change") {
                out.changes += 1;
                hasChange = true;
                if (cell.cleared) { out.cleared += 1; }
            }
            else if (kind === "fix") { out.cells += 1; out.leftOut += 1; hasFix = true; }
            else if (kind === "left") { out.leftOut += 1; }
            else if (kind === "off") { out.offScheme += 1; hasOff = true; }
        }
        if (hasChange) { people.add(row.emp_id); }
        out.rows.all += 1;
        if (hasChange) { out.rows.chg += 1; }
        if (hasFix) { out.rows.att += 1; }
        if (hasOff) { out.rows.off += 1; }
        if (!hasChange && !hasFix) { out.rows.same += 1; }
    }
    for (const u of rv.unmatched || []) {
        if (u.bound) { continue; }
        out.leftOut += Object.keys(u.values || {}).length;
        if (!u.skipped) { out.rowsOpen += 1; }
    }
    out.people = people.size;
    out.attention = out.cells + out.rowsOpen;
    return out;
}

/**
 * True when a typed value says, word for word, what the screen shows today.
 * The server applies the same rule (`_same_text`): a named reference is looked
 * up by name, so a namesake would otherwise read as a change (ledger G11).
 */
export function sameText(typed, shown) {
    const norm = (v) => String(v === null || v === undefined ? "" : v).replace(/\s+/g, " ").trim();
    return !!norm(typed) && norm(typed) === norm(shown);
}

/** A cell's verdict from a recheck item (`pb.updates.desk.recheck`). */
export function cellFromItem(item, value) {
    const text = value === null || value === undefined ? "" : String(value);
    if (item.status !== "same" && item.status !== "off_scheme" && sameText(text, item.old_label)) {
        item.status = "same";
    }
    return {
        status: item.status, old: item.old_label || "",
        new: item.status === "off_scheme" ? text : (item.new_label || (item.cleared ? "" : text)),
        why: item.status === "refused" || item.status === "off_scheme" ? item.why : "",
        value: item.cleared ? "" : value, cleared: !!item.cleared,
        // UPDATES P2d — a one-off amount carries its number and its effect.
        amount: item.amount, role: item.role,
    };
}

// ---------------------------------------------------------------------------
//  UPDATES P2d — one-off pay items: totals per pay item and for the month
// ---------------------------------------------------------------------------
/** A number in the review's money: "1,500,000 ₫" / "$ 12.50". */
export function moneyLabel(rv, n) {
    const cur = (rv && rv.currency) || {};
    const digits = Number.isInteger(cur.digits) ? cur.digits : 0;
    const text = Number(n || 0).toLocaleString(undefined, {
        minimumFractionDigits: digits, maximumFractionDigits: digits });
    if (!cur.symbol) { return text; }
    return cur.position === "before" ? `${cur.symbol} ${text}` : `${text} ${cur.symbol}`;
}

/** `{byCol: {field_id: n}, earn, take}` over the amounts Apply would send. */
export function oneoffTotals(rv) {
    const out = { byCol: {}, earn: 0, take: 0 };
    const roles = Object.fromEntries((rv.columns || []).map((c) => [c.field_id, c.role]));
    for (const row of rv.rows || []) {
        for (const [fid, cell] of Object.entries(row.cells || {})) {
            if (cellKind(cell) !== "change" || cell.cleared) { continue; }
            const n = Number(cell.amount || 0);
            out.byCol[fid] = (out.byCol[fid] || 0) + n;
            if ((cell.role || roles[fid]) === "deduction") { out.take += n; } else { out.earn += n; }
        }
    }
    return out;
}

/** The changes Apply sends: every cell the desk said yes to, not left out.
 *  A row with its own start date (from the file) sends it with each value;
 *  the rest take the default the person picks on the Apply step. */
export function changesToSend(rv) {
    const out = [];
    for (const row of rv.rows || []) {
        const own = row.start && !row.start.error ? row.start.date : "";
        for (const [fieldId, cell] of Object.entries(row.cells || {})) {
            if (cellKind(cell) === "change") {
                const change = { emp_id: row.emp_id, field_id: fieldId, value: cell.value };
                if (own) { change.start = own; }
                out.push(change);
            }
        }
    }
    return out;
}

/** The Continue button's own promise. */
export function continueLabel(counts) {
    if (!counts.changes) { return _t("Nothing to apply yet"); }
    if (counts.attention === 1) { return _t("Continue without the 1 that needs attention"); }
    if (counts.attention) {
        return _t("Continue without the %s that need attention", grouped(counts.attention));
    }
    return _t("Continue");
}

// ---------------------------------------------------------------------------
//  UpdFixRow — sort one cell out without going back to Excel
// ---------------------------------------------------------------------------
export class UpdFixRow extends Component {
    static template = "pb_updates.UpdFixRow";
    static props = {
        cell: { type: Object },
        colspan: { type: Number },
        label: { type: String },
        person: { type: String },
        canWrite: { type: Boolean, optional: true },
        // (value) => Promise<{ok, why}>
        onCheck: { type: Function },
        onLeave: { type: Function },
        onRestore: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.cell = useState(this.props.cell);
        const cell = this.props.cell;
        this.state = useState({
            draft: cell.value === null || cell.value === undefined ? "" : String(cell.value),
            busy: false,
            msg: "",
        });
        this.input = useRef("input");
        onMounted(() => {
            const el = this.input.el;
            if (el) { el.focus(); el.select(); }
        });
    }

    icon(name, size) { return icon(name, size); }

    get kind() { return cellKind(this.cell); }

    get headline() {
        if (this.kind === "fix") { return _t("Needs a fix"); }
        if (this.kind === "left") { return _t("Left out"); }
        return _t("Will change");
    }

    get sentence() {
        const cell = this.cell;
        if (this.state.msg) { return this.state.msg; }
        if (this.kind === "fix" && cell.date_refused) {
            return _t("%s The value itself is fine: correct the date in your file and upload it again, or leave this one out.", cell.why || "");
        }
        if (this.kind === "fix") { return cell.why || _t("This value cannot be used as it is."); }
        if (this.kind === "left") { return _t("You chose to leave this value out. It stays as it is now."); }
        if (cell.cleared) {
            return _t("%(field)s is emptied. Today it is %(old)s.", { field: this.props.label, old: cell.old });
        }
        return cell.old
            ? _t("%(field)s goes from %(old)s to %(new)s.", { field: this.props.label, old: cell.old, new: cell.new })
            : _t("%(field)s is empty today and becomes %(new)s.", { field: this.props.label, new: cell.new });
    }

    onKey(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.onClose();
        } else if (ev.key === "Enter" && ev.target === this.input.el) {
            ev.preventDefault();
            this.check();
        }
    }

    async check() {
        const value = (this.state.draft || "").trim();
        if (!value) {
            this.state.msg = _t("Type a value first, or leave this one out.");
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.props.onCheck(value);
            if (res && !res.ok) { this.state.msg = res.why; }
        } finally {
            this.state.busy = false;
        }
    }
}

// ---------------------------------------------------------------------------
//  UpdPersonFinder — bind a row that matched nobody
// ---------------------------------------------------------------------------
export class UpdPersonFinder extends Component {
    static template = "pb_updates.UpdPersonFinder";
    static props = {
        // (term) => Promise<[{id, label}]>
        lookup: { type: Function },
        // ({id, label}) => void
        onPick: { type: Function },
        onCancel: { type: Function },
    };

    setup() {
        this.state = useState({ term: "", results: [], active: 0, busy: false, searched: false });
        this.input = useRef("input");
        this._timer = null;
        this._seq = 0;
        onMounted(() => this.input.el && this.input.el.focus());
        onWillUnmount(() => clearTimeout(this._timer));
    }

    icon(name, size) { return icon(name, size); }

    onInput(ev) {
        this.state.term = ev.target.value;
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.search(), 220);
    }

    async search() {
        const term = (this.state.term || "").trim();
        const seq = ++this._seq;
        if (!term) {
            Object.assign(this.state, { results: [], searched: false });
            return;
        }
        this.state.busy = true;
        const results = await this.props.lookup(term);
        if (seq !== this._seq) { return; }
        Object.assign(this.state, { results: results || [], active: 0, busy: false, searched: true });
    }

    onKey(ev) {
        const n = this.state.results.length;
        if (ev.key === "ArrowDown" && n) {
            ev.preventDefault();
            this.state.active = (this.state.active + 1) % n;
        } else if (ev.key === "ArrowUp" && n) {
            ev.preventDefault();
            this.state.active = (this.state.active - 1 + n) % n;
        } else if (ev.key === "Enter" && n) {
            ev.preventDefault();
            this.props.onPick(this.state.results[this.state.active]);
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.props.onCancel();
        }
    }
}

// ---------------------------------------------------------------------------
//  UpdReview — the grid, its sentence and its footer
// ---------------------------------------------------------------------------
export class UpdReview extends Component {
    static template = "pb_updates.UpdReview";
    static components = { UpdFixRow, UpdPersonFinder };
    static props = {
        rv: { type: Object },
        canWrite: { type: Boolean, optional: true },
        // (changes) => Promise<{items, counts}>
        recheck: { type: Function },
        // (term) => Promise<[{id,label}]>
        lookup: { type: Function },
        onBack: { type: Function },
        onContinue: { type: Function },
        onChangeMatching: { type: Function, optional: true },
    };

    setup() {
        this.ui = useState({ finder: -1, flash: "" });
        // Observe the review object the parent owns: every change made here
        // (a fix, a bound row, a filter) redraws this grid and the parent's
        // counts alike. A new review always mounts a new grid (the parent
        // keys its views), so the object never changes under this one.
        this._rv = useState(this.props.rv);
    }

    icon(name, size) { return icon(name, size); }
    kind(cell) { return cellKind(cell); }
    grouped(n) { return grouped(n); }
    get rv() { return this._rv; }
    get counts() { return reviewCounts(this.rv); }

    // ------------------------------------------------------------- the words
    get heroParts() {
        const c = this.counts;
        if (!c.changes && !c.attention) {
            return { lead: _t("Every value in this file is already on record."),
                     tail: _t("There is nothing to change."), tone: "fine" };
        }
        const lead = c.changes
            ? (this.rv.oneoff
                ? _t("This sheet sends %(amounts)s for %(people)s, paid in %(month)s.", {
                    amounts: plural(c.changes, _t("1 one-off amount"), _t("%s one-off amounts")),
                    people: plural(c.people, _t("1 person"), _t("%s people")),
                    month: this.rv.month_label || "" })
                : _t("This file will make %(changes)s for %(people)s.", {
                    changes: plural(c.changes, _t("1 change"), _t("%s changes")),
                    people: plural(c.people, _t("1 person"), _t("%s people")) }))
            : _t("Nothing in this file can go in yet.");
        if (!c.attention) {
            return { lead, tail: _t("Everything checks out."), tone: "fine" };
        }
        const bits = [];
        if (c.cells) { bits.push(plural(c.cells, _t("1 cell"), _t("%s cells"))); }
        if (c.rowsOpen) { bits.push(plural(c.rowsOpen, _t("1 row"), _t("%s rows"))); }
        const who = bits.join(_t(" and "));
        return { lead, tone: "att",
                 tail: c.attention === 1 ? _t("%s needs your attention.", who)
                                         : _t("%s need your attention.", who) };
    }

    get identityLine() {
        return {
            code: _t("Rows were matched to people by employee code."),
            email: _t("Rows were matched to people by work email."),
            name: _t("Rows were matched to people by name."),
        }[this.rv.identity] || "";
    }

    get ignoredLine() {
        const ignored = (this.rv.summary && this.rv.summary.columns_ignored) || [];
        return ignored.length ? _t("Not brought in: %s.", ignored.join(", ")) : "";
    }

    get filters() {
        const c = this.counts.rows;
        const out = [
            { key: "all", label: _t("Everyone"), count: c.all },
            { key: "chg", label: _t("With changes"), count: c.chg },
            { key: "att", label: _t("Needs attention"), count: c.att },
            { key: "same", label: _t("Nothing to change"), count: c.same },
        ];
        if (this.counts.offScheme) {
            // Counted in VALUES, never red: it is not something to fix.
            out.push({ key: "off", label: _t("Not in their pay scheme"), count: this.counts.offScheme, quiet: true });
        }
        // UPDATES P2c — rows by when they start (rows, not values).
        if (c.later) { out.push({ key: "later", label: _t("Starts later"), count: c.later, when: "later" }); }
        if (c.past) { out.push({ key: "past", label: _t("Dated in the past"), count: c.past, when: "past" }); }
        return out;
    }

    // ------------------------------------------------------------- one-offs (P2d)
    get totals() { return oneoffTotals(this.rv); }
    money(n) { return moneyLabel(this.rv, n); }
    colTotal(col) {
        const n = this.totals.byCol[col.field_id] || 0;
        return n ? this.money(n) : "";
    }
    roleLabel(col) {
        if (!col.role) { return ""; }
        return col.role === "deduction" ? _t("Takes from pay") : _t("Adds to pay");
    }
    get paidMonthRows() { return (this.rv.rows || []).filter((r) => r.paid_month).length; }
    get stripMonthLine() { return _t("One-off pay for %s", this.rv.month_label || ""); }
    get paidMonthChip() {
        const n = this.paidMonthRows;
        return n === 1 ? _t("1 person already paid for %s", this.rv.month_label || "")
            : _t("%(n)s people already paid for %(month)s", { n, month: this.rv.month_label || "" });
    }
    get paidTag() { return _t("Already paid for %s", this.rv.month_label || ""); }

    // ------------------------------------------------------------- start dates
    get showStarts() { return showsStarts(this.rv); }

    /** The "Starts" cell of a row: what it says, its icon, tone and tooltip. */
    startCell(row) {
        const s = rowStart(this.rv, row);
        if (s.error) {
            return { kind: "error", label: _t("Not a date"), icon: "alert", title: s.error };
        }
        if (s.kind === "past") {
            return { kind: "past", label: dayLabel(s.date), icon: "history",
                     title: _t("Recorded as starting on %s. Pay runs already finished are not recalculated.", dayLabel(s.date)) };
        }
        if (s.kind === "future") {
            return { kind: "future", label: dayLabel(s.date), icon: "calendarClock",
                     title: _t("Scheduled: written on %s, not before.", dayLabel(s.date)) };
        }
        return { kind: "today", label: _t("Today"), icon: "", title: _t("Changes as soon as it is applied.") };
    }

    // ------------------------------------------------------------- pay schemes
    /** "Pay schemes in this file": one chip per scheme with its head-count. */
    get schemeChips() {
        const rv = this.rv;
        if (!rv.pay_items) { return []; }
        const out = (rv.schemes || []).map((s) => ({
            key: `s${s.id}`, id: s.id, label: s.name, count: s.count, tone: "pri" }));
        if (rv.no_scheme) {
            out.push({ key: "none", id: "none", label: _t("No pay scheme yet"), count: rv.no_scheme, tone: "warn" });
        }
        return out;
    }

    setScheme(id) {
        this.rv.scheme = this.rv.scheme === id ? null : id;
        this.rv.limit = PAGE_ROWS;
        this.rv.fix = null;
    }

    inScheme(row) {
        const s = this.rv.scheme;
        if (s === null || s === undefined) { return true; }
        if (s === "none") { return !!row.no_scheme; }
        return (row.scheme_ids || []).includes(s);
    }

    noSchemeTitle() {
        return _t("No pay scheme covers this person yet. Pay items are still saved on their contract.");
    }

    setFilter(key) {
        this.rv.filter = key;
        this.rv.limit = PAGE_ROWS;
        this.rv.fix = null;
    }

    rowClass(row) {
        let change = false;
        let fix = false;
        let off = false;
        for (const cell of Object.values(row.cells)) {
            const kind = cellKind(cell);
            if (kind === "change") { change = true; }
            if (kind === "fix") { fix = true; }
            if (kind === "off") { off = true; }
        }
        return { change, fix, off };
    }

    get filteredRows() {
        const f = this.rv.filter;
        const rows = this.rv.scheme === null || this.rv.scheme === undefined
            ? this.rv.rows : this.rv.rows.filter((row) => this.inScheme(row));
        if (f === "all") { return rows; }
        if (f === "later" || f === "past") {
            const want = f === "later" ? "future" : "past";
            return rows.filter((row) => rowStart(this.rv, row).kind === want);
        }
        return rows.filter((row) => {
            const k = this.rowClass(row);
            if (f === "chg") { return k.change; }
            if (f === "att") { return k.fix; }
            if (f === "off") { return k.off; }
            return !k.change && !k.fix;
        });
    }

    get pageRows() { return this.filteredRows.slice(0, this.rv.limit); }
    get moreRows() { return Math.max(0, this.filteredRows.length - this.rv.limit); }
    showMore() { this.rv.limit += PAGE_ROWS; }
    get moreLabel() {
        return _t("Show %(n)s more (%(left)s not shown yet)", {
            n: grouped(Math.min(PAGE_ROWS, this.moreRows)), left: grouped(this.moreRows) });
    }

    /** Only the columns something happens in, unless asked for all of them. */
    get columns() {
        if (this.rv.allCols) { return this.rv.columns; }
        const live = new Set();
        for (const row of this.rv.rows) {
            for (const [fid, cell] of Object.entries(row.cells)) {
                const kind = cellKind(cell);
                if (kind === "change" || kind === "fix" || kind === "left" || kind === "off") { live.add(fid); }
            }
        }
        const cols = this.rv.columns.filter((c) => live.has(c.field_id));
        return cols.length ? cols : this.rv.columns;
    }

    get hiddenColumns() { return this.rv.columns.length - this.columns.length; }

    // ------------------------------------------------- UPDATES P3a — lanes
    laneIcon(lane) { return LANE_ICON[lane] || "pencil"; }
    laneLabel(lane) { return laneLabel(lane); }

    /** The legend strip: each lane in this file, its count and its rule. */
    get laneStrip() {
        if (this.rv.oneoff) { return []; }
        const counts = laneCounts(this.rv);
        const present = new Set((this.rv.columns || []).map((c) => c.lane).filter(Boolean));
        return LANES.filter((l) => present.has(l)).map((lane) => ({
            lane, label: laneLabel(lane), hint: laneHint(lane), count: counts[lane],
            icon: LANE_ICON[lane],
        }));
    }

    get columnsToggleLabel() {
        return this.rv.allCols
            ? _t("Only columns with changes")
            : _t("Show all %s columns", grouped(this.rv.columns.length));
    }

    // ------------------------------------------------------------- cells
    cellClass(row, col) {
        const cell = row.cells[col.field_id];
        const kind = cellKind(cell);
        const flash = this.ui.flash === `${row.key}|${col.field_id}`;
        return `pbu-c pbu-c--${kind}${cell && cell.fixed ? " is-fixed" : ""}${flash ? " is-flash" : ""}${this.isOpen(row, col) ? " is-open" : ""}`;
    }

    cellTitle(row, col) {
        const cell = row.cells[col.field_id];
        const kind = cellKind(cell);
        if (kind === "blank") { return _t("Blank in your file, so nothing changes."); }
        if (kind === "same") { return _t("Already set to this. Nothing changes."); }
        if (kind === "dup") { return cell.why; }
        if (kind === "fix") { return cell.why; }
        if (kind === "off") { return cell.why; }
        if (kind === "same" && cell.cleared) { return _t("Already empty. Nothing changes."); }
        if (kind === "change" && cell.cleared) {
            return _t("Emptied on apply (the file says CLEAR). Press Enter to leave it out or change it.");
        }
        if (kind === "left") { return _t("Left out. It stays as it is now."); }
        return _t("Changes on apply. Press Enter to leave it out or change it.");
    }

    isActionable(row, col) {
        const kind = cellKind(row.cells[col.field_id]);
        return kind === "change" || kind === "fix" || kind === "left";
    }

    isOpen(row, col) {
        const fix = this.rv.fix;
        return !!fix && fix.rowKey === row.key && fix.fieldId === col.field_id;
    }

    rowOpen(row) { return !!this.rv.fix && this.rv.fix.rowKey === row.key; }

    openFix(row, col) {
        if (!this.isActionable(row, col)) { return; }
        this.rv.fix = this.isOpen(row, col) ? null : { rowKey: row.key, fieldId: col.field_id };
    }

    onCellKey(ev, row, col) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.openFix(row, col);
        } else if (ev.key === "Escape" && this.rv.fix) {
            ev.preventDefault();
            this.closeFix();
        }
    }

    closeFix() {
        const fix = this.rv.fix;
        this.rv.fix = null;
        if (fix) { this.focusCell(fix.rowKey, fix.fieldId); }
    }

    focusCell(rowKey, fieldId) {
        // After the fix row is gone the cell is still in the DOM; give the
        // keyboard back to it so Esc never strands focus at the page top.
        setTimeout(() => {
            const el = document.querySelector(`.pbu-grid [data-cell="${rowKey}|${fieldId}"]`);
            if (el) { el.focus(); }
        }, 0);
    }

    fixFor(row) {
        const fix = this.rv.fix;
        return fix && fix.rowKey === row.key ? row.cells[fix.fieldId] : null;
    }

    fixLabel() {
        const fix = this.rv.fix;
        const col = fix && this.rv.columns.find((c) => c.field_id === fix.fieldId);
        return col ? col.label : "";
    }

    flash(rowKey, fieldId) {
        this.ui.flash = `${rowKey}|${fieldId}`;
        setTimeout(() => {
            if (this.ui.flash === `${rowKey}|${fieldId}`) { this.ui.flash = ""; }
        }, 900);
    }

    /** Ask the desk about one typed value; the cell takes its verdict. */
    async checkValue(row, value) {
        const fieldId = this.rv.fix.fieldId;
        if (row.cells[fieldId] && row.cells[fieldId].date_refused) {
            // The VALUE is not the problem: this row's start date is.
            return { ok: false, why: row.cells[fieldId].why };
        }
        const res = await this.props.recheck([{ emp_id: row.emp_id, field_id: fieldId, value }]);
        const item = (res.items || []).find((i) => i.field_id === fieldId) || (res.items || [])[0];
        if (!item) { return { ok: false, why: _t("This value could not be checked. Try again.") }; }
        const cell = row.cells[fieldId];
        const next = cellFromItem(item, value);
        if (next.status === "ok" || next.status === "same" || next.status === "off_scheme") {
            Object.assign(cell, next, { left: false, fixed: next.status !== "off_scheme" });
            this.closeFix();
            this.flash(row.key, fieldId);
            return { ok: true };
        }
        Object.assign(cell, { why: item.why, value, new: value });
        return { ok: false, why: item.why };
    }

    leaveOut(row) {
        const fieldId = this.rv.fix.fieldId;
        row.cells[fieldId].left = true;
        this.closeFix();
    }

    restore(row) {
        const fieldId = this.rv.fix.fieldId;
        row.cells[fieldId].left = false;
        this.closeFix();
    }

    // ------------------------------------------------------------- unmatched
    get openUnmatched() { return (this.rv.unmatched || []).filter((u) => !u.bound); }

    unmatchedTitle(u) {
        const bits = [u.code, u.name, u.email].filter(Boolean);
        return bits.length ? bits.join(" · ") : _t("A row with no name or code");
    }

    unmatchedValues(u) {
        const labels = Object.fromEntries(this.rv.columns.map((c) => [c.field_id, c.label]));
        return Object.entries(u.values || {}).map(([fid, v]) => `${labels[fid] || fid}: ${v === "" ? _t("CLEAR") : v}`).join(" · ");
    }

    valuesWaiting(u) {
        return plural(Object.keys(u.values || {}).length, _t("1 value waiting"), _t("%s values waiting"));
    }

    startFind(index) { this.ui.finder = this.ui.finder === index ? -1 : index; }
    cancelFind() { this.ui.finder = -1; }
    skip(u) { u.skipped = true; this.ui.finder = -1; }
    unskip(u) { u.skipped = false; }

    /** Bind the row, then let the desk judge its values like any other row. */
    async bind(u, person) {
        this.ui.finder = -1;
        const changes = Object.entries(u.values || {}).map(([fieldId, value]) => ({
            emp_id: person.id, field_id: fieldId, value }));
        const res = changes.length ? await this.props.recheck(changes) : { items: [] };
        const cells = {};
        const groups = Object.fromEntries(this.rv.columns.map((c) => [c.field_id, c.group]));
        const badDate = u.start && u.start.error;
        for (const change of changes) {
            const item = (res.items || []).find((i) => i.field_id === change.field_id) || null;
            const text = change.value === null || change.value === undefined ? "" : String(change.value);
            if (badDate && DATED_GROUPS.includes(groups[change.field_id])) {
                // UPDATES P2c: the row's start date cannot be read.
                cells[change.field_id] = { status: "refused", date_refused: true, old: "",
                                           new: text, value: change.value, why: u.start.error };
                continue;
            }
            cells[change.field_id] = item
                ? cellFromItem(item, change.value)
                : { status: "refused", old: "", new: text, value: change.value,
                    why: _t("This value could not be checked. Try again.") };
        }
        const [name, rest] = String(person.label || "").split(" — ");
        const scheme = (res.people || {})[String(person.id)] || {};
        const row = { key: `u${u.row}`, row: u.row, emp_id: person.id, name: name || "",
                      code: rest || "", department: "", twice: false, bound: true, cells,
                      scheme: scheme.scheme || "", scheme_ids: scheme.scheme_ids || [],
                      no_scheme: !!scheme.no_scheme, start: u.start || undefined };
        const at = this.rv.rows.findIndex((r) => r.row > u.row);
        if (at === -1) { this.rv.rows.push(row); } else { this.rv.rows.splice(at, 0, row); }
        u.bound = true;
        this.flash(row.key, Object.keys(cells)[0] || "");
    }

    // ------------------------------------------------------------- footer
    get continueLabel() { return continueLabel(this.counts); }
    get canContinue() { return this.counts.changes > 0; }
    get attentionNote() {
        const c = this.counts;
        if (!c.attention || !c.changes) { return ""; }
        return _t("Cells and rows that still need attention are simply not applied. Nothing is lost: they stay as they are now.");
    }
    get noWriteLine() {
        return _t("You can look through these changes, but applying them needs permission to change employee records. Ask an administrator for the HR or Payroll Officer role.");
    }
}
