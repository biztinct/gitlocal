/* Enhanced Payroll Analytics JavaScript */
/* pb_hr_payroll_base/static/src/js/payroll_analytics.js */

odoo.define('pb_hr_payroll_base.analytics', function (require) {
'use strict';

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var rpc = require('web.rpc');
var Dialog = require('web.Dialog');
var framework = require('web.framework');
var field_utils = require('web.field_utils');

var QWeb = core.qweb;
var _t = core._t;

/**
 * Payroll Analytics Dashboard Controller
 */
var PayrollAnalytics = AbstractAction.extend({
    template: 'payroll_analytics_dashboard',
    cssLibs: [
        '/pb_hr_payroll_base/static/src/css/payroll_analytics.css'
    ],
    
    events: {
        'click .analytics-card': '_onAnalyticsCardClick',
        'click .generate-analytics-btn': '_onGenerateAnalytics',
        'click .export-analytics-btn': '_onExportAnalytics',
        'click .compare-periods-btn': '_onComparePeriods',
        'change .country-filter': '_onCountryFilterChange',
        'change .period-filter': '_onPeriodFilterChange',
        'click .metric-drill-down': '_onMetricDrillDown',
        'click .refresh-analytics': '_onRefreshAnalytics',
    },

    init: function (parent, context) {
        this._super(parent, context);
        this.analytics_data = [];
        this.current_country = context.country || 'all';
        this.current_period = context.period || 'monthly';
        this.charts = {};
        this.isLoading = false;
    },

    willStart: function () {
        var self = this;
        return this._super().then(function () {
            return self._fetchAnalyticsData();
        });
    },

    start: function () {
        var self = this;
        return this._super().then(function () {
            self._initializeAnalytics();
            self._renderCharts();
            self._setupFilters();
            self._bindEvents();
        });
    },

    destroy: function () {
        this._destroyCharts();
        this._super();
    },

    // Data Management
    _fetchAnalyticsData: function () {
        var self = this;
        var domain = [['state', 'in', ['ready', 'approved']]];
        
        if (this.current_country !== 'all') {
            domain.push(['country_code', '=', this.current_country]);
        }

        return rpc.query({
            model: 'payroll.analytics',
            method: 'search_read',
            args: [domain],
            kwargs: {
                fields: [
                    'period_name', 'country_code', 'period_start', 'period_end',
                    'total_employees', 'total_payroll', 'average_salary', 'median_salary',
                    'employee_growth', 'payroll_growth', 'average_salary_growth',
                    'anomaly_count', 'currency_id', 'state'
                ],
                order: 'period_start desc',
                limit: 50
            }
        }).then(function (data) {
            self.analytics_data = data;
            return self._processAnalyticsData();
        }).catch(function (error) {
            console.error('Error fetching analytics data:', error);
            self._showError(_t('Failed to load analytics data'));
        });
    },

    _processAnalyticsData: function () {
        var self = this;
        
        // Group data by country
        this.analytics_by_country = {};
        this.analytics_data.forEach(function (record) {
            if (!self.analytics_by_country[record.country_code]) {
                self.analytics_by_country[record.country_code] = [];
            }
            self.analytics_by_country[record.country_code].push(record);
        });

        // Calculate summary metrics
        this._calculateSummaryMetrics();
        
        return Promise.resolve();
    },

    _calculateSummaryMetrics: function () {
        var total_employees = 0;
        var total_payroll = 0;
        var countries_count = Object.keys(this.analytics_by_country).length;
        var total_anomalies = 0;

        this.analytics_data.forEach(function (record) {
            total_employees += record.total_employees;
            total_payroll += record.total_payroll;
            total_anomalies += record.anomaly_count;
        });

        this.summary_metrics = {
            total_employees: total_employees,
            total_payroll: total_payroll,
            average_payroll: countries_count > 0 ? total_payroll / countries_count : 0,
            countries_count: countries_count,
            total_anomalies: total_anomalies,
            latest_period: this.analytics_data.length > 0 ? this.analytics_data[0].period_start : null
        };
    },

    // UI Initialization
    _initializeAnalytics: function () {
        this._renderSummaryCards();
        this._renderAnalyticsTable();
        this._setupTooltips();
    },

    _renderSummaryCards: function () {
        var $container = this.$('.summary-cards-container');
        if (!$container.length) return;

        $container.empty();

        var cards = [
            {
                title: _t('Total Employees'),
                value: this.summary_metrics.total_employees,
                icon: 'fa-users',
                color: 'primary'
            },
            {
                title: _t('Total Payroll'),
                value: this._formatCurrency(this.summary_metrics.total_payroll),
                icon: 'fa-money',
                color: 'success'
            },
            {
                title: _t('Countries'),
                value: this.summary_metrics.countries_count,
                icon: 'fa-globe',
                color: 'info'
            },
            {
                title: _t('Anomalies'),
                value: this.summary_metrics.total_anomalies,
                icon: 'fa-warning',
                color: 'warning'
            }
        ];

        cards.forEach(function (card) {
            var $card = $(`
                <div class="col-md-3">
                    <div class="analytics-summary-card ${card.color}">
                        <div class="card-icon">
                            <i class="fa ${card.icon}"></i>
                        </div>
                        <div class="card-content">
                            <h3 class="card-value">${card.value}</h3>
                            <p class="card-title">${card.title}</p>
                        </div>
                    </div>
                </div>
            `);
            $container.append($card);
        });
    },

    _renderAnalyticsTable: function () {
        var self = this;
        var $table = this.$('.analytics-table tbody');
        if (!$table.length) return;

        $table.empty();

        this.analytics_data.forEach(function (record) {
            var $row = $(`
                <tr class="analytics-row" data-id="${record.id}">
                    <td>${record.period_name}</td>
                    <td><span class="country-flag">${self._getCountryFlag(record.country_code)}</span> ${record.country_code}</td>
                    <td class="text-right">${record.total_employees}</td>
                    <td class="text-right">${self._formatCurrency(record.total_payroll)}</td>
                    <td class="text-right">${self._formatCurrency(record.average_salary)}</td>
                    <td class="text-right">
                        <span class="growth-indicator ${record.employee_growth >= 0 ? 'positive' : 'negative'}">
                            ${record.employee_growth.toFixed(1)}%
                        </span>
                    </td>
                    <td class="text-right">
                        <span class="growth-indicator ${record.payroll_growth >= 0 ? 'positive' : 'negative'}">
                            ${record.payroll_growth.toFixed(1)}%
                        </span>
                    </td>
                    <td class="text-center">
                        <span class="badge ${record.anomaly_count > 0 ? 'badge-warning' : 'badge-success'}">
                            ${record.anomaly_count}
                        </span>
                    </td>
                    <td>
                        <span class="badge badge-${self._getStateBadgeClass(record.state)}">
                            ${record.state}
                        </span>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-primary metric-drill-down" data-id="${record.id}">
                            <i class="fa fa-search"></i> Details
                        </button>
                    </td>
                </tr>
            `);
            $table.append($row);
        });
    },

    // Chart Management
    _renderCharts: function () {
        this._renderEmployeeGrowthChart();
        this._renderPayrollTrendChart();
        this._renderCountryComparisonChart();
        this._renderAnomalyChart();
    },

    _renderEmployeeGrowthChart: function () {
        var self = this;
        var $canvas = this.$('#employeeGrowthChart');
        if (!$canvas.length) return;

        var ctx = $canvas[0].getContext('2d');
        
        // Prepare data
        var labels = [];
        var data = [];
        
        this.analytics_data.slice(0, 12).reverse().forEach(function (record) {
            labels.push(record.period_name.split(' - ')[0]);
            data.push(record.total_employees);
        });

        this.charts.employeeGrowth = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Total Employees',
                    data: data,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Employee Growth Trend'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    },

    _renderPayrollTrendChart: function () {
        var self = this;
        var $canvas = this.$('#payrollTrendChart');
        if (!$canvas.length) return;

        var ctx = $canvas[0].getContext('2d');
        
        // Group by country for comparison
        var datasets = [];
        var colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe'];
        var colorIndex = 0;

        Object.keys(this.analytics_by_country).forEach(function (country) {
            var countryData = self.analytics_by_country[country].slice(0, 6).reverse();
            var data = countryData.map(function (record) {
                return record.total_payroll;
            });
            
            datasets.push({
                label: country,
                data: data,
                borderColor: colors[colorIndex % colors.length],
                backgroundColor: colors[colorIndex % colors.length] + '20',
                tension: 0.4
            });
            colorIndex++;
        });

        var labels = this.analytics_data.slice(0, 6).reverse().map(function (record) {
            return record.period_name.split(' - ')[0];
        });

        this.charts.payrollTrend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Payroll Trend by Country'
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

    _renderCountryComparisonChart: function () {
        var self = this;
        var $canvas = this.$('#countryComparisonChart');
        if (!$canvas.length) return;

        var ctx = $canvas[0].getContext('2d');
        
        // Get latest data for each country
        var latestData = {};
        this.analytics_data.forEach(function (record) {
            if (!latestData[record.country_code] || 
                record.period_start > latestData[record.country_code].period_start) {
                latestData[record.country_code] = record;
            }
        });

        var labels = Object.keys(latestData);
        var employeeData = labels.map(function (country) {
            return latestData[country].total_employees;
        });
        var payrollData = labels.map(function (country) {
            return latestData[country].total_payroll;
        });

        this.charts.countryComparison = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Employees',
                    data: employeeData,
                    backgroundColor: '#667eea',
                    yAxisID: 'y'
                }, {
                    label: 'Payroll',
                    data: payrollData,
                    backgroundColor: '#764ba2',
                    yAxisID: 'y1'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Latest Country Comparison'
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
                        },
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

    _renderAnomalyChart: function () {
        var $canvas = this.$('#anomalyChart');
        if (!$canvas.length) return;

        var ctx = $canvas[0].getContext('2d');
        
        var labels = [];
        var data = [];
        
        this.analytics_data.slice(0, 12).reverse().forEach(function (record) {
            labels.push(record.period_name.split(' - ')[0]);
            data.push(record.anomaly_count);
        });

        this.charts.anomaly = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Anomalies Detected',
                    data: data,
                    backgroundColor: data.map(function (value) {
                        return value > 5 ? '#e74c3c' : value > 2 ? '#f39c12' : '#27ae60';
                    })
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Anomaly Detection Trend'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    },

    _destroyCharts: function () {
        Object.values(this.charts).forEach(function (chart) {
            if (chart && chart.destroy) {
                chart.destroy();
            }
        });
        this.charts = {};
    },

    // Event Handlers
    _onAnalyticsCardClick: function (event) {
        var $card = $(event.currentTarget);
        var analyticsId = $card.data('id');
        
        if (analyticsId) {
            this._openAnalyticsDetails(analyticsId);
        }
    },

    _onGenerateAnalytics: function (event) {
        event.preventDefault();
        this._openGenerateAnalyticsWizard();
    },

    _onExportAnalytics: function (event) {
        event.preventDefault();
        this._exportAnalyticsData();
    },

    _onComparePeriods: function (event) {
        event.preventDefault();
        this._openComparisonWizard();
    },

    _onCountryFilterChange: function (event) {
        this.current_country = $(event.target).val();
        this._refreshAnalytics();
    },

    _onPeriodFilterChange: function (event) {
        this.current_period = $(event.target).val();
        this._refreshAnalytics();
    },

    _onMetricDrillDown: function (event) {
        event.preventDefault();
        event.stopPropagation();
        
        var analyticsId = $(event.currentTarget).data('id');
        this._openAnalyticsDetails(analyticsId);
    },

    _onRefreshAnalytics: function (event) {
        event.preventDefault();
        this._refreshAnalytics();
    },

    // Analytics Actions
    _openAnalyticsDetails: function (analyticsId) {
        this.do_action({
            name: _t('Analytics Details'),
            type: 'ir.actions.act_window',
            res_model: 'payroll.analytics',
            res_id: analyticsId,
            view_mode: 'form',
            target: 'new'
        });
    },

    _openGenerateAnalyticsWizard: function () {
        this.do_action({
            name: _t('Generate Analytics'),
            type: 'ir.actions.act_window',
            res_model: 'analytics.wizard',
            view_mode: 'form',
            target: 'new',
            context: {
                default_country_code: this.current_country !== 'all' ? this.current_country : false
            }
        });
    },

    _exportAnalyticsData: function () {
        var self = this;
        framework.blockUI();
        
        rpc.query({
            model: 'payroll.analytics',
            method: 'export_analytics_excel',
            args: [this.analytics_data.map(function (record) { return record.id; })]
        }).then(function (result) {
            if (result.url) {
                window.open(result.url, '_blank');
            }
        }).catch(function (error) {
            self._showError(_t('Failed to export analytics data'));
        }).finally(function () {
            framework.unblockUI();
        });
    },

    _openComparisonWizard: function () {
        this.do_action({
            name: _t('Compare Periods'),
            type: 'ir.actions.act_window',
            res_model: 'payroll.comparison.wizard',
            view_mode: 'form',
            target: 'new'
        });
    },

    _refreshAnalytics: function () {
        var self = this;
        if (this.isLoading) return;
        
        this.isLoading = true;
        this._showLoadingIndicator();
        
        this._fetchAnalyticsData().then(function () {
            self._initializeAnalytics();
            self._destroyCharts();
            self._renderCharts();
        }).finally(function () {
            self.isLoading = false;
            self._hideLoadingIndicator();
        });
    },

    // Utility Functions
    _setupFilters: function () {
        var self = this;
        
        // Setup country filter
        var $countrySelect = this.$('.country-filter');
        $countrySelect.empty();
        $countrySelect.append('<option value="all">All Countries</option>');
        
        Object.keys(this.analytics_by_country).forEach(function (country) {
            $countrySelect.append(`<option value="${country}">${country}</option>`);
        });
        
        $countrySelect.val(this.current_country);
    },

    _setupTooltips: function () {
        this.$('[data-toggle="tooltip"]').tooltip();
    },

    _bindEvents: function () {
        var self = this;
        
        // Setup real-time updates
        this.updateInterval = setInterval(function () {
            if (!self.isLoading) {
                self._refreshAnalytics();
            }
        }, 300000); // Refresh every 5 minutes
    },

    _getCountryFlag: function (countryCode) {
        var flags = {
            'VN': '🇻🇳', 'ID': '🇮🇩', 'IN': '🇮🇳',
            'SG': '🇸🇬', 'MY': '🇲🇾', 'TH': '🇹🇭', 'PH': '🇵🇭'
        };
        return flags[countryCode] || '🏴';
    },

    _getStateBadgeClass: function (state) {
        var classes = {
            'draft': 'secondary',
            'computing': 'info',
            'ready': 'warning',
            'approved': 'success',
            'archived': 'dark'
        };
        return classes[state] || 'secondary';
    },

    _formatCurrency: function (amount, currency) {
        return field_utils.format.monetary(amount, {currency_id: currency});
    },

    _showLoadingIndicator: function () {
        this.$('.analytics-loading').show();
    },

    _hideLoadingIndicator: function () {
        this.$('.analytics-loading').hide();
    },

    _showError: function (message) {
        this.displayNotification({
            title: _t('Error'),
            message: message,
            type: 'danger',
            sticky: true
        });
    }
});

// Register the widget
core.action_registry.add('payroll_analytics_dashboard', PayrollAnalytics);

return {
    PayrollAnalytics: PayrollAnalytics
};

});