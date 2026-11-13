/** @odoo-module **/
import { Component } from "@odoo/owl";

// Presentational autocomplete dropdown (T2.6). The trigger/parse/insert logic
// lives in GridStudio (it owns the editor input + caret); this just renders the
// candidate list and reports hover/pick. Positioned fixed so the grid's
// overflow-scroll container never clips it.
export class CellAutocomplete extends Component {
    static template = "pb_formula_studio.CellAutocomplete";
    static props = {
        items: Array,            // [{id, col, code, name, value}]
        active: Number,          // highlighted index
        style: { type: String, optional: true },   // fixed-position CSS
        onPick: Function,        // (item) => insert
        onHover: Function,       // (index) => set active
    };
}
