/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

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
            // "Payruns" picker overlay. Opens on entry (no silent "newest"
            // default) and is re-openable from the grid header. All runs are
            // loaded once; faceting/sort/search happen client-side (à la the
            // Config Switcher) so the chips can show live counts.
            picker: {
                open: true, loading: false, view: "cards",
                all: [], activeCompany: "", multiCompany: false,
                f: { search: "", status: "", cycle: "", division: "", company: "",
                     year: "", range: "", from: "", to: "", sort: "newest" },
            },
        });
        this._searchTimer = null;
        // Land on the picker, not on an arbitrary run's grid.
        onWillStart(async () => { await this.loadPicker(); });
    }

    // ---- pay-run picker (loads once, then all-client-side) ----
    async loadPicker() {
        this.state.picker.loading = true;
        try {
            const r = await this.orm.call("pb.payrun.results", "list_runs", []);
            this.state.picker.all = (r && r.runs) || [];
            this.state.picker.activeCompany = (r && r.active_company) || "";
            this.state.picker.multiCompany = !!(r && r.multi_company);
        } catch (e) {
            this.state.picker.all = [];
            this.notif.add(_t("Could not load pay runs"), { type: "danger" });
        } finally {
            this.state.picker.loading = false;
        }
    }
    openPicker() { this.state.picker.open = true; this.loadPicker(); }
    closePicker() { this.state.picker.open = false; }
    setView(v) { this.state.picker.view = v; }
    onPickerSearch(ev) { this.state.picker.f.search = ev.target.value || ""; }

    // toggle a facet chip: click to select, click again to clear
    toggleFacet(key, v) {
        const f = this.state.picker.f;
        f[key] = (String(f[key]) === String(v)) ? "" : v;
    }
    setSort(v) { this.state.picker.f.sort = v; }
    setRange(key) {
        const f = this.state.picker.f;
        f.range = (f.range === key) ? "" : key;
        if (f.range) { f.from = ""; f.to = ""; }   // a quick range clears custom
    }
    setCustom(which, ev) {
        this.state.picker.f[which] = ev.target.value || "";
        this.state.picker.f.range = "";            // a custom date clears the quick range
    }
    clearFilters() {
        this.state.picker.f = { search: "", status: "", cycle: "", division: "", company: "",
                                year: "", range: "", from: "", to: "", sort: "newest" };
    }
    get pickerDirty() {
        const f = this.state.picker.f;
        return !!(f.search || f.status || f.cycle || f.division || f.company || f.year
                  || f.range || f.from || f.to || (f.sort && f.sort !== "newest"));
    }
    async chooseRun(id) {
        this.state.runId = id;
        this.state.filters.page = 1;
        this.state.picker.open = false;
        await this.load();
    }

    // ---- facets (counts over the full set, like the Config Switcher) ----
    _facet(valKey, labelKey, extraKey) {
        const m = {};
        for (const c of this.state.picker.all) {
            const v = c[valKey];
            if (v === "" || v === false || v === undefined || v === null) continue;
            const k = String(v);
            if (!m[k]) m[k] = { v, label: c[labelKey] || k, n: 0, extra: extraKey ? c[extraKey] : "" };
            m[k].n++;
        }
        return Object.values(m).sort((a, b) => b.n - a.n || String(a.label).localeCompare(String(b.label)));
    }
    get statusFacets() {
        const order = ["draft", "verify", "level1", "level2", "done", "close", "paid"];
        return this._facet("state", "state_label", "state_tone")
            .sort((a, b) => order.indexOf(a.v) - order.indexOf(b.v));
    }
    get cycleFacets() { return this._facet("cycle_type", "cycle_label"); }
    get divisionFacets() { return this._facet("division", "division_label"); }
    get companyFacets() { return this.state.picker.multiCompany ? this._facet("company_id", "company") : []; }
    get yearFacets() { return this._facet("year", "year").sort((a, b) => String(b.v).localeCompare(String(a.v))); }
    get quickRanges() {
        return [
            { key: "tm", label: _t("This month") }, { key: "lm", label: _t("Last month") },
            { key: "tq", label: _t("This quarter") }, { key: "ty", label: _t("This year") },
            { key: "ly", label: _t("Last year") },
        ];
    }

    // ---- filtered + sorted list, and the KPI roll-up over it ----
    _rangeBounds() {
        const f = this.state.picker.f;
        if (f.from || f.to) return { lo: f.from || "", hi: f.to || "" };
        if (!f.range) return null;
        const d = new Date(), y = d.getFullYear(), m = d.getMonth();
        const pad = (n) => String(n).padStart(2, "0");
        const iso = (yy, mm, dd) => `${yy}-${pad(mm + 1)}-${pad(dd)}`;
        const last = (yy, mm) => new Date(yy, mm + 1, 0).getDate();
        if (f.range === "tm") return { lo: iso(y, m, 1), hi: iso(y, m, last(y, m)) };
        if (f.range === "lm") { const pm = m === 0 ? 11 : m - 1, py = m === 0 ? y - 1 : y; return { lo: iso(py, pm, 1), hi: iso(py, pm, last(py, pm)) }; }
        if (f.range === "tq") { const q = Math.floor(m / 3) * 3; return { lo: iso(y, q, 1), hi: iso(y, q + 2, last(y, q + 2)) }; }
        if (f.range === "ty") return { lo: iso(y, 0, 1), hi: iso(y, 11, 31) };
        if (f.range === "ly") return { lo: iso(y - 1, 0, 1), hi: iso(y - 1, 11, 31) };
        return null;
    }
    get pRuns() {
        const f = this.state.picker.f;
        let out = this.state.picker.all.slice();
        const q = (f.search || "").trim().toLowerCase();
        if (q) out = out.filter((c) => (c.name || "").toLowerCase().includes(q));
        if (f.status) out = out.filter((c) => c.state === f.status);
        if (f.cycle) out = out.filter((c) => c.cycle_type === f.cycle);
        if (f.division) out = out.filter((c) => c.division === f.division);
        if (f.company) out = out.filter((c) => String(c.company_id) === String(f.company));
        if (f.year) out = out.filter((c) => c.year === String(f.year));
        const b = this._rangeBounds();
        if (b) {
            if (b.lo) out = out.filter((c) => c.date_end && c.date_end >= b.lo);
            if (b.hi) out = out.filter((c) => c.date_start && c.date_start <= b.hi);
        }
        if (f.sort === "oldest") out.sort((a, z) => (a.date_start || "").localeCompare(z.date_start || "") || a.id - z.id);
        else if (f.sort === "emp") out.sort((a, z) => (z.employees || 0) - (a.employees || 0));
        else if (f.sort === "net") out.sort((a, z) => (Number(z.net) || 0) - (Number(a.net) || 0));
        else out.sort((a, z) => (z.date_start || "").localeCompare(a.date_start || "") || z.id - a.id);
        return out;
    }
    get pSummary() {
        const rows = this.pRuns;
        let emp = 0, net = 0, approved = 0;
        for (const c of rows) { emp += c.employees || 0; net += Number(c.net) || 0; if (c.state === "done") approved++; }
        return { runs: rows.length, employees: emp, net, approved,
                 currency: (rows[0] && rows[0].currency) || "₫" };
    }

    // ---- picker formatting ----
    pNum(n) { return Number(n || 0).toLocaleString("en-US"); }
    pMoneyShort(n, cur) {
        n = Number(n) || 0; cur = cur || "₫";
        if (n >= 1e9) return cur + (n / 1e9).toFixed(1).replace(/\.0$/, "") + "B";
        if (n >= 1e6) return cur + (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
        if (n >= 1e3) return cur + Math.round(n / 1e3) + "K";
        return cur + Math.round(n).toLocaleString("en-US");
    }
    // Net/Gross come from stored salary-category roll-ups; shown only when they
    // genuinely exist (the tiny JSON-import runs file everything under "Other"
    // → 0). Employees is the always-reliable hero.
    pRunMoney(card) {
        const cur = card.currency || "₫";
        if (Number(card.net) > 0) return cur + Math.round(card.net).toLocaleString("en-US");
        if (Number(card.gross) > 0) return cur + Math.round(card.gross).toLocaleString("en-US");
        return "";
    }
    pRunMoneyLabel(card) {
        if (Number(card.net) > 0) return _t("Net pay");
        if (Number(card.gross) > 0) return _t("Gross");
        return "";
    }
    pDate(iso) {
        if (!iso) return "";
        const p = iso.split("-");
        if (p.length !== 3) return iso;
        const M = [_t("Jan"), _t("Feb"), _t("Mar"), _t("Apr"), _t("May"), _t("Jun"),
            _t("Jul"), _t("Aug"), _t("Sep"), _t("Oct"), _t("Nov"), _t("Dec")];
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

    // ---- grid filters ----
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
            if (!r || !r.ok) { this.notif.add((r && r.msg) || _t("Export failed"), { type: "warning" }); return; }
            const bin = atob(r.file_b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            const url = URL.createObjectURL(new Blob([bytes], { type: r.mimetype }));
            const a = document.createElement("a");
            a.href = url; a.download = r.filename; a.click();
            URL.revokeObjectURL(url);
            this.notif.add(_t("Results exported to Excel"), { type: "success" });
        } catch (e) {
            this.notif.add(_t("Export failed"), { type: "danger" });
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
