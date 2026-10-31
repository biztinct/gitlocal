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
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { loadBundle } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

/** The list's facade on the shared filter panel (FILTER wave 8). */
const LIST = "pb.payroll.report";
/** Rows per page (server: `REPORT_PAGE`). */
const PAGE = 60;

function fmt(val) {
    if (!val && val !== 0) return "–";
    return val.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export class PayrollReport extends Component {
    static template = "pb_hr_workforce.PayrollReport";
    static components = { PbFilterLayout };

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
        this.orm = useService("orm");

        // Check if opened from batch run with context
        const action = this.props.action || {};
        const ctx = action.context || {};
        const initialBatchId = ctx.default_batch_id || ctx.batch_id || false;

        this.state = useState({
            loading: false,
            activeTab: "earnings",
            batchId: initialBatchId,
            batches: [],
            batchesLoaded: false,
            batch: {},
            prevBatch: {},
            // FILTER wave 8: the run's payslips, one page at a time for the
            // filter panel; the totals and the department summary come from
            // the server over every payslip the filters match.
            rows: [],
            total: 0,
            listLoaded: false,
            loadingMore: false,
            deptChart: [],
            summary: { total_employees: 0, total_gross: 0, total_net: 0, total_deductions: 0, changes: 0 },
            expandedEmp: false,
        });

        // The panel is pointed at the picked run (`pbf_ctx.run_id`) once the
        // run list has answered, and pointed again whenever another run is
        // picked — so it is loaded by hand (`defer`).
        this.kit = useFilterKit({
            model: LIST,
            noun: _t("payslips"),
            defer: true,
            onChange: () => this.loadPage(),
        });

        onWillStart(async () => {
            await this.loadBatches();
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    fmt(val) { return fmt(val); }
    batchLabel(b) {
        return _t("%(name)s (%(count)s slips)", { name: b.name, count: b.count });
    }

    async _rpc(method, args = []) {
        return rpc("/web/dataset/call_kw/hr.payroll.report.api/" + method, {
            model: "hr.payroll.report.api", method, args, kwargs: {},
        });
    }

    async loadBatches() {
        try {
            this.state.batches = await this._rpc("get_all_batches");
        } catch (e) {
            console.error("Failed to load batches:", e);
            this.notification.add(_t("The pay runs could not be listed. Try again in a moment."), { type: "danger" });
        }
        this.state.batchesLoaded = true;
        // Opened from a run, or the newest one
        const id = this.state.batchId || (this.state.batches[0] && this.state.batches[0].id);
        if (id) {
            await this.selectRun(id);
        }
    }

    /** Point the panel at a run. The filters a reader set travel with them. */
    async selectRun(id) {
        this.state.batchId = id;
        this.state.listLoaded = false;
        this.state.expandedEmp = false;
        const keep = this.kit.loaded && !this.kit.failed
            ? { filters: this.kit.filters, search: this.kit.search, viewKey: this.kit.viewKey }
            : undefined;
        await this.kit.reconfigure({ ctx: { run_id: id }, initial: keep });
    }

    /** One page of payslips for the panel's state (and, on the first page,
     *  the totals and department summary of everything that matches). */
    async loadPage({ more = false } = {}) {
        if (!this.state.batchId) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const data = await this.orm.call(LIST, "get_report_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
                context: { pbf_ctx: { run_id: this.state.batchId } },
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...data.rows] : data.rows;
            this.state.total = data.total;
            if (!more) {
                Object.assign(this.state, {
                    batch: data.batch || {},
                    prevBatch: data.prev_batch || {},
                    deptChart: data.dept_chart || [],
                    summary: data.summary || this.state.summary,
                    expandedEmp: false,
                });
                if (this.state.activeTab === "summary") {
                    setTimeout(() => this._renderDonut(), 100);
                }
            }
            this.state.listLoaded = true;
        } catch (e) {
            if (this.kit.isCurrent(q.seq)) {
                console.error("Report load failed:", e);
                this.notification.add(_t("The payroll report could not be loaded. Try again in a moment."), { type: "danger" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }

    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    get hasMore() { return this.state.rows.length < this.state.total; }
    get nextLabel() {
        return _t("Show %s more", fmt(Math.min(PAGE, this.state.total - this.state.rows.length)));
    }
    get showingLine() {
        return _t("Showing %(shown)s of %(total)s", { shown: fmt(this.state.rows.length), total: fmt(this.state.total) });
    }
    get rows() { return this.state.rows; }
    get filtered() { return !!(this.kit.activeCount || this.kit.search); }
    get emptyTitle() {
        return this.kit.search && !this.kit.activeCount
            ? _t("Nobody in this run matches “%s”", this.kit.search)
            : _t("No payslip matches these filters");
    }
    get kpiNote() {
        return _t("Totals for the %s payslips the filters show.", fmt(this.state.summary.total_employees));
    }
    /** The Changes figure is the "Pay changed" filter. */
    get changedOn() { return this.kit.loaded && this.kit.isExactly({ changed: ["changed"] }); }
    toggleChanged() {
        if (this.kit.loaded && !this.kit.failed) { this.kit.toggleFilters({ changed: ["changed"] }); }
    }
    showEveryone() { this.kit.home(); }

    onBatchChange(ev) {
        const id = parseInt(ev.target.value);
        if (id) {
            this.selectRun(id);
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
