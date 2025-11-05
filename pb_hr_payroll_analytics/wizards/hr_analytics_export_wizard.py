# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class HrAnalyticsExportWizard(models.TransientModel):
    """Export Wizard for PDF/Excel/CSV export of analytics reports"""

    _name = 'hr.analytics.export.wizard'
    _description = 'HR Analytics Export Wizard'

    file_format = fields.Selection([
        ('pdf', 'PDF Report'),
        ('xlsx', 'Excel Spreadsheet'),
        ('csv', 'CSV Data')
    ], default='pdf', required=True, string='File Format')

    report_type = fields.Selection([
        ('personnel_costs', 'Personnel Costs'),
        ('cross_country', 'Cross Country Analytics'),
        ('statutory', 'Statutory Contributions'),
        ('headcount', 'Headcount Analysis'),
        ('dependents', 'Dependents & Benefits'),
        ('budget', 'Budget Variance'),
        ('annual', 'Annual HR Costs')
    ], required=True, string='Report Type')

    include_charts = fields.Boolean(
        string='Include Charts',
        default=True,
        help='Include visualizations in exported report'
    )

    include_tables = fields.Boolean(
        string='Include Tables',
        default=True,
        help='Include detailed data tables'
    )

    include_summary = fields.Boolean(
        string='Include Summary',
        default=True,
        help='Include executive summary'
    )

    file_name = fields.Char(
        string='File Name',
        compute='_compute_file_name'
    )

    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True
    )

    @api.depends('report_type', 'file_format')
    def _compute_file_name(self):
        """Generate export file name"""
        for record in self:
            timestamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
            report_names = {
                'personnel_costs': 'Personnel_Costs',
                'cross_country': 'Cross_Country_Analytics',
                'statutory': 'Statutory_Contributions',
                'headcount': 'Headcount_Analysis',
                'dependents': 'Dependents_Benefits',
                'budget': 'Budget_Variance',
                'annual': 'Annual_HR_Costs'
            }

            extension = {
                'pdf': '.pdf',
                'xlsx': '.xlsx',
                'csv': '.csv'
            }

            record.file_name = f"{report_names.get(record.report_type, 'Report')}_{timestamp}{extension.get(record.file_format, '.pdf')}"

    def action_export(self):
        """Execute export action"""
        self.ensure_one()

        try:
            if self.file_format == 'pdf':
                return self._export_to_pdf()
            elif self.file_format == 'xlsx':
                return self._export_to_excel()
            elif self.file_format == 'csv':
                return self._export_to_csv()
        except Exception as e:
            _logger.exception('Export error: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('Export failed: %s') % str(e),
                    'type': 'danger'
                }
            }

    def _export_to_pdf(self):
        """Export report to PDF"""
        # Reference QWeb report
        report_ref_map = {
            'personnel_costs': 'pb_hr_payroll_analytics.action_report_personnel_costs',
            'statutory': 'pb_hr_payroll_analytics.action_report_statutory_contrib',
            'headcount': 'pb_hr_payroll_analytics.action_report_headcount',
        }

        report_ref = report_ref_map.get(self.report_type)

        if report_ref:
            try:
                report = self.env.ref(report_ref)
                # Return action to generate PDF
                return report.report_action(self.env['hr.analytics.dashboard'])
            except Exception as e:
                _logger.exception('PDF generation error: %s', str(e))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('PDF export not yet configured for this report'),
                'type': 'warning'
            }
        }

    def _export_to_excel(self):
        """Export report to Excel"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Excel export coming soon - use PDF for now'),
                'type': 'warning'
            }
        }

    def _export_to_csv(self):
        """Export report to CSV"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('CSV export coming soon - use PDF for now'),
                'type': 'warning'
            }
        }
