/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { ic } from "@pb_import_kit/js/import_icons";
import { _t } from "@web/core/l10n/translation";
import { toNumber } from "./blueprint_steps";

/**
 * "Adjust sample inputs" — change what the sample employee earns and watch the
 * take-home number move.
 *
 * The kit's `.pbim-modal` chrome, so this dialog and every other dialog in the
 * product are the same object. Escape closes it, the first field is focused on
 * open, and a value that is not a number is refused AT THE FIELD with a reason
 * rather than swallowed and stored as zero.
 */
export class SampleInputsDialog extends Component {
    static template = "pb_blueprint.SampleInputsDialog";
    static props = {
        title: { type: String },
        rows: { type: Array },        // [{code, name, value}]
        busy: { type: Boolean, optional: true },
        onSave: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.state = useState({
            values: Object.fromEntries(
                this.props.rows.map((r) => [r.code, String(r.value ?? 0)])),
            bad: {},
        });
        // Focus the first field on open. Found by walking the body rather than
        // by a per-row ref: a dynamic `t-ref` on one row of a `t-foreach` is a
        // name that only sometimes exists, which is a bug waiting for the day
        // the rows are reordered.
        this.bodyRef = useRef("body");
        onMounted(() => {
            const first = this.bodyRef.el && this.bodyRef.el.querySelector("input");
            if (first) first.focus();
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    onInput(code, ev) {
        this.state.values[code] = ev.target.value;
        if (toNumber(ev.target.value) === null && ev.target.value !== "") {
            this.state.bad[code] = _t("That is not a number.");
        } else {
            delete this.state.bad[code];
        }
    }

    onKey(ev) {
        if (ev.key === "Escape") {
            ev.stopPropagation();
            this.props.onClose();
        }
        if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) this.save();
    }

    get hasBad() { return Object.keys(this.state.bad).length > 0; }

    save() {
        if (this.hasBad || this.props.busy) return;
        const out = {};
        for (const row of this.props.rows) {
            const n = toNumber(this.state.values[row.code]);
            out[row.code] = n === null ? 0 : n;
        }
        this.props.onSave(out);
    }
}
