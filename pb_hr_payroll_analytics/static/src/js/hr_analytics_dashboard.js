/* HR Analytics Dashboard - Main Dashboard Controller */

odoo.define('pb_hr_payroll_analytics.Dashboard', function (require) {
    'use strict';

    var FormController = require('web.FormController');
    var rpc = require('web.rpc');
    var ChartLib = require('pb_hr_payroll_analytics.Charts');

    return FormController.extend({
        events: _.extend({}, FormController.prototype.events, {
            'click .nav-link': '_onTabClick',
            'click button[name="action_refresh_all_analytics"]': '_onRefresh',
            'click button[name="action_export_report"]': '_onExport'
        }),

        init: function() {
            this._super.apply(this, arguments);
            this.charts = {};
            this.chartJSLoaded = false;
            this.activeTab = 'personnel_costs';
        },

        willStart: function() {
            return Promise.all([
                this._super.apply(this, arguments),
                this._loadChartJS()
            ]);
        },

        start: function() {
            return this._super.apply(this, arguments).then(() => {
                this._setupDashboard();
                this._setupTabNavigation();
            });
        },

        destroy: function() {
            this._destroyAllCharts();
            this._super.apply(this, arguments);
        },

        // =====================================================================
        // CHART LOADING
        // =====================================================================

        _loadChartJS: function() {
            return new Promise(function(resolve, reject) {
                if (window.Chart) {
                    resolve();
                } else {
                    // Load Chart.js from CDN
                    var script = document.createElement('script');
                    script.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
                    script.onload = resolve;
                    script.onerror = reject;
                    document.head.appendChild(script);
                }
            });
        },

        // =====================================================================
        // DASHBOARD INITIALIZATION
        // =====================================================================

        _setupDashboard: function() {
            var self = this;
            this._setupMetricCards();
            this._loadTabData('personnel_costs');
        },

        _setupMetricCards: function() {
            // Update metric cards with data
            var personnel_costs = this.renderer.state.data.personnel_costs_id;
            var statutory = this.renderer.state.data.statutory_contrib_id;
            var headcount = this.renderer.state.data.headcount_id;

            if (personnel_costs) {
                this._updateMetricCard('total_employees', headcount ? headcount.total_headcount : 0);
                this._updateMetricCard('total_personnel_cost', personnel_costs.total_personnel_cost);
                this._updateMetricCard('total_contributions', statutory ? statutory.total_contrib : 0);
                this._updateMetricCard('average_salary', personnel_costs.average_cost_per_employee);
            }
        },

        _updateMetricCard: function(cardId, value) {
            var element = document.querySelector('[data-metric="' + cardId + '"]');
            if (element) {
                element.textContent = ChartLib.formatCurrency(value);
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
            var self = this;

            switch(tabName) {
                case 'personnel_costs':
                    this._loadPersonnelCostsCharts();
                    break;
                case 'cross_country':
                    this._loadCrossCountryCharts();
                    break;
                case 'statutory_contrib':
                    this._loadStatutoryContribCharts();
                    break;
                case 'headcount':
                    this._loadHeadcountCharts();
                    break;
                case 'budget_variance':
                    this._loadBudgetVarianceCharts();
                    break;
                case 'annual_costs':
                    this._loadAnnualCostsCharts();
                    break;
            }
        },

        // =====================================================================
        // PERSONNEL COSTS CHARTS
        // =====================================================================

        _loadPersonnelCostsCharts: function() {
            var personnel_costs = this.renderer.state.data.personnel_costs_id;

            if (!personnel_costs) return;

            try {
                var direct_salaries = JSON.parse(personnel_costs.direct_salaries_json || '{}');
                var contrib = JSON.parse(personnel_costs.employer_contributions_json || '{}');
                var total_cost = JSON.parse(personnel_costs.total_cost_json || '{}');

                // Chart 1: Cost Breakdown by Department (Doughnut)
                var deptNames = Object.keys(direct_salaries);
                var deptSalaries = deptNames.map(d => direct_salaries[d].total || 0);

                if (document.getElementById('doughnut-chart-personnel')) {
                    ChartLib.destroyChart('doughnut-chart-personnel');
                    ChartLib.createDoughnutChart(
                        'doughnut-chart-personnel',
                        deptNames,
                        deptSalaries,
                        Object.values(ChartLib.colorPalettes.department).slice(0, deptNames.length)
                    );
                }

                // Chart 2: Salary Components (Stacked Bar)
                if (document.getElementById('stacked-bar-chart-personnel')) {
                    this._createSalaryComponentsChart(direct_salaries, contrib);
                }

            } catch (e) {
                console.log('Error loading personnel costs charts:', e);
            }
        },

        _createSalaryComponentsChart: function(salaries, contributions) {
            var deptNames = Object.keys(salaries);

            var basicData = deptNames.map(d => salaries[d].basic || 0);
            var allowanceData = deptNames.map(d => salaries[d].allowances || 0);
            var contribData = deptNames.map(d => contributions[d].total || 0);

            var datasets = [
                {
                    label: 'Basic Salary',
                    data: basicData,
                    backgroundColor: '#3498db'
                },
                {
                    label: 'Allowances',
                    data: allowanceData,
                    backgroundColor: '#2ecc71'
                },
                {
                    label: 'Contributions',
                    data: contribData,
                    backgroundColor: '#e74c3c'
                }
            ];

            ChartLib.destroyChart('stacked-bar-chart-personnel');
            ChartLib.createStackedBarChart('stacked-bar-chart-personnel', deptNames, datasets);
        },

        // =====================================================================
        // CROSS COUNTRY CHARTS
        // =====================================================================

        _loadCrossCountryCharts: function() {
            // Sample data for cross-country comparison
            var countries = ['Vietnam', 'Indonesia', 'India', 'Singapore', 'Thailand', 'Malaysia', 'Cambodia'];
            var costs = [1245, 820, 420, 185, 85, 45, 25];
            var headcount = [450, 280, 120, 45, 32, 15, 8];

            // Bar chart: Cost by Country
            if (document.getElementById('bar-chart-country-costs')) {
                var datasets = [{
                    label: 'Total Personnel Cost (Millions)',
                    data: costs,
                    backgroundColor: '#3498db'
                }];
                ChartLib.destroyChart('bar-chart-country-costs');
                ChartLib.createVerticalBarChart('bar-chart-country-costs', countries, datasets);
            }

            // Pie chart: Headcount Distribution
            if (document.getElementById('pie-chart-headcount')) {
                ChartLib.destroyChart('pie-chart-headcount');
                ChartLib.createPieChart('pie-chart-headcount', countries, headcount);
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
        },

        // =====================================================================
        // STATUTORY CONTRIBUTIONS CHARTS
        // =====================================================================

        _loadStatutoryContribCharts: function() {
            var statutory = this.renderer.state.data.statutory_contrib_id;

            if (!statutory) return;

            try {
                var contrib_summary = JSON.parse(statutory.contribution_summary || '{}');

                // Chart 1: Contribution Type Breakdown (Doughnut)
                var contribTypes = Object.keys(contrib_summary);
                var contribTotals = contribTypes.map(c => contrib_summary[c].total || 0);

                if (document.getElementById('doughnut-chart-statutory')) {
                    ChartLib.destroyChart('doughnut-chart-statutory');
                    ChartLib.createDoughnutChart('doughnut-chart-statutory', contribTypes, contribTotals);
                }

                // Chart 2: Employee vs Employer Contributions (Stacked)
                if (document.getElementById('stacked-bar-chart-statutory')) {
                    this._createContributionComparisonChart(contrib_summary, contribTypes);
                }

            } catch (e) {
                console.log('Error loading statutory contribution charts:', e);
            }
        },

        _createContributionComparisonChart: function(summary, contribTypes) {
            var employeeData = contribTypes.map(c => summary[c].employee || 0);
            var employerData = contribTypes.map(c => summary[c].employer || 0);

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
        },

        // =====================================================================
        // HEADCOUNT CHARTS
        // =====================================================================

        _loadHeadcountCharts: function() {
            var headcount = this.renderer.state.data.headcount_id;

            if (!headcount) return;

            try {
                var hc_by_type = JSON.parse(headcount.headcount_by_type || '{}');

                // Pie chart: Headcount by Type
                if (document.getElementById('pie-chart-hc-type')) {
                    var types = Object.keys(hc_by_type);
                    var counts = types.map(t => hc_by_type[t] || 0);

                    ChartLib.destroyChart('pie-chart-hc-type');
                    ChartLib.createPieChart('pie-chart-hc-type', types, counts);
                }

            } catch (e) {
                console.log('Error loading headcount charts:', e);
            }
        },

        // =====================================================================
        // BUDGET VARIANCE CHARTS
        // =====================================================================

        _loadBudgetVarianceCharts: function() {
            var budget = this.renderer.state.data.budget_variance_id;

            if (!budget) return;

            try {
                var budget_data = JSON.parse(budget.budget_data || '{}');
                var actual_data = JSON.parse(budget.actual_data || '{}');
                var variance_data = JSON.parse(budget.variance_json || '{}');

                var departments = Object.keys(budget_data);

                // Chart: Budget vs Actual
                if (document.getElementById('grouped-bar-chart-budget')) {
                    this._createBudgetComparisonChart(budget_data, actual_data, departments);
                }

                // Chart: Variance %
                if (document.getElementById('bar-chart-variance')) {
                    this._createVarianceChart(variance_data, departments);
                }

            } catch (e) {
                console.log('Error loading budget variance charts:', e);
            }
        },

        _createBudgetComparisonChart: function(budgets, actuals, departments) {
            var budgetAmounts = departments.map(d => budgets[d].budget || 0);
            var actualAmounts = departments.map(d => actuals[d].actual || 0);

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
        },

        _createVarianceChart: function(variance, departments) {
            var variancePercentages = departments.map(d => variance[d] ? variance[d].variance_pct : 0);

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
        },

        // =====================================================================
        // ANNUAL COSTS CHARTS
        // =====================================================================

        _loadAnnualCostsCharts: function() {
            var annual = this.renderer.state.data.annual_costs_id;

            if (!annual) return;

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
});
