/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

class WfpDashboard extends Component {
    static template = "pb_hr_workforce_planning.WfpDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.monthlyChartRef = useRef("monthlyChart");
        this.deptChartRef = useRef("deptChart");
        this.employerChartRef = useRef("employerChart");

        this.state = useState({
            scenarios: [],
            selectedScenarioId: null,
            dashboardData: null,
            loading: true,
            compareMode: false,
            searchQuery: "",
            sortField: "increase_amount",
            sortOrder: "desc",
        });

        onWillStart(async () => {
            await this._loadScenarios();
        });

        onMounted(() => {
            if (this.state.dashboardData) {
                this._renderCharts();
            }
        });
    }

    // ==========================================
    // DATA LOADING
    // ==========================================
    async _loadScenarios() {
        try {
            const scenarios = await this.orm.searchRead(
                "wfp.planning.scenario",
                [["state", "in", ["calculated", "approved"]]],
                ["id", "name", "state", "fiscal_year", "headcount",
                 "total_increase_pct", "formula_config_id"],
                { order: "create_date desc", limit: 50 }
            );
            this.state.scenarios = scenarios;
            if (scenarios.length > 0 && !this.state.selectedScenarioId) {
                await this._selectScenario(scenarios[0].id);
            } else {
                this.state.loading = false;
            }
        } catch (e) {
            console.error("WFP Dashboard: Error loading scenarios", e);
            this.state.loading = false;
        }
    }

    async _selectScenario(scenarioId) {
        this.state.loading = true;
        this.state.selectedScenarioId = scenarioId;
        try {
            const data = await this.orm.call(
                "wfp.planning.scenario",
                "get_dashboard_data",
                [scenarioId]
            );
            this.state.dashboardData = data;
            this.state.loading = false;
            // Re-render charts after state update
            setTimeout(() => this._renderCharts(), 100);
        } catch (e) {
            console.error("WFP Dashboard: Error loading data", e);
            this.state.loading = false;
        }
    }

    // ==========================================
    // CHART RENDERING
    // ==========================================
    _renderCharts() {
        const data = this.state.dashboardData;
        if (!data) return;

        this._renderMonthlyChart(data.monthly);
        this._renderDeptChart(data.departments);
        this._renderEmployerChart(data.employees);
    }

    _renderMonthlyChart(monthly) {
        const canvas = this.monthlyChartRef.el;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        // Simple canvas chart — monthly cost bars
        const W = canvas.width = canvas.parentElement.clientWidth;
        const H = canvas.height = 280;
        ctx.clearRect(0, 0, W, H);

        if (!monthly || monthly.length === 0) return;

        const maxVal = Math.max(...monthly.map(m => m.total_cost)) || 1;
        const barW = (W - 80) / monthly.length;
        const chartH = H - 60;

        // Gradient background
        const grad = ctx.createLinearGradient(0, 0, 0, H);
        grad.addColorStop(0, "rgba(33, 67, 95, 0.02)");
        grad.addColorStop(1, "rgba(33, 67, 95, 0.08)");
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, W, H);

        monthly.forEach((m, i) => {
            const x = 50 + i * barW;
            const h = (m.total_cost / maxVal) * chartH;
            const y = chartH - h + 20;

            // Bar
            const barGrad = ctx.createLinearGradient(x, y, x, y + h);
            if (m.is_pre) {
                barGrad.addColorStop(0, "rgba(33, 67, 95, 0.6)");
                barGrad.addColorStop(1, "rgba(33, 67, 95, 0.3)");
            } else {
                barGrad.addColorStop(0, "rgba(39, 174, 96, 0.8)");
                barGrad.addColorStop(1, "rgba(39, 174, 96, 0.4)");
            }
            ctx.fillStyle = barGrad;
            ctx.beginPath();
            ctx.roundRect(x + 4, y, barW - 8, h, [4, 4, 0, 0]);
            ctx.fill();

            // Label
            ctx.fillStyle = "#666";
            ctx.font = "10px Inter, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText(m.period, x + barW / 2, H - 8);
        });

        // Y-axis labels
        ctx.fillStyle = "#999";
        ctx.font = "10px Inter, sans-serif";
        ctx.textAlign = "right";
        for (let i = 0; i <= 4; i++) {
            const val = (maxVal / 4) * i;
            const y = chartH - (val / maxVal) * chartH + 20;
            ctx.fillText(this._formatCompact(val), 45, y + 4);
            ctx.strokeStyle = "rgba(0,0,0,0.05)";
            ctx.beginPath();
            ctx.moveTo(50, y);
            ctx.lineTo(W - 10, y);
            ctx.stroke();
        }
    }

    _renderDeptChart(departments) {
        const canvas = this.deptChartRef.el;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        const W = canvas.width = canvas.parentElement.clientWidth;
        const entries = Object.entries(departments || {});
        const H = canvas.height = Math.max(200, entries.length * 40 + 40);

        ctx.clearRect(0, 0, W, H);
        if (entries.length === 0) return;

        const maxVal = Math.max(...entries.map(([, d]) => Math.max(d.current, d.forecast))) || 1;
        const barH = 14;

        entries.sort((a, b) => b[1].forecast - a[1].forecast);
        entries.forEach(([dept, data], i) => {
            const y = 20 + i * 40;

            // Dept label
            ctx.fillStyle = "#333";
            ctx.font = "11px Inter, sans-serif";
            ctx.textAlign = "left";
            ctx.fillText(dept.substring(0, 25), 10, y);

            // Current bar
            const barArea = W - 200;
            const cw = (data.current / maxVal) * barArea;
            ctx.fillStyle = "rgba(33, 67, 95, 0.4)";
            ctx.beginPath();
            ctx.roundRect(180, y + 4, cw, barH, 3);
            ctx.fill();

            // Forecast bar
            const fw = (data.forecast / maxVal) * barArea;
            ctx.fillStyle = "rgba(39, 174, 96, 0.6)";
            ctx.beginPath();
            ctx.roundRect(180, y + 4 + barH + 2, fw, barH, 3);
            ctx.fill();

            // Values
            ctx.fillStyle = "#999";
            ctx.font = "9px Inter, sans-serif";
            ctx.textAlign = "left";
            ctx.fillText(this._formatCompact(data.current), 180 + cw + 4, y + 15);
            ctx.fillText(this._formatCompact(data.forecast), 180 + fw + 4, y + 31);
        });
    }

    _renderEmployerChart(employees) {
        const canvas = this.employerChartRef.el;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        const W = canvas.width = canvas.parentElement.clientWidth;
        const H = canvas.height = 200;
        ctx.clearRect(0, 0, W, H);

        if (!employees || employees.length === 0) return;

        // Top 10 by employer cost increase
        const sorted = [...employees]
            .sort((a, b) => (b.forecast_employer - b.current_employer) - (a.forecast_employer - a.current_employer))
            .slice(0, 10);

        const maxDelta = Math.max(...sorted.map(e => Math.abs(e.forecast_employer - e.current_employer))) || 1;
        const barW = (W - 60) / sorted.length;

        sorted.forEach((emp, i) => {
            const delta = emp.forecast_employer - emp.current_employer;
            const x = 40 + i * barW;
            const h = Math.abs(delta / maxDelta) * (H - 60);
            const y = delta >= 0 ? H - 40 - h : H - 40;

            ctx.fillStyle = delta >= 0 ? "rgba(231, 76, 60, 0.6)" : "rgba(39, 174, 96, 0.6)";
            ctx.beginPath();
            ctx.roundRect(x + 2, y, barW - 4, h, 3);
            ctx.fill();

            ctx.fillStyle = "#999";
            ctx.font = "9px Inter, sans-serif";
            ctx.textAlign = "center";
            const name = emp.name.split(" ")[0].substring(0, 8);
            ctx.fillText(name, x + barW / 2, H - 8);
        });
    }

    // ==========================================
    // HELPERS
    // ==========================================
    _formatCurrency(value) {
        if (value === undefined || value === null) return "0";
        return new Intl.NumberFormat(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(value);
    }

    _formatCompact(value) {
        if (!value) return "0";
        if (Math.abs(value) >= 1e9) return (value / 1e9).toFixed(1) + "B";
        if (Math.abs(value) >= 1e6) return (value / 1e6).toFixed(1) + "M";
        if (Math.abs(value) >= 1e3) return (value / 1e3).toFixed(1) + "K";
        return value.toFixed(0);
    }

    _formatPct(value) {
        return (value || 0).toFixed(2) + "%";
    }

    get filteredEmployees() {
        const data = this.state.dashboardData;
        if (!data || !data.employees) return [];

        let list = [...data.employees];
        const q = (this.state.searchQuery || "").toLowerCase();
        if (q) {
            list = list.filter(e =>
                e.name.toLowerCase().includes(q) ||
                e.department.toLowerCase().includes(q) ||
                e.job.toLowerCase().includes(q) ||
                e.rule_name.toLowerCase().includes(q)
            );
        }

        const field = this.state.sortField;
        const dir = this.state.sortOrder === "asc" ? 1 : -1;
        list.sort((a, b) => {
            const av = a[field] || 0;
            const bv = b[field] || 0;
            if (typeof av === "string") return av.localeCompare(bv) * dir;
            return (av - bv) * dir;
        });

        return list;
    }

    // ==========================================
    // ACTIONS
    // ==========================================
    onScenarioChange(ev) {
        const id = parseInt(ev.target.value);
        if (id) this._selectScenario(id);
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
    }

    onSort(field) {
        if (this.state.sortField === field) {
            this.state.sortOrder = this.state.sortOrder === "asc" ? "desc" : "asc";
        } else {
            this.state.sortField = field;
            this.state.sortOrder = "desc";
        }
    }

    async onNewScenario() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "wfp.planning.scenario",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onExport() {
        if (!this.state.selectedScenarioId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "wfp.export.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_scenario_id: this.state.selectedScenarioId,
            },
        });
    }

    async onTagComponents() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "wfp.tagging.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
        });
    }

    onViewScenario() {
        if (!this.state.selectedScenarioId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "wfp.planning.scenario",
            res_id: this.state.selectedScenarioId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("wfp_dashboard", WfpDashboard);
