/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, onMounted, useRef, markup } from "@odoo/owl";

/* ── Chart.js loader ── */
let chartJSLoaded = false;
const loadChartJS = async () => {
    if (chartJSLoaded || (typeof Chart !== 'undefined')) { chartJSLoaded = true; return true; }
    try {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js';
        document.head.appendChild(script);
        await new Promise((ok, fail) => { script.onload = ok; script.onerror = fail; });
        chartJSLoaded = true;
        return true;
    } catch (e) {
        console.error('Failed to load Chart.js:', e);
        return false;
    }
};

class BfsiAiDashboard extends Component {
    static template = "hr_development_ai.BfsiAiDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.forecastChartRef = useRef("forecastChart");
        this.sparkCanvasRefs = {};

        this.state = useState({
            isLoading: true,
            error: null,

            // Date range
            dateRange: 'mtd',
            customFrom: '',
            customTo: '',

            // Branch selector
            branchId: null,
            availableBranches: [],

            // Dashboard data sections
            branch: {},
            dateRangeInfo: {},
            kpiSummary: {},
            rootCause: { summary: '', categories: [], ai_available: false },
            forecast: {
                on_track_pct: 0, shortfall: 0, chart: { labels: [], actual: [], predicted: [], target: 0 },
                ai_prediction: '', key_predictions: [],
            },
            teamPerformance: [],
            smartInsights: [],
            executiveSummary: { text: '', top_risk: null, top_opportunity: null },
            benchmarking: { text: '', leader: null, avg_score: 0 },
            incentiveData: { available: false },

            // UI state
            insightsTab: 'today',
            teamSort: 'score_desc',
            showDatePicker: false,
            showInsights: true,
            showSummaryView: false,
            aiChatInput: '',
            aiChatOpen: false,

            // Report modal
            showReportModal: false,
            reportLoading: false,
            reportHtml: '',

            // AI enhancement loading states
            aiLoadingRootCause: false,
            aiLoadingForecast: false,
            aiLoadingExecSummary: false,
            aiEnhancedRootCause: '',
            aiEnhancedForecast: '',
            aiEnhancedExecSummary: '',
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });

        onMounted(async () => {
            this.state.isLoading = false;
            await loadChartJS();
            this.renderForecastChart();
        });
    }

    // ═══════════════════════════════ DATA LOADING ═══════════════════════════════

    async loadDashboardData() {
        try {
            this.state.isLoading = true;
            this.state.error = null;

            const data = await this.orm.call(
                'bfsi.ai.dashboard',
                'get_dashboard_data',
                [],
                {
                    branch_id: this.state.branchId || false,
                    date_range: this.state.dateRange,
                    custom_from: this.state.customFrom || false,
                    custom_to: this.state.customTo || false,
                }
            );

            if (data.error) {
                this.state.error = data.error;
                return;
            }

            // Populate all sections
            this.state.branch = data.branch || {};
            this.state.dateRangeInfo = data.date_range || {};
            this.state.kpiSummary = data.kpi_summary || {};
            this.state.rootCause = data.root_cause || { summary: '', categories: [] };
            this.state.forecast = data.forecast || this.state.forecast;
            this.state.teamPerformance = data.team_performance || [];
            this.state.smartInsights = data.smart_insights || [];
            this.state.executiveSummary = data.executive_summary || {};
            this.state.benchmarking = data.benchmarking || {};
            this.state.incentiveData = data.incentive_data || { available: false };
            this.state.branchId = data.branch?.id || null;

        } catch (error) {
            console.error('Dashboard load error:', error);
            this.state.error = 'Failed to load dashboard data. Please refresh.';
        } finally {
            this.state.isLoading = false;
        }
    }

    // ═══════════════════════════════ DATE RANGE ═══════════════════════════════

    async onDateRangeChange(range) {
        this.state.dateRange = range;
        this.state.showDatePicker = (range === 'custom');
        if (range !== 'custom') {
            await this.loadDashboardData();
            this.renderForecastChart();
        }
    }

    async onCustomDateApply() {
        if (this.state.customFrom && this.state.customTo) {
            await this.loadDashboardData();
            this.renderForecastChart();
        }
    }

    onCustomFromChange(ev) {
        this.state.customFrom = ev.target.value;
    }

    onCustomToChange(ev) {
        this.state.customTo = ev.target.value;
    }

    toggleDatePicker() {
        this.state.showDatePicker = !this.state.showDatePicker;
    }

    // ═══════════════════════════════ REFRESH ═══════════════════════════════

    async onRefresh() {
        await this.loadDashboardData();
        this.renderForecastChart();
        this.notification.add("Dashboard refreshed", { type: "info" });
    }

    // ═══════════════════════════════ CHARTS ═══════════════════════════════

    renderForecastChart() {
        const el = this.forecastChartRef.el;
        if (!el) return;

        const ctx = el.getContext('2d');
        const f = this.state.forecast;
        if (!f.chart || !f.chart.labels || f.chart.labels.length === 0) return;

        // Destroy existing chart
        if (this._forecastChart) {
            this._forecastChart.destroy();
        }

        const actualLen = f.chart.actual.length;
        const datasets = [
            {
                label: 'Actual Revenue',
                data: f.chart.actual,
                borderColor: '#4F46E5',
                backgroundColor: 'rgba(79, 70, 229, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 2,
                borderWidth: 2,
            },
        ];

        // Predicted line (starts from last actual point)
        if (f.chart.predicted && f.chart.predicted.some(v => v !== null)) {
            const predData = f.chart.predicted.map((v, i) => {
                if (i === actualLen - 1) return f.chart.actual[actualLen - 1];
                return v;
            });
            datasets.push({
                label: 'Predicted',
                data: predData,
                borderColor: '#10B981',
                borderDash: [6, 3],
                fill: false,
                tension: 0.4,
                pointRadius: 0,
                borderWidth: 2,
            });
        }

        // Target line
        if (f.chart.target > 0) {
            datasets.push({
                label: 'Target',
                data: Array(f.chart.labels.length).fill(f.chart.target),
                borderColor: '#EF4444',
                borderDash: [4, 4],
                fill: false,
                pointRadius: 0,
                borderWidth: 1,
            });
        }

        try {
            this._forecastChart = new Chart(ctx, {
                type: 'line',
                data: { labels: f.chart.labels, datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { mode: 'index', intersect: false },
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(0,0,0,0.06)' },
                            ticks: { color: '#64748B', font: { size: 10 }, maxTicksLimit: 8 },
                        },
                        y: {
                            grid: { color: 'rgba(0,0,0,0.06)' },
                            ticks: {
                                color: '#64748B',
                                font: { size: 10 },
                                callback: (v) => this.formatCurrencyShort(v),
                            },
                        },
                    },
                    interaction: { mode: 'nearest', axis: 'x', intersect: false },
                },
            });
        } catch (e) {
            console.warn('Chart.js not available:', e);
        }
    }

    // ═══════════════════════════════ TEAM TABLE ═══════════════════════════════

    sortTeam(field) {
        const team = [...this.state.teamPerformance];
        const key = field === 'score' ? 'overall_score'
            : field === 'revenue' ? 'revenue'
            : field === 'rank' ? 'branch_rank'
            : field === 'forecast' ? 'forecast_pct'
            : 'overall_score';

        const isDesc = this.state.teamSort === `${field}_desc`;
        team.sort((a, b) => isDesc ? a[key] - b[key] : b[key] - a[key]);
        this.state.teamPerformance = team;
        this.state.teamSort = isDesc ? `${field}_asc` : `${field}_desc`;
    }

    onNextSteps(bankerId) {
        // Open action plans for this banker
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Action Plans',
            res_model: 'bfsi.action.plan',
            views: [[false, 'list'], [false, 'form']],
            domain: [['employee_id', '=', bankerId], ['state', 'in', ['committed', 'in_progress']]],
        });
    }

    onBankerClick(bankerId) {
        // Open banker profile
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Banker Profile',
            res_model: 'hr.employee',
            res_id: bankerId,
            views: [[false, 'form']],
        });
    }

    toggleSummaryView() {
        this.state.showSummaryView = !this.state.showSummaryView;
        if (this.state.showSummaryView) {
            // Generate summary for each team member
            this.state.teamPerformance = this.state.teamPerformance.map(m => {
                if (!m._summary) {
                    m._summary = this._generateMemberSummary(m);
                }
                return m;
            });
        }
    }

    _generateMemberSummary(m) {
        const parts = [];
        // Score assessment
        const score = Math.round(m.overall_score || 0);
        if (score >= 75) {
            parts.push(`Strong performer (score ${score}/100, rank #${m.branch_rank}).`);
        } else if (score >= 50) {
            parts.push(`Average performer (score ${score}/100, rank #${m.branch_rank}).`);
        } else {
            parts.push(`Needs coaching (score ${score}/100, rank #${m.branch_rank}).`);
        }
        // Revenue
        parts.push(`Revenue: ${m.revenue_formatted}, Conv. Rate: ${m.conversion_rate}%.`);
        // Forecast
        const fp = m.forecast_pct || 0;
        if (fp >= 90) {
            parts.push(`On track at ${fp}% of target.`);
        } else if (fp >= 60) {
            parts.push(`Slightly behind at ${fp}% of target — needs push.`);
        } else {
            parts.push(`At risk — only ${fp}% of target. Immediate coaching recommended.`);
        }
        // Trend
        if (m.rank_movement > 0) {
            parts.push(`Trending up ↑${m.rank_movement} ranks.`);
        } else if (m.rank_movement < 0) {
            parts.push(`Trending down ↓${Math.abs(m.rank_movement)} ranks.`);
        }
        return parts.join(' ');
    }

    // ═══════════════════════════════ INSIGHTS TABS ═══════════════════════════════

    switchInsightsTab(tab) {
        this.state.insightsTab = tab;
    }

    // ═══════════════════════════════ AI ENHANCEMENTS ═══════════════════════════════

    async requestAiRootCause() {
        this.state.aiLoadingRootCause = true;
        try {
            const result = await this.orm.call(
                'bfsi.ai.dashboard', 'get_ai_enhanced_analysis', [],
                { branch_id: this.state.branchId, section: 'root_cause', data_context: this.state.rootCause }
            );
            if (result.ai_text) {
                this.state.aiEnhancedRootCause = result.ai_text;
            }
        } catch (e) {
            console.warn('AI root cause failed:', e);
        } finally {
            this.state.aiLoadingRootCause = false;
        }
    }

    async requestAiExecSummary() {
        this.state.aiLoadingExecSummary = true;
        try {
            const result = await this.orm.call(
                'bfsi.ai.dashboard', 'get_ai_enhanced_analysis', [],
                { branch_id: this.state.branchId, section: 'executive_summary', data_context: this.state.kpiSummary }
            );
            if (result.ai_text) {
                this.state.aiEnhancedExecSummary = result.ai_text;
            }
        } catch (e) {
            console.warn('AI exec summary failed:', e);
        } finally {
            this.state.aiLoadingExecSummary = false;
        }
    }

    // ═══════════════════════════════ REPORT ═══════════════════════════════

    async generateReport() {
        try {
            const result = await this.orm.call(
                'bfsi.ai.dashboard', 'generate_ai_report', [],
                { branch_id: this.state.branchId, date_range: this.state.dateRange }
            );
            if (result.report_text) {
                // Copy to clipboard
                await navigator.clipboard.writeText(result.report_text);
                this.notification.add("Report copied to clipboard!", { type: "success" });
            }
        } catch (e) {
            this.notification.add("Failed to generate report", { type: "danger" });
        }
    }

    // ═══════════════════════════════ INSIGHTS TOGGLE ═══════════════════════════════

    toggleInsights() {
        this.state.showInsights = !this.state.showInsights;
    }

    // ═══════════════════════════════ REPORT MODAL ═══════════════════════════════

    async openReportModal() {
        this.state.showReportModal = true;
        this.state.reportLoading = true;
        this.state.reportHtml = '';

        try {
            const result = await this.orm.call(
                'bfsi.ai.dashboard', 'generate_ai_report', [],
                { branch_id: this.state.branchId, date_range: this.state.dateRange }
            );
            if (result.report_text) {
                this.state.reportHtml = markup(this._formatReportToHtml(result.report_text));
            } else {
                this.state.reportHtml = markup(this._generateLocalReport());
            }
        } catch (e) {
            // Generate a local report from available data
            this.state.reportHtml = markup(this._generateLocalReport());
        } finally {
            this.state.reportLoading = false;
        }
    }

    closeReportModal() {
        this.state.showReportModal = false;
    }

    async copyReportToClipboard() {
        const el = document.querySelector('.ai-report-content');
        if (el) {
            await navigator.clipboard.writeText(el.innerText);
            this.notification.add("Report copied to clipboard!", { type: "success" });
        }
    }

    _formatReportToHtml(text) {
        // Convert markdown-style text to HTML
        return text
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/^### (.+)$/gm, '<h4>$1</h4>')
            .replace(/^## (.+)$/gm, '<h3>$1</h3>')
            .replace(/^# (.+)$/gm, '<h2>$1</h2>')
            .replace(/^- (.+)$/gm, '<li>$1</li>')
            .replace(/(<li>.+<\/li>)/gs, '<ul>$1</ul>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br/>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    }

    _generateLocalReport() {
        const ks = this.state.kpiSummary;
        const fc = this.state.forecast;
        const ex = this.state.executiveSummary;
        const rc = this.state.rootCause;
        const team = this.state.teamPerformance;
        const bench = this.state.benchmarking;

        let html = `<h2>🏢 Branch: ${this.state.branch.name || 'N/A'}</h2>`;
        html += `<p class="report-date">Report generated on ${new Date().toLocaleDateString('en-AU', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>`;

        // Executive Summary
        html += `<h3>📊 Executive Summary</h3>`;
        html += `<p>${ex.text || 'No summary available.'}</p>`;

        // KPI Overview
        html += `<h3>📈 KPI Overview</h3>`;
        html += `<table class="report-table">`;
        html += `<tr><td><strong>Monthly Forecast</strong></td><td>${ks.forecast_pct || 0}% of target</td></tr>`;
        html += `<tr><td><strong>MTD Revenue</strong></td><td>${ks.mtd_revenue_formatted || '$0'}</td></tr>`;
        html += `<tr><td><strong>Avg Conversion Rate</strong></td><td>${ks.avg_conversion_rate || 0}%</td></tr>`;
        html += `<tr><td><strong>Active Bankers</strong></td><td>${ks.active_bankers_count || 0}/${ks.total_bankers || 0}</td></tr>`;
        html += `<tr><td><strong>Coverage</strong></td><td>${ks.coverage_pct || 0}%</td></tr>`;
        html += `<tr><td><strong>Target Revenue</strong></td><td>${ks.target_revenue_formatted || 'N/A'}</td></tr>`;
        html += `</table>`;

        // Root Cause
        if (rc.summary) {
            html += `<h3>🔍 Root Cause Analysis</h3>`;
            html += `<p>${rc.summary}</p>`;
            if (rc.categories && rc.categories.length) {
                html += `<ul>`;
                rc.categories.forEach(c => {
                    html += `<li><strong>${c.label}</strong>: ${c.detail} (Impact: ${c.impact_formatted || 'N/A'})</li>`;
                });
                html += `</ul>`;
            }
        }

        // Forecast
        html += `<h3>📉 Forecast Performance</h3>`;
        html += `<p>On track for <strong>${fc.on_track_pct || 0}%</strong> of target.`;
        if (fc.shortfall_formatted) html += ` Shortfall: ${fc.shortfall_formatted}`;
        html += `</p>`;

        // Team Performance
        if (team.length) {
            html += `<h3>👥 Team Performance</h3>`;
            html += `<table class="report-table"><thead><tr>`;
            html += `<th>Banker</th><th>Score</th><th>Rank</th><th>Revenue</th><th>Conv. Rate</th><th>Forecast</th><th>Priority</th>`;
            html += `</tr></thead><tbody>`;
            team.forEach(m => {
                html += `<tr>`;
                html += `<td><strong>${m.name}</strong><br/><small>${m.banker_type_label}</small></td>`;
                html += `<td>${Math.round(m.overall_score)}</td>`;
                html += `<td>#${m.branch_rank || '-'}</td>`;
                html += `<td>${m.revenue_formatted}</td>`;
                html += `<td>${m.conversion_rate}%</td>`;
                html += `<td>${m.forecast_pct}%</td>`;
                html += `<td>${(m.coaching_priority || 'low').toUpperCase()}</td>`;
                html += `</tr>`;
            });
            html += `</tbody></table>`;
        }

        // Risk & Opportunity
        if (ex.top_risk || ex.top_opportunity) {
            html += `<h3>⚠️ Risks & Opportunities</h3>`;
            if (ex.top_risk) {
                html += `<p>🔴 <strong>Top Risk:</strong> ${ex.top_risk.name} — Score: ${Math.round(ex.top_risk.score || 0)}</p>`;
            }
            if (ex.top_opportunity) {
                html += `<p>🟢 <strong>Top Opportunity:</strong> ${ex.top_opportunity.name} — ↑${ex.top_opportunity.rank_movement || 0} ranks</p>`;
            }
        }

        // Benchmarking
        if (bench.text) {
            html += `<h3>🏆 Benchmarking</h3>`;
            html += `<p>${bench.text}</p>`;
        }

        return html;
    }

    async copyExecSummary() {
        const text = this.state.aiEnhancedExecSummary || this.state.executiveSummary.text || '';
        if (text) {
            await navigator.clipboard.writeText(text);
            this.notification.add("Summary copied to clipboard", { type: "info" });
        }
    }

    // ═══════════════════════════════ FORMATTING HELPERS ═══════════════════════════════

    formatCurrencyShort(value) {
        if (!value) return '0';
        const abs = Math.abs(value);
        const sign = value < 0 ? '-' : '';
        if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(1)}B`;
        if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(1)}M`;
        if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(1)}K`;
        return `${sign}${abs.toFixed(0)}`;
    }

    getPriorityClass(priority) {
        const map = {
            'critical': 'priority-critical',
            'high': 'priority-high',
            'medium': 'priority-medium',
            'low': 'priority-low',
        };
        return map[priority] || 'priority-low';
    }

    getRankIcon(movement) {
        if (movement > 0) return 'fa-arrow-up text-success';
        if (movement < 0) return 'fa-arrow-down text-danger';
        return 'fa-minus text-muted';
    }

    getSparklineStyle(values) {
        if (!values || values.length < 2) return '';
        // CSS-based sparkline using linear gradient
        const max = Math.max(...values);
        const min = Math.min(...values);
        const range = max - min || 1;
        const points = values.map((v, i) => {
            const x = (i / (values.length - 1)) * 100;
            const y = (1 - (v - min) / range) * 100;
            return `${x}% ${y}%`;
        });
        return points.join(', ');
    }

    getChangeClass(value) {
        if (value > 0) return 'change-positive';
        if (value < 0) return 'change-negative';
        return 'change-neutral';
    }
}

// Register as client action
registry.category("actions").add("bfsi_ai_dashboard", BfsiAiDashboard);
