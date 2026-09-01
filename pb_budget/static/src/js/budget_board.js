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
 * R1 — no `t-as` variable is named lt / gt / lte / gte / and / or / not / in.
 * R2 — every sentence is ONE expression; JavaScript has no implicit string
 * concatenation and a Python habit here kills the entire asset bundle.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
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

        this.state = useState({
            loaded: false,
            failed: "",
            board: null,
            view: "heat",                  // heat | table
            fy: 0,
            type: "manpower",
            currency: "report",
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

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        try {
            const board = await this.orm.call("pb.budget", "get_board", [
                this.state.fy || null, this.state.type, this.state.currency,
            ]);
            this.state.board = board;
            this.state.fy = board.fy;
            this.state.type = board.budget_type;
            this.state.currency = board.currency.mode;
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
            ]);
        } catch (e) {
            this.notif.add(this._msg(e, _t("That function could not be opened.")),
                           { type: "danger" });
            this.state.open = 0;
        } finally {
            this.state.drillBusy = false;
        }
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
