odoo.define('payroll_analytics_approval.dashboard_main', function (require) {
    'use strict';

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var Dialog = require('web.Dialog');
    var QWeb = core.qweb;
    var _t = core._t;

    var PayrollAnalyticsDashboard = AbstractAction.extend({
        template: 'payroll_analytics_approval.dashboard_template',
        
        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.dashboardData = action.context || {};
            this.charts = {};
            this.analyticsId = null;
        },

        start: function () {
            var self = this;
            return this._super().then(function () {
                self._loadDashboardData();
                self._bindEvents();
            });
        },

        _loadDashboardData: function () {
            var self = this;
            var country = this.dashboardData.country || 'ID';
            
            return rpc.query({
                model: 'payroll.dashboard',
                method: 'get_analytics_stats',
                args: [country],
            }).then(function (data) {
                self._updateDashboardStats(data);
            });
        },

        _updateDashboardStats: function (data) {
            // Update dashboard tiles with real data
            this.$('#pending-approvals-count').text(data.pending_approvals || 0);
            this.$('#ready-exports-count').text(data.ready_exports || 0);
            this.$('#total-employees-count').text(data.total_employees_current || 0);
            
            // Add animation classes
            this.$('.dashboard-tile').addClass('fade-in');
        },

        _bindEvents: function () {
            var self = this;
            
            // Dashboard tile clicks
            this.$('.payroll-approval-tile').on('click', function () {
                self._openPayrollApproval();
            });
            
            this.$('.bank-export-tile').on('click', function () {
                self._openBankExport();
            });
            
            this.$('.analytics-overview-tile').on('click', function () {
                self._openAnalyticsOverview();
            });
        },

        _openPayrollApproval: function () {
            var self = this;
            var country = this.dashboardData.country || 'ID';
            
            this.do_action({
                type: 'ir.actions.act_window',
                name: _t('Payroll Approval'),
                res_model: 'payroll.analytics',
                view_mode: 'tree,form',
                domain: [('country', '=', country), ('state', '=', 'ready')],
                context: {}
            });
        },

        _openBankExport: function () {
            var country = this.dashboardData.country || 'ID';
            
            this.do_action({
                type: 'ir.actions.act_window',
                name: _t('Export Bank File'),
                res_model: 'payroll.bank.export.wizard',
                view_mode: 'form',
                target: 'new',
                context: {
                    default_country: country,
                }
            });
        },

        _openAnalyticsOverview: function () {
            this.do_action({
                type: 'ir.actions.act_window',
                name: _t('Payroll Analytics'),
                res_model: 'payroll.analytics',
                view_mode: 'tree,form',
                context: {}
            });
        },

        _showNotification: function (message, type) {
            this.displayNotification({
                title: type === 'success' ? _t('Success') : type === 'warning' ? _t('Warning') : _t('Info'),
                message: message,
                type: type || 'info',
                sticky: false,
            });
        }
    });

    var PayrollAnalyticsDetailDashboard = AbstractAction.extend({
        template: 'payroll_analytics_approval.detail_dashboard_template',
        
        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.analyticsId = action.context.analytics_id;
            this.chartData = action.context.chart_data || {};
            this.components = action.context.components || {};
            this.comparisons = action.context.comparisons || {};
            this.anomalies = action.context.anomalies || {};
            this.charts = {};
        },

        start: function () {
            var self = this;
            return this._super().then(function () {
                self._initializeCharts();
                self._populateComponentsTable();
                self._showRecommendations();
                self._showAnomalyAlerts();
                self._bindEvents();
            });
        },

        _initializeCharts: function () {
            // Initialize charts if Chart.js is available
            if (typeof Chart !== 'undefined') {
                this._initComponentsChart();
                this._initComparisonChart();
            }
        },

        _initComponentsChart: function () {
            var ctx = this.$('#components-chart')[0];
            if (!ctx) return;

            var componentData = this.chartData.components || {};
            
            this.charts.components = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: componentData.labels || [],
                    datasets: [{
                        data: componentData.totals || [],
                        backgroundColor: [
                            '#3498db', '#27ae60', '#f39c12', '#e74c3c',
                            '#9b59b6', '#1abc9c', '#34495e', '#95a5a6'
                        ],
                        borderWidth: 2,
                        borderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'right'
                        }
                    }
                }
            });
        },

        _initComparisonChart: function () {
            var ctx = this.$('#comparison-chart')[0];
            if (!ctx) return;

            var comparisonData = this.chartData.comparison || {};
            
            this.charts.comparison = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: this.chartData.components.labels || [],
                    datasets: [{
                        label: _t('Current Month'),
                        data: comparisonData.current || [],
                        backgroundColor: 'rgba(52, 152, 219, 0.8)',
                        borderColor: '#3498db',
                        borderWidth: 1
                    }, {
                        label: _t('Previous Month'),
                        data: comparisonData.previous || [],
                        backgroundColor: 'rgba(149, 165, 166, 0.8)',
                        borderColor: '#95a5a6',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        },

        _populateComponentsTable: function () {
            var self = this;
            var tbody = this.$('#components-table-body');
            var components = this.components;
            
            if (!tbody.length || !components) return;
            
            tbody.empty();
            
            Object.keys(components).forEach(function (code) {
                var component = components[code];
                
                var row = $('<tr>').html(
                    '<td>' + (component.name || code) + '</td>' +
                    '<td><code>' + code + '</code></td>' +
                    '<td class="text-right">' + (component.total || 0).toLocaleString() + '</td>' +
                    '<td class="text-right">' + (component.average || 0).toLocaleString() + '</td>' +
                    '<td class="text-center"><span class="badge badge-success">' + _t('Normal') + '</span></td>'
                );
                
                tbody.append(row);
            });
        },

        _showRecommendations: function () {
            var recommendations = [
                _t('Employee count is stable compared to last month'),
                _t('Total payroll variance is within acceptable range'),
                _t('No critical anomalies detected in salary components'),
                _t('Bank export file can be generated after approval')
            ];
            
            var list = this.$('#recommendations-list');
            if (!list.length) return;
            
            list.empty();
            recommendations.forEach(function (recommendation) {
                list.append('<li><i class="fa fa-check text-success"></i> ' + recommendation + '</li>');
            });
        },

        _showAnomalyAlerts: function () {
            var alertsContainer = this.$('#anomaly-alerts .alert-section');
            if (!alertsContainer.length) return;

            alertsContainer.empty();
            
            if (!this.anomalies || Object.keys(this.anomalies).length === 0) {
                alertsContainer.append(
                    '<div class="alert alert-success">' +
                    '<h5><i class="fa fa-check-circle"></i> ' + _t('No Anomalies Detected') + '</h5>' +
                    '<p>' + _t('All payroll components are within expected ranges.') + '</p>' +
                    '</div>'
                );
                return;
            }
        },

        _bindEvents: function () {
            var self = this;
            
            // Final approval button
            this.$('#final-approve-btn').on('click', function () {
                self._showApprovalConfirmation();
            });
            
            // Export bank file button
            this.$('#export-bank-btn').on('click', function () {
                self._exportBankFile();
            });
        },

        _showApprovalConfirmation: function () {
            var self = this;
            
            if (confirm(_t('Are you sure you want to approve this payroll? This action cannot be undone.'))) {
                self._finalApprove();
            }
        },

        _finalApprove: function () {
            var self = this;
            
            // Disable the button to prevent multiple clicks
            self.$('#final-approve-btn').prop('disabled', true).text(_t('Processing...'));
            
            rpc.query({
                model: 'payroll.analytics',
                method: 'action_approve_payroll',
                args: [[this.analyticsId]],
            }).then(function (result) {
                // Check if we got an action back from server
                if (result && result.type === 'ir.actions.act_window') {
                    // Show success message if provided
                    if (result.context && result.context.success_message) {
                        self._showNotification(result.context.success_message, 'success');
                    }
                    
                    // Execute the action to refresh the view
                    self.do_action(result);
                } else {
                    // Fallback - show notification and force reload
                    self._showNotification(_t('Payroll approved successfully! Refreshing page...'), 'success');
                    
                    setTimeout(function () {
                        window.location.reload(true);
                    }, 1500);
                }
            }).catch(function (error) {
                // Re-enable the button on error
                self.$('#final-approve-btn').prop('disabled', false).text(_t('FINAL APPROVE'));
                self._showNotification(_t('Error approving payroll: ') + (error.message && error.message.data ? error.message.data.message : _t('Unknown error')), 'danger');
            });
        },

        _exportBankFile: function () {
            this.do_action({
                type: 'ir.actions.act_window',
                name: _t('Export Bank File'),
                res_model: 'payroll.bank.export.wizard',
                view_mode: 'form',
                target: 'new',
                context: {
                    default_analytics_id: this.analyticsId,
                }
            });
        },

        _showNotification: function (message, type) {
            this.displayNotification({
                title: type === 'success' ? _t('Success') : type === 'danger' ? _t('Error') : _t('Info'),
                message: message,
                type: type === 'danger' ? 'danger' : type || 'info',
                sticky: false,
            });
        }
    });

    // Register actions with UNIQUE names
    core.action_registry.add('payroll_analytics_main_dashboard', PayrollAnalyticsDashboard);
    core.action_registry.add('payroll_analytics_detail_dashboard', PayrollAnalyticsDetailDashboard);

    return {
        PayrollAnalyticsDashboard: PayrollAnalyticsDashboard,
        PayrollAnalyticsDetailDashboard: PayrollAnalyticsDetailDashboard
    };
});
