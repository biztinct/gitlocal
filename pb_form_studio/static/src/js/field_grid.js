/** @odoo-module **/
/**
 * PbFieldGrid — the published sections of a record, drawn as cards, in a
 * READ mode (detail pages) and an EDIT mode (drawers, the dev host).
 *
 * Generalised from `pb_contracts` `CdEditor` / `CdPicker`
 * (pb_contracts/static/src/js/contract_360.js:112-437) — CLONED here, not
 * imported, so the contract module does not have to depend on the engine yet.
 * Same contract per editor: commit, cancel, move on; every key handled stops
 * propagating (a drawer one level up listens for Escape too).
 *
 * Input = `pb.form.studio.render(host_key, record_id).sections`. The grid
 * never writes: in edit mode it stages values and hands each one to
 * `onChange(name, value, display)`; the host saves through
 * `pb.form.studio.write_values` and re-renders.
 *
 * Locked sections: the host draws them through a slot named after the
 * section id (`<t t-set-slot="pay">…</t>`); without a slot the grid draws the
 * section's note as a quiet placeholder.
 *
 * W96 (pb_contracts): every expression a template evaluates is a method here.
 */
import { Component, useState, useRef, onMounted, onWillUnmount, useExternalListener } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { fsIc, KIND_ICON } from "./fs_icons";
import { FACADE, toneClass, isEmptyDisplay, readFileAsDataUrl } from "./fs_words";

// ---------------------------------------------------------------------------
//  PbfsPicker — a filterable list floated beside its cell
// ---------------------------------------------------------------------------
export class PbfsPicker extends Component {
    static template = "pb_form_studio.Picker";
    static props = {
        rows: { type: Array, optional: true },
        lookup: { type: Function, optional: true },
        onPick: { type: Function },
        onCancel: { type: Function },
        allowClear: { type: Boolean, optional: true },
        anchorEl: { optional: true },
        current: { optional: true },
    };

    setup() {
        this.rootRef = useRef("root");
        this.inputRef = useRef("input");
        const first = this.staticRows("");
        const lit = first.findIndex((r) => String(r.id) === String(this.props.current));
        this.state = useState({ term: "", rows: first, active: lit > 0 ? lit : 0,
                                loading: false, top: 0, left: 0, width: 260 });
        this._timer = null;
        onMounted(() => {
            this.place();
            (this.inputRef.el || this.rootRef.el)?.focus();
            if (this.props.lookup) { this.search(""); }
        });
        onWillUnmount(() => this._timer && clearTimeout(this._timer));
        useExternalListener(window, "scroll", () => this.place(), { capture: true });
        useExternalListener(window, "resize", () => this.place());
        useExternalListener(window, "mousedown", (ev) => {
            if (!(ev.target.closest && ev.target.closest(".pbfb-pick"))) { this.props.onCancel(); }
        }, { capture: true });
    }

    ic(n, s = 14) { return fsIc(n, s); }

    /** Fixed position measured from the cell; corrected for a transformed
     *  ancestor exactly as CdPicker.place does. */
    place() {
        const el = this.props.anchorEl;
        const root = this.rootRef.el;
        if (!el || !el.getBoundingClientRect || !root) { return; }
        const r = el.getBoundingClientRect();
        const own = root.getBoundingClientRect();
        const offX = own.left - this.state.left;
        const offY = own.top - this.state.top;
        const width = Math.max(r.width, 240);
        const maxH = 292;
        const below = window.innerHeight - r.bottom;
        const up = below < maxH && r.top > below;
        const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8));
        const wanted = up ? r.top - maxH - 6 : r.bottom + 6;
        const top = Math.max(8, Math.min(wanted, window.innerHeight - maxH - 8));
        this.state.width = width;
        this.state.left = left - offX;
        this.state.top = top - offY;
    }
    get posStyle() {
        return `top:${Math.round(this.state.top)}px;left:${Math.round(this.state.left)}px;width:${Math.round(this.state.width)}px`;
    }
    staticRows(term) {
        const t = (term || "").toLowerCase();
        return (this.props.rows || []).filter((r) => !t || String(r.label || "").toLowerCase().includes(t));
    }
    get filterable() { return (this.props.rows || []).length > 8 || Boolean(this.props.lookup); }
    get placeholder() { return this.props.lookup ? _t("Type to search…") : _t("Type to filter…"); }
    get emptyLabel() { return _t("Nothing matches."); }
    get clearText() { return _t("Leave empty"); }
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
            this.state.rows = (await this.props.lookup(term)) || [];
            this.state.active = 0;
        } finally {
            this.state.loading = false;
        }
    }
    pick(row) { if (row) { this.props.onPick(row.id, row.label); } }
    clear() { this.props.onPick(false, ""); }
    onKey(ev) {
        const rows = this.state.rows;
        if (ev.key === "ArrowDown") {
            ev.preventDefault(); ev.stopPropagation();
            this.state.active = Math.min(this.state.active + 1, rows.length - 1);
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault(); ev.stopPropagation();
            this.state.active = Math.max(this.state.active - 1, 0);
        } else if (ev.key === "Enter") {
            ev.preventDefault(); ev.stopPropagation();
            this.pick(rows[this.state.active]);
        } else if (ev.key === "Escape") {
            ev.preventDefault(); ev.stopPropagation();
            this.props.onCancel();
        }
    }
    rowClass(i) { return { on: this.state.active === i }; }
    setActive(i) { this.state.active = i; }
}

// ---------------------------------------------------------------------------
//  PbfsEditor — one value being typed into (ten kinds, one switch)
// ---------------------------------------------------------------------------
export class PbfsEditor extends Component {
    static template = "pb_form_studio.Editor";
    static components = { PbfsPicker };
    static props = {
        entry: { type: Object },
        value: { optional: true },
        currency: { type: String, optional: true },
        onCommit: { type: Function },
        onCancel: { type: Function },
        lookup: { type: Function, optional: true },
        anchorEl: { optional: true },
    };

    setup() {
        this.inputRef = useRef("input");
        this.rootRef = useRef("root");
        const v = this.props.value;
        this.state = useState({ draft: v === null || v === undefined || v === false ? "" : String(v) });
        this._done = false;
        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
                if (this.inputRef.el.select && this.kind !== "file") { this.inputRef.el.select(); }
            } else if (this.kind === "bool" && this.rootRef.el) {
                (this.rootRef.el.querySelector("button") || this.rootRef.el).focus();
            }
        });
    }

    ic(n, s = 14) { return fsIc(n, s); }
    get entry() { return this.props.entry; }
    get kind() { return this.entry.kind || "text"; }
    get isNumeric() { return ["money", "number", "integer"].includes(this.kind); }
    get edClass() { return { num: this.isNumeric, pop: ["select", "m2o"].includes(this.kind) }; }
    get inputMode() { return this.kind === "integer" ? "numeric" : "decimal"; }
    get currencyPrefix() { return this.kind === "money" ? this.props.currency || "" : ""; }
    get pickerRows() { return (this.entry.options || []).map((o) => ({ id: o.value, label: o.label })); }
    get allowClear() { return !this.entry.required; }
    get yesLabel() { return _t("Yes"); }
    get noLabel() { return _t("No"); }
    get chooseFileLabel() { return _t("Choose a file"); }
    boolClass(on) { return { on: Boolean(this.props.value) === on }; }

    commit(value, display) { this._done = true; this.props.onCommit(value, display); }
    onInput(ev) { this.state.draft = ev.target.value; }
    onPick(id, label) { this.commit(id, label); }
    onBool(on) { this.commit(on, on ? this.yesLabel : this.noLabel); }
    async onFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        const data = await readFileAsDataUrl(file);
        this.commit(data, file.name);
    }
    onBlur() {
        if (this._done) { return; }
        if (["text", "longtext", "date", "money", "number", "integer"].includes(this.kind)) {
            this.commit(this.state.draft, this.state.draft);
        }
    }
    onKey(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault(); ev.stopPropagation();
            this._done = true;
            this.props.onCancel();
            return;
        }
        if (this.kind === "bool") { return; }
        if (ev.key === "Enter" && (this.kind !== "longtext" || ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault(); ev.stopPropagation();
            this.commit(this.state.draft, this.state.draft);
        }
    }
}

// ---------------------------------------------------------------------------
//  PbFieldGrid
// ---------------------------------------------------------------------------
export class PbFieldGrid extends Component {
    static template = "pb_form_studio.FieldGrid";
    static components = { PbfsEditor };
    static props = {
        sections: { type: Array },
        mode: { type: String, optional: true },          // "read" (default) | "edit"
        model: { type: String, optional: true },         // for link lookups
        currency: { type: String, optional: true },
        staged: { type: Object, optional: true },        // {name: {value, display}}
        errors: { type: Object, optional: true },        // {name: text}
        onChange: { type: Function, optional: true },    // (name, value, display)
        showEmpty: { type: Boolean, optional: true },    // draw open sections with no field
        slots: { type: Object, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ editing: null });
        this.anchorEl = null;
    }

    ic(n, s = 14) { return fsIc(n, s); }
    get isEdit() { return this.props.mode === "edit"; }
    get visibleSections() {
        return this.props.sections.filter((s) =>
            s.kind === "locked" ? this.hasSlot(s) || s.note
                : (s.fields || []).length || this.props.showEmpty);
    }
    hasSlot(sec) { return Boolean(this.props.slots && this.props.slots[sec.id]); }
    cardClass(sec) {
        return { "pbfb-card-locked": sec.kind === "locked", wide: sec.kind === "locked" && !this.hasSlot(sec) };
    }
    toneCls(sec) { return "pbfb-tone-" + toneClass(sec.tone); }
    secIcon(sec) { return fsIc(sec.icon || "layers", 15); }
    kindIcon(f) { return fsIc(KIND_ICON[f.kind] || "type", 13); }
    staged(f) { return (this.props.staged || {})[f.name]; }
    display(f) {
        const st = this.staged(f);
        return st ? st.display : f.display;
    }
    isEmpty(f) { return isEmptyDisplay(this.display(f)); }
    valueClass(f) { return { money: f.kind === "money", empty: this.isEmpty(f), dirty: Boolean(this.staged(f)) }; }
    emptyText() { return "—"; }
    errorFor(f) { return (this.props.errors || {})[f.name] || ""; }
    canEdit(f) { return this.isEdit && f.writable; }
    cellClass(f) {
        return { editable: this.canEdit(f), editing: this.state.editing === f.name,
                 bad: Boolean(this.errorFor(f)), custom: f.custom };
    }
    cellTab(f) { return this.canEdit(f) ? 0 : -1; }
    editValue(f) {
        const st = this.staged(f);
        return st ? st.value : f.value;
    }
    isEditing(f) { return this.state.editing === f.name; }
    start(f, ev) {
        if (!this.canEdit(f) || this.state.editing === f.name) { return; }
        this.anchorEl = ev && ev.currentTarget;
        this.state.editing = f.name;
    }
    onCellKey(f, ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            if (!this.isEditing(f)) { ev.preventDefault(); this.start(f, ev); }
        }
    }
    commit(f, value, display) {
        this.state.editing = null;
        if (this.props.onChange) {
            let shown = display;
            if (f.kind === "date" && value) {
                shown = value;
            }
            this.props.onChange(f.name, value, shown === undefined ? String(value || "") : shown);
        }
    }
    cancel() { this.state.editing = null; }
    lookupFor(f) {
        if (f.kind !== "m2o" || !this.props.model) { return undefined; }
        return (term) => this.orm.call(FACADE, "lookup", [this.props.model, f.name, term]);
    }
    hasHelp(f) { return Boolean(f.help); }
    fileUrl(f) { return !this.staged(f) && f.url ? f.url : ""; }
}
