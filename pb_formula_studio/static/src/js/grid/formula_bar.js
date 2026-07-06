/** @odoo-module **/
import { Component, useState, useRef, onMounted, onPatched } from "@odoo/owl";

// Always-visible formula bar (T2.3). Shows the focused component's =formula,
// editable with the SAME validate/save round-trip as the in-cell overlay (both
// call onValidateLive → onSaveFormula). Its edit state is independent, and a
// superseded validation never overwrites newer input (sequence-guarded, so an
// old in-flight validate that resolves late is discarded).
export class FormulaBar extends Component {
    static template = "pb_formula_studio.FormulaBar";
    static props = {
        focused: { optional: true },          // focused component object | null
        canEdit: { type: Boolean, optional: true },
        onSaveFormula: Function,              // (ruleId, formula) => parent save + refresh
        onValidateLive: Function,             // (formula, excludeRuleId) => {valid, message}
    };

    setup() {
        this.state = useState({ editing: false, buffer: "", valid: null, message: "" });
        this.inputRef = useRef("input");
        this._liveTimer = null;
        this._vseq = 0;                       // monotonic validation token (supersede guard)
        onMounted(() => this._syncInput());
        onPatched(() => this._syncInput());
    }

    get editable() {
        const f = this.props.focused;
        return !!(this.props.canEdit && f && f.type === "formula");
    }
    get placeholder() {
        const f = this.props.focused;
        if (!f) return "Select a component";
        if (f.type === "input") return "Input — value comes from the data source";
        if (f.type === "constant") return "Constant value";
        return "= formula";
    }
    _formulaOf(f) { return (f && f.type === "formula") ? (f.excel_formula || "") : ""; }

    // Keep the (uncontrolled) input in sync with the focused component when NOT
    // actively editing — reflects saves + focus changes without caret jumps.
    _syncInput() {
        const el = this.inputRef.el;
        if (!el || this.state.editing) return;
        const v = this._formulaOf(this.props.focused);
        if (el.value !== v) el.value = v;
    }

    onFocus(ev) {
        if (!this.editable) return;
        this.state.editing = true;
        this.state.buffer = ev.target.value;
        this.state.valid = null; this.state.message = "";
    }
    onInput(ev) {
        this.state.buffer = ev.target.value;
        clearTimeout(this._liveTimer);
        const seq = ++this._vseq;
        const val = this.state.buffer;
        this._liveTimer = setTimeout(async () => {
            const res = await this.props.onValidateLive(val, this.props.focused ? this.props.focused.id : null);
            if (seq === this._vseq && res) { this.state.valid = res.valid; this.state.message = res.message || ""; }
        }, 260);
    }
    onKeydown(ev) {
        if (ev.key === "Enter") { ev.preventDefault(); this._commit(); }
        else if (ev.key === "Escape") { ev.preventDefault(); this._cancel(); }
        ev.stopPropagation();                 // never leak to the grid navigator
    }
    async _commit() {
        const f = this.props.focused;
        if (!f || !this.editable) return;
        // final synchronous guard — invalid syntax must never call save_formula
        const res = await this.props.onValidateLive(this.state.buffer, f.id);
        if (res && res.valid === false) { this.state.valid = false; this.state.message = res.message || "Invalid formula"; return; }
        const buf = this.state.buffer;
        this.state.editing = false; this.state.valid = null; this.state.message = "";
        await this.props.onSaveFormula(f.id, buf);
        if (this.inputRef.el) this.inputRef.el.blur();
    }
    _cancel() {
        this.state.editing = false; this.state.valid = null; this.state.message = "";
        clearTimeout(this._liveTimer); this._vseq++;   // invalidate any in-flight validate
        this._syncInput();
        if (this.inputRef.el) this.inputRef.el.blur();
    }
    onBlur() {
        // leaving the bar without Enter reverts (like Escape) — no silent save
        if (this.state.editing) this._cancel();
    }
}
