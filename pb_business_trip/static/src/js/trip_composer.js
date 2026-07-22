/** @odoo-module **/
/**
 * Trip composer field widgets (Phase C §4.2) — embedded in the native
 * pb.business.trip form, skinned by the VU Form Engine.
 *
 *  • biz_perdiem_panel  — a read-only "live per-diem" panel that recomputes as
 *    the dates / rate / policy change: "4 days × 200,000 ₫ = 800,000 ₫". Bound
 *    to per_diem_total; reads duration_days + per_diem_rate from the record so
 *    it tracks every onchange without a save.
 *  • biz_receipt_drop   — a drag-drop / tap-to-browse receipt zone per expense
 *    line with a thumbnail. Bound to receipt_attachment_id (m2o ir.attachment);
 *    it creates the attachment and sets the m2o. jpg/png/pdf, ≤ 10 MB.
 */
import { Component, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatCurrency } from "@web/core/currency";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const MAX_BYTES = 10 * 1024 * 1024;
const OK_MIME = /^(image\/(png|jpe?g)|application\/pdf)$/i;

// ------------------------------------------------------------- per-diem panel
export class PerDiemPanel extends Component {
    static template = "pb_business_trip.PerDiemPanel";
    static props = { ...standardFieldProps };

    get days() { return this.props.record.data.duration_days || 0; }
    get rate() { return this.props.record.data.per_diem_rate || 0; }
    get total() { return this.props.record.data.per_diem_total || 0; }
    get currencyId() {
        const c = this.props.record.data.currency_id;
        if (Array.isArray(c)) { return c[0]; }
        if (c && typeof c === "object") { return c.id ?? c.resId ?? false; }
        return c || false;
    }
    money(v) {
        try { return formatCurrency(v || 0, this.currencyId); }
        catch { return Math.round(v || 0).toLocaleString(); }
    }
}

registry.category("fields").add("biz_perdiem_panel", {
    component: PerDiemPanel,
    supportedTypes: ["monetary", "float"],
});

// ------------------------------------------------------------- receipt drop
export class ReceiptDrop extends Component {
    static template = "pb_business_trip.ReceiptDrop";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.fileRef = useRef("file");
        this.state = useState({ over: false, busy: false });
    }

    // current attachment value → [id, name] | false
    get att() {
        const v = this.props.record.data[this.props.name];
        if (Array.isArray(v)) { return { id: v[0], name: v[1] }; }
        if (v && typeof v === "object") { return { id: v.id ?? v.resId, name: v.display_name || v.name }; }
        return null;
    }
    get thumbUrl() {
        const a = this.att;
        return a ? `/web/image/ir.attachment/${a.id}/datas` : "";
    }
    get isPdf() {
        const a = this.att;
        return !!a && /\.pdf$/i.test(a.name || "");
    }
    get readonly() {
        // the view supplies readonly="parent.state == 'approved'" on the field
        return !!this.props.readonly;
    }

    onDragOver(ev) { if (this.readonly) { return; } ev.preventDefault(); this.state.over = true; }
    onDragLeave() { this.state.over = false; }
    onDrop(ev) {
        ev.preventDefault();
        this.state.over = false;
        if (this.readonly) { return; }
        const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (file) { this._ingest(file); }
    }
    browse() { if (!this.readonly && this.fileRef.el) { this.fileRef.el.click(); } }
    onPick(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (file) { this._ingest(file); }
        ev.target.value = "";  // allow re-picking the same file
    }

    async _ingest(file) {
        if (!OK_MIME.test(file.type)) {
            this.notif.add(_t("Only JPG, PNG or PDF receipts are accepted."), { type: "danger" });
            return;
        }
        if (file.size > MAX_BYTES) {
            this.notif.add(_t("Receipt is larger than 10 MB."), { type: "danger" });
            return;
        }
        this.state.busy = true;
        try {
            const dataUrl = await new Promise((resolve, reject) => {
                const r = new FileReader();
                r.onload = () => resolve(r.result);
                r.onerror = reject;
                r.readAsDataURL(file);
            });
            const b64 = String(dataUrl).split(",")[1] || "";
            // orphan attachment (no res_model) — creator-only readable; the
            // expense bridge sudo-copies it at authorization (C18.25).
            const id = await this.orm.call("ir.attachment", "create", [{
                name: file.name,
                datas: b64,
                mimetype: file.type,
            }]);
            await this.props.record.update({ [this.props.name]: [id, file.name] });
        } catch (e) {
            this.notif.add(e.message || _t("Upload failed."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async clear() {
        if (this.readonly) { return; }
        await this.props.record.update({ [this.props.name]: false });
    }
}

registry.category("fields").add("biz_receipt_drop", {
    component: ReceiptDrop,
    supportedTypes: ["many2one"],
});
