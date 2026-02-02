/* Vietnam Insurance Analytics - Extension for Salary Structure Analytics Dashboard */
/* Extends the FormulaConfigAnalytics controller to handle Insurance Analysis tab */

odoo.define('pb_hr_payroll_vietnam.InsuranceAnalytics', function (require) {
    'use strict';

    var core = require('web.core');
    var _t = core._t;

    // Get the original controller
    var FormulaConfigAnalyticsController;
    try {
        FormulaConfigAnalyticsController = require('pb_hr_payroll_analytics.FormulaConfigAnalytics');
    } catch (e) {
        console.warn('pb_hr_payroll_analytics.FormulaConfigAnalytics not available');
        return;
    }

    // Format currency for display (same as parent)
    function formatCurrency(amount) {
        if (typeof amount === 'undefined' || amount === null) return '0 ₫';
        var formatted = Math.abs(amount).toLocaleString('vi-VN', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        });
        return (amount < 0 ? '-' : '') + formatted + ' ₫';
    }

    // Insurance chart colors
    var insuranceColors = {
        si: '#3b82f6',  // Blue - Social Insurance
        hi: '#f59e0b',  // Yellow - Health Insurance  
        ui: '#ec4899',  // Pink - Unemployment Insurance
        oa: '#ef4444',  // Red - Occupational Accident
        employer: '#10b981',  // Green - Employer
        employee: '#6366f1'   // Indigo - Employee
    };

    // Extend the form controller to add insurance handling
    if (FormulaConfigAnalyticsController && FormulaConfigAnalyticsController.Controller) {
        FormulaConfigAnalyticsController.Controller.include({

            /**
             * Override _onTabClick to handle insurance_analysis tab
             */
            _onTabClick: function (ev) {
                var self = this;
                var tabName = ev.currentTarget.getAttribute('name') ||
                    ev.currentTarget.closest('.nav-link')?.getAttribute('name') ||
                    ev.currentTarget.getAttribute('href')?.replace('#', '') ||
                    ev.currentTarget.textContent?.trim()?.toLowerCase()?.replace(/\s+/g, '_');

                // Check if it's the insurance analysis tab
                if (tabName === 'insurance_analysis' ||
                    ev.currentTarget.textContent?.trim() === 'Insurance Analysis') {
                    setTimeout(function () {
                        self._loadInsuranceAnalysisView();
                    }, 100);
                } else {
                    // Call parent handler
                    this._super.apply(this, arguments);
                }
            },

            /**
             * Load and render Insurance Analysis View
             */
            _loadInsuranceAnalysisView: function () {
                var recordData = this.model.get(this.handle).data;
                var insuranceJson = recordData.insurance_data_json;

                if (!insuranceJson) {
                    this._showInsuranceNoData();
                    return;
                }

                try {
                    var data = JSON.parse(insuranceJson);
                    this._renderInsuranceKPIs(data);
                    this._renderInsuranceCharts(data);
                    this._renderInsuranceTable(data);
                    this._renderEnrollmentStats(data);
                } catch (e) {
                    console.error('Error parsing insurance data:', e);
                    this._showInsuranceNoData();
                }
            },

            /**
             * Show no data message for insurance
             */
            _showInsuranceNoData: function () {
                var container = document.getElementById('chart-insurance-distribution');
                if (container) {
                    container.parentElement.innerHTML = '<div style="text-align: center; color: #6b7280; padding: 60px;">' +
                        '<i class="fa fa-info-circle" style="font-size: 48px; margin-bottom: 20px;"></i>' +
                        '<p>' + _t('No insurance data available. Ensure employees have insurance policies assigned.') + '</p></div>';
                }
            },

            /**
             * Render Insurance KPI Cards
             */
            _renderInsuranceKPIs: function (data) {
                // SI Total
                var siTotal = document.getElementById('ins-si-total');
                if (siTotal) {
                    siTotal.textContent = formatCurrency((data.si_employer || 0) + (data.si_employee || 0));
                }

                // HI Total
                var hiTotal = document.getElementById('ins-hi-total');
                if (hiTotal) {
                    hiTotal.textContent = formatCurrency((data.hi_employer || 0) + (data.hi_employee || 0));
                }

                // UI Total
                var uiTotal = document.getElementById('ins-ui-total');
                if (uiTotal) {
                    uiTotal.textContent = formatCurrency((data.ui_employer || 0) + (data.ui_employee || 0));
                }

                // Grand Total
                var grandTotal = document.getElementById('ins-grand-total');
                if (grandTotal) {
                    grandTotal.textContent = formatCurrency(data.grand_total || 0);
                }
            },

            /**
             * Render Insurance Charts
             */
            _renderInsuranceCharts: function (data) {
                var self = this;

                // Chart 1: Insurance Distribution (Doughnut)
                var distCanvas = document.getElementById('chart-insurance-distribution');
                if (distCanvas && window.Chart && data.distribution_chart) {
                    this._destroyChart('chart-insurance-distribution');

                    var ctx = distCanvas.getContext('2d');
                    this.charts['chart-insurance-distribution'] = new Chart(ctx, {
                        type: 'doughnut',
                        data: {
                            labels: data.distribution_chart.labels,
                            datasets: [{
                                data: data.distribution_chart.data,
                                backgroundColor: data.distribution_chart.colors,
                                borderColor: '#fff',
                                borderWidth: 2
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            cutout: '50%',
                            plugins: {
                                legend: {
                                    position: 'right',
                                    labels: {
                                        padding: 15,
                                        font: { size: 11 },
                                        usePointStyle: true,
                                        boxWidth: 12
                                    }
                                },
                                tooltip: {
                                    callbacks: {
                                        label: function (context) {
                                            var sum = context.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                                            var percentage = sum > 0 ? ((context.parsed / sum) * 100).toFixed(1) : 0;
                                            return context.label + ': ' + formatCurrency(context.parsed) + ' (' + percentage + '%)';
                                        }
                                    }
                                }
                            }
                        }
                    });
                }

                // Chart 2: Employer vs Employee Split (Stacked Bar)
                var splitCanvas = document.getElementById('chart-insurance-split');
                if (splitCanvas && window.Chart && data.split_chart) {
                    this._destroyChart('chart-insurance-split');

                    var ctx2 = splitCanvas.getContext('2d');
                    this.charts['chart-insurance-split'] = new Chart(ctx2, {
                        type: 'bar',
                        data: {
                            labels: data.split_chart.labels,
                            datasets: [
                                {
                                    label: _t('Employer'),
                                    data: data.split_chart.employer,
                                    backgroundColor: insuranceColors.employer,
                                    borderColor: insuranceColors.employer,
                                    borderWidth: 1
                                },
                                {
                                    label: _t('Employee'),
                                    data: data.split_chart.employee,
                                    backgroundColor: insuranceColors.employee,
                                    borderColor: insuranceColors.employee,
                                    borderWidth: 1
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: true,
                            plugins: {
                                legend: {
                                    position: 'bottom',
                                    labels: { padding: 20, font: { size: 12 } }
                                },
                                tooltip: {
                                    callbacks: {
                                        label: function (context) {
                                            return context.dataset.label + ': ' + formatCurrency(context.parsed.y);
                                        }
                                    }
                                }
                            },
                            scales: {
                                x: {
                                    stacked: true,
                                    grid: { display: false }
                                },
                                y: {
                                    stacked: true,
                                    ticks: {
                                        callback: function (value) { return formatCurrency(value); }
                                    }
                                }
                            }
                        }
                    });
                }
            },

            /**
             * Render Insurance Breakdown Table
             */
            _renderInsuranceTable: function (data) {
                // SI amounts
                var siEmployerAmt = document.getElementById('si-employer-amt');
                if (siEmployerAmt) siEmployerAmt.textContent = formatCurrency(data.si_employer || 0);

                var siEmployeeAmt = document.getElementById('si-employee-amt');
                if (siEmployeeAmt) siEmployeeAmt.textContent = formatCurrency(data.si_employee || 0);

                var siTotalAmt = document.getElementById('si-total-amt');
                if (siTotalAmt) siTotalAmt.textContent = formatCurrency((data.si_employer || 0) + (data.si_employee || 0));

                // HI amounts
                var hiEmployerAmt = document.getElementById('hi-employer-amt');
                if (hiEmployerAmt) hiEmployerAmt.textContent = formatCurrency(data.hi_employer || 0);

                var hiEmployeeAmt = document.getElementById('hi-employee-amt');
                if (hiEmployeeAmt) hiEmployeeAmt.textContent = formatCurrency(data.hi_employee || 0);

                var hiTotalAmt = document.getElementById('hi-total-amt');
                if (hiTotalAmt) hiTotalAmt.textContent = formatCurrency((data.hi_employer || 0) + (data.hi_employee || 0));

                // UI amounts
                var uiEmployerAmt = document.getElementById('ui-employer-amt');
                if (uiEmployerAmt) uiEmployerAmt.textContent = formatCurrency(data.ui_employer || 0);

                var uiEmployeeAmt = document.getElementById('ui-employee-amt');
                if (uiEmployeeAmt) uiEmployeeAmt.textContent = formatCurrency(data.ui_employee || 0);

                var uiTotalAmt = document.getElementById('ui-total-amt');
                if (uiTotalAmt) uiTotalAmt.textContent = formatCurrency((data.ui_employer || 0) + (data.ui_employee || 0));

                // OA/OD amounts
                var oaEmployerAmt = document.getElementById('oa-employer-amt');
                if (oaEmployerAmt) oaEmployerAmt.textContent = formatCurrency(data.oa_od || 0);

                var oaTotalAmt = document.getElementById('oa-total-amt');
                if (oaTotalAmt) oaTotalAmt.textContent = formatCurrency(data.oa_od || 0);

                // Totals
                var totalEmployerAmt = document.getElementById('total-employer-amt');
                if (totalEmployerAmt) totalEmployerAmt.textContent = formatCurrency(data.total_employer || 0);

                var totalEmployeeAmt = document.getElementById('total-employee-amt');
                if (totalEmployeeAmt) totalEmployeeAmt.textContent = formatCurrency(data.total_employee || 0);

                var grandTotalAmt = document.getElementById('grand-total-amt');
                if (grandTotalAmt) grandTotalAmt.textContent = formatCurrency(data.grand_total || 0);
            },

            /**
             * Render Enrollment Statistics
             */
            _renderEnrollmentStats: function (data) {
                var siCount = document.getElementById('si-enrolled-count');
                if (siCount) siCount.textContent = data.si_enrolled || 0;

                var hiCount = document.getElementById('hi-enrolled-count');
                if (hiCount) hiCount.textContent = data.hi_enrolled || 0;

                var uiCount = document.getElementById('ui-enrolled-count');
                if (uiCount) uiCount.textContent = data.ui_enrolled || 0;
            }
        });
    }

    return {};
});
