/** @odoo-module **/
/**
 * The table view of a filtered list (kit 1.5.0): columns people choose.
 *
 *     this.cols = useListColumns({ model: "pb.people", kit: this.kit,
 *                                  onMode: () => this.loadPage() });
 *
 * and in the template, inside <PbFilterLayout>:
 *
 *     <t t-set-slot="toolbar"><PbTableTools cols="cols" kit="kit"/></t>
 *     <PbListTable t-if="cols.table" cols="cols" kit="kit" rows="rows" …/>
 *
 * Three layers make the columns somebody sees, each a list of `{key, on}`:
 * the board's standard set (`_pbf_columns` on the server) → the company's
 * default, set by an administrator "For everyone" → the person's own choice,
 * "Just me". A key a layer names that the board no longer has is skipped (a
 * deleted field never breaks the list); a column the board gained since a
 * layer was saved joins with its default, next to its neighbour.
 *
 * Nothing here changes a board that does not use it: the filter panel, its
 * views, sort and paging are the kit's as before.
 */
import {
    Component, markRaw, onMounted, onPatched, onWillStart, onWillUnmount, useExternalListener, useRef,
    useState,
} from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { pbfIcon, fmtCount } from "./filter_kit";

const MODES = ["cards", "table"];
const SAVE_DELAY = 350;
const FLASH_MS = 1300;

function clone(v) {
    return JSON.parse(JSON.stringify(v));
}

/**
 * `base` laid over by `saved` (both `[{key, on}]`): saved order and switches
 * for keys the base still has, then every base key saved did not know,
 * placed right after its nearest earlier neighbour.
 */
export function mergeColumns(base, saved) {
    const out = [];
    if (!Array.isArray(saved)) {
        return base.map((c) => ({ key: c.key, on: !!c.on }));
    }
    const known = new Map(base.map((c) => [String(c.key), c]));
    const seen = new Set();
    for (const s of saved) {
        const k = String(s && s.key);
        if (known.has(k) && !seen.has(k)) {
            out.push({ key: known.get(k).key, on: !!s.on });
            seen.add(k);
        }
    }
    base.forEach((c, i) => {
        const k = String(c.key);
        if (seen.has(k)) {
            return;
        }
        let at = 0;
        for (let j = i - 1; j >= 0; j--) {
            const idx = out.findIndex((o) => String(o.key) === String(base[j].key));
            if (idx >= 0) {
                at = idx + 1;
                break;
            }
        }
        out.splice(at, 0, { key: c.key, on: !!c.on });
        seen.add(k);
    });
    return out;
}

function sameCols(a, b) {
    return JSON.stringify(a || null) === JSON.stringify(b || null);
}

/** "2026-11-19" → "19 Nov 2026" (the chips' own date style). */
export function fmtDate(iso) {
    if (!iso) {
        return "";
    }
    try {
        const d = luxon.DateTime.fromISO(String(iso));
        return d.isValid ? d.toFormat("d LLL yyyy") : String(iso);
    } catch {
        return String(iso);
    }
}

// ================================================================= model
export class ListColumns {
    constructor({ orm, notification, model, kit, onMode }) {
        this.orm = markRaw(orm);
        this.notification = markRaw(notification);
        this.model = model;
        this.kit = kit;
        this.onMode = onMode;

        this.loaded = false;
        this.failed = false;
        this.screen = "";
        this.spec = [];
        this.company = null;
        this.mine = null;
        this.canCompany = false;
        this.mode = this._readMode() || "cards";

        this.ui = {
            open: false,
            scope: "me",
            draft: null,
            drag: null,
            over: null,
            flash: null,
            saving: false,
            saved: false,
            exporting: false,
        };
        this._timers = {};
        this._loading = null;
    }

    // ------------------------------------------------------------ storage
    get _modeKey() {
        return `pbf:lt:${this.model}:${user.userId}`;
    }
    _readMode() {
        try {
            const m = browser.localStorage.getItem(this._modeKey);
            return MODES.includes(m) ? m : null;
        } catch {
            return null;
        }
    }
    _writeMode(m) {
        try {
            browser.localStorage.setItem(this._modeKey, m);
        } catch {
            // private window: the switch still works, it just is not remembered here
        }
    }

    // --------------------------------------------------------------- load
    ensure() {
        if (!this._loading) {
            // raw: a promise behind a reactive proxy cannot be awaited
            this._loading = markRaw(this.load());
        }
        return this._loading;
    }
    async load() {
        let res;
        try {
            res = await this.orm.call(this.model, "pbf_columns", [], this.kit ? this.kit.kw() : {});
        } catch (e) {
            console.error("pb_filter_kit: the table columns could not load", e);
            this.failed = true;
            this.loaded = true;
            return;
        }
        this.screen = res.screen || "";
        this.spec = res.columns || [];
        this.company = res.company || null;
        this.mine = res.mine || null;
        this.canCompany = !!res.can_company;
        this.loaded = true;
        if (!this.spec.length) {
            // a board with no table: never stay in table mode
            this._applyMode("cards", false);
            return;
        }
        // The person's last choice on any device wins over this browser's memory.
        if (res.mode && res.mode !== this.mode) {
            this._applyMode(res.mode, true);
        }
    }

    // --------------------------------------------------------------- mode
    get table() {
        return this.mode === "table" && !this.failed && (!this.loaded || this.spec.length > 0);
    }
    get available() {
        return !this.loaded || (!this.failed && this.spec.length > 0);
    }
    _applyMode(mode, notify) {
        if (!MODES.includes(mode) || mode === this.mode) {
            return;
        }
        this.mode = mode;
        this._writeMode(mode);
        if (mode !== "table") {
            this.close();
        }
        if (notify && this.onMode) {
            this.onMode(mode);
        }
    }
    async setMode(mode) {
        if (!MODES.includes(mode) || mode === this.mode) {
            return;
        }
        if (mode === "table") {
            await this.ensure();
            if (this.failed || !this.spec.length) {
                this.notification.add(_t("The table could not be shown just now. Try again in a moment."),
                                      { type: "warning" });
                return;
            }
        }
        this._applyMode(mode, true);
        if (this.screen) {
            this.orm.call("pb.filter.view", "pbf_columns_save", [this.screen], { mode }).catch((e) => {
                console.warn("pb_filter_kit: view mode not remembered", e);
            });
        }
    }

    // ------------------------------------------------------------- layers
    get byKey() {
        return Object.fromEntries(this.spec.map((c) => [String(c.key), c]));
    }
    get base() {
        return this.spec.map((c) => ({ key: c.key, on: !!c.default }));
    }
    _pinFirst(list) {
        const pin = this.spec.find((c) => c.pin);
        if (!pin) {
            return list;
        }
        const rest = list.filter((c) => String(c.key) !== String(pin.key));
        return [{ key: pin.key, on: true }, ...rest];
    }
    get companyCols() {
        return this._pinFirst(mergeColumns(this.base, this.company));
    }
    get effectiveCols() {
        return this._pinFirst(mergeColumns(this.companyCols, this.mine));
    }
    get current() {
        return this.ui.open && this.ui.draft ? this.ui.draft : this.effectiveCols;
    }
    /** The columns the table draws, in order. */
    get columns() {
        const by = this.byKey;
        return this.current.filter((c) => c.on && by[String(c.key)]).map((c) => by[String(c.key)]);
    }
    /** Every column with its switch, for the chooser. */
    get chooser() {
        const by = this.byKey;
        return this.current.filter((c) => by[String(c.key)]).map((c) => ({ ...by[String(c.key)], on: c.on }));
    }
    get shownCount() {
        return this.columns.length;
    }
    get customOff() {
        return this.chooser.filter((c) => c.custom && !c.on).length;
    }

    // ------------------------------------------------------------ chooser
    open(scope = "me") {
        this.ui.open = true;
        this.setScope(scope);
    }
    close() {
        this.ui.open = false;
        this.ui.draft = null;
        this.ui.drag = null;
        this.ui.over = null;
        this.ui.saved = false;
    }
    setScope(scope) {
        if (scope === "company" && !this.canCompany) {
            scope = "me";
        }
        this.ui.scope = scope;
        this.ui.draft = clone(scope === "company" ? this.companyCols : this.effectiveCols);
        this.ui.saved = false;
    }
    get companyDirty() {
        return this.ui.scope === "company" && !!this.ui.draft && !sameCols(this.ui.draft, this.companyCols);
    }
    _isPin(key) {
        const c = this.byKey[String(key)];
        return !!(c && c.pin);
    }
    _flash(key) {
        this.ui.flash = key;
        clearTimeout(this._timers.flash);
        this._timers.flash = setTimeout(() => {
            this.ui.flash = null;
        }, FLASH_MS);
    }
    toggle(key) {
        if (!this.ui.draft || this._isPin(key)) {
            return;
        }
        this.ui.draft = this.ui.draft.map((c) => (String(c.key) === String(key) ? { ...c, on: !c.on } : c));
        const now = this.ui.draft.find((c) => String(c.key) === String(key));
        if (now && now.on) {
            this._flash(key);
        }
        this._changed();
    }
    /** Move `key` to sit before `beforeKey` (null = at the end). */
    moveBefore(key, beforeKey) {
        if (!this.ui.draft || this._isPin(key) || String(key) === String(beforeKey)) {
            return;
        }
        const list = this.ui.draft.filter((c) => String(c.key) !== String(key));
        const item = this.ui.draft.find((c) => String(c.key) === String(key));
        if (!item) {
            return;
        }
        let at = beforeKey === null || beforeKey === undefined
            ? list.length : list.findIndex((c) => String(c.key) === String(beforeKey));
        if (at < 0) {
            at = list.length;
        }
        list.splice(at, 0, item);
        this.ui.draft = this._pinFirst(list);
        this._flash(key);
        this._changed();
    }
    moveBy(key, delta) {
        if (!this.ui.draft) {
            return;
        }
        const keys = this.ui.draft.map((c) => String(c.key));
        const from = keys.indexOf(String(key));
        const min = this.spec.some((c) => c.pin) ? 1 : 0;
        const to = Math.max(min, Math.min(keys.length - 1, from + delta));
        if (from < 0 || to === from || this._isPin(key)) {
            return;
        }
        const list = [...this.ui.draft];
        const [item] = list.splice(from, 1);
        list.splice(to, 0, item);
        this.ui.draft = list;
        this._flash(key);
        this._changed();
    }
    canMove(key, delta) {
        if (!this.ui.draft || this._isPin(key)) {
            return false;
        }
        const keys = this.ui.draft.map((c) => String(c.key));
        const from = keys.indexOf(String(key));
        const min = this.spec.some((c) => c.pin) ? 1 : 0;
        const to = from + delta;
        return from >= 0 && to >= min && to < keys.length;
    }
    _changed() {
        this.ui.saved = false;
        if (this.ui.scope === "me") {
            clearTimeout(this._timers.save);
            this._timers.save = setTimeout(() => this.saveMine(), SAVE_DELAY);
        }
    }
    async saveMine() {
        if (!this.ui.draft || this.ui.scope !== "me" || !this.screen) {
            return;
        }
        const cols = clone(this.ui.draft);
        this.ui.saving = true;
        try {
            const res = await this.orm.call("pb.filter.view", "pbf_columns_save", [this.screen], { columns: cols });
            this.mine = res.mine || null;
            this.company = res.company || null;
            this.ui.saved = true;
        } catch (e) {
            this._fail(e, _t("Your columns could not be saved. Try again in a moment."));
        } finally {
            this.ui.saving = false;
        }
    }
    /** "Just me" → back to the company's columns. */
    async resetMine() {
        if (!this.screen) {
            return;
        }
        clearTimeout(this._timers.save);
        try {
            const res = await this.orm.call("pb.filter.view", "pbf_columns_reset", [this.screen], { scope: "me" });
            this.mine = res.mine || null;
            this.company = res.company || null;
            if (this.ui.open) {
                this.ui.draft = clone(this.effectiveCols);
            }
            this.notification.add(_t("Your own columns are gone: you now see the company's columns."),
                                  { type: "success" });
        } catch (e) {
            this._fail(e, _t("Your columns could not be reset. Try again in a moment."));
        }
    }
    /** "For everyone" → the board's standard set, still to be saved. */
    standardDraft() {
        if (this.ui.scope === "company") {
            this.ui.draft = this._pinFirst(this.base);
        }
    }
    get draftIsStandard() {
        return sameCols(this.ui.draft, this._pinFirst(this.base));
    }
    async saveCompany() {
        if (this.ui.scope !== "company" || !this.ui.draft || !this.screen) {
            return;
        }
        this.ui.saving = true;
        try {
            const res = this.draftIsStandard
                ? await this.orm.call("pb.filter.view", "pbf_columns_reset", [this.screen], { scope: "company" })
                : await this.orm.call("pb.filter.view", "pbf_columns_save", [this.screen],
                                      { columns: clone(this.ui.draft), scope: "company" });
            this.company = res.company || null;
            this.mine = res.mine || null;
            this.close();
            this.notification.add(
                _t("Saved for everyone. People who chose their own columns keep them."),
                { type: "success" }
            );
        } catch (e) {
            this._fail(e, _t("The columns for everyone could not be saved."));
        } finally {
            this.ui.saving = false;
        }
    }

    // ------------------------------------------------------------- export
    async download() {
        if (this.ui.exporting) {
            return;
        }
        const kit = this.kit;
        const q = kit.query;
        const total = kit.matched;
        this.ui.exporting = true;
        if (total > 500) {
            this.notification.add(_t("Building the file for %s rows…", fmtCount(total)), { type: "info" });
        }
        let res;
        try {
            res = await this.orm.call(this.model, "pbf_export_table", [], kit.kw({
                filters: q.filters,
                search: q.search,
                sort: q.sort,
                columns: this.columns.map((c) => c.key),
            }));
        } catch (e) {
            this._fail(e, _t("The file could not be built. Try again in a moment."));
            return;
        } finally {
            this.ui.exporting = false;
        }
        if (!res.ok) {
            this.notification.add(res.msg || _t("The file could not be built."), { type: "warning" });
            return;
        }
        saveFile(res);
        if (res.truncated) {
            this.notification.add(
                _t("%(shown)s of %(total)s rows are in the file — that is the most one file holds. Filter the list and download again for the rest.",
                   { shown: fmtCount(res.rows), total: fmtCount(res.total) }),
                { type: "warning", sticky: true }
            );
        } else {
            this.notification.add(
                res.rows === 1 ? _t("Downloaded — 1 row in the file.")
                    : _t("Downloaded — %s rows in the file.", fmtCount(res.rows)),
                { type: "success" }
            );
        }
    }

    _fail(e, message) {
        console.error("pb_filter_kit:", e);
        const detail = e && e.data && e.data.message;
        this.notification.add(detail || message, { type: "danger" });
    }
    destroy() {
        for (const t of Object.values(this._timers)) {
            clearTimeout(t);
        }
    }
}

/** base64 → a saved file, without leaving the page (the Records Desk way). */
export function saveFile(res) {
    const binary = window.atob(res.file_b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: res.mimetype });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = res.filename;
    link.click();
    URL.revokeObjectURL(url);
}

/**
 * Hook: one ListColumns for this board. In table mode the columns load before
 * the first paint; in card mode they load quietly after it, so a choice made
 * on another device still switches the board to the table.
 */
export function useListColumns(opts) {
    const orm = useService("orm");
    const notification = useService("notification");
    const cols = useState(new ListColumns({ orm, notification, ...opts }));
    onWillStart(async () => {
        if (cols.mode === "table") {
            await cols.ensure();
        }
    });
    onMounted(() => {
        if (cols.mode !== "table") {
            cols.ensure();
        }
    });
    onWillUnmount(() => cols.destroy());
    return cols;
}

// ============================================================ components
class PbltBase extends Component {
    static props = ["*"];
    setup() {
        this.cols = useState(this.props.cols);
    }
    icon(name, size = 16) {
        return pbfIcon(name, size);
    }
}

// --------------------------------------------------------- the chooser
export class PbColumnsButton extends PbltBase {
    static template = "pb_filter_kit.ColumnsButton";
    setup() {
        super.setup();
        this.root = useRef("root");
        useExternalListener(window, "mousedown", (ev) => {
            // "Just me" saves as it goes, so a click away simply closes; an
            // unsaved "For everyone" waits for Save or Cancel.
            if (this.cols.ui.open && this.root.el && !this.root.el.contains(ev.target)
                && !this.cols.companyDirty) {
                this.cols.close();
            }
        });
        useExternalListener(window, "keydown", (ev) => {
            if (ev.key === "Escape" && this.cols.ui.open) {
                this.cols.close();
            }
        });
    }
    toggle() {
        if (this.cols.ui.open) {
            this.cols.close();
        } else {
            this.cols.open("me");
        }
    }
    sub(c) {
        if (c.pin) {
            return _t("Always first");
        }
        if (c.custom) {
            return _t("Added with the Form builder");
        }
        return c.help || "";
    }
    // drag to reorder (mouse); the arrows do the same by keyboard or touch
    onDragStart(ev, c) {
        if (c.pin) {
            ev.preventDefault();
            return;
        }
        this.cols.ui.drag = c.key;
        try {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", String(c.key));
        } catch {
            // some browsers refuse data on drag start; the state carries it
        }
    }
    onDragOver(ev, c) {
        if (this.cols.ui.drag === null || c.pin) {
            return;
        }
        ev.preventDefault();
        if (this.cols.ui.over !== c.key) {
            this.cols.ui.over = c.key;
        }
    }
    onDrop(ev, c) {
        ev.preventDefault();
        const key = this.cols.ui.drag;
        this.cols.ui.drag = null;
        this.cols.ui.over = null;
        if (key !== null && !c.pin) {
            this.cols.moveBefore(key, c.key);
        }
    }
    onDropEnd(ev) {
        ev.preventDefault();
        const key = this.cols.ui.drag;
        this.cols.ui.drag = null;
        this.cols.ui.over = null;
        if (key !== null) {
            this.cols.moveBefore(key, null);
        }
    }
    onDragEnd() {
        this.cols.ui.drag = null;
        this.cols.ui.over = null;
    }
    get title() {
        return _t("Choose which columns the table shows, and their order");
    }
    moveLabel(c, dir) {
        return dir < 0 ? _t("Move %s up", c.label) : _t("Move %s down", c.label);
    }
}

// ----------------------------------------------- the toolbar's three tools
export class PbTableTools extends PbltBase {
    static template = "pb_filter_kit.TableTools";
    static components = { PbColumnsButton };
    get kit() {
        return this.props.kit;
    }
    setMode(m) {
        this.cols.setMode(m);
    }
    download() {
        this.cols.download();
    }
}

// ------------------------------------------------------------ the table
export class PbListTable extends PbltBase {
    static template = "pb_filter_kit.ListTable";
    setup() {
        super.setup();
        this.kit = useState(this.props.kit);
        this.scroll = useRef("scroll");
        this.st = useState({ left: false, right: false });
        const measure = () => this.measure();
        onMounted(measure);
        onPatched(measure);
        useExternalListener(window, "resize", measure);
    }
    measure() {
        const el = this.scroll.el;
        if (!el) {
            return;
        }
        const left = el.scrollLeft > 2;
        const right = el.scrollLeft + el.clientWidth < el.scrollWidth - 2;
        if (left !== this.st.left) {
            this.st.left = left;
        }
        if (right !== this.st.right) {
            this.st.right = right;
        }
    }
    get rowKey() {
        return this.props.rowKey || "id";
    }
    get hasActions() {
        return !!(this.props.slots && this.props.slots.actions);
    }
    get allTicked() {
        const rows = this.props.rows || [];
        return rows.length > 0 && rows.every((r) => this.props.isSelected(r[this.rowKey]));
    }
    // ---- sort: a heading switches between the board's own sort keys
    _sortable(c) {
        if (!c.sort) {
            return false;
        }
        const keys = new Set((this.kit.sorts || []).map((s) => s.key));
        return keys.has(c.sort.asc) || keys.has(c.sort.desc);
    }
    sortDir(c) {
        if (!c.sort) {
            return "";
        }
        if (c.sort.asc && this.kit.sort === c.sort.asc) {
            return "asc";
        }
        if (c.sort.desc && this.kit.sort === c.sort.desc) {
            return "desc";
        }
        return "";
    }
    ariaSort(c) {
        const d = this.sortDir(c);
        return d === "asc" ? "ascending" : d === "desc" ? "descending" : undefined;
    }
    sortBy(c) {
        if (!this._sortable(c)) {
            return;
        }
        const keys = new Set((this.kit.sorts || []).map((s) => s.key));
        const cur = this.sortDir(c);
        const asc = keys.has(c.sort.asc) ? c.sort.asc : null;
        const desc = keys.has(c.sort.desc) ? c.sort.desc : null;
        let next = asc || desc;
        if (cur === "asc" && desc) {
            next = desc;
        } else if (cur === "desc" && asc) {
            next = asc;
        }
        if (next && next !== this.kit.sort) {
            this.kit.setSort(next);
        }
    }
    thClass(c) {
        return {
            "is-pin": !!c.pin,
            "is-right": c.align === "right",
            "is-custom": !!c.custom,
            "is-sort": this._sortable(c),
            "is-sorted": !!this.sortDir(c),
            "is-flash": String(this.cols.ui.flash) === String(c.key),
        };
    }
    tdClass(c) {
        return {
            "is-pin": !!c.pin,
            "is-right": c.align === "right",
            "is-flash": String(this.cols.ui.flash) === String(c.key),
            [`k-${c.kind}`]: true,
        };
    }
    // ---- cells
    /** `{text, tone, icon, chip, chipTone, title, empty}` for one cell. */
    cell(row, c) {
        const own = this.props.cell ? this.props.cell(row, c) : null;
        const out = own ? { ...own } : this._default(row, c);
        out.empty = out.text === undefined || out.text === null || out.text === "";
        return out;
    }
    _value(row, c) {
        return row[c.field || c.key];
    }
    _default(row, c) {
        const v = this._value(row, c);
        switch (c.kind) {
            case "custom": {
                const cell = (row.pbfs || {})[c.key];
                return { text: cell === undefined || cell === null ? "" : String(cell) };
            }
            case "date":
                return { text: this.fmtDate(v) };
            case "money":
                return { text: v ? this.money(v, row.currency) : "" };
            case "flag":
                return v
                    ? { text: c.yes || _t("Yes"), icon: "checkCircle", tone: "green" }
                    : { text: c.no || _t("No"), icon: "alert", tone: "amber" };
            case "count":
                return { text: v ? fmtCount(v) : "" };
            case "badge":
                return { text: v || "", pill: true,
                         tone: (c.tones || {})[row[c.tone_field || c.key]] || "slate" };
            default:
                return { text: v === undefined || v === null || v === false ? "" : String(v) };
        }
    }
    fmtDate(iso) {
        return fmtDate(iso);
    }
    money(n, cur) {
        if (this.props.money) {
            return this.props.money(n, cur);
        }
        return (cur || "") + Number(n || 0).toLocaleString("en-US");
    }
    sub(row, c) {
        return c.sub ? row[c.sub] || "" : "";
    }
    // ---- rows
    onRow(row) {
        if (this.props.onRowClick) {
            this.props.onRowClick(row);
        }
    }
    onRowKey(ev, row) {
        if ((ev.key === "Enter" || ev.key === " ") && ev.target === ev.currentTarget) {
            ev.preventDefault();
            this.onRow(row);
        }
    }
    onTick(row) {
        if (this.props.onToggle) {
            this.props.onToggle(row[this.rowKey]);
        }
    }
    onTickAll() {
        if (this.props.onToggleAll) {
            this.props.onToggleAll(!this.allTicked);
        }
    }
    isTicked(row) {
        return !!(this.props.isSelected && this.props.isSelected(row[this.rowKey]));
    }
}
