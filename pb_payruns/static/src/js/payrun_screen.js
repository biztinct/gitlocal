/** @odoo-module **/
/**
 * THE PAY RUN SCREEN (PRS P2, docs/handovers/payrunscreen/PRS_P2_HANDOVER.md).
 *
 * One view widget, `pb_payrun_screen`, sits first in the native pay run form
 * (`hr.payslip.run`) and draws the approved mock-up
 * (docs/design/payrun-screen-prototype.html) from ONE server payload,
 * `pb.payruns.get_run_screen`. Same URL, same record, same breadcrumbs.
 *
 * How it stays a good citizen of the form:
 *   - every button goes through the form's own `env.onClickViewButton`, so
 *     the record is saved first and reloaded after, exactly like a native
 *     header button (Odoo 19 view_button_hook.js);
 *   - the payload is reloaded whenever the form record is reloaded or saved
 *     (its identity, write_date or state change), so a date edited in Run
 *     settings re-runs the checks;
 *   - the old pieces of the form are hidden by CSS, never deleted
 *     (`pb-prs-legacy`), and More › "Show the classic layout" brings them all
 *     back for this browser tab (sessionStorage only — a tab toggle).
 *
 * Loads in two steps (item 16): `parts: 'main'` first, then — when the run
 * is a draft with payslips — `parts: 'route'`, which fills who signs it off.
 * The rest of the screen never waits for the approval engine.
 *
 * A second, tiny widget, `pb_payrun_history`, draws "What happened" beside
 * the native Run settings group from the same payload (shared store below).
 */
import { Component, useState, useRef, useEffect, onWillStart, onMounted,
         onWillUnmount, reactive, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { sprintf } from "@web/core/utils/strings";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ic } from "@pb_import_kit/js/import_icons";

const PAGE = 100;
const CLASSIC_KEY = "pb_prs_classic";
const MATRIX_ACTION = "pb_approval_config.action_pb_approval_matrix";

// One payload per run, shared by the screen and its history widget.
export const PRS_STORE = reactive({});

// Icons are memoised: `t-out` of a NEW markup() re-inserts the DOM on every
// render (memory: owl-markup-flicker), and the people table re-renders on
// every keystroke in the search box.
const ICONS = new Map();
function icon(name, size = 16) {
    const key = `${name}|${size}`;
    if (!ICONS.has(key)) {
        ICONS.set(key, ic(name, size));
    }
    return ICONS.get(key);
}

function readClassic() {
    try {
        return window.sessionStorage.getItem(CLASSIC_KEY) === "1";
    } catch {
        return false;
    }
}
function writeClassic(on) {
    try {
        if (on) {
            window.sessionStorage.setItem(CLASSIC_KEY, "1");
        } else {
            window.sessionStorage.removeItem(CLASSIC_KEY);
        }
    } catch {
        // a tab toggle that cannot be remembered still works for this view
    }
}

function typingIn(el) {
    if (!el) {
        return false;
    }
    const tag = (el.tagName || "").toUpperCase();
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

function dialogOpen() {
    return Boolean(document.querySelector(".o_dialog, .modal.show"));
}

const FLAG_ICON = { ok: "check", rose: "triangleAlert", amber: "triangleAlert",
                    p: "trendingUp", muted: "ban" };
const FLAG_ORDER = { rose: 0, amber: 1, p: 2, ok: 3, muted: 4 };
const DELIVERY_ICON = { approved: "check", bank_file: "landmark", paid: "banknote",
                        sent: "mail", journals: "bookOpen" };
const LOOK_KEYS = ["atlas", "changes"];
const CHANGE_KEYS = ["remake", "recalc", "split", "email"];

export class PbPayrunScreen extends Component {
    static template = "pb_payruns.PayrunScreen";
    static props = { ...standardWidgetProps };

    setup() {
        // Silent: the screen draws its own skeletons, so the app-wide loading
        // cover must not sit on top of them while the payload loads.
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.root = useRef("root");
        this.search = useRef("search");
        this.icon = icon;
        this.state = useState({
            loading: true, error: null, data: null,
            routeLoading: false, routeError: null,
            q: "", team: null, view: "all", sort: "net", dir: -1,
            sel: {}, anchor: null, panel: null, menu: null, limit: PAGE,
            classic: readClassic(), statement: {}, busy: false,
        });
        this.seq = 0;
        this.loadedKey = null;
        this.routePromise = null;

        onWillStart(() => this.load());
        onMounted(() => this.applyClassic());
        onWillUnmount(() => {
            document.body.classList.remove("pb-prs-classic");
            const id = this.resId;
            if (id && PRS_STORE[id]) {
                delete PRS_STORE[id];
            }
        });
        // The form reloads its record after a button, a save or a wizard
        // closing. Reading the key in render subscribes this component to
        // those fields; the effect then reloads the payload once per change.
        useEffect(
            (key) => {
                if (this.loadedKey !== null && key !== this.loadedKey) {
                    this.load();
                }
            },
            () => [this.recordKey]
        );
        // Capture phase: another window-level listener in the web client
        // swallows Escape before a bubbling listener sees it (PRS-G25).
        useExternalListener(window, "keydown", this.onKeydown.bind(this), { capture: true });
        useExternalListener(window, "click", this.onWindowClick.bind(this), true);
    }

    // ------------------------------------------------------------ loading
    get resId() {
        return this.props.record.resId;
    }

    get recordKey() {
        const rec = this.props.record;
        const d = rec.data || {};
        const wd = d.write_date ? String(d.write_date) : "";
        return `${rec.resId || 0}|${wd}|${d.state || ""}|${rec.id}`;
    }

    async load() {
        const id = this.resId;
        this.loadedKey = this.recordKey;
        if (!id) {
            this.state.loading = false;
            this.state.data = null;
            return;
        }
        const seq = ++this.seq;
        if (!this.state.data) {
            this.state.loading = true;
        }
        this.state.error = null;
        let data;
        try {
            data = await this.orm.silent.call("pb.payruns", "get_run_screen", [id],
                                       { parts: "main" });
        } catch (e) {
            if (seq !== this.seq) {
                return;
            }
            this.state.loading = false;
            this.state.error = this.errorText(e);
            return;
        }
        if (seq !== this.seq) {
            return;
        }
        this.state.data = data;
        this.state.loading = false;
        PRS_STORE[id] = { data };
        this.pruneSelection();
        if (data.route_pending) {
            this.routePromise = this.loadRoute(id, seq);
        } else {
            this.routePromise = null;
        }
    }

    async loadRoute(id, seq) {
        this.state.routeLoading = true;
        this.state.routeError = null;
        try {
            const part = await this.orm.silent.call("pb.payruns", "get_run_screen", [id],
                                             { parts: "route" });
            if (seq !== this.seq || !this.state.data) {
                return;
            }
            Object.assign(this.state.data, part);
        } catch (e) {
            if (seq === this.seq) {
                this.state.routeError = this.errorText(e);
            }
        } finally {
            if (seq === this.seq) {
                this.state.routeLoading = false;
            }
        }
    }

    errorText(e) {
        const msg = e && e.data && e.data.message;
        if (msg && e.data.name && e.data.name.includes("UserError")) {
            return msg;
        }
        if (e && e.data && e.data.name && e.data.name.includes("AccessError")) {
            return _t("You are not allowed to open this pay run.");
        }
        return _t("The server did not answer in time, or something went wrong on its side.");
    }

    retry() {
        this.state.data = null;
        this.load();
    }

    pruneSelection() {
        const ids = new Set(this.allRows.map((r) => r.slip_id));
        for (const k of Object.keys(this.state.sel)) {
            if (!ids.has(Number(k))) {
                delete this.state.sel[k];
            }
        }
        if (this.state.panel && !ids.has(this.state.panel)) {
            this.state.panel = null;
        }
    }

    // ------------------------------------------------------------ getters
    get d() {
        return this.state.data;
    }
    get header() {
        return this.d.header;
    }
    get statusKey() {
        return this.header.status.key;
    }
    get state_() {
        return (this.d.run && this.d.run.state) || "draft";
    }
    get isEmpty() {
        return !this.d.people.total && this.state_ !== "cancel";
    }
    get isRejected() {
        return this.state_ === "cancel";
    }
    get primary() {
        const p = this.d.primary;
        return p && p.kind !== "none" && p.label ? p : null;
    }
    get primaryIcon() {
        return { make: "plus", submit: "send", resubmit: "send", decide: "userCheck",
                 approvals: "userCheck", paydeliver: "banknote" }[this.d.primary.kind] || "arrowRight";
    }
    get pillTone() {
        return { draft: "slate", sent_back: "amber", pending: "p", done: "green",
                 rejected: "rose" }[this.statusKey] || "slate";
    }
    get allRows() {
        return (this.d && this.d.people && this.d.people.rows) || [];
    }

    money(amount) {
        const h = this.header;
        const dec = Math.max(0, h.decimals || 0);
        const v = Number(amount || 0);
        const text = Math.abs(v).toLocaleString("en-US", {
            minimumFractionDigits: dec, maximumFractionDigits: dec });
        return `${v < 0 ? "−" : ""}${h.symbol}${text}`;
    }
    moneyBare(amount) {
        const h = this.header;
        const dec = Math.max(0, h.decimals || 0);
        return Math.abs(Number(amount || 0)).toLocaleString("en-US", {
            minimumFractionDigits: dec, maximumFractionDigits: dec });
    }
    short(amount) {
        const v = Math.abs(Number(amount || 0));
        const sym = this.header.symbol;
        const trim = (t) => (t.includes(".") ? t.replace(/0+$/, "").replace(/\.$/, "") : t);
        if (v >= 1e9) {
            return sprintf(_t("%(amount)sbn"), { amount: sym + trim((v / 1e9).toFixed(2)) });
        }
        if (v >= 1e6) {
            return sprintf(_t("%(amount)sm"), { amount: sym + trim((v / 1e6).toFixed(1)) });
        }
        return this.money(v);
    }
    pct(part, whole) {
        if (!whole) {
            return 0;
        }
        return Math.max(0, Math.min(100, (part / whole) * 100));
    }

    /** The money sentence with the figures in bold, as in the mock-up. */
    get sentenceParts() {
        const text = this.d.money.sentence || "";
        const sym = (this.header.symbol || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const words = "(?:\\s(?:billion|million|tỷ|triệu))?";
        const re = new RegExp(`((?:^\\d+\\s\\S+)|−?${sym}[\\d.,]+${words})`, "g");
        const parts = [];
        let last = 0;
        for (const m of text.matchAll(re)) {
            if (m.index > last) {
                parts.push({ t: text.slice(last, m.index), b: false });
            }
            parts.push({ t: m[0], b: true });
            last = m.index + m[0].length;
        }
        if (last < text.length) {
            parts.push({ t: text.slice(last), b: false });
        }
        return parts;
    }

    get flow() {
        const m = this.d.money;
        const net = Math.max(0, m.net || 0);
        const ded = Math.max(0, m.deductions || 0);
        const emp = Math.max(0, m.employer_cost || 0);
        const whole = net + ded + emp;
        return {
            net: this.pct(net, whole), ded: this.pct(ded, whole), emp: this.pct(emp, whole),
            netOfCost: Math.round(this.pct(m.net || 0, m.total_cost || 0)),
        };
    }

    get compareTone() {
        const c = this.d.compare;
        if (!c || c.change_pct === null || c.change_pct === undefined) {
            return "";
        }
        return c.change_pct > 0 ? "up" : c.change_pct < 0 ? "down" : "";
    }

    // --------------------------------------------------------- checks/route
    get checkItems() {
        return (this.d.checks && this.d.checks.items) || [];
    }
    tickIcon(item) {
        return { ok: "check", bad: "triangleAlert", amber: "triangleAlert",
                 pending: "loader" }[item.tone] || "check";
    }
    get verdictIcon() {
        return { ok: "shieldCheck", done: "shieldCheck", wait: "shieldCheck",
                 bad: "triangleAlert" }[this.d.checks.verdict] || "shieldCheck";
    }
    get showRoute() {
        return !this.isEmpty && !this.isRejected && this.state_ !== "done";
    }
    get routeAmber() {
        const r = this.d.route;
        return r.mode === "preview" && !r.error && !r.seats.length;
    }
    get routeSeats() {
        return this.d.route.seats || [];
    }
    get deliverySteps() {
        return (this.d.delivery && this.d.delivery.steps) || [];
    }
    get deliveryLeft() {
        const left = this.d.delivery.left || 0;
        if (!left) {
            return _t("All done");
        }
        return left === 1 ? _t("1 step left")
            : sprintf(_t("%(n)s steps left"), { n: left });
    }
    deliveryIcon(step) {
        return DELIVERY_ICON[step.key] || "circle";
    }

    // -------------------------------------------------------------- people
    get teams() {
        return this.d.people.teams || [];
    }
    get maxTeamNet() {
        return Math.max(1, ...this.teams.map((t) => t.net || 0));
    }
    get changedLabel() {
        const c = this.d.compare;
        return c && c.label
            ? sprintf(_t("Changed since %(month)s"), { month: c.label.split(" ")[0] })
            : _t("Changed");
    }
    get filteredRows() {
        let rows = this.allRows.slice();
        const st = this.state;
        if (st.team) {
            rows = rows.filter((r) => (r.team || this.noTeam) === st.team);
        }
        if (st.view === "flagged") {
            rows = rows.filter((r) => r.flag.kind === "rose" || r.flag.kind === "amber");
        } else if (st.view === "changed") {
            rows = rows.filter((r) => r.flag.kind === "p");
        }
        const q = st.q.trim().toLowerCase();
        if (q) {
            rows = rows.filter((r) =>
                `${r.name} ${r.team} ${r.job}`.toLowerCase().includes(q));
        }
        const k = st.sort;
        const dir = st.dir;
        rows.sort((a, b) => {
            let c;
            if (k === "name") {
                c = a.name.localeCompare(b.name);
            } else if (k === "flag") {
                c = (FLAG_ORDER[a.flag.kind] ?? 9) - (FLAG_ORDER[b.flag.kind] ?? 9);
            } else {
                c = (a[k] || 0) - (b[k] || 0);
            }
            return c * dir || a.name.localeCompare(b.name);
        });
        return rows;
    }
    get shownRows() {
        return this.filteredRows.slice(0, this.state.limit);
    }
    get moreLeft() {
        return Math.max(0, this.filteredRows.length - this.state.limit);
    }
    get showMoreLabel() {
        const n = Math.min(PAGE, this.moreLeft);
        return sprintf(_t("Show %(n)s more"), { n });
    }
    get shownNet() {
        return this.filteredRows.reduce((a, r) => a + (r.net || 0), 0);
    }
    get maxNet() {
        return Math.max(1, ...this.allRows.map((r) => r.net || 0));
    }
    get noTeam() {
        return _t("No team");
    }
    get shownLabel() {
        const n = this.filteredRows.length;
        const all = this.d.people.total;
        let text = sprintf(_t("%(n)s of %(all)s shown"), { n, all });
        if (this.state.team) {
            text += ` · ${this.state.team}`;
        }
        return text;
    }
    get nobodyLabel() {
        return this.state.q
            ? sprintf(_t("Nobody matches “%(q)s”."), { q: this.state.q })
            : _t("Nobody here.");
    }
    get anyBulk() {
        const b = this.d.bulk || {};
        return Boolean(b.recalc || b.pdf || b.delete);
    }
    get selIds() {
        return Object.keys(this.state.sel).filter((k) => this.state.sel[k]).map(Number);
    }
    get allShownSelected() {
        const rows = this.shownRows;
        return rows.length > 0 && rows.every((r) => this.state.sel[r.slip_id]);
    }
    flagIcon(row) {
        return FLAG_ICON[row.flag.kind] || "check";
    }
    netBar(row) {
        return Math.max(8, ((row.net || 0) / this.maxNet) * 90);
    }

    setTeam(name) {
        this.state.team = name;
        this.state.limit = PAGE;
    }
    setView(v) {
        this.state.view = v;
        this.state.limit = PAGE;
    }
    onSearch(ev) {
        this.state.q = ev.target.value;
        this.state.limit = PAGE;
    }
    clearFilters() {
        this.state.q = "";
        this.state.team = null;
        this.state.view = "all";
        this.state.limit = PAGE;
    }
    sortBy(key) {
        if (this.state.sort === key) {
            this.state.dir *= -1;
        } else {
            this.state.sort = key;
            this.state.dir = key === "name" ? 1 : -1;
        }
    }
    sortIcon(key) {
        return this.state.dir < 0 ? "chevronDown" : "chevronUp";
    }
    showMore() {
        this.state.limit += PAGE;
    }

    toggleRow(row, ev) {
        ev.stopPropagation();
        const rows = this.shownRows;
        const id = row.slip_id;
        const on = !this.state.sel[id];
        if (ev.shiftKey && this.state.anchor) {
            const a = rows.findIndex((r) => r.slip_id === this.state.anchor);
            const b = rows.findIndex((r) => r.slip_id === id);
            if (a >= 0 && b >= 0) {
                const [lo, hi] = a < b ? [a, b] : [b, a];
                for (let i = lo; i <= hi; i++) {
                    this.state.sel[rows[i].slip_id] = on;
                }
                this.state.anchor = id;
                return;
            }
        }
        this.state.sel[id] = on;
        this.state.anchor = id;
    }
    toggleAll() {
        const on = !this.allShownSelected;
        for (const r of this.shownRows) {
            this.state.sel[r.slip_id] = on;
        }
    }
    clearSelection() {
        this.state.sel = {};
        this.state.anchor = null;
    }

    // ---------------------------------------------------------- quick look
    get panelRow() {
        return this.state.panel ? this.allRows.find((r) => r.slip_id === this.state.panel) : null;
    }
    get panelIndex() {
        return this.filteredRows.findIndex((r) => r.slip_id === this.state.panel);
    }
    get panelPos() {
        return sprintf(_t("%(i)s of %(n)s"), { i: this.panelIndex + 1, n: this.filteredRows.length });
    }
    get panelStatement() {
        const s = this.state.statement[this.state.panel];
        return s && s !== "loading" && s !== "none" ? s : null;
    }
    get panelLoading() {
        return this.state.statement[this.state.panel] === "loading";
    }
    get atlasItem() {
        return (this.d.actions.more || []).find((a) => a.key === "atlas") || null;
    }
    openPanel(row) {
        this.state.panel = row.slip_id;
        this.state.menu = null;
        this.loadStatement(row.slip_id);
    }
    closePanel() {
        this.state.panel = null;
    }
    movePanel(step) {
        const rows = this.filteredRows;
        const i = rows.findIndex((r) => r.slip_id === this.state.panel);
        const next = rows[Math.min(rows.length - 1, Math.max(0, i + step))];
        if (next) {
            this.openPanel(next);
            const tr = this.root.el && this.root.el.querySelector(`tr[data-slip="${next.slip_id}"]`);
            if (tr && tr.scrollIntoView) {
                tr.scrollIntoView({ block: "nearest" });
            }
        }
    }
    async loadStatement(slipId) {
        if (!this.d.statement_available || this.state.statement[slipId]) {
            return;
        }
        this.state.statement[slipId] = "loading";
        try {
            const [rec] = await this.orm.silent.read("hr.payslip", [slipId], ["pb_statement_json"]);
            const parsed = rec && rec.pb_statement_json ? JSON.parse(rec.pb_statement_json) : null;
            this.state.statement[slipId] = parsed || "none";
        } catch {
            this.state.statement[slipId] = "none";
        }
    }
    /** A statement line marked "already inside another line's total" is
     *  drawn as a sub-line only when its section also has ordinary lines;
     *  a scheme that marks every line that way would otherwise dim them all. */
    lineClass(lines, ln) {
        return ln.detail && lines.some((x) => !x.detail) ? "detail" : "";
    }
    stmtMoney(amount, negative = false) {
        const v = Math.abs(Number(amount || 0));
        return `${negative ? "−" : ""}${this.money(v)}`;
    }
    openSlip(slipId) {
        this.state.panel = null;
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.payslip", res_id: slipId,
            views: [[false, "form"]], target: "current",
        });
    }

    // ------------------------------------------------------------- menus
    get downloads() {
        return this.d.actions.downloads || [];
    }
    get moreLook() {
        return (this.d.actions.more || []).filter((a) => LOOK_KEYS.includes(a.key));
    }
    get moreChange() {
        return (this.d.actions.more || []).filter((a) => CHANGE_KEYS.includes(a.key));
    }
    get moreDanger() {
        return (this.d.actions.more || []).filter(
            (a) => !LOOK_KEYS.includes(a.key) && !CHANGE_KEYS.includes(a.key));
    }
    menuIcon(item) {
        return { xlsx: "fileSpreadsheet", report: "chartColumn", pdf: "printer",
                 atlas: "gitBranch", changes: "arrowLeftRight", remake: "plus",
                 recalc: "refresh", split: "gitMerge", cleardraft: "trash",
                 reject: "ban", redraft: "undo", email: "mail" }[item.key] || "arrowRight";
    }
    toggleMenu(name, ev) {
        ev.stopPropagation();
        this.state.menu = this.state.menu === name ? null : name;
    }
    onWindowClick(ev) {
        if (this.state.menu && !(ev.target.closest && ev.target.closest(".pb-prs-menu, .pb-prs-menu-btn"))) {
            this.state.menu = null;
        }
    }

    // ----------------------------------------------------------- actions
    clickParams(item) {
        if (item.method) {
            return { type: "object", name: item.method };
        }
        if (item.action) {
            return { type: "action", name: item.action, context: item.context || {} };
        }
        return null;
    }

    async runButton(clickParams) {
        const record = this.props.record;
        if (!clickParams) {
            return;
        }
        const keyBefore = this.loadedKey;
        if (this.env.onClickViewButton) {
            await this.env.onClickViewButton({
                clickParams,
                getResParams: () => ({
                    context: record.context, evalContext: record.evalContext,
                    resModel: record.resModel, resId: record.resId, resIds: record.resIds,
                }),
            });
        } else {
            // Not inside a form controller (should not happen): run it plainly.
            const saved = record.isDirty ? await record.save() : true;
            if (saved === false) {
                return;
            }
            await this.action.doActionButton({
                ...clickParams, resModel: record.resModel, resId: record.resId,
                resIds: [record.resId], context: record.context,
                onClose: () => record.model.load(),
            });
        }
        // The form normally reloads its record after a button, and the
        // record-key effect then reloads this screen. Only when that did not
        // happen (a download, a notification) is the screen reloaded here.
        setTimeout(() => {
            if (this.loadedKey === keyBefore && this.root.el && this.root.el.isConnected) {
                this.load();
            }
        }, 400);
    }

    confirmThen(confirm, fn) {
        if (!confirm) {
            return fn();
        }
        this.dialog.add(ConfirmationDialog, {
            title: confirm.title,
            body: confirm.body,
            confirmLabel: confirm.ok,
            cancelLabel: confirm.cancel,
            confirmClass: confirm.danger ? "btn-danger" : "btn-primary",
            confirm: () => fn(),
            cancel: () => {},
        });
    }

    runItem(item) {
        this.state.menu = null;
        this.confirmThen(item.confirm, () => this.runButton(this.clickParams(item)));
    }

    async pressPrimary() {
        if (!this.primary || this.state.busy) {
            return;
        }
        if (this.routePromise) {
            // The confirm names who it goes to: wait for the route part.
            this.state.busy = true;
            try {
                await this.routePromise;
            } finally {
                this.state.busy = false;
            }
        }
        const p = this.d.primary;
        if (!p || p.kind === "none") {
            return;
        }
        if (p.kind === "decide" || p.kind === "approvals") {
            if (p.action) {
                this.action.doAction(p.action);
            }
            return;
        }
        this.confirmThen(p.confirm, () => this.runButton(this.clickParams(p)));
    }

    checkDoor(item) {
        const door = item.door;
        if (!door) {
            return;
        }
        if (door.kind === "flagged") {
            this.showFlagged();
        } else if (door.kind === "atlas") {
            const atlas = this.atlasItem;
            this.runButton({ type: "object", name: (atlas && atlas.method) || "action_open_source_atlas" });
        } else if (door.kind === "approvals_setup") {
            this.action.doAction(MATRIX_ACTION);
        } else if (door.kind === "board") {
            this.boardDoor(door);
        }
    }

    /** A door carried by one of the board's own check lines (`_run_checks`
     *  `next`), opened the way the board opens it. 'run' means "this run":
     *  we are on it, so it goes to the people who need a look. */
    async boardDoor(door) {
        if (door.key === "run") {
            this.showFlagged();
            return;
        }
        if (door.key === "close") {
            try {
                await this.action.doAction("pb_mission.action_pb_workforce", {
                    additionalContext: { pb_shell_lens: "close" },
                });
            } catch {
                this.notification.add(_t("Workforce is not available on this server."),
                                      { type: "warning" });
            }
            return;
        }
        if (door.action) {
            this.action.doAction(door.action, { additionalContext: door.context || {} });
        }
    }

    showFlagged() {
        this.state.view = "flagged";
        this.state.team = null;
        this.state.q = "";
        const el = this.root.el && this.root.el.querySelector(".pb-prs-people");
        if (el && el.scrollIntoView) {
            el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    deliveryClick(step) {
        if (step.state === "now" && this.primary && this.d.primary.kind === "paydeliver") {
            this.pressPrimary();
        }
    }

    bulk(verb) {
        const ids = this.selIds;
        if (!ids.length) {
            return;
        }
        const go = () => this.runButton({
            type: "object", name: "action_pb_slips", args: JSON.stringify([verb, ids]),
        }).then(() => {
            if (verb !== "pdf") {
                this.clearSelection();
            }
        });
        if (verb === "delete") {
            const n = ids.length;
            this.confirmThen({
                title: n === 1 ? _t("Delete this draft payslip?")
                    : sprintf(_t("Delete %(n)s draft payslips?"), { n }),
                body: _t("Only the payslips you picked are deleted. The run stays, and you can make them again. Nothing approved is touched."),
                ok: _t("Delete payslips"), cancel: _t("Keep them"), danger: true,
            }, go);
        } else {
            go();
        }
    }
    get selCountLabel() {
        const n = this.selIds.length;
        return n === 1 ? _t("1 selected") : sprintf(_t("%(n)s selected"), { n });
    }

    // ------------------------------------------------------------ classic
    applyClassic() {
        document.body.classList.toggle("pb-prs-classic", this.state.classic);
    }
    toggleClassic() {
        this.state.menu = null;
        this.state.classic = !this.state.classic;
        writeClassic(this.state.classic);
        this.applyClassic();
    }

    // ----------------------------------------------------------- keyboard
    onKeydown(ev) {
        if (!this.root.el || !this.root.el.isConnected || !this.d) {
            return;
        }
        if (dialogOpen()) {
            return;
        }
        const typing = typingIn(document.activeElement);
        if (ev.key === "/" && !typing && !ev.metaKey && !ev.ctrlKey) {
            if (this.search.el) {
                ev.preventDefault();
                this.search.el.focus();
            }
            return;
        }
        if (ev.key === "Escape") {
            if (this.state.panel) {
                this.state.panel = null;
            } else if (this.state.menu) {
                this.state.menu = null;
            } else if (typing && document.activeElement === this.search.el) {
                this.search.el.blur();
            } else if (this.selIds.length) {
                this.clearSelection();
            } else {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            return;
        }
        if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
            if (this.primary) {
                ev.preventDefault();
                ev.stopPropagation();
                this.pressPrimary();
            }
            return;
        }
        if (this.state.panel && (ev.key === "ArrowDown" || ev.key === "ArrowUp") && !typing) {
            ev.preventDefault();
            this.movePanel(ev.key === "ArrowDown" ? 1 : -1);
        }
    }

    // ------------------------------------------------------------- words
    get t() {
        return {
            journeyAria: _t("Where this pay run is"),
        };
    }
    get emptyText() {
        const h = this.header;
        return h.scheme
            ? sprintf(_t("Press Make payslips and one is made for each person on the %(scheme)s scheme, for work dates %(dates)s. Nothing is sent to anyone."),
                      { scheme: h.scheme, dates: h.work_dates })
            : sprintf(_t("Press Make payslips and pick who is paid, for work dates %(dates)s. Nothing is sent to anyone."),
                      { dates: h.work_dates });
    }
    get peopleChip() {
        const n = this.header.people || 0;
        return n === 1 ? _t("1 person") : sprintf(_t("%(n)s people"), { n });
    }
    get paidInChip() {
        const h = this.header;
        return sprintf(_t("Paid in %(name)s (%(symbol)s)"), { name: h.currency_name, symbol: h.symbol });
    }
    get workDatesChip() {
        return sprintf(_t("Work dates %(dates)s"), { dates: this.header.work_dates });
    }
    get sentBackTitle() {
        const r = this.d.run;
        if (r.return_by && r.return_on) {
            return sprintf(_t("Sent back by %(who)s on %(when)s"), { who: r.return_by, when: r.return_on });
        }
        return r.return_by ? sprintf(_t("Sent back by %(who)s"), { who: r.return_by }) : _t("Sent back to be fixed");
    }
    get rejectedTitle() {
        const r = this.d.run;
        return r.reject_by ? sprintf(_t("Rejected by %(who)s"), { who: r.reject_by }) : _t("This pay run was rejected");
    }
    get netOfCostLabel() {
        return sprintf(_t("%(pct)s% of the total cost"), { pct: this.flow.netOfCost });
    }
    get totalCostSub() {
        return sprintf(_t("Gross pay %(gross)s + the company's share"),
                       { gross: this.money(this.d.money.gross) });
    }
    get warnBadge() {
        return sprintf(_t("%(n)s to check"), { n: this.d.primary.warn });
    }
    traceFromPanel() {
        const atlas = this.atlasItem;
        this.closePanel();
        if (atlas) {
            this.runItem(atlas);
        }
    }
    get flaggedCount() {
        return this.d.people.counts.flagged || 0;
    }
    get keyHint() {
        return /Mac|iPhone|iPad/.test(navigator.platform || "") ? "⌘" : "Ctrl";
    }
}

/** "What happened", beside Run settings, from the screen's own payload. */
export class PbPayrunHistory extends Component {
    static template = "pb_payruns.PayrunHistory";
    static props = { ...standardWidgetProps };

    setup() {
        this.store = useState(PRS_STORE);
        this.icon = icon;
    }
    get events() {
        const entry = this.store[this.props.record.resId];
        const run = entry && entry.data && entry.data.run;
        if (!run || !run.history) {
            return null;
        }
        // An event with no date is "now" only when it is the step a run
        // waiting for approval is waiting on; any other undated event (an
        // approval recorded without its day) just shows no date.
        const last = run.history.length - 1;
        return run.history.map((ev, i) => ({
            text: ev[0], when: ev[1] || "",
            wait: !ev[1] && run.state === "approval_pending" && i === last,
        }));
    }
}

registry.category("view_widgets").add("pb_payrun_screen", {
    component: PbPayrunScreen,
});
registry.category("view_widgets").add("pb_payrun_history", {
    component: PbPayrunHistory,
});
