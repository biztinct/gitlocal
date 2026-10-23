/** @odoo-module **/
import { Component, useState, useRef, onMounted, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Char-field widget for a mapping's source_field path. Free-text (any path is
// allowed) with a dropdown of discovered paths from get_available_source_fields
// (T4.3), substring-matched on path + sample. The input is uncontrolled so
// typing never fights the record value; external changes sync on patch.
export class SourceFieldAutocomplete extends Component {
    static template = "pb_hr_payroll_formula.SourceFieldAutocomplete";
    static props = { ...standardFieldProps, placeholder: { type: String, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ open: false, options: [], active: -1 });
        this.inputRef = useRef("input");
        this._all = [];
        this._loaded = false;
        onMounted(() => this._syncInput());
        onPatched(() => this._syncInput());
    }

    get value() { return this.props.record.data[this.props.name] || ""; }
    get connectorId() {
        const c = this.props.record.data.connector_id;
        if (!c) return null;
        if (Array.isArray(c)) return c[0];                 // [id, name]
        if (typeof c === "object") return c.id ?? c.resId ?? null;  // {id, display_name}
        return c;                                          // bare id
    }
    _syncInput() {
        const el = this.inputRef.el;
        if (el && document.activeElement !== el && el.value !== this.value) el.value = this.value;
    }

    async _load() {
        if (this._loaded) return;
        this._loaded = true;
        const cid = this.connectorId;
        if (!cid) return;
        try {
            this._all = await this.orm.call(
                "hr.integration.field.mapping", "get_available_source_fields", [cid]) || [];
        } catch (e) { this._all = []; }
    }
    _filter(q) {
        const query = (q || "").toLowerCase();
        const src = query
            ? this._all.filter(o => (o.path || "").toLowerCase().includes(query)
                || String(o.sample ?? "").toLowerCase().includes(query))
            : this._all;
        this.state.options = src.slice(0, 12);
        this.state.active = -1;
    }
    _commit(val) { this.props.record.update({ [this.props.name]: val }); }

    async onFocus() { await this._load(); this._filter(this.value); this.state.open = true; }
    onInput(ev) { this._commit(ev.target.value); this._filter(ev.target.value); this.state.open = true; }
    onKeydown(ev) {
        if (!this.state.open || !this.state.options.length) return;
        if (ev.key === "ArrowDown") { ev.preventDefault(); this.state.active = Math.min(this.state.options.length - 1, this.state.active + 1); }
        else if (ev.key === "ArrowUp") { ev.preventDefault(); this.state.active = Math.max(0, this.state.active - 1); }
        else if ((ev.key === "Enter" || ev.key === "Tab") && this.state.active >= 0) { ev.preventDefault(); this.pick(this.state.options[this.state.active]); }
        else if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); this.state.open = false; }
    }
    onBlur() { setTimeout(() => { this.state.open = false; }, 150); }  // allow mousedown pick first
    pick(opt) {
        this._commit(opt.path);
        if (this.inputRef.el) this.inputRef.el.value = opt.path;
        this.state.open = false;
    }
    sampleText(opt) {
        if (opt.sample === null || opt.sample === undefined) return "";
        return String(opt.sample).slice(0, 40);
    }
}

export const sourceFieldAutocomplete = {
    component: SourceFieldAutocomplete,
    displayName: "Source Field Autocomplete",
    supportedTypes: ["char"],
    extractProps: ({ attrs }) => ({ placeholder: attrs.placeholder }),
};

registry.category("fields").add("source_field_autocomplete", sourceFieldAutocomplete);
