/** @odoo-module **/
/**
 * DocDrop — a generic drag-drop / tap-to-browse document upload zone.
 *
 * Zero product dependency: styled through --bdo-* CSS custom properties. Emits
 * the picked file to the parent as { name, mime, data } (data = base64, no
 * data: prefix) via the onFile callback; jpg / png / pdf only, ≤ 10 MB.
 *
 * Props:
 *   onFile   Function  called with { name, mime, data }
 *   accept   String?   comma MIME list (default image/png,image/jpeg,application/pdf)
 *   maxMb    Number?   size cap in MB (default 10)
 *   label    String?   drop-zone call to action
 *   compact  Boolean?  smaller variant
 */
import { Component, useState, useRef } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class DocDrop extends Component {
    static template = "biz_doc_ocr.DocDrop";
    static props = {
        onFile: Function,
        accept: { type: String, optional: true },
        maxMb: { type: Number, optional: true },
        label: { type: String, optional: true },
        compact: { type: Boolean, optional: true },
    };

    setup() {
        this.fileRef = useRef("file");
        this.state = useState({ over: false, error: "" });
    }

    get accept() {
        return this.props.accept || "image/png,image/jpeg,application/pdf";
    }
    get maxBytes() {
        return (this.props.maxMb || 10) * 1024 * 1024;
    }
    get ctaLabel() {
        return this.props.label || _t("Drop a document here, or click to browse");
    }

    onDragOver(ev) { ev.preventDefault(); this.state.over = true; }
    onDragLeave() { this.state.over = false; }
    onDrop(ev) {
        ev.preventDefault();
        this.state.over = false;
        const file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (file) { this._read(file); }
    }
    browse() { if (this.fileRef.el) { this.fileRef.el.click(); } }
    onPick(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (file) { this._read(file); }
        ev.target.value = "";
    }

    async _read(file) {
        this.state.error = "";
        const ok = this.accept.split(",").map((s) => s.trim());
        if (ok.length && !ok.includes(file.type)) {
            this.state.error = _t("Unsupported file type — use JPG, PNG or PDF.");
            return;
        }
        if (file.size > this.maxBytes) {
            this.state.error = _t("File is larger than %s MB.", this.props.maxMb || 10);
            return;
        }
        try {
            const dataUrl = await new Promise((resolve, reject) => {
                const r = new FileReader();
                r.onload = () => resolve(r.result);
                r.onerror = reject;
                r.readAsDataURL(file);
            });
            const data = String(dataUrl).split(",")[1] || "";
            this.props.onFile({ name: file.name, mime: file.type, data });
        } catch (e) {
            this.state.error = e.message || _t("Could not read the file.");
        }
    }
}
