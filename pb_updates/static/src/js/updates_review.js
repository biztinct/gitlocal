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
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { grouped } from "@pb_records/js/records_review";

/** Rows drawn at once; "Show more" adds this many again. */
export const PAGE_ROWS = 150;

const ICONS = {};
/** One markup object per icon and size, reused on every render (OWL t-out
 *  re-inserts a NEW markup every redraw — memory: owl-markup-flicker). */
export function icon(name, size = 16) {
    const key = `${name}:${size}`;
    if (!ICONS[key]) { ICONS[key] = ic(name, size); }
    return ICONS[key];
}

/** One count, in the right number. Never "1 changes". */
export function plural(count, one, many) {
    return count === 1 ? one : many.replace("%s", grouped(count));
}

/** What a cell will do: change · fix · left · same · dup · blank. */
export function cellKind(cell) {
    if (!cell) { return "blank"; }
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
export function reviewCounts(rv) {
    const out = { changes: 0, people: 0, cells: 0, rowsOpen: 0, attention: 0,
                  leftOut: 0, rows: { all: 0, chg: 0, att: 0, same: 0 } };
    const people = new Set();
    for (const row of rv.rows || []) {
        let hasChange = false;
        let hasFix = false;
        for (const cell of Object.values(row.cells || {})) {
            const kind = cellKind(cell);
            if (kind === "change") { out.changes += 1; hasChange = true; }
            else if (kind === "fix") { out.cells += 1; out.leftOut += 1; hasFix = true; }
            else if (kind === "left") { out.leftOut += 1; }
        }
        if (hasChange) { people.add(row.emp_id); }
        out.rows.all += 1;
        if (hasChange) { out.rows.chg += 1; }
        if (hasFix) { out.rows.att += 1; }
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

/** The changes Apply sends: every cell the desk said yes to, not left out. */
export function changesToSend(rv) {
    const out = [];
    for (const row of rv.rows || []) {
        for (const [fieldId, cell] of Object.entries(row.cells || {})) {
            if (cellKind(cell) === "change") {
                out.push({ emp_id: row.emp_id, field_id: fieldId, value: cell.value });
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
        if (this.kind === "fix") { return cell.why || _t("This value cannot be used as it is."); }
        if (this.kind === "left") { return _t("You chose to leave this value out. It stays as it is now."); }
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
            ? _t("This file will make %(changes)s for %(people)s.", {
                changes: plural(c.changes, _t("1 change"), _t("%s changes")),
                people: plural(c.people, _t("1 person"), _t("%s people")) })
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
        return [
            { key: "all", label: _t("Everyone"), count: c.all },
            { key: "chg", label: _t("With changes"), count: c.chg },
            { key: "att", label: _t("Needs attention"), count: c.att },
            { key: "same", label: _t("Nothing to change"), count: c.same },
        ];
    }

    setFilter(key) {
        this.rv.filter = key;
        this.rv.limit = PAGE_ROWS;
        this.rv.fix = null;
    }

    rowClass(row) {
        let change = false;
        let fix = false;
        for (const cell of Object.values(row.cells)) {
            const kind = cellKind(cell);
            if (kind === "change") { change = true; }
            if (kind === "fix") { fix = true; }
        }
        return { change, fix };
    }

    get filteredRows() {
        const f = this.rv.filter;
        if (f === "all") { return this.rv.rows; }
        return this.rv.rows.filter((row) => {
            const k = this.rowClass(row);
            if (f === "chg") { return k.change; }
            if (f === "att") { return k.fix; }
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
                if (kind === "change" || kind === "fix" || kind === "left") { live.add(fid); }
            }
        }
        const cols = this.rv.columns.filter((c) => live.has(c.field_id));
        return cols.length ? cols : this.rv.columns;
    }

    get hiddenColumns() { return this.rv.columns.length - this.columns.length; }

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
        const res = await this.props.recheck([{ emp_id: row.emp_id, field_id: fieldId, value }]);
        const item = (res.items || []).find((i) => i.field_id === fieldId) || (res.items || [])[0];
        if (!item) { return { ok: false, why: _t("This value could not be checked. Try again.") }; }
        const cell = row.cells[fieldId];
        if (item.status !== "same" && sameText(value, item.old_label)) { item.status = "same"; }
        if (item.status === "ok") {
            Object.assign(cell, { status: "ok", old: item.old_label || "", new: item.new_label || value,
                                  why: "", value, left: false, fixed: true });
            this.closeFix();
            this.flash(row.key, fieldId);
            return { ok: true };
        }
        if (item.status === "same") {
            Object.assign(cell, { status: "same", old: item.old_label || "", new: item.new_label || value,
                                  why: "", value, left: false, fixed: true });
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
        return Object.entries(u.values || {}).map(([fid, v]) => `${labels[fid] || fid}: ${v}`).join(" · ");
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
        for (const change of changes) {
            const item = (res.items || []).find((i) => i.field_id === change.field_id) || null;
            const text = change.value === null || change.value === undefined ? "" : String(change.value);
            if (item && item.status !== "same" && sameText(text, item.old_label)) { item.status = "same"; }
            cells[change.field_id] = item
                ? { status: item.status, old: item.old_label || "", new: item.new_label || text,
                    why: item.status === "refused" ? item.why : "", value: change.value }
                : { status: "refused", old: "", new: text, value: change.value,
                    why: _t("This value could not be checked. Try again.") };
        }
        const [name, rest] = String(person.label || "").split(" — ");
        const row = { key: `u${u.row}`, row: u.row, emp_id: person.id, name: name || "",
                      code: rest || "", department: "", twice: false, bound: true, cells };
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
