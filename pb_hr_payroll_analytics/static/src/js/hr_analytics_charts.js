/* HR Analytics Charts - Chart.js Integration with 10+ Chart Types */

console.log('[HR Analytics] Charts.js file loaded');

odoo.define('pb_hr_payroll_analytics.Charts', function (require) {
    'use strict';

    console.log('[HR Analytics] Charts module definition starting...');

    var Chart = window.Chart || {};
    var charts = {};

    console.log('[HR Analytics] Chart object available:', !!Chart);

    // Color Palettes
    var colorPalettes = {
        primary: ['#3498db', '#2ecc71', '#e74c3c', '#f39c12', '#9b59b6'],
        pastel: ['#FFB6C1', '#87CEEB', '#98FB98', '#FFD700', '#DDA0DD'],
        vibrant: ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8'],
        department: {
            'Sales': '#3498db',
            'HR': '#2ecc71',
            'IT': '#e74c3c',
            'Finance': '#f39c12',
            'Admin': '#9b59b6',
            'Operations': '#1abc9c',
            'Marketing': '#e91e63'
        }
    };

    // =====================================================================
    // 1. DOUGHNUT CHART
    // =====================================================================
    var createDoughnutChart = function (elementId, labels, data, colors, onClickCallback) {
        if (!document.getElementById(elementId)) return;

        var ctx = document.getElementById(elementId).getContext('2d');
        charts[elementId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors || colorPalettes.primary,
                    borderColor: '#fff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                onClick: function (event, activeElements) {
                    if (activeElements.length > 0 && onClickCallback) {
                        var index = activeElements[0].index;
                        var label = labels[index];
                        var value = data[index];
                        console.log('[HR Analytics] Chart segment clicked:', label, value);
                        onClickCallback(label, value, index);
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            font: { size: 12, weight: 600 },
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        padding: 12,
                        titleFont: { size: 13 },
                        bodyFont: { size: 12 },
                        callbacks: {
                            label: function (context) {
                                var sum = context.dataset.data.reduce((a, b) => a + b, 0);
                                var percentage = ((context.parsed / sum) * 100).toFixed(1);
                                return context.label + ': ' + formatCurrency(context.parsed) + ' (' + percentage + '%)';
                            }
                        }
                    }
                },
                animation: {
                    animateRotate: true,
                    animateScale: false,
                    duration: 1000,
                    easing: 'easeInOutQuart'
                }
            }
        });
    };

    // =====================================================================
    // 2. HORIZONTAL BAR CHART
    // =====================================================================
    var createHorizontalBarChart = function (elementId, labels, datasets) {
        if (!document.getElementById(elementId)) return;

        var ctx = document.getElementById(elementId).getContext('2d');
        charts[elementId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        labels: { font: { size: 12 } }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        padding: 12
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0,0,0,0.05)' }
                    },
                    y: {
                        grid: { display: false }
                    }
                }
            }
        });
    };

    // =====================================================================
    // 3. VERTICAL BAR CHART
    // =====================================================================
    var createVerticalBarChart = function (elementId, labels, datasets) {
        if (!document.getElementById(elementId)) return;

        var ctx = document.getElementById(elementId).getContext('2d');
        charts[elementId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        labels: { font: { size: 12 } }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0,0,0,0.05)' }
                    }
                }
            }
        });
    };

    // =====================================================================
    // 4. STACKED BAR CHART
    // =====================================================================
    var createStackedBarChart = function (elementId, labels, datasets) {
        if (!document.getElementById(elementId)) return;

        var ctx = document.getElementById(elementId).getContext('2d');
        charts[elementId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { usePointStyle: true, padding: 15 }
                    }
                }
            }
        });
    };

    // =====================================================================
    // 5. LINE CHART (for trends)
    // =====================================================================
    var createLineChart = function (elementId, labels, datasets) {
        if (!document.getElementById(elementId)) return;

        var ctx = document.getElementById(elementId).getContext('2d');
        charts[elementId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: true }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } }
                },
                elements: {
                    line: { tension: 0.4 }
                }
            }
        });
    };

    // =====================================================================
    // 6. SCATTER PLOT CHART
    // =====================================================================
    var createScatterChart = function (elementId, dataPoints, labels) {
        if (!document.getElementById(elementId)) return;

        var ctx = document.getElementById(elementId).getContext('2d');
        charts[elementId] = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Countries',
                    data: dataPoints,
                    backgroundColor: 'rgba(52, 152, 219, 0.6)',
                    borderColor: '#3498db',
                    borderWidth: 2,
                    pointRadius: 8,
                    pointHoverRadius: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: true }
                },
                scales: {
                    y: { beginAtZero: true, title: { display: true, text: 'Cost per Employee' } },
                    x: { title: { display: true, text: 'Headcount' } }
                }
            }
        });
    };

    // =====================================================================
    // 7. PIE CHART
    // =====================================================================
    var createPieChart = function (elementId, labels, data, colors) {
        if (!document.getElementById(elementId)) return;

        var ctx = document.getElementById(elementId).getContext('2d');
        charts[elementId] = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors || colorPalettes.primary
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    };

    // =====================================================================
    // UTILITY FUNCTIONS
    // =====================================================================

    var formatCurrency = function (amount) {
        if (amount >= 1000000) {
            return (amount / 1000000).toFixed(1) + 'M';
        } else if (amount >= 1000) {
            return (amount / 1000).toFixed(1) + 'K';
        }
        return amount.toFixed(0);
    };

    var destroyChart = function (elementId) {
        if (charts[elementId]) {
            charts[elementId].destroy();
            delete charts[elementId];
        }
    };

    var destroyAllCharts = function () {
        Object.keys(charts).forEach(function (key) {
            charts[key].destroy();
        });
        charts = {};
    };

    // =====================================================================
    // EXPORT PUBLIC FUNCTIONS
    // =====================================================================

    return {
        createDoughnutChart: createDoughnutChart,
        createHorizontalBarChart: createHorizontalBarChart,
        createVerticalBarChart: createVerticalBarChart,
        createStackedBarChart: createStackedBarChart,
        createLineChart: createLineChart,
        createScatterChart: createScatterChart,
        createPieChart: createPieChart,
        formatCurrency: formatCurrency,
        destroyChart: destroyChart,
        destroyAllCharts: destroyAllCharts,
        colorPalettes: colorPalettes
    };
});
