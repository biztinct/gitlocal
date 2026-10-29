/** @odoo-module **/
/** One report catalogue and one measure workbench, mounted in each owning hub. */
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { openHub } from "@pb_hub/js/hub_nav";
import { ic } from "@pb_import_kit/js/import_icons";
import { PbInsights } from "@pb_insights/js/insights";

export const MODULE_INSIGHT_HOMES = {
    people: { xmlid: "pb_people_hub.action_pb_people_hub", lens: "insights", label: "People" },
    workforce: { xmlid: "pb_mission.action_pb_workforce", lens: "insights", lensKey: "pb_shell_lens", label: "Workforce" },
    expenses: { xmlid: "pb_expenses_hub.action_pb_expenses_hub", lens: "insights", label: "Expenses" },
    hiring: { xmlid: "pb_hiring.action_pb_hiring_hub", lens: "numbers", label: "Hiring" },
    talent: { xmlid: "pb_talent_hub.action_pb_talent_hub", lens: "goal_numbers", label: "Talent" },
    learning: { xmlid: "pb_learning_hub.action_pb_learning_hub", lens: "numbers", label: "Learning" },
    payroll: { xmlid: "pb_payhub.action_pb_pay_hub", lens: "insights", label: "Payroll" },
    all: { xmlid: "pb_insights_hub.action_pb_insights_hub", lens: "reports", label: "Insights" },
};

export class PbModuleInsights extends Component {
    static template = "pb_insights.PbModuleInsights";
    static components = { PbInsights };
    static props = {
        area: String,
        embedded: { type: Boolean, optional: true },
        startTab: { type: String, optional: true },
        explorerComponent: { optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            tab: this.props.startTab || "overview", busy: true, error: "",
            measure: "", dimension: "", over: "month", months: 6,
            measures: [], catalogue: [], overview: [], result: null,
            chart: "bars", search: "",
        });
        this.request = 0;
        onWillStart(() => this.initialize());
    }

    get area() { return this.props.area; }
    get isPayroll() { return this.area === "payroll"; }
    get isCatalogue() { return this.area === "all"; }
    get selectedMeasure() {
        return this.state.measures.find((m) => m.key === this.state.measure) || null;
    }
    get dimensions() { return this.selectedMeasure?.dimensions || []; }
    get visibleReports() {
        const query = this.state.search.trim().toLowerCase();
        return this.state.catalogue.filter((r) =>
            !query || `${r.label} ${r.area}`.toLowerCase().includes(query));
    }
    get chartRows() { return (this.state.result?.rows || []).slice(0, 24); }
    get hiddenRows() { return Math.max(0, (this.state.result?.rows || []).length - 24); }
    get chartMax() { return Math.max(1, ...this.chartRows.map((r) => Math.abs(r.value))); }
    get title() { return MODULE_INSIGHT_HOMES[this.area]?.label || _t("Insights"); }

    icon(name, size = 17) { return ic(name, size); }
    width(value) { return `${Math.max(2, Math.abs(value) / this.chartMax * 100)}%`; }
    number(value, kind = "count", currency = "") {
        if (value === null || value === undefined) { return "—"; }
        const formatted = new Intl.NumberFormat(undefined, {
            maximumFractionDigits: kind === "rate" || kind === "avg" ? 1 : 0,
        }).format(value);
        return kind === "rate" || kind === "avg" ? `${formatted}%`
            : currency ? `${formatted} ${currency}` : formatted;
    }

    async initialize() {
        const token = ++this.request;
        try {
            const catalogue = await this.orm.call("pb.module.insights", "catalogue", [this.area]);
            if (token !== this.request) { return; }
            this.state.catalogue = catalogue;
            if (this.isCatalogue) { this.state.busy = false; return; }
            const meta = await this.orm.call("pb.module.insights", "measures", [this.area]);
            if (token !== this.request) { return; }
            this.state.measures = meta.measures || [];
            this.state.measure = this.state.measures[0]?.key || "";
            this.state.dimension = this.state.measures[0]?.dimensions[0] || "";
            this.state.over = this.state.measures[0]?.has_time ? "month" : "total";
            if (!this.isPayroll) {
                const overview = await this.orm.call("pb.module.insights", "overview", [this.area]);
                if (token !== this.request) { return; }
                this.state.overview = overview.tiles || [];
                if (this.state.tab === "explorer") { await this.loadExplorer(); }
            }
        } catch (error) {
            console.warn("module Insights could not load", error);
            this.state.error = _t("The insights could not be read. Try refreshing this page.");
        } finally {
            if (token === this.request) { this.state.busy = false; }
        }
    }

    async selectTab(tab) {
        this.state.tab = tab;
        if (tab === "explorer" && !this.isPayroll && !this.state.result) {
            await this.loadExplorer();
        }
    }
    async changeMeasure(ev) {
        this.state.measure = ev.target.value;
        this.state.dimension = this.dimensions[0] || "";
        this.state.over = this.selectedMeasure?.has_time ? "month" : "total";
        await this.loadExplorer();
    }
    async changeDimension(ev) { this.state.dimension = ev.target.value; await this.loadExplorer(); }
    async changeOver(ev) { this.state.over = ev.target.value; await this.loadExplorer(); }
    async changeMonths(ev) { this.state.months = Number(ev.target.value); await this.loadExplorer(); }

    async loadExplorer() {
        if (!this.state.measure) { return; }
        const token = ++this.request;
        this.state.busy = true;
        this.state.error = "";
        try {
            const result = await this.orm.call("pb.module.insights", "explore", [
                this.area, this.state.measure, this.state.dimension,
                this.state.over, this.state.months,
            ]);
            if (token === this.request) { this.state.result = result; }
        } catch (error) {
            if (token === this.request) {
                this.state.result = null;
                this.state.error = error?.data?.message ||
                    _t("This view could not be read. Try another measure or period.");
            }
        } finally {
            if (token === this.request) { this.state.busy = false; }
        }
    }

    openReport(report) {
        const home = MODULE_INSIGHT_HOMES[this.area];
        const back = { label: home.label, xmlid: home.xmlid, lens: home.lens,
                       lensKey: home.lensKey || "pb_lens" };
        openHub(this.actionService, {
            xmlid: report.xmlid, lens: report.lens || undefined,
            lensKey: report.xmlid === "pb_mission.action_pb_workforce" ? "pb_shell_lens" : "pb_lens",
            back,
        });
    }
}
