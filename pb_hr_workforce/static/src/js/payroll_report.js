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
import { Component, useState, onMounted, onWillStart } from "@odoo/owl";
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
    static template = "pb_hr_workforce.PayrollReport";

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
    batchLabel(b) {
        return _t("%(name)s (%(count)s slips)", { name: b.name, count: b.count });
    }

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
