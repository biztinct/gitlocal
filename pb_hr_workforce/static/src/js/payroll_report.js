/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
/**
 * Rippling-style Payroll Report Dashboard
 * Tab 1: Employee Earnings Grid with Current vs. Previous comparison
 * Tab 2: Department Summary Donut + Table
 */

import { Component, useState, onMounted, onWillStart, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

function fmt(val) {
    if (!val && val !== 0) return '–';
    return val.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

class PayrollReport extends Component {
    static template = xml`
    <div class="prd-container">
        <div class="wf-breadcrumb">
            <span class="wf-bc-home" t-on-click="goHome"><i class="fa fa-home"/></span>
            <span class="wf-bc-sep"><i class="fa fa-chevron-right"/></span>
            <span class="wf-bc-link" t-on-click="goFlowDashboard">Dashboard</span>
            <span class="wf-bc-sep"><i class="fa fa-chevron-right"/></span>
            <span class="wf-bc-current">Payroll Report</span>
        </div>
        <!-- Toolbar -->
        <div class="prd-toolbar">
            <div class="prd-toolbar-left">
                <div class="prd-title"><i class="fa fa-bar-chart"/> Payroll Report</div>
                <select class="prd-select" t-on-change="onBatchChange">
                    <option value="">Select Pay Run…</option>
                    <t t-foreach="state.batches" t-as="b" t-key="b.id">
                        <option t-att-value="b.id" t-att-selected="state.batchId === b.id">
                            <t t-esc="b.name"/> (<t t-esc="b.count"/> slips)
                        </option>
                    </t>
                </select>
                <div class="prd-search">
                    <i class="fa fa-search"/>
                    <input type="text" placeholder="Search employee..." t-model="state.searchQuery"/>
                </div>
            </div>
            <div class="prd-toolbar-right">
                <div class="prd-tab-bar">
                    <button t-attf-class="prd-tab {{ state.activeTab === 'earnings' ? 'active' : '' }}"
                            t-on-click="() => this.setTab('earnings')">
                        <i class="fa fa-money"/> Earnings
                    </button>
                    <button t-attf-class="prd-tab {{ state.activeTab === 'deductions' ? 'active' : '' }}"
                            t-on-click="() => this.setTab('deductions')">
                        <i class="fa fa-minus-circle"/> Deductions
                    </button>
                    <button t-attf-class="prd-tab {{ state.activeTab === 'summary' ? 'active' : '' }}"
                            t-on-click="() => this.setTab('summary')">
                        <i class="fa fa-pie-chart"/> Dept Summary
                    </button>
                </div>
            </div>
        </div>

        <!-- Summary KPI Cards -->
        <div class="prd-kpis" t-if="state.summary.total_employees > 0">
            <div class="prd-kpi">
                <div class="prd-kpi-num" t-esc="state.summary.total_employees"/>
                <div class="prd-kpi-label">Employees</div>
            </div>
            <div class="prd-kpi prd-kpi-gross">
                <div class="prd-kpi-num" t-esc="fmt(state.summary.total_gross)"/>
                <div class="prd-kpi-label">Total Gross</div>
            </div>
            <div class="prd-kpi prd-kpi-ded">
                <div class="prd-kpi-num" t-esc="fmt(state.summary.total_deductions)"/>
                <div class="prd-kpi-label">Total Deductions</div>
            </div>
            <div class="prd-kpi prd-kpi-net">
                <div class="prd-kpi-num" t-esc="fmt(state.summary.total_net)"/>
                <div class="prd-kpi-label">Total Net Pay</div>
            </div>
            <div class="prd-kpi prd-kpi-changes" t-if="state.summary.changes > 0">
                <div class="prd-kpi-num" t-esc="state.summary.changes"/>
                <div class="prd-kpi-label">Changes</div>
            </div>
        </div>

        <!-- Batch context -->
        <div class="prd-batch-info" t-if="state.batch.name">
            <div class="prd-batch-current">
                <strong t-esc="state.batch.name"/>
                <span class="prd-batch-dates">
                    <t t-esc="state.batch.date_start"/> → <t t-esc="state.batch.date_end"/>
                </span>
            </div>
            <div class="prd-batch-prev" t-if="state.prevBatch.name">
                vs. <span t-esc="state.prevBatch.name"/>
            </div>
        </div>

        <!-- TAB: Earnings -->
        <div class="prd-content" t-if="state.activeTab === 'earnings' and !state.loading">
            <table class="prd-table">
                <thead>
                    <tr>
                        <th class="prd-col-emp">Employee</th>
                        <th class="prd-col-num">Basic</th>
                        <th class="prd-col-num">Gross Pay</th>
                        <th class="prd-col-num">Previous</th>
                        <th class="prd-col-num">Variance</th>
                        <th class="prd-col-events">Related Events</th>
                    </tr>
                </thead>
                <tbody>
                    <t t-foreach="filteredEmployees" t-as="emp" t-key="emp.id">
                        <tr class="prd-row" t-on-click="() => this.toggleDetail(emp.id)">
                            <td class="prd-col-emp">
                                <div class="prd-emp-info">
                                    <img class="prd-avatar" t-att-src="emp.avatar_url" loading="lazy"/>
                                    <div>
                                        <div class="prd-emp-name" t-esc="emp.name"/>
                                        <div class="prd-emp-meta" t-esc="emp.job_title"/>
                                    </div>
                                </div>
                            </td>
                            <td class="prd-col-num" t-esc="fmt(emp.basic)"/>
                            <td class="prd-col-num prd-val-current" t-esc="fmt(emp.gross)"/>
                            <td class="prd-col-num prd-val-prev" t-esc="fmt(emp.prev_gross)"/>
                            <td t-attf-class="prd-col-num {{ emp.diff_gross > 0 ? 'prd-var-up' : (emp.diff_gross &lt; 0 ? 'prd-var-down' : '') }}">
                                <span t-if="emp.diff_gross > 0">▲ <t t-esc="fmt(emp.diff_gross)"/></span>
                                <span t-if="emp.diff_gross &lt; 0">▼ <t t-esc="fmt(emp.diff_gross)"/></span>
                                <span t-if="emp.diff_gross === 0">–</span>
                            </td>
                            <td class="prd-col-events">
                                <t t-foreach="emp.events" t-as="ev" t-key="ev_index">
                                    <div class="prd-event"><span class="prd-event-dot"/>
                                        <t t-esc="ev"/></div>
                                </t>
                            </td>
                        </tr>
                        <!-- Expandable detail row -->
                        <tr t-if="state.expandedEmp === emp.id" class="prd-detail-row">
                            <td colspan="6">
                                <div class="prd-detail-grid">
                                    <div class="prd-detail-section">
                                        <h4>Earnings Breakdown</h4>
                                        <table class="prd-detail-table">
                                            <tr><th>Component</th><th>Current</th><th>Previous</th><th>Change</th></tr>
                                            <t t-foreach="emp.earnings" t-as="e" t-key="e.code">
                                                <tr>
                                                    <td t-esc="e.name"/>
                                                    <td class="prd-val-current" t-esc="fmt(e.current)"/>
                                                    <td class="prd-val-prev" t-esc="fmt(e.previous)"/>
                                                    <td t-attf-class="{{ e.diff > 0 ? 'prd-var-up' : (e.diff &lt; 0 ? 'prd-var-down' : '') }}">
                                                        <t t-esc="fmt(e.diff)"/>
                                                    </td>
                                                </tr>
                                            </t>
                                        </table>
                                    </div>
                                    <div class="prd-detail-section">
                                        <h4>Deductions</h4>
                                        <table class="prd-detail-table">
                                            <tr><th>Component</th><th>Current</th><th>Previous</th><th>Change</th></tr>
                                            <t t-foreach="emp.deduction_lines" t-as="d" t-key="d.code">
                                                <tr>
                                                    <td t-esc="d.name"/>
                                                    <td t-esc="fmt(d.current)"/>
                                                    <td t-esc="fmt(d.previous)"/>
                                                    <td t-attf-class="{{ d.diff > 0 ? 'prd-var-up' : (d.diff &lt; 0 ? 'prd-var-down' : '') }}">
                                                        <t t-esc="fmt(d.diff)"/>
                                                    </td>
                                                </tr>
                                            </t>
                                        </table>
                                    </div>
                                </div>
                            </td>
                        </tr>
                    </t>
                </tbody>
            </table>
            <div class="prd-empty" t-if="filteredEmployees.length === 0 and !state.loading">
                <i class="fa fa-inbox fa-3x"/>
                <h3>No payroll data</h3>
                <p>Select a pay run batch to view the report.</p>
            </div>
        </div>

        <!-- TAB: Deductions -->
        <div class="prd-content" t-if="state.activeTab === 'deductions' and !state.loading">
            <table class="prd-table">
                <thead>
                    <tr>
                        <th class="prd-col-emp">Employee</th>
                        <th class="prd-col-num">Deductions</th>
                        <th class="prd-col-num">Net Pay</th>
                        <th class="prd-col-num">Previous Net</th>
                        <th class="prd-col-num">Variance</th>
                    </tr>
                </thead>
                <tbody>
                    <t t-foreach="filteredEmployees" t-as="emp" t-key="emp.id">
                        <tr class="prd-row" t-on-click="() => this.toggleDetail(emp.id)">
                            <td class="prd-col-emp">
                                <div class="prd-emp-info">
                                    <img class="prd-avatar" t-att-src="emp.avatar_url" loading="lazy"/>
                                    <div>
                                        <div class="prd-emp-name" t-esc="emp.name"/>
                                        <div class="prd-emp-meta" t-esc="emp.department"/>
                                    </div>
                                </div>
                            </td>
                            <td class="prd-col-num" t-esc="fmt(emp.deductions)"/>
                            <td class="prd-col-num prd-val-current" t-esc="fmt(emp.net)"/>
                            <td class="prd-col-num prd-val-prev" t-esc="fmt(emp.prev_net)"/>
                            <td t-attf-class="prd-col-num {{ emp.diff_net > 0 ? 'prd-var-up' : (emp.diff_net &lt; 0 ? 'prd-var-down' : '') }}">
                                <span t-if="emp.diff_net > 0">▲ <t t-esc="fmt(emp.diff_net)"/></span>
                                <span t-if="emp.diff_net &lt; 0">▼ <t t-esc="fmt(emp.diff_net)"/></span>
                                <span t-if="emp.diff_net === 0">–</span>
                            </td>
                        </tr>
                    </t>
                </tbody>
            </table>
        </div>

        <!-- TAB: Department Summary -->
        <div class="prd-content" t-if="state.activeTab === 'summary' and !state.loading">
            <div class="prd-summary-layout">
                <div class="prd-chart-area">
                    <canvas id="prdDonutChart" width="300" height="300"/>
                </div>
                <div class="prd-chart-legend">
                    <t t-foreach="state.deptChart" t-as="dept" t-key="dept.name">
                        <div class="prd-legend-item">
                            <span class="prd-legend-dot" t-attf-style="background: {{ dept.color }}"/>
                            <span class="prd-legend-name" t-esc="dept.name"/>
                            <span class="prd-legend-val" t-esc="fmt(dept.net)"/>
                        </div>
                    </t>
                </div>
            </div>
            <table class="prd-table prd-dept-table">
                <thead>
                    <tr>
                        <th>Department</th>
                        <th class="prd-col-num">Employees</th>
                        <th class="prd-col-num">Total Gross</th>
                        <th class="prd-col-num">Deductions</th>
                        <th class="prd-col-num">Net Pay</th>
                    </tr>
                </thead>
                <tbody>
                    <t t-foreach="state.deptChart" t-as="dept" t-key="dept.name">
                        <tr>
                            <td>
                                <div class="prd-dept-cell">
                                    <span class="prd-dept-badge" t-attf-style="background: {{ dept.color }}">
                                        <t t-esc="dept.name.substring(0,2).toUpperCase()"/>
                                    </span>
                                    <t t-esc="dept.name"/>
                                </div>
                            </td>
                            <td class="prd-col-num" t-esc="dept.count"/>
                            <td class="prd-col-num" t-esc="fmt(dept.gross)"/>
                            <td class="prd-col-num" t-esc="fmt(dept.deductions)"/>
                            <td class="prd-col-num prd-val-current" t-esc="fmt(dept.net)"/>
                        </tr>
                    </t>
                </tbody>
            </table>
        </div>

        <!-- Loading -->
        <div t-if="state.loading" class="prd-loading">
            <i class="fa fa-circle-o-notch fa-spin fa-2x"/>
            <span>Loading payroll data…</span>
        </div>
    </div>`;

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");

        // Check if opened from batch run with context
        const action = this.props.action || {};
        const ctx = action.context || {};
        const initialBatchId = ctx.default_batch_id || ctx.batch_id || false;

        this.state = useState({
            loading: false,
            activeTab: 'earnings',
            batchId: initialBatchId,
            batches: [],
            batch: {},
            prevBatch: {},
            employees: [],
            deptChart: [],
            summary: { total_employees: 0, total_gross: 0, total_net: 0, total_deductions: 0, changes: 0 },
            searchQuery: '',
            expandedEmp: false,
        });

        onWillStart(async () => {
            await this.loadBatches();
        });
        onMounted(async () => {
            if (this.state.batchId) {
                await this.loadReport(this.state.batchId);
            }
        });
    }

    fmt(val) { return fmt(val); }

    get filteredEmployees() {
        const q = (this.state.searchQuery || '').toLowerCase().trim();
        if (!q) return this.state.employees;
        return this.state.employees.filter(e =>
            e.name.toLowerCase().includes(q) ||
            (e.job_title || '').toLowerCase().includes(q) ||
            (e.department || '').toLowerCase().includes(q)
        );
    }

    async _rpc(method, args = []) {
        return rpc('/web/dataset/call_kw/hr.payroll.report.api/' + method, {
            model: 'hr.payroll.report.api', method, args, kwargs: {},
        });
    }

    async loadBatches() {
        try {
            this.state.batches = await this._rpc('get_all_batches');
            // Auto-select first if none selected
            if (!this.state.batchId && this.state.batches.length > 0) {
                this.state.batchId = this.state.batches[0].id;
                await this.loadReport(this.state.batchId);
            }
        } catch (e) {
            console.error('Failed to load batches:', e);
        }
    }

    async loadReport(batchId) {
        this.state.loading = true;
        try {
            const data = await this._rpc('get_batch_report', [batchId]);
            if (data.error) {
                this.notification.add(data.error, { type: 'danger' });
                this.state.loading = false;
                return;
            }
            Object.assign(this.state, {
                batch: data.batch,
                prevBatch: data.prev_batch,
                employees: data.employees,
                deptChart: data.dept_chart,
                summary: data.summary,
            });
            // Render chart after data loads
            if (this.state.activeTab === 'summary') {
                setTimeout(() => this._renderDonut(), 100);
            }
        } catch (e) {
            console.error('Report load failed:', e);
            this.notification.add(_t("Failed to load payroll report"), { type: 'danger' });
        }
        this.state.loading = false;
    }

    onBatchChange(ev) {
        const id = parseInt(ev.target.value);
        if (id) {
            this.state.batchId = id;
            this.loadReport(id);
        }
    }

    setTab(tab) {
        this.state.activeTab = tab;
        if (tab === 'summary') {
            setTimeout(() => this._renderDonut(), 100);
        }
    }

    toggleDetail(empId) {
        this.state.expandedEmp = this.state.expandedEmp === empId ? false : empId;
    }

    _renderDonut() {
        const canvas = document.getElementById('prdDonutChart');
        if (!canvas || !this.state.deptChart.length) return;
        // Destroy existing chart
        if (this._chart) { this._chart.destroy(); }
        const ctx = canvas.getContext('2d');
        const data = this.state.deptChart;
        // Simple donut using Chart.js if available, else fallback
        if (typeof Chart !== 'undefined') {
            this._chart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.map(d => d.name),
                    datasets: [{
                        data: data.map(d => d.net),
                        backgroundColor: data.map(d => d.color),
                        borderWidth: 2,
                        borderColor: '#fff',
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    cutout: '65%',
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.label}: ${fmt(ctx.raw)}`,
                            },
                        },
                    },
                },
            });
        }
    }

    goHome() { this.actionService.doAction('pb_dashboard.action_pb_dashboard'); }
    goFlowDashboard() {
        this.actionService.doAction('pb_dashboard.action_pb_dashboard');
    }
}

registry.category("actions").add("payroll_report_dashboard", PayrollReport);
