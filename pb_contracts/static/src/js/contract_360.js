/** @odoo-module **/
/**
 * CD-2/CD-3 — the contract drawer. A bespoke slide-over on the Contracts lens
 * with three tabs (Terms · Components · History). CD-2 built it read-only;
 * CD-3 turns the same cells into editors, adds the Save bar, the debounced
 * refusal preview, staged component adds/removes and the lifecycle actions.
 *
 * Shape, motion and restraint mirror `Employee360Drawer`
 * (pb_employee_vault/static/src/js/employee_360.js) — teal is a person, indigo
 * is a contract. It registers into the soft "pb_contracts_drawer" registry so
 * the Contracts cockpit keeps a hard import out of `contracts.js` and stays
 * installable if this file ever moves to a satellite module.
 *
 * RPC facade: pb.contracts — `get_contract_360`, `save_contract_360`,
 * `preview_contract_360`, `lookup_contract_m2o`, `run_contract_action`. All
 * five already existed before this file learned to write; CD-3 added no server
 * method. Lucide icons only, from the SHARED registry (W2). Wage values are
 * masked server-side for non-payroll managers — the client never sees a number
 * it may not show, and never turns a masked cell into an input.
 *
 * W96: every expression a template evaluates lives in a method here. A
 * template is compiled against the COMPONENT and nothing else, so `String(x)`
 * or `Object.keys(x)` in the XML becomes `ctx.String(...)` and dies at mount
 * with no dialog and nothing in the log.
 *
 * No `t-model` anywhere: every editor is an explicit `t-att-value` plus
 * `t-on-input`, because the handler has to coerce the text, diff it against
 * what the record holds so the dirty key can be DELETED when the value comes
 * back, and kick the debounced preview.
 */
import {
    Component, useState, useRef, onWillStart, onMounted, onWillUnmount,
    useExternalListener,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.contracts";
const TABS = ["terms", "components", "history"];

// How long after the last keystroke the server is asked what it would refuse.
const PREVIEW_MS = 400;
// The m2o feed is debounced separately: a picker is typed into faster.
const LOOKUP_MS = 220;

// Group key → the icon that titles its section.
const GROUP_ICON = { money: "banknote", dates: "calendar", place: "mapPin", rules: "shield" };

// Term name → the icon on its cell. A term with no entry here gets a neutral
// dot-free label; nothing is invented per module (W2).
const FIELD_ICON = {
    wage: "banknote", struct_id: "layers", type_id: "users", schedule_pay: "clock",
    grade_id: "award", compa_ratio: "percent", journal_id: "bookOpen",
    date_start: "calendar", date_end: "calendar", trial_date_end: "clock",
    resource_calendar_id: "clock",
    department_id: "building", job_id: "briefcase", location: "mapPin",
    costcenter: "hash", hr_responsible_id: "user",
    hirestatus: "activity", tupart: "users", shuipart: "shield",
    dependents: "users", tax_identification_number: "stamp",
};

// Readiness chip key → icon.
const READY_ICON = { structure: "layers", schedule: "clock", tax: "stamp", category: "users" };

// History row kind → icon.
const KIND_ICON = { component: "banknote", field: "fileText", retro: "history" };

// Contract state → the chip tone the shared kit already paints.
const STATE_TONE = { open: "ok", close: "warn", draft: "info", cancel: "muted" };

const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// The three lifecycle steps the server will actually run
// (`pb_contracts.LIFECYCLE`). "Renew" is offered by the same payload and is
// NOT one of them, so it keeps carrying the person to the screen that owns it
// instead of being a button that quietly does nothing.
const RUNNABLE = new Set(["set_running", "terminate", "cancel"]);

/** Group digits so a big amount stays readable while it is being staged. */
function grouped(value) {
    const n = Number(value);
    if (!isFinite(n)) { return String(value); }
    return n.toLocaleString("en-US", {
        minimumFractionDigits: 0,
        maximumFractionDigits: Number.isInteger(n) ? 0 : 2,
    });
}

// ---------------------------------------------------------------------------
//  CdPicker — one filterable list, two sources, floated clear of the drawer
// ---------------------------------------------------------------------------
/**
 * A selection and a many2one both present as "a list you filter and choose
 * from", so they share one popover; the only difference is where the rows come
 * from (a fixed `options` list, or `lookup_contract_m2o` debounced over the
 * wire).
 *
 * It is `position: fixed` and placed from the cell's own
 * `getBoundingClientRect()`. The drawer body is `overflow-y: auto`, so a
 * popover positioned inside it is clipped by the scroller the moment the list
 * is taller than the room under the cell — CD-2 flagged this as the hardest
 * thing in the phase. Fixed takes it out of the scroller entirely; the cost is
 * that it no longer travels with the content, so it re-places itself on every
 * scroll and resize, and closes on an outside click or Escape.
 */
export class CdPicker extends Component {
    static template = "pb_contracts.CdPicker";
    static props = {
        rows: { type: Array, optional: true },         // fixed list [{id,label}]
        lookup: { type: Function, optional: true },    // async (term) => rows
        onPick: { type: Function },
        onCancel: { type: Function },
        allowClear: { type: Boolean, optional: true },
        anchorEl: { optional: true },                  // the cell to float beside
        clearLabel: { type: String, optional: true },
    };

    setup() {
        this.rootRef = useRef("root");
        this.inputRef = useRef("input");
        this.clearRef = useRef("clear");
        this.state = useState({
            term: "", rows: this.staticRows(""), active: 0, loading: false,
            top: 0, left: 0, width: 260, up: false, placed: false,
        });
        this._timer = null;
        onMounted(() => {
            this.place();
            // A short fixed list has no search box, so there would be nothing
            // for Escape to land on and the edit could not be got out of. The
            // popover itself takes focus in that case.
            const target = this.inputRef.el || this.rootRef.el;
            if (target) { target.focus(); }
            if (this.props.lookup) { this.search(""); }
        });
        onWillUnmount(() => this._timer && clearTimeout(this._timer));
        // Fixed means "does not travel with the content", so it has to be told
        // when the content moved. Capture catches the drawer body's own scroll,
        // which never reaches window in the bubble phase.
        useExternalListener(window, "scroll", () => this.place(), { capture: true });
        useExternalListener(window, "resize", () => this.place());
        useExternalListener(window, "mousedown", (ev) => this.onOutside(ev), { capture: true });
    }

    ic(n, s = 14) { return ic(n, s); }

    // --------------------------------------------------------------- placing
    /**
     * Where the list goes.
     *
     * TWO traps, both measured rather than assumed:
     *
     * 1. The drawer body is `overflow-y: auto`, so anything laid out inside it
     *    is clipped by the scroller. `position: fixed` takes the list out of
     *    that scroller entirely.
     * 2. `position: fixed` is NOT relative to the viewport when an ancestor
     *    carries a transform — and the drawer does, because it slides. So the
     *    containing block may be the drawer's own box, and viewport
     *    coordinates from `getBoundingClientRect()` would land the list 680px
     *    off to the right. Instead of guessing which ancestor won, the origin
     *    is measured: where did the last applied `top/left` actually put us?
     *    The difference is the correction, and it is zero when there is no
     *    transformed ancestor.
     */
    place() {
        const el = this.props.anchorEl;
        const root = this.rootRef.el;
        if (!el || !el.getBoundingClientRect || !root) { return; }
        const r = el.getBoundingClientRect();
        const own = root.getBoundingClientRect();
        const offsetX = own.left - this.state.left;
        const offsetY = own.top - this.state.top;

        const width = Math.max(r.width, 240);
        const maxH = 292;
        const below = window.innerHeight - r.bottom;
        const up = below < maxH && r.top > below;
        const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8));
        const wanted = up ? (r.top - maxH - 6) : (r.bottom + 6);
        // Clamped both ways: an anchor scrolled half out of the drawer body
        // must not push the list off the bottom of the screen.
        const top = Math.max(8, Math.min(wanted, window.innerHeight - maxH - 8));

        this.state.width = width;
        this.state.left = left - offsetX;
        this.state.top = top - offsetY;
        this.state.up = up;
        this.state.placed = true;
    }
    get posStyle() {
        return "top:" + Math.round(this.state.top) + "px;left:"
            + Math.round(this.state.left) + "px;width:"
            + Math.round(this.state.width) + "px";
    }

    onOutside(ev) {
        const root = ev.target && ev.target.closest
            ? ev.target.closest(".pbc-pick") : null;
        if (!root) { this.props.onCancel(); }
    }

    // ---------------------------------------------------------------- rows
    staticRows(term) {
        const t = (term || "").toLowerCase();
        return (this.props.rows || []).filter(
            (r) => !t || String(r.label || "").toLowerCase().includes(t));
    }
    get allRows() { return this.state.rows; }
    get filterable() { return (this.props.rows || []).length > 8 || Boolean(this.props.lookup); }
    get placeholder() {
        return this.props.lookup ? _t("Type to search…") : _t("Type to filter…");
    }
    get emptyLabel() {
        return this.props.lookup
            ? _t("Nothing matches — and nothing is created from here.")
            : _t("No choice matches that.");
    }
    get clearText() { return this.props.clearLabel || _t("Leave empty"); }

    onInput(ev) {
        this.state.term = ev.target.value;
        if (!this.props.lookup) {
            this.state.rows = this.staticRows(this.state.term);
            this.state.active = 0;
            return;
        }
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.search(this.state.term), LOOKUP_MS);
    }

    async search(term) {
        this.state.loading = true;
        try {
            this.state.rows = (await this.props.lookup(term)) || [];
            this.state.active = 0;
        } finally {
            this.state.loading = false;
        }
    }

    pick(row) {
        if (!row) { return; }
        this.props.onPick(row.id, row.label);
    }
    clear() { this.props.onPick(false, ""); }

    /**
     * Every key handled here stops here.
     *
     * Two listeners are waiting for the same keys one level up: the editor's
     * own keydown, and the drawer's window-level Escape. A picker that lets
     * Escape through cancels the edit AND closes the whole panel in one press.
     */
    onKey(ev) {
        const rows = this.allRows;
        if (ev.key === "ArrowDown") {
            ev.preventDefault(); ev.stopPropagation();
            this.state.active = Math.min(this.state.active + 1, rows.length - 1);
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault(); ev.stopPropagation();
            this.state.active = Math.max(this.state.active - 1, 0);
        } else if (ev.key === "Enter") {
            ev.preventDefault(); ev.stopPropagation();
            this.pick(rows[this.state.active]);
        } else if (ev.key === "Escape") {
            ev.preventDefault(); ev.stopPropagation();
            this.props.onCancel();
        } else if (ev.key === "Tab") {
            // Trapped: Tab moves between the two focusable things this popover
            // owns and never walks off into the roster behind the drawer.
            ev.preventDefault(); ev.stopPropagation();
            const onInput = document.activeElement === this.inputRef.el;
            const target = (onInput && this.clearRef.el) ? this.clearRef.el : this.inputRef.el;
            if (target) { target.focus(); }
        }
    }
    rowClass(index) { return { on: this.state.active === index }; }
    setActive(index) { this.state.active = index; }
}

// ---------------------------------------------------------------------------
//  CdEditor — one value, being typed into
// ---------------------------------------------------------------------------
/**
 * One component with a nine-way switch rather than nine components, because
 * every one of them owes the drawer the same three things — commit, cancel and
 * move on — and nine copies of that contract is how two of them end up
 * disagreeing about what Escape does (`RdCellEditor`,
 * pb_records/static/src/js/records_cells.js:230).
 */
export class CdEditor extends Component {
    static template = "pb_contracts.CdEditor";
    static components = { CdPicker };
    static props = {
        entry: { type: Object },            // {kind, options?, comodel?, required, label}
        value: { optional: true },
        currency: { type: String, optional: true },
        onCommit: { type: Function },       // (value, label) => void
        onCancel: { type: Function },
        onMove: { type: Function, optional: true },   // ("next"|"prev") => void
        lookup: { type: Function, optional: true },
        anchorEl: { optional: true },
        resting: { type: String, optional: true },
    };

    setup() {
        this.rootRef = useRef("root");
        this.inputRef = useRef("input");
        this.state = useState({ draft: this.initialDraft() });
        this._committed = false;
        onMounted(() => {
            if (this.inputRef.el) {
                this.inputRef.el.focus();
                if (this.inputRef.el.select) { this.inputRef.el.select(); }
            } else if (this.kind === "toggle" && this.rootRef.el) {
                // The YES / NO pair has no input, so the first of the two
                // buttons takes focus: otherwise Escape has nothing listening
                // for it and the cell cannot be got out of without saving
                // something, and there is no visible focus either.
                //
                // Guarded to `toggle` on purpose. A child's `onMounted` runs
                // BEFORE its parent's, so for a select or a many2one the
                // popover has already focused its own search box by now — and
                // an unguarded `querySelector("button")` here found the
                // popover's "Leave empty" and stole the focus straight back.
                // Caught on the live walk.
                const first = this.rootRef.el.querySelector("button");
                (first || this.rootRef.el).focus();
            }
        });
    }

    ic(n, s = 14) { return ic(n, s); }

    get entry() { return this.props.entry; }
    /** The nine kinds the payload can name. `readonly` never reaches here. */
    get kind() {
        const k = this.entry.kind;
        return ["money", "number", "integer", "text", "date", "select",
                "toggle", "m2o"].includes(k) ? k : "text";
    }
    get isNumeric() { return ["money", "number", "integer"].includes(this.kind); }
    /** `pop` means "this kind lives in a floated popover, not in the box": the
     *  wrapper must then take no space at all, or the cell grows by an empty
     *  input while the list is open. */
    get edClass() {
        return { num: this.isNumeric, pop: ["select", "m2o"].includes(this.kind) };
    }
    get currencyPrefix() { return this.kind === "money" ? (this.props.currency || "") : ""; }
    /** What the cell keeps showing while a floated popover is open over it.
     *  Without this the cell reads as emptied for as long as the list is up. */
    get restingText() { return this.props.resting || ""; }
    /** A whole number takes no decimal point, so the keypad shows none. */
    get inputMode() { return this.kind === "integer" ? "numeric" : "decimal"; }

    initialDraft() {
        const v = this.props.value;
        if (v === null || v === undefined || v === false) { return ""; }
        return String(v);
    }

    // ------------------------------------------------------------- options
    get pickerRows() {
        return (this.entry.options || []).map(
            (o) => ({ id: o.value, label: o.label }));
    }
    /** Only an optional field may be emptied — offering it otherwise is an
     *  offer the server declines, and that is worse than no control (W29). */
    get allowClear() { return !this.entry.required; }
    get yesLabel() { return _t("Yes"); }
    get noLabel() { return _t("No"); }
    get toggleOptions() { return this.entry.options || []; }
    toggleClass(option) {
        return { on: String(this.props.value || "") === String(option.value) };
    }

    // ------------------------------------------------------------- commits
    commit(value, label) { this._committed = true; this.props.onCommit(value, label); }
    onInput(ev) { this.state.draft = ev.target.value; }

    onPick(id, label) { this.commit(id, label); }
    onToggle(option) { this.commit(option.value, option.label); }

    onBlur() {
        // A blur is a commit, never a silent discard: somebody who types a
        // value and clicks elsewhere on the panel has said what they meant.
        if (this._committed) { return; }
        if (["text", "date", "money", "number", "integer"].includes(this.kind)) {
            this.commit(this.state.draft);
        }
    }

    /**
     * EVERY key this editor handles stops here.
     *
     * Without `stopPropagation` the keydown reaches the drawer, which listens
     * for the same keys — and Escape there closes the whole panel, so a person
     * who meant "undo this cell" loses every staged change on the contract.
     * (`records_cells.js:293`, found on a live walk, is the same scar.)
     */
    onKey(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault(); ev.stopPropagation();
            // Marked done so the blur that follows the unmount cannot come
            // back round and commit the very draft that was just abandoned.
            this._committed = true;
            this.props.onCancel();
            return;
        }
        // The two buttons own Enter and Space themselves; committing a "draft"
        // here as well would stage the value that is already on the record.
        if (this.kind === "toggle") { return; }
        if (ev.key === "Enter") {
            ev.preventDefault(); ev.stopPropagation();
            this.commit(this.state.draft);
            if (this.props.onMove) { this.props.onMove("next"); }
        } else if (ev.key === "Tab") {
            ev.preventDefault(); ev.stopPropagation();
            this.commit(this.state.draft);
            if (this.props.onMove) { this.props.onMove(ev.shiftKey ? "prev" : "next"); }
        }
    }
}

// ---------------------------------------------------------------------------
//  Contract360Drawer
// ---------------------------------------------------------------------------
export class Contract360Drawer extends Component {
    static template = "pb_contracts.Contract360Drawer";
    static components = { CdEditor, CdPicker };
    static props = {
        contractId: { type: [Number, String] },
        onClose: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, shown: false, tab: "terms", d: null,
            // CD-3 — what has been typed but not written. A key is DELETED the
            // moment its value comes back to what the record holds, so the
            // count on the Save bar can never lie
            // (`component_treatment.js:198`).
            dirty: { terms: {}, comps: { edits: {}, adds: [], removes: [] } },
            // {"term:wage": "sentence"} — a refusal is a red dot with a
            // sentence under its own cell, never a modal
            // (`records_desk.js:412`).
            refusals: {},
            accept: 0,
            edit: null,        // {scope, key}
            addOpen: false,
            saving: false,
            busy: false,       // a lifecycle action is running
            asking: false,     // a confirmation dialog owns Escape
        });
        // Non-reactive: the cell a popover floats beside. Putting a DOM node in
        // reactive state makes OWL proxy it, and a proxied element is not the
        // element `getBoundingClientRect` was measured on.
        this._anchorEl = null;
        this._addAnchorEl = null;
        this._previewTimer = null;

        onWillStart(() => this.load());
        // One frame after mount, so the panel has a place to slide in FROM.
        onMounted(() => { this.state.shown = true; });
        onWillUnmount(() => clearTimeout(this._previewTimer));
        // Escape closes, Cmd/Ctrl-Enter saves. Capture phase is the safe
        // pattern for an overlay that does not steal focus from the roster
        // underneath it — and it is exactly why `onKey` has to stand aside for
        // an open editor: a capture listener on window runs BEFORE the child's
        // own handler, so the child's `stopPropagation` cannot reach it.
        useExternalListener(window, "keydown", (ev) => this.onKey(ev), { capture: true });
    }

    // ---------------------------------------------------------------- reading
    async load() {
        try {
            this.state.d = await this.orm.call(MODEL, "get_contract_360", [Number(this.props.contractId)]);
        } catch (e) {
            this.state.d = { error: this._err(e) };
        } finally {
            this.state.loaded = true;
        }
    }
    _err(e) {
        return (e && e.message && e.message.data && e.message.data.message)
            || (e && e.data && e.data.message)
            || _t("Payobook could not open this contract just now. Try again in a moment.");
    }

    // ------------------------------------------------------------- accessors
    // Rail 10: a payload from an older server is missing keys, not broken. Every
    // accessor below hands back an empty shape rather than letting the template
    // read through `undefined`.
    get d() { return this.state.d || {}; }
    get header() { return this.d.header || {}; }
    get terms() { return this.d.terms || []; }
    get readiness() { return this.d.readiness || []; }
    get components() { return this.d.components || {}; }
    get compRows() { return this.components.rows || []; }
    get addable() { return this.components.addable || []; }
    get history() { return this.d.history || {}; }
    get pipeline() { return this.header.pipeline || []; }
    get nextActions() { return this.header.next_actions || []; }
    get compCount() { return this.compRows.length + this.state.dirty.comps.adds.length; }
    get histCount() { return this.history.total || 0; }
    get hasMoreHistory() { return (this.history.total || 0) > (this.history.shown || 0); }
    get canWrite() { return this.d.can_write === true; }
    get currency() { return this.d.currency || ""; }

    // The header's wage is a raw number; its SENTENCE was formatted once,
    // server-side (rail 8), and lives on the `wage` term. Read it from there
    // rather than teaching the client a second opinion about money.
    termEntry(name) {
        for (const group of this.terms) {
            for (const field of (group.fields || [])) {
                if (field.name === name) { return field; }
            }
        }
        return null;
    }
    get wageDisplay() {
        const entry = this.termEntry("wage");
        if (!entry) { return ""; }
        // A staged wage shows in the header so the summary and the cell agree
        // — but a REFUSED one does not: the header is the one number a person
        // reads at a glance, and "abc" up there is a lie about the contract.
        const staged = this.state.dirty.terms.wage;
        if (staged && !this.refusalFor("term", "wage")) { return staged.label; }
        return entry.display || "";
    }
    get wageStaged() {
        return this.isTermDirty("wage") && !this.hasRefusal("term", "wage");
    }

    ic(n, s = 16) { return ic(n, s); }
    groupIcon(key) { return ic(GROUP_ICON[key] || "fileText", 14); }
    fieldIcon(name) { return ic(FIELD_ICON[name] || "chevron", 14); }
    readyIcon(key) { return ic(READY_ICON[key] || "check", 14); }
    kindIcon(kind) { return ic(KIND_ICON[kind] || "history", 15); }
    stateTone(s) { return STATE_TONE[s] || "muted"; }

    // ---------------------------------------------------------------- chrome
    // Switching tabs starts the new one at the top. Without this, arriving at
    // Components from the bottom of Terms lands halfway down a list of
    // twenty-one rows and the explainer above them is never seen.
    setTab(t) {
        this.state.edit = null;
        this.state.addOpen = false;
        this.state.tab = t;
        const body = document.querySelector(".pbc-body");
        if (body) { body.scrollTop = 0; }
    }
    get tabIndex() {
        const i = TABS.indexOf(this.state.tab);
        return i < 0 ? 0 : i;
    }
    // The tab underline slides because ONE bar moves, not because three bars
    // fade. Equal-width tabs make the offset pure arithmetic — no measuring, no
    // onPatched write-back into reactive state (W148).
    get inkStyle() { return "transform: translateX(" + (this.tabIndex * 100) + "%)"; }

    /**
     * The drawer's own keys.
     *
     * It stands aside whenever something nearer the person owns the key: an
     * open editor owns Escape (this listener is on window in the CAPTURE
     * phase, so it fires before the editor and `stopPropagation` down there
     * cannot stop it), and a confirmation dialog owns Escape too — without
     * that guard, dismissing "Leave them?" would immediately ask it again.
     */
    onKey(ev) {
        if (this.state.asking) { return; }
        if ((ev.key === "Enter") && (ev.metaKey || ev.ctrlKey)) {
            if (!this.canWrite) { return; }
            ev.preventDefault();
            ev.stopPropagation();
            // A cell still being typed into is committed first — a blur IS a
            // commit — so this never saves a set that is one keystroke out of
            // date. One tick later, because the blur has to land first.
            if (this.state.edit && document.activeElement
                    && document.activeElement.blur) {
                document.activeElement.blur();
            }
            setTimeout(() => this.save(), 0);
            return;
        }
        if (ev.key !== "Escape") { return; }
        if (this.state.edit || this.state.addOpen) { return; }
        this.close();
    }

    close() {
        if (this.dirtyCount > 0) { this.askBeforeLeaving(); return; }
        this.reallyClose();
    }
    reallyClose() {
        this.state.shown = false;
        const done = this.props.onClose || (() => { });
        setTimeout(done, 180);   // let the slide-out play before we unmount
    }
    /**
     * An edit that vanishes silently is the worst thing that can happen on this
     * screen, so Escape, the scrim and the × all come through here.
     */
    askBeforeLeaving() {
        const n = this.dirtyCount;
        this.state.asking = true;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Unsaved changes"),
            body: n === 1
                ? _t("You have 1 unsaved change on this contract. Leave it?")
                : _t("You have %s unsaved changes on this contract. Leave them?",
                     grouped(n)),
            confirmLabel: _t("Leave"),
            cancelLabel: _t("Keep editing"),
            confirm: () => { this.state.asking = false; this.reallyClose(); },
            cancel: () => { this.state.asking = false; },
        }, { onClose: () => { this.state.asking = false; } });
    }

    // The escape hatch. Never called "the Odoo form" — it is the full form.
    openFullForm() {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.contract",
            res_id: Number(this.props.contractId), views: [[false, "form"]],
            target: "current",
        });
    }
    openFullScreen() {
        this.action.doAction({
            type: "ir.actions.client", tag: "pb_contract_detail", name: "Contract",
            params: { contract_id: Number(this.props.contractId) },
        });
    }

    // =====================================================================
    //  CD-3 — the dirty map
    // =====================================================================
    get dirty() { return this.state.dirty; }
    get dirtyCount() {
        const c = this.state.dirty.comps;
        return Object.keys(this.state.dirty.terms).length
            + Object.keys(c.edits).length + c.adds.length + c.removes.length;
    }
    get isDirty() { return this.dirtyCount > 0; }

    _num(value) {
        const text = String(value === false || value === undefined || value === null
            ? "" : value).replace(/,/g, "").trim();
        if (text === "") { return 0; }
        const n = Number(text);
        return isFinite(n) ? n : null;
    }

    /** Has this value come back to what the record holds? Then it is not a
     *  change, and its key is deleted so the Save bar's count stays truthful. */
    _sameAsRecord(entry, value) {
        const cur = entry.value;
        if (entry.kind === "money" || entry.kind === "number" || entry.kind === "integer") {
            const a = this._num(value);
            if (a === null) { return false; }
            return Math.abs(a - Number(cur || 0)) < 1e-9;
        }
        if (entry.kind === "m2o") {
            return Number(value || 0) === Number(cur || 0);
        }
        const left = (value === false || value === undefined || value === null) ? "" : String(value);
        const right = (cur === false || cur === undefined || cur === null) ? "" : String(cur);
        return left.trim() === right.trim();
    }

    /**
     * The one thing the client judges for itself.
     *
     * The server's whole-number coercion is `int(float(x))`, which would turn
     * 2.5 into 2 and report it saved — so a decimal typed into a whole-number
     * cell is refused HERE, in the server's own words, and the key is held
     * back from the save instead of being quietly rounded.
     */
    _clientRefusal(entry, value) {
        if (entry.kind !== "integer") { return null; }
        const text = String(value === false || value === undefined || value === null
            ? "" : value).replace(/,/g, "").trim();
        if (text === "") { return null; }
        if (/^-?\d+$/.test(text)) { return null; }
        return _t("'%s' is not a whole number — type a number like 2.", text);
    }

    /** What a staged value reads as before it is saved. Server-side formatting
     *  is the only formatting after a save (rail 12); until then the person
     *  sees what they typed, grouped, and the old value struck through. */
    _stageLabel(entry, value, label) {
        if (label !== undefined && label !== null) { return label; }
        if (value === false || value === "" || value === undefined || value === null) {
            return _t("Empty");
        }
        if (["money", "number", "integer"].includes(entry.kind)) {
            const n = this._num(value);
            return n === null ? String(value) : grouped(n);
        }
        return String(value);
    }

    // -------------------------------------------------------------- terms
    canEdit(f) { return Boolean(this.canWrite && f.writable); }
    cellTab(f) { return this.canEdit(f) ? 0 : -1; }
    compTab(row) { return this.canEditComp(row) ? 0 : -1; }
    cellKey(f) { return "term:" + f.name; }
    cellClass(f) {
        return {
            "tone-warn": f.tone === "warn" && !this.isTermDirty(f.name),
            editable: this.canEdit(f),
            locked: !this.canEdit(f),
            staged: this.isTermDirty(f.name),
            refused: Boolean(this.refusalFor("term", f.name)),
            editing: this.isEditing("term", f.name),
        };
    }
    isTermDirty(name) { return Object.prototype.hasOwnProperty.call(this.state.dirty.terms, name); }
    isEditing(scope, key) {
        const e = this.state.edit;
        return Boolean(e && e.scope === scope && String(e.key) === String(key));
    }
    termDisplay(f) {
        const staged = this.state.dirty.terms[f.name];
        return staged ? staged.label : (f.display || "—");
    }
    termWas(f) { return this.isTermDirty(f.name) ? (f.display || "—") : ""; }
    termEditValue(f) {
        const staged = this.state.dirty.terms[f.name];
        if (!staged) { return f.value; }
        return staged.value;
    }
    /** `undefined`, never `null` — a typed optional prop rejects null (W35). */
    termLookup(f) {
        if (f.kind !== "m2o" || !f.comodel) { return undefined; }
        return (term) => this.orm.call(MODEL, "lookup_contract_m2o", [], {
            comodel: f.comodel, term: term || "", limit: 12,
        });
    }
    get anchorEl() { return this._anchorEl; }
    get addAnchorEl() { return this._addAnchorEl; }

    startTerm(f, ev) {
        if (!this.canEdit(f)) { return; }
        if (this.isEditing("term", f.name)) { return; }
        this._anchorEl = ev.currentTarget;
        this.state.addOpen = false;
        this.state.edit = { scope: "term", key: f.name };
    }
    onCellKey(f, ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            if (!this.canEdit(f) || this.isEditing("term", f.name)) { return; }
            ev.preventDefault();
            ev.stopPropagation();
            this._anchorEl = ev.currentTarget;
            this.state.edit = { scope: "term", key: f.name };
        }
    }
    commitTerm(f, value, label) {
        if (this._sameAsRecord(f, value)) {
            delete this.state.dirty.terms[f.name];
        } else {
            this.state.dirty.terms[f.name] = {
                value, label: this._stageLabel(f, value, label),
            };
        }
        this.state.edit = null;
        this.onChanged();
    }
    cancelEdit() { this.state.edit = null; }

    /** The writable terms, in the order they are painted. */
    editableTermNames() {
        const out = [];
        for (const group of this.terms) {
            for (const f of (group.fields || [])) {
                if (this.canEdit(f)) { out.push(f.name); }
            }
        }
        return out;
    }
    moveTerm(f, dir) {
        const names = this.editableTermNames();
        const i = names.indexOf(f.name);
        const j = dir === "prev" ? i - 1 : i + 1;
        if (i < 0 || j < 0 || j >= names.length) { this.state.edit = null; return; }
        const next = names[j];
        this._anchorEl = document.querySelector('[data-cdkey="term:' + next + '"]');
        this.state.edit = { scope: "term", key: next };
    }

    // ---------------------------------------------------------- components
    compKey(row) { return "comp:" + row.id; }
    canEditComp(row) { return Boolean(this.canWrite && row.writable && !this.isRemoved(row.id)); }
    isCompDirty(id) { return Object.prototype.hasOwnProperty.call(this.state.dirty.comps.edits, String(id)); }
    isRemoved(id) { return this.state.dirty.comps.removes.includes(Number(id)); }
    compClass(row) {
        return {
            editable: this.canEditComp(row),
            staged: this.isCompDirty(row.id),
            removed: this.isRemoved(row.id),
            refused: Boolean(this.refusalFor("comp", row.id)),
            editing: this.isEditing("comp", row.id),
        };
    }
    compDisplay(row) {
        const staged = this.state.dirty.comps.edits[String(row.id)];
        return staged ? staged.label : (row.display || "—");
    }
    compWas(row) { return this.isCompDirty(row.id) ? (row.display || "—") : ""; }
    compEditValue(row) {
        const staged = this.state.dirty.comps.edits[String(row.id)];
        if (staged) { return staged.value; }
        return row.value_type === "text" ? (row.text_value || "") : (row.amount || 0);
    }
    /** The payload's component row, dressed as a term entry so ONE editor and
     *  ONE coercion path serve both halves of the drawer. */
    compEntry(row) {
        return {
            name: "comp" + row.id,
            label: row.name,
            kind: row.value_type === "text" ? "text" : "money",
            value: row.value_type === "text" ? (row.text_value || "") : (row.amount || 0),
            required: false,
            writable: true,
        };
    }
    startComp(row, ev) {
        if (!this.canEditComp(row)) { return; }
        if (this.isEditing("comp", row.id)) { return; }
        this._anchorEl = ev.currentTarget;
        this.state.addOpen = false;
        this.state.edit = { scope: "comp", key: row.id };
    }
    onCompKey(row, ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            if (!this.canEditComp(row) || this.isEditing("comp", row.id)) { return; }
            ev.preventDefault();
            ev.stopPropagation();
            this._anchorEl = ev.currentTarget;
            this.state.edit = { scope: "comp", key: row.id };
        }
    }
    commitComp(row, value) {
        const entry = this.compEntry(row);
        const key = String(row.id);
        if (this._sameAsRecord(entry, value)) {
            delete this.state.dirty.comps.edits[key];
        } else {
            this.state.dirty.comps.edits[key] = {
                value,
                isText: row.value_type === "text",
                label: this._stageLabel(entry, value),
            };
        }
        this.state.edit = null;
        this.onChanged();
    }
    editableCompIds() {
        return this.compRows.filter((r) => this.canEditComp(r)).map((r) => r.id);
    }
    moveComp(row, dir) {
        const ids = this.editableCompIds();
        const i = ids.indexOf(row.id);
        const j = dir === "prev" ? i - 1 : i + 1;
        if (i < 0 || j < 0 || j >= ids.length) { this.state.edit = null; return; }
        const next = ids[j];
        this._anchorEl = document.querySelector('[data-cdkey="comp:' + next + '"]');
        this.state.edit = { scope: "comp", key: next };
    }

    /**
     * The amber lines under a component that is being changed.
     *
     * Shown WHILE the person types, not after they save: a value the next pay
     * run overwrites is a thing to know before the effort, not after it. This
     * is information, never a refusal — the edit is always allowed.
     */
    compWarnings(row) {
        if (!this.isCompDirty(row.id) && !this.isEditing("comp", row.id)) { return []; }
        const out = [];
        // Worded for the actual source. Written out one literal per case, not
        // looked up from a map, because a sentence that reaches `_t` as a
        // variable is never collected for translation.
        if (row.fills_from === "excel") {
            out.push(_t("The next pay run will replace this with the value from the pay data file."));
        } else if (row.fills_from === "api") {
            out.push(_t("The next pay run will replace this with the value from the connected system."));
        } else if (row.fills_from === "rule") {
            out.push(_t("The next pay run will work this value out with a formula and replace what you type."));
        }
        // The owner's ruling of 2026-08-29, stated honestly rather than as an
        // error: a change like this is normally a new contract, and here it
        // deliberately is not.
        if (row.requires_new_contract) {
            out.push(_t("A change like this usually starts a new contract. This one is saved onto the contract you are looking at."));
        }
        return out;
    }

    stageRemove(row) {
        if (!this.canWrite) { return; }
        if (this.isRemoved(row.id)) { return; }
        delete this.state.dirty.comps.edits[String(row.id)];
        this.state.dirty.comps.removes.push(Number(row.id));
        if (this.isEditing("comp", row.id)) { this.state.edit = null; }
        this.onChanged();
    }
    undoRemove(row) {
        const i = this.state.dirty.comps.removes.indexOf(Number(row.id));
        if (i >= 0) { this.state.dirty.comps.removes.splice(i, 1); }
        this.onChanged();
    }

    // ------------------------------------------------------- staged adds
    get addRows() { return this.state.dirty.comps.adds; }
    get addPickerRows() {
        return this.addable.map((a) => ({ id: a.template_id, label: a.name }));
    }
    openAdd(ev) {
        this._addAnchorEl = ev.currentTarget;
        this.state.edit = null;
        this.state.addOpen = true;
    }
    closeAdd() { this.state.addOpen = false; }
    pickAdd(templateId) {
        this.state.addOpen = false;
        if (!templateId) { return; }
        const source = this.addable.find((a) => a.template_id === templateId);
        if (!source) { return; }
        if (this.state.dirty.comps.adds.some((a) => a.template_id === templateId)) { return; }
        this.state.dirty.comps.adds.push({
            template_id: source.template_id,
            code: source.code,
            name: source.name,
            value_type: source.value_type || "amount",
            amount: source.default || 0,
            text_value: "",
            label: this._stageLabel({ kind: "money" }, source.default || 0),
        });
        this.onChanged();
    }
    addKey(index) { return "add:" + index; }
    addEntry(add) {
        return {
            name: "add" + add.template_id, label: add.name,
            kind: add.value_type === "text" ? "text" : "money",
            value: add.value_type === "text" ? add.text_value : add.amount,
            required: false, writable: true,
        };
    }
    addValue(add) { return add.value_type === "text" ? add.text_value : add.amount; }
    startAdd(index, ev) {
        this._anchorEl = ev.currentTarget;
        this.state.addOpen = false;
        this.state.edit = { scope: "add", key: index };
    }
    commitAdd(index, value) {
        const add = this.state.dirty.comps.adds[index];
        if (!add) { this.state.edit = null; return; }
        if (add.value_type === "text") {
            add.text_value = String(value === false ? "" : value);
            add.label = add.text_value || _t("Empty");
        } else {
            add.amount = value;
            add.label = this._stageLabel({ kind: "money" }, value);
        }
        this.state.edit = null;
        this.onChanged();
    }
    dropAdd(index) {
        this.state.dirty.comps.adds.splice(index, 1);
        this.state.edit = null;
        this.onChanged();
    }
    addClass(add) { return { refused: Boolean(this.refusalFor("comp", add.template_id)) }; }

    // =====================================================================
    //  CD-3 — refusals, previewed while typing
    // =====================================================================
    refusalFor(scope, key) { return this.state.refusals[scope + ":" + key] || ""; }
    hasRefusal(scope, key) { return Boolean(this.refusalFor(scope, key)); }

    /** Every client-side judgement, keyed the way the server keys its own. */
    _clientRefusals() {
        const out = {};
        for (const [name, staged] of Object.entries(this.state.dirty.terms)) {
            const entry = this.termEntry(name);
            if (!entry) { continue; }
            const why = this._clientRefusal(entry, staged.value);
            if (why) { out["term:" + name] = why; }
        }
        return out;
    }

    onChanged() {
        clearTimeout(this._previewTimer);
        this._previewTimer = setTimeout(() => this.runPreview(), PREVIEW_MS);
    }

    /** What the save would send. A key the client already knows is wrong is
     *  never sent: the server would refuse it anyway, and sending it hides a
     *  client bug behind a server sentence (rail 2). */
    termsPayload() {
        const bad = this._clientRefusals();
        const out = {};
        for (const [name, staged] of Object.entries(this.state.dirty.terms)) {
            if (bad["term:" + name]) { continue; }
            out[name] = staged.value;
        }
        return out;
    }
    compsPayload() {
        const c = this.state.dirty.comps;
        const edits = {};
        for (const [id, staged] of Object.entries(c.edits)) {
            edits[id] = staged.isText
                ? { text_value: staged.value } : { amount: staged.value };
        }
        const adds = c.adds.map((a) => (a.value_type === "text"
            ? { template_id: a.template_id, text_value: a.text_value }
            : { template_id: a.template_id, amount: a.amount }));
        return { edits, adds, removes: c.removes.slice() };
    }

    async runPreview() {
        const client = this._clientRefusals();
        if (this.dirtyCount === 0) {
            this.state.refusals = {};
            this.state.accept = 0;
            return;
        }
        let data = null;
        try {
            data = await this.orm.call(MODEL, "preview_contract_360", [], {
                contract_id: Number(this.props.contractId),
                terms: this.termsPayload(),
                components: this.compsPayload(),
            });
        } catch (e) {
            // A preview that cannot reach the server is not a refusal; the Save
            // button stays honest and the person finds out on save.
            this.state.refusals = client;
            return;
        }
        const map = Object.assign({}, client);
        for (const r of (data.refusals || [])) {
            map[(r.scope === "term" ? "term" : "comp") + ":" + r.key] = r.why;
        }
        this.state.refusals = map;
        this.state.accept = data.accept || 0;
    }

    get refusalCount() { return Object.keys(this.state.refusals).length; }

    /**
     * "1 change", never "1 changes".
     *
     * Both sentences are written out rather than interpolated into one,
     * because a count is the thing a person reads twice before pressing Save
     * (`records_desk.js:388`).
     */
    get saveLabel() {
        const bad = this.refusalCount;
        if (bad && this.state.accept === 0) {
            return bad === 1 ? _t("1 change needs a look")
                : _t("%s changes need a look", grouped(bad));
        }
        if (bad) {
            return _t("Save %(ok)s · leave %(bad)s", {
                ok: grouped(Math.max(this.state.accept, 0)), bad: grouped(bad),
            });
        }
        const n = this.dirtyCount;
        return n === 1 ? _t("Save 1 change") : _t("Save %s changes", grouped(n));
    }
    get discardLabel() { return _t("Discard"); }
    /**
     * Enabled while there is at least one change the server said it would
     * take. Pressing Save with only refusals left would spend a round trip to
     * be told "nothing was saved", which is a dead end dressed as a button.
     */
    get canSave() {
        if (this.dirtyCount === 0 || this.state.saving) { return false; }
        return !(this.refusalCount > 0 && this.state.accept === 0);
    }
    get saveDisabled() { return !this.canSave; }
    // The footer holds BOTH rows and swaps which one is on, so the panel never
    // changes height when the first change is staged.
    get saveBarClass() { return { on: this.isDirty }; }
    /** A bar nobody can press is a bar nobody should be read either. */
    get saveBarHidden() { return this.isDirty ? undefined : "true"; }
    get restClass() { return { off: this.isDirty }; }

    discard() {
        this.state.dirty = { terms: {}, comps: { edits: {}, adds: [], removes: [] } };
        this.state.refusals = {};
        this.state.accept = 0;
        this.state.edit = null;
        clearTimeout(this._previewTimer);
    }

    // =====================================================================
    //  CD-3 — saving
    // =====================================================================
    /**
     * ONE call carries the whole dirty set.
     *
     * The Save bar is the only way anything is written from this drawer, so
     * there is never a second edit in flight to clobber — the question CD-2
     * left open is answered by the shape, not by a lock.
     */
    async save() {
        if (!this.canWrite || this.state.saving || this.dirtyCount === 0) { return; }
        this.state.edit = null;
        this.state.saving = true;
        let result = null;
        try {
            result = await this.orm.call(MODEL, "save_contract_360", [], {
                contract_id: Number(this.props.contractId),
                terms: this.termsPayload(),
                components: this.compsPayload(),
            });
        } catch (e) {
            // Sticky, and it says what did NOT happen: the difference between
            // "try again" and "check what got through first".
            this.notif.add(
                _t("Nothing was saved — the change could not be sent. %s", this._err(e)),
                { type: "danger", sticky: true });
            this.state.saving = false;
            return;
        }
        this.state.saving = false;

        const refusals = result.refusals || [];
        if (result.detail) { this.state.d = result.detail; }

        if (result.ok === false && !refusals.length) {
            this.notif.add(result.msg || _t("Nothing was saved."), { type: "warning" });
            return;
        }

        // The house contract: a mutate hands back everything, and the refused
        // keys STAY staged with their sentences so the person can fix them.
        const badTerms = new Set();
        const badComps = new Set();
        for (const r of refusals) {
            if (r.scope === "term") { badTerms.add(String(r.key)); }
            else { badComps.add(String(r.key)); }
        }
        const client = this._clientRefusals();
        for (const key of Object.keys(client)) { badTerms.add(key.slice(5)); }

        for (const name of Object.keys(this.state.dirty.terms)) {
            if (!badTerms.has(name)) { delete this.state.dirty.terms[name]; }
        }
        for (const id of Object.keys(this.state.dirty.comps.edits)) {
            if (!badComps.has(String(id))) { delete this.state.dirty.comps.edits[id]; }
        }
        this.state.dirty.comps.adds = this.state.dirty.comps.adds.filter(
            (a) => badComps.has(String(a.template_id)));
        this.state.dirty.comps.removes = this.state.dirty.comps.removes.filter(
            (id) => badComps.has(String(id)));

        const map = Object.assign({}, client);
        for (const r of refusals) {
            map[(r.scope === "term" ? "term" : "comp") + ":" + r.key] = r.why;
        }
        this.state.refusals = map;
        this.state.accept = 0;

        this.notif.add(result.msg || _t("Saved."),
                       { type: refusals.length ? "warning" : "success" });
        if (refusals.length) { this.showFirstRefusal(refusals[0]); }
    }

    /** A refusal the person cannot see is a screen that lies about saving. */
    showFirstRefusal(refusal) {
        const scope = refusal.scope === "term" ? "term" : "comp";
        if (scope === "term" && this.state.tab !== "terms") { this.setTab("terms"); }
        if (scope === "comp" && this.state.tab !== "components") { this.setTab("components"); }
        const selector = '[data-cdkey="' + scope + ":" + refusal.key + '"]';
        setTimeout(() => {
            const el = document.querySelector(selector);
            if (el && el.scrollIntoView) {
                el.scrollIntoView({ block: "center", behavior: "smooth" });
            }
        }, 60);
    }

    // =====================================================================
    //  CD-3 §2.7 — the lifecycle actions, no longer a dead end
    // =====================================================================
    actClass(act) {
        return { primary: act.kind === "primary", danger: act.kind === "danger",
                 ghost: act.kind !== "primary" && act.kind !== "danger" };
    }
    actRuns(act) { return RUNNABLE.has(act.method); }
    actTitle(act) {
        return this.actRuns(act) ? "" : _t("Opens the full contract screen, where this happens");
    }
    get lockedLine() {
        return _t("You can see this contract but not change it. An HR manager can.");
    }

    runAction(act) {
        if (!this.actRuns(act)) { this.openFullScreen(); return; }
        if (!this.canWrite || this.state.busy) { return; }
        if (this.dirtyCount > 0) {
            this.notif.add(_t("Save or discard your changes first."), { type: "warning" });
            return;
        }
        if (act.method === "set_running") { this.doAction(act.method); return; }
        const who = this.header.employee || _t("this person");
        const body = act.method === "terminate"
            ? _t("Terminate %s's contract? It will be marked as ended today and will stop feeding pay runs.", who)
            : _t("Cancel %s's contract? It will be marked as cancelled and will stop feeding pay runs.", who);
        this.state.asking = true;
        this.dialog.add(ConfirmationDialog, {
            title: act.method === "terminate" ? _t("End this contract") : _t("Cancel this contract"),
            body,
            confirmLabel: act.method === "terminate" ? _t("Terminate") : _t("Cancel it"),
            cancelLabel: _t("Keep it running"),
            confirm: () => { this.state.asking = false; this.doAction(act.method); },
            cancel: () => { this.state.asking = false; },
        }, { onClose: () => { this.state.asking = false; } });
    }

    async doAction(method) {
        this.state.busy = true;
        let outcome = null;
        try {
            outcome = await this.orm.call(MODEL, "run_contract_action", [], {
                contract_id: Number(this.props.contractId), method,
            });
        } catch (e) {
            this.state.busy = false;
            this.notif.add(_t("Nothing changed — that step could not be taken. %s", this._err(e)),
                           { type: "danger", sticky: true });
            return;
        }
        if (outcome && outcome.error) {
            this.state.busy = false;
            this.notif.add(String(outcome.error), { type: "danger", sticky: true });
            return;
        }
        // The drawer reads ONE payload, so the fresh truth comes from the same
        // place it always does rather than from the action's own reply.
        await this.load();
        this.state.busy = false;
        this.notif.add(
            method === "set_running" ? _t("This contract is now running.")
                : method === "terminate" ? _t("This contract has been ended.")
                    : _t("This contract has been cancelled."),
            { type: "success" });
    }

    // --------------------------------------------------------------- history
    // Month separators, cloned from the employee drawer's `timelineRows()`.
    historyRows() {
        const out = [];
        let lastMonth = null;
        for (const row of (this.history.rows || [])) {
            const m = (row.when || "").slice(0, 7);
            if (m && m !== lastMonth) {
                out.push({ sep: true, key: "sep-" + m + "-" + out.length, label: this._monthLabel(m) });
                lastMonth = m;
            }
            out.push(Object.assign({ sep: false, key: "it-" + out.length }, row));
        }
        return out;
    }
    _monthLabel(m) {
        const parts = m.split("-");
        return (MONTHS[parseInt(parts[1], 10)] || "") + " " + parts[0];
    }
    hasDelta(row) { return Boolean(row.from || row.to); }
    historyCountLabel() {
        return "Showing " + (this.history.shown || 0) + " of " + (this.history.total || 0);
    }
}

registry.category("pb_contracts_drawer").add("contract_360", Contract360Drawer);
