/** @odoo-module **/
/**
 * Fill my own Excel layout (DOCSTUDIO X, study line 920).
 *
 *  - `PbExcelLayoutButton` — "My Excel layout", offered to ANY screen through
 *    contract C2: registry `pb_excel_layout`, key `button`, props
 *    { sourceModel, sourceId, disabledReason? }. The host renders it when the
 *    registry has it and nothing when it does not.
 *  - `PbExcelLayoutDialog` — the set-up (the hero moment): drop the file, see
 *    THEIR sheet, click the cell where the figures start, watch the table
 *    area light up at the size of the current result, Try it, Save.
 *
 * Every call goes through the facade `pb.excel.layout.board`, which checks on
 * the server that the reader may open the report (the hub gate is advisory).
 */
import { Component, markup, onWillStart, onWillUpdateProps, useExternalListener,
         useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { IC } from "@pb_import_kit/js/import_icons";

const BOARD = "pb.excel.layout.board";
const MAX_BYTES = 10 * 1024 * 1024;
const GRID_ROWS = 20;
const GRID_COLS = 12;

// Icons are made ONCE and reused: `t-out` of a NEW markup() re-inserts the
// node on every redraw (ledger gotcha "OWL markup flicker").
const ICONS = {};
export function xic(name, size = 16) {
    const key = `${name}|${size}`;
    if (!ICONS[key]) {
        const path = IC[name] || IC.file;
        ICONS[key] = markup(
            `<svg class="pbxl-ic" width="${size}" height="${size}" viewBox="0 0 24 24" ` +
            `fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" ` +
            `stroke-linejoin="round" aria-hidden="true">${path}</svg>`);
    }
    return ICONS[key];
}

export function colLetter(n) {
    let out = "";
    while (n > 0) {
        const rem = (n - 1) % 26;
        out = String.fromCharCode(65 + rem) + out;
        n = Math.floor((n - 1) / 26);
    }
    return out;
}

/** "B6" → { c: 2, r: 6 }; anything else → null. */
export function splitCell(ref) {
    const m = /^\$?([A-Za-z]{1,3})\$?([0-9]{1,7})$/.exec((ref || "").trim());
    if (!m) { return null; }
    let c = 0;
    for (const ch of m[1].toUpperCase()) { c = c * 26 + (ch.charCodeAt(0) - 64); }
    const r = Number(m[2]);
    if (c < 1 || c > 16384 || r < 1 || r > 1048576) { return null; }
    return { c, r };
}

function splitRange(ref) {
    const [a, b] = (ref || "").split(":");
    const p = splitCell(a);
    const q = splitCell(b || a);
    if (!p || !q) { return null; }
    return { c0: Math.min(p.c, q.c), r0: Math.min(p.r, q.r),
             c1: Math.max(p.c, q.c), r1: Math.max(p.r, q.r) };
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
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function readB64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || "").split(",").pop());
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
    });
}

function sizeWord(bytes) {
    if (bytes >= 1024 * 1024) { return `${(bytes / 1024 / 1024).toFixed(1)} MB`; }
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function errText(e) {
    return e?.data?.message || e?.message || _t("Something went wrong. Try again.");
}

// =====================================================================
//  The set-up dialog
// =====================================================================
export class PbExcelLayoutDialog extends Component {
    static template = "pb_excel_layout.Dialog";
    static components = { Dialog };
    static props = {
        sourceModel: String,
        sourceId: Number,
        sourceName: { type: String, optional: true },
        mode: { type: String, optional: true },        // new | edit | replace
        layoutId: { type: Number, optional: true },
        onSaved: { type: Function, optional: true },
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.xic = xic;
        this.colLetter = colLetter;
        this.fileRef = useRef("file");
        this.gridRef = useRef("grid");
        this.rows = Array.from({ length: GRID_ROWS }, (_v, i) => i + 1);
        this.cols = Array.from({ length: GRID_COLS }, (_v, i) => i + 1);
        this.state = useState({
            phase: this.props.mode === "edit" ? "reading" : "drop",
            dragging: false,
            error: "",
            fileName: "",
            fileSize: 0,
            fileB64: "",
            file: null,
            table: null,
            sheet: "",
            start: "A1",
            startText: "A1",
            headers: true,
            name: "",
            shared: false,
            busy: "",
            tried: null,
            hover: null,
            layout: null,
            saveError: "",
        });
        onWillStart(async () => {
            if (this.props.layoutId && this.props.mode !== "new") {
                await this.loadLayout();
            }
        });
    }

    get mode() { return this.props.mode || "new"; }

    get title() {
        if (this.mode === "edit") { return _t("Change where the figures go"); }
        if (this.mode === "replace") { return _t("Replace the Excel file"); }
        return _t("Use my Excel layout");
    }

    // ------------------------------------------------------------ loading
    async loadLayout() {
        try {
            const res = await this.orm.call(BOARD, "detail", [this.props.layoutId]);
            const lay = res.layout;
            this.state.layout = lay;
            this.state.table = res.table;
            this.state.name = lay.name;
            this.state.shared = lay.shared;
            this.state.headers = lay.headers;
            this.setStart(lay.start);
            if (this.mode === "replace") {
                this.state.phase = "drop";
                return;
            }
            if (!res.file.ok) {
                this.state.phase = "error";
                this.state.error = res.file.msg;
                return;
            }
            this.state.file = res.file;
            this.state.fileName = lay.file_name;
            this.state.fileSize = res.file.size;
            this.state.sheet = lay.sheet_ok ? lay.sheet : (this.firstUsable()?.name || "");
            this.state.phase = "ready";
        } catch (e) {
            this.state.phase = "error";
            this.state.error = errText(e);
        }
    }

    firstUsable() {
        return (this.state.file?.sheets || []).find((s) => s.usable && !s.hidden)
            || (this.state.file?.sheets || []).find((s) => s.usable);
    }

    pickFile() { this.fileRef.el?.click(); }

    onDropKey(ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.pickFile();
        }
    }

    onFileInput(ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (file) { this.takeFile(file); }
    }

    onDragOver(ev) { ev.preventDefault(); this.state.dragging = true; }
    onDragLeave() { this.state.dragging = false; }
    onDrop(ev) {
        ev.preventDefault();
        this.state.dragging = false;
        const file = ev.dataTransfer?.files && ev.dataTransfer.files[0];
        if (file) { this.takeFile(file); }
    }

    async takeFile(file) {
        const lower = (file.name || "").toLowerCase();
        this.state.error = "";
        this.state.tried = null;
        this.state.saveError = "";
        if (lower.endsWith(".xls")) {
            return this.fail(_t("This is an old-style Excel file (.xls). Open it in Excel, save it as .xlsx and upload it again."));
        }
        if (!lower.endsWith(".xlsx") && !lower.endsWith(".xlsm")) {
            return this.fail(_t("Only Excel files ending in .xlsx or .xlsm can be used."));
        }
        if (file.size > MAX_BYTES) {
            return this.fail(_t("This file is larger than 10 MB. Remove what is not needed (old sheets, large pictures) and upload it again."));
        }
        this.state.phase = "reading";
        this.state.fileName = file.name;
        this.state.fileSize = file.size;
        try {
            const b64 = await readB64(file);
            const res = await this.orm.call(BOARD, "inspect",
                [b64, file.name, this.props.sourceModel, this.props.sourceId]);
            if (!res.ok) { return this.fail(res.msg); }
            this.state.fileB64 = b64;
            this.state.file = res;
            this.state.table = res.table || this.state.table;
            const keep = this.state.layout
                && res.sheets.find((s) => s.name === this.state.layout.sheet && s.usable);
            if (keep) {
                this.state.sheet = keep.name;
            } else {
                const first = this.firstUsable();
                this.state.sheet = first ? first.name : "";
                if (this.mode === "new" && first?.suggested) {
                    this.setStart(first.suggested.cell);
                    this.state.headers = first.suggested.headers;
                }
            }
            if (this.mode === "new" && !this.state.name) {
                this.state.name = (file.name || "").replace(/\.(xlsx|xlsm)$/i, "").slice(0, 80);
            }
            this.state.phase = "ready";
        } catch (e) {
            this.fail(errText(e));
        }
    }

    fail(msg) {
        this.state.phase = "error";
        this.state.error = msg;
        this.state.fileB64 = "";
    }

    // ------------------------------------------------------------- sheets
    get sheets() { return this.state.file?.sheets || []; }

    get sheet() { return this.sheets.find((sh) => sh.name === this.state.sheet) || null; }

    get fileMeta() {
        const n = this.sheets.length;
        const count = n === 1 ? _t("1 sheet") : _t("%s sheets", n);
        return this.state.fileSize ? `${count} · ${sizeWord(this.state.fileSize)}` : count;
    }

    /** After a file replace the layout's sheet may be gone (X5). */
    get sheetGone() {
        const lay = this.state.layout;
        if (!lay || !this.state.file) { return ""; }
        if (this.sheets.some((s) => s.name === lay.sheet && s.usable)) { return ""; }
        return lay.sheet;
    }

    pickSheet(sheet) {
        if (!sheet.usable) { return; }
        this.state.sheet = sheet.name;
        this.state.tried = null;
        const full = this.sheet;
        if (full && !full.grid) { this.peekSheet(full.name); }
        if (this.mode === "new" && full?.suggested) {
            this.setStart(full.suggested.cell);
            this.state.headers = full.suggested.headers;
        }
    }

    async peekSheet(name) {
        // `inspect` describes the first 30 sheets in full; a sheet past them
        // (or a layout opened from the server) is read on demand.
        if (!this.state.fileB64) { return; }
        try {
            const res = await this.orm.call(BOARD, "peek", [this.state.fileB64, name, this.state.fileName]);
            if (res.ok && res.sheet) {
                const at = this.sheets.findIndex((s) => s.name === name);
                if (at >= 0) { this.state.file.sheets[at] = res.sheet; }
            }
        } catch {
            // the tab stays without a preview; Try it still checks the sheet
        }
    }

    sheetTitle(sheet) {
        if (sheet.kind !== "worksheet") { return _t("A chart sheet has no cells to fill."); }
        if (sheet.hidden) { return _t("Hidden in Excel"); }
        return sheet.name;
    }

    // ------------------------------------------------------------ the cell
    setStart(ref) {
        const p = splitCell(ref);
        if (!p) { return; }
        this.state.start = `${colLetter(p.c)}${p.r}`;
        this.state.startText = this.state.start;
        this.state.tried = null;
    }

    clickCell(r, c) {
        this.setStart(`${colLetter(c)}${r}`);
        this.gridRef.el?.focus();
    }

    onStartInput(ev) {
        this.state.startText = ev.target.value.toUpperCase();
        const p = splitCell(this.state.startText);
        if (p) { this.setStart(this.state.startText); }
    }

    onGridKey(ev) {
        const p = splitCell(this.state.start) || { c: 1, r: 1 };
        const moves = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
        const step = moves[ev.key];
        if (!step) { return; }
        ev.preventDefault();
        const c = Math.max(1, p.c + step[0]);
        const r = Math.max(1, p.r + step[1]);
        this.setStart(`${colLetter(c)}${r}`);
    }

    hoverCell(r, c) { this.state.hover = { r, c }; }
    leaveGrid() { this.state.hover = null; }

    get startValid() { return !!splitCell(this.state.startText); }

    /** The table area on the sheet: where headings and figures will land. */
    get area() {
        const p = splitCell(this.state.start);
        const t = this.state.table;
        if (!p || !t) { return null; }
        const cols = Math.max(1, t.cols);
        const rows = t.rows + (this.state.headers ? 1 : 0);
        return { c0: p.c, r0: p.r, c1: p.c + cols - 1, r1: p.r + Math.max(rows, 1) - 1,
                 head: this.state.headers ? p.r : 0 };
    }

    cellClass(r, c) {
        const a = this.area;
        const out = [];
        if (a && c >= a.c0 && c <= a.c1 && r >= a.r0 && r <= a.r1) {
            out.push(r === a.head ? "is-head" : "is-area");
            // What the sheet holds there today is about to be replaced.
            if (r !== a.head && this.sheet?.grid?.[r - 1]?.[c - 1]) { out.push("will-go"); }
            if (r === a.r0) { out.push("e-t"); }
            if (r === a.r1) { out.push("e-b"); }
            if (c === a.c0) { out.push("e-l"); }
            if (c === a.c1) { out.push("e-r"); }
            if (r === a.r0 && c === a.c0) { out.push("is-start"); }
        }
        const h = this.state.hover;
        if (h && h.r === r && h.c === c) { out.push("is-hover"); }
        if (this.inMerged(r, c)) { out.push("is-merged"); }
        return out.join(" ");
    }

    cellText(r, c) {
        const a = this.area;
        const grid = this.sheet?.grid;
        // In the heading row the preview shows the headings that will be
        // written; elsewhere what the sheet holds today.
        if (a && a.head === r && c >= a.c0 && c <= a.c1) {
            return this.state.table.labels[c - a.c0] || "";
        }
        return (grid && grid[r - 1] && grid[r - 1][c - 1]) || "";
    }

    cellStyle(r, c) {
        const look = this.sheet?.looks?.[r - 1]?.[c - 1];
        if (!look) { return ""; }
        let css = "";
        if (look.b) { css += "font-weight:700;"; }
        const a = this.area;
        const inside = a && c >= a.c0 && c <= a.c1 && r >= a.r0 && r <= a.r1;
        if (look.bg && !inside) {
            css += `background:${look.bg};`;
            // Their dark heading fill keeps its text readable here.
            const n = parseInt(look.bg.slice(1), 16);
            const lum = (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
            if (lum < 0.5) { css += "color:#fff;"; }
        }
        return css;
    }

    get merged() {
        return (this.sheet?.merged || []).map(splitRange).filter(Boolean);
    }

    inMerged(r, c) {
        return this.merged.some((m) => c >= m.c0 && c <= m.c1 && r >= m.r0 && r <= m.r1);
    }

    /** Merged cells in the way (§5 state): said before Try it is pressed. */
    get mergedInWay() {
        const a = this.area;
        if (!a) { return ""; }
        const hit = (this.sheet?.merged || []).find((ref) => {
            const m = splitRange(ref);
            return m && m.c1 >= a.c0 && m.c0 <= a.c1 && m.r1 >= a.r0;
        });
        return hit || "";
    }

    get outline() {
        const a = this.area;
        const t = this.state.table;
        if (!a || !t) { return ""; }
        return _t("%(cols)s columns × %(rows)s rows from %(cell)s",
                  { cols: t.cols, rows: t.rows, cell: this.state.start });
    }

    get continues() {
        const a = this.area;
        if (!a) { return ""; }
        const parts = [];
        if (a.c1 > GRID_COLS) { parts.push(_t("across to column %s", colLetter(a.c1))); }
        if (a.r1 > GRID_ROWS) { parts.push(_t("down to row %s", a.r1)); }
        return parts.length ? _t("Continues %s", parts.join(_t(" and "))) : "";
    }

    get tableHere() {
        const p = splitCell(this.state.start);
        return (this.sheet?.tables || []).find((t) => {
            const s = splitCell(t.start);
            return s && p && s.c === p.c && s.r === (this.state.headers ? p.r : p.r - 1);
        }) || null;
    }

    get keepLine() {
        const lay = this.state.layout;
        return lay ? _t("The sheet “%(sheet)s” and the start cell %(cell)s are kept when the new file still has that sheet.",
                        { sheet: lay.sheet, cell: lay.start }) : "";
    }

    get goneLine() {
        return _t("The sheet “%s” is not in this file. Pick the sheet that receives the figures.", this.sheetGone);
    }

    get onSheet() { return _t("on “%s”", this.state.sheet); }

    get tableLine() {
        return _t("Your Excel table “%s” starts here. It will grow and shrink with the rows.", this.tableHere?.name || "");
    }

    get mergedLine() {
        return _t("Merged cells (%s) are in the way of the figures. Unmerge them in Excel, or start the figures somewhere else.",
                  this.mergedInWay);
    }

    get triedLine() {
        const t = this.state.tried;
        return t ? _t("Your file is downloaded with %(rows)s rows from %(cell)s. Open it to check, then save the layout.",
                      { rows: t.rows, cell: this.state.start }) : "";
    }

    get blocked() {
        return !this.state.sheet || !this.startValid || !!this.mergedInWay
            || !this.state.table || !this.state.table.cols;
    }

    toggleHeaders() { this.state.headers = !this.state.headers; this.state.tried = null; }
    toggleShared() { this.state.shared = !this.state.shared; }

    // ------------------------------------------------------- try and save
    async tryIt() {
        if (this.blocked || this.state.busy) { return; }
        this.state.busy = "try";
        this.state.saveError = "";
        try {
            const res = await this.orm.call(BOARD, "try_it", [
                this.state.fileB64 || false, this.state.sheet, this.state.start,
                this.state.headers, this.props.sourceModel, this.props.sourceId,
                this.state.fileName, this.state.fileB64 ? false : (this.props.layoutId || false)]);
            if (!res.ok) {
                this.state.saveError = res.msg;
                return;
            }
            saveFile(res.file_b64, res.filename, res.mimetype);
            this.state.tried = { rows: res.rows, cols: res.cols, notes: res.notes || [], filename: res.filename };
        } catch (e) {
            this.state.saveError = errText(e);
        } finally {
            this.state.busy = "";
        }
    }

    async save() {
        if (this.blocked || this.state.busy) { return; }
        const name = (this.state.name || "").trim();
        if (!name) {
            this.state.saveError = _t("Give the layout a name.");
            return;
        }
        this.state.busy = "save";
        this.state.saveError = "";
        try {
            let payload;
            if (this.mode === "new") {
                payload = await this.orm.call(BOARD, "save", [{
                    name, file_b64: this.state.fileB64, file_name: this.state.fileName,
                    sheet: this.state.sheet, start: this.state.start,
                    headers: this.state.headers, shared: this.state.shared,
                    source_model: this.props.sourceModel, source_id: this.props.sourceId,
                }]);
            } else {
                if (this.mode === "replace") {
                    const res = await this.orm.call(BOARD, "replace_file",
                        [this.props.layoutId, this.state.fileB64, this.state.fileName]);
                    if (!res.ok) {
                        this.state.saveError = res.msg;
                        return;
                    }
                }
                payload = await this.orm.call(BOARD, "update", [this.props.layoutId, {
                    name, sheet: this.state.sheet, start: this.state.start,
                    headers: this.state.headers, shared: this.state.shared }]);
            }
            this.notif.add(this.mode === "new"
                ? _t("“%s” is saved. Use “Download in my layout” any time.", payload.name)
                : _t("“%s” is saved.", payload.name), { type: "success" });
            this.props.onSaved?.(payload);
            this.props.close();
        } catch (e) {
            this.state.saveError = errText(e);
        } finally {
            this.state.busy = "";
        }
    }
}

// =====================================================================
//  The button — contract C2
// =====================================================================
export class PbExcelLayoutButton extends Component {
    static template = "pb_excel_layout.Button";
    static props = {
        sourceModel: String,
        sourceId: Number,
        disabledReason: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        this.xic = xic;
        this.rootRef = useRef("root");
        this.state = useState({
            open: false, loading: false, loaded: false, layouts: [], canAdd: true,
            confirm: 0, renaming: null, busy: 0, error: "", coach: "", menu: 0,
        });
        onWillUpdateProps((next) => {
            if (next.sourceId !== this.props.sourceId || next.sourceModel !== this.props.sourceModel) {
                Object.assign(this.state, { open: false, loaded: false, layouts: [], confirm: 0, renaming: null, menu: 0 });
            }
        });
        useExternalListener(window, "mousedown", (ev) => {
            if (this.state.open && this.rootRef.el && !this.rootRef.el.contains(ev.target)) {
                this.close();
            }
        }, { capture: true });
        useExternalListener(window, "keydown", (ev) => {
            if (this.state.open && ev.key === "Escape") { this.close(); }
        });
    }

    get disabled() { return !!this.props.disabledReason || !this.props.sourceId; }

    get btnTitle() {
        return this.disabled ? this.reason : _t("Fill your own Excel file with these figures");
    }

    get reason() {
        return this.props.disabledReason || (this.props.sourceId ? "" : _t("Save this view first"));
    }

    get mine() { return this.state.layouts.filter((l) => l.mine); }
    get shared() { return this.state.layouts.filter((l) => !l.mine); }

    async toggle() {
        if (this.disabled) { return; }
        if (this.state.open) { return this.close(); }
        this.state.open = true;
        await this.load();
    }

    close() {
        this.state.open = false;
        this.state.confirm = 0;
        this.state.renaming = null;
        this.state.menu = 0;
    }

    async load() {
        this.state.loading = !this.state.loaded;
        this.state.error = "";
        try {
            const res = await this.orm.call(BOARD, "list_for", [this.props.sourceModel, this.props.sourceId]);
            this.state.layouts = res.layouts;
            this.state.canAdd = res.can_add;
            this.state.coach = res.coach;
            this.state.loaded = true;
        } catch (e) {
            this.state.error = errText(e);
        } finally {
            this.state.loading = false;
        }
    }

    openDialog(mode, layout) {
        this.close();
        this.dialog.add(PbExcelLayoutDialog, {
            sourceModel: this.props.sourceModel,
            sourceId: this.props.sourceId,
            mode,
            layoutId: layout ? layout.id : 0,
            onSaved: () => { this.state.loaded = false; this.load(); },
        });
    }

    async download(layout) {
        if (this.state.busy) { return; }
        this.state.busy = layout.id;
        try {
            const res = await this.orm.call(BOARD, "download", [layout.id]);
            saveFile(res.file_b64, res.filename, res.mimetype);
            if (res.fallback) {
                this.notif.add(_t("“%(name)s” could not be used: %(why)s The standard Excel was downloaded instead.",
                                  { name: layout.name, why: res.msg }), { type: "warning", sticky: true });
            } else {
                this.notif.add(_t("Downloaded “%(name)s” with %(rows)s rows.", { name: layout.name, rows: res.rows }),
                               { type: "success" });
            }
            for (const note of res.notes || []) { this.notif.add(note, { type: "info" }); }
            this.close();
        } catch (e) {
            this.notif.add(errText(e), { type: "danger" });
        } finally {
            this.state.busy = 0;
        }
    }

    toggleMenu(layout) {
        this.state.menu = this.state.menu === layout.id ? 0 : layout.id;
        this.state.confirm = 0;
    }

    startRename(layout) {
        this.state.menu = 0;
        this.state.renaming = { id: layout.id, name: layout.name };
    }

    cancelRename() { this.state.renaming = null; }

    onRenameKey(ev) {
        if (ev.key === "Enter") { this.saveRename(); }
        if (ev.key === "Escape") { ev.stopPropagation(); this.state.renaming = null; }
    }

    async saveRename() {
        const r = this.state.renaming;
        if (!r) { return; }
        try {
            await this.orm.call(BOARD, "rename", [r.id, r.name]);
            this.state.renaming = null;
            await this.load();
        } catch (e) {
            this.notif.add(errText(e), { type: "danger" });
        }
    }

    async toggleShare(layout) {
        this.state.menu = 0;
        try {
            await this.orm.call(BOARD, "share", [layout.id, !layout.shared]);
            await this.load();
            this.notif.add(layout.shared
                ? _t("“%s” is now only yours.", layout.name)
                : _t("Everyone who can open this view can now use “%s”.", layout.name),
                { type: "success" });
        } catch (e) {
            this.notif.add(errText(e), { type: "danger" });
        }
    }

    askDelete(layout) { this.state.menu = 0; this.state.confirm = layout.id; }
    keep() { this.state.confirm = 0; }

    async remove(layout) {
        try {
            await this.orm.call(BOARD, "remove", [layout.id]);
            this.state.confirm = 0;
            await this.load();
        } catch (e) {
            this.notif.add(errText(e), { type: "danger" });
        }
    }

    fromWho(layout) { return _t("From %s", layout.owner); }

    meta(layout) {
        return layout.headers
            ? _t("Sheet “%(sheet)s” · from %(cell)s · with headings", { sheet: layout.sheet, cell: layout.start })
            : _t("Sheet “%(sheet)s” · from %(cell)s", { sheet: layout.sheet, cell: layout.start });
    }
}

registry.category("pb_excel_layout").add("button", PbExcelLayoutButton);
