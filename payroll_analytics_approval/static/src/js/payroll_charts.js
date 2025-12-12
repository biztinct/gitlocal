/* Enhanced Payroll Analytics Dashboard JavaScript - Fixed Version */

odoo.define('payroll_analytics_approval.enhanced_dashboard', function (require) {
    'use strict';

    var FormController = require('web.FormController');
    var FormView = require('web.FormView');
    var viewRegistry = require('web.view_registry');
    var core = require('web.core');
    var rpc = require('web.rpc');

    var PayrollAnalyticsDashboard = FormController.extend({
        
        init: function () {
            this._super.apply(this, arguments);
            this.charts = {};
            this.chartJSLoaded = false;
            this._lastRecordId = null; // Track record changes for navigation detection
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                if (self.modelName === 'payroll.analytics') {
                    // Check if this is a forced refresh from action_open_dashboard
                    var forceRefresh = self.initialState && self.initialState.context && self.initialState.context.force_refresh;
                    if (forceRefresh) {
                        console.log('Force refresh detected from action_open_dashboard');
                    }
                    
                    self._initializeDashboard();
                    
                    // Set up navigation event listeners
                    self._setupNavigationListeners();
                }
            });
        },

        _setupNavigationListeners: function() {
            var self = this;
            
            // Listen for browser navigation events that could change the record
            window.addEventListener('popstate', function() {
                if (self.modelName === 'payroll.analytics') {
                    console.log('Browser navigation detected, refreshing dashboard...');
                    setTimeout(() => {
                        self._setupDashboard();
                    }, 500);
                }
            });
            
            // Listen for hash changes that could indicate record navigation
            window.addEventListener('hashchange', function() {
                if (self.modelName === 'payroll.analytics') {
                    console.log('URL hash changed, refreshing dashboard...');
                    setTimeout(() => {
                        self._setupDashboard();
                    }, 500);
                }
            });
        },

        _initializeDashboard: function () {
            var self = this;
            
            // Load Chart.js if not already loaded
            if (typeof Chart === 'undefined' && !this.chartJSLoaded) {
                this._loadChartJS().then(function () {
                    self.chartJSLoaded = true;
                    self._setupDashboard();
                }).catch(function(error) {
                    console.error('Failed to load Chart.js:', error);
                    self._showChartLoadError();
                });
            } else {
                this._setupDashboard();
            }
        },

        _loadChartJS: function () {
            return new Promise(function (resolve, reject) {
                if (typeof Chart !== 'undefined') {
                    resolve();
                    return;
                }
                
                var script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
                script.onload = function() {
                    console.log('Chart.js loaded successfully');
                    resolve();
                };
                script.onerror = function() {
                    console.error('Failed to load Chart.js');
                    reject(new Error('Chart.js loading failed'));
                };
                document.head.appendChild(script);
            });
        },

        _destroyAllCharts: function() {
            var self = this;
            console.log('Destroying existing charts...');
            
            // Destroy existing charts to prevent conflicts
            Object.keys(this.charts).forEach(function (key) {
                if (self.charts[key]) {
                    try {
                        self.charts[key].destroy();
                        console.log('Destroyed chart:', key);
                    } catch (e) {
                        console.warn('Error destroying chart:', key, e);
                    }
                }
            });
            this.charts = {};
            
            // Also clear canvas elements to ensure clean state
            var canvases = ['componentsChart', 'comparisonChart', 'varianceChart'];
            canvases.forEach(function(canvasId) {
                var canvas = document.getElementById(canvasId);
                if (canvas) {
                    // Clear the canvas
                    var ctx = canvas.getContext('2d');
                    if (ctx) {
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                    }
                    // Remove any chart.js attached properties
                    if (canvas.chart) {
                        try {
                            canvas.chart.destroy();
                        } catch (e) {
                            console.warn('Error destroying canvas chart:', e);
                        }
                        delete canvas.chart;
                    }
                }
            });
        },

        _setupDashboard: function () {
            var self = this;
            
            // Destroy existing charts first to prevent memory leaks and display issues
            this._destroyAllCharts();
            
            // Wait a bit for DOM to be ready
            setTimeout(function() {
                try {
                    // Get data from form fields
                    var employeeMetrics = self._getFieldValue('employee_metrics');
                    var salaryComponents = self._getFieldValue('salary_components');
                    var comparisonData = self._getFieldValue('comparison_data');
                    var anomalyAlerts = self._getFieldValue('anomaly_alerts');

                    console.log('Dashboard data:', {
                        employeeMetrics: employeeMetrics,
                        salaryComponents: salaryComponents,
                        comparisonData: comparisonData,
                        anomalyAlerts: anomalyAlerts
                    });

                    // Parse and validate data with proper error handling
                    var parsedComponents = {};
                    var parsedComparison = {};
                    var parsedAlerts = [];
                    var parsedMetrics = {};

                    try {
                        if (employeeMetrics && employeeMetrics.trim()) {
                            parsedMetrics = JSON.parse(employeeMetrics);
                        }
                        if (salaryComponents && salaryComponents.trim()) {
                            parsedComponents = JSON.parse(salaryComponents);
                        }
                        if (comparisonData && comparisonData.trim()) {
                            parsedComparison = JSON.parse(comparisonData);
                        }
                        if (anomalyAlerts && anomalyAlerts.trim()) {
                            var alertsData = JSON.parse(anomalyAlerts);
                            // Ensure parsedAlerts is always an array
                            if (Array.isArray(alertsData)) {
                                parsedAlerts = alertsData;
                            } else if (alertsData && typeof alertsData === 'object') {
                                // If it's an object, try to convert to array
                                parsedAlerts = Object.values(alertsData);
                            } else {
                                parsedAlerts = [];
                            }
                        }
                    } catch (e) {
                        console.error('Error parsing dashboard data:', e);
                        // Set default values on parse error
                        parsedComponents = {};
                        parsedComparison = {};
                        parsedAlerts = [];
                        parsedMetrics = {};
                    }

                    // Ensure parsedAlerts is always an array before proceeding
                    if (!Array.isArray(parsedAlerts)) {
                        console.warn('Alerts data is not an array, converting to empty array');
                        parsedAlerts = [];
                    }

                    // Update metric cards
                    self._updateMetricCards(parsedMetrics, parsedComparison);

                    // Create charts if we have data
                    if (Object.keys(parsedComponents).length > 0) {
                        self._createCharts(parsedComponents, parsedComparison);
                    } else {
                        console.warn('No salary components data available for charts');
                        self._showNoDataMessage();
                    }

                    // Display alerts - now safe since parsedAlerts is guaranteed to be an array
                    self._displayAnomalyAlerts(parsedAlerts);

                    // Populate analysis table
                    if (Object.keys(parsedComponents).length > 0) {
                        self._populateAnalysisTable(parsedComponents, parsedComparison);
                        self._generateRecommendations(parsedComponents, parsedComparison, parsedAlerts);
                    }

                    // Add animations
                    self._addAnimations();
                    
                } catch (error) {
                    console.error('Error setting up dashboard:', error);
                    self._showGeneralError();
                }
            }, 500);
        },

        _getFieldValue: function (fieldName) {
            try {
                // Method 1: Try getting from hidden input fields
                var hiddenField = this.$('input[name="' + fieldName + '"]');
                if (hiddenField.length && hiddenField.val()) {
                    return hiddenField.val();
                }

                // Method 2: Try getting from field elements
                var field = this.$('field[name="' + fieldName + '"]');
                if (field.length) {
                    var value = field.text() || field.val();
                    if (value && value.trim()) return value.trim();
                }
                
                // Method 3: Try getting from record data
                if (this.renderer && this.renderer.state && this.renderer.state.data) {
                    var fieldValue = this.renderer.state.data[fieldName];
                    if (fieldValue) return fieldValue;
                }
                
                // Method 4: Try getting from model data
                if (this.model && this.model.localData) {
                    var recordId = this.renderer.state.id;
                    var record = this.model.localData[recordId];
                    if (record && record.data && record.data[fieldName]) {
                        return record.data[fieldName];
                    }
                }

                // Method 5: Try direct DOM query
                var spanField = this.$('span[name="' + fieldName + '"]');
                if (spanField.length && spanField.text()) {
                    return spanField.text();
                }
                
                return null;
            } catch (e) {
                console.error('Error getting field value for ' + fieldName + ':', e);
                return null;
            }
        },

        _updateMetricCards: function(metrics, comparison) {
            try {
                // Update variance display with proper handling
                if (comparison && comparison.previous_month_total !== undefined) {
                    var currentTotal = (metrics && metrics.total_payroll) || 0;
                    var previousTotal = comparison.previous_month_total || 0;
                    var variance = 0;

                    if (previousTotal > 0) {
                        variance = ((currentTotal - previousTotal) / previousTotal) * 100;
                    } else if (currentTotal > 0) {
                        variance = 100;
                    }

                    // Update variance display
                    var varianceElement = this.$('.metric-variance .metric-value');
                    if (varianceElement.length) {
                        var sign = variance >= 0 ? '+' : '';
                        varianceElement.html(sign + variance.toFixed(1) + '%');
                        
                        // Add color coding
                        varianceElement.removeClass('text-success text-danger text-muted');
                        if (variance > 5) {
                            varianceElement.addClass('text-success');
                        } else if (variance < -5) {
                            varianceElement.addClass('text-danger');
                        } else {
                            varianceElement.addClass('text-muted');
                        }
                    }
                }
            } catch (error) {
                console.error('Error updating metric cards:', error);
            }
        },

        _createCharts: function (components, comparison) {
            var self = this;
            
            if (typeof Chart === 'undefined') {
                console.error('Chart.js not loaded');
                this._showChartLoadError();
                return;
            }

            // Destroy existing charts
            Object.keys(this.charts).forEach(function (key) {
                if (self.charts[key]) {
                    try {
                        self.charts[key].destroy();
                    } catch (e) {
                        console.warn('Error destroying chart:', key, e);
                    }
                }
            });
            this.charts = {};

            // Create charts with error handling
            try {
                this._createComponentChart(components);
            } catch (e) {
                console.error('Error creating component chart:', e);
            }
            
            try {
                this._createComparisonChart(components, comparison);
            } catch (e) {
                console.error('Error creating comparison chart:', e);
            }
            
            try {
                this._createVarianceChart(components, comparison);
            } catch (e) {
                console.error('Error creating variance chart:', e);
            }
        },

        _createComponentChart: function (components) {
            var self = this;
            var ctx = document.getElementById('componentsChart');
            if (!ctx) {
                console.warn('Components chart canvas not found');
                return;
            }

            var labels = [];
            var data = [];
            var colors = [
                'rgba(255, 99, 132, 0.8)',
                'rgba(54, 162, 235, 0.8)',
                'rgba(255, 205, 86, 0.8)',
                'rgba(75, 192, 192, 0.8)',
                'rgba(153, 102, 255, 0.8)',
                'rgba(255, 159, 64, 0.8)',
                'rgba(199, 199, 199, 0.8)',
                'rgba(83, 102, 255, 0.8)',
                'rgba(255, 99, 255, 0.8)',
                'rgba(99, 255, 132, 0.8)',
                'rgba(255, 159, 132, 0.8)',
                'rgba(132, 255, 159, 0.8)'
            ];

            Object.keys(components).forEach(function (code) {
                var component = components[code];
                if (component && component.total && component.total > 0) {
                    labels.push(component.name || code);
                    data.push(component.total);
                }
            });

            if (data.length === 0) {
                this._showNoDataForChart('componentsChart');
                return;
            }

            this.charts.components = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: colors.slice(0, data.length),
                        borderColor: colors.slice(0, data.length).map(c => c.replace('0.8', '1')),
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: function (event, elements) {
                        if (elements && elements.length) {
                            var index = elements[0].index;
                            var label = labels[index];
                            self._openPivotForComponent(label);
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                usePointStyle: true,
                                font: { size: 12 }
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
                        animateRotate: true,
                        duration: 1000
                    }
                }
            });
        },

        _createComparisonChart: function (components, comparison) {
            var self = this;
            var ctx = document.getElementById('comparisonChart');
            if (!ctx) {
                console.warn('Comparison chart canvas not found');
                return;
            }

            var labels = [];
            var currentData = [];
            var previousData = [];

            Object.keys(components).forEach(function (code) {
                var component = components[code];
                if (component && component.total && component.total > 0) {
                    labels.push(component.name || code);
                    currentData.push(component.total);
                    
                    if (comparison && comparison.previous_month && comparison.previous_month[code]) {
                        previousData.push(comparison.previous_month[code].total || 0);
                    } else {
                        previousData.push(0);
                    }
                }
            });

            if (currentData.length === 0) {
                this._showNoDataForChart('comparisonChart');
                return;
            }

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
                    onClick: function (event, elements) {
                        if (elements && elements.length) {
                            var index = elements[0].index;
                            var label = labels[index];
                            self._openPivotForComponent(label);
                        }
                    },
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
                                maxRotation: 45,
                                minRotation: 0
                            }
                        }
                    },
                    plugins: {
                        legend: { position: 'top' },
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
                            return context.dataIndex * 150;
                        },
                        duration: 800
                    }
                }
            });
        },

        _createVarianceChart: function (components, comparison) {
            var self = this;
            var ctx = document.getElementById('varianceChart');
            if (!ctx) {
                console.warn('Variance chart canvas not found');
                return;
            }

            var labels = [];
            var varianceData = [];
            var colors = [];

            var hasNonZeroVariance = false;
            
            Object.keys(components).forEach(function (code) {
                var component = components[code];
                if (component && component.total && component.total > 0) {
                    labels.push(component.name || code);
                    
                    var variance = 0;
                    if (comparison && comparison.variance && comparison.variance[code] !== undefined) {
                        variance = parseFloat(comparison.variance[code]) || 0;
                    }
                    
                    // Track if we have any meaningful variance
                    if (Math.abs(variance) > 0.1) {
                        hasNonZeroVariance = true;
                    }
                    
                    varianceData.push(variance);
                    
                    // Color based on variance with more sensitive thresholds
                    if (variance > 5) {
                        colors.push('rgba(76, 175, 80, 0.8)'); // Green for positive
                    } else if (variance < -5) {
                        colors.push('rgba(244, 67, 54, 0.8)'); // Red for negative
                    } else if (Math.abs(variance) > 0.1) {
                        colors.push('rgba(255, 193, 7, 0.8)'); // Yellow for small changes
                    } else {
                        colors.push('rgba(149, 165, 166, 0.8)'); // Gray for no change
                    }
                }
            });

            if (varianceData.length === 0) {
                this._showNoDataForChart('varianceChart');
                return;
            }
            
            // If all variances are zero or very small, show a "no variance" message
            if (!hasNonZeroVariance) {
                var container = document.getElementById('varianceChart');
                if (container) {
                    container.style.display = 'none';
                    var parent = container.parentElement;
                    if (parent) {
                        parent.innerHTML = '<div class="no-variance-message text-center p-4">' +
                            '<i class="fa fa-info-circle fa-2x text-muted mb-2"></i>' +
                            '<h5 class="text-muted">No Significant Variance</h5>' +
                            '<p class="text-muted">Current month values are similar to previous month</p>' +
                            '</div>';
                    }
                }
                return;
            }

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
                    onClick: function (event, elements) {
                        if (elements && elements.length) {
                            var index = elements[0].index;
                            var label = labels[index];
                            self._openPivotForComponent(label);
                        }
                    },
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
                                maxRotation: 45,
                                minRotation: 0
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false },
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
                        },
                        duration: 800
                    }
                }
            });
        },

        _openPivotForComponent: function (componentLabel) {
            if (!componentLabel) {
                console.warn('Drill-down skipped: empty component label');
                return;
            }
            // Map some friendly labels back to payroll codes
            var code = componentLabel;
            var labelToCode = {
                'Total Cost to Employer': 'TOTCOST',
                'Total Cost': 'TOTCOST',
                'Total Payroll': 'TOTCOST',
                'Total Deductions': 'TOTDEDU',
                'ATI': 'ATI',
                'ACTBASE': 'ACTBASE',
                'UI': 'UI',
                'SI': 'SI',
                'TAXIN': 'TAXIN'
            };
            if (labelToCode[componentLabel]) {
                code = labelToCode[componentLabel];
            }
            code = code.toString();

            var dateFrom = this._getFieldValue('date_from');
            var dateTo = this._getFieldValue('date_to');
            var domain = [['code', '=', code]];
            if (dateFrom) {
                domain.push(['slip_id.date_from', '>=', dateFrom.toString()]);
            }
            if (dateTo) {
                domain.push(['slip_id.date_to', '<=', dateTo.toString()]);
            }
            domain = domain.filter(function (d) {
                return d && d.length >= 3 && d[2] !== undefined && d[2] !== null;
            });

            var self = this;
            var action = {
                type: 'ir.actions.act_window',
                name: (core._t("Drill-down: ") + componentLabel),
                res_model: 'hr.payslip.line',
                view_mode: 'pivot,tree',
                views: [
                    [false, 'pivot'],
                    [false, 'list'],
                ],
                domain: domain,
                context: {
                    search_default_group_by_employee: 1,
                    search_default_group_by_slip: 1,
                }
            };

            // Align with analytics module: navigate first, then destroy charts shortly after
            this.do_action(action);
            setTimeout(function () {
                self._destroyAllCharts();
            }, 80);
        },

        _displayAnomalyAlerts: function (alerts) {
            var container = document.getElementById('anomaly-alerts-container');
            if (!container) {
                console.warn('Anomaly alerts container not found');
                return;
            }

            // Ensure alerts is an array
            if (!Array.isArray(alerts)) {
                console.warn('Alerts parameter is not an array:', alerts);
                alerts = [];
            }

            if (!alerts.length) {
                container.innerHTML = '<div class="alert alert-success"><i class="fa fa-check-circle"></i> No anomalies detected</div>';
                return;
            }

            var html = '';
            alerts.forEach(function (alert) {
                // Validate alert object structure
                if (!alert || typeof alert !== 'object') {
                    console.warn('Invalid alert object:', alert);
                    return;
                }

                var severity = alert.severity || 'info';
                var severityClass = 'alert-' + (severity === 'high' ? 'danger' : 
                                              severity === 'medium' ? 'warning' : 'info');
                var iconClass = severity === 'high' ? 'fa-exclamation-triangle' :
                               severity === 'medium' ? 'fa-warning' : 'fa-info-circle';
                
                html += '<div class="alert ' + severityClass + ' fade-in">';
                html += '<i class="fa ' + iconClass + '"></i> ';
                html += '<strong>' + (alert.component_name || alert.component || 'Unknown Component') + '</strong><br>';
                html += (alert.message || 'No message available');
                html += '</div>';
            });

            container.innerHTML = html;
        },

        _populateAnalysisTable: function (components, comparison) {
            var tbody = document.getElementById('analysis-table-body');
            if (!tbody) {
                console.warn('Analysis table body not found');
                return;
            }

            var html = '';
            Object.keys(components).forEach(function (code) {
                var component = components[code];
                if (!component) return;

                var currentTotal = component.total || 0;
                var previousTotal = 0;
                var variance = 0;
                var status = 'normal';

                if (comparison && comparison.previous_month && comparison.previous_month[code]) {
                    previousTotal = comparison.previous_month[code].total || 0;
                }

                if (comparison && comparison.variance && comparison.variance[code] !== undefined) {
                    variance = comparison.variance[code];
                    
                    if (Math.abs(variance) > 20) {
                        status = 'alert';
                    } else if (Math.abs(variance) > 10) {
                        status = 'warning';
                    }
                }

                var varianceClass = variance > 0 ? 'text-success' : (variance < 0 ? 'text-danger' : 'text-muted');
                var statusBadge = status === 'alert' ? 'badge-danger' : 
                                 status === 'warning' ? 'badge-warning' : 'badge-success';
                var statusText = status === 'alert' ? 'Alert' :
                                status === 'warning' ? 'Warning' : 'Normal';

                html += '<tr>';
                html += '<td><strong>' + (component.name || code) + '</strong></td>';
                html += '<td>' + new Intl.NumberFormat().format(currentTotal) + '</td>';
                html += '<td>' + new Intl.NumberFormat().format(previousTotal) + '</td>';
                html += '<td>' + new Intl.NumberFormat().format(component.average || 0) + '</td>';
                html += '<td class="' + varianceClass + '"><strong>' + variance.toFixed(1) + '%</strong></td>';
                html += '<td><span class="badge ' + statusBadge + '">' + statusText + '</span></td>';
                html += '</tr>';
            });

            tbody.innerHTML = html;
        },

        _generateRecommendations: function (components, comparison, alerts) {
            var recList = document.getElementById('recommendations-list');
            var warnList = document.getElementById('warnings-list');
            
            if (!recList || !warnList) {
                console.warn('Recommendation or warning list elements not found');
                return;
            }

            // Ensure alerts is an array
            if (!Array.isArray(alerts)) {
                console.warn('Alerts parameter is not an array in _generateRecommendations:', alerts);
                alerts = [];
            }

            var recommendations = [];
            var warnings = [];

            // Generate recommendations based on data
            if (comparison && comparison.trend === 'increasing') {
                recommendations.push('Overall payroll is trending upward - consider budget implications');
            } else if (comparison && comparison.trend === 'decreasing') {
                recommendations.push('Overall payroll is trending downward - good cost management');
            }
            
            if (alerts.length === 0) {
                recommendations.push('No anomalies detected - payroll appears consistent');
            }

            // Check for large variances
            var hasLargeVariances = false;
            if (comparison && comparison.variance) {
                Object.keys(comparison.variance).forEach(function(code) {
                    var variance = comparison.variance[code];
                    if (Math.abs(variance) > 30) {
                        var componentName = (components[code] && components[code].name) || code;
                        warnings.push('Large variance detected in ' + componentName + ' (' + variance.toFixed(1) + '%)');
                        hasLargeVariances = true;
                    }
                });
            }

            // Generate warnings from alerts - now safe since alerts is guaranteed to be an array
            alerts.forEach(function(alert) {
                if (alert && alert.severity === 'high' && alert.message) {
                    warnings.push(alert.message);
                }
            });

            // Default recommendations if none generated
            if (recommendations.length === 0) {
                recommendations.push('Review all components carefully before approval');
                recommendations.push('Verify employee counts and salary calculations');
                if (!hasLargeVariances) {
                    recommendations.push('Data appears consistent with previous period');
                }
            }

            // Default warnings if none generated
            if (warnings.length === 0) {
                warnings.push('No critical issues detected');
            }

            // Populate lists with safe HTML generation
            try {
                recList.innerHTML = recommendations.map(function(r) { 
                    return '<li><i class="fa fa-check text-success"></i> ' + (r || '') + '</li>'; 
                }).join('');
                
                warnList.innerHTML = warnings.map(function(w) { 
                    return '<li><i class="fa fa-warning text-warning"></i> ' + (w || '') + '</li>'; 
                }).join('');
            } catch (error) {
                console.error('Error populating recommendation lists:', error);
                recList.innerHTML = '<li>Error loading recommendations</li>';
                warnList.innerHTML = '<li>Error loading warnings</li>';
            }
        },

        _addAnimations: function () {
            // Add fade-in animations to cards
            var cards = document.querySelectorAll('.metric-card, .chart-card, .recommendation-card, .warning-card');
            cards.forEach(function (card, index) {
                setTimeout(function() {
                    card.style.opacity = '0';
                    card.style.transform = 'translateY(20px)';
                    card.style.transition = 'all 0.6s ease';
                    
                    setTimeout(function() {
                        card.style.opacity = '1';
                        card.style.transform = 'translateY(0)';
                    }, 50);
                }, index * 100);
            });
        },

        _showNoDataMessage: function () {
            // Show message when no data is available for all charts
            var chartContainers = document.querySelectorAll('.chart-container');
            chartContainers.forEach(function (container) {
                container.innerHTML = '<div class="no-data-message text-center p-4">' +
                    '<i class="fa fa-info-circle fa-3x text-muted mb-3"></i>' +
                    '<h5 class="text-muted">No Data Available</h5>' +
                    '<p class="text-muted">Charts will display when payroll data is processed</p>' +
                    '</div>';
            });
        },

        _showNoDataForChart: function(chartId) {
            var container = document.getElementById(chartId);
            if (container) {
                container.style.display = 'none';
                var parent = container.parentElement;
                if (parent) {
                    parent.innerHTML = '<div class="no-data-message text-center p-4">' +
                        '<i class="fa fa-info-circle fa-2x text-muted mb-2"></i>' +
                        '<p class="text-muted">No data for this chart</p>' +
                        '</div>';
                }
            }
        },

        _showChartLoadError: function() {
            var chartContainers = document.querySelectorAll('.chart-container');
            chartContainers.forEach(function (container) {
                container.innerHTML = '<div class="error-message text-center p-4">' +
                    '<i class="fa fa-exclamation-triangle fa-3x text-danger mb-3"></i>' +
                    '<h5 class="text-danger">Chart Loading Error</h5>' +
                    '<p class="text-muted">Unable to load Chart.js library</p>' +
                    '</div>';
            });
        },

        _showDataParseError: function() {
            var container = document.querySelector('.analytics-dashboard');
            if (container) {
                container.innerHTML = '<div class="alert alert-danger text-center">' +
                    '<i class="fa fa-exclamation-triangle fa-2x mb-3"></i>' +
                    '<h4>Data Parse Error</h4>' +
                    '<p>Unable to parse analytics data. Please contact your administrator.</p>' +
                    '</div>';
            }
        },

        _showGeneralError: function() {
            var container = document.querySelector('.analytics-dashboard');
            if (container) {
                container.innerHTML = '<div class="alert alert-warning text-center">' +
                    '<i class="fa fa-warning fa-2x mb-3"></i>' +
                    '<h4>Dashboard Load Error</h4>' +
                    '<p>There was an issue loading the dashboard. Please refresh the page.</p>' +
                    '</div>';
            }
        },

        // Method to handle field updates
        _onFieldChanged: function() {
            this._super.apply(this, arguments);
            // Re-initialize dashboard when field data changes
            if (this.modelName === 'payroll.analytics') {
                setTimeout(() => {
                    this._setupDashboard();
                }, 100);
            }
        },

        // Method to handle record navigation (arrow keys, next/prev buttons)
        _onNavigationChanged: function() {
            this._super.apply(this, arguments);
            // Re-initialize dashboard when navigating between records
            if (this.modelName === 'payroll.analytics') {
                console.log('Navigation detected, refreshing dashboard...');
                setTimeout(() => {
                    this._setupDashboard();
                }, 200); // Slightly longer delay for navigation
            }
        },

        // Override update method to detect record changes
        _update: function() {
            var result = this._super.apply(this, arguments);
            // Check if we're on analytics dashboard and record has changed
            if (this.modelName === 'payroll.analytics') {
                var currentRecordId = this.renderer && this.renderer.state && this.renderer.state.res_id;
                if (currentRecordId !== this._lastRecordId) {
                    console.log('Record changed from', this._lastRecordId, 'to', currentRecordId, '- refreshing dashboard');
                    this._lastRecordId = currentRecordId;
                    // Refresh dashboard after a short delay to ensure DOM is updated
                    setTimeout(() => {
                        this._setupDashboard();
                    }, 300);
                }
            }
            return result;
        },

        // Method to refresh dashboard data
        refreshDashboard: function() {
            this._setupDashboard();
        },

        // Override reload method to refresh dashboard after reload
        reload: function() {
            var self = this;
            var result = this._super.apply(this, arguments);
            // If this is analytics dashboard, refresh after reload
            if (this.modelName === 'payroll.analytics') {
                result.then(function() {
                    console.log('Dashboard reloaded, refreshing charts...');
                    setTimeout(() => {
                        self._setupDashboard();
                    }, 400);
                });
            }
            return result;
        },

        // Override _confirmSave to refresh dashboard after any data changes
        _confirmSave: function() {
            var self = this;
            var result = this._super.apply(this, arguments);
            if (this.modelName === 'payroll.analytics') {
                result.then(function() {
                    console.log('Data saved, refreshing dashboard...');
                    setTimeout(() => {
                        self._setupDashboard();
                    }, 300);
                });
            }
            return result;
        },

        // Cleanup method
        destroy: function() {
            // Destroy all charts before destroying the controller
            var self = this;
            Object.keys(this.charts).forEach(function (key) {
                if (self.charts[key]) {
                    try {
                        self.charts[key].destroy();
                    } catch (e) {
                        console.warn('Error destroying chart:', key, e);
                    }
                }
            });
            this.charts = {};
            return this._super.apply(this, arguments);
        }
    });

    // Dashboard integration controller for country dashboards
    var DashboardIntegrationController = FormController.extend({
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                if (self.modelName === 'payroll.dashboard') {
                    self._loadDashboardStats();
                    self._setupDashboardHandlers();
                }
            });
        },
        
        _loadDashboardStats: function () {
            var self = this;
            if (this.renderer && this.renderer.state && this.renderer.state.data) {
                var country = this.renderer.state.data.country;
                
                if (country) {
                    rpc.query({
                        model: 'payroll.analytics',
                        method: 'get_analytics_stats',
                        args: [country],
                    }).then(function (stats) {
                        self._updateDashboardStats(country, stats);
                    }).catch(function(error) {
                        console.error('Error loading dashboard stats:', error);
                    });
                }
            }
        },
        
        _updateDashboardStats: function (country, stats) {
            var countryCode = country.toLowerCase();
            
            // Update pending approvals
            var pendingElement = document.getElementById(countryCode + '-pending-approvals');
            if (pendingElement) {
                pendingElement.textContent = stats.pending_approvals || 0;
            }
            
            // Update ready exports
            var exportsElement = document.getElementById(countryCode + '-ready-exports');
            if (exportsElement) {
                exportsElement.textContent = stats.ready_exports || 0;
            }
        },

        _setupDashboardHandlers: function() {
            // Add click handlers for dashboard buttons with proper delegation
            var self = this;
            
            // Use event delegation for dynamically added buttons
            document.addEventListener('click', function(e) {
                if (e.target.closest('button[name="action_open_analytics_dashboard"]')) {
                    e.preventDefault();
                    var button = e.target.closest('button[name="action_open_analytics_dashboard"]');
                    var country = button.getAttribute('data-country') || 
                                 (self.renderer && self.renderer.state && self.renderer.state.data.country);
                    if (country) {
                        self._openAnalyticsDashboard(country);
                    }
                }
                
                if (e.target.closest('button[name="action_export_bank_file"]')) {
                    e.preventDefault();
                    var button = e.target.closest('button[name="action_export_bank_file"]');
                    var country = button.getAttribute('data-country') || 
                                 (self.renderer && self.renderer.state && self.renderer.state.data.country);
                    if (country) {
                        self._openBankExport(country);
                    }
                }
            });
        },

        _openAnalyticsDashboard: function(country) {
            var self = this;
            // Call the server method to open analytics dashboard
            rpc.query({
                model: 'payroll.dashboard',
                method: 'action_open_analytics_dashboard',
                args: [],
                context: { country: country }
            }).then(function(action) {
                if (action && self.do_action) {
                    self.do_action(action);
                }
            }).catch(function(error) {
                console.error('Error opening analytics dashboard:', error);
                if (self.displayNotification) {
                    self.displayNotification({
                        title: 'Error',
                        message: 'Failed to open analytics dashboard',
                        type: 'danger'
                    });
                }
            });
        },

        _openBankExport: function(country) {
            var self = this;
            // Call the server method to open bank export
            rpc.query({
                model: 'payroll.dashboard',
                method: 'action_export_bank_file',
                args: [],
                context: { country: country }
            }).then(function(action) {
                if (action && self.do_action) {
                    self.do_action(action);
                }
            }).catch(function(error) {
                console.error('Error opening bank export:', error);
                if (self.displayNotification) {
                    self.displayNotification({
                        title: 'Error',
                        message: 'Failed to open bank export',
                        type: 'danger'
                    });
                }
            });
        }
    });

    // Register both controllers
    var PayrollAnalyticsFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: PayrollAnalyticsDashboard,
        }),
    });

    var DashboardIntegrationFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: DashboardIntegrationController,
        }),
    });

    // Register views in the view registry
    viewRegistry.add('payroll_analytics_dashboard', PayrollAnalyticsFormView);
    viewRegistry.add('payroll_dashboard_integration', DashboardIntegrationFormView);

    // Export the controllers for external use
    return {
        PayrollAnalyticsDashboard: PayrollAnalyticsDashboard,
        DashboardIntegrationController: DashboardIntegrationController,
        PayrollAnalyticsFormView: PayrollAnalyticsFormView,
        DashboardIntegrationFormView: DashboardIntegrationFormView
    };
});


// Replace the dashboard controller in your payroll_charts.js with this improved version

odoo.define('payroll_analytics_approval.dashboard_controller_fixed', function (require) {
    'use strict';

    var FormController = require('web.FormController');
    var rpc = require('web.rpc');

    // Enhanced Dashboard Integration Controller with Fixed Error Handling
    var DashboardIntegrationController = FormController.extend({
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                if (self.modelName === 'payroll.dashboard') {
                    self._loadDashboardStats();
                    self._setupDashboardHandlers();
                }
            });
        },
        
        _loadDashboardStats: function () {
            var self = this;
            if (this.renderer && this.renderer.state && this.renderer.state.data) {
                var country = this.renderer.state.data.country;
                
                if (country) {
                    rpc.query({
                        model: 'payroll.analytics',
                        method: 'get_analytics_stats',
                        args: [country],
                    }).then(function (stats) {
                        self._updateDashboardStats(country, stats);
                    }).catch(function(error) {
                        console.warn('Could not load dashboard stats:', error);
                        // Don't show error notification for stats loading failure
                    });
                }
            }
        },
        
        _updateDashboardStats: function (country, stats) {
            // This method can be used to update tile statistics if needed
            // For now, keeping it simple since we removed the stat displays
            console.log('Dashboard stats for', country, ':', stats);
        },

        _setupDashboardHandlers: function() {
            var self = this;
            
            // Use event delegation for button clicks
            document.addEventListener('click', this._handleDashboardClick.bind(this));
        },
        
        _handleDashboardClick: function(e) {
            var self = this;
            
            // Handle Analytics Dashboard button
            var analyticsButton = e.target.closest('button[name="action_open_analytics_dashboard"]');
            if (analyticsButton) {
                e.preventDefault();
                e.stopPropagation();
                
                var country = analyticsButton.getAttribute('data-country');
                if (country) {
                    this._openAnalyticsDashboard(country, analyticsButton);
                }
                return;
            }
            
            // Handle Bank Export button
            var exportButton = e.target.closest('button[name="action_export_bank_file"]');
            if (exportButton) {
                e.preventDefault();
                e.stopPropagation();
                
                var country = exportButton.getAttribute('data-country');
                if (country) {
                    this._openBankExport(country, exportButton);
                }
                return;
            }
        },

        _openAnalyticsDashboard: function(country, button) {
            var self = this;
            
            // Show loading state
            if (button) {
                var originalText = button.innerHTML;
                button.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Loading...';
                button.disabled = true;
                
                // Restore button state after delay regardless of outcome
                setTimeout(function() {
                    if (button) {
                        button.innerHTML = originalText;
                        button.disabled = false;
                    }
                }, 2000);
            }
            
            // Call the server method with improved error handling
            rpc.query({
                model: 'payroll.dashboard',
                method: 'action_open_analytics_dashboard',
                args: [],
                context: { 
                    active_id: this.renderer.state.res_id,
                    country: country 
                }
            }).then(function(result) {
                // Check if result is a valid action
                if (result && typeof result === 'object' && result.type) {
                    if (self.do_action) {
                        self.do_action(result);
                    }
                } else {
                    // If no valid action returned, don't show error since dashboard might still work
                    console.log('Analytics dashboard action completed');
                }
            }).catch(function(error) {
                console.error('Analytics dashboard error:', error);
                
                // Only show user-friendly error if it's a real failure
                if (error && error.message && !error.message.includes('[object Object]')) {
                    self._showNotification('Could not open analytics dashboard: ' + error.message, 'warning');
                } else {
                    // For [object Object] errors, don't notify user since dashboard might still work
                    console.warn('Analytics dashboard opened but returned unexpected response');
                }
            });
        },

        _openBankExport: function(country, button) {
            var self = this;
            
            // Show loading state
            if (button) {
                var originalText = button.innerHTML;
                button.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Loading...';
                button.disabled = true;
                
                // Restore button state after delay
                setTimeout(function() {
                    if (button) {
                        button.innerHTML = originalText;
                        button.disabled = false;
                    }
                }, 2000);
            }
            
            // Call the server method with improved error handling
            rpc.query({
                model: 'payroll.dashboard',
                method: 'action_export_bank_file',
                args: [],
                context: { 
                    active_id: this.renderer.state.res_id,
                    country: country 
                }
            }).then(function(result) {
                // Check if result is a valid action
                if (result && typeof result === 'object' && result.type) {
                    if (self.do_action) {
                        self.do_action(result);
                    }
                } else if (result && result.params && result.params.message) {
                    // Handle notification-type responses
                    self._showNotification(result.params.message, result.params.type || 'info');
                } else {
                    console.log('Bank export action completed');
                }
            }).catch(function(error) {
                console.error('Bank export error:', error);
                
                // Only show meaningful errors to user
                if (error && error.message && !error.message.includes('[object Object]')) {
                    self._showNotification('Could not open bank export: ' + error.message, 'warning');
                } else {
                    console.warn('Bank export completed but returned unexpected response');
                }
            });
        },
        
        _showNotification: function(message, type) {
            try {
                if (this.displayNotification) {
                    this.displayNotification({
                        title: type === 'danger' ? 'Error' : type === 'warning' ? 'Warning' : 'Info',
                        message: message,
                        type: type || 'info',
                        sticky: false
                    });
                } else {
                    // Fallback for older Odoo versions
                    console.log(type.toUpperCase() + ': ' + message);
                }
            } catch (e) {
                console.log('Notification: ' + message);
            }
        },
        
        // Cleanup when destroying the controller
        destroy: function() {
            // Remove event listeners if needed
            return this._super.apply(this, arguments);
        }
    });

    // Register the enhanced controller
    var FormView = require('web.FormView');
    var viewRegistry = require('web.view_registry');

    var DashboardIntegrationFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: DashboardIntegrationController,
        }),
    });

    // Re-register with the same name to override
    viewRegistry.add('payroll_dashboard_integration', DashboardIntegrationFormView);

    return DashboardIntegrationController;
});
