odoo.define('payroll_analytics_approval.charts_manager', function (require) {
    'use strict';

    var core = require('web.core');
    var rpc = require('web.rpc');

    // Professional color palette for charts
    var CHART_COLORS = {
        primary: ['#3498db', '#27ae60', '#f39c12', '#e74c3c', '#9b59b6', '#1abc9c'],
        secondary: ['#5dade2', '#58d68d', '#f7dc6f', '#ec7063', '#bb8fce', '#76d7c4'],
        gradient: {
            blue: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            green: 'linear-gradient(135deg, #27ae60 0%, #2ecc71 100%)',
            orange: 'linear-gradient(135deg, #f39c12 0%, #f1c40f 100%)',
            red: 'linear-gradient(135deg, #e74c3c 0%, #c0392b 100%)',
            purple: 'linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%)',
            teal: 'linear-gradient(135deg, #1abc9c 0%, #16a085 100%)'
        }
    };

    var PayrollChartManager = core.Class.extend({
        
        init: function(container, options) {
            this.container = container;
            this.options = options || {};
            this.charts = {};
            this.chartDefaults = {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 15,
                            font: {
                                size: 12,
                                family: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        borderColor: '#667eea',
                        borderWidth: 1,
                        cornerRadius: 6,
                        displayColors: true,
                        callbacks: {}
                    }
                },
                animation: {
                    duration: 1000,
                    easing: 'easeInOutQuart'
                }
            };
        },

        createComponentsChart: function(canvasId, data, type) {
            type = type || 'doughnut';
            var ctx = document.getElementById(canvasId);
            if (!ctx) return null;

            var chartData = {
                labels: data.labels || [],
                datasets: [{
                    data: data.values || [],
                    backgroundColor: CHART_COLORS.primary,
                    borderColor: '#fff',
                    borderWidth: 3,
                    hoverOffset: 8
                }]
            };

            var options = _.extend({}, this.chartDefaults, {
                plugins: _.extend({}, this.chartDefaults.plugins, {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                var label = context.label || '';
                                var value = context.parsed;
                                var total = context.dataset.data.reduce((a, b) => a + b, 0);
                                var percentage = ((value / total) * 100).toFixed(1);
                                return label + ': ' + value.toLocaleString() + ' (' + percentage + '%)';
                            }
                        }
                    }
                })
            });

            if (typeof Chart !== 'undefined') {
                this.charts[canvasId] = new Chart(ctx, {
                    type: type,
                    data: chartData,
                    options: options
                });
                return this.charts[canvasId];
            }
            return null;
        },

        createComparisonChart: function(canvasId, data) {
            var ctx = document.getElementById(canvasId);
            if (!ctx) return null;

            var chartData = {
                labels: data.labels || [],
                datasets: [
                    {
                        label: 'Current Month',
                        data: data.current || [],
                        backgroundColor: 'rgba(52, 152, 219, 0.8)',
                        borderColor: '#3498db',
                        borderWidth: 2,
                        borderRadius: 4,
                        borderSkipped: false,
                    },
                    {
                        label: 'Previous Month',
                        data: data.previous || [],
                        backgroundColor: 'rgba(149, 165, 166, 0.8)',
                        borderColor: '#95a5a6',
                        borderWidth: 2,
                        borderRadius: 4,
                        borderSkipped: false,
                    }
                ]
            };

            var options = _.extend({}, this.chartDefaults, {
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            font: {
                                size: 11
                            },
                            maxRotation: 45
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)',
                            drawBorder: false
                        },
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString();
                            },
                            font: {
                                size: 11
                            }
                        }
                    }
                },
                plugins: _.extend({}, this.chartDefaults.plugins, {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + context.parsed.y.toLocaleString();
                            }
                        }
                    }
                })
            });

            if (typeof Chart !== 'undefined') {
                this.charts[canvasId] = new Chart(ctx, {
                    type: 'bar',
                    data: chartData,
                    options: options
                });
                return this.charts[canvasId];
            }
            return null;
        },

        createTrendChart: function(canvasId, data) {
            var ctx = document.getElementById(canvasId);
            if (!ctx) return null;

            var chartData = {
                labels: data.labels || [],
                datasets: [
                    {
                        label: 'Total Payroll',
                        data: data.payroll || [],
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#3498db',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 6,
                        pointHoverRadius: 8
                    },
                    {
                        label: 'Employee Count',
                        data: data.employees || [],
                        borderColor: '#27ae60',
                        backgroundColor: 'rgba(39, 174, 96, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#27ae60',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 6,
                        pointHoverRadius: 8,
                        yAxisID: 'y1'
                    }
                ]
            };

            var options = _.extend({}, this.chartDefaults, {
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Payroll Amount'
                        },
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString();
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Employee Count'
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                }
            });

            if (typeof Chart !== 'undefined') {
                this.charts[canvasId] = new Chart(ctx, {
                    type: 'line',
                    data: chartData,
                    options: options
                });
                return this.charts[canvasId];
            }
            return null;
        },

        createVarianceChart: function(canvasId, data) {
            var ctx = document.getElementById(canvasId);
            if (!ctx) return null;

            var chartData = {
                labels: data.labels || [],
                datasets: [{
                    label: 'Variance %',
                    data: data.variance || [],
                    backgroundColor: function(context) {
                        var value = context.parsed.y;
                        if (value > 10) return 'rgba(39, 174, 96, 0.8)';
                        if (value < -10) return 'rgba(231, 76, 60, 0.8)';
                        return 'rgba(149, 165, 166, 0.8)';
                    },
                    borderColor: function(context) {
                        var value = context.parsed.y;
                        if (value > 10) return '#27ae60';
                        if (value < -10) return '#e74c3c';
                        return '#95a5a6';
                    },
                    borderWidth: 2
                }]
            };

            var options = _.extend({}, this.chartDefaults, {
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Variance %'
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                },
                plugins: _.extend({}, this.chartDefaults.plugins, {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'Variance: ' + context.parsed.y.toFixed(1) + '%';
                            }
                        }
                    }
                })
            });

            if (typeof Chart !== 'undefined') {
                this.charts[canvasId] = new Chart(ctx, {
                    type: 'bar',
                    data: chartData,
                    options: options
                });
                return this.charts[canvasId];
            }
            return null;
        },

        updateChart: function(chartId, newData) {
            if (this.charts[chartId]) {
                var chart = this.charts[chartId];
                chart.data = newData;
                chart.update('active');
            }
        },

        destroyChart: function(chartId) {
            if (this.charts[chartId]) {
                this.charts[chartId].destroy();
                delete this.charts[chartId];
            }
        },

        destroyAllCharts: function() {
            Object.keys(this.charts).forEach(function(chartId) {
                this.destroyChart(chartId);
            }.bind(this));
        },

        // Utility functions for data formatting
        formatCurrency: function(amount, currency) {
            currency = currency || 'IDR';
            return new Intl.NumberFormat('id-ID', {
                style: 'currency',
                currency: currency,
                minimumFractionDigits: 0
            }).format(amount);
        },

        formatPercentage: function(value, decimals) {
            decimals = decimals || 1;
            return value.toFixed(decimals) + '%';
        },

        getVarianceColor: function(variance) {
            if (variance > 10) return '#27ae60';
            if (variance < -10) return '#e74c3c';
            return '#95a5a6';
        },

        // Animation helpers
        animateValue: function(element, start, end, duration) {
            var startTimestamp = null;
            var step = function(timestamp) {
                if (!startTimestamp) startTimestamp = timestamp;
                var progress = Math.min((timestamp - startTimestamp) / duration, 1);
                var currentValue = progress * (end - start) + start;
                element.innerHTML = Math.floor(currentValue).toLocaleString();
                if (progress < 1) {
                    window.requestAnimationFrame(step);
                }
            };
            window.requestAnimationFrame(step);
        },

        // Data fetching helper
        fetchChartData: function(model, method, args) {
            return rpc.query({
                model: model,
                method: method,
                args: args || []
            });
        }
    });

    // Export the classes for use in other modules with UNIQUE names
    return {
        PayrollChartManager: PayrollChartManager,
        CHART_COLORS: CHART_COLORS
    };
});