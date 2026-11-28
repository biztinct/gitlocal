/** @odoo-module **/
/**
 * People › Insights › People reports (WDGAP S9-B; owner rulings P6, PR1, PR2).
 *
 * HR only, for the companies the reader already sees. PR1: HR sees every
 * figure (no small-group hiding on this screen). PR2: the headcount at each
 * month end, joiners and leavers per month, grouped by quarter, drawn as a
 * line and listed as a table. The download is built from the same payload.
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

// the headcount line's drawing box (SVG units; it scales to the card width)
const CHART = { w: 1100, h: 240, left: 48, right: 16, top: 18, bottom: 32 };

export class PbPeopleReports extends Component {
    static template = "pb_people_reports.PbPeopleReports";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, allowed: true, why: "", options: null,
            view: "headcount", company_id: 0, department_id: 0, period: "",
            data: null, busy: false, error: false, downloading: false,
            hover: -1,
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
            this.state.period = o.period || "";
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
        return { company_id: this.state.company_id, department_id: this.state.department_id, period: this.state.period };
    }

    async load() {
        this.state.busy = true;
        this.state.error = false;
        this.state.hover = -1;
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
    onPeriod(ev) { this.state.period = ev.target.value || ""; this.load(); }

    get departments() {
        const o = this.state.options || {};
        const cid = this.state.company_id;
        return (o.departments || []).filter((d) => !cid || d.company_id === cid);
    }
    get companies() { return (this.state.options && this.state.options.companies) || []; }
    get views() { return (this.state.options && this.state.options.views) || []; }
    get periods() { return (this.state.options && this.state.options.periods) || []; }

    // ---------------------------------------------------------------- figures
    num(v) { return v === null || v === undefined ? "—" : Number(v).toLocaleString(); }
    pct(v) { return v === null || v === undefined ? "—" : `${Number(v).toLocaleString()}%`; }
    netLabel(v) {
        if (v === null || v === undefined) { return "—"; }
        return v > 0 ? `+${v.toLocaleString()}` : v.toLocaleString();
    }
    netClass(v) { return v > 0 ? "is-up" : v < 0 ? "is-down" : ""; }
    get maxMove() {
        const s = (this.state.data && this.state.data.months) || [];
        return Math.max(1, ...s.map((r) => Math.max(r.j || 0, r.l || 0)));
    }
    barStyle(v, max) {
        return `width: ${Math.max(0, Math.min(100, ((v || 0) * 100) / (max || 1)))}%`;
    }
    rowBarStyle(v) { return `width: ${Math.max(0, Math.min(100, v || 0))}%`; }

    /** Month rows with each quarter's total right after its last month. */
    get monthRows() {
        const D = this.state.data || {};
        const out = [];
        for (const q of D.quarters || []) {
            for (const i of q.months) { out.push({ kind: "m", key: D.months[i].key, row: D.months[i], i }); }
            out.push({ kind: "q", key: q.key, row: q });
        }
        return out;
    }

    // ------------------------------------------------------- the headcount line
    get chart() {
        const D = this.state.data || {};
        const months = D.months || [];
        if (!months.length) { return null; }
        const values = [D.tiles.h0, ...months.map((m) => m.h)];
        let lo = Math.min(...values);
        let hi = Math.max(...values);
        if (hi === lo) { hi += 1; lo = Math.max(0, lo - 1); }
        const pad = Math.max(1, Math.round((hi - lo) * 0.15));
        lo = Math.max(0, lo - pad);
        hi += pad;
        const { w, h, left, right, top, bottom } = CHART;
        const plotW = w - left - right;
        const plotH = h - top - bottom;
        const n = months.length;
        const x = (i) => left + (n === 1 ? plotW / 2 : (i * plotW) / n);
        const y = (v) => top + plotH - ((v - lo) * plotH) / (hi - lo);
        // point 0 is the start of the period (the day before its first month)
        const pts = values.map((v, i) => ({ x: x(i), y: y(v), v }));
        const ticks = [lo, Math.round((lo + hi) / 2), hi].map((v) => ({ v, y: y(v) }));
        const slot = n > 1 ? plotW / n : plotW;
        return {
            w, h, left, right, base: top + plotH,
            path: pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" "),
            ticks,
            points: months.map((m, i) => ({
                i, key: m.key, x: pts[i + 1].x, y: pts[i + 1].y, label: m.short,
                hitX: pts[i + 1].x - slot / 2, hitW: slot,
                // label every month up to 12, every other one beyond
                showLabel: n <= 12 || i % 2 === 0 || i === n - 1,
            })),
            start: pts[0],
        };
    }
    onHover(i) { this.state.hover = i; }
    get hovered() {
        const D = this.state.data || {};
        const i = this.state.hover;
        if (i < 0 || !D.months || !D.months[i]) { return null; }
        const c = this.chart;
        const p = c.points[i];
        return {
            m: D.months[i],
            style: `left: ${(p.x / c.w) * 100}%; top: ${(p.y / c.h) * 100}%;`,
        };
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
