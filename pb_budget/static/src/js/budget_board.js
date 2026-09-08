/** @odoo-module **/
/**
 * `pb_budget_board` — the Budget lens on the Insights mission.
 *
 * THE HERO IS THE HEAT VIEW, AND ITS IDEA IS ONE COMPARISON.
 *
 * "Marketing has spent 71% of its budget" is neither good news nor bad until you
 * know whether it is March or November. Every tile therefore carries TWO marks
 * on one bar: the fill is how much of the money is gone, and the notch is how
 * much of the YEAR is gone. A fill short of the notch is a function with money
 * in hand; a fill past it is one that will run out early. That is the whole
 * board, and it reads in about a second.
 *
 * COLOUR IS NEVER THE MESSAGE. Every tile carries its percentage and a word —
 * "Ahead of the year", "Running warm", "On pace", "Behind the year" — so the
 * board reads identically to somebody who cannot tell the amber from the rose.
 *
 * THE MOTION IS A CSS CUSTOM PROPERTY AND IT IS OPTIONAL. Tiles rise on a
 * stagger driven by `--bdg-i`, set per tile from the loop index; the whole
 * animation, the transform and the opacity all live inside a
 * `@media (prefers-reduced-motion: no-preference)` block in the stylesheet, so a
 * person who has asked their machine for less movement gets the finished board
 * on the first frame with nothing to recover from. No JavaScript decides that.
 *
 * A MONTH IS A SCOPE, NOT A BAR (TIDY rule 13, phase P3).
 *
 * The strip under the numbers is thirteen chips — "Whole year" and the twelve
 * months — and each month chip already answers, before anything is clicked,
 * whether that month ran over its budget: a two-tone micro bar and a signed
 * percentage. Click one and the WHOLE board becomes that month in one motion.
 * The tiles keep their places (they are sorted by the YEAR's spend on the
 * server, whatever the scope, and keyed by function id, so OWL moves nothing);
 * only the numbers, the words, the fills and the notch change, and the fill
 * has a width transition, so the board visibly re-scopes rather than blinking.
 * Escape and "Whole year" always come back; ← and → walk the strip.
 *
 * R1 — no `t-as` variable is named lt / gt / lte / gte / and / or / not / in.
 * R2 — every sentence is ONE expression; JavaScript has no implicit string
 * concatenation and a Python habit here kills the entire asset bundle.
 */
import { Component, useState, onWillStart, useExternalListener,
         useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbBudgetBoard extends Component {
    static template = "pb_budget.PbBudgetBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.stripRef = useRef("strip");

        this.state = useState({
            loaded: false,
            failed: "",
            board: null,
            view: "heat",                  // heat | table
            fy: 0,
            type: "manpower",
            currency: "report",
            month: "",                     // "" = the whole year, else YYYY-MM
            scoping: false,                // a month is being switched to
            stripFocus: "",                // the chip the keyboard is standing on
            open: 0,                       // the function whose drill is open
            drill: null,
            drillBusy: false,
            expanded: {},                  // table view: which rows show months

            uploading: false,
            upload: { file: "", name: "", plan: null, busy: false },

            spending: false,
            expense: { name: "", amount: "", budget_type: "hr_ops",
                       spend_date: "", department_id: 0, department: "",
                       supplier: "", note: "" },
            people: [],
            busy: false,
        });

        // THE DEEP LINK, READ ONCE. `pb_focus: "month:2026-03"` arrives on the
        // hub's action and the shell hands it to this lens because the lens
        // says `wantsArrival`. A month outside the year on screen is not an
        // error: the server answers with the whole year and the strip clears
        // itself, so a stale bookmark lands somewhere real.
        const arrival = this.props.arrival || {};
        const asked = String(arrival.focus || "");
        if (asked.startsWith("month:")) {
            this.state.month = asked.slice(6);
        }

        useExternalListener(window, "keydown", (ev) => this.onKey(ev),
                            { capture: true });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        try {
            const board = await this.orm.call("pb.budget", "get_board", [
                this.state.fy || null, this.state.type, this.state.currency,
                null, this.state.month || null,
            ]);
            this.state.board = board;
            this.state.fy = board.fy;
            this.state.type = board.budget_type;
            this.state.currency = board.currency.mode;
            // The server is the authority on what scope this board IS: it
            // resolves "current", and it refuses a month that is not one of
            // this year's twelve.
            this.state.month = board.scope.kind === "month"
                ? board.scope.key : "";
            this.state.failed = "";
        } catch (e) {
            // Reported, never swallowed into a decoration: a board that could
            // not be read says so, and never shows zeroes as though they were
            // the answer.
            this.state.board = null;
            this.state.failed = this._msg(
                e, _t("The budget board could not be read."));
        } finally {
            this.state.loaded = true;
        }
    }

    async reload() {
        this.state.loaded = false;
        this.state.open = 0;
        this.state.drill = null;
        await this.load();
    }

    get board() { return this.state.board || {}; }
    get kpis() { return (this.state.board && this.state.board.kpis) || {}; }
    get functions() {
        return (this.state.board && this.state.board.functions) || [];
    }
    get cur() {
        return (this.state.board && this.state.board.currency) || {};
    }

    // ============================================================ the month
    get scope() {
        return (this.state.board && this.state.board.scope)
            || { kind: "year", key: "", label: "", name: "", state: "current" };
    }

    get strip() { return (this.state.board && this.state.board.strip) || []; }

    get isMonth() { return this.scope.kind === "month"; }

    /**
     * The notch is WHERE THE CALENDAR IS, and a month that has not started has
     * no calendar inside it yet — so it carries no notch at all rather than one
     * pinned at zero, which reads as "nothing spent" and is a different claim.
     */
    get showNotch() {
        return !(this.isMonth && this.scope.state === "future");
    }

    /** Every caption on the board, in one place, so the year and the month
     *  cannot drift apart. ONE expression each (R2). */
    get caps() {
        if (!this.isMonth) {
            return {
                budget: _t("budget for the year"),
                spent: _t("spent so far"),
                left: _t("left"),
                ratio: _t("money gone, year gone"),
                hot: _t("functions running warm or worse"),
            };
        }
        const name = this.scope.name;
        return {
            budget: _t("budget for %s", name),
            spent: _t("spent in %s", name),
            left: _t("left in %s", name),
            ratio: _t("compared with the budget"),
            hot: _t("functions over budget in %s", name),
        };
    }

    /** The fifth number: warm-or-worse over a year, over budget in a month. */
    get hotCount() {
        return this.isMonth ? (this.kpis.over || 0) : (this.kpis.hot || 0);
    }

    /** What the notch on a tile means, in this scope. ONE expression (R2). */
    paceTitle(f) {
        if (!this.isMonth) {
            return _t("The year is %s gone", this.pct(f.pace));
        }
        if (this.scope.state === "past") {
            return _t("%s is finished", this.scope.name);
        }
        return _t("%s of %s has gone", this.pct(f.pace), this.scope.name);
    }

    /** The one line that says where you are. ONE expression (R2). */
    get scopeLine() {
        return _t("Every figure on this board is %s. Press Escape to go back to the whole year.", this.scope.label);
    }

    /** "+12%" / "−4%" — the minus is a real minus sign, not a hyphen. */
    signed(n) {
        const v = Math.round(Number(n) || 0);
        return v > 0 ? `+${v}%` : `${String(v).replace("-", "−")}%`;
    }

    /** "Left" is not good news when there is none of it. A green tick over a
     *  negative figure is the one thing on this board that could be misread at
     *  a glance, so the icon and its colour change with the sign. */
    get overspent() { return (Number(this.kpis.left) || 0) < 0; }

    /** The short form with its sign — the same true minus sign the percentage
     *  beside it uses, so one row does not mix two kinds of dash. */
    signedShort(n) {
        const v = Number(n) || 0;
        return v > 0 ? `+${this.short(v)}` : `${this.short(v)}`.replace("-", "−");
    }

    /** What goes in a "left" slot: the plain short form, and a TRUE minus sign
     *  when there is none left — so the tiles and the number above them do not
     *  print two different kinds of dash for the same fact. */
    leftText(value) {
        const v = Number(value) || 0;
        return v < 0 ? this.signedShort(v) : this.short(v);
    }

    /** Money with its sign, for a variance cell. */
    signedMoney(n) {
        const v = Math.round(Number(n) || 0);
        const body = `${Math.abs(v).toLocaleString()} ${this.cur.code || ""}`;
        return v > 0 ? `+${body}`.trim() : `−${body}`.trim();
    }

    /** A month cell of the expanded table, in the shape `varianceTone` reads. */
    cell(mo) {
        return { budget: mo.budget || 0, variance: (mo.spent || 0) - (mo.budget || 0) };
    }

    cellPct(mo) {
        return mo.budget ? ((mo.spent || 0) - mo.budget) / mo.budget * 100 : 0;
    }

    /** Over budget is rose, under is teal, close to it is green. */
    varianceTone(row) {
        if (!row.budget) { return "none"; }
        const band = Math.abs(row.budget) * 0.05;
        if (row.variance > band) { return "over"; }
        if (Math.abs(row.variance) <= band) { return "onpace"; }
        return "calm";
    }

    /** What one chip says when a person hovers or focuses it. ONE expression. */
    chipTitle(mo) {
        if (mo.state === "future" && !mo.spent) {
            return _t("%s has not started.", mo.title);
        }
        if (!mo.has_budget) {
            return _t("%(month)s — no budget set, %(spent)s spent.",
                      { month: mo.title, spent: this.money(mo.spent) });
        }
        return _t("%(month)s — %(spent)s spent of %(budget)s (%(tone)s).",
                  { month: mo.title, spent: this.money(mo.spent),
                    budget: this.money(mo.budget), tone: mo.tone_label });
    }

    /**
     * A month chip is never DISABLED while the board is re-scoping: setting
     * `disabled` on the button the keyboard is standing on blurs it, and the
     * next arrow press then goes nowhere. The guard is here instead.
     */
    async setMonth(key) {
        if (this.state.month === key || this.state.scoping) { return; }
        this.state.month = key;
        this.state.stripFocus = key;
        // The board is NOT unmounted: `loaded` stays true, the tiles keep their
        // keys and their places, and the numbers change under them. That is the
        // whole motion.
        this.state.open = 0;
        this.state.drill = null;
        this.state.scoping = true;
        try {
            await this.load();
        } finally {
            this.state.scoping = false;
        }
    }

    async clearMonth() {
        if (!this.state.month) { return; }
        this.state.month = "";
        this.state.stripFocus = "";
        this.state.open = 0;
        this.state.drill = null;
        this.state.scoping = true;
        try {
            await this.load();
        } finally {
            this.state.scoping = false;
        }
    }

    /** ← and → walk the strip; Enter and Space are the button's own job. */
    async onStripKey(ev) {
        if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") { return; }
        const keys = this.strip.map((m) => m.key);
        if (!keys.length) { return; }
        // WHERE THE KEYBOARD IS STANDING IS THE CHIP THAT HAS FOCUS, not the
        // month in scope: tabbing to April and pressing → must go to May, and
        // reading it off the state sent it to January instead, because the
        // state still said "the whole year".
        const chip = ev.target && ev.target.closest
            ? ev.target.closest("[data-month]") : null;
        const from = (chip && chip.dataset.month)
            || this.state.month || this.state.stripFocus;
        const here = keys.indexOf(from);
        const step = ev.key === "ArrowRight" ? 1 : -1;
        const next = here < 0
            ? (step > 0 ? 0 : keys.length - 1)
            : Math.min(keys.length - 1, Math.max(0, here + step));
        ev.preventDefault();
        await this.setMonth(keys[next]);
        this.focusChip(keys[next]);
    }

    focusChip(key) {
        const root = this.stripRef.el;
        if (!root) { return; }
        const el = root.querySelector(`[data-month="${key}"]`);
        if (el) { el.focus(); }
    }

    /**
     * Escape means "the last thing I opened", never "everything" — the two
     * dialogs first, then the drill, then the month. Registered with
     * `{ capture: true }` because the platform's own hotkey service eats
     * Escape before a bubbling listener ever sees it (WF4).
     */
    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.uploading || this.state.spending) { return; }
        if (this.state.open) {
            this.closeDrill();
            ev.stopPropagation();
            return;
        }
        if (this.state.month) {
            this.clearMonth();
            ev.stopPropagation();
        }
    }

    // -------------------------------------------------------------- filters
    async setYear(ev) {
        this.state.fy = parseInt(ev.target.value, 10) || this.state.fy;
        await this.reload();
    }

    async setType(key) {
        if (this.state.type === key) { return; }
        this.state.type = key;
        await this.reload();
    }

    async setCurrency(mode) {
        if (this.state.currency === mode) { return; }
        this.state.currency = mode;
        await this.reload();
    }

    setView(view) { this.state.view = view; }

    /**
     * The local/reporting switch, offered only when it would DO something.
     *
     * On a tenant whose budgets are all in the company's own money the two
     * chips read "VND" and "VND", which is a control that changes nothing and
     * a question nobody asked. It appears when the two are genuinely different.
     */
    get showCurrencyToggle() {
        const c = this.cur;
        return Boolean(c.local_available && c.local_code
                       && c.local_code !== c.report_code);
    }

    toggleRow(id) {
        this.state.expanded[id] = !this.state.expanded[id];
    }

    // --------------------------------------------------------------- format
    /** Full precision, with the currency beside it. */
    money(n) {
        const v = Math.round(Number(n) || 0);
        return `${v.toLocaleString()} ${this.cur.code || ""}`.trim();
    }

    /** A tile has room for four characters, not for eleven digits. */
    short(n) {
        const v = Number(n) || 0;
        const abs = Math.abs(v);
        if (abs >= 1e12) { return `${(v / 1e12).toFixed(1)}tn`; }
        if (abs >= 1e9) { return `${(v / 1e9).toFixed(1)}bn`; }
        if (abs >= 1e6) { return `${(v / 1e6).toFixed(1)}m`; }
        if (abs >= 1e3) { return `${(v / 1e3).toFixed(0)}k`; }
        return `${Math.round(v)}`;
    }

    pct(n) { return `${Math.round(Number(n) || 0)}%`; }

    /** The fill never runs off the end of its own bar. */
    barWidth(n) { return Math.max(0, Math.min(100, Number(n) || 0)); }

    /** The spark bar and the drill column for the month in scope are LIT. */
    isOnMonth(key) {
        return Boolean(this.state.month) && this.state.month === key;
    }

    /** A month's spend bar on a tile, as a share of the busiest month. */
    monthHeight(f, m) {
        const peak = Math.max(...f.months.map((x) => Math.abs(x.spent || 0)), 1);
        return Math.max(2, Math.round(Math.abs(m.spent || 0) / peak * 100));
    }

    /**
     * A bar in the drill's month chart.
     *
     * Budget and spend are drawn against the SAME peak — the biggest of either
     * across the year — or the two series would each be scaled to themselves
     * and a month that spent half its budget would draw as tall as the budget
     * beside it.
     */
    mBar(f, value) {
        const peak = Math.max(
            ...f.months.map((x) => Math.abs(x.spent || 0)),
            ...f.months.map((x) => Math.abs(x.budget || 0)), 1);
        return Math.max(2, Math.round(Math.abs(Number(value) || 0) / peak * 100));
    }

    typeLabel(key) {
        const opt = (this.board.type_options || []).find((o) => o.key === key);
        return opt ? opt.label : key;
    }

    /** ONE expression per sentence, so the spaces survive (R34). */
    get syncLine() {
        if (!this.board.last_sync) {
            return _t("The pay figures have not been read yet.");
        }
        return _t("Pay figures last read %s.", this.board.last_sync);
    }

    // ---------------------------------------------------------- the drill
    async openFunction(f) {
        if (this.state.open === f.id) { this.closeDrill(); return; }
        this.state.open = f.id;
        this.state.drill = null;
        this.state.drillBusy = true;
        try {
            this.state.drill = await this.orm.call("pb.budget", "get_function", [
                f.id, this.state.fy, this.state.type, this.state.currency,
                this.state.month || null,
            ]);
        } catch (e) {
            this.notif.add(this._msg(e, _t("That function could not be opened.")),
                           { type: "danger" });
            this.state.open = 0;
        } finally {
            this.state.drillBusy = false;
        }
    }

    // ------------------------------------------------------ how it compares
    get compareTitle() {
        return _t("How %s compares", this.scope.name);
    }

    /**
     * The four figures, in the order a person reads them: where they are, the
     * month before, the same month a year ago, and what a month of this year
     * is worth on average.
     */
    get compareCells() {
        const cmp = (this.state.drill && this.state.drill.compare) || null;
        if (!cmp) { return []; }
        return ["this", "last", "last_year", "average"]
            .filter((id) => cmp[id])
            .map((id) => ({ id, ...cmp[id] }));
    }

    /** ONE expression (R2). */
    compareLine(cc) {
        if (!cc.budget) { return _t("no budget set"); }
        return _t("of %s budget", this.short(cc.budget));
    }

    closeDrill() {
        this.state.open = 0;
        this.state.drill = null;
    }

    // --------------------------------------------------------- the actions
    async refreshActuals() {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.budget", "refresh_actuals", []);
            this.notif.add(res.message, { type: "success", sticky: true });
            await this.reload();
        } catch (e) {
            this.notif.add(this._msg(e, _t("The pay figures could not be read.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async exportFile(kind) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.budget", "export_board", [
                this.state.fy, this.state.type, this.state.currency, kind,
                this.state.month || null,
            ]);
            this.download(res);
            this.notif.add(
                kind === "pdf"
                    ? _t("The summary has been downloaded.")
                    : _t("The spreadsheet has been downloaded."),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be built.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    /** base64 to a saved file, without ever leaving the page. */
    download(res) {
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

    // ----------------------------------------------------------- the upload
    openUpload() {
        this.state.upload = { file: "", name: "", plan: null, busy: false };
        this.state.uploading = true;
    }

    closeUpload() { this.state.uploading = false; }

    async getTemplate() {
        this.state.upload.busy = true;
        try {
            const res = await this.orm.call(
                "pb.budget.upload.wizard", "template_xlsx",
                [this.state.fy, this.state.type]);
            this.download(res);
            this.notif.add(
                _t("Template downloaded — %s departments to fill in.",
                   res.departments),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("The template could not be built.")),
                           { type: "danger" });
        } finally {
            this.state.upload.busy = false;
        }
    }

    onUploadFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        const reader = new FileReader();
        reader.onload = async () => {
            const b64 = String(reader.result).split(",")[1] || "";
            this.state.upload.file = b64;
            this.state.upload.name = file.name;
            this.state.upload.plan = null;
            await this.peekUpload();
        };
        reader.readAsDataURL(file);
    }

    async peekUpload() {
        if (!this.state.upload.file) { return; }
        this.state.upload.busy = true;
        try {
            this.state.upload.plan = await this.orm.call(
                "pb.budget.upload.wizard", "peek",
                [this.state.upload.file, this.state.fy, this.state.type]);
        } catch (e) {
            this.state.upload.plan = null;
            this.notif.add(this._msg(e, _t("That file could not be read.")),
                           { type: "danger" });
        } finally {
            this.state.upload.busy = false;
        }
    }

    async applyUpload() {
        if (!this.state.upload.file) { return; }
        this.state.upload.busy = true;
        try {
            const plan = await this.orm.call(
                "pb.budget.upload.wizard", "apply",
                [this.state.upload.file, this.state.fy, this.state.type]);
            this.state.uploading = false;
            this.notif.add(plan.message, { type: "success", sticky: true });
            await this.reload();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That file could not be applied.")),
                           { type: "danger" });
        } finally {
            this.state.upload.busy = false;
        }
    }

    // ---------------------------------------------------------- the expense
    openExpense() {
        this.state.expense = {
            name: "", amount: "",
            budget_type: this.state.type === "admin" ? "admin" : "hr_ops",
            spend_date: new Date().toISOString().slice(0, 10),
            department_id: 0, department: "", supplier: "", note: "",
        };
        this.state.people = [];
        this.state.spending = true;
    }

    closeExpense() { this.state.spending = false; }

    onExpense(field, ev) {
        this.state.expense[field] = ev.target.value;
    }

    async onDeptSearch(ev) {
        const term = ev.target.value;
        this.state.expense.department = term;
        this.state.expense.department_id = 0;
        if (!term || term.length < 2) { this.state.people = []; return; }
        try {
            this.state.people = await this.orm.call(
                "pb.budget", "department_options", [term]);
        } catch (e) {
            this.state.people = [];
        }
    }

    pickDept(dept) {
        this.state.expense.department_id = dept.id;
        this.state.expense.department = dept.name;
        this.state.people = [];
    }

    async saveExpense() {
        const e = this.state.expense;
        if (!(e.name || "").trim()) {
            this.notif.add(_t("Say what the money was for."), { type: "warning" });
            return;
        }
        if (!(Number(e.amount) > 0)) {
            this.notif.add(_t("Put in what it cost."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.budget", "add_expense", [{
                name: e.name, amount: Number(e.amount),
                budget_type: e.budget_type, spend_date: e.spend_date,
                department_id: e.department_id, supplier: e.supplier,
                note: e.note,
            }]);
            this.state.spending = false;
            this.notif.add(res.message, { type: "success" });
            await this.reload();
        } catch (err) {
            this.notif.add(this._msg(err, _t("That could not be saved.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    openExpenseList() {
        this.action.doAction("pb_budget.action_pb_budget_expense");
    }

    openRowList() {
        this.action.doAction("pb_budget.action_pb_budget_rows");
    }

    // --------------------------------------------------------------- errors
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) {
            return e.message.data.message;
        }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_budget_board", PbBudgetBoard);
