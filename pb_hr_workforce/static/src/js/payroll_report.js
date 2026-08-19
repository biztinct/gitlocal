/** @odoo-module **/
/**
 * Payroll Report — the per-employee current-vs-previous payroll comparison.
 *
 * IA Cycle 4 RE-SKINNED this surface; it did not rebuild it. Every RPC, every
 * getter, every tab and every column is the one that was here before. What
 * changed is the three things that made it the last off-system cockpit in the
 * product:
 *
 *   1. **Font Awesome is gone.** Eleven `<i class="fa fa-…"/>` glyphs became
 *      Lucide SVG through the shared `ic()` registry (W2). The four names it
 *      needed that the registry did not have were ADDED to the registry, not
 *      to a private map here.
 *   2. **The internal breadcrumb is gone.** The surface drew its own
 *      home / Dashboard / Payroll Report trail on top of the web client's,
 *      so a user saw two breadcrumbs saying different things, and the private
 *      one's two links both went to the same action. The shell's crumb — or,
 *      in a hub, the hub's own command bar — is the one that knows where the
 *      user actually came from. `wf_breadcrumb.css` had no other consumer and
 *      went with it (W76: a retirement and the thing it points at have one
 *      lifetime).
 *   3. **It is on the kit.** The root is a `.pbim` node, so the pbim custom
 *      properties resolve (W14) and the surface takes the one indigo accent,
 *      the flat fills and the tabular figures every other Payobook cockpit
 *      has. And it takes an `embedded` prop, so the Insights hub can mount it
 *      as a lens — one component, one facade, two mount points (W17).
 *
 * One behaviour fix came with the re-skin and is not cosmetic, so it is stated
 * plainly rather than buried: the department donut asked
 * `typeof Chart !== "undefined"` and drew nothing when the answer was no.
 * Chart.js lives in Odoo's LAZY `web.chartjs_lib` bundle, which nothing on this
 * page had ever loaded — so the canvas has been blank since the tab was
 * written, silently, with the legend and the table beside it rendering
 * perfectly (W40's shape: a `catch`-like guard that turns a missing dependency
 * into a missing feature). The bundle is now awaited before the first paint.
 */
import { Component, useState, onMounted, onWillStart, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { loadBundle } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

function fmt(val) {
    if (!val && val !== 0) return "–";
    return val.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export class PayrollReport extends Component {
    static template = xml`
    <div class="pbim prd" t-att-class="{ 'prd--embedded': props.embedded }">
      <div class="prd-wrap">

        <!-- ============================== toolbar ============================== -->
        <div class="prd-toolbar">
            <div class="prd-toolbar-left">
                <div class="prd-title" t-if="!props.embedded">
                    <span class="prd-title-ic" t-out="ic('barChart', 19)"/>
                    <span>Payroll Report</span>
                </div>
                <select class="prd-select" t-on-change="onBatchChange" aria-label="Pay run">
                    <option value="">Select Pay Run…</option>
                    <t t-foreach="state.batches" t-as="b" t-key="b.id">
                        <option t-att-value="b.id" t-att-selected="state.batchId === b.id">
                            <t t-esc="b.name"/> (<t t-esc="b.count"/> slips)
                        </option>
                    </t>
                </select>
                <div class="prd-search">
                    <span class="prd-search-ic" t-out="ic('search', 15)"/>
                    <input type="text" placeholder="Search employee..." t-model="state.searchQuery"/>
                </div>
            </div>
            <div class="prd-toolbar-right">
                <div class="prd-tab-bar">
                    <button class="prd-tab" t-att-class="{ 'is-on': state.activeTab === 'earnings' }"
                            t-att-aria-current="state.activeTab === 'earnings' ? 'true' : false"
                            t-on-click="() => this.setTab('earnings')">
                        <span class="prd-tab-ic" t-out="ic('banknote', 15)"/> Earnings
                    </button>
                    <button class="prd-tab" t-att-class="{ 'is-on': state.activeTab === 'deductions' }"
                            t-att-aria-current="state.activeTab === 'deductions' ? 'true' : false"
                            t-on-click="() => this.setTab('deductions')">
                        <span class="prd-tab-ic" t-out="ic('minusCircle', 15)"/> Deductions
                    </button>
                    <button class="prd-tab" t-att-class="{ 'is-on': state.activeTab === 'summary' }"
                            t-att-aria-current="state.activeTab === 'summary' ? 'true' : false"
                            t-on-click="() => this.setTab('summary')">
                        <span class="prd-tab-ic" t-out="ic('pieChart', 15)"/> Dept Summary
                    </button>
                </div>
            </div>
        </div>

        <!-- ============================ summary KPIs ============================ -->
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

        <!-- =========================== batch context =========================== -->
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

        <!-- ============================== earnings ============================== -->
        <div class="prd-content" t-if="state.activeTab === 'earnings' and !state.loading">
            <div class="prd-tablewrap" t-if="filteredEmployees.length">
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
                        <tr class="prd-row" t-att-class="{ 'is-open': state.expandedEmp === emp.id }"
                            t-on-click="() => this.toggleDetail(emp.id)">
                            <td class="prd-col-emp">
                                <div class="prd-emp-info">
                                    <img class="prd-avatar" t-att-src="emp.avatar_url" loading="lazy" alt=""/>
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
                                <span t-if="emp.diff_gross > 0" class="prd-var">
                                    <span class="prd-var-ic" t-out="ic('trendingUp', 13)"/><t t-esc="fmt(emp.diff_gross)"/>
                                </span>
                                <span t-if="emp.diff_gross &lt; 0" class="prd-var">
                                    <span class="prd-var-ic" t-out="ic('trendingDown', 13)"/><t t-esc="fmt(emp.diff_gross)"/>
                                </span>
                                <span t-if="emp.diff_gross === 0">–</span>
                            </td>
                            <td class="prd-col-events">
                                <t t-foreach="emp.events" t-as="ev" t-key="ev_index">
                                    <div class="prd-event"><span class="prd-event-dot"/>
                                        <t t-esc="ev"/></div>
                                </t>
                            </td>
                        </tr>
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
            </div>
            <div class="prd-empty" t-else="">
                <span class="prd-empty-ic" t-out="ic('inbox', 30)"/>
                <h3>No payroll data</h3>
                <p>Select a pay run batch to view the report.</p>
            </div>
        </div>

        <!-- ============================= deductions ============================= -->
        <div class="prd-content" t-if="state.activeTab === 'deductions' and !state.loading">
            <div class="prd-tablewrap">
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
                                    <img class="prd-avatar" t-att-src="emp.avatar_url" loading="lazy" alt=""/>
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
                                <span t-if="emp.diff_net > 0" class="prd-var">
                                    <span class="prd-var-ic" t-out="ic('trendingUp', 13)"/><t t-esc="fmt(emp.diff_net)"/>
                                </span>
                                <span t-if="emp.diff_net &lt; 0" class="prd-var">
                                    <span class="prd-var-ic" t-out="ic('trendingDown', 13)"/><t t-esc="fmt(emp.diff_net)"/>
                                </span>
                                <span t-if="emp.diff_net === 0">–</span>
                            </td>
                        </tr>
                    </t>
                </tbody>
            </table>
            </div>
        </div>

        <!-- ========================== department summary ========================== -->
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
            <div class="prd-tablewrap">
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
        </div>

        <!-- =============================== loading =============================== -->
        <div t-if="state.loading" class="prd-loading">
            <div class="prd-spin"/>
            <span>Loading payroll data…</span>
        </div>

      </div>
    </div>`;

    static props = {
        action: { type: Object, optional: true },
        // W17: suppresses only the chrome the host already owns — here, the
        // title chip. Never a facade call, never a column, never a tab.
        embedded: { type: Boolean, optional: true },
        "*": true,
    };

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");

        // Check if opened from batch run with context
        const action = this.props.action || {};
        const ctx = action.context || {};
        const initialBatchId = ctx.default_batch_id || ctx.batch_id || false;

        this.state = useState({
            loading: false,
            activeTab: "earnings",
            batchId: initialBatchId,
            batches: [],
            batch: {},
            prevBatch: {},
            employees: [],
            deptChart: [],
            summary: { total_employees: 0, total_gross: 0, total_net: 0, total_deductions: 0, changes: 0 },
            searchQuery: "",
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

    ic(n, s = 16) { return ic(n, s); }
    fmt(val) { return fmt(val); }

    get filteredEmployees() {
        const q = (this.state.searchQuery || "").toLowerCase().trim();
        if (!q) return this.state.employees;
        return this.state.employees.filter(e =>
            e.name.toLowerCase().includes(q) ||
            (e.job_title || "").toLowerCase().includes(q) ||
            (e.department || "").toLowerCase().includes(q)
        );
    }

    async _rpc(method, args = []) {
        return rpc("/web/dataset/call_kw/hr.payroll.report.api/" + method, {
            model: "hr.payroll.report.api", method, args, kwargs: {},
        });
    }

    async loadBatches() {
        try {
            this.state.batches = await this._rpc("get_all_batches");
            // Auto-select first if none selected
            if (!this.state.batchId && this.state.batches.length > 0) {
                this.state.batchId = this.state.batches[0].id;
                await this.loadReport(this.state.batchId);
            }
        } catch (e) {
            console.error("Failed to load batches:", e);
        }
    }

    async loadReport(batchId) {
        this.state.loading = true;
        try {
            const data = await this._rpc("get_batch_report", [batchId]);
            if (data.error) {
                this.notification.add(data.error, { type: "danger" });
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
            if (this.state.activeTab === "summary") {
                setTimeout(() => this._renderDonut(), 100);
            }
        } catch (e) {
            console.error("Report load failed:", e);
            this.notification.add(_t("Failed to load payroll report"), { type: "danger" });
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
        if (tab === "summary") {
            setTimeout(() => this._renderDonut(), 100);
        }
    }

    toggleDetail(empId) {
        this.state.expandedEmp = this.state.expandedEmp === empId ? false : empId;
    }

    /**
     * Chart.js is in a LAZY bundle, so it is awaited rather than assumed.
     *
     * The previous form was `if (typeof Chart !== "undefined")`, which is a
     * guard that silently deletes the feature when the answer is no — and the
     * answer was always no, because nothing on this page loads
     * `web.chartjs_lib`. The legend and the department table beside the canvas
     * kept rendering, so the tab looked like it worked.
     */
    async _renderDonut() {
        const canvas = document.getElementById("prdDonutChart");
        if (!canvas || !this.state.deptChart.length) return;
        let Chart = window.Chart;
        if (!Chart || !Chart.version) {
            try {
                await loadBundle("web.chartjs_lib");
                Chart = window.Chart;
            } catch (e) {
                // Reported, never swallowed into "the chart is just missing".
                console.warn("payroll_report: could not load Chart.js", e);
                return;
            }
        }
        if (!Chart) { return; }
        // The tab may have changed while the bundle was in flight.
        if (this.state.activeTab !== "summary") { return; }
        if (this._chart) { this._chart.destroy(); }
        const ctx = canvas.getContext("2d");
        const data = this.state.deptChart;
        this._chart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: data.map(d => d.name),
                datasets: [{
                    data: data.map(d => d.net),
                    backgroundColor: data.map(d => d.color),
                    borderWidth: 2,
                    borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                cutout: "65%",
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (c) => `${c.label}: ${fmt(c.raw)}`,
                        },
                    },
                },
            },
        });
    }
}

registry.category("actions").add("payroll_report_dashboard", PayrollReport);
