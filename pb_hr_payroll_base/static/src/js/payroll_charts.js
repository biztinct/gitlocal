/* Enhanced Payroll Charts JavaScript */
/* pb_hr_payroll_base/static/src/js/payroll_charts.js */

odoo.define('pb_hr_payroll_base.charts', function (require) {
'use strict';

var AbstractField = require('web.AbstractField');
var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var rpc = require('web.rpc');
var field_registry = require('web.field_registry');

var QWeb = core.qweb;
var _t = core._t;

/**
 * Base Chart Component
 */
var BaseChart = AbstractField.extend({
    supportedFieldTypes: ['text', 'char'],
    
    init: function () {
        this._super.apply(this, arguments);
        this.chart = null;
        this.chartData = null;
        this.chartOptions = {};
    },

    start: function () {
        var self = this;
        return this._super().then(function () {
            return self._loadChartLibrary().then(function () {
                self._renderChart();
            });
        });
    },

    destroy: function () {
        if (this.chart) {
            this.chart.destroy();
        }
        this._super();
    },

    _loadChartLibrary: function () {
        return new Promise(function (resolve) {
            if (typeof Chart !== 'undefined') {
                resolve();
                return;
            }
            
            var script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js';
            script.onload = resolve;
            document.head.appendChild(script);
        });
    },

    _renderChart: function () {
        var $canvas = $('<canvas>').attr({
            width: this.attrs.width || 400,
            height: this.attrs.height || 300
        });
        
        this.$el.empty().append($canvas);
        
        if (this.value) {
            try {
                this.chartData = JSON.parse(this.value);
                this._createChart($canvas[0].getContext('2d'));
            } catch (e) {
                console.error('Error parsing chart data:', e);
                this.$el.html('<div class="alert alert-warning">Invalid chart data</div>');
            }
        }
    },

    _createChart: function (ctx) {
        // Override in subclasses
        console.warn('_createChart method should be overridden');
    },

    _getValue: function () {
        return this.value || '{}';
    }
});

/**
 * Employee Growth Chart Field
 */
var EmployeeGrowthChart = BaseChart.extend({
    _createChart: function (ctx) {
        var self = this;
        
        var defaultData = {
            labels: [],
            datasets: [{
                label: 'Employee Count',
                data: [],
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                tension: 0.4,
                fill: true
            }]
        };

        var data = this.chartData || defaultData;
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Employee Growth Trend'
                    },
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });
    }
});

/**
 * Payroll Trend Chart Field
 */
var PayrollTrendChart = BaseChart.extend({
    _createChart: function (ctx) {
        var self = this;
        
        var defaultData = {
            labels: [],
            datasets: [{
                label: 'Total Payroll',
                data: [],
                borderColor: '#764ba2',
                backgroundColor: 'rgba(118, 75, 162, 0.1)',
                tension: 0.4,
                fill: true
            }]
        };

        var data = this.chartData || defaultData;
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Payroll Trend Analysis'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function (value) {
                                return self._formatCurrency(value);
                            }
                        }
                    }
                }
            }
        });
    },

    _formatCurrency: function (value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value);
    }
});

/**
 * Salary Distribution Chart Field
 */
var SalaryDistributionChart = BaseChart.extend({
    _createChart: function (ctx) {
        var defaultData = {
            labels: ['Low', 'Medium', 'High', 'Executive'],
            datasets: [{
                label: 'Salary Distribution',
                data: [25, 45, 25, 5],
                backgroundColor: [
                    '#f093fb',
                    '#f5576c',
                    '#4facfe',
                    '#00f2fe'
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        };

        var data = this.chartData || defaultData;
        
        this.chart = new Chart(ctx, {
            type: 'doughnut',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Salary Distribution'
                    },
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
});

/**
 * Department Comparison Chart Field
 */
var DepartmentComparisonChart = BaseChart.extend({
    _createChart: function (ctx) {
        var defaultData = {
            labels: ['Engineering', 'Sales', 'Marketing', 'HR', 'Finance'],
            datasets: [{
                label: 'Employees',
                data: [45, 32, 18, 12, 8],
                backgroundColor: '#667eea'
            }, {
                label: 'Average Salary',
                data: [75000, 65000, 55000, 50000, 70000],
                backgroundColor: '#764ba2',
                yAxisID: 'y1'
            }]
        };

        var data = this.chartData || defaultData;
        
        this.chart = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Department Comparison'
                    }
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: {
                            drawOnChartArea: false,
                        }
                    }
                }
            }
        });
    }
});

/**
 * Anomaly Detection Chart Field
 */
var AnomalyChart = BaseChart.extend({
    _createChart: function (ctx) {
        var defaultData = {
            labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            datasets: [{
                label: 'Anomalies Detected',
                data: [2, 1, 4, 0, 3, 1],
                backgroundColor: function(context) {
                    var value = context.parsed.y;
                    return value > 3 ? '#e74c3c' : value > 1 ? '#f39c12' : '#27ae60';
                }
            }]
        };

        var data = this.chartData || defaultData;
        
        this.chart = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Anomaly Detection'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
    }
});

/**
 * Country Performance Chart Field
 */
var CountryPerformanceChart = BaseChart.extend({
    _createChart: function (ctx) {
        var defaultData = {
            labels: ['Vietnam', 'Indonesia', 'India', 'Singapore', 'Malaysia'],
            datasets: [{
                label: 'Payroll Efficiency',
                data: [85, 78, 92, 88, 75],
                backgroundColor: [
                    'rgba(102, 126, 234, 0.8)',
                    'rgba(118, 75, 162, 0.8)',
                    'rgba(240, 147, 251, 0.8)',
                    'rgba(245, 87, 108, 0.8)',
                    'rgba(79, 172, 254, 0.8)'
                ],
                borderColor: [
                    '#667eea',
                    '#764ba2',
                    '#f093fb',
                    '#f5576c',
                    '#4facfe'
                ],
                borderWidth: 2
            }]
        };

        var data = this.chartData || defaultData;
        
        this.chart = new Chart(ctx, {
            type: 'radar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Country Performance Radar'
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            stepSize: 20
                        }
                    }
                }
            }
        });
    }
});

/**
 * Interactive Dashboard Chart Widget
 */
var InteractiveDashboardChart = AbstractAction.extend({
    template: 'payroll_interactive_chart_dashboard',
    
    events: {
        'click .chart-filter-btn': '_onFilterClick',
        'change .chart-period-select': '_onPeriodChange',
        'click .chart-export-btn': '_onExportChart',
        'click .chart-refresh-btn': '_onRefreshChart',
    },

    init: function (parent, context) {
        this._super(parent, context);
        this.charts = {};
        this.currentFilters = {
            country: 'all',
            period: 'monthly',
            metric: 'all'
        };
    },

    start: function () {
        var self = this;
        return this._super().then(function () {
            return self._loadChartData().then(function () {
                self._initializeCharts();
                self._setupFilters();
            });
        });
    },

    destroy: function () {
        this._destroyAllCharts();
        this._super();
    },

    _loadChartData: function () {
        var self = this;
        return rpc.query({
            route: '/payroll/api/analytics/chart-data',
            params: this.currentFilters
        }).then(function (data) {
            self.chartData = data;
        });
    },

    _initializeCharts: function () {
        this._createEmployeeTrendChart();
        this._createPayrollComparisonChart();
        this._createEfficiencyChart();
        this._createGrowthChart();
    },

    _createEmployeeTrendChart: function () {
        var $canvas = this.$('#employeeTrendChart');
        if (!$canvas.length) return;

        var ctx = $canvas[0].getContext('2d');
        
        this.charts.employeeTrend = new Chart(ctx, {
            type: 'line',
            data: this.chartData.employee_trend || {labels: [], datasets: []},
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Employee Trend Analysis'
                    }
                },
                interaction: {
                    mode: 'index',
                    intersect: false
                }
            }
        });
    },

    _createPayrollComparisonChart: function () {
        var $canvas = this.$('#payrollComparisonChart');
        if (!$canvas.length) return;

        var ctx = $canvas[0].getContext('2d');
        
        this.charts.payrollComparison = new Chart(ctx, {
            type: 'bar',
            data: this.chartData.payroll_comparison || {labels: [], datasets: []},
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Payroll Comparison by Country'
                    }
                }
            }
        });
    },

    _createEfficiencyChart: function () {
        var $canvas = this.$('#efficiencyChart');
        if (!$canvas.length) return;

        var ctx = $canvas[0].getContext('2d');
        
        this.charts.efficiency = new Chart(ctx, {
            type: 'doughnut',
            data: this.chartData.efficiency || {labels: [], datasets: []},
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Payroll Processing Efficiency'
                    }
                }
            }
        });
    },

    _createGrowthChart: function () {
        var $canvas = this.$('#growthChart');
        if (!$canvas.length) return;

        var ctx = $canvas[0].getContext('2d');
        
        this.charts.growth = new Chart(ctx, {
            type: 'scatter',
            data: this.chartData.growth_analysis || {datasets: []},
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Growth Analysis Scatter Plot'
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Employee Growth %'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Payroll Growth %'
                        }
                    }
                }
            }
        });
    },

    _setupFilters: function () {
        // Initialize filter controls
        this._updateFilterButtons();
    },

    _updateFilterButtons: function () {
        var self = this;
        
        // Update active filter buttons
        this.$('.chart-filter-btn').removeClass('active');
        this.$('.chart-filter-btn[data-filter="' + this.currentFilters.country + '"]').addClass('active');
        
        // Update period select
        this.$('.chart-period-select').val(this.currentFilters.period);
    },

    // Event Handlers
    _onFilterClick: function (event) {
        var $btn = $(event.currentTarget);
        var filterType = $btn.data('filter-type');
        var filterValue = $btn.data('filter');
        
        this.currentFilters[filterType] = filterValue;
        this._refreshCharts();
    },

    _onPeriodChange: function (event) {
        this.currentFilters.period = $(event.target).val();
        this._refreshCharts();
    },

    _onExportChart: function (event) {
        var chartName = $(event.currentTarget).data('chart');
        this._exportChart(chartName);
    },

    _onRefreshChart: function (event) {
        this._refreshCharts();
    },

    _refreshCharts: function () {
        var self = this;
        
        this._loadChartData().then(function () {
            self._destroyAllCharts();
            self._initializeCharts();
            self._updateFilterButtons();
        });
    },

    _exportChart: function (chartName) {
        if (this.charts[chartName]) {
            var url = this.charts[chartName].toBase64Image();
            var link = document.createElement('a');
            link.download = chartName + '_chart.png';
            link.href = url;
            link.click();
        }
    },

    _destroyAllCharts: function () {
        Object.values(this.charts).forEach(function (chart) {
            if (chart && chart.destroy) {
                chart.destroy();
            }
        });
        this.charts = {};
    }
});

/**
 * Chart Utility Functions
 */
var ChartUtils = {
    
    /**
     * Generate color palette for charts
     */
    generateColorPalette: function (count) {
        var colors = [
            '#667eea', '#764ba2', '#f093fb', '#f5576c', 
            '#4facfe', '#00f2fe', '#43e97b', '#38f9d7',
            '#ffecd2', '#fcb69f', '#a8edea', '#fed6e3'
        ];
        
        var palette = [];
        for (var i = 0; i < count; i++) {
            palette.push(colors[i % colors.length]);
        }
        return palette;
    },

    /**
     * Create gradient background
     */
    createGradient: function (ctx, color1, color2) {
        var gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, color1);
        gradient.addColorStop(1, color2);
        return gradient;
    },

    /**
     * Format data for Chart.js
     */
    formatChartData: function (data, options) {
        options = options || {};
        
        return {
            labels: data.labels || [],
            datasets: data.datasets.map(function (dataset, index) {
                var colors = ChartUtils.generateColorPalette(data.datasets.length);
                return {
                    label: dataset.label,
                    data: dataset.data,
                    backgroundColor: options.type === 'line' ? 
                        colors[index] + '20' : colors[index],
                    borderColor: colors[index],
                    borderWidth: 2,
                    tension: options.tension || 0.4
                };
            })
        };
    },

    /**
     * Common chart options
     */
    getCommonOptions: function (title, options) {
        options = options || {};
        
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: title,
                    font: {
                        size: 16,
                        weight: 'bold'
                    }
                },
                legend: {
                    display: options.showLegend !== false,
                    position: options.legendPosition || 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: options.scales || {
                y: {
                    beginAtZero: true
                }
            }
        };
    }
};

// Register all chart fields
field_registry.add('employee_growth_chart', EmployeeGrowthChart);
field_registry.add('payroll_trend_chart', PayrollTrendChart);
field_registry.add('salary_distribution_chart', SalaryDistributionChart);
field_registry.add('department_comparison_chart', DepartmentComparisonChart);
field_registry.add('anomaly_chart', AnomalyChart);
field_registry.add('country_performance_chart', CountryPerformanceChart);

// Register interactive dashboard
core.action_registry.add('payroll_interactive_charts', InteractiveDashboardChart);

// Export for use in other modules
return {
    BaseChart: BaseChart,
    EmployeeGrowthChart: EmployeeGrowthChart,
    PayrollTrendChart: PayrollTrendChart,
    SalaryDistributionChart: SalaryDistributionChart,
    DepartmentComparisonChart: DepartmentComparisonChart,
    AnomalyChart: AnomalyChart,
    CountryPerformanceChart: CountryPerformanceChart,
    InteractiveDashboardChart: InteractiveDashboardChart,
    ChartUtils: ChartUtils
};

});