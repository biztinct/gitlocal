/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { loadBundle } from "@web/core/assets";

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
        this.budgetTimelineRef = useRef("budgetTimelineChart");
        this.budgetDeptRef = useRef("budgetDeptChart");
        this.budgetGaugeRef = useRef("budgetGaugeChart");
        this.scatterRef = useRef("scatterChart");
        this.waterfallRef = useRef("waterfallChart");
        this.perfDistRef = useRef("perfDistChart");
        this.gradeDistRef = useRef("gradeDistChart");
        this.otBreakdownRef = useRef("otBreakdownChart");
        this.laborForecastRef = useRef("laborForecastChart");
        this.absenceRef = useRef("absenceChart");

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
            budgetData: null,
            budgetLoaded: false,
            analyticsData: null,
            analyticsLoaded: false,
            demandData: null,
            demandLoaded: false,
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
    // Chart.js ships with Odoo in the LAZY `web.chartjs_lib` bundle. Injecting
    // a jsDelivr <script> instead sent every dashboard visit to a third party,
    // broke on any offline install, and pinned a version we do not control.
    async _loadChartJS() {
        if (typeof Chart !== 'undefined') return;
        await loadBundle("web.chartjs_lib");
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
        if (tab === 'budget' && !this.state.budgetLoaded && this.state.selectedScenarioId) {
            await this._loadBudgetData();
        }
        if (tab === 'budget' && this.state.budgetData) {
            setTimeout(() => this._renderBudgetCharts(), 150);
        }
        if (tab === 'analytics' && !this.state.analyticsLoaded && this.state.selectedScenarioId) {
            await this._loadAnalyticsData();
        }
        if (tab === 'analytics' && this.state.analyticsData) {
            setTimeout(() => this._renderAnalyticsCharts(), 150);
        }
        if (tab === 'demand' && !this.state.demandLoaded) {
            await this._loadDemandData();
        }
        if (tab === 'demand' && this.state.demandData) {
            setTimeout(() => this._renderDemandCharts(), 150);
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
        this._renderOtBreakdown(data.ot_breakdown);
        this._renderLaborForecast(data.labor_forecast);
        this._renderAbsenceImpact(data.absence_impact);
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
                        label: _t('Hours Worked'),
                        data: trend.map(t => t.hours),
                        backgroundColor: CHART_COLORS.blueAlpha,
                        borderColor: CHART_COLORS.blue,
                        borderWidth: 2,
                        borderRadius: 6,
                    },
                    {
                        label: _t('Target'),
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
                    label: _t('Check-ins'),
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
                        label: _t('Hours Worked'),
                        data: depts.map(d => d.hours),
                        backgroundColor: CHART_COLORS.blueAlpha,
                        borderColor: CHART_COLORS.blue,
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: _t('Target Hours'),
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

    _renderOtBreakdown(otData) {
        const canvas = this.otBreakdownRef.el;
        if (!canvas || !otData || otData.length === 0) return;
        this._destroyChart('otBreakdown');

        this.chartInstances.otBreakdown = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: otData.map(o => o.type),
                datasets: [
                    {
                        label: _t('OT Hours'),
                        data: otData.map(o => o.hours),
                        backgroundColor: [CHART_COLORS.blueAlpha, CHART_COLORS.orangeAlpha],
                        borderColor: [CHART_COLORS.blue, CHART_COLORS.orange],
                        borderWidth: 2,
                        borderRadius: 8,
                        yAxisID: 'y',
                    },
                    {
                        label: _t('OT Cost'),
                        data: otData.map(o => o.cost),
                        type: 'line',
                        borderColor: CHART_COLORS.red,
                        backgroundColor: CHART_COLORS.redAlpha,
                        borderWidth: 2,
                        pointRadius: 5,
                        fill: true,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: true, labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 } } },
                },
                scales: {
                    ...CHART_DEFAULTS.scales,
                    y: { ...CHART_DEFAULTS.scales.y, title: { display: true, text: 'Hours', color: CHART_COLORS.text } },
                    y1: { ...CHART_DEFAULTS.scales.y, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Cost', color: CHART_COLORS.text }, ticks: { ...CHART_DEFAULTS.scales.y.ticks, callback: (v) => this._formatCurrency(v) } },
                },
            },
        });
    }

    _renderLaborForecast(forecast) {
        const canvas = this.laborForecastRef.el;
        if (!canvas || !forecast || forecast.length === 0) return;
        this._destroyChart('laborForecast');

        this.chartInstances.laborForecast = new Chart(canvas, {
            type: 'line',
            data: {
                labels: forecast.map(f => f.date),
                datasets: [
                    {
                        label: _t('Upper Bound'),
                        data: forecast.map(f => f.upper),
                        borderColor: 'transparent',
                        backgroundColor: CHART_COLORS.blueAlpha,
                        fill: '+1',
                        pointRadius: 0,
                    },
                    {
                        label: _t('Projected Cost'),
                        data: forecast.map(f => f.projected),
                        borderColor: CHART_COLORS.blue,
                        backgroundColor: CHART_COLORS.blueAlpha,
                        borderWidth: 3,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        fill: false,
                        tension: 0.3,
                    },
                    {
                        label: _t('Lower Bound'),
                        data: forecast.map(f => f.lower),
                        borderColor: 'transparent',
                        backgroundColor: CHART_COLORS.blueAlpha,
                        fill: '-1',
                        pointRadius: 0,
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: false },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                const f = forecast[ctx.dataIndex];
                                return [
                                    `Projected: ${this.formatMoney(f.projected)}`,
                                    `Range: ${this.formatMoney(f.lower)} - ${this.formatMoney(f.upper)}`,
                                ];
                            },
                        },
                    },
                },
                scales: {
                    ...CHART_DEFAULTS.scales,
                    y: {
                        ...CHART_DEFAULTS.scales.y,
                        ticks: { ...CHART_DEFAULTS.scales.y.ticks, callback: (v) => this._formatCurrency(v) },
                    },
                },
            },
        });
    }

    _renderAbsenceImpact(absence) {
        const canvas = this.absenceRef.el;
        if (!canvas || !absence || absence.length === 0) return;
        this._destroyChart('absence');

        this.chartInstances.absence = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: absence.map(a => a.type),
                datasets: [{
                    data: absence.map(a => a.days),
                    backgroundColor: absence.map((_, i) => CHART_COLORS.palette[i % CHART_COLORS.palette.length]),
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'right',
                        labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 }, usePointStyle: true, padding: 12 },
                    },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                const a = absence[ctx.dataIndex];
                                return [
                                    `${a.days} days (${a.count} requests)`,
                                    `Cost Impact: ${this.formatMoney(a.cost_impact)}`,
                                ];
                            },
                        },
                    },
                },
            },
        });
    }

    // ==========================================
    // PHASE G: WORKFORCE DEMAND & TALENT TAB
    // ==========================================
    async _loadDemandData() {
        try {
            const data = await this.orm.call(
                "wfp.planning.scenario",
                "get_workforce_demand_data",
                []
            );
            this.state.demandData = data;
            this.state.demandLoaded = true;
            setTimeout(() => this._renderDemandCharts(), 150);
        } catch (e) {
            console.error("WFP: Error loading demand data", e);
        }
    }

    _renderDemandCharts() {
        const data = this.state.demandData;
        if (!data || typeof Chart === 'undefined') return;
        this._renderRecruitmentFunnel(data.pipeline);
        this._renderSkillsGap(data.skills);
        this._renderDeptRecruitment(data.dept_recruitment);
    }

    _renderRecruitmentFunnel(pipeline) {
        const canvas = document.getElementById('recruitmentFunnelChart');
        if (!canvas || !pipeline || pipeline.length === 0) return;
        this._destroyChart('recruitFunnel');

        // Funnel = horizontal bar sorted by stage sequence (already sorted)
        this.chartInstances.recruitFunnel = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: pipeline.map(p => p.stage),
                datasets: [{
                    label: _t('Applicants'),
                    data: pipeline.map(p => p.count),
                    backgroundColor: pipeline.map((_, i) => {
                        const hue = 220 - (i * 30);
                        return `hsla(${hue}, 80%, 55%, 0.7)`;
                    }),
                    borderColor: pipeline.map((_, i) => {
                        const hue = 220 - (i * 30);
                        return `hsl(${hue}, 80%, 55%)`;
                    }),
                    borderWidth: 2,
                    borderRadius: 6,
                    barPercentage: 0.7,
                }],
            },
            options: {
                ...CHART_DEFAULTS,
                indexAxis: 'y',
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: false },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                const p = pipeline[ctx.dataIndex];
                                return `${p.count} applicants (${p.pct}%)`;
                            },
                        },
                    },
                },
            },
        });
    }

    _renderSkillsGap(skills) {
        const canvas = document.getElementById('skillsGapChart');
        if (!canvas || !skills || skills.length === 0) return;
        this._destroyChart('skillsGap');

        this.chartInstances.skillsGap = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: skills.slice(0, 12).map(s => s.skill),
                datasets: [{
                    label: _t('Coverage %'),
                    data: skills.slice(0, 12).map(s => s.coverage_pct),
                    backgroundColor: skills.slice(0, 12).map(s => {
                        if (s.coverage_pct >= 50) return CHART_COLORS.greenAlpha;
                        if (s.coverage_pct >= 25) return CHART_COLORS.orangeAlpha;
                        return CHART_COLORS.redAlpha;
                    }),
                    borderColor: skills.slice(0, 12).map(s => {
                        if (s.coverage_pct >= 50) return CHART_COLORS.green;
                        if (s.coverage_pct >= 25) return CHART_COLORS.orange;
                        return CHART_COLORS.red;
                    }),
                    borderWidth: 2,
                    borderRadius: 6,
                    barPercentage: 0.6,
                }],
            },
            options: {
                ...CHART_DEFAULTS,
                indexAxis: 'y',
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: false },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                const s = skills[ctx.dataIndex];
                                return `${s.employees} employees (${s.coverage_pct}% coverage)`;
                            },
                        },
                    },
                },
                scales: {
                    ...CHART_DEFAULTS.scales,
                    x: {
                        ...CHART_DEFAULTS.scales.x,
                        max: 100,
                        ticks: { ...CHART_DEFAULTS.scales.x.ticks, callback: v => v + '%' },
                    },
                },
            },
        });
    }

    _renderDeptRecruitment(deptData) {
        const canvas = document.getElementById('deptRecruitmentChart');
        if (!canvas || !deptData || deptData.length === 0) return;
        this._destroyChart('deptRecruit');

        this.chartInstances.deptRecruit = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: deptData.map(d => d.department),
                datasets: [{
                    data: deptData.map(d => d.count),
                    backgroundColor: deptData.map((_, i) => CHART_COLORS.palette[i % CHART_COLORS.palette.length]),
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'right',
                        labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 }, usePointStyle: true, padding: 12 },
                    },
                    tooltip: CHART_DEFAULTS.plugins.tooltip,
                },
            },
        });
    }

    // ==========================================
    // PHASE C: BUDGET & ACTUALS TAB
    // ==========================================
    async _loadBudgetData() {
        if (!this.state.selectedScenarioId) return;
        try {
            const data = await this.orm.call(
                "wfp.planning.scenario",
                "get_budget_vs_actual_data",
                [this.state.selectedScenarioId]
            );
            this.state.budgetData = data;
            this.state.budgetLoaded = true;
            setTimeout(() => this._renderBudgetCharts(), 150);
        } catch (e) {
            console.error("WFP: Error loading budget data", e);
        }
    }

    _renderBudgetCharts() {
        const data = this.state.budgetData;
        if (!data || typeof Chart === 'undefined') return;
        this._renderBudgetTimeline(data.months);
        this._renderBudgetDeptBreakdown(data.departments);
        this._renderBudgetGauge(data.summary);
    }

    _renderBudgetTimeline(months) {
        const canvas = this.budgetTimelineRef.el;
        if (!canvas || !months || months.length === 0) return;
        this._destroyChart('budgetTimeline');

        this.chartInstances.budgetTimeline = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: months.map(m => m.period),
                datasets: [
                    {
                        label: _t('Forecast'),
                        data: months.map(m => m.forecast_cost),
                        backgroundColor: CHART_COLORS.blueAlpha,
                        borderColor: CHART_COLORS.blue,
                        borderWidth: 2,
                        borderRadius: 6,
                        order: 2,
                    },
                    {
                        label: _t('Actual'),
                        data: months.map(m => m.actual_cost),
                        backgroundColor: months.map(m =>
                            m.variance >= 0 ? CHART_COLORS.greenAlpha : CHART_COLORS.redAlpha
                        ),
                        borderColor: months.map(m =>
                            m.variance >= 0 ? CHART_COLORS.green : CHART_COLORS.red
                        ),
                        borderWidth: 2,
                        borderRadius: 6,
                        order: 1,
                    },
                    {
                        label: _t('Variance'),
                        type: 'line',
                        data: months.map(m => m.variance),
                        borderColor: CHART_COLORS.orange,
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [6, 3],
                        pointRadius: 4,
                        pointBackgroundColor: CHART_COLORS.orange,
                        tension: 0.3,
                        yAxisID: 'y1',
                        order: 0,
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: {
                        display: true,
                        labels: {
                            color: CHART_COLORS.text,
                            font: { family: "'Inter', sans-serif", size: 11 },
                            usePointStyle: true,
                            pointStyle: 'rectRounded',
                        },
                    },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                const val = ctx.raw || 0;
                                return `${ctx.dataset.label}: ${this.formatMoney(val)}`;
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
                            callback: (v) => this._formatCurrency(v),
                        },
                    },
                    y1: {
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: {
                            color: CHART_COLORS.orange,
                            font: { family: "'Inter', sans-serif", size: 11 },
                            callback: (v) => this._formatCurrency(v),
                        },
                    },
                },
            },
        });
    }

    _renderBudgetDeptBreakdown(departments) {
        const canvas = this.budgetDeptRef.el;
        if (!canvas || !departments || departments.length === 0) return;
        this._destroyChart('budgetDept');

        const labels = departments.map(d => d.name.substring(0, 20));
        this.chartInstances.budgetDept = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Forecast',
                        data: departments.map(d => d.forecast),
                        backgroundColor: CHART_COLORS.blueAlpha,
                        borderColor: CHART_COLORS.blue,
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: 'Actual',
                        data: departments.map(d => d.actual),
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
                    legend: {
                        display: true,
                        labels: { color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 11 } },
                    },
                },
                scales: {
                    ...CHART_DEFAULTS.scales,
                    x: {
                        ...CHART_DEFAULTS.scales.x,
                        ticks: {
                            ...CHART_DEFAULTS.scales.x.ticks,
                            callback: (v) => this._formatCurrency(v),
                        },
                    },
                },
            },
        });
    }

    _renderBudgetGauge(summary) {
        const canvas = this.budgetGaugeRef.el;
        if (!canvas || !summary) return;
        this._destroyChart('budgetGauge');

        const budget = summary.scenario_budget || 0;
        const actual = summary.total_actual || 0;
        const forecast = summary.total_forecast || 0;
        const utilization = budget > 0 ? Math.min((actual / budget) * 100, 120) : 0;
        const remaining = Math.max(100 - utilization, 0);

        this.chartInstances.budgetGauge = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: ['Spent', 'Remaining'],
                datasets: [{
                    data: [utilization, remaining],
                    backgroundColor: [
                        utilization > 100 ? CHART_COLORS.red :
                        utilization > 85 ? CHART_COLORS.orange : CHART_COLORS.green,
                        'rgba(0,0,0,0.05)',
                    ],
                    borderWidth: 0,
                    cutout: '75%',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false },
                },
            },
            plugins: [{
                id: 'gaugeLabel',
                afterDraw: (chart) => {
                    const { ctx, width, height } = chart;
                    ctx.save();
                    const pct = summary.budget_utilization || 0;
                    ctx.font = `700 28px 'Inter', sans-serif`;
                    ctx.fillStyle = '#1e293b';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(`${pct.toFixed(1)}%`, width / 2, height / 2 - 8);
                    ctx.font = `400 12px 'Inter', sans-serif`;
                    ctx.fillStyle = '#64748b';
                    ctx.fillText('Budget Used', width / 2, height / 2 + 16);
                    ctx.restore();
                },
            }],
        });
    }

    // ==========================================
    // PHASE D: ANALYTICS TAB
    // ==========================================
    async _loadAnalyticsData() {
        if (!this.state.selectedScenarioId) return;
        try {
            const data = await this.orm.call(
                "wfp.planning.scenario",
                "get_advanced_analytics_data",
                [this.state.selectedScenarioId]
            );
            this.state.analyticsData = data;
            this.state.analyticsLoaded = true;
            setTimeout(() => this._renderAnalyticsCharts(), 150);
        } catch (e) {
            console.error("WFP: Error loading analytics data", e);
        }
    }

    _renderAnalyticsCharts() {
        const data = this.state.analyticsData;
        if (!data || typeof Chart === 'undefined') return;
        this._renderScatterChart(data.scatter);
        this._renderWaterfallChart(data.waterfall);
        this._renderPerfDistChart(data.performance);
        this._renderGradeDistChart(data.grades);
    }

    _renderScatterChart(scatter) {
        const canvas = this.scatterRef.el;
        if (!canvas || !scatter || scatter.length === 0) return;
        this._destroyChart('scatter');

        // Color by performance rating
        const getColor = (perf) => {
            if (perf >= 4) return CHART_COLORS.green;
            if (perf >= 3) return CHART_COLORS.blue;
            if (perf >= 2) return CHART_COLORS.orange;
            return CHART_COLORS.red;
        };

        const points = scatter.map(s => ({
            x: s.compa_ratio,
            y: s.increase_pct,
            name: s.name,
            dept: s.department,
            perf: s.performance,
        }));

        this.chartInstances.scatter = new Chart(canvas, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: _t('Employees'),
                    data: points,
                    backgroundColor: points.map(p => {
                        const c = getColor(p.perf);
                        return c.replace(')', ', 0.6)').replace('rgb', 'rgba');
                    }),
                    borderColor: points.map(p => getColor(p.perf)),
                    borderWidth: 1.5,
                    pointRadius: 6,
                    pointHoverRadius: 9,
                }],
            },
            options: {
                ...CHART_DEFAULTS,
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: false },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            title: (items) => items[0]?.raw?.name || '',
                            label: (ctx) => {
                                const p = ctx.raw;
                                return [
                                    `Department: ${p.dept}`,
                                    `Compa Ratio: ${p.x}`,
                                    `Increase: ${p.y}%`,
                                    `Performance: ${p.perf || 'N/A'}`,
                                ];
                            },
                        },
                    },
                    annotation: undefined,
                },
                scales: {
                    x: {
                        ...CHART_DEFAULTS.scales.x,
                        title: { display: true, text: 'Compa Ratio', color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 12, weight: '600' } },
                        min: 0,
                        suggestedMax: 2,
                    },
                    y: {
                        ...CHART_DEFAULTS.scales.y,
                        title: { display: true, text: 'Increase %', color: CHART_COLORS.text, font: { family: "'Inter', sans-serif", size: 12, weight: '600' } },
                    },
                },
            },
        });
    }

    _renderWaterfallChart(waterfall) {
        const canvas = this.waterfallRef.el;
        if (!canvas || !waterfall) return;
        this._destroyChart('waterfall');

        const labels = [_t('Current Total'), _t('+ Base Δ'), _t('+ Allowance Δ'), _t('+ Employer Δ'), _t('Forecast Total')];
        const d = waterfall.delta;
        const cumulative = [
            waterfall.current.total,
            waterfall.current.total + d.base,
            waterfall.current.total + d.base + d.allowances,
            waterfall.current.total + d.base + d.allowances + d.employer,
            waterfall.forecast.total,
        ];

        // For waterfall: invisible base + visible segment
        const base = [0, waterfall.current.total, cumulative[1], cumulative[2], 0];
        const visible = [
            waterfall.current.total,
            d.base,
            d.allowances,
            d.employer,
            waterfall.forecast.total,
        ];

        this.chartInstances.waterfall = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: _t('Base'),
                        data: base,
                        backgroundColor: 'transparent',
                        borderWidth: 0,
                        stack: 'waterfall',
                    },
                    {
                        label: _t('Amount'),
                        data: visible.map(v => Math.abs(v)),
                        backgroundColor: [
                            CHART_COLORS.blue,
                            d.base >= 0 ? CHART_COLORS.green : CHART_COLORS.red,
                            d.allowances >= 0 ? CHART_COLORS.green : CHART_COLORS.red,
                            d.employer >= 0 ? CHART_COLORS.green : CHART_COLORS.red,
                            CHART_COLORS.purple,
                        ],
                        borderRadius: 4,
                        stack: 'waterfall',
                    },
                ],
            },
            options: {
                ...CHART_DEFAULTS,
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: false },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                if (ctx.datasetIndex === 0) return '';
                                return `${ctx.label}: ${this.formatMoney(visible[ctx.dataIndex])}`;
                            },
                        },
                        filter: (item) => item.datasetIndex === 1,
                    },
                },
                scales: {
                    ...CHART_DEFAULTS.scales,
                    x: { ...CHART_DEFAULTS.scales.x, stacked: true },
                    y: {
                        ...CHART_DEFAULTS.scales.y,
                        stacked: true,
                        ticks: {
                            ...CHART_DEFAULTS.scales.y.ticks,
                            callback: (v) => this._formatCurrency(v),
                        },
                    },
                },
            },
        });
    }

    _renderPerfDistChart(performance) {
        const canvas = this.perfDistRef.el;
        if (!canvas || !performance) return;
        this._destroyChart('perfDist');

        const labels = ['Not Rated', '1 — Needs Improvement', '2 — Partially Meets', '3 — Meets', '4 — Exceeds', '5 — Outstanding'];
        const values = [0, 1, 2, 3, 4, 5].map(i => performance[String(i)] || 0);
        const colors = [
            '#94a3b8',
            CHART_COLORS.red,
            CHART_COLORS.orange,
            CHART_COLORS.blue,
            CHART_COLORS.green,
            '#059669',
        ];

        this.chartInstances.perfDist = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Employees',
                    data: values,
                    backgroundColor: colors.map(c => c + '33'),
                    borderColor: colors,
                    borderWidth: 2,
                    borderRadius: 8,
                    barPercentage: 0.6,
                }],
            },
            options: {
                ...CHART_DEFAULTS,
                indexAxis: 'y',
                plugins: {
                    ...CHART_DEFAULTS.plugins,
                    legend: { display: false },
                },
            },
        });
    }

    _renderGradeDistChart(grades) {
        const canvas = this.gradeDistRef.el;
        if (!canvas || !grades || grades.length === 0) return;
        this._destroyChart('gradeDist');

        this.chartInstances.gradeDist = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: grades.map(g => g.grade),
                datasets: [{
                    data: grades.map(g => g.total_cost),
                    backgroundColor: grades.map((_, i) => CHART_COLORS.palette[i % CHART_COLORS.palette.length]),
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'right',
                        labels: {
                            color: CHART_COLORS.text,
                            font: { family: "'Inter', sans-serif", size: 11 },
                            usePointStyle: true,
                            padding: 12,
                        },
                    },
                    tooltip: {
                        ...CHART_DEFAULTS.plugins.tooltip,
                        callbacks: {
                            label: (ctx) => {
                                const g = grades[ctx.dataIndex];
                                return [
                                    `Cost: ${this.formatMoney(g.total_cost)}`,
                                    `Headcount: ${g.headcount}`,
                                    `Avg Compa: ${g.avg_compa}`,
                                ];
                            },
                        },
                    },
                },
            },
        });
    }
}

registry.category("actions").add("wfp_dashboard", WfpDashboard);
