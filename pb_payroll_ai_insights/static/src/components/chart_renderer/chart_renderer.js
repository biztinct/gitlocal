/** @odoo-module **/

import { Component, useRef, useState, onMounted, onWillUnmount, onPatched } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * ChartRenderer — Reusable OWL component that renders a Chart.js chart
 * from a JSON configuration object.
 *
 * Features:
 *   - Chart type switcher toolbar (bar, line, pie, doughnut, radar, polarArea)
 *   - Drill-down: click a chart element → open Odoo pivot view
 */
export class ChartRenderer extends Component {
    static template = "pb_payroll_ai_insights.ChartRenderer";
    static props = {
        chartConfig: { type: Object, optional: true },
        height: { type: String, optional: true },
        chartId: { type: String, optional: true },
        showToolbar: { type: Boolean, optional: true },
        drillDownModel: { type: String, optional: true },
    };

    setup() {
        this.canvasRef = useRef("chartCanvas");
        this.chartInstance = null;

        // Action service — always available in Odoo OWL components
        this.actionService = useService("action");

        this.state = useState({
            currentType: this.props.chartConfig?.type || "bar",
        });

        this.chartTypes = [
            { type: "bar", label: _t("Bar"), icon: "fa fa-bar-chart" },
            { type: "line", label: _t("Line"), icon: "fa fa-line-chart" },
            { type: "pie", label: _t("Pie"), icon: "fa fa-pie-chart" },
            { type: "doughnut", label: _t("Doughnut"), icon: "fa fa-circle-o-notch" },
            { type: "radar", label: _t("Radar"), icon: "fa fa-bullseye" },
            { type: "polarArea", label: _t("Polar"), icon: "fa fa-compass" },
        ];
        this._resizeObserver = null;

        onMounted(() => {
            this.renderChart();
            // Watch for container resize (e.g., from Gridstack drag/resize)
            this._setupResizeObserver();
        });

        onPatched(() => {
            this.renderChart();
        });

        onWillUnmount(() => {
            this.destroyChart();
            if (this._resizeObserver) {
                this._resizeObserver.disconnect();
                this._resizeObserver = null;
            }
        });
    }

    get canvasHeight() {
        return this.props.height || "280px";
    }

    get showToolbar() {
        return this.props.showToolbar || false;
    }

    get drillDownModel() {
        const model = this.props.drillDownModel;
        return model && model.length > 0 ? model : "";
    }

    _setupResizeObserver() {
        if (!this.canvasRef.el) return;
        const wrapper = this.canvasRef.el.parentElement;
        if (!wrapper) return;

        let resizeTimeout = null;
        this._resizeObserver = new ResizeObserver(() => {
            // Debounce resize events (Gridstack fires many during drag)
            if (resizeTimeout) clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                if (this.chartInstance) {
                    this.chartInstance.resize();
                }
            }, 100);
        });
        this._resizeObserver.observe(wrapper);
    }

    switchChartType(newType) {
        this.state.currentType = newType;
        this.renderChart();
    }

    renderChart() {
        if (!this.props.chartConfig || !this.canvasRef.el) {
            return;
        }

        // Destroy previous instance
        this.destroyChart();

        try {
            const ctx = this.canvasRef.el.getContext("2d");
            const config = JSON.parse(JSON.stringify(this.props.chartConfig));

            // Apply selected chart type if toolbar is showing
            if (this.showToolbar && this.state.currentType) {
                config.type = this.state.currentType;
            }

            // Ensure responsive options
            if (!config.options) config.options = {};
            config.options.responsive = true;
            config.options.maintainAspectRatio = false;

            // Add drill-down click handler
            const drillModel = this.drillDownModel;
            if (drillModel) {
                config.options.onClick = (event, elements) => {
                    this._handleChartClick(event, elements, config, drillModel);
                };
                config.options.onHover = (event, elements) => {
                    if (event.native && event.native.target) {
                        event.native.target.style.cursor = elements.length ? "pointer" : "default";
                    }
                };
            }

            // Create new Chart instance
            this.chartInstance = new Chart(ctx, config);
        } catch (error) {
            console.error("ChartRenderer: Failed to render chart:", error);
        }
    }

    _handleChartClick(event, elements, config, model) {
        if (!elements || !elements.length) return;

        const element = elements[0];
        const label = config.data.labels?.[element.index];
        if (!label) return;

        // Build domain + group_by context per model
        const drillConfig = {
            "hr.employee":           { domain: [["department_id.name", "=", label]],                     groupBy: "department_id" },
            "hr.contract":           { domain: [["department_id.name", "=", label]],                     groupBy: "department_id" },
            "hr.payslip":            { domain: [],                                                       groupBy: "date_from:month" },
            "hr.payslip.line":       { domain: [["slip_id.employee_id.department_id.name", "=", label]], groupBy: "salary_rule_id" },
            "hr.attendance":         { domain: [["employee_id.department_id.name", "=", label]],          groupBy: "employee_id" },
            "hr.leave":              { domain: [["holiday_status_id.name", "=", label]],                  groupBy: "holiday_status_id" },
            "hr.applicant":          { domain: [["stage_id.name", "=", label]],                           groupBy: "stage_id" },
            "account.analytic.line": { domain: [["project_id.name", "=", label]],                        groupBy: "project_id" },
        };

        const cfg = drillConfig[model] || { domain: [], groupBy: false };

        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: `${label} — Detail`,
            res_model: model,
            view_mode: "pivot,list,form",
            views: [[false, "pivot"], [false, "list"], [false, "form"]],
            domain: cfg.domain,
            context: cfg.groupBy ? { group_by: [cfg.groupBy] } : {},
            target: "current",
        });
    }

    destroyChart() {
        if (this.chartInstance) {
            this.chartInstance.destroy();
            this.chartInstance = null;
        }
    }
}
