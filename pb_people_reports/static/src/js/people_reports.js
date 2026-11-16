/** @odoo-module **/
/**
 * People › Insights › People reports (WDGAP S9-B, owner ruling P6).
 *
 * HR only, for the companies the reader already sees. Every figure arrives
 * from the server already hidden when it covers fewer than 5 people (or would
 * let one be worked out): a hidden cell is `{v: null, h: true}` and its value
 * never reaches the browser. The download is built from the same payload.
 *
 * Registered under `insights` (a tab of People › Insights, ledger S9-F7): no
 * shared file is edited. R2 — icons are the filter kit's cached markup.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { pbfIcon } from "@pb_filter_kit/js/filter_kit";

export const PEOPLE_REPORTS_GATE = ["hr.group_hr_user"];

export class PbPeopleReports extends Component {
    static template = "pb_people_reports.PbPeopleReports";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, allowed: true, why: "", options: null,
            view: "headcount", company_id: 0, department_id: 0, year: 0,
            data: null, busy: false, error: false, downloading: false,
        });
        onWillStart(async () => { await this.init(); });
    }

    icon(name, size = 16) { return pbfIcon(name, size); }

    async init() {
        try {
            const o = await this.orm.call("pb.people.reports", "get_options", []);
            this.state.allowed = o.allowed !== false;
            this.state.why = o.why || "";
            this.state.options = o;
            this.state.year = o.year || 0;
            if (this.state.allowed) { await this.load(); }
        } catch (e) {
            console.warn("pb_people_reports: options could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The people reports could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    get params() {
        return { company_id: this.state.company_id, department_id: this.state.department_id, year: this.state.year };
    }

    async load() {
        this.state.busy = true;
        this.state.error = false;
        try {
            this.state.data = await this.orm.call("pb.people.reports", "get_report", [this.state.view, this.params]);
        } catch (e) {
            console.error("pb_people_reports: the report could not load", e);
            this.state.error = true;
        } finally {
            this.state.busy = false;
        }
    }

    pickView(key) { if (key !== this.state.view) { this.state.view = key; this.load(); } }
    onCompany(ev) {
        this.state.company_id = parseInt(ev.target.value || "0", 10);
        this.state.department_id = 0;
        this.load();
    }
    onDept(ev) {
        const id = parseInt(ev.target.value || "0", 10);
        this.state.department_id = id;
        // a department is looked at inside its own company (the server does the same)
        const d = this.departments.find((x) => x.id === id);
        if (d && this.companies.length > 1) { this.state.company_id = d.company_id; }
        this.load();
    }
    onYear(ev) { this.state.year = parseInt(ev.target.value || "0", 10); this.load(); }

    get departments() {
        const o = this.state.options || {};
        const cid = this.state.company_id;
        return (o.departments || []).filter((d) => !cid || d.company_id === cid);
    }
    get companies() { return (this.state.options && this.state.options.companies) || []; }
    get views() { return (this.state.options && this.state.options.views) || []; }
    get years() { return (this.state.options && this.state.options.years) || []; }

    // ---------------------------------------------------------------- cells
    shown(c) { return c && !c.h && c.v !== null && c.v !== undefined; }
    num(c) { return this.shown(c) ? Number(c.v).toLocaleString() : ""; }
    pct(c) { return this.shown(c) ? `${Number(c.v).toLocaleString()}%` : ""; }
    get maxHead() {
        const s = (this.state.data && this.state.data.series) || [];
        return Math.max(1, ...s.map((r) => (this.shown(r.h) ? r.h.v : 0)));
    }
    get maxMove() {
        const s = (this.state.data && this.state.data.quarters) || [];
        return Math.max(1, ...s.map((r) => Math.max(this.shown(r.j) ? r.j.v : 0, this.shown(r.l) ? r.l.v : 0)));
    }
    barStyle(c, max) {
        const v = this.shown(c) ? c.v : 0;
        return `width: ${Math.max(0, Math.min(100, (v * 100) / (max || 1)))}%`;
    }
    rowBarStyle(c) { return `width: ${this.shown(c) ? Math.max(0, Math.min(100, c.v)) : 0}%`; }
    netLabel(c) {
        if (!this.shown(c)) { return ""; }
        return c.v > 0 ? `+${c.v}` : String(c.v);
    }

    async download() {
        this.state.downloading = true;
        try {
            const f = await this.orm.call("pb.people.reports", "export_xlsx", [this.state.view, this.params]);
            const bin = atob(f.data);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) { bytes[i] = bin.charCodeAt(i); }
            const blob = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = f.name || "people-report.xlsx";
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 2000);
        } catch (e) {
            this.notif.add(_t("The spreadsheet could not be made just now."), { type: "warning" });
        } finally {
            this.state.downloading = false;
        }
    }
}

// A TAB of People › Insights (`under: "insights"`), straight into the People
// hub's lens registry — not into the closed Insights table (ledger S9-F7).
registry.category("pb_people_hub_lens").add("people_reports", {
    key: "people_reports",
    icon: "pieChart",
    label: _t("People reports"),
    title: _t("People reports"),
    Component: PbPeopleReports,
    groups: PEOPLE_REPORTS_GATE,
    probe: { model: "pb.people.reports", method: "can_open" },
    under: "insights",
}, { sequence: 86 });

registry.category("pb_hub_palette").add("people_reports", {
    id: "people_reports",
    label: _t("People reports"),
    sublabel: _t("People"),
    icon: "pieChart",
    groups: PEOPLE_REPORTS_GATE,
    probe: { model: "pb.people.reports", method: "can_open" },
    action: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "people_reports" },
    keywords: ["turnover", "headcount", "joiners", "leavers", "gender", "age", "tenure", "nghỉ việc", "pergantian"],
}, { sequence: 2780 });
