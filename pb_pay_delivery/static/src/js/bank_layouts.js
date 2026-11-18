/** @odoo-module **/
/**
 * `pb_bank_layouts` — Settings › Payroll › Bank layouts (WDGAP S2-C).
 *
 * Every bank layout this company may use: the ones Payobook ships (read-only
 * here — "Make our own copy") and the company's own copies (editable: the
 * file's shape, its columns, the lines before and after the payments). A
 * payment-list layout previews with three made-up DEMO people, through the
 * same code that makes the real file.
 *
 * R1 — icons are cached markup (a NEW markup() per render re-inserts the SVG
 *      on every patch: OWL markup flicker).
 * R2 — every sentence a person reads is a `_t()` literal or comes from the
 *      server already translated. The server decides who may open it
 *      (payroll manager); the Settings card's groups are only a hint.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.bank.layout.studio";
const ICONS = {};
function icon(name, size = 16) {
    const key = name + ":" + size;
    if (!ICONS[key]) { ICONS[key] = ic(name, size); }
    return ICONS[key];
}

const SETTING_FIELDS = [
    "name", "file_type", "delimiter", "encoding", "with_header", "header_template",
    "trailer_template", "amount_format", "date_format", "line_ending", "ascii_only",
    "code_label", "code_pattern", "account_pattern", "note",
];

export class PbBankLayouts extends Component {
    static template = "pb_pay_delivery.PbBankLayouts";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.icon = icon;
        this.state = useState({
            loaded: false, denied: "", busy: false, board: null,
            search: "", selectedId: 0, layout: null, draft: null, dirty: false,
            preview: null, previewBusy: false,
        });
        onWillStart(async () => { await this.loadBoard(); });
    }

    // ------------------------------------------------------------ loading
    async loadBoard(selectId) {
        try {
            this.state.board = await this.orm.call(MODEL, "get_board", []);
            this.state.loaded = true;
            const first = selectId || this.state.selectedId
                || (this.state.board.layouts[0] && this.state.board.layouts[0].id);
            if (first) { await this.select(first); }
        } catch (e) {
            this.state.loaded = true;
            this.state.denied = this._err(e);
        }
    }
    async select(id) {
        if (this.state.dirty && id !== this.state.selectedId
                && !window.confirm(_t("Leave this layout without saving your changes?"))) {
            return;
        }
        this.state.selectedId = id;
        this.state.preview = null;
        try {
            const layout = await this.orm.call(MODEL, "get_layout", [id]);
            this._show(layout);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        }
    }
    _show(layout) {
        this.state.layout = layout;
        this.state.draft = {
            ...Object.fromEntries(SETTING_FIELDS.map((f) => [f, layout[f]])),
            column_rows: layout.column_rows.map((c) => ({ ...c })),
        };
        this.state.dirty = false;
    }

    // ------------------------------------------------------------ the list
    get groups() {
        const q = (this.state.search || "").trim().toLowerCase();
        const out = [];
        const seen = {};
        for (const l of (this.state.board && this.state.board.layouts) || []) {
            if (q && !(`${l.name} ${l.country}`).toLowerCase().includes(q)) { continue; }
            const key = l.country || _t("Other");
            if (!seen[key]) { seen[key] = { country: key, rows: [] }; out.push(seen[key]); }
            seen[key].rows.push(l);
        }
        return out;
    }
    get counts() {
        const rows = (this.state.board && this.state.board.layouts) || [];
        return {
            shipped: rows.filter((l) => l.shipped).length,
            own: rows.filter((l) => !l.shipped && l.active).length,
            unconfirmed: rows.filter((l) => l.inferred && l.active).length,
        };
    }
    onSearch(ev) { this.state.search = ev.target.value; }

    // ------------------------------------------------------------ editing
    get editable() { return !!(this.state.layout && this.state.layout.editable); }
    choices(key) { return (this.state.board && this.state.board[key]) || []; }
    setField(name, ev) {
        const el = ev.target;
        this.state.draft[name] = el.type === "checkbox" ? el.checked : el.value;
        this.state.dirty = true;
    }
    setCol(index, name, ev) {
        const el = ev.target;
        let value = el.type === "checkbox" ? el.checked : el.value;
        if (["width", "max_length"].includes(name)) { value = parseInt(value || "0", 10) || 0; }
        this.state.draft.column_rows[index][name] = value;
        this.state.dirty = true;
    }
    addColumn() {
        this.state.draft.column_rows.push({
            id: 0, header: "", source: "literal", literal_value: "", width: 0,
            pad: "right", number_format: "none", max_length: 0, required: false,
        });
        this.state.dirty = true;
    }
    moveColumn(index, step) {
        const rows = this.state.draft.column_rows;
        const to = index + step;
        if (to < 0 || to >= rows.length) { return; }
        const [row] = rows.splice(index, 1);
        rows.splice(to, 0, row);
        this.state.dirty = true;
    }
    removeColumn(index) {
        this.state.draft.column_rows.splice(index, 1);
        this.state.dirty = true;
    }
    sourceLabel(key) {
        const found = this.choices("sources").find((s) => s.key === key);
        return found ? found.label : key;
    }

    async makeCopy() {
        if (this.state.busy || !this.state.layout) { return; }
        this.state.busy = true;
        try {
            const copy = await this.orm.call(MODEL, "copy_layout", [this.state.layout.id]);
            this.state.dirty = false;
            await this.loadBoard(copy.id);
            this.notif.add(_t("Your own copy is ready. Change it to match your bank's template."), { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    async save() {
        if (this.state.busy || !this.editable) { return; }
        this.state.busy = true;
        try {
            const layout = await this.orm.call(MODEL, "save_layout",
                [this.state.layout.id, this.state.draft]);
            this._show(layout);
            this.state.preview = null;
            this.state.board = await this.orm.call(MODEL, "get_board", []);
            this.notif.add(_t("Saved."), { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    discard() { if (this.state.layout) { this._show(this.state.layout); } }
    async toggleConfirmed(ev) {
        if (this.state.busy || !this.state.layout || !this.state.layout.can_confirm) { return; }
        const on = !!ev.target.checked;
        if (this.state.dirty) {
            ev.target.checked = !on;
            this.notif.add(_t("Save your changes first."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const layout = await this.orm.call(MODEL, "confirm_layout", [this.state.layout.id, on]);
            this._show(layout);
            this.state.board = await this.orm.call(MODEL, "get_board", []);
        } catch (e) {
            ev.target.checked = !on;
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    get confirmedLine() {
        const l = this.state.layout || {};
        if (!l.bank_confirmed) { return ""; }
        return _t("Confirmed with our bank by %(who)s on %(when)s", {
            who: l.bank_confirmed_by || "", when: (l.bank_confirmed_on || "").slice(0, 10),
        });
    }
    async archive() {
        if (this.state.busy || !this.editable) { return; }
        if (!window.confirm(_t("Stop offering this copy on Pay & deliver? You can bring it back later."))) { return; }
        this.state.busy = true;
        try {
            this.state.board = await this.orm.call(MODEL, "archive_layout", [this.state.layout.id]);
            const layout = await this.orm.call(MODEL, "get_layout", [this.state.layout.id]);
            this._show(layout);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    async restore() {
        if (this.state.busy || !this.editable) { return; }
        this.state.busy = true;
        try {
            const layout = await this.orm.call(MODEL, "restore_layout", [this.state.layout.id]);
            this._show(layout);
            this.state.board = await this.orm.call(MODEL, "get_board", []);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    async loadPreview() {
        if (this.state.previewBusy || !this.state.layout) { return; }
        if (this.state.dirty) {
            this.notif.add(_t("Save your changes first; the preview shows the saved layout."), { type: "warning" });
            return;
        }
        this.state.previewBusy = true;
        try {
            this.state.preview = await this.orm.call(MODEL, "preview", [this.state.layout.id]);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.previewBusy = false;
        }
    }
    get previewLine() {
        const p = this.state.preview;
        if (!p) { return ""; }
        return _t("%(n)s sample people in the file • total %(total)s %(currency)s", {
            n: p.count, currency: p.currency || "",
            total: (p.total || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
        });
    }
    reasonList(reasons) { return (reasons || []).join(" · "); }
    _err(e) {
        return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed.");
    }
}

registry.category("actions").add("pb_bank_layouts", PbBankLayouts);
