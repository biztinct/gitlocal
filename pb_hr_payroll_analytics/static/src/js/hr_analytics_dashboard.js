/* HR Analytics Dashboard - Main Dashboard Controller */

console.log('[HR Analytics] Dashboard.js file loaded - about to define module');

odoo.define('pb_hr_payroll_analytics.Dashboard', function (require) {
    'use strict';

    console.log('[HR Analytics] Dashboard module definition starting...');

    var FormController = require('web.FormController');
    var FormView = require('web.FormView');
    var rpc = require('web.rpc');

    console.log('[HR Analytics] Attempting to load ChartLib...');
    var ChartLib;
    try {
        ChartLib = require('pb_hr_payroll_analytics.Charts');
        console.log('[HR Analytics] ChartLib loaded successfully');
    } catch(e) {
        console.warn('[HR Analytics] ChartLib not available, will use fallback');
        ChartLib = window.ChartLib || {};
    }

    console.log('[HR Analytics] FormController require complete, ChartLib available:', !!ChartLib);

    // Create custom FormController class
    var DashboardController = FormController.extend({
        events: _.extend({}, FormController.prototype.events, {
            'click .nav-link': '_onTabClick',
            'click button[name="action_refresh_all_analytics"]': '_onRefresh',
            'click button[name="action_export_report"]': '_onExport'
        }),

        init: function() {
            console.log('[HR Analytics] FormController init called with args:', arguments);
            this._super.apply(this, arguments);
            this.charts = {};
            this.chartJSLoaded = false;
            this.activeTab = 'personnel_costs';
            console.log('[HR Analytics] FormController initialized successfully');
        },

        willStart: function() {
            console.log('[HR Analytics] willStart called');
            return Promise.all([
                this._super.apply(this, arguments),
                this._loadChartJS()
            ]);
        },

        start: function() {
            console.log('[HR Analytics] start called');
            return this._super.apply(this, arguments).then(() => {
                console.log('[HR Analytics] Super start complete, scheduling dashboard setup...');
                this._scheduleDashboardSetup();
            });
        },

        _scheduleDashboardSetup: function() {
            var self = this;
            console.log('[HR Analytics] _scheduleDashboardSetup: Scheduling dashboard setup with 500ms delay');

            // Use setTimeout to ensure DOM is fully rendered before accessing canvas elements
            setTimeout(function() {
                console.log('[HR Analytics] _scheduleDashboardSetup: 500ms delay complete, initializing dashboard');
                try {
                    self._setupDashboard();
                    self._setupTabNavigation();
                    console.log('[HR Analytics] Dashboard setup complete');
                } catch(e) {
                    console.error('[HR Analytics] Error during dashboard setup:', e);
                }
            }, 500);
        },

        destroy: function() {
            console.log('[HR Analytics] Destroying charts');
            this._destroyAllCharts();
            this._super.apply(this, arguments);
        },

        // =====================================================================
        // CHART LOADING
        // =====================================================================

        _loadChartJS: function() {
            var self = this;
            return new Promise(function(resolve, reject) {
                if (window.Chart) {
                    console.log('[HR Analytics] Chart.js already loaded');
                    self.chartJSLoaded = true;
                    resolve();
                } else {
                    console.log('[HR Analytics] Loading Chart.js from CDN...');
                    // Load Chart.js from CDN
                    var script = document.createElement('script');
                    script.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
                    script.onload = function() {
                        console.log('[HR Analytics] Chart.js loaded successfully');
                        self.chartJSLoaded = true;
                        resolve();
                    };
                    script.onerror = function() {
                        console.error('[HR Analytics] Failed to load Chart.js');
                        reject(new Error('Failed to load Chart.js'));
                    };
                    document.head.appendChild(script);
                }
            });
        },

        // =====================================================================
        // DASHBOARD INITIALIZATION
        // =====================================================================

        _setupDashboard: function() {
            console.log('[HR Analytics] _setupDashboard called');
            console.log('[HR Analytics] Chart.js available:', !!window.Chart);
            console.log('[HR Analytics] ChartLib available:', !!ChartLib);
            console.log('[HR Analytics] chartJSLoaded:', this.chartJSLoaded);

            var self = this;
            this._setupMetricCards();
            console.log('[HR Analytics] Loading initial tab data (personnel_costs)...');
            this._loadTabData('personnel_costs');
        },

        _setupMetricCards: function() {
            console.log('[HR Analytics] Setting up metric cards...');
            // Update metric cards with data from form fields
            var data = this.record.data;

            // Update stat info boxes with current field values
            var headcountElements = document.querySelectorAll('.o_stat_value');
            console.log('[HR Analytics] Found ' + headcountElements.length + ' stat value elements');
            if (headcountElements.length > 0) {
                // Fields are auto-updated by Odoo's field widgets
                console.log('[HR Analytics] Dashboard stats loaded from field values');
            }
        },

        // =====================================================================
        // TAB MANAGEMENT
        // =====================================================================

        _setupTabNavigation: function() {
            var self = this;
            var tabs = document.querySelectorAll('.nav-link');
            tabs.forEach(function(tab) {
                tab.addEventListener('click', function(e) {
                    e.preventDefault();
                    var tabName = this.getAttribute('data-tab');
                    self._switchTab(tabName);
                });
            });
        },

        _onTabClick: function(e) {
            e.preventDefault();
            var tabName = e.currentTarget.getAttribute('data-tab');
            this._switchTab(tabName);
        },

        _switchTab: function(tabName) {
            // Hide all tabs
            document.querySelectorAll('[role="tabpanel"]').forEach(function(panel) {
                panel.style.display = 'none';
            });

            // Remove active class from all nav links
            document.querySelectorAll('.nav-link').forEach(function(link) {
                link.classList.remove('active');
            });

            // Show selected tab
            var tabPanel = document.querySelector('[data-tab-pane="' + tabName + '"]');
            if (tabPanel) {
                tabPanel.style.display = 'block';
            }

            // Add active class to clicked link
            var activeLink = document.querySelector('[data-tab="' + tabName + '"]');
            if (activeLink) {
                activeLink.classList.add('active');
            }

            this.activeTab = tabName;

            // Load data for this tab
            this._loadTabData(tabName);
        },

        _loadTabData: function(tabName) {
            console.log('[HR Analytics] _loadTabData called for tab:', tabName);
            var self = this;

            switch(tabName) {
                case 'personnel_costs':
                    console.log('[HR Analytics] Switching to personnel_costs tab');
                    this._loadPersonnelCostsCharts();
                    break;
                case 'cross_country':
                    console.log('[HR Analytics] Switching to cross_country tab');
                    this._loadCrossCountryCharts();
                    break;
                case 'statutory_contributions':
                    console.log('[HR Analytics] Switching to statutory_contributions tab');
                    this._loadStatutoryContribCharts();
                    break;
                case 'headcount':
                    console.log('[HR Analytics] Switching to headcount tab');
                    this._loadHeadcountCharts();
                    break;
                case 'dependents':
                    console.log('[HR Analytics] Switching to dependents tab');
                    this._loadDependentsCharts();
                    break;
                case 'budget_variance':
                    console.log('[HR Analytics] Switching to budget_variance tab');
                    this._loadBudgetVarianceCharts();
                    break;
                case 'annual_costs':
                    console.log('[HR Analytics] Switching to annual_costs tab');
                    this._loadAnnualCostsCharts();
                    break;
                default:
                    console.warn('[HR Analytics] Unknown tab name:', tabName);
            }
        },

        // =====================================================================
        // PERSONNEL COSTS CHARTS
        // =====================================================================

        _loadPersonnelCostsCharts: function() {
            console.log('[HR Analytics] Loading Personnel Costs charts...');
            try {
                // Sample data for Personnel Costs
                var departments = ['Engineering', 'Sales', 'Operations', 'HR', 'Finance'];
                var basicSalaries = [45000, 38000, 32000, 28000, 35000];
                var allowances = [5000, 4000, 3000, 2000, 4000];
                var contributions = [8000, 7000, 6000, 5000, 6500];

                // Chart 1: Cost Breakdown by Department (Doughnut)
                var doughnutEl = document.getElementById('doughnut-chart-personnel');
                console.log('[HR Analytics] doughnut-chart-personnel element:', doughnutEl);

                if (doughnutEl) {
                    console.log('[HR Analytics] Creating doughnut chart...');
                    var totalByCost = departments.map((d, i) => basicSalaries[i] + allowances[i] + contributions[i]);
                    ChartLib.destroyChart('doughnut-chart-personnel');
                    ChartLib.createDoughnutChart(
                        'doughnut-chart-personnel',
                        departments,
                        totalByCost,
                        ['#3498db', '#2ecc71', '#e74c3c', '#f39c12', '#9b59b6']
                    );
                    console.log('[HR Analytics] Doughnut chart created successfully');
                } else {
                    console.warn('[HR Analytics] doughnut-chart-personnel element not found in DOM');
                }

                // Chart 2: Salary Components (Stacked Bar)
                var stackedEl = document.getElementById('stacked-bar-chart-personnel');
                console.log('[HR Analytics] stacked-bar-chart-personnel element:', stackedEl);

                if (stackedEl) {
                    console.log('[HR Analytics] Creating stacked bar chart...');
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

                    ChartLib.destroyChart('stacked-bar-chart-personnel');
                    ChartLib.createStackedBarChart('stacked-bar-chart-personnel', departments, datasets);
                    console.log('[HR Analytics] Stacked bar chart created successfully');
                } else {
                    console.warn('[HR Analytics] stacked-bar-chart-personnel element not found in DOM');
                }

            } catch (e) {
                console.error('[HR Analytics] Error loading personnel costs charts:', e);
            }
        },

        // =====================================================================
        // CROSS COUNTRY CHARTS
        // =====================================================================

        _loadCrossCountryCharts: function() {
            console.log('[HR Analytics] Loading Cross Country charts...');
            try {
                // Sample data for cross-country comparison
                var countries = ['Vietnam', 'Indonesia', 'India', 'Singapore', 'Thailand', 'Malaysia', 'Cambodia'];
                var costs = [1245, 820, 420, 185, 85, 45, 25];
                var headcount = [450, 280, 120, 45, 32, 15, 8];

                // Bar chart: Cost by Country
                console.log('[HR Analytics] Looking for bar-chart-country-costs element');
                if (document.getElementById('bar-chart-country-costs')) {
                    console.log('[HR Analytics] Creating vertical bar chart for countries');
                    var datasets = [{
                        label: 'Total Personnel Cost (Millions)',
                        data: costs,
                        backgroundColor: '#3498db'
                    }];
                    ChartLib.destroyChart('bar-chart-country-costs');
                    ChartLib.createVerticalBarChart('bar-chart-country-costs', countries, datasets);
                    console.log('[HR Analytics] Country costs chart created');
                } else {
                    console.warn('[HR Analytics] bar-chart-country-costs element not found');
                }

                // Pie chart: Headcount Distribution
                console.log('[HR Analytics] Looking for pie-chart-headcount element');
                if (document.getElementById('pie-chart-headcount')) {
                    console.log('[HR Analytics] Creating pie chart for headcount');
                    ChartLib.destroyChart('pie-chart-headcount');
                    ChartLib.createPieChart('pie-chart-headcount', countries, headcount);
                    console.log('[HR Analytics] Headcount pie chart created');
                } else {
                    console.warn('[HR Analytics] pie-chart-headcount element not found');
                }

                // Scatter plot: Cost per Employee vs Headcount
                console.log('[HR Analytics] Looking for scatter-chart-costvsheadcount element');
                if (document.getElementById('scatter-chart-costvsheadcount')) {
                    console.log('[HR Analytics] Creating scatter chart');
                    var dataPoints = countries.map((c, i) => ({
                        x: headcount[i],
                        y: (costs[i] * 1000000) / headcount[i]
                    }));
                    ChartLib.destroyChart('scatter-chart-costvsheadcount');
                    ChartLib.createScatterChart('scatter-chart-costvsheadcount', dataPoints);
                    console.log('[HR Analytics] Scatter chart created');
                } else {
                    console.warn('[HR Analytics] scatter-chart-costvsheadcount element not found');
                }
            } catch (e) {
                console.error('[HR Analytics] Error loading cross country charts:', e);
            }
        },

        // =====================================================================
        // STATUTORY CONTRIBUTIONS CHARTS
        // =====================================================================

        _loadStatutoryContribCharts: function() {
            try {
                // Sample data for Statutory Contributions
                var contribTypes = ['Social Insurance', 'Health Insurance', 'Unemployment Insurance'];
                var employeeData = [5000, 3000, 500];
                var employerData = [8000, 4000, 1000];
                var totals = [13000, 7000, 1500];

                // Chart 1: Contribution Type Breakdown (Doughnut)
                if (document.getElementById('doughnut-chart-statutory')) {
                    ChartLib.destroyChart('doughnut-chart-statutory');
                    ChartLib.createDoughnutChart('doughnut-chart-statutory', contribTypes, totals);
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
                console.error('Error loading statutory contribution charts:', e);
            }
        },

        // =====================================================================
        // HEADCOUNT CHARTS
        // =====================================================================

        _loadHeadcountCharts: function() {
            try {
                // Sample data for Headcount Analysis
                var types = ['Full-time', 'Part-time', 'Contractor'];
                var counts = [850, 125, 25];

                // Pie chart: Headcount by Type
                if (document.getElementById('pie-chart-hc-type')) {
                    ChartLib.destroyChart('pie-chart-hc-type');
                    ChartLib.createPieChart('pie-chart-hc-type', types, counts);
                }

            } catch (e) {
                console.error('Error loading headcount charts:', e);
            }
        },

        // =====================================================================
        // DEPENDENTS CHARTS
        // =====================================================================

        _loadDependentsCharts: function() {
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
                ChartLib.destroyChart('bar-chart-dependents');
                ChartLib.createVerticalBarChart('bar-chart-dependents', departments, datasets);
            }
        },

        // =====================================================================
        // BUDGET VARIANCE CHARTS
        // =====================================================================

        _loadBudgetVarianceCharts: function() {
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
                            label: 'Budgeted',
                            data: budgetAmounts,
                            backgroundColor: '#3498db'
                        },
                        {
                            label: 'Actual',
                            data: actualAmounts,
                            backgroundColor: '#2ecc71'
                        }
                    ];

                    ChartLib.destroyChart('grouped-bar-chart-budget');
                    ChartLib.createVerticalBarChart('grouped-bar-chart-budget', departments, datasets);
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

                    ChartLib.destroyChart('bar-chart-variance');
                    ChartLib.createVerticalBarChart('bar-chart-variance', departments, datasets);
                }

            } catch (e) {
                console.error('Error loading budget variance charts:', e);
            }
        },

        // =====================================================================
        // ANNUAL COSTS CHARTS
        // =====================================================================

        _loadAnnualCostsCharts: function() {
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
        // CHART CLEANUP
        // =====================================================================

        _destroyAllCharts: function() {
            ChartLib.destroyAllCharts();
        },

        // =====================================================================
        // ACTION HANDLERS
        // =====================================================================

        _onRefresh: function(e) {
            e.preventDefault();
            this._refreshAllAnalytics();
        },

        _refreshAllAnalytics: function() {
            var self = this;
            rpc.query({
                model: 'hr.analytics.dashboard',
                method: 'action_refresh_all_analytics',
                args: [this.recordID]
            }).then(function() {
                self._setupDashboard();
                self._loadTabData(self.activeTab);
                self.do_notify('Success', 'Analytics refreshed successfully');
            });
        },

        _onExport: function(e) {
            e.preventDefault();
            // Open export wizard
        }
    });

    console.log('[HR Analytics] DashboardController class created successfully');
    console.log('[HR Analytics] Registering DashboardController as pb_hr_payroll_analytics.Dashboard');

    // =====================================================================
    // FORMVIEW EXTENSION - Inject DashboardController
    // =====================================================================

    console.log('[HR Analytics] Creating FormView extension to inject custom controller...');

    // Create a custom FormView that uses our DashboardController
    var DashboardFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: DashboardController,
        }),

        init: function(viewInfo, params) {
            console.log('[HR Analytics] DashboardFormView init called for model:', viewInfo.model);

            // Always use our custom controller for dashboard views
            if (viewInfo.model === 'hr.analytics.dashboard') {
                console.log('[HR Analytics] Setting up DashboardController for hr.analytics.dashboard');
                viewInfo.controllerClass = DashboardController;
                this.config.Controller = DashboardController;
            }

            return this._super.apply(this, arguments);
        }
    });

    console.log('[HR Analytics] FormView extension created successfully');

    // =====================================================================
    // REGISTER FORMVIEW IN VIEWREGISTRY
    // =====================================================================

    console.log('[HR Analytics] Registering DashboardFormView in viewRegistry with key "hr_analytics_dashboard"');

    try {
        var viewRegistry = require('web.view_registry');

        // Register the DashboardFormView with the exact js_class name from the form view XML
        viewRegistry.add('hr_analytics_dashboard', DashboardFormView);

        console.log('[HR Analytics] DashboardFormView successfully registered in viewRegistry');
        console.log('[HR Analytics] This FormView will be used for forms with js_class="hr_analytics_dashboard"');
    } catch(e) {
        console.error('[HR Analytics] Error registering DashboardFormView in viewRegistry:', e);
    }

    return DashboardController;
});

console.log('[HR Analytics] Dashboard module fully loaded and exported');
