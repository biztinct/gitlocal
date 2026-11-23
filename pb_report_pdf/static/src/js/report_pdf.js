/** @odoo-module **/
/**
 * Design the PDF of a report (DOCSTUDIO phase B, study line 881).
 *
 *  - `PbReportPdfButton` — "PDF", offered to ANY report toolbar through the
 *    registry `pb_report_pdf`, key `button`, props
 *    { sourceModel, sourceId, disabledReason? } (the same shape as the Excel
 *    layout button, contract C2). A toolbar renders it when the registry has
 *    it and nothing when it does not.
 *  - `PbReportPdfDesigner` — the hero moment: options on the left, the REAL
 *    first page on the right, drawn by the server (`pb.report.pdf.preview`)
 *    in a sandboxed frame that runs no script, redrawn a moment after each
 *    change. Drag a column edge on the page to change its width. "Download
 *    PDF" gives the true file, built as the person pressing it.
 *
 * Every rule about who may see what lives on the server: the table always
 * comes from the report itself, read as the reader.
 */
import { Component, markup, onMounted, onWillStart, onWillUnmount, useExternalListener,
         useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";

const FACADE = "pb.report.pdf";
const MM = 3.7795;              // CSS px per millimetre

// Lucide icons (24x24, currentColor stroke). Made ONCE and reused: `t-out`
// of a NEW markup() re-inserts the node on every redraw (ledger "OWL markup
// flicker").
const P = {
    fileText: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8M16 13H8M16 17H8"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    save: '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    rotateCcw: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    building: '<rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01M16 6h.01M12 6h.01M12 10h.01M12 14h.01M16 10h.01M16 14h.01M8 10h.01M8 14h.01"/>',
    type: '<polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/><line x1="12" x2="12" y1="4" y2="20"/>',
    palette: '<circle cx="13.5" cy="6.5" r="1"/><circle cx="17.5" cy="10.5" r="1"/><circle cx="8.5" cy="7.5" r="1"/><circle cx="6.5" cy="12.5" r="1"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.65-.75 1.65-1.69 0-.44-.18-.84-.44-1.13-.29-.29-.44-.65-.44-1.13a1.64 1.64 0 0 1 1.67-1.67h2c3.05 0 5.55-2.5 5.55-5.55C21.97 6.01 17.46 2 12 2z"/>',
    columns: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18M15 3v18"/>',
    layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    sigma: '<path d="M18 7V4H6l6 8-6 8h12v-3"/>',
    panelBottom: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 15h18"/>',
    heading: '<path d="M6 12h12M6 20V4M18 20V4"/>',
    file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    moveH: '<path d="m18 8 4 4-4 4"/><path d="M2 12h20"/><path d="m6 8-4 4 4 4"/>',
    loader: '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    note: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    rows: '<path d="M3 5h18M3 12h18M3 19h18"/>',
    pageTurn: '<rect width="12" height="16" x="6" y="4" rx="1.5"/><path d="M3 9h3M18 15h3"/>',
};
const ICONS = {};
export function rpIcon(name, size = 16) {
    const key = `${name}|${size}`;
    if (!ICONS[key]) {
        ICONS[key] = markup(
            `<svg class="pbrp-ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
            `stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" ` +
            `aria-hidden="true">${P[name] || P.file}</svg>`);
    }
    return ICONS[key];
}

function saveFile(b64, name, mime) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) { bytes[i] = bin.charCodeAt(i); }
    const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function errText(e) {
    return e?.data?.message || e?.message || _t("Something went wrong. Try again.");
}

function clone(obj) { return JSON.parse(JSON.stringify(obj)); }

/** The frame's own styles: the fonts of the page (the frame loads nothing
 *  else) and the sheet with its footer. */
const FRAME_STYLE = `
@font-face{font-family:'Roboto';src:url('/web/static/fonts/google/Roboto/Roboto-Regular.ttf') format('truetype');font-weight:400}
@font-face{font-family:'Roboto';src:url('/web/static/fonts/google/Roboto/Roboto-Bold.ttf') format('truetype');font-weight:700}
@font-face{font-family:'Open_Sans';src:url('/web/static/fonts/google/Open_Sans/Open_Sans-Regular.ttf') format('truetype');font-weight:400}
@font-face{font-family:'Open_Sans';src:url('/web/static/fonts/google/Open_Sans/Open_Sans-Bold.ttf') format('truetype');font-weight:700}
@font-face{font-family:'Montserrat';src:url('/web/static/fonts/google/Montserrat/Montserrat-Regular.ttf') format('truetype');font-weight:400}
@font-face{font-family:'Montserrat';src:url('/web/static/fonts/google/Montserrat/Montserrat-Bold.ttf') format('truetype');font-weight:700}
html,body{margin:0;padding:0;background:#fff}
.pbrp-sheet{position:relative;overflow:hidden;background:#fff;box-sizing:border-box}
.pbrp-sheet-body{position:absolute;left:0;right:0;top:0;bottom:22mm;overflow:hidden}
.pbrp-sheet-body .pbds-page{box-sizing:border-box;height:100%}
.pbrp-sheet-foot{position:absolute;left:12mm;right:12mm;bottom:7mm;font-family:Roboto,'DejaVu Sans',Arial,sans-serif;font-size:8.5px;color:#64748b}
.pbrp-sheet-contact{text-align:center;padding-bottom:1.5mm}
.pbrp-sheet-line{display:flex;justify-content:space-between;gap:4mm;border-top:1px solid #e2e4ee;padding-top:1.5mm}
.pbrp-sheet-cap{display:block;color:#92400e}
.pbrp-sheet-page{white-space:nowrap}
.pbrp table.pbrp-t th{position:relative}
.pbrp table.pbrp-t th.pbrp-rs-hot{box-shadow:inset -3px 0 0 #f5b300}
body.pbrp-rs-on, body.pbrp-rs-on *{cursor:col-resize !important;user-select:none}
.pbrp-rs-guide{position:absolute;top:0;bottom:0;width:0;border-left:2px dashed #5A4BB0;pointer-events:none;z-index:5}
`;

// =====================================================================
//  The designer
// =====================================================================
export class PbReportPdfDesigner extends Component {
    static template = "pb_report_pdf.Designer";
    static components = { Dialog };
    static props = {
        sourceModel: String,
        sourceId: Number,
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.icon = rpIcon;
        this.stageRef = useRef("stage");
        this.frameA = useRef("frameA");
        this.frameB = useRef("frameB");
        this.titleRef = useRef("title");
        this.state = useState({
            loading: true, error: "", data: null, look: null, saved: "",
            pv: null, pvBusy: false, pvError: "",
            frames: { a: "", b: "" }, front: "a",
            scale: 0.5, downloading: false, saving: false, done: "",
            confirmReset: false, confirmClose: false, dragging: false,
            hint: true,
        });
        this._seq = 0;
        this._timer = null;
        this._ro = null;
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        onWillStart(() => this.load());
        onMounted(() => {
            if (window.ResizeObserver) {
                this._ro = new ResizeObserver(() => this.fit());
                if (this.stageRef.el) { this._ro.observe(this.stageRef.el); }
            }
            this.fit();
        });
        onWillUnmount(() => {
            clearTimeout(this._timer);
            if (this._ro) { this._ro.disconnect(); }
        });
    }

    // ------------------------------------------------------------ loading
    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const res = await this.orm.call(FACADE, "open", [this.props.sourceModel, this.props.sourceId]);
            if (!res.ok) {
                this.state.error = res.msg;
                return;
            }
            this.state.data = res;
            this.state.look = clone(res.look);
            this.state.saved = JSON.stringify(res.look);
            this.applyPreview(res.preview);
        } catch (e) {
            this.state.error = errText(e);
        } finally {
            this.state.loading = false;
            setTimeout(() => this.fit(), 0);
        }
    }

    // ------------------------------------------------------------ preview
    schedulePreview(delay = 220) {
        clearTimeout(this._timer);
        this.state.pvBusy = true;
        this._timer = setTimeout(() => this.refresh(), delay);
    }

    async refresh() {
        const seq = ++this._seq;
        this.state.pvBusy = true;
        try {
            const res = await this.orm.call(FACADE, "preview",
                [this.props.sourceModel, this.props.sourceId, this.state.look]);
            if (seq !== this._seq) { return; }
            if (!res.ok) {
                this.state.pvError = res.msg;
                return;
            }
            this.state.pvError = "";
            if (res.columns && this.state.data) { this.state.data.columns = res.columns; }
            this.applyPreview(res);
        } catch (e) {
            if (seq === this._seq) { this.state.pvError = errText(e); }
        } finally {
            if (seq === this._seq) { this.state.pvBusy = false; }
        }
    }

    applyPreview(pv) {
        this.state.pv = pv;
        // Double buffer: the new page loads in the hidden frame and takes
        // the front only once it has drawn (no blank flash).
        const back = this.state.front === "a" ? "b" : "a";
        this.state.frames[back] = this.frameDoc(pv.html || "");
        this._pendingBack = back;
        setTimeout(() => this.fit(), 0);
    }

    frameDoc(html) {
        return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src * data: blob:; font-src *"><style>${FRAME_STYLE}</style></head><body>${html}</body></html>`;
    }

    onFrameLoad(which, ev) {
        if (!this.state.frames[which]) { return; }
        if (this._pendingBack === which) {
            this.state.front = which;
            this._pendingBack = null;
        }
        this.wireResize(ev.target);
    }

    get paperPx() {
        const mm = (this.state.pv && this.state.pv.paper_mm) || [210, 297];
        return { w: Math.round(mm[0] * MM), h: Math.round(mm[1] * MM) };
    }

    fit() {
        const el = this.stageRef.el;
        if (!el) { return; }
        const { w, h } = this.paperPx;
        // the room left for the sheet: the stage's width, and the window
        // height below the chips bar (the stage itself may scroll)
        const bar = el.querySelector(".pbrp-stage-bar");
        const top = bar ? bar.getBoundingClientRect().bottom : el.getBoundingClientRect().top;
        const availW = Math.max(el.clientWidth - 48, 200);
        const availH = Math.max(window.innerHeight - top - 84, 200);
        this.state.scale = Math.max(0.2, Math.min(availW / w, availH / h, 1.4));
    }

    get sheetBoxStyle() {
        const { w, h } = this.paperPx;
        const s = this.state.scale;
        return `width: ${Math.round(w * s)}px; height: ${Math.round(h * s)}px;`;
    }

    get frameStyle() {
        const { w, h } = this.paperPx;
        return `width: ${w}px; height: ${h}px; transform: scale(${this.state.scale});`;
    }

    // ------------------------------------------------------------ widths
    /** Drag the edge between two columns on the page itself. The frame runs
     *  no script: the handles are wired from here (same origin). */
    wireResize(frame) {
        let doc = null;
        try { doc = frame.contentDocument; } catch { doc = null; }
        if (!doc || !doc.body) { return; }
        const table = doc.querySelector("table.pbrp-t");
        if (!table) { return; }
        const ths = Array.from(table.querySelectorAll("thead th"));
        const cols = Array.from(table.querySelectorAll("colgroup col"));
        if (ths.length < 2) { return; }
        const EDGE = 6;
        let hot = -1;
        let drag = null;
        const keys = ths.map((th) => th.dataset.key);
        const edgeAt = (x, y) => {
            const headRect = table.tHead.getBoundingClientRect();
            if (y < headRect.top - 2 || y > headRect.bottom + 2) { return -1; }
            for (let i = 0; i < ths.length - 1; i++) {
                const r = ths[i].getBoundingClientRect();
                if (Math.abs(x - r.right) <= EDGE) { return i; }
            }
            return -1;
        };
        const setHot = (i) => {
            if (hot === i) { return; }
            if (hot >= 0 && ths[hot]) { ths[hot].classList.remove("pbrp-rs-hot"); }
            hot = i;
            if (hot >= 0) { ths[hot].classList.add("pbrp-rs-hot"); }
            doc.body.classList.toggle("pbrp-rs-on", hot >= 0);
        };
        doc.addEventListener("mousemove", (ev) => {
            if (!drag) {
                setHot(edgeAt(ev.clientX, ev.clientY));
                return;
            }
            const delta = ((ev.clientX - drag.x) / drag.tableW) * 100;
            const pair = drag.start[drag.i] + drag.start[drag.i + 1];
            const left = Math.min(Math.max(drag.start[drag.i] + delta, 3), pair - 3);
            drag.now = drag.start.slice();
            drag.now[drag.i] = left;
            drag.now[drag.i + 1] = pair - left;
            cols[drag.i].style.width = `${left}%`;
            cols[drag.i + 1].style.width = `${pair - left}%`;
            const r = ths[drag.i].getBoundingClientRect();
            drag.guide.style.left = `${r.right + doc.defaultView.scrollX}px`;
        });
        doc.addEventListener("mousedown", (ev) => {
            const i = edgeAt(ev.clientX, ev.clientY);
            if (i < 0) { return; }
            ev.preventDefault();
            const tableRect = table.getBoundingClientRect();
            const start = ths.map((th) => (th.getBoundingClientRect().width / tableRect.width) * 100);
            const guide = doc.createElement("div");
            guide.className = "pbrp-rs-guide";
            guide.style.left = `${ths[i].getBoundingClientRect().right}px`;
            doc.body.appendChild(guide);
            drag = { i, x: ev.clientX, tableW: tableRect.width, start, now: start.slice(), guide };
            this.state.dragging = true;
        });
        const finish = () => {
            if (!drag) { return; }
            const done = drag;
            drag = null;
            done.guide.remove();
            this.state.dragging = false;
            const moved = done.now.some((w, i) => Math.abs(w - done.start[i]) > 0.3);
            if (!moved) { return; }
            // Every printed column keeps the width it has now, so the next
            // drawing is exactly what was dragged.
            const look = this.state.look;
            look.columns = { ...(look.columns || {}) };
            keys.forEach((key, i) => {
                look.columns[key] = { ...(look.columns[key] || {}), w: Math.round(done.now[i] * 100) / 100 };
            });
            this.state.hint = false;
            this.schedulePreview(0);
        };
        doc.addEventListener("mouseup", finish);
        doc.addEventListener("mouseleave", () => { if (!drag) { setHot(-1); } else { finish(); } });
    }

    // ------------------------------------------------------------ options
    set(key, value) {
        this.state.look[key] = value;
        this.state.done = "";
        this.schedulePreview();
    }
    toggle(key) { this.set(key, !this.state.look[key]); }
    onText(key, ev) {
        this.state.look[key] = ev.target.value;
        this.state.done = "";
        this.schedulePreview(450);
    }

    colHidden(col) { return col.hide; }
    toggleColumn(col) {
        const look = this.state.look;
        look.columns = { ...(look.columns || {}) };
        look.columns[col.key] = { ...(look.columns[col.key] || {}), hide: !col.hide };
        col.hide = !col.hide;
        this.state.done = "";
        this.schedulePreview(120);
    }
    widthWord(col) {
        if (col.hide) { return _t("Not printed"); }
        const w = this.state.pv && this.state.pv.widths ? this.state.pv.widths[col.key] : null;
        const own = this.state.look.columns && this.state.look.columns[col.key] && this.state.look.columns[col.key].w;
        if (!w) { return ""; }
        const pct = `${Math.round(w)}%`;
        return own ? _t("%s wide", pct) : _t("Auto · %s", pct);
    }
    get anyOwnWidth() {
        const c = this.state.look.columns || {};
        return Object.values(c).some((v) => v && v.w);
    }
    autoWidths() {
        const look = this.state.look;
        const out = {};
        for (const [k, v] of Object.entries(look.columns || {})) {
            if (v && "hide" in v) { out[k] = { hide: v.hide }; }
        }
        look.columns = out;
        this.schedulePreview(0);
    }
    get printedCount() {
        const cols = (this.state.data && this.state.data.columns) || [];
        return cols.filter((c) => !c.hide).length;
    }
    get columnCount() {
        return ((this.state.data && this.state.data.columns) || []).length;
    }
    get noColumns() { return this.state.data && this.printedCount === 0; }

    // ------------------------------------------------------------ words
    get dirty() {
        return !!this.state.look && JSON.stringify(this.state.look) !== this.state.saved;
    }
    get originWord() {
        const d = this.state.data;
        if (!d) { return ""; }
        if (this.dirty) { return _t("Unsaved changes"); }
        if (d.origin === "mine") { return d.my_shared ? _t("Your look · shared") : _t("Your look"); }
        if (d.origin === "shared") { return _t("Shared by %s", d.shared_by || _t("the report's owner")); }
        if (d.origin === "default") { return _t("Company look"); }
        return _t("Standard look");
    }
    get turnWord() {
        const pv = this.state.pv;
        if (!pv) { return ""; }
        const side = pv.sideways ? _t("Sideways") : _t("Upright");
        return this.state.look.turn === "fit" ? _t("%s (fit)", side) : side;
    }
    get fitHint() {
        const n = (this.state.data && this.state.data.options.fit[this.state.look.paper]) || 7;
        return _t("Fit turns the page sideways when more than %s columns print.", n);
    }
    get pageWord() {
        const pv = this.state.pv;
        if (!pv) { return ""; }
        return pv.pages === 1 ? _t("1 page") : _t("About %s pages", pv.pages.toLocaleString());
    }
    get rowWord() {
        const pv = this.state.pv;
        if (!pv) { return ""; }
        if (pv.capped) { return _t("%s of %s rows", pv.rows.toLocaleString(), pv.total_rows.toLocaleString()); }
        return pv.rows === 1 ? _t("1 row") : _t("%s rows", pv.rows.toLocaleString());
    }
    get titlePlaceholder() { return this.state.data ? this.state.data.title_default : ""; }
    get subPlaceholder() {
        return (this.state.data && this.state.data.sub_default) || _t("A line under the title");
    }
    fontStyle(font) { return `font-family: ${font.css};`; }
    swatchStyle(c) { return `background: ${c.bg}; color: ${c.fg};`; }

    // ------------------------------------------------------------ actions
    async download() {
        if (this.state.downloading || this.noColumns) { return; }
        this.state.downloading = true;
        this.state.done = "";
        try {
            const res = await this.orm.call(FACADE, "download",
                [this.props.sourceModel, this.props.sourceId, this.state.look]);
            if (!res.ok) {
                this.notif.add(res.msg, { type: "danger" });
                return;
            }
            saveFile(res.data, res.name, "application/pdf");
            const rows = res.rows === 1 ? _t("1 row") : _t("%s rows", res.rows.toLocaleString());
            this.state.done = _t("Your PDF is downloaded: %(rows)s, made in %(sec)s seconds.")
                .replace("%(rows)s", rows).replace("%(sec)s", res.seconds.toLocaleString());
        } catch (e) {
            this.notif.add(errText(e), { type: "danger" });
        } finally {
            this.state.downloading = false;
        }
    }

    async save(shared = null) {
        if (this.state.saving) { return; }
        this.state.saving = true;
        try {
            const res = await this.orm.call(FACADE, "save",
                [this.props.sourceModel, this.props.sourceId, this.state.look, shared]);
            this.state.look = clone(res.look);
            this.state.saved = JSON.stringify(res.look);
            this.state.data.origin = "mine";
            this.state.data.my_shared = res.my_shared;
            this.notif.add(shared === true ? _t("Look saved and shared with everyone who opens this report.")
                : shared === false ? _t("Look saved. Only you print with it now.")
                    : _t("Look saved. This report prints like this from now on."), { type: "success" });
            return true;
        } catch (e) {
            this.notif.add(errText(e), { type: "danger" });
            return false;
        } finally {
            this.state.saving = false;
        }
    }

    toggleShare() { this.save(!(this.state.data && this.state.data.my_shared)); }

    async reset() {
        this.state.confirmReset = false;
        try {
            const res = await this.orm.call(FACADE, "reset", [this.props.sourceModel, this.props.sourceId]);
            if (!res.ok) { this.state.error = res.msg; return; }
            this.state.data = res;
            this.state.look = clone(res.look);
            this.state.saved = JSON.stringify(res.look);
            this.applyPreview(res.preview);
            this.notif.add(_t("Back to the standard look."), { type: "info" });
        } catch (e) {
            this.notif.add(errText(e), { type: "danger" });
        }
    }

    async makeDefault() {
        try {
            await this.orm.call(FACADE, "set_default", [this.state.look]);
            this.state.data.has_default = true;
            this.notif.add(_t("New reports now start with this paper, page and table style."), { type: "success" });
        } catch (e) {
            this.notif.add(errText(e), { type: "danger" });
        }
    }

    async clearDefault() {
        try {
            await this.orm.call(FACADE, "clear_default", []);
            this.state.data.has_default = false;
            this.notif.add(_t("New reports start with the standard look again."), { type: "info" });
        } catch (e) {
            this.notif.add(errText(e), { type: "danger" });
        }
    }

    askClose() {
        if (this.dirty && !this.state.confirmClose) {
            this.state.confirmClose = true;
            return;
        }
        this.props.close();
    }

    async saveAndClose() {
        if (await this.save()) { this.props.close(); }
    }

    onKey(ev) {
        const mod = ev.metaKey || ev.ctrlKey;
        if (!mod || this.state.loading || this.state.error) { return; }
        const key = (ev.key || "").toLowerCase();
        if (key === "s") {
            ev.preventDefault();
            ev.stopPropagation();
            this.save();
        } else if (key === "enter" || key === "p") {
            ev.preventDefault();
            ev.stopPropagation();
            this.download();
        }
    }
}

// =====================================================================
//  The toolbar button (registry `pb_report_pdf`, key `button`)
// =====================================================================
export class PbReportPdfButton extends Component {
    static template = "pb_report_pdf.Button";
    static props = {
        sourceModel: String,
        sourceId: Number,
        disabledReason: { type: String, optional: true },
    };

    setup() {
        this.dialog = useService("dialog");
        this.icon = rpIcon;
    }

    get disabled() { return !this.props.sourceId || !!this.props.disabledReason; }
    get reason() {
        return this.props.disabledReason || (!this.props.sourceId ? _t("Save the report first.") : "");
    }
    get btnTitle() {
        return this.disabled ? this.reason : _t("Design the PDF of this report");
    }

    open() {
        if (this.disabled) { return; }
        this.dialog.add(PbReportPdfDesigner, {
            sourceModel: this.props.sourceModel,
            sourceId: this.props.sourceId,
        });
    }
}

registry.category("pb_report_pdf").add("button", PbReportPdfButton);
