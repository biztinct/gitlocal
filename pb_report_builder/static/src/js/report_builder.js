/** @odoo-module **/
/**
 * Insights › Build a report (DOCSTUDIO phase R, study line 900).
 *
 * Pick what each row is, click fields: the column slides into a live table
 * of real rows. Filter, sort, group by up to two fields with totals, save,
 * share, Excel. Every read happens on the server AS THE READER
 * (`pb.report.builder`): this file holds only the layout the person is
 * building, never a rule about who may see what.
 *
 * A TAB of the Insights hub, added through `pb_insights_hub_lens` (the hub is
 * Python-free with a fixed lens order — registry only). The hub's tab gate
 * is advisory; the facade refuses on its own (W12).
 *
 * Contract C2: when the Excel-layout module registered its button in
 * `registry.category("pb_excel_layout")` under "button", the toolbar shows
 * it; otherwise nothing.
 */
import { Component, onWillStart, onWillUnmount, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatInteger } from "@web/views/fields/formatters";
import { pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { saveFile } from "@pb_filter_kit/js/list_table";

/** Who sees the tab: the facade's own `_GATE_GROUPS`. */
export const REPORT_BUILDER_GATE = [
    "pb_hr_payroll_base.group_payroll_base_manager",
    "pb_hr_payroll_base.group_payroll_analytics_user",
    "pb_hr_payroll_base.group_payroll_super_admin",
    "hr.group_hr_user",
    "base.group_system",
];

const MODEL = "pb.report.builder";
const UNDO_MAX = 30;
const KIND_ICON = {
    text: "fileText", choice: "list", link: "link", number: "hash", money: "coins",
    date: "calendar", datetime: "clock", bool: "checkCircle", count: "sigma",
};

function clone(value) {
    return JSON.parse(JSON.stringify(value));
}

function fold(text) {
    return String(text || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export class PbReportBuilder extends Component {
    static template = "pb_report_builder.PbReportBuilder";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.searchRef = useRef("search");
        this.nameRef = useRef("name");
        this.state = useState({
            loaded: false, allowed: true, why: "", schema: null,
            view: "home", homeBusy: false, reports: [], examples: [],
            report: null, name: "", shared: false, spec: null, dirty: false,
            result: null, busy: false, error: "", loadingMore: false, newKey: "",
            groupsOpen: {}, groupRows: {},
            search: "", menu: "", editor: null, choices: [], choiceBusy: false,
            confirmDelete: false, saving: false, downloading: false,
            dragKey: "", dragOver: "", pickSubject: false,
        });
        this.undoStack = [];
        this.seq = 0;
        this.layoutButton = registry.category("pb_excel_layout").get("button", null);
        this._newTimer = null;
        this._choiceTimer = null;
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        useExternalListener(window, "click", (ev) => this.onWindowClick(ev));
        onWillStart(async () => { await this.init(); });
        onWillUnmount(() => {
            clearTimeout(this._newTimer);
            clearTimeout(this._choiceTimer);
        });
    }

    // ------------------------------------------------------------- helpers
    icon(name, size = 16) { return pbfIcon(name, size); }
    kindIcon(kind) { return this.icon(KIND_ICON[kind] || "fileText", 14); }
    int(n) { return formatInteger(n || 0); }
    errorText(e) {
        const data = e && e.data;
        return (data && data.message) || (e && e.message) || _t("Something went wrong just now.");
    }

    // ----------------------------------------------------------------- init
    async init() {
        try {
            const schema = await this.orm.call(MODEL, "schema", []);
            this.state.schema = schema;
            this.state.allowed = schema.allowed !== false;
            this.state.why = schema.why || "";
            if (this.state.allowed) { await this.loadHome(); }
        } catch (e) {
            console.warn("pb_report_builder: the field list could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The report builder could not be opened just now. Try again in a moment.");
        } finally {
            this.state.loaded = true;
        }
    }

    async loadHome() {
        this.state.homeBusy = true;
        try {
            const [reports, examples] = await Promise.all([
                this.orm.call(MODEL, "my_reports", []),
                this.orm.call(MODEL, "examples", []),
            ]);
            this.state.reports = reports;
            this.state.examples = examples;
        } catch (e) {
            this.notification.add(this.errorText(e), { type: "warning" });
        } finally {
            this.state.homeBusy = false;
        }
    }

    // ------------------------------------------------------------- subjects
    get subjects() { return (this.state.schema && this.state.schema.subjects) || []; }
    get subject() {
        const spec = this.state.spec;
        return spec ? this.subjects.find((s) => s.key === spec.subject) || null : null;
    }
    get myReports() { return this.state.reports.filter((r) => r.mine); }
    get sharedReports() { return this.state.reports.filter((r) => !r.mine); }

    get allFields() {
        const s = this.subject;
        const out = {};
        for (const sec of (s && s.sections) || []) {
            for (const f of sec.fields) { out[f.key] = f; }
        }
        return out;
    }
    field(key) { return this.allFields[key] || null; }

    get sections() {
        const s = this.subject;
        if (!s || !s.sections) { return []; }
        const q = fold(this.state.search.trim());
        return s.sections.map((sec) => ({
            ...sec,
            fields: q ? sec.fields.filter((f) => fold(f.label).includes(q)) : sec.fields,
        })).filter((sec) => sec.fields.length);
    }
    get searchEmpty() { return this.state.search.trim() && !this.sections.length; }
    isOn(key) { return !!this.state.spec && this.state.spec.columns.includes(key); }

    emptySpec(subjectKey) {
        const s = this.subjects.find((x) => x.key === subjectKey);
        const date = s && !s.date_optional && s.dates && s.dates.length ? s.dates[0].key : "";
        return {
            subject: subjectKey, columns: [], sort: null, filters: [],
            period: { preset: "any", from: null, to: null, date },
            group_by: [], totals: {}, summary: false,
        };
    }

    // ----------------------------------------------------------- navigation
    newReport() {
        this.undoStack = [];
        Object.assign(this.state, {
            view: "build", report: null, name: "", shared: false, spec: null, dirty: false,
            result: null, error: "", search: "", pickSubject: true, confirmDelete: false,
            groupsOpen: {}, groupRows: {}, editor: null, menu: "",
        });
    }

    async goHome() {
        this.state.view = "home";
        this.state.editor = null;
        this.state.menu = "";
        await this.loadHome();
    }

    startFromExample(ex) {
        this.undoStack = [];
        Object.assign(this.state, {
            view: "build", report: null, name: ex.name, shared: false, spec: clone(ex.spec),
            dirty: true, result: null, error: "", search: "", pickSubject: false,
            confirmDelete: false, groupsOpen: {}, groupRows: {}, editor: null, menu: "",
        });
        this.run();
    }

    async openReport(card) {
        if (card.locked) {
            this.notification.add(_t("This report is about something you cannot open. Ask your administrator for access."), { type: "warning" });
            return;
        }
        try {
            const res = await this.orm.call(MODEL, "open_report", [card.id]);
            if (!res.ok) {
                this.notification.add(res.msg, { type: "warning" });
                await this.loadHome();
                return;
            }
            this.undoStack = [];
            Object.assign(this.state, {
                view: "build", report: res.report, name: res.report.name,
                shared: res.report.shared, spec: res.spec, dirty: false, result: null,
                error: "", search: "", pickSubject: false, confirmDelete: false,
                groupsOpen: {}, groupRows: {}, editor: null, menu: "",
            });
            await this.run(res.notes);
        } catch (e) {
            this.notification.add(this.errorText(e), { type: "warning" });
        }
    }

    pickSubject(s) {
        if (s.locked) {
            this.notification.add(s.why || _t("You cannot open this kind of report."), { type: "warning" });
            return;
        }
        if (this.state.spec && this.state.spec.subject === s.key) {
            this.state.pickSubject = false;
            return;
        }
        this.pushUndo();
        this.state.spec = this.emptySpec(s.key);
        if (!this.state.report) { this.state.name = ""; }
        this.state.pickSubject = false;
        this.state.result = null;
        this.state.search = "";
        this.state.groupsOpen = {};
        this.state.groupRows = {};
        this.state.dirty = true;
        setTimeout(() => this.searchRef.el && this.searchRef.el.focus(), 60);
    }

    // ----------------------------------------------------------------- undo
    pushUndo() {
        if (!this.state.spec) { return; }
        this.undoStack.push({ spec: clone(this.state.spec) });
        if (this.undoStack.length > UNDO_MAX) { this.undoStack.shift(); }
    }
    get canUndo() { return this.undoStack.length > 0; }
    undo() {
        const last = this.undoStack.pop();
        if (!last) { return; }
        this.state.spec = last.spec;
        this.state.dirty = true;
        this.state.groupsOpen = {};
        this.state.groupRows = {};
        this.run();
    }

    /** Every layout change goes through here: snapshot, change, run. */
    change(fn, { rerun = true } = {}) {
        this.pushUndo();
        fn(this.state.spec);
        this.state.dirty = true;
        this.state.menu = "";
        if (rerun) {
            this.state.groupsOpen = {};
            this.state.groupRows = {};
            this.run();
        }
    }

    // ------------------------------------------------------------------ run
    async run(extraNotes) {
        const spec = this.state.spec;
        if (!spec || !spec.subject) { return; }
        const seq = ++this.seq;
        this.state.busy = true;
        this.state.error = "";
        try {
            const res = await this.orm.call(MODEL, "run", [spec, 0, (this.state.schema && this.state.schema.page) || 50]);
            if (seq !== this.seq) { return; }
            if (extraNotes && extraNotes.length) {
                res.notes = [...new Set([...(extraNotes || []), ...(res.notes || [])])];
            }
            this.state.result = res;
            this.state.spec = res.spec;
        } catch (e) {
            if (seq !== this.seq) { return; }
            this.state.error = this.errorText(e);
        } finally {
            if (seq === this.seq) { this.state.busy = false; }
        }
    }

    async loadMore() {
        const r = this.state.result;
        if (!r || !r.has_more || this.state.loadingMore) { return; }
        this.state.loadingMore = true;
        const seq = this.seq;
        try {
            const res = await this.orm.call(MODEL, "run", [this.state.spec, r.rows.length, 50]);
            if (seq !== this.seq) { return; }
            r.rows = [...r.rows, ...res.rows];
            r.ids = [...r.ids, ...res.ids];
            r.has_more = res.has_more;
        } catch (e) {
            this.notification.add(this.errorText(e), { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }

    // --------------------------------------------------------------- fields
    toggleField(f) {
        if (this.isOn(f.key)) {
            this.change((spec) => {
                spec.columns = spec.columns.filter((k) => k !== f.key);
                delete spec.totals[f.key];
                if (spec.sort && spec.sort.key === f.key) { spec.sort = null; }
            });
            return;
        }
        this.change((spec) => { spec.columns.push(f.key); });
        this.flashNew(f.key);
    }
    flashNew(key) {
        this.state.newKey = key;
        clearTimeout(this._newTimer);
        this._newTimer = setTimeout(() => { this.state.newKey = ""; }, 1100);
    }
    onSearchKey(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            for (const sec of this.sections) {
                const f = sec.fields.find((x) => !this.isOn(x.key));
                if (f) { this.toggleField(f); return; }
            }
        } else if (ev.key === "Escape") {
            this.state.search = "";
            ev.target.blur();
        }
    }
    /** The columns as the person laid them out — a column just clicked
     * shows at once (its cells shimmer until its values arrive). */
    get columns() {
        const spec = this.state.spec;
        if (!spec) { return []; }
        const known = {};
        for (const c of (this.state.result && this.state.result.columns) || []) { known[c.key] = c; }
        return spec.columns.map((k) => known[k] || this.field(k) || { key: k, label: "", kind: "text" });
    }
    /** For each column on screen, where its value sits in the answer's rows (-1 = coming). */
    get colIdx() {
        const keys = ((this.state.result && this.state.result.columns) || []).map((c) => c.key);
        return this.columns.map((c) => keys.indexOf(c.key));
    }
    cells(row) {
        const idx = this.colIdx;
        return this.columns.map((c, i) => ({
            key: c.key, kind: c.kind, wait: idx[i] < 0, text: idx[i] < 0 ? "" : row[idx[i]],
        }));
    }
    isNum(kind) { return kind === "number" || kind === "money" || kind === "count"; }
    get hiddenTitle() { return _t("You may not see this record."); }
    get quickFields() {
        const s = this.subject;
        if (!s || !s.sections || !s.sections.length) { return []; }
        return s.sections[0].fields.slice(0, 5);
    }

    // --------------------------------------------------------- column menu
    toggleMenu(key, ev) {
        ev.stopPropagation();
        this.state.menu = this.state.menu === key ? "" : key;
    }
    sortBy(key, dir) {
        this.change((spec) => { spec.sort = { key, dir }; });
    }
    clickSort(col) {
        if (!col.sortable) { return; }
        const sort = this.state.spec.sort;
        const dir = sort && sort.key === col.key && sort.dir === "asc" ? "desc" : "asc";
        this.sortBy(col.key, dir);
    }
    sortIcon(col) {
        const sort = this.state.spec && this.state.spec.sort;
        if (!sort || sort.key !== col.key) { return null; }
        return sort.dir === "asc" ? "arrowUp" : "arrowDown";
    }
    setTotal(key, how) {
        this.change((spec) => {
            if (how) { spec.totals[key] = how; } else { delete spec.totals[key]; }
        });
    }
    groupByThis(key) {
        const spec = this.state.spec;
        if (spec.group_by.includes(key)) { return; }
        if (spec.group_by.length >= 2) {
            this.notification.add(_t("A report can be grouped by two fields at most. Remove one first."), { type: "info" });
            return;
        }
        this.change((s) => { s.group_by.push(key); });
    }
    hideColumn(key) {
        this.change((spec) => {
            spec.columns = spec.columns.filter((k) => k !== key);
            delete spec.totals[key];
            if (spec.sort && spec.sort.key === key) { spec.sort = null; }
        });
    }
    sortWords(col) {
        if (col.kind === "date" || col.kind === "datetime") { return [_t("Oldest first"), _t("Newest first")]; }
        if (this.isNum(col.kind)) { return [_t("Smallest first"), _t("Largest first")]; }
        return [_t("A to Z"), _t("Z to A")];
    }
    totalWord(how) {
        return { sum: _t("Sum"), avg: _t("Average"), count: _t("Count") }[how] || how;
    }

    // ------------------------------------------------------- drag to order
    onDragStart(key, ev) {
        this.state.dragKey = key;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", key);
        }
    }
    onDragOver(key, ev) {
        if (!this.state.dragKey) { return; }
        ev.preventDefault();
        this.state.dragOver = key;
    }
    onDragEnd() { this.state.dragKey = ""; this.state.dragOver = ""; }
    onDrop(key, ev) {
        ev.preventDefault();
        const from = this.state.dragKey;
        this.onDragEnd();
        if (!from || from === key) { return; }
        // reorder in place: the rows already on screen move with their
        // column, no new read is needed
        const r = this.state.result;
        const cols = this.state.spec.columns.slice();
        const i = cols.indexOf(from);
        const j = cols.indexOf(key);
        if (i < 0 || j < 0) { return; }
        this.pushUndo();
        cols.splice(i, 1);
        cols.splice(j, 0, from);
        // the rows on screen follow through the cell map: no new read
        this.state.spec.columns = cols;
        this.state.dirty = true;
        if (r) { r.spec = clone(this.state.spec); }
    }

    // --------------------------------------------------------------- groups
    groupKey(node) { return JSON.stringify(node.key); }
    isOpen(node) { return !!this.state.groupsOpen[this.groupKey(node)]; }
    get grouped() { return !!(this.state.result && this.state.result.groups); }
    async toggleGroup(node) {
        if (this.state.spec.summary && !(node.children && node.children.length)) { return; }
        const k = this.groupKey(node);
        if (this.state.groupsOpen[k]) {
            delete this.state.groupsOpen[k];
            return;
        }
        this.state.groupsOpen[k] = true;
        if (!(node.children && node.children.length) && !this.state.groupRows[k]) {
            await this.loadGroupRows(node, 0);
        }
    }
    async loadGroupRows(node, offset) {
        const k = this.groupKey(node);
        const prev = this.state.groupRows[k];
        this.state.groupRows[k] = { rows: prev ? prev.rows : [], has_more: false, busy: true, total: node.count };
        const seq = this.seq;
        try {
            const res = await this.orm.call(MODEL, "run", [this.state.spec, offset, 50, node.key]);
            if (seq !== this.seq) { return; }
            this.state.groupRows[k] = {
                rows: [...(prev && offset ? prev.rows : []), ...res.rows],
                has_more: res.has_more, busy: false, total: res.total,
            };
        } catch (e) {
            this.state.groupRows[k] = { rows: [], has_more: false, busy: false, total: 0, error: this.errorText(e) };
        }
    }
    groupMore(node) {
        const g = this.state.groupRows[this.groupKey(node)];
        this.loadGroupRows(node, g ? g.rows.length : 0);
    }
    removeGroup(key) {
        this.change((spec) => {
            spec.group_by = spec.group_by.filter((k) => k !== key);
            if (!spec.group_by.length) { spec.summary = false; }
        });
    }
    addGroup(ev) {
        const key = ev.target.value;
        ev.target.value = "";
        if (key) { this.groupByThis(key); }
    }
    toggleSummary() {
        this.change((spec) => { spec.summary = !spec.summary; });
    }
    get groupable() {
        return Object.values(this.allFields).filter((f) => f.groupable && !this.state.spec.group_by.includes(f.key));
    }
    get leadSpan() {
        // the group's label spans the leading columns that carry no total
        const totals = (this.state.spec && this.state.spec.totals) || {};
        let n = 0;
        for (const c of this.columns) {
            if (totals[c.key]) { break; }
            n += 1;
        }
        return Math.max(1, n);
    }
    get tailColumns() { return this.columns.slice(this.leadSpan); }
    get hasTotals() {
        const t = this.state.result && this.state.result.totals;
        return !!(t && Object.keys(t).length);
    }
    leadTotal(node) {
        // a total on the very first column has no cell of its own on a group row
        const totals = (this.state.spec && this.state.spec.totals) || {};
        const first = this.columns[0];
        return first && totals[first.key] && this.leadSpan === 1 ? (node.totals || {})[first.key] || "" : "";
    }

    // -------------------------------------------------------------- period
    get presets() { return (this.state.schema && this.state.schema.presets) || []; }
    get dateChoices() { return (this.subject && this.subject.dates) || []; }
    onPreset(ev) {
        const preset = ev.target.value;
        this.change((spec) => {
            spec.period = { ...spec.period, preset };
            if (preset !== "custom") { spec.period.from = null; spec.period.to = null; }
            if (preset !== "any" && !spec.period.date && !this.subject.date_optional && this.dateChoices.length) {
                spec.period.date = this.dateChoices[0].key;
            }
        }, { rerun: preset !== "custom" });
    }
    onPeriodDate(which, ev) {
        const value = ev.target.value || null;
        this.change((spec) => { spec.period = { ...spec.period, [which]: value }; },
            { rerun: true });
    }
    onDateField(ev) {
        this.change((spec) => { spec.period = { ...spec.period, date: ev.target.value }; });
    }

    // ------------------------------------------------------------- filters
    get filterChips() {
        const words = (this.state.result && this.state.result.filter_words) || [];
        return this.state.spec.filters.map((f, i) => ({ i, text: words[i] || this.fallbackChip(f) }));
    }
    fallbackChip(f) {
        const field = this.field(f.key);
        return field ? field.label : f.key;
    }
    opsFor(kind) {
        const ops = (this.state.schema && this.state.schema.ops) || {};
        return ops[kind] || [];
    }
    get filterable() {
        return Object.values(this.allFields).filter((f) => f.filterable);
    }
    openEditor(key, index = null) {
        const f = this.field(key) || this.filterable[0];
        if (!f) { return; }
        const existing = index !== null ? this.state.spec.filters[index] : null;
        const op = existing ? existing.op : this.opsFor(f.kind)[0].key;
        this.state.editor = {
            index, key: f.key, op,
            value: existing ? clone(existing.value) : this.blankValue(f, op),
            search: "", names: {},
        };
        this.state.menu = "";
        this.state.choices = [];
        if (f.kind === "link") { this.searchChoices(""); }
    }
    blankValue(f, op) {
        if (op === "between") { return { from: null, to: null }; }
        if (op === "in") { return []; }
        if (f.kind === "bool") { return true; }
        if (op === "empty" || op === "not_empty") { return null; }
        return f.kind === "number" || f.kind === "money" ? null : "";
    }
    get editorField() { return this.state.editor ? this.field(this.state.editor.key) : null; }
    onEditorField(ev) {
        const f = this.field(ev.target.value);
        if (!f) { return; }
        const op = this.opsFor(f.kind)[0].key;
        Object.assign(this.state.editor, { key: f.key, op, value: this.blankValue(f, op), search: "", names: {} });
        this.state.choices = [];
        if (f.kind === "link") { this.searchChoices(""); }
    }
    onEditorOp(ev) {
        const op = ev.target.value;
        const f = this.editorField;
        const keep = (op === "in") === (this.state.editor.op === "in")
            && (op === "between") === (this.state.editor.op === "between");
        this.state.editor.op = op;
        if (!keep || op === "empty" || op === "not_empty") { this.state.editor.value = this.blankValue(f, op); }
    }
    onEditorValue(ev, part) {
        const f = this.editorField;
        let v = ev.target.value;
        if (f.kind === "number" || f.kind === "money") { v = v === "" ? null : Number(v); }
        if (part) { this.state.editor.value = { ...(this.state.editor.value || {}), [part]: v || (v === 0 ? 0 : null) }; } else { this.state.editor.value = v; }
    }
    setBool(v) { this.state.editor.value = v; }
    toggleChoice(val, label) {
        const e = this.state.editor;
        const list = Array.isArray(e.value) ? e.value.slice() : [];
        const i = list.indexOf(val);
        if (i >= 0) { list.splice(i, 1); } else { list.push(val); }
        e.value = list;
        if (label) { e.names[val] = label; }
    }
    choiceOn(val) {
        const e = this.state.editor;
        return Array.isArray(e.value) && e.value.includes(val);
    }
    onChoiceSearch(ev) {
        this.state.editor.search = ev.target.value;
        clearTimeout(this._choiceTimer);
        this._choiceTimer = setTimeout(() => this.searchChoices(this.state.editor.search), 220);
    }
    async searchChoices(text) {
        const e = this.state.editor;
        if (!e) { return; }
        this.state.choiceBusy = true;
        try {
            this.state.choices = await this.orm.call(MODEL, "values_for", [this.state.spec.subject, e.key, text || ""]);
        } catch {
            this.state.choices = [];
        } finally {
            this.state.choiceBusy = false;
        }
    }
    pickOne(c) {
        // "is" / "is not" on a linked field: one choice
        this.state.editor.value = c.id;
        this.state.editor.names[c.id] = c.label;
    }
    get editorReady() {
        const e = this.state.editor;
        const f = this.editorField;
        if (!e || !f) { return false; }
        if (e.op === "empty" || e.op === "not_empty") { return true; }
        if (f.kind === "bool") { return typeof e.value === "boolean"; }
        if (e.op === "in") { return Array.isArray(e.value) && e.value.length > 0; }
        if (e.op === "between") { return !!e.value && (e.value.from !== null && e.value.from !== "" || e.value.to !== null && e.value.to !== ""); }
        return e.value !== null && e.value !== "" && e.value !== undefined;
    }
    applyEditor() {
        if (!this.editorReady) { return; }
        const e = this.state.editor;
        const f = this.editorField;
        let value = e.value;
        if (f.kind === "link" && (e.op === "is" || e.op === "is_not")) { value = Number(value); }
        const flt = { key: e.key, op: e.op, value: (e.op === "empty" || e.op === "not_empty") ? null : value };
        this.state.editor = null;
        this.change((spec) => {
            if (e.index !== null && e.index !== undefined) { spec.filters[e.index] = flt; } else { spec.filters.push(flt); }
        });
    }
    removeFilter(i) {
        this.change((spec) => { spec.filters.splice(i, 1); });
    }
    closeEditor() { this.state.editor = null; }

    // --------------------------------------------------------- save, share
    async save() {
        if (!this.state.spec || !this.state.spec.subject) { return; }
        const name = (this.state.name || "").trim();
        if (!name) {
            this.notification.add(_t("Give the report a name first."), { type: "info" });
            if (this.nameRef.el) { this.nameRef.el.focus(); }
            return;
        }
        this.state.saving = true;
        try {
            if (this.state.report && this.state.report.mine) {
                this.state.report = await this.orm.call(MODEL, "update_report", [this.state.report.id,
                    { name, spec: this.state.spec, shared: this.state.shared }]);
            } else {
                this.state.report = await this.orm.call(MODEL, "save_report", [name, this.state.spec, this.state.shared]);
            }
            this.state.name = this.state.report.name;
            this.state.dirty = false;
            this.notification.add(_t("Report saved."), { type: "success" });
        } catch (e) {
            this.notification.add(this.errorText(e), { type: "warning" });
        } finally {
            this.state.saving = false;
        }
    }
    async toggleShare() {
        const next = !this.state.shared;
        this.state.shared = next;
        if (this.state.report && this.state.report.mine) {
            try {
                this.state.report = await this.orm.call(MODEL, "update_report", [this.state.report.id, { shared: next }]);
                this.notification.add(next ? _t("Shared with everyone who can open reports.") : _t("Only you can see this report now."), { type: "success" });
            } catch (e) {
                this.state.shared = !next;
                this.notification.add(this.errorText(e), { type: "warning" });
            }
        }
    }
    async duplicate() {
        if (!this.state.report) { return; }
        try {
            const copy = await this.orm.call(MODEL, "duplicate_report", [this.state.report.id]);
            this.notification.add(_t("A copy is ready. It is yours to change."), { type: "success" });
            await this.openReport(copy);
        } catch (e) {
            this.notification.add(this.errorText(e), { type: "warning" });
        }
    }
    async remove() {
        if (!this.state.report) { return; }
        try {
            await this.orm.call(MODEL, "remove_report", [this.state.report.id]);
            this.notification.add(_t("Report deleted."), { type: "success" });
            this.state.confirmDelete = false;
            await this.goHome();
        } catch (e) {
            this.notification.add(this.errorText(e), { type: "warning" });
        }
    }
    get readOnly() { return !!(this.state.report && !this.state.report.mine); }

    async download() {
        if (!this.state.spec || !this.state.spec.columns.length) { return; }
        this.state.downloading = true;
        try {
            const res = await this.orm.call(MODEL, "export_xlsx", [this.state.spec, this.state.name || ""]);
            if (!res.ok) {
                this.notification.add(res.msg, { type: "warning" });
                return;
            }
            saveFile(res);
            if (res.truncated) { this.notification.add(res.note, { type: "info", sticky: true }); }
        } catch (e) {
            this.notification.add(this.errorText(e), { type: "warning" });
        } finally {
            this.state.downloading = false;
        }
    }
    get layoutProps() {
        const id = (this.state.report && this.state.report.id) || 0;
        const props = { sourceModel: "pb.report.definition", sourceId: id };
        if (!id) { props.disabledReason = _t("Save the report first."); } else if (this.state.dirty) { props.disabledReason = _t("Save your changes first."); }
        return props;
    }

    // ------------------------------------------------------------ keyboard
    onKey(ev) {
        if (this.state.view !== "build" || !this.state.spec) { return; }
        const tag = (ev.target && ev.target.tagName) || "";
        const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(tag) || (ev.target && ev.target.isContentEditable);
        const mod = ev.metaKey || ev.ctrlKey;
        if (mod && (ev.key === "s" || ev.key === "S")) {
            ev.preventDefault();
            if (!this.readOnly) { this.save(); }
            return;
        }
        if (mod && !ev.shiftKey && (ev.key === "z" || ev.key === "Z") && !typing) {
            ev.preventDefault();
            this.undo();
            return;
        }
        if (ev.key === "/" && !typing && !mod) {
            ev.preventDefault();
            if (this.searchRef.el) { this.searchRef.el.focus(); }
            return;
        }
        if (ev.key === "Escape") {
            this.state.menu = "";
            this.state.editor = null;
        }
    }
    onWindowClick(ev) {
        if (this.state.menu && !(ev.target && ev.target.closest && ev.target.closest(".pbrb-colmenu"))) {
            this.state.menu = "";
        }
    }
    onName(ev) {
        this.state.name = ev.target.value;
        this.state.dirty = true;
    }
}

// A TAB of the Insights hub. Bolted-on lenses start at sequence 20.
registry.category("pb_insights_hub_lens").add("report_builder", {
    key: "report_builder",
    icon: "layoutGrid",
    label: _t("Build a report"),
    title: _t("Build a report"),
    Component: PbReportBuilder,
    groups: REPORT_BUILDER_GATE,
    probe: { model: MODEL, method: "can_open" },
}, { sequence: 30 });

registry.category("pb_hub_palette").add("report_builder", {
    id: "report_builder",
    label: _t("Build a report"),
    sublabel: _t("Insights"),
    icon: "layoutGrid",
    groups: REPORT_BUILDER_GATE,
    probe: { model: MODEL, method: "can_open" },
    action: { xmlid: "pb_insights_hub.action_pb_insights_hub", lens: "report_builder" },
    keywords: ["report", "custom report", "report builder", "excel", "báo cáo", "laporan"],
}, { sequence: 1150 });
