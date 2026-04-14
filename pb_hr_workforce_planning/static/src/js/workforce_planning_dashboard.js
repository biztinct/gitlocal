/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// Chart.js dark-mode defaults
const CHART_COLORS = {
    blue: '#3b82f6',
    green: '#10b981',
    orange: '#d97706',
    red: '#dc2626',
    purple: '#7c3aed',
    cyan: '#0891b2',
    blueAlpha: 'rgba(37, 99, 235, 0.15)',
    greenAlpha: 'rgba(5, 150, 105, 0.15)',
    orangeAlpha: 'rgba(217, 119, 6, 0.15)',
    redAlpha: 'rgba(220, 38, 38, 0.15)',
    purpleAlpha: 'rgba(124, 58, 237, 0.15)',
    cyanAlpha: 'rgba(8, 145, 178, 0.15)',
    text: '#64748b',
    grid: 'rgba(0, 0, 0, 0.04)',
    palette: ['#2563eb', '#059669', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#db2777', '#0d9488'],
    paletteAlpha: ['rgba(37,99,235,0.15)', 'rgba(5,150,105,0.15)', 'rgba(217,119,6,0.15)',
        'rgba(220,38,38,0.15)', 'rgba(124,58,237,0.15)', 'rgba(8,145,178,0.15)',
        'rgba(219,39,119,0.15)', 'rgba(13,148,136,0.15)'],
};

const CHART_DEFAULTS = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 800, easing: 'easeOutQuart' },
    plugins: {
        legend: {
            display: false,
            labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 } },
        },
        tooltip: {
            backgroundColor: '#ffffff',
            titleColor: '#1e293b',
            bodyColor: '#475569',
            borderColor: '#e2e8f0',
            borderWidth: 1,
            cornerRadius: 8,
            padding: 12,
            titleFont: { family: "'Inter', sans-serif", weight: '700', size: 13 },
            bodyFont: { family: "'Inter', sans-serif", size: 12 },
            displayColors: true,
            boxPadding: 4,
        },
    },
    scales: {
        x: {
            grid: { color: CHART_COLORS.grid, drawBorder: false },
            ticks: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 } },
        },
        y: {
            grid: { color: CHART_COLORS.grid, drawBorder: false },
            ticks: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 } },
            beginAtZero: true,
        },
    },
};

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
        this.compareChartRef = useRef("compareChart");

        this.chartInstances = {};

        this.state = useState({
            scenarios: [],
            selectedScenarioId: null,
            dashboardData: null,
            loading: true,
            activeTab: "compensation",
            hasLaborModule: false,
            laborData: null,
            laborLoaded: false,
            searchQuery: "",
            sortField: "increase_amount",
            sortOrder: "desc",
            compareScenarioId: null,
        });

        onWillStart(async () => {
            await this._loadChartJS();
            await this._checkLaborModule();
            await this._loadScenarios();
        });

        onMounted(() => {
            if (this.state.dashboardData) {
                this._renderCharts();
            }
        });
    }

    // ==========================================
    // INIT
    // ==========================================
    async _loadChartJS() {
        if (typeof Chart !== 'undefined') return;
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async _checkLaborModule() {
        try {
            const count = await this.orm.searchCount("ir.module.module", [
                ["name", "=", "pb_hr_workforce"],
                ["state", "=", "installed"],
            ]);
            this.state.hasLaborModule = count > 0;
        } catch {
            this.state.hasLaborModule = false;
        }
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
            setTimeout(() => this._renderCharts(), 150);
        } catch (e) {
            console.error("WFP Dashboard: Error loading data", e);
            this.state.loading = false;
        }
    }

    // ==========================================
    // CHART RENDERING (Chart.js)
    // ==========================================
    _destroyChart(key) {
        if (this.chartInstances[key]) {
            this.chartInstances[key].destroy();
            delete this.chartInstances[key];
        }
    }

    _renderCharts() {
        const data = this.state.dashboardData;
        if (!data || typeof Chart === 'undefined') return;

        this._renderMonthlyChart(data.monthly);
        this._renderDeptChart(data.departments);
        this._renderEmployerChart(data.employees);
    }

    _renderMonthlyChart(monthly) {
        const canvas = this.monthlyChartRef.el;
        if (!canvas || !monthly || monthly.length === 0) return;
        this._destroyChart('monthly');

        const labels = monthly.map(m => m.period);
        const preData = monthly.map(m => m.is_pre ? m.total_cost : null);
        const postData = monthly.map(m => !m.is_pre ? m.total_cost : null);

        this.chartInstances.monthly = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: _t('Current'),
                        data: preData,
                        backgroundColor: CHART_COLORS.cyanAlpha,
                        borderColor: CHART_COLORS.cyan,
                        borderWidth: 2,
                        borderRadius: 6,
                        barPercentage: 0.7,
                    },
                    {
                        label: _t('Forecast'),
                        data: postData,
                        backgroundColor: CHART_COLORS.greenAlpha,
                        borderColor: CHART_COLORS.green,
                        borderWidth: 2,
                        borderRadius: 6,
                        barPercentage: 0.7,
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: true, position: 'top',
                        labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 },
                            usePointStyle: true, pointStyle: 'rectRounded', padding: 16 }
                    },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                const val = ctx.raw || 0;
                                return ` ${ctx.dataset.label}: ${this._formatCompact(val)}`;
                            },
                        },
                    },
                },
                scales: {
                    ...CHART_DEFAULTS.scales,
                    y: {
                        ...CHART_DEFAULTS.scales.y,
                        ticks: {
                            ...CHART_DEFAULTS.scales.y.ticks,
                            callback: (v) => this._formatCompact(v),
                        },
                    },
                },
            },
        });
    }

    _renderDeptChart(departments) {
        const canvas = this.deptChartRef.el;
        if (!canvas || !departments) return;
        this._destroyChart('dept');

        const entries = Object.entries(departments || {});
        if (entries.length === 0) return;

        entries.sort((a, b) => b[1].forecast - a[1].forecast);
        const labels = entries.map(([name]) => name.substring(0, 20));
        const currentData = entries.map(([, d]) => d.current);
        const forecastData = entries.map(([, d]) => d.forecast);

        this.chartInstances.dept = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: _t('Current'),
                        data: currentData,
                        backgroundColor: CHART_COLORS.blueAlpha,
                        borderColor: CHART_COLORS.blue,
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: _t('Forecast'),
                        data: forecastData,
                        backgroundColor: CHART_COLORS.greenAlpha,
                        borderColor: CHART_COLORS.green,
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                indexAxis: 'y',
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: true, position: 'top',
                        labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 },
                            usePointStyle: true, pointStyle: 'rectRounded', padding: 16 }
                    },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => ` ${ctx.dataset.label}: ${this._formatCompact(ctx.raw)}`,
                        },
                    },
                },
                scales: {
                    x: {
                        ...CHART_DEFAULTS.scales.x,
                        ticks: {
                            ...CHART_DEFAULTS.scales.x.ticks,
                            callback: (v) => this._formatCompact(v),
                        },
                    },
                    y: { ...CHART_DEFAULTS.scales.y, beginAtZero: false },
                },
            },
        });
    }

    _renderEmployerChart(employees) {
        const canvas = this.employerChartRef.el;
        if (!canvas || !employees || employees.length === 0) return;
        this._destroyChart('employer');

        const sorted = [...employees]
            .sort((a, b) => (b.forecast_employer - b.current_employer) -
                (a.forecast_employer - a.current_employer))
            .slice(0, 12);

        const labels = sorted.map(e => e.name.split(' ')[0]);
        const deltas = sorted.map(e => e.forecast_employer - e.current_employer);
        const colors = deltas.map(d => d >= 0 ? CHART_COLORS.redAlpha : CHART_COLORS.greenAlpha);
        const borders = deltas.map(d => d >= 0 ? CHART_COLORS.red : CHART_COLORS.green);

        this.chartInstances.employer = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: _t('Cost Change'),
                    data: deltas,
                    backgroundColor: colors,
                    borderColor: borders,
                    borderWidth: 2,
                    borderRadius: 6,
                }],
            },
            options: {
                ...CHART_DEFAULTS,
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                const val = ctx.raw;
                                const sign = val >= 0 ? '+' : '';
                                return ` ${sign}${this._formatCompact(val)}`;
                            },
                        },
                    },
                },
                scales: {
                    ...CHART_DEFAULTS.scales,
                    y: {
                        ...CHART_DEFAULTS.scales.y,
                        beginAtZero: false,
                        ticks: {
                            ...CHART_DEFAULTS.scales.y.ticks,
                            callback: (v) => this._formatCompact(v),
                        },
                    },
                },
            },
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

    async onTabSwitch(tab) {
        this.state.activeTab = tab;
        if (tab === 'labor' && !this.state.laborLoaded) {
            await this._loadLaborData();
        }
        if (tab === 'labor' && this.state.laborData) {
            setTimeout(() => this._renderLaborCharts(), 150);
        }
    }

    async _loadLaborData() {
        try {
            const data = await this.orm.call(
                "wfp.planning.scenario",
                "get_labor_analytics_data",
                [],
                { department_id: false, date_from: false, date_to: false }
            );
            this.state.laborData = data;
            this.state.laborLoaded = true;
            setTimeout(() => this._renderLaborCharts(), 150);
        } catch (e) {
            console.error("WFP: Error loading labor data", e);
        }
    }

    formatMoney(val) {
        if (!val && val !== 0) return '0';
        if (Math.abs(val) >= 1000000) return (val / 1000000).toFixed(1) + 'M';
        if (Math.abs(val) >= 1000) return (val / 1000).toFixed(0) + 'K';
        return Math.round(val).toLocaleString();
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

    async onCompareScenarioChange(ev) {
        const id = parseInt(ev.target.value);
        if (!id) {
            this.state.compareScenarioId = null;
            this._destroyChart('compare');
            return;
        }
        this.state.compareScenarioId = id;
        // Load comparison data
        try {
            const compareData = await this.orm.call(
                "wfp.planning.scenario",
                "get_dashboard_data",
                [id]
            );
            this._renderCompareChart(compareData);
        } catch (e) {
            console.error("WFP: comparison load error", e);
        }
    }

    _renderCompareChart(compareData) {
        const canvas = this.compareChartRef.el;
        if (!canvas) return;
        this._destroyChart('compare');

        const mainData = this.state.dashboardData;
        if (!mainData || !compareData) return;

        const mainDepts = mainData.departments || {};
        const compareDepts = compareData.departments || {};
        const allDepts = [...new Set([...Object.keys(mainDepts), ...Object.keys(compareDepts)])];
        allDepts.sort();

        const mainForecast = allDepts.map(d => (mainDepts[d] || {}).forecast || 0);
        const compareForecast = allDepts.map(d => (compareDepts[d] || {}).forecast || 0);
        const labels = allDepts.map(d => d.substring(0, 15));

        const mainName = this.state.scenarios.find(s => s.id === this.state.selectedScenarioId)?.name || 'Scenario A';
        const compareName = this.state.scenarios.find(s => s.id === this.state.compareScenarioId)?.name || 'Scenario B';

        this.chartInstances.compare = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: mainName,
                        data: mainForecast,
                        backgroundColor: CHART_COLORS.blueAlpha,
                        borderColor: CHART_COLORS.blue,
                        borderWidth: 2,
                        borderRadius: 4,
                    },
                    {
                        label: compareName,
                        data: compareForecast,
                        backgroundColor: CHART_COLORS.purpleAlpha,
                        borderColor: CHART_COLORS.purple,
                        borderWidth: 2,
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: true, position: 'top',
                        labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 },
                            usePointStyle: true, pointStyle: 'rectRounded', padding: 16 }
                    },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => ` ${ctx.dataset.label}: ${this._formatCompact(ctx.raw)}`,
                        },
                    },
                },
                scales: {
                    ...CHART_DEFAULTS.scales,
                    y: {
                        ...CHART_DEFAULTS.scales.y,
                        ticks: {
                            ...CHART_DEFAULTS.scales.y.ticks,
                            callback: (v) => this._formatCompact(v),
                        },
                    },
                },
            },
        });
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

    // ==========================================
    // LABOR CHARTS
    // ==========================================
    _renderLaborCharts() {
        const data = this.state.laborData;
        if (!data || typeof Chart === 'undefined') return;
        this._renderLaborHoursTrend(data.hours_trend);
        this._renderLaborAttendanceDay(data.attendance_by_day);
        this._renderLaborDeptUtil(data.dept_breakdown);
    }

    _renderLaborHoursTrend(trend) {
        const canvas = document.getElementById('laborHoursTrendChart');
        if (!canvas || !trend || !trend.length) return;
        this._destroyChart('laborHours');
        this.chartInstances['laborHours'] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: trend.map(t => t.week),
                datasets: [
                    {
                        label: 'Hours Worked',
                        data: trend.map(t => t.hours),
                        backgroundColor: CHART_COLORS.blueAlpha,
                        borderColor: CHART_COLORS.blue,
                        borderWidth: 2,
                        borderRadius: 6,
                    },
                    {
                        label: 'Target',
                        data: trend.map(t => t.target),
                        type: 'line',
                        borderColor: CHART_COLORS.orange,
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: true, labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 } } },
                },
            },
        });
    }

    _renderLaborAttendanceDay(byDay) {
        const canvas = document.getElementById('laborAttendanceDayChart');
        if (!canvas || !byDay) return;
        this._destroyChart('laborDay');
        const labels = Object.keys(byDay);
        const values = Object.values(byDay);
        this.chartInstances['laborDay'] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Check-ins',
                    data: values,
                    backgroundColor: labels.map((_, i) => CHART_COLORS.palette[i % CHART_COLORS.palette.length]),
                    borderRadius: 8,
                    barPercentage: 0.6,
                }],
            },
            options: CHART_DEFAULTS,
        });
    }

    _renderLaborDeptUtil(depts) {
        const canvas = document.getElementById('laborDeptUtilChart');
        if (!canvas || !depts || !depts.length) return;
        this._destroyChart('laborDept');
        this.chartInstances['laborDept'] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: depts.map(d => d.name),
                datasets: [
                    {
                        label: 'Hours Worked',
                        data: depts.map(d => d.hours),
                        backgroundColor: CHART_COLORS.blueAlpha,
                        borderColor: CHART_COLORS.blue,
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: 'Target Hours',
                        data: depts.map(d => d.target),
                        backgroundColor: CHART_COLORS.orangeAlpha,
                        borderColor: CHART_COLORS.orange,
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                indexAxis: 'y',
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: true, labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 } } },
                },
            },
        });
    }
}

registry.category("actions").add("wfp_dashboard", WfpDashboard);
