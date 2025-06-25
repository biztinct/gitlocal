/* Payroll Analytics Dashboard JavaScript */

odoo.define('payroll_analytics_approval.dashboard', function (require) {
    'use strict';

    var FormController = require('web.FormController');
    var FormView = require('web.FormView');
    var viewRegistry = require('web.view_registry');
    var core = require('web.core');

    var PayrollAnalyticsDashboard = FormController.extend({
        
        init: function () {
            this._super.apply(this, arguments);
            this.charts = {};
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                if (self.modelName === 'payroll.analytics') {
                    self._initializeDashboard();
                }
            });
        },

        _initializeDashboard: function () {
            var self = this;
            
            // Load Chart.js if not already loaded
            if (typeof Chart === 'undefined') {
                this._loadChartJS().then(function () {
                    self._setupDashboard();
                });
            } else {
                this._setupDashboard();
            }
        },

        _loadChartJS: function () {
            return new Promise(function (resolve) {
                var script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
                script.onload = resolve;
                document.head.appendChild(script);
            });
        },

        _setupDashboard: function () {
            var self = this;
            
            // Get data from form fields
            var employeeMetrics = this._getFieldValue('employee_metrics');
            var salaryComponents = this._getFieldValue('salary_components');
            var comparisonData = this._getFieldValue('comparison_data');
            var anomalyAlerts = this._getFieldValue('anomaly_alerts');

            if (salaryComponents) {
                this._createCharts(JSON.parse(salaryComponents), JSON.parse(comparisonData || '{}'));
            }

            if (anomalyAlerts) {
                this._displayAnomalyAlerts(JSON.parse(anomalyAlerts));
            }

            if (salaryComponents && comparisonData) {
                this._populateAnalysisTable(JSON.parse(salaryComponents), JSON.parse(comparisonData || '{}'));
                this._generateRecommendations(JSON.parse(salaryComponents), JSON.parse(comparisonData || '{}'), JSON.parse(anomalyAlerts || '[]'));
            }

            // Add animations
            this._addAnimations();
        },

        _getFieldValue: function (fieldName) {
            var field = this.$('field[name="' + fieldName + '"]');
            return field.length ? field.text() : null;
        },

        _createCharts: function (components, comparison) {
            this._createComponentsChart(components);
            this._createComparisonChart(components, comparison);
            this._createVarianceChart(components, comparison);
        },

        _createComponentsChart: function (components) {
            var ctx = document.getElementById('componentsChart');
            if (!ctx) return;

            var labels = [];
            var data = [];
            var colors = [
                '#4fc3f7', '#66bb6a', '#ffa726', '#ef5350',
                '#ab47bc', '#42a5f5', '#26c6da', '#66bb6a',
                '#9ccc65', '#ffca28', '#ffa726', '#ff7043'
            ];

            Object.keys(components).forEach(function (code, index) {
                var component = components[code];
                labels.push(component.name || code);
                data.push(component.total || 0);
            });

            this.charts.components = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: colors.slice(0, data.length),
                        borderWidth: 0,
                        hoverBorderWidth: 3,
                        hoverBorderColor: '#fff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                usePointStyle: true,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    var label = context.label || '';
                                    var value = new Intl.NumberFormat().format(context.parsed);
                                    return label + ': ' + value;
                                }
                            }
                        }
                    },
                    animation: {
                        animateScale: true,
                        animateRotate: true
                    }
                }
            });
        },

        _createComparisonChart: function (components, comparison) {
            var ctx = document.getElementById('comparisonChart');
            if (!ctx) return;

            var labels = [];
            var currentData = [];
            var previousData = [];

            Object.keys(components).forEach(function (code) {
                var component = components[code];
                labels.push(component.name || code);
                currentData.push(component.total || 0);
                
                if (comparison.previous_month && comparison.previous_month[code]) {
                    previousData.push(comparison.previous_month[code].total || 0);
                } else {
                    previousData.push(0);
                }
            });

            this.charts.comparison = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Current Month',
                        data: currentData,
                        backgroundColor: 'rgba(102, 187, 106, 0.8)',
                        borderColor: 'rgba(102, 187, 106, 1)',
                        borderWidth: 2
                    }, {
                        label: 'Previous Month',
                        data: previousData,
                        backgroundColor: 'rgba(149, 165, 166, 0.8)',
                        borderColor: 'rgba(149, 165, 166, 1)',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return new Intl.NumberFormat().format(value);
                                }
                            }
                        },
                        x: {
                            ticks: {
                                maxRotation: 45
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top'
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    var label = context.dataset.label || '';
                                    var value = new Intl.NumberFormat().format(context.parsed.y);
                                    return label + ': ' + value;
                                }
                            }
                        }
                    },
                    animation: {
                        delay: function(context) {
                            return context.dataIndex * 100;
                        }
                    }
                }
            });
        },

        _createVarianceChart: function (components, comparison) {
            var ctx = document.getElementById('varianceChart');
            if (!ctx) return;

            var labels = [];
            var varianceData = [];
            var colors = [];

            Object.keys(components).forEach(function (code) {
                var component = components[code];
                labels.push(component.name || code);
                
                var variance = 0;
                if (comparison.variance && comparison.variance[code]) {
                    variance = comparison.variance[code];
                }
                
                varianceData.push(variance);
                
                // Color based on variance
                if (variance > 10) {
                    colors.push('rgba(76, 175, 80, 0.8)'); // Green for positive
                } else if (variance < -10) {
                    colors.push('rgba(244, 67, 54, 0.8)'); // Red for negative
                } else {
                    colors.push('rgba(149, 165, 166, 0.8)'); // Gray for neutral
                }
            });

            this.charts.variance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Variance %',
                        data: varianceData,
                        backgroundColor: colors,
                        borderColor: colors.map(c => c.replace('0.8', '1')),
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        },
                        x: {
                            ticks: {
                                maxRotation: 45
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return 'Variance: ' + context.parsed.y.toFixed(1) + '%';
                                }
                            }
                        }
                    },
                    animation: {
                        delay: function(context) {
                            return context.dataIndex * 150;
                        }
                    }
                }
            });
        },

        _displayAnomalyAlerts: function (alerts) {
            var container = document.getElementById('anomaly-alerts-container');
            if (!container || !alerts.length) return;

            var html = '';
            alerts.forEach(function (alert) {
                var severityClass = 'alert-' + (alert.severity || 'low');
                html += '<div class="alert-item ' + severityClass + ' fade-in">';
                html += '<div class="alert-title">' + (alert.component_name || alert.component) + '</div>';
                html += '<div class="alert-message">' + alert.message + '</div>';
                html += '</div>';
            });

            container.innerHTML = html;
        },

        _populateAnalysisTable: function (components, comparison) {
            var tbody = document.getElementById('analysis-table-body');
            if (!tbody) return;

            var html = '';
            Object.keys(components).forEach(function (code) {
                var component = components[code];
                var currentTotal = component.total || 0;
                var previousTotal = 0;
                var variance = 0;
                var status = 'normal';

                if (comparison.previous_month && comparison.previous_month[code]) {
                    previousTotal = comparison.previous_month[code].total || 0;
                }

                if (comparison.variance && comparison.variance[code]) {
                    variance = comparison.variance[code];
                    
                    if (Math.abs(variance) > 20) {
                        status = 'alert';
                    } else if (Math.abs(variance) > 10) {
                        status = 'warning';
                    }
                }

                var varianceClass = variance > 0 ? 'variance-positive' : (variance < 0 ? 'variance-negative' : 'variance-neutral');

                html += '<tr class="fade-in">';
                html += '<td><strong>' + (component.name || code) + '</strong></td>';
                html += '<td>' + new Intl.NumberFormat().format(currentTotal) + '</td>';
                html += '<td>' + new Intl.NumberFormat().format(previousTotal) + '</td>';
                html += '<td>' + new Intl.NumberFormat().format(component.average || 0) + '</td>';
                html += '<td class="' + varianceClass + '">' + variance.toFixed(1) + '%</td>';
                html += '<td><span class="status-badge status-' + status + '">' + status.toUpperCase() + '</span></td>';
                html += '</tr>';
            });

            tbody.innerHTML = html;
        },

        _generateRecommendations: function (components, comparison, alerts) {
            var recommendationsList = document.getElementById('recommendations-list');
            var warningsList = document.getElementById('warnings-list');
            
            if (!recommendationsList || !warningsList) return;

            var recommendations = [];
            var warnings = [];

            // Generate recommendations based on data
            var totalVariance = 0;
            var positiveVariances = 0;
            var negativeVariances = 0;

            Object.keys(comparison.variance || {}).forEach(function (code) {
                var variance = comparison.variance[code];
                totalVariance += Math.abs(variance);
                
                if (variance > 5) positiveVariances++;
                if (variance < -5) negativeVariances++;
            });

            // Recommendations
            if (positiveVariances > negativeVariances) {
                recommendations.push('Overall payroll trend is positive. Consider reviewing budget allocations.');
            }

            if (totalVariance / Object.keys(comparison.variance || {}).length < 5) {
                recommendations.push('Payroll is stable with minimal variances. Good consistency in payments.');
            }

            if (alerts.length === 0) {
                recommendations.push('No anomalies detected. Payroll data appears normal and ready for approval.');
            }

            // Add component-specific recommendations
            Object.keys(components).forEach(function (code) {
                var component = components[code];
                if (component.total > 0 && component.count > 0) {
                    if (code === 'BASIC' && component.average > 0) {
                        recommendations.push('Basic salary distribution is healthy across ' + component.count + ' employees.');
                    }
                }
            });

            // Warnings
            alerts.forEach(function (alert) {
                if (alert.severity === 'high') {
                    warnings.push(alert.message + ' - Requires immediate attention.');
                }
            });

            Object.keys(comparison.variance || {}).forEach(function (code) {
                var variance = comparison.variance[code];
                if (Math.abs(variance) > 30) {
                    warnings.push(components[code].name + ' has significant variance (' + variance.toFixed(1) + '%). Please review.');
                }
            });

            // Check for zero critical components
            if (components.BASIC && components.BASIC.total === 0) {
                warnings.push('Basic salary total is zero. This may indicate a data issue.');
            }

            if (components.NETPAY && components.NETPAY.total === 0) {
                warnings.push('Net pay total is zero. Please verify payroll calculations.');
            }

            // Default messages if no specific recommendations/warnings
            if (recommendations.length === 0) {
                recommendations.push('Review the detailed analysis above before final approval.');
                recommendations.push('Ensure all variances are within acceptable business limits.');
            }

            if (warnings.length === 0) {
                warnings.push('No critical issues detected in current payroll data.');
            }

            // Populate lists
            recommendationsList.innerHTML = recommendations.map(function (rec) {
                return '<li class="fade-in">' + rec + '</li>';
            }).join('');

            warningsList.innerHTML = warnings.map(function (warn) {
                return '<li class="fade-in">' + warn + '</li>';
            }).join('');
        },

        _addAnimations: function () {
            // Add staggered animations to cards
            var cards = document.querySelectorAll('.metric-card, .chart-card, .alert-item');
            cards.forEach(function (card, index) {
                setTimeout(function () {
                    card.classList.add('slide-up');
                }, index * 100);
            });

            // Add hover effects
            var metricCards = document.querySelectorAll('.metric-card');
            metricCards.forEach(function (card) {
                card.addEventListener('mouseenter', function () {
                    this.style.transform = 'translateY(-5px) scale(1.02)';
                });
                
                card.addEventListener('mouseleave', function () {
                    this.style.transform = 'translateY(0) scale(1)';
                });
            });
        },

        destroy: function () {
            // Clean up charts
            Object.values(this.charts).forEach(function (chart) {
                if (chart && typeof chart.destroy === 'function') {
                    chart.destroy();
                }
            });
            this._super.apply(this, arguments);
        }
    });

    var PayrollAnalyticsFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: PayrollAnalyticsDashboard,
        }),
    });

    viewRegistry.add('payroll_analytics_dashboard', PayrollAnalyticsFormView);

    return {
        PayrollAnalyticsDashboard: PayrollAnalyticsDashboard,
        PayrollAnalyticsFormView: PayrollAnalyticsFormView,
    };
});

// Additional utility functions for payroll analytics
odoo.define('payroll_analytics_approval.utils', function (require) {
    'use strict';

    var rpc = require('web.rpc');
    var Dialog = require('web.Dialog');
    var core = require('web.core');
    var _t = core._t;

    var PayrollAnalyticsUtils = {

        generateAnalytics: function (country, dateFrom, dateTo) {
            return rpc.query({
                model: 'payroll.analytics',
                method: 'generate_analytics',
                args: [country, dateFrom, dateTo],
            });
        },

        showApprovalConfirmation: function (analyticsId, callback) {
            var dialog = new Dialog(null, {
                title: _t('Confirm Payroll Approval'),
                size: 'medium',
                buttons: [{
                    text: _t('Approve'),
                    classes: 'btn-primary',
                    click: function () {
                        callback();
                        dialog.close();
                    }
                }, {
                    text: _t('Cancel'),
                    close: true
                }],
                $content: $('<div>').html(_t(
                    'Are you sure you want to approve this payroll? This action will:<br/><br/>' +
                    '• Set all payslip batches to DONE status<br/>' +
                    '• Enable bank file export<br/>' +
                    '• Cannot be undone<br/><br/>' +
                    'Please review all analytics and anomaly alerts before proceeding.'
                ))
            });
            dialog.open();
        },

        exportBankFile: function (analyticsId) {
            return rpc.query({
                model: 'payroll.analytics',
                method: 'action_export_bank_file',
                args: [[analyticsId]],
            });
        },

        formatCurrency: function (amount, currency) {
            if (!currency) currency = 'IDR';
            return new Intl.NumberFormat('id-ID', {
                style: 'currency',
                currency: currency,
                minimumFractionDigits: 0
            }).format(amount);
        },

        formatPercentage: function (value, decimals) {
            if (decimals === undefined) decimals = 1;
            return value.toFixed(decimals) + '%';
        },

        getVarianceColor: function (variance) {
            if (variance > 10) return '#27ae60'; // Green
            if (variance < -10) return '#e74c3c'; // Red
            return '#95a5a6'; // Gray
        },

        debounce: function (func, wait) {
            var timeout;
            return function executedFunction() {
                var later = function () {
                    clearTimeout(timeout);
                    func.apply(this, arguments);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
    };

    return PayrollAnalyticsUtils;
});