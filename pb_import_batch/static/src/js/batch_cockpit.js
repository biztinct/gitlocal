/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.import.batch.cockpit";
const LINE_CLS = {
    matched: "ok", validated: "ok", processed: "ok",
    unmatched: "warn", error: "err", draft: "muted",
};
// line-table quick filters
const LINE_FILTERS = ["all", "matched", "new", "errors"];
const LINE_FILTER_LABEL = { all: _t("All"), matched: _t("Matched"), new: _t("New"), errors: _t("Needs attention") };

export class BatchCockpit extends Component {
    static template = "pb_import_batch.BatchCockpit";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.batchId = p.batch_id || p.active_id;
        this.state = useState({
            loaded: false, busy: false, busyMsg: "",
            detail: null, filter: "all",
            match: { lineId: null, results: [] },
        });
        onWillStart(async () => { await this.refresh(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    async refresh() {
        try {
            this.state.detail = await this.orm.call(MODEL, "get_batch_detail", [this.batchId]);
        } catch (e) {
            this.state.detail = { error: "Could not load this batch." };
        } finally {
            this.state.loaded = true;
        }
    }

    // ---- derived ----
    get d() { return this.state.detail || {}; }
    lineCls(s) { return LINE_CLS[s] || "muted"; }
    initials() {
        const n = (this.d.name || "?").trim();
        return n.slice(0, 2).toUpperCase();
    }
    _lineIn(l) {
        const f = this.state.filter;
        if (f === "all") return true;
        if (f === "new") return l.is_new;
        if (f === "errors") return l.state === "error" || l.state === "unmatched";
        return l.state === f;          // matched
    }
    get filteredLines() { return (this.d.lines || []).filter((l) => this._lineIn(l)); }
    get lineFilters() { return LINE_FILTERS; }
    lineFilterLabel(f) { return LINE_FILTER_LABEL[f]; }
    countLines(f) {
        const ls = this.d.lines || [];
        if (f === "all") return ls.length;
        if (f === "new") return ls.filter((l) => l.is_new).length;
        if (f === "errors") return ls.filter((l) => l.state === "error" || l.state === "unmatched").length;
        return ls.filter((l) => l.state === f).length;
    }
    setFilter(f) { this.state.filter = f; }

    // ---- lifecycle actions ----
    async _run(promise, msg) {
        this.state.busy = true; this.state.busyMsg = msg || "Working…";
        try {
            const res = await promise;
            if (res && typeof res === "object") {
                this.state.detail = res;
                if (res.error) this.notif.add(res.error, { type: "warning" });
            }
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || _t("Action failed."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    runAction(method) {
        return this._run(this.orm.call(MODEL, "run_batch_action", [this.batchId, method]),
                         "Running…");
    }

    // ---- result links ----
    async openLink(method) {
        try {
            const act = await this.orm.call(MODEL, "get_link", [this.batchId, method]);
            if (act) this.action.doAction(act);
        } catch (e) { /* ignore */ }
    }
    openRun() {
        const id = this.d.results && this.d.results.payslip_run_id;
        if (id) this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.payslip.run",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }
    openAdvancedForm() {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.payroll.import.batch",
            res_id: this.batchId, views: [[false, "form"]], target: "current",
        });
    }
    back() { this.action.doAction("pb_import.action_pb_import", { clearBreadcrumbs: true }); }

    // ---- inline line fixes + manual match ----
    async fixLine(id, op) {
        this.state.detail = await this.orm.call(MODEL, "fix_line", [id, op]);
    }
    openMatch(lineId) {
        const m = this.state.match;
        m.lineId = m.lineId === lineId ? null : lineId;
        m.results = [];
        if (m.lineId) this._searchEmp("");
    }
    async onMatchSearch(ev) { await this._searchEmp(ev.target.value); }
    async _searchEmp(term) {
        try {
            this.state.match.results = await this.orm.call(MODEL, "search_employees", [term, 12]);
        } catch (e) { this.state.match.results = []; }
    }
    async pickEmployee(empId) {
        const lineId = this.state.match.lineId;
        if (!lineId) return;
        this.state.detail = await this.orm.call(MODEL, "match_line", [lineId, empId, false]);
        this.state.match.lineId = null; this.state.match.results = [];
    }
    async markNewEmployee(lineId) {
        this.state.detail = await this.orm.call(MODEL, "match_line", [lineId, false, true]);
        this.state.match.lineId = null; this.state.match.results = [];
    }
}

registry.category("actions").add("pb_import_batch_cockpit", BatchCockpit);
