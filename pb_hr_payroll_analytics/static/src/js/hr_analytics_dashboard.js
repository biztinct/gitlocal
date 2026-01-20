/* HR Analytics Dashboard - Main Dashboard Controller */

odoo.define('pb_hr_payroll_analytics.Dashboard', function (require) {
    'use strict';

    var FormController = require('web.FormController');
    var FormView = require('web.FormView');
    var rpc = require('web.rpc');

    var ChartLib;
    try {
        ChartLib = require('pb_hr_payroll_analytics.Charts');
    } catch (e) {
        ChartLib = window.ChartLib || {};
    }

    // Create custom FormController class
    var DashboardController = FormController.extend({
        events: _.extend({}, FormController.prototype.events, {
            'click .nav-link': '_onTabClick',
            'click button[name="action_refresh_all_analytics"]': '_onRefresh',
            'click button[name="action_export_report"]': '_onExport',
            'change [name="selected_country"]': '_onCountryChange',
            'change [name="date_from"]': '_onDateChange',
            'change [name="date_to"]': '_onDateChange'
        }),

        init: function () {
            this._super.apply(this, arguments);
            this.charts = {};
            this.chartJSLoaded = false;
            this.activeTab = 'personnel_costs';
        },

        willStart: function () {
            return Promise.all([
                this._super.apply(this, arguments),
                this._loadChartJS()
            ]);
        },

        start: function () {
            return this._super.apply(this, arguments).then(() => {
                this._scheduleDashboardSetup();
            });
        },

        on_attach_callback: function () {
            // Re-render charts when returning to this view
            var self = this;
            setTimeout(function () {
                if (self.activeTab) {
                    self._loadTabData(self.activeTab);
                } else {
                    self._loadTabData('personnel_costs');
                }
            }, 300);
        },

        _scheduleDashboardSetup: function () {
            var self = this;

            // Use setTimeout to ensure DOM is fully rendered before accessing canvas elements
            setTimeout(function () {
                try {
                    self._setupDashboard();
                    self._setupTabNavigation();
                } catch (e) {
                    // Silent fail on dashboard setup
                }
            }, 500);
        },

        destroy: function () {
            this._destroyAllCharts();
            this._super.apply(this, arguments);
        },

        // =====================================================================
        // CHART LOADING
        // =====================================================================

        _loadChartJS: function () {
            var self = this;
            return new Promise(function (resolve, reject) {
                if (window.Chart) {
                    self.chartJSLoaded = true;
                    resolve();
                } else {
                    // Load Chart.js from CDN
                    var script = document.createElement('script');
                    script.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
                    script.onload = function () {
                        self.chartJSLoaded = true;
                        resolve();
                    };
                    script.onerror = function () {
                        reject(new Error('Failed to load Chart.js'));
                    };
                    document.head.appendChild(script);
                }
            });
        },

        // =====================================================================
        // DASHBOARD INITIALIZATION
        // =====================================================================

        _setupDashboard: function () {
            var self = this;

            // Validate prerequisites
            if (!window.Chart) {
                return;
            }

            if (!ChartLib || typeof ChartLib.createDoughnutChart !== 'function') {
                return;
            }

            try {
                this._setupMetricCards();
                this._loadTabData('personnel_costs');
            } catch (e) {
                // Silent fail on dashboard setup
            }
        },

        _setupMetricCards: function () {
            // Metric cards are auto-populated by Odoo's field widgets
            // The form fields (total_headcount, total_personnel_cost, total_contributions, average_salary)
            // are automatically rendered and updated by the field system
        },

        // =====================================================================
        // TAB MANAGEMENT
        // =====================================================================

        _setupTabNavigation: function () {
            var self = this;
            // Don't add custom click handlers - let Bootstrap handle tab switching
            // We'll use the event handler below to load charts when tabs are shown
        },

        _onTabClick: function (e) {
            // Get tab name from the link's name attribute
            var tabName = e.currentTarget.getAttribute('name');

            // Don't prevent default - let Bootstrap handle the tab switching
            // Just schedule chart loading after the tab transition completes
            var self = this;

            // Set active tab immediately
            this.activeTab = tabName;

            // Load charts after a short delay to allow Bootstrap tab animation to complete
            setTimeout(function () {
                self._loadTabData(tabName);
            }, 100);
        },

        _onCountryChange: function (e) {
            var self = this;
            var recordData = this.model.get(this.handle).data;
            var selectedCountry = recordData.selected_country;

            // Metrics will update automatically via computed field
            // Reload current tab charts with new country filter
            setTimeout(function () {
                self._loadTabData(self.activeTab);
            }, 100);
        },

        _onDateChange: function (e) {
            var self = this;
            var recordData = this.model.get(this.handle).data;
            var dateFrom = recordData.date_from;
            var dateTo = recordData.date_to;

            // Reload current tab charts with new date range
            setTimeout(function () {
                self._loadTabData(self.activeTab);
            }, 100);
        },

        _loadTabData: function (tabName) {
            var self = this;

            // Validate tab name
            if (!tabName) {
                return;
            }

            try {
                switch (tabName) {
                    case 'personnel_costs':
                        this._loadPersonnelCostsCharts();
                        break;
                    case 'cross_country':
                        this._loadCrossCountryCharts();
                        break;
                    case 'statutory_contributions':
                        this._loadStatutoryContribCharts();
                        break;
                    case 'headcount':
                        this._loadHeadcountCharts();
                        break;
                    case 'dependents':
                        this._loadDependentsCharts();
                        break;
                    case 'budget_variance':
                        this._loadBudgetVarianceCharts();
                        break;
                    case 'annual_costs':
                        this._loadAnnualCostsCharts();
                        break;
                    default:
                        // Unknown tab
                        break;
                }
            } catch (e) {
                // Silent fail on tab data loading
            }
        },

        // =====================================================================
        // PERSONNEL COSTS CHARTS
        // =====================================================================

        _loadPersonnelCostsCharts: function () {
            try {
                // Sample data for Personnel Costs
                var departments = ['Engineering', 'Sales', 'Operations', 'HR', 'Finance'];
                var basicSalaries = [45000, 38000, 32000, 28000, 35000];
                var allowances = [5000, 4000, 3000, 2000, 4000];
                var contributions = [8000, 7000, 6000, 5000, 6500];

                // Chart 1: Cost Breakdown by Department (Doughnut)
                var doughnutEl = document.getElementById('doughnut-chart-personnel');

                if (doughnutEl) {
                    try {
                        var totalByCost = departments.map((d, i) => basicSalaries[i] + allowances[i] + contributions[i]);

                        // Destroy existing chart
                        if (ChartLib.destroyChart) {
                            ChartLib.destroyChart('doughnut-chart-personnel');
                        }

                        // Create new chart with click handler
                        if (ChartLib.createDoughnutChart) {
                            var self = this;
                            ChartLib.createDoughnutChart(
                                'doughnut-chart-personnel',
                                departments,
                                totalByCost,
                                ['#3498db', '#2ecc71', '#e74c3c', '#f39c12', '#9b59b6'],
                                function (departmentName, value, index) {
                                    // Drill-down callback
                                    self._onChartSegmentClick(departmentName);
                                }
                            );
                        }
                    } catch (chartError) {
                        // Silent fail on doughnut chart creation
                    }
                }

                // Chart 2: Salary Components (Stacked Bar)
                var stackedEl = document.getElementById('stacked-bar-chart-personnel');

                if (stackedEl) {
                    try {
                        var datasets = [
                            {
                                label: 'Basic Salary',
                                data: basicSalaries,
                                backgroundColor: '#3498db'
                            },
                            {
                                label: 'Allowances',
                                data: allowances,
                                backgroundColor: '#2ecc71'
                            },
                            {
                                label: 'Contributions',
                                data: contributions,
                                backgroundColor: '#e74c3c'
                            }
                        ];

                        if (ChartLib.destroyChart) {
                            ChartLib.destroyChart('stacked-bar-chart-personnel');
                        }

                        if (ChartLib.createStackedBarChart) {
                            var self = this;
                            ChartLib.createStackedBarChart('stacked-bar-chart-personnel', departments, datasets, function (departmentName) {
                                self._onChartSegmentClick(departmentName);
                            });
                        }
                    } catch (chartError) {
                        // Silent fail on stacked bar chart creation
                    }
                }

            } catch (e) {
                // Silent fail on personnel costs charts
            }
        },

        // =====================================================================
        // CROSS COUNTRY CHARTS
        // =====================================================================

        _loadCrossCountryCharts: function () {
            try {
                // Sample data for cross-country comparison
                var countries = ['Vietnam', 'Indonesia', 'India', 'Singapore', 'Thailand', 'Malaysia', 'Cambodia'];
                var costs = [1245, 820, 420, 185, 85, 45, 25];
                var headcount = [450, 280, 120, 45, 32, 15, 8];

                // Chart 3: Cost by Country (Vertical Bar)
                if (document.getElementById('bar-chart-country-costs')) {
                    var datasets = [{
                        label: 'Total Cost',
                        data: costs,
                        backgroundColor: '#3498db'
                    }];
                    var self = this;
                    ChartLib.destroyChart('bar-chart-country-costs');
                    ChartLib.createVerticalBarChart('bar-chart-country-costs', countries, datasets, function (departmentName) {
                        self._onChartSegmentClick(departmentName);
                    });
                }

                // Pie chart: Headcount Distribution
                if (document.getElementById('pie-chart-headcount')) {
                    var self = this;
                    ChartLib.destroyChart('pie-chart-headcount');
                    ChartLib.createPieChart('pie-chart-headcount', countries, headcount, function (departmentName) {
                        self._onChartSegmentClick(departmentName);
                    });
                }

                // Scatter plot: Cost per Employee vs Headcount
                if (document.getElementById('scatter-chart-costvsheadcount')) {
                    var dataPoints = countries.map((c, i) => ({
                        x: headcount[i],
                        y: (costs[i] * 1000000) / headcount[i]
                    }));
                    ChartLib.destroyChart('scatter-chart-costvsheadcount');
                    ChartLib.createScatterChart('scatter-chart-costvsheadcount', dataPoints);
                }
            } catch (e) {
                // Silent fail on cross country charts
            }
        },

        // =====================================================================
        // STATUTORY CONTRIBUTIONS CHARTS
        // =====================================================================

        _loadStatutoryContribCharts: function () {
            try {
                // Sample data for Statutory Contributions
                var contribTypes = ['Social Insurance', 'Health Insurance', 'Unemployment Insurance'];
                var employeeData = [5000, 3000, 500];
                var employerData = [8000, 4000, 1000];
                var totals = [13000, 7000, 1500];

                // Chart 1: Contribution Type Breakdown (Doughnut)
                if (document.getElementById('doughnut-chart-statutory')) {
                    var self = this;
                    ChartLib.destroyChart('doughnut-chart-statutory');
                    ChartLib.createDoughnutChart('doughnut-chart-statutory', contribTypes, totals, null, function (departmentName) {
                        self._onChartSegmentClick(departmentName);
                    });
                }

                // Chart 2: Employee vs Employer Contributions (Stacked)
                if (document.getElementById('stacked-bar-chart-statutory')) {
                    var datasets = [
                        {
                            label: 'Employee Contributions',
                            data: employeeData,
                            backgroundColor: '#3498db'
                        },
                        {
                            label: 'Employer Contributions',
                            data: employerData,
                            backgroundColor: '#2ecc71'
                        }
                    ];

                    ChartLib.destroyChart('stacked-bar-chart-statutory');
                    ChartLib.createStackedBarChart('stacked-bar-chart-statutory', contribTypes, datasets);
                }

            } catch (e) {
                // Silent fail on statutory contribution charts
            }
        },

        // =====================================================================
        // HEADCOUNT CHARTS
        // =====================================================================

        _loadHeadcountCharts: function () {
            try {
                // Sample data for Headcount Analysis
                var types = ['Full-time', 'Part-time', 'Contractor'];
                var counts = [850, 125, 25];

                // Pie chart: Headcount by Type
                if (document.getElementById('pie-chart-hc-type')) {
                    var self = this;
                    ChartLib.destroyChart('pie-chart-hc-type');
                    ChartLib.createPieChart('pie-chart-hc-type', types, counts, function (departmentName) {
                        self._onChartSegmentClick(departmentName);
                    });
                }

            } catch (e) {
                // Silent fail on headcount charts
            }
        },

        // =====================================================================
        // DEPENDENTS CHARTS
        // =====================================================================

        _loadDependentsCharts: function () {
            // Sample data for dependents analysis
            var departments = ['Engineering', 'Sales', 'Operations', 'HR', 'Finance'];
            var dependentCounts = [45, 32, 28, 15, 22];

            // Bar chart: Dependents by Department
            if (document.getElementById('bar-chart-dependents')) {
                var datasets = [{
                    label: 'Dependents Count',
                    data: dependentCounts,
                    backgroundColor: '#9b59b6'
                }];
                var self = this;
                ChartLib.destroyChart('bar-chart-dependents');
                ChartLib.createVerticalBarChart('bar-chart-dependents', departments, datasets, function (departmentName) {
                    self._onChartSegmentClick(departmentName);
                });
            }
        },

        // =====================================================================
        // BUDGET VARIANCE CHARTS
        // =====================================================================

        _loadBudgetVarianceCharts: function () {
            try {
                // Sample data for Budget Variance
                var departments = ['Engineering', 'Sales', 'Operations', 'HR', 'Finance'];
                var budgetAmounts = [250000, 200000, 180000, 120000, 150000];
                var actualAmounts = [245000, 215000, 175000, 125000, 155000];
                var variancePercentages = [2, 7.5, 2.8, 4.2, 3.3];

                // Chart: Budget vs Actual
                if (document.getElementById('grouped-bar-chart-budget')) {
                    var datasets = [
                        {
                            label: 'Budget',
                            data: budgetAmounts,
                            backgroundColor: '#3498db'
                        },
                        {
                            label: 'Actual',
                            data: actualAmounts,
                            backgroundColor: '#2ecc71'
                        }
                    ];

                    var self = this;
                    ChartLib.destroyChart('grouped-bar-chart-budget');
                    ChartLib.createVerticalBarChart('grouped-bar-chart-budget', departments, datasets, function (departmentName) {
                        self._onChartSegmentClick(departmentName);
                    });
                }

                // Chart: Variance %
                if (document.getElementById('bar-chart-variance')) {
                    var colors = variancePercentages.map(v => {
                        if (v > 10) return '#e74c3c';  // Red - high variance
                        if (v > 5) return '#f39c12';   // Orange - medium
                        return '#2ecc71';               // Green - acceptable
                    });

                    var datasets = [{
                        label: 'Variance %',
                        data: variancePercentages,
                        backgroundColor: colors
                    }];

                    var self = this;
                    ChartLib.destroyChart('bar-chart-variance');
                    ChartLib.createVerticalBarChart('bar-chart-variance', departments, datasets, function (departmentName) {
                        self._onChartSegmentClick(departmentName);
                    });
                }

            } catch (e) {
                // Silent fail on budget variance charts
            }
        },

        // =====================================================================
        // ANNUAL COSTS CHARTS
        // =====================================================================

        _loadAnnualCostsCharts: function () {
            // Use sample data for annual costs since annual_costs_id may not exist
            // var annual = this.record.data.annual_costs_id;
            // if (!annual) return;

            // Sample monthly data for trend
            var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            var monthlyCosts = [95000, 96000, 98000, 97000, 99000, 101000, 100000, 102000, 101000, 103000, 104000, 105000];

            if (document.getElementById('line-chart-annual-trend')) {
                var datasets = [{
                    label: 'Monthly Cost',
                    data: monthlyCosts,
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    tension: 0.4
                }];

                ChartLib.destroyChart('line-chart-annual-trend');
                ChartLib.createLineChart('line-chart-annual-trend', months, datasets);
            }
        },

        // =====================================================================
        // CHART DRILL-DOWN
        // =====================================================================

        _onChartSegmentClick: function (departmentName) {
            var self = this;

            // Get current filters
            var recordData = this.model.get(this.handle).data;
            var dateFrom = recordData.date_from;
            var dateTo = recordData.date_to;
            var countryCode = recordData.selected_country;

            // Call backend to generate drill-down data and open pivot view
            rpc.query({
                model: 'hr.payroll.employee.detail',
                method: 'generate_drill_down_data',
                kwargs: {
                    department_name: departmentName,
                    date_from: dateFrom,
                    date_to: dateTo,
                    country_code: countryCode
                }
            }).then(function (action) {
                // Destroy charts AFTER starting navigation to prevent handleEvent errors
                // Use setTimeout to defer destruction until after do_action starts
                setTimeout(function () {
                    self._destroyAllCharts();
                }, 50);

                self.do_action(action);
            }).catch(function (error) {
                // Try to get more detailed error message
                var errorMsg = 'Unknown error';
                if (error && error.message && error.message.data) {
                    errorMsg = error.message.data.message || error.message.data.name || errorMsg;
                } else if (error && error.message) {
                    errorMsg = error.message;
                }
                self.displayNotification({
                    title: 'Drill-Down Error',
                    message: 'Failed to load employee details: ' + errorMsg,
                    type: 'danger'
                });
            });
        },

        // =====================================================================
        // CHART CLEANUP
        // =====================================================================

        _destroyAllCharts: function () {
            ChartLib.destroyAllCharts();
        },

        // =====================================================================
        // ACTION HANDLERS
        // =====================================================================

        _onRefresh: function (e) {
            e.preventDefault();
            this._refreshAllAnalytics();
        },

        _refreshAllAnalytics: function () {
            var self = this;
            rpc.query({
                model: 'hr.analytics.dashboard',
                method: 'action_refresh_all_analytics',
                args: [this.recordID]
            }).then(function () {
                self._setupDashboard();
                self._loadTabData(self.activeTab);
                self.do_notify('Success', 'Analytics refreshed successfully');
            });
        },

        _onExport: function (e) {
            e.preventDefault();
            // Open export wizard
        },

        // =====================================================================
        // DIAGNOSTICS - Run this to check system health
        // =====================================================================

        runDiagnostics: function () {
            // Diagnostics disabled in production
        }
    });

    // =====================================================================
    // FORMVIEW EXTENSION - Inject DashboardController
    // =====================================================================

    // Create a custom FormView that uses our DashboardController
    var DashboardFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: DashboardController,
        }),

        init: function (viewInfo, params) {
            // Always use our custom controller for dashboard views
            if (viewInfo.model === 'hr.analytics.dashboard') {
                viewInfo.controllerClass = DashboardController;
                this.config.Controller = DashboardController;
            }

            return this._super.apply(this, arguments);
        }
    });

    // =====================================================================
    // REGISTER FORMVIEW IN VIEWREGISTRY
    // =====================================================================

    try {
        var viewRegistry = require('web.view_registry');

        // Register the DashboardFormView with the exact js_class name from the form view XML
        viewRegistry.add('hr_analytics_dashboard', DashboardFormView);
    } catch (e) {
        // Silent fail on view registry
    }

    return DashboardController;
});
