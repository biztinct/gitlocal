/* HR Analytics Export - PDF/Excel/CSV Export Functionality */

odoo.define('pb_hr_payroll_analytics.Export', function (require) {
    'use strict';

    var rpc = require('web.rpc');
    var framework = require('web.framework');
    var core = require('web.core');
    var _t = core._t;

    return {
        // =====================================================================
        // PDF EXPORT
        // =====================================================================

        exportToPDF: function(reportType, analyticsId) {
            var reportMap = {
                'personnel_costs': 'pb_hr_payroll_analytics.action_report_personnel_costs',
                'statutory': 'pb_hr_payroll_analytics.action_report_statutory_contrib',
                'headcount': 'pb_hr_payroll_analytics.action_report_headcount'
            };

            var reportRef = reportMap[reportType];
            if (reportRef) {
                framework.blockUI();
                rpc.query({
                    model: 'ir.actions.report',
                    method: 'render',
                    args: [reportRef, [analyticsId]],
                }).then(function(data) {
                    framework.unblockUI();
                    var blob = new Blob([data], { type: 'application/pdf' });
                    var url = URL.createObjectURL(blob);
                    var link = document.createElement('a');
                    link.href = url;
                    link.download = reportType + '_' + new Date().getTime() + '.pdf';
                    link.click();
                    URL.revokeObjectURL(url);
                });
            }
        },

        // =====================================================================
        // EXCEL EXPORT
        // =====================================================================

        exportToExcel: function(reportType, data) {
            var ws = XLSX.utils.json_to_sheet(data);
            var wb = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(wb, ws, _t('Report'));
            XLSX.writeFile(wb, reportType + '_' + new Date().getTime() + '.xlsx');
        },

        // =====================================================================
        // CSV EXPORT
        // =====================================================================

        exportToCSV: function(reportType, data) {
            var csv = this._convertToCSV(data);
            var blob = new Blob([csv], { type: 'text/csv' });
            var url = URL.createObjectURL(blob);
            var link = document.createElement('a');
            link.href = url;
            link.download = reportType + '_' + new Date().getTime() + '.csv';
            link.click();
            URL.revokeObjectURL(url);
        },

        _convertToCSV: function(data) {
            var csv = '';

            if (Array.isArray(data) && data.length > 0) {
                // Header row
                var headers = Object.keys(data[0]);
                csv = headers.join(',') + '\n';

                // Data rows
                data.forEach(function(row) {
                    var values = headers.map(function(header) {
                        var value = row[header];
                        // Escape quotes in values
                        if (typeof value === 'string' && value.includes(',')) {
                            value = '"' + value.replace(/"/g, '""') + '"';
                        }
                        return value || '';
                    });
                    csv += values.join(',') + '\n';
                });
            }

            return csv;
        },

        // =====================================================================
        // CHART IMAGE EXPORT
        // =====================================================================

        exportChartImage: function(chartElementId, fileName) {
            var canvas = document.getElementById(chartElementId);
            if (!canvas) return;

            var link = document.createElement('a');
            link.href = canvas.toDataURL('image/png');
            link.download = (fileName || _t('chart')) + '.png';
            link.click();
        },

        // =====================================================================
        // COMBINED REPORT EXPORT
        // =====================================================================

        exportCompleteReport: function(reportType, format, options) {
            options = options || {};

            var reportData = {
                type: reportType,
                format: format,
                includeCharts: options.includeCharts || true,
                includeTables: options.includeTables || true,
                includeSummary: options.includeSummary || true,
                timestamp: new Date().toISOString()
            };

            if (format === 'pdf') {
                this._generatePDFReport(reportData);
            } else if (format === 'xlsx') {
                this._generateExcelReport(reportData);
            } else if (format === 'csv') {
                this._generateCSVReport(reportData);
            }
        },

        _generatePDFReport: function(reportData) {
            // Placeholder - actual PDF generation would use jsPDF or similar
            console.log('Generating PDF Report:', reportData);
        },

        _generateExcelReport: function(reportData) {
            // Placeholder - actual Excel generation would use XLSX library
            console.log('Generating Excel Report:', reportData);
        },

        _generateCSVReport: function(reportData) {
            // Placeholder - actual CSV generation
            console.log('Generating CSV Report:', reportData);
        },

        // =====================================================================
        // PRINT FUNCTIONALITY
        // =====================================================================

        printReport: function(contentElementId) {
            var printWindow = window.open('', '', 'height=600,width=800');
            var printContents = document.getElementById(contentElementId).innerHTML;

            printWindow.document.write('<html><head><title>' + _t('HR Analytics Report') + '</title>');
            printWindow.document.write('<link rel="stylesheet" href="/pb_hr_payroll_analytics/static/src/css/hr_analytics_dashboard.css">');
            printWindow.document.write('</head><body>');
            printWindow.document.write(printContents);
            printWindow.document.write('</body></html>');

            printWindow.document.close();
            printWindow.print();

            return false;
        }
    };
});
