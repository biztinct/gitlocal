/* Enhanced Payroll Dashboard JavaScript */
/* pb_hr_payroll_base/static/src/js/payroll_dashboard_enhanced.js */

odoo.define('pb_hr_payroll_base.dashboard_enhanced', function (require) {
'use strict';

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');
var rpc = require('web.rpc');
var session = require('web.session');
var Dialog = require('web.Dialog');
var framework = require('web.framework');

var QWeb = core.qweb;
var _t = core._t;

/**
 * Enhanced Payroll Dashboard Controller
 */
var PayrollDashboard = AbstractAction.extend({
    template: 'payroll_dashboard_enhanced',
    cssLibs: [
        '/pb_hr_payroll_base/static/src/css/payroll_dashboard_enhanced.css'
    ],
    
    events: {
        'click .country-card': '_onCountrySelect',
        'click .metric-card': '_onMetricClick', 
        'click .action-button': '_onActionClick',
        'click .refresh-btn': '_onRefreshClick',
        'keydown .country-card': '_onCountryKeydown',
    },

    init: function (parent, context) {
        this._super(parent, context);
        this.dashboards = [];
        this.accessRights = {};
        this.refreshInterval = null;
        this.isLoading = false;
    },

    willStart: function () {
        var self = this;
        return this._super().then(function () {
            return self._fetchDashboardData();
        });
    },

    start: function () {
        var self = this;
        return this._super().then(function () {
            self._initializeComponents();
            self._startAutoRefresh();
            self._bindEvents();
            self._animateMetrics();
        });
    },

    destroy: function () {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        this._super();
    },

    // Data Management
    _fetchDashboardData: function () {
        var self = this;
        return rpc.query({
            model: 'payroll.dashboard',
            method: 'get_dashboard_data',
            args: [],
        }).then(function (data) {
            self.dashboards = data;
            return self._fetchAccessRights();
        }).catch(function (error) {
            console.error('Error fetching dashboard data:', error);
            self._showError(_t('Failed to load dashboard data'));
        });
    },

    _fetchAccessRights: function () {
        var self = this;
        return rpc.query({
            route: '/api/payroll/countries',
            params: {},
        }).then(function (response) {
            if (response.success) {
                self.accessRights = {};
                response.data.forEach(function (country) {
                    self.accessRights[country.code] = true;
                });
            }
        }).catch(function (error) {
            console.warn('Could not fetch access rights:', error);
            // Fallback: assume access to all countries
            self.dashboards.forEach(function (dashboard) {
                self.accessRights[dashboard.country] = true;
            });
        });
    },

    // UI Initialization
    _initializeComponents: function () {
        this._renderCountryCards();
        this._setupTooltips();
        this._initializeSearch();
        this._setupAccessibilityFeatures();
    },

    _renderCountryCards: function () {
        var self = this;
        var $container = this.$('.countries-container');
        
        if (!$container.length) {
            $container = $('<div class="countries-container row">').appendTo(this.$el);
        }
        
        $container.empty();
        
        this.dashboards.forEach(function (dashboard) {
            var hasAccess = self.accessRights[dashboard.country] || false;
            var $card = self._createCountryCard(dashboard, hasAccess);
            $container.append($card);
        });
    },

    _createCountryCard: function (dashboard, hasAccess) {
        var flagEmoji = this._getCountryFlag(dashboard.country);
        var statusClass = this._getStatusClass(dashboard);
        
        var $card = $(`
            <div class="col-lg-4 col-md-6 col-sm-12 mb-4">
                <div class="payroll-country-card ${hasAccess ? 'has-access' : 'no-access'}" 
                     data-country="${dashboard.country}"
                     tabindex="0"
                     role="button"
                     aria-label="Open ${dashboard.country_name} payroll dashboard">
                     
                    <div class="country-card-header">
                        <div class="country-flag">${flagEmoji}</div>
                        <div class="country-name">${dashboard.name}</div>
                        <span class="status-indicator ${statusClass}"></span>
                    </div>
                    
                    <div class="country-metrics">
                        <div class="metric-row">
                            <div class="metric-item" title="Total Employees">
                                <span class="metric-icon">👥</span>
                                <span class="metric-value" data-count="${dashboard.employee_count}">0</span>
                                <span class="metric-label">Employees</span>
                            </div>
                            <div class="metric-item" title="Active Contracts">
                                <span class="metric-icon">📄</span>
                                <span class="metric-value" data-count="${dashboard.active_contracts}">0</span>
                                <span class="metric-label">Contracts</span>
                            </div>
                        </div>
                        
                        <div class="metric-row">
                            <div class="metric-item" title="Pending Payslips">
                                <span class="metric-icon">⏳</span>
                                <span class="metric-value" data-count="${dashboard.pending_payslips}">0</span>
                                <span class="metric-label">Pending</span>
                            </div>
                            <div class="metric-item" title="Total Gross Salary">
                                <span class="metric-icon">💰</span>
                                <span class="metric-value">${this._formatCurrency(dashboard.total_gross_salary, dashboard.currency)}</span>
                                <span class="metric-label">${dashboard.currency}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="country-actions">
                        <button class="btn btn-primary btn-sm" 
                                ${hasAccess ? '' : 'disabled'}>
                            ${hasAccess ? 'Open Dashboard' : 'No Access'}
                        </button>
                    </div>
                    
                    <div class="country-footer">
                        <small>Updated: ${this._formatDateTime(dashboard.last_updated)}</small>
                    </div>
                </div>
            </div>
        `);
        
        return $card;
    },

    // Event Handlers
    _onCountrySelect: function (event) {
        event.preventDefault();
        var $card = $(event.currentTarget).closest('.payroll-country-card');
        var country = $card.data('country');
        
        if (!this.accessRights[country]) {
            this._showAccessDenied(country);
            return;
        }
        
        this._openCountryDashboard(country, $card);
    },

    _onCountryKeydown: function (event) {
        if (event.keyCode === 13 || event.keyCode === 32) { // Enter or Space
            event.preventDefault();
            this._onCountrySelect(event);
        }
    },

    _onMetricClick: function (event) {
        event.stopPropagation();
        var $metric = $(event.currentTarget);
        var metricType = $metric.data('metric');
        
        if (metricType) {
            this._showMetricDetails(metricType);
        }
    },

    _onActionClick: function (event) {
        event.preventDefault();
        event.stopPropagation();
        
        var action = $(event.currentTarget).data('action');
        var country = $(event.currentTarget).closest('.payroll-country-card').data('country');
        
        this._executeAction(action, country);
    },

    _onRefreshClick: function (event) {
        event.preventDefault();
        this._refreshDashboard();
    },

    // Dashboard Actions
    _openCountryDashboard: function (country, $card) {
        var self = this;
        
        // Add loading state
        $card.addClass('loading');
        framework.blockUI();
        
        rpc.query({
            route: '/payroll/select-country',
            params: {
                country_code: country
            }
        }).then(function (response) {
            if (response.success) {
                if (response.action === 'dashboard' && response.action_id) {
                    self.do_action(response.action_id);
                } else if (response.menu_id) {
                    self.do_action({
                        type: 'ir.actions.client',
                        tag: 'menu',
                        params: {menu_id: response.menu_id}
                    });
                }
            } else {
                self._showError(response.message || _t('Failed to open dashboard'));
            }
        }).catch(function (error) {
            console.error('Error opening dashboard:', error);
            self._showError(_t('Failed to open dashboard'));
        }).finally(function () {
            $card.removeClass('loading');
            framework.unblockUI();
        });
    },

    _executeAction: function (action, country) {
        var actions = {
            'import_employees': this._importEmployees,
            'edit_spreadsheet': this._editSpreadsheet,
            'process_payroll': this._processPayroll,
            'view_analytics': this._viewAnalytics,
        };
        
        if (actions[action]) {
            actions[action].call(this, country);
        }
    },

    _importEmployees: function (country) {
        this.do_action({
            name: _t('Import Employees'),
            type: 'ir.actions.act_window',
            res_model: 'zoho.employee.import.wizard',
            view_mode: 'form',
            target: 'new',
            context: {
                default_country_code: country
            }
        });
    },

    _editSpreadsheet: function (country) {
        var url = `/payroll/spreadsheet/${country}`;
        window.open(url, '_blank');
    },

    _processPayroll: function (country) {
        this.do_action({
            name: _t('Process Payroll'),
            type: 'ir.actions.act_window',
            res_model: 'payroll.import.wizard',
            view_mode: 'form',
            target: 'new',
            context: {
                default_country_code: country
            }
        });
    },

    _viewAnalytics: function (country) {
        this.do_action({
            name: _t('Payroll Analytics'),
            type: 'ir.actions.act_window',
            res_model: 'payroll.analytics',
            view_mode: 'tree,form',
            domain: [['country_code', '=', country]],
            context: {
                default_country_code: country
            }
        });
    },

    // Auto Refresh
    _startAutoRefresh: function () {
        var self = this;
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        // Refresh every 5 minutes
        this.refreshInterval = setInterval(function () {
            self._refreshDashboard();
        }, 300000);
    },

    _refreshDashboard: function () {
        var self = this;
        
        if (this.isLoading) {
            return;
        }
        
        this.isLoading = true;
        this._showRefreshIndicator();
        
        this._fetchDashboardData().then(function () {
            self._renderCountryCards();
            self._animateMetrics();
            self._showNotification(_t('Dashboard refreshed'), 'success');
        }).catch(function (error) {
            self._showError(_t('Failed to refresh dashboard'));
        }).finally(function () {
            self.isLoading = false;
            self._hideRefreshIndicator();
        });
    },

    // Animations
    _animateMetrics: function () {
        var self = this;
        
        this.$('.metric-value[data-count]').each(function () {
            var $this = $(this);
            var targetCount = parseInt($this.data('count')) || 0;
            
            self._animateCounter($this, 0, targetCount, 1500);
        });
    },

    _animateCounter: function ($element, start, end, duration) {
        var range = end - start;
        var current = start;
        var increment = range / (duration / 16);
        
        var timer = setInterval(function () {
            current += increment;
            if (current >= end) {
                current = end;
                clearInterval(timer);
            }
            $element.text(Math.floor(current));
        }, 16);
    },

    // UI Helpers
    _setupTooltips: function () {
        this.$('[title]').tooltip({
            delay: { show: 500, hide: 100 }
        });
    },

    _initializeSearch: function () {
        var self = this;
        var $search = $('<input type="text" class="form-control mb-3" placeholder="Search countries...">');
        
        $search.on('input', function () {
            var query = $(this).val().toLowerCase();
            self._filterCountries(query);
        });
        
        this.$('.countries-container').before($search);
    },

    _filterCountries: function (query) {
        this.$('.payroll-country-card').each(function () {
            var $card = $(this);
            var countryName = $card.find('.country-name').text().toLowerCase();
            
            if (countryName.includes(query) || query === '') {
                $card.closest('.col-lg-4').show();
            } else {
                $card.closest('.col-lg-4').hide();
            }
        });
    },

    _setupAccessibilityFeatures: function () {
        // Add keyboard navigation
        this.$('.payroll-country-card').attr('tabindex', '0');
        
        // Add ARIA labels
        this.$('.metric-item').each(function () {
            var $item = $(this);
            var label = $item.find('.metric-label').text();
            var value = $item.find('.metric-value').text();
            $item.attr('aria-label', `${label}: ${value}`);
        });
    },

    // Utility Functions
    _getCountryFlag: function (countryCode) {
        var flags = {
            'VN': '🇻🇳',
            'ID': '🇮🇩', 
            'IN': '🇮🇳',
            'SG': '🇸🇬',
            'MY': '🇲🇾',
            'TH': '🇹🇭',
            'PH': '🇵🇭'
        };
        return flags[countryCode] || '🏴';
    },

    _getStatusClass: function (dashboard) {
        if (dashboard.pending_payslips > 10) {
            return 'status-warning';
        } else if (dashboard.pending_payslips > 0) {
            return 'status-warning';
        }
        return 'status-active';
    },

    _formatCurrency: function (amount, currency) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency || 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    },

    _formatDateTime: function (datetime) {
        if (!datetime) return 'Never';
        
        var date = new Date(datetime);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    // Notification and Error Handling
    _showNotification: function (message, type) {
        this.displayNotification({
            title: type === 'success' ? _t('Success') : _t('Information'),
            message: message,
            type: type || 'info',
            sticky: false
        });
    },

    _showError: function (message) {
        this.displayNotification({
            title: _t('Error'),
            message: message,
            type: 'danger',
            sticky: true
        });
    },

    _showAccessDenied: function (country) {
        Dialog.alert(this, _t('You do not have access to the %s payroll system. Please contact your administrator.', country), {
            title: _t('Access Denied')
        });
    },

    _showRefreshIndicator: function () {
        this.$('.refresh-btn').addClass('fa-spin');
    },

    _hideRefreshIndicator: function () {
        this.$('.refresh-btn').removeClass('fa-spin');
    },

    _showMetricDetails: function (metricType) {
        // Show detailed breakdown of the metric
        var self = this;
        
        rpc.query({
            route: '/api/payroll/metric-details',
            params: {
                metric: metricType
            }
        }).then(function (response) {
            if (response.success) {
                self._openMetricDialog(metricType, response.data);
            }
        }).catch(function (error) {
            console.error('Error fetching metric details:', error);
        });
    },

    _openMetricDialog: function (metricType, data) {
        var $content = $(`
            <div class="metric-details">
                <h4>${metricType} Details</h4>
                <div class="metric-breakdown">
                    <!-- Metric breakdown content -->
                </div>
            </div>
        `);
        
        Dialog.confirm(this, $content, {
            title: _t('Metric Details'),
            size: 'medium'
        });
    }
});

/**
 * Real-time Metrics Widget
 */
var MetricsWidget = AbstractAction.extend({
    template: 'payroll_metrics_widget',
    
    init: function (parent, options) {
        this._super(parent, options);
        this.country = options.country;
        this.autoRefresh = options.autoRefresh !== false;
        this.refreshInterval = null;
    },

    start: function () {
        var self = this;
        return this._super().then(function () {
            self._loadMetrics();
            if (self.autoRefresh) {
                self._startAutoRefresh();
            }
        });
    },

    destroy: function () {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        this._super();
    },

    _loadMetrics: function () {
        var self = this;
        return rpc.query({
            route: '/payroll/api/metrics/' + this.country,
            params: {}
        }).then(function (response) {
            if (response.success) {
                self._updateMetrics(response.data);
            }
        });
    },

    _updateMetrics: function (data) {
        this.$('.employee-count').text(data.employee_count);
        this.$('.active-contracts').text(data.active_contracts);
        this.$('.pending-payslips').text(data.pending_payslips);
        this.$('.total-salary').text(this._formatCurrency(data.total_gross_salary, data.currency));
        this.$('.last-updated').text(this._formatDateTime(data.last_updated));
    },

    _startAutoRefresh: function () {
        var self = this;
        this.refreshInterval = setInterval(function () {
            self._loadMetrics();
        }, 60000); // Refresh every minute
    },

    _formatCurrency: function (amount, currency) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency || 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    },

    _formatDateTime: function (datetime) {
        if (!datetime) return 'Never';
        var date = new Date(datetime);
        return date.toLocaleString();
    }
});

/**
 * Analytics Chart Widget
 */
var AnalyticsChart = AbstractAction.extend({
    template: 'payroll_analytics_chart',
    
    init: function (parent, options) {
        this._super(parent, options);
        this.chartType = options.chartType || 'line';
        this.country = options.country;
        this.period = options.period || 'monthly';
        this.chart = null;
    },

    start: function () {
        var self = this;
        return this._super().then(function () {
            return self._loadChartData().then(function () {
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

    _loadChartData: function () {
        var self = this;
        return rpc.query({
            model: 'payroll.analytics',
            method: 'get_chart_data',
            args: [this.country, this.period]
        }).then(function (data) {
            self.chartData = data;
        });
    },

    _renderChart: function () {
        var self = this;
        var ctx = this.$('canvas')[0].getContext('2d');
        
        // Load Chart.js if not already loaded
        if (typeof Chart === 'undefined') {
            this._loadChartJS().then(function () {
                self._createChart(ctx);
            });
        } else {
            this._createChart(ctx);
        }
    },

    _loadChartJS: function () {
        return new Promise(function (resolve) {
            var script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js';
            script.onload = resolve;
            document.head.appendChild(script);
        });
    },

    _createChart: function (ctx) {
        var chartConfig = this._getChartConfig();
        this.chart = new Chart(ctx, chartConfig);
    },

    _getChartConfig: function () {
        return {
            type: this.chartType,
            data: {
                labels: this.chartData.labels,
                datasets: [{
                    label: 'Payroll Amount',
                    data: this.chartData.values,
                    borderColor: 'rgb(102, 126, 234)',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: 'Payroll Analytics - ' + this.country
                    },
                    legend: {
                        display: true
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function (value) {
                                return new Intl.NumberFormat('en-US', {
                                    style: 'currency',
                                    currency: 'USD',
                                    minimumFractionDigits: 0
                                }).format(value);
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        };
    }
});

/**
 * Country Selector Widget
 */
var CountrySelector = AbstractAction.extend({
    template: 'payroll_country_selector',
    events: {
        'click .country-option': '_onCountrySelect',
        'keydown .country-option': '_onCountryKeydown'
    },

    init: function (parent, options) {
        this._super(parent, options);
        this.selectedCountry = options.selectedCountry;
        this.availableCountries = options.availableCountries || [];
        this.accessRights = options.accessRights || {};
    },

    start: function () {
        var self = this;
        return this._super().then(function () {
            self._renderCountryOptions();
            self._setupKeyboardNavigation();
        });
    },

    _renderCountryOptions: function () {
        var self = this;
        var $container = this.$('.country-options');
        
        this.availableCountries.forEach(function (country) {
            var hasAccess = self.accessRights[country.code];
            var $option = $(`
                <div class="country-option ${hasAccess ? 'accessible' : 'restricted'}" 
                     data-country="${country.code}"
                     tabindex="0"
                     role="button"
                     aria-label="Select ${country.name}">
                    <div class="country-flag">${self._getCountryFlag(country.code)}</div>
                    <div class="country-info">
                        <div class="country-name">${country.name}</div>
                        <div class="access-status">${hasAccess ? 'Accessible' : 'Restricted'}</div>
                    </div>
                    ${hasAccess ? '<i class="fa fa-check-circle"></i>' : '<i class="fa fa-lock"></i>'}
                </div>
            `);
            
            $container.append($option);
        });
    },

    _onCountrySelect: function (event) {
        var $option = $(event.currentTarget);
        var country = $option.data('country');
        
        if (!$option.hasClass('accessible')) {
            this._showAccessDenied(country);
            return;
        }
        
        this.trigger('country_selected', country);
    },

    _onCountryKeydown: function (event) {
        if (event.keyCode === 13 || event.keyCode === 32) {
            event.preventDefault();
            this._onCountrySelect(event);
        }
    },

    _setupKeyboardNavigation: function () {
        var self = this;
        this.$('.country-option').on('keydown', function (event) {
            var $current = $(this);
            var $options = self.$('.country-option');
            var currentIndex = $options.index($current);
            
            switch (event.keyCode) {
                case 38: // Up arrow
                    event.preventDefault();
                    if (currentIndex > 0) {
                        $options.eq(currentIndex - 1).focus();
                    }
                    break;
                case 40: // Down arrow
                    event.preventDefault();
                    if (currentIndex < $options.length - 1) {
                        $options.eq(currentIndex + 1).focus();
                    }
                    break;
            }
        });
    },

    _getCountryFlag: function (countryCode) {
        var flags = {
            'VN': '🇻🇳', 'ID': '🇮🇩', 'IN': '🇮🇳',
            'SG': '🇸🇬', 'MY': '🇲🇾', 'TH': '🇹🇭', 'PH': '🇵🇭'
        };
        return flags[countryCode] || '🏴';
    },

    _showAccessDenied: function (country) {
        Dialog.alert(this, _t('You do not have access to %s payroll. Please contact your administrator.', country), {
            title: _t('Access Denied')
        });
    }
});

/**
 * Payroll Action Executor
 */
var PayrollActionExecutor = {
    
    executeImportEmployees: function (country, context) {
        return rpc.query({
            model: 'zoho.employee.import.wizard',
            method: 'create_and_open',
            args: [{
                country_code: country
            }],
            context: context || {}
        });
    },

    executeProcessPayroll: function (country, context) {
        return rpc.query({
            model: 'payroll.import.wizard', 
            method: 'create_and_open',
            args: [{
                country_code: country
            }],
            context: context || {}
        });
    },

    executeGenerateAnalytics: function (country, periodStart, periodEnd) {
        return rpc.query({
            route: '/payroll/api/analytics/generate',
            params: {
                country_code: country,
                period_start: periodStart,
                period_end: periodEnd
            }
        });
    },

    executeExportBankFile: function (country, periodStart, periodEnd) {
        var url = `/api/payroll/export/bank-file/${country}`;
        if (periodStart) url += `?period_start=${periodStart}`;
        if (periodEnd) url += `${periodStart ? '&' : '?'}period_end=${periodEnd}`;
        
        window.open(url, '_blank');
    }
};

// Register widgets
core.action_registry.add('payroll_dashboard_enhanced', PayrollDashboard);
core.action_registry.add('payroll_metrics_widget', MetricsWidget);
core.action_registry.add('payroll_analytics_chart', AnalyticsChart);
core.action_registry.add('payroll_country_selector', CountrySelector);

// Export for use in other modules
return {
    PayrollDashboard: PayrollDashboard,
    MetricsWidget: MetricsWidget,
    AnalyticsChart: AnalyticsChart,
    CountrySelector: CountrySelector,
    PayrollActionExecutor: PayrollActionExecutor
};

});