/** @odoo-module **/
/**
 * Records Desk — the file half.
 *
 * Two components and two sentences, and the sentences are the point.
 *
 * The hero moment of R3 is that dropping the file you exported does NOT open a
 * second import system: it opens the SAME review drawer the grid opens, already
 * knowing what the file would do — *"This file changes 41 values on 19 people ·
 * 3 rows match nobody · 2 values need a look"* — with every row shown as
 * `old → new` before a single value is written. So the two functions that build
 * those sentences live here, as plain functions over the summary the server
 * returns, and they are tested directly: a count a person reads twice before
 * pressing Apply is a count that must be right in both its singular and its
 * plural, and neither form can be interpolated out of the other.
 *
 * `RdDropZone` owns exactly one thing the desk should not: the drag counter.
 * `dragenter`/`dragleave` fire for every child element the pointer crosses, so
 * a naive boolean flickers the overlay off the moment the pointer moves over
 * the text inside the zone. The depth counter is why the overlay is steady.
 *
 * `RdFileReview` is the drawer's BODY in file mode — three tabs over what the
 * peek found. The drawer chrome (header, note, Apply) stays where it always
 * was, because "the same drawer" has to be literally true or the promise is
 * only a visual resemblance.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { RdPicker } from "@pb_records/js/records_cells";

/** One count, in the right number. Never `1 changes`. */
function n(count, one, many) {
    return count === 1 ? _t(one) : _t(many, count);
}

/**
 * What the file would do, in one line, before anything is written.
 */
export function fileSummaryLine(summary) {
    const s = summary || {};
    const parts = [];
    if (s.changes_ok) {
        parts.push(_t("This file changes ")
            + n(s.changes_ok, "1 value", "%s values") + " "
            + n(s.people_changed || 0, "on 1 person", "on %s people"));
    } else {
        parts.push(_t("This file changes nothing yet"));
    }
    if (s.people_unmatched) {
        parts.push(n(s.people_unmatched, "1 row matches nobody",
                     "%s rows match nobody"));
    }
    if (s.changes_refused) {
        parts.push(n(s.changes_refused, "1 value needs a look",
                     "%s values need a look"));
    }
    if (s.changes_same) {
        parts.push(n(s.changes_same, "1 is already set", "%s are already set"));
    }
    return parts.join(" · ");
}

/** The Apply button's own promise: what goes in, and what stays behind. */
export function fileApplyLabel(summary) {
    const s = summary || {};
    if (!s.changes_ok) { return _t("Nothing to apply"); }
    if (s.changes_refused) {
        return _t("Apply %(ok)s · leave %(bad)s",
                  { ok: s.changes_ok, bad: s.changes_refused });
    }
    return n(s.changes_ok, "Apply 1 change", "Apply %s changes");
}

/** How the rows were matched, said in the words a person would use. */
export function identityLine(identity) {
    return {
        code: _t("Rows were matched by employee code."),
        email: _t("Rows were matched by work email."),
        name: _t("Rows were matched by name."),
    }[identity] || _t("Rows were matched to people already in Payobook.");
}

// ---------------------------------------------------------------------------
//  RdDropZone — a file arrives
// ---------------------------------------------------------------------------
export class RdDropZone extends Component {
    static template = "pb_records.RdDropZone";
    static props = {
        // (File) => void
        onFile: { type: Function },
        label: { type: String, optional: true },
        hint: { type: String, optional: true },
        busy: { type: Boolean, optional: true },
        busyLabel: { type: String, optional: true },
    };

    setup() {
        // A DEPTH, not a boolean. `dragleave` fires when the pointer crosses on
        // to a CHILD of the zone, so a boolean turns the overlay off while the
        // file is still very much over it.
        this.state = useState({ depth: 0 });
    }

    ic(name, size = 16) { return ic(name, size); }

    get over() { return this.state.depth > 0; }

    onDragEnter(ev) {
        ev.preventDefault();
        this.state.depth += 1;
    }

    onDragOver(ev) { ev.preventDefault(); }

    onDragLeave(ev) {
        ev.preventDefault();
        this.state.depth = Math.max(0, this.state.depth - 1);
    }

    onDrop(ev) {
        ev.preventDefault();
        this.state.depth = 0;
        const file = ev.dataTransfer && ev.dataTransfer.files
            && ev.dataTransfer.files[0];
        if (file) { this.props.onFile(file); }
    }

    onPick(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (file) { this.props.onFile(file); }
        ev.target.value = "";
    }

    get zoneLabel() {
        return this.props.label || _t("Drop a records file, or click");
    }

    get zoneHint() {
        return this.props.hint || _t(".xlsx or .csv");
    }

    get overLabel() { return _t("Drop to review changes"); }
}

// ---------------------------------------------------------------------------
//  RdFileReview — the drawer's body, in file mode
// ---------------------------------------------------------------------------
export class RdFileReview extends Component {
    static template = "pb_records.RdFileReview";
    static components = { RdPicker };
    static props = {
        summary: { type: Object },
        items: { type: Array },
        unmatched: { type: Array },
        identity: { type: String, optional: true },
        // (rowIndex, {id,label}) => void — bind an unmatched row by hand
        onBind: { type: Function, optional: true },
        // (term) => Promise<[{id,label}]>
        lookup: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ tab: "changes", binding: -1 });
    }

    ic(name, size = 14) { return ic(name, size); }

    get ignored() {
        return (this.props.summary && this.props.summary.columns_ignored) || [];
    }

    get tabs() {
        const s = this.props.summary || {};
        return [
            { key: "changes", label: _t("Changes"),
              count: (s.changes_ok || 0) + (s.changes_refused || 0) },
            { key: "unmatched", label: _t("Unmatched"),
              count: s.people_unmatched || 0 },
            { key: "ignored", label: _t("Ignored columns"),
              count: this.ignored.length },
        ];
    }

    isOn(key) { return this.state.tab === key; }

    show(key) {
        this.state.tab = key;
        this.state.binding = -1;
    }

    /** Left/Right walk the tabs — the ARIA tablist contract, not a nicety. */
    onTabKey(ev) {
        if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") { return; }
        ev.preventDefault();
        const keys = this.tabs.map((t) => t.key);
        const at = keys.indexOf(this.state.tab);
        const next = ev.key === "ArrowRight"
            ? (at + 1) % keys.length
            : (at - 1 + keys.length) % keys.length;
        this.show(keys[next]);
    }

    /** Only the rows worth reading: an unchanged value is not a change. */
    get rows() {
        return this.props.items.filter((i) => i.status !== "same");
    }

    get people() {
        const byPerson = new Map();
        for (const item of this.rows) {
            if (!byPerson.has(item.emp_id)) {
                byPerson.set(item.emp_id,
                             { id: item.emp_id, name: item.emp_name, rows: [] });
            }
            byPerson.get(item.emp_id).rows.push(item);
        }
        return [...byPerson.values()];
    }

    get matchedByLine() { return identityLine(this.props.identity || ""); }

    startBind(index) {
        this.state.binding = this.state.binding === index ? -1 : index;
    }

    /** `undefined`, never `null` — a typed optional prop rejects null (W35). */
    get pickerCol() {
        return { ttype: "many2one", selection: [],
                 m2o: { comodel: "hr.employee", creates_missing: false,
                        key: "name" } };
    }

    onPicked(index, picked) {
        this.state.binding = -1;
        if (this.props.onBind && picked && picked.value
            && typeof picked.value === "object") {
            this.props.onBind(index, picked.value);
        }
    }

    cancelBind() { this.state.binding = -1; }

    rowTitle(row) {
        const bits = [row.code, row.name, row.email].filter(Boolean);
        return bits.length ? bits.join(" · ") : _t("(a row with nothing in it)");
    }

    valueCount(row) {
        const many = Object.keys(row.values || {}).length;
        return n(many, "1 value waiting", "%s values waiting");
    }

    get emptyChanges() {
        return _t("Nothing to change — every value in this file already "
                  + "matches what is on record.");
    }

    get emptyUnmatched() {
        return _t("Every row found its person.");
    }

    get emptyIgnored() {
        return _t("Every column in the file was understood.");
    }

    get blankLine() {
        const blank = (this.props.summary || {}).cells_blank || 0;
        if (!blank) { return ""; }
        return n(blank, "1 empty cell was left alone.",
                 "%s empty cells were left alone.");
    }
}
