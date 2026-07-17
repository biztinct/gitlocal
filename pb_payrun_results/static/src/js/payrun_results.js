/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PbPayrunResults extends Component {
    static template = "pb_payrun_results.PbPayrunResults";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, busy: false, data: {},
            runId: false,
            filters: { department_id: "", search: "", with_variance: false, page: 1 },
            exporting: false,
            // F112b — pay-run picker overlay. Opens on entry (no silent "newest"
            // default) and is re-openable from the grid header.
            picker: {
                open: true, loading: false, view: "cards",
                runs: [], total: 0, grandTotal: 0,
                options: { states: [], divisions: [], companies: [] },
                filters: { search: "", date_from: "", date_to: "", state: "", division: "", company_id: "", sort: "newest" },
            },
        });
        this._searchTimer = null;
        this._pickerTimer = null;
        // Land on the picker, not on an arbitrary run's grid.
        onWillStart(async () => { await this.loadPicker(); });
    }

    // ---- pay-run picker ----
    async loadPicker() {
        this.state.picker.loading = true;
        try {
            const r = await this.orm.call("pb.payrun.results", "list_runs",
                [this.state.picker.filters]);
            this.state.picker.runs = (r && r.runs) || [];
            this.state.picker.total = (r && r.total) || 0;
            this.state.picker.grandTotal = (r && r.grand_total) || 0;
            if (r && r.options) this.state.picker.options = r.options;
        } catch (e) {
            this.state.picker.runs = [];
            this.notif.add("Could not load pay runs", { type: "danger" });
        } finally {
            this.state.picker.loading = false;
        }
    }
    openPicker() { this.state.picker.open = true; this.loadPicker(); }
    closePicker() { this.state.picker.open = false; }
    setView(v) { this.state.picker.view = v; }
    onPickerSearch(ev) {
        this.state.picker.filters.search = ev.target.value || "";
        clearTimeout(this._pickerTimer);
        this._pickerTimer = setTimeout(() => this.loadPicker(), 250);
    }
    setPFilter(key, ev) {
        this.state.picker.filters[key] = ev.target.value || "";
        this.loadPicker();
    }
    resetPicker() {
        this.state.picker.filters = { search: "", date_from: "", date_to: "", state: "", division: "", company_id: "", sort: "newest" };
        this.loadPicker();
    }
    get pickerDirty() {
        const f = this.state.picker.filters;
        return !!(f.search || f.date_from || f.date_to || f.state || f.division || f.company_id || (f.sort && f.sort !== "newest"));
    }
    async chooseRun(id) {
        this.state.runId = id;
        this.state.filters.page = 1;
        this.state.picker.open = false;
        await this.load();
    }

    // ---- picker formatting ----
    pNum(n) { return Number(n || 0).toLocaleString("en-US"); }
    // Net/Gross come from stored salary-category roll-ups, which are 0 for
    // formula runs whose lines are all filed under "Other" — so money is shown
    // only when it genuinely exists; employees is the always-reliable hero.
    pRunMoney(card) {
        const cur = card.currency || "₫";
        if (Number(card.net) > 0) return cur + Math.round(card.net).toLocaleString("en-US");
        if (Number(card.gross) > 0) return cur + Math.round(card.gross).toLocaleString("en-US");
        return "";
    }
    pRunMoneyLabel(card) {
        if (Number(card.net) > 0) return "Net pay";
        if (Number(card.gross) > 0) return "Gross";
        return "";
    }
    pDate(iso) {
        if (!iso) return "";
        const p = iso.split("-");
        if (p.length !== 3) return iso;
        const M = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        return `${parseInt(p[2], 10)} ${M[parseInt(p[1], 10) - 1]} ${p[0]}`;
    }
    pPeriod(card) {
        const a = this.pDate(card.date_start), b = this.pDate(card.date_end);
        if (a && b) return `${a} – ${b}`;
        return a || b || "";
    }

    async load() {
        this.state.busy = true;
        try {
            const d = await this.orm.call("pb.payrun.results", "get_grid",
                [this.state.runId || false, this.state.filters]);
            this.state.data = d;
            this.state.runId = d.run ? d.run.id : (d.runs && d.runs[0] && d.runs[0].id) || false;
        } catch (e) {
            this.state.data = { ok: false, empty_reason: "Could not load results.", columns: [], rows: [] };
        } finally {
            this.state.busy = false;
            this.state.loaded = true;
        }
    }

    // ---- run switcher + filters ----
    async selectRun(ev) {
        this.state.runId = parseInt(ev.target.value) || false;
        this.state.filters.page = 1;
        await this.load();
    }
    async selectDept(ev) {
        this.state.filters.department_id = ev.target.value || "";
        this.state.filters.page = 1;
        await this.load();
    }
    onSearch(ev) {
        this.state.filters.search = ev.target.value || "";
        this.state.filters.page = 1;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.load(), 300);
    }
    async toggleVariance() {
        this.state.filters.with_variance = !this.state.filters.with_variance;
        await this.load();
    }
    async gotoPage(p) {
        const pc = this.state.data.page_count || 1;
        const np = Math.min(Math.max(1, p), pc);
        if (np === this.state.filters.page) return;
        this.state.filters.page = np;
        await this.load();
    }

    // ---- drill ----
    openPayslip(row) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.payslip",
            res_id: row.slip_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ---- formatting ----
    fmt(col, v) {
        if (v === null || v === undefined || v === "") return "—";
        const n = Number(v);
        if (isNaN(n)) return String(v);
        const cur = (this.state.data.run && this.state.data.run.currency) || "₫";
        if (col.number_format === "percentage") return (Math.round(n * 10000) / 100).toLocaleString("en-US") + "%";
        if (col.number_format === "integer") return Math.round(n).toLocaleString("en-US");
        if (col.number_format === "number") return (Math.round(n * 100) / 100).toLocaleString("en-US");
        return cur + Math.round(n).toLocaleString("en-US");
    }
    // variance heat: green up / amber down, bucketed by magnitude
    deltaClass(row, col) {
        if (!row.deltas) return "";
        const d = row.deltas[col.code];
        if (!d) return "";
        const mag = Math.abs(d) > 1000000 ? "hi" : Math.abs(d) > 100000 ? "mid" : "lo";
        return `pbr-delta ${d > 0 ? "up" : "down"} ${mag}`;
    }
    deltaLabel(row, col) {
        if (!row.deltas) return "";
        const d = row.deltas[col.code];
        if (!d) return "";
        const s = d > 0 ? "▲" : "▼";
        return s + this.fmt(col, Math.abs(d));
    }

    // ---- export ----
    async exportXlsx() {
        if (this.state.exporting) return;
        this.state.exporting = true;
        try {
            const r = await this.orm.call("pb.payrun.results", "export_grid",
                [this.state.runId, this.state.filters]);
            if (!r || !r.ok) { this.notif.add((r && r.msg) || "Export failed", { type: "warning" }); return; }
            const bin = atob(r.file_b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            const url = URL.createObjectURL(new Blob([bytes], { type: r.mimetype }));
            const a = document.createElement("a");
            a.href = url; a.download = r.filename; a.click();
            URL.revokeObjectURL(url);
            this.notif.add("Results exported to Excel", { type: "success" });
        } catch (e) {
            this.notif.add("Export failed", { type: "danger" });
        } finally {
            this.state.exporting = false;
        }
    }

    get pageInfo() {
        const d = this.state.data;
        const from = ((d.page || 1) - 1) * 100 + 1;
        const to = Math.min((d.page || 1) * 100, d.row_count || 0);
        return { from, to, total: d.row_count || 0 };
    }
}

registry.category("actions").add("pb_payrun_results", PbPayrunResults);
