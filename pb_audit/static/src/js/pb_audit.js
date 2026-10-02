/** @odoo-module **/
/**
 * Audit & Compliance console — a READ-ONLY, day-grouped compliance ledger over
 * every audit source in the platform (field changes, approvals, bank master,
 * exports, deliveries, logins) plus the salary and login lenses. RPC facade:
 * pb.audit.console. pbim-tokenized (.pbim.pbau). Lucide icons only (ic()).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.audit.console";

const SOURCE_CHIPS = [
    { key: "all", label: _t("All") },
    { key: "field", label: _t("Fields") },
    { key: "approval", label: _t("Approvals") },
    { key: "bank", label: _t("Bank") },
    { key: "export", label: _t("Exports") },
    { key: "delivery", label: _t("Payslips") },
    { key: "login", label: _t("Logins") },
];

export class PbAudit extends Component {
    static template = "pb_audit.PbAudit";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.sourceChips = SOURCE_CHIPS;
        this.state = useState({
            loaded: false,
            busy: false,
            view: "stream",                 // stream | salary | login
            kpis: {},
            filters: {
                date_from: null, date_to: null, source: "all",
                actor_id: null, employee_id: null, model: null, text: "",
            },
            employeeLabel: "",
            stream: { rows: [], offset: 0, has_more: false, capped: false,
                      sources: [], loading: false },
            salary: null,
            login: null,
            retentionEdit: false,
            retentionValue: 0,
        });
        onWillStart(async () => {
            await this.loadKpis();
            await this.loadStream(true);
            this.state.loaded = true;
        });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- loaders
    async loadKpis() {
        this.state.kpis = await this.orm.call(MODEL, "get_kpis", []);
        this.state.retentionValue = this.state.kpis.retention_days || 0;
    }

    get filterPayload() {
        const f = this.state.filters;
        return {
            date_from: f.date_from || null, date_to: f.date_to || null,
            source: f.source || "all", actor_id: f.actor_id || null,
            employee_id: f.employee_id || null, model: f.model || null,
            text: f.text || "",
        };
    }

    async loadStream(reset) {
        this.state.stream.loading = true;
        try {
            if (reset) { this.state.stream.offset = 0; }
            const data = await this.orm.call(MODEL, "get_stream",
                [this.filterPayload, this.state.stream.offset]);
            this.state.stream.rows = reset
                ? data.rows : this.state.stream.rows.concat(data.rows);
            this.state.stream.has_more = data.has_more;
            this.state.stream.capped = data.capped;
            this.state.stream.sources = data.sources;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.stream.loading = false;
        }
    }

    async loadMore() {
        // The server pages by 50 and we concat; the next offset is exactly the
        // number of rows already held.
        this.state.stream.offset = this.state.stream.rows.length;
        await this.loadStream(false);
    }

    async loadSalary() {
        this.state.busy = true;
        try {
            this.state.salary = await this.orm.call(
                MODEL, "get_salary_lens", [this.filterPayload]);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async loadLogin() {
        this.state.busy = true;
        try {
            this.state.login = await this.orm.call(
                MODEL, "get_login_lens", [this.filterPayload]);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- views
    async setView(view) {
        this.state.view = view;
        if (view === "salary" && !this.state.salary) { await this.loadSalary(); }
        if (view === "login" && !this.state.login) { await this.loadLogin(); }
    }

    async reloadCurrent() {
        if (this.state.view === "stream") { await this.loadStream(true); }
        if (this.state.view === "salary") { await this.loadSalary(); }
        if (this.state.view === "login") { await this.loadLogin(); }
    }

    // ------------------------------------------------------------- filters
    async setSource(key) {
        this.state.filters.source = key;
        await this.loadStream(true);
    }
    onText(ev) { this.state.filters.text = ev.target.value; }
    async applyText() { await this.loadStream(true); }
    onDateFrom(ev) { this.state.filters.date_from = ev.target.value || null; }
    onDateTo(ev) { this.state.filters.date_to = ev.target.value || null; }
    async applyDates() { await this.reloadCurrent(); }

    async clearFilters() {
        this.state.filters = {
            date_from: null, date_to: null, source: "all",
            actor_id: null, employee_id: null, model: null, text: "",
        };
        this.state.employeeLabel = "";
        await this.reloadCurrent();
    }

    // quick chips -----------------------------------------------------------
    _todayStr(offsetDays = 0) {
        const d = new Date();
        d.setDate(d.getDate() - offsetDays);
        return d.toISOString().slice(0, 10);
    }
    async quickToday() {
        const t = this._todayStr(0);
        this.state.filters.date_from = t;
        this.state.filters.date_to = t;
        await this.reloadCurrent();
    }
    async quickWeek() {
        this.state.filters.date_from = this._todayStr(6);
        this.state.filters.date_to = this._todayStr(0);
        await this.reloadCurrent();
    }
    async quickByMe() {
        this.state.filters.actor_id = user.userId;
        await this.reloadCurrent();
    }
    async quickSalary() { await this.setView("salary"); }
    async quickLogins() { await this.setView("login"); }

    get isMineActive() { return this.state.filters.actor_id === user.userId; }

    // ------------------------------------------------------------- deep-links
    openEmployee(id) {
        if (!id) { return; }
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.employee",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }
    openRef(ref) {
        if (!ref || !ref.model || !ref.res_id) { return; }
        this.action.doAction({
            type: "ir.actions.act_window", res_model: ref.model,
            res_id: ref.res_id, views: [[false, "form"]], target: "current",
        });
    }

    // ------------------------------------------------------------- retention
    startRetention() {
        this.state.retentionEdit = true;
        this.state.retentionValue = this.state.kpis.retention_days || 0;
    }
    onRetention(ev) { this.state.retentionValue = parseInt(ev.target.value, 10) || 0; }
    cancelRetention() { this.state.retentionEdit = false; }
    async saveRetention() {
        this.state.busy = true;
        try {
            const r = await this.orm.call(MODEL, "set_retention",
                [this.state.retentionValue]);
            this.state.kpis.retention_days = r.retention_days;
            this.state.retentionEdit = false;
            this.notif.add(_t("Retention updated."), { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- export
    async exportView() {
        const kind = this.state.view;
        this.state.busy = true;
        try {
            const r = await this.orm.call(MODEL, "export_stream",
                [this.filterPayload, kind]);
            const link = document.createElement("a");
            link.href = r.url;
            link.download = r.filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            let msg = _t("Exported %s rows.", r.count);
            if (r.truncated) {
                msg = _t("Exported %s rows — capped at %s (refine filters for the rest).",
                    r.count, r.cap);
            }
            this.notif.add(msg, { type: r.truncated ? "warning" : "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- day groups
    get groupedStream() {
        const groups = [];
        const byDay = {};
        for (const row of this.state.stream.rows) {
            if (!byDay[row.day]) {
                byDay[row.day] = { day: row.day, label: this._dayLabel(row.day), rows: [] };
                groups.push(byDay[row.day]);
            }
            byDay[row.day].rows.push(row);
        }
        return groups;
    }
    _dayLabel(day) {
        if (!day) { return _t("Undated"); }
        const today = this._todayStr(0);
        const yest = this._todayStr(1);
        if (day === today) { return _t("Today"); }
        if (day === yest) { return _t("Yesterday"); }
        return day;
    }

    // ------------------------------------------------------------- sparklines
    sparkBars(values) {
        const max = Math.max(1, ...(values || []));
        return (values || []).map((v) => ({ v, h: Math.round((v / max) * 100) }));
    }
    salaryLinePoints(series, w = 220, h = 46) {
        if (!series || !series.length) { return ""; }
        const max = Math.max(1, ...series.map((s) => s.count));
        const step = series.length > 1 ? w / (series.length - 1) : w;
        return series.map((s, i) => {
            const x = Math.round(i * step);
            const y = Math.round(h - (s.count / max) * (h - 4) - 2);
            return `${x},${y}`;
        }).join(" ");
    }

    // ------------------------------------------------------------- helpers
    sourcePills() { return this.state.kpis.sources || []; }
    presentCount() { return this.sourcePills().filter((s) => s.installed).length; }
    retentionDialPct() {
        // a simple 0..1 fill for the dial: 730d = full ring baseline.
        const d = this.state.kpis.retention_days || 0;
        return Math.min(1, d / 730);
    }
    deltaLabel(pct) {
        if (pct === null || pct === undefined) { return "—"; }
        const sign = pct > 0 ? "+" : "";
        return `${sign}${pct}%`;
    }
    _err(e) {
        return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed.");
    }
}

registry.category("actions").add("pb_audit", PbAudit);
