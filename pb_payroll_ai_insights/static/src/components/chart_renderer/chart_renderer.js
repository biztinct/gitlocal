/** @odoo-module **/

import { Component, useRef, onMounted, onWillUnmount, onPatched } from "@odoo/owl";

/**
 * ChartRenderer — Reusable OWL component that renders a Chart.js chart
 * from a JSON configuration object.
 *
 * Usage:
 *   <ChartRenderer chartConfig="someChartConfig" height="'300px'" />
 */
export class ChartRenderer extends Component {
    static template = "pb_payroll_ai_insights.ChartRenderer";
    static props = {
        chartConfig: { type: Object, optional: true },
        height: { type: String, optional: true },
        chartId: { type: String, optional: true },
    };

    setup() {
        this.canvasRef = useRef("chartCanvas");
        this.chartInstance = null;

        onMounted(() => {
            this.renderChart();
        });

        onPatched(() => {
            this.renderChart();
        });

        onWillUnmount(() => {
            this.destroyChart();
        });
    }

    get canvasHeight() {
        return this.props.height || "280px";
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

            // Ensure responsive options
            if (!config.options) config.options = {};
            config.options.responsive = true;
            config.options.maintainAspectRatio = false;

            // Create new Chart instance
            this.chartInstance = new Chart(ctx, config);
        } catch (error) {
            console.error("ChartRenderer: Failed to render chart:", error);
        }
    }

    destroyChart() {
        if (this.chartInstance) {
            this.chartInstance.destroy();
            this.chartInstance = null;
        }
    }
}
