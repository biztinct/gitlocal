/** @odoo-module **/
/**
 * Records Desk — how one value is SHOWN and how one value is TYPED.
 *
 * Two exports and one component:
 *
 *   `cellText(col, cell)`   what a cell reads as, dirty or clean
 *   `RdCellEditor`          the editor for a cell, chosen by the card's ttype
 *
 * The editor is one component with a switch rather than eight components,
 * because every one of them owes the grid the same three things — commit,
 * cancel, and move on — and eight copies of that contract is how two of them
 * end up disagreeing about what Escape does.
 *
 * A note on the pickers. A selection and a many2one both present as "a list you
 * filter and choose from", so they share `RdPicker`; the only difference is
 * where the rows come from (a fixed list of labels, or `lookup_m2o` debounced
 * over the wire) and whether an unmatched value can be created. That last bit
 * is shown, never guessed: `creates_missing` comes off the card, which got it
 * from the SAME predicate the import uses (`m2o_creates_missing`), so the
 * promise on screen and the behaviour on apply cannot drift apart.
 */
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** Card ttypes that take a free-text input. */
const TEXTISH = ["char", "text", "bank", "text_component"];
/** Card ttypes that are numbers. */
const NUMERIC = ["integer", "float", "monetary", "amount"];

export function isNumeric(ttype) {
    return NUMERIC.includes(ttype);
}

export function isTextish(ttype) {
    return TEXTISH.includes(ttype);
}

/** Group digits so a big amount is readable at a glance. */
export function formatNumber(value) {
    if (value === "" || value === null || value === undefined) {
        return "";
    }
    const n = Number(value);
    if (!isFinite(n)) {
        return String(value);
    }
    return n.toLocaleString("en-US", {
        minimumFractionDigits: 0,
        maximumFractionDigits: Number.isInteger(n) ? 0 : 2,
    });
}

/**
 * What the cell reads as.
 *
 * `cell` is `{v, label, missing}` from the server; `dirty` is `{value, label}`
 * when the person has typed something that is not saved yet. A dirty cell shows
 * the NEW text — the old one is rendered beneath it by the grid, struck
 * through, because "what it will become" is the thing being decided and "what
 * it was" is the thing being checked.
 */
export function cellText(col, cell, dirty) {
    if (dirty) {
        return dirty.label !== undefined ? dirty.label : String(dirty.value ?? "");
    }
    if (!cell) {
        return "";
    }
    if (cell.missing) {
        return "";
    }
    return cell.label || "";
}

/** The label a raw value should carry, for cards the client can label itself. */
export function labelFor(col, value) {
    if (col.ttype === "boolean") {
        return value ? _t("Yes") : _t("No");
    }
    if (col.ttype === "selection") {
        const hit = (col.selection || []).find((s) => s.key === value);
        return hit ? hit.label : String(value ?? "");
    }
    if (isNumeric(col.ttype)) {
        return formatNumber(value);
    }
    if (value && typeof value === "object") {
        return value.label || "";
    }
    return String(value ?? "");
}

// ---------------------------------------------------------------------------
//  RdPicker — one filterable list, two sources
// ---------------------------------------------------------------------------
export class RdPicker extends Component {
    static template = "pb_records.RdPicker";
    static props = {
        col: { type: Object },
        value: { optional: true },
        // async (term) => [{id|key, label}] — absent means a fixed list
        lookup: { type: Function, optional: true },
        onPick: { type: Function },
        onCancel: { type: Function },
    };

    setup() {
        this.state = useState({
            term: "",
            rows: this.staticRows(""),
            active: 0,
            loading: false,
        });
        this.inputRef = useRef("input");
        this._timer = null;
        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
                this.inputRef.el.select();
            }
            if (this.props.lookup) {
                this.search("");
            }
        });
        onWillUnmount(() => this._timer && clearTimeout(this._timer));
    }

    ic(n, s = 14) { return ic(n, s); }

    staticRows(term) {
        const t = (term || "").toLowerCase();
        return (this.props.col.selection || [])
            .filter((s) => !t || s.label.toLowerCase().includes(t)
                        || s.key.toLowerCase().includes(t))
            .map((s) => ({ key: s.key, label: s.label }));
    }

    /**
     * Free text with no match. It is offered as a row of its own ONLY when the
     * card says an unseen value would be created — offering it otherwise would
     * be an offer the apply refuses, and a control that promises what the server
     * declines is worse than no control (W29).
     */
    get createRow() {
        const term = (this.state.term || "").trim();
        if (!term || !this.props.lookup) { return null; }
        if (!(this.props.col.m2o && this.props.col.m2o.creates_missing)) { return null; }
        if (this.state.rows.some((r) => (r.label || "").toLowerCase() === term.toLowerCase())) {
            return null;
        }
        return { key: null, label: term, create: true };
    }

    get allRows() {
        const rows = [...this.state.rows];
        const extra = this.createRow;
        if (extra) { rows.push(extra); }
        return rows;
    }

    onInput(ev) {
        this.state.term = ev.target.value;
        if (!this.props.lookup) {
            this.state.rows = this.staticRows(this.state.term);
            this.state.active = 0;
            return;
        }
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.search(this.state.term), 220);
    }

    async search(term) {
        this.state.loading = true;
        try {
            const rows = await this.props.lookup(term);
            this.state.rows = rows || [];
            this.state.active = 0;
        } finally {
            this.state.loading = false;
        }
    }

    pick(row) {
        if (!row) { return; }
        if (row.create) {
            this.props.onPick({ value: row.label, label: row.label });
            return;
        }
        if (this.props.lookup) {
            this.props.onPick({ value: { id: row.id, label: row.label }, label: row.label });
            return;
        }
        this.props.onPick({ value: row.key, label: row.label });
    }

    /** Every handled key stops here — see `RdCellEditor.onKey` for why. */
    onKey(ev) {
        const rows = this.allRows;
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            ev.stopPropagation();
            this.state.active = Math.min(this.state.active + 1, rows.length - 1);
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            ev.stopPropagation();
            this.state.active = Math.max(this.state.active - 1, 0);
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            ev.stopPropagation();
            this.pick(rows[this.state.active]);
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.onCancel();
        }
    }

    get emptyLabel() {
        return this.props.lookup
            ? _t("Nothing matches — and records are not created here.")
            : _t("No choice matches that.");
    }
}

// ---------------------------------------------------------------------------
//  RdCellEditor — one cell, being typed into
// ---------------------------------------------------------------------------
export class RdCellEditor extends Component {
    static template = "pb_records.RdCellEditor";
    static components = { RdPicker };
    static props = {
        col: { type: Object },
        value: { optional: true },
        // (value, label) => void
        onCommit: { type: Function },
        onCancel: { type: Function },
        // "next" | "down" | null — where to go after committing
        onMove: { type: Function, optional: true },
        lookup: { type: Function, optional: true },
        // A wider popover for "Set for everyone selected…" reuses this editor.
        wide: { type: Boolean, optional: true },
    };

    setup() {
        this.inputRef = useRef("input");
        this.state = useState({ draft: this.initialDraft() });
        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
                if (this.inputRef.el.select) { this.inputRef.el.select(); }
            }
        });
    }

    ic(n, s = 14) { return ic(n, s); }

    get col() { return this.props.col; }
    get kind() {
        const t = this.col.ttype;
        if (t === "boolean") { return "boolean"; }
        if (t === "selection") { return "selection"; }
        if (t === "many2one") { return "m2o"; }
        if (t === "date") { return "date"; }
        if (t === "datetime") { return "date"; }
        if (isNumeric(t)) { return "number"; }
        return "text";
    }

    initialDraft() {
        const v = this.props.value;
        if (v === null || v === undefined || v === false) { return ""; }
        if (typeof v === "object") { return v.label || ""; }
        return String(v);
    }

    commitRaw(value, label) {
        this.props.onCommit(value, label === undefined ? labelFor(this.col, value) : label);
    }

    onInput(ev) { this.state.draft = ev.target.value; }

    /**
     * EVERY key this editor handles stops here.
     *
     * Without `stopPropagation` the keydown bubbles to the grid, which is
     * listening for the same keys — and since committing has already closed the
     * editor by then, the grid reads the very same Enter as "start editing" and
     * opens the editor again one row down. Found on the live walk: Enter
     * committed the cell and then put the NEXT one into edit mode.
     */
    onKey(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.stopPropagation();
            this.commitRaw(this.state.draft);
            if (this.props.onMove) { this.props.onMove("down"); }
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.onCancel();
        } else if (ev.key === "Tab") {
            ev.preventDefault();
            ev.stopPropagation();
            this.commitRaw(this.state.draft);
            if (this.props.onMove) { this.props.onMove(ev.shiftKey ? "prev" : "next"); }
        }
    }

    onBlur() {
        // A blur is a commit, never a silent discard: somebody who types a value
        // and clicks the next cell has said what they meant.
        if (this.kind === "text" || this.kind === "number" || this.kind === "date") {
            this.commitRaw(this.state.draft);
        }
    }

    setBool(flag) {
        this.commitRaw(flag, flag ? _t("Yes") : _t("No"));
    }

    onPick(picked) {
        this.commitRaw(picked.value, picked.label);
    }

    get yesLabel() { return _t("Yes"); }
    get noLabel() { return _t("No"); }
    get clearLabel() { return _t("Leave empty"); }

    clear() { this.commitRaw("", ""); }
}
