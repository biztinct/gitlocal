# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import io
import json
import logging

_logger = logging.getLogger(__name__)


class WfpExportWizard(models.TransientModel):
    """Wizard to export scenario forecasts to Excel."""
    _name = 'wfp.export.wizard'
    _description = 'WFP Export Wizard'

    scenario_id = fields.Many2one(
        'wfp.planning.scenario',
        string='Scenario',
        required=True,
    )
    export_type = fields.Selection([
        ('detail', 'Employee Detail'),
        ('summary', 'Department Summary'),
        ('component', 'Component Breakdown'),
        ('monthly', 'Monthly Projections'),
    ], string='Export Type', default='detail', required=True)

    export_file = fields.Binary(string='Export File', readonly=True)
    export_filename = fields.Char(string='Filename', readonly=True)

    def action_export(self):
        """Generate Excel export."""
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_(
                "xlsxwriter library is required for Excel export. "
                "Please install it: pip install xlsxwriter"
            ))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Formats
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#21435F', 'font_color': 'white',
            'border': 1, 'text_wrap': True, 'valign': 'vcenter',
        })
        number_fmt = workbook.add_format({
            'num_format': '#,##0', 'border': 1,
        })
        pct_fmt = workbook.add_format({
            'num_format': '0.00%', 'border': 1,
        })
        text_fmt = workbook.add_format({'border': 1})

        if self.export_type == 'detail':
            self._export_detail(workbook, header_fmt, number_fmt, pct_fmt, text_fmt)
        elif self.export_type == 'summary':
            self._export_summary(workbook, header_fmt, number_fmt, pct_fmt, text_fmt)
        elif self.export_type == 'component':
            self._export_component(workbook, header_fmt, number_fmt, pct_fmt, text_fmt)
        elif self.export_type == 'monthly':
            self._export_monthly(workbook, header_fmt, number_fmt, pct_fmt, text_fmt)

        workbook.close()
        output.seek(0)

        import base64
        self.export_file = base64.b64encode(output.read())
        self.export_filename = '%s_%s.xlsx' % (
            self.scenario_id.name.replace(' ', '_'),
            self.export_type,
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wfp.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _export_detail(self, wb, hfmt, nfmt, pfmt, tfmt):
        ws = wb.add_worksheet('Employee Detail')
        headers = [
            'Employee', 'Department', 'Job', 'Country', 'Location',
            'Current Base', 'Current Gross', 'Current Employer Cost',
            'Current TCOW', 'Forecast Base', 'Forecast Gross',
            'Forecast Employer Cost', 'Forecast TCOW',
            'Increase Amount', 'Increase %', 'Rule Applied',
        ]
        for col, h in enumerate(headers):
            ws.write(0, col, h, hfmt)
            ws.set_column(col, col, 16)

        forecasts = self.scenario_id.employee_forecast_ids.filtered(
            lambda f: not f.is_excluded
        ).sorted(key=lambda f: f.employee_id.name)

        for row, f in enumerate(forecasts, start=1):
            ws.write(row, 0, f.employee_id.name or '', tfmt)
            ws.write(row, 1, f.department_id.name or '', tfmt)
            ws.write(row, 2, f.job_id.name or '', tfmt)
            ws.write(row, 3, f.country_code or '', tfmt)
            ws.write(row, 4, f.location or '', tfmt)
            ws.write(row, 5, f.current_base, nfmt)
            ws.write(row, 6, f.current_gross, nfmt)
            ws.write(row, 7, f.current_employer_cost, nfmt)
            ws.write(row, 8, f.current_total_cost, nfmt)
            ws.write(row, 9, f.forecast_base, nfmt)
            ws.write(row, 10, f.forecast_gross, nfmt)
            ws.write(row, 11, f.forecast_employer_cost, nfmt)
            ws.write(row, 12, f.forecast_total_cost, nfmt)
            ws.write(row, 13, f.increase_amount, nfmt)
            ws.write(row, 14, f.increase_pct / 100, pfmt)
            ws.write(row, 15, f.applied_rule_name or '', tfmt)

    def _export_summary(self, wb, hfmt, nfmt, pfmt, tfmt):
        ws = wb.add_worksheet('Department Summary')
        headers = [
            'Department', 'Headcount', 'Current TCOW', 'Forecast TCOW',
            'Increase', 'Increase %',
        ]
        for col, h in enumerate(headers):
            ws.write(0, col, h, hfmt)
            ws.set_column(col, col, 18)

        forecasts = self.scenario_id.employee_forecast_ids.filtered(
            lambda f: not f.is_excluded
        )
        dept_data = {}
        for f in forecasts:
            dept = f.department_id.name or _('No Department')
            if dept not in dept_data:
                dept_data[dept] = {
                    'headcount': 0, 'current': 0, 'forecast': 0,
                }
            dept_data[dept]['headcount'] += 1
            dept_data[dept]['current'] += f.current_total_cost
            dept_data[dept]['forecast'] += f.forecast_total_cost

        for row, (dept, data) in enumerate(
            sorted(dept_data.items()), start=1
        ):
            increase = data['forecast'] - data['current']
            pct = (increase / data['current'] * 100) if data['current'] else 0
            ws.write(row, 0, dept, tfmt)
            ws.write(row, 1, data['headcount'], nfmt)
            ws.write(row, 2, data['current'], nfmt)
            ws.write(row, 3, data['forecast'], nfmt)
            ws.write(row, 4, increase, nfmt)
            ws.write(row, 5, pct / 100, pfmt)

    def _export_component(self, wb, hfmt, nfmt, pfmt, tfmt):
        ws = wb.add_worksheet('Component Breakdown')
        headers = [
            'Employee', 'Component Code', 'Component Name',
            'WFP Category', 'Current Amount', 'Forecast Amount', 'Delta',
        ]
        for col, h in enumerate(headers):
            ws.write(0, col, h, hfmt)
            ws.set_column(col, col, 18)

        forecasts = self.scenario_id.employee_forecast_ids.filtered(
            lambda f: not f.is_excluded
        )
        row = 1
        for f in forecasts.sorted(key=lambda f: f.employee_id.name):
            current_comps = f.get_current_components()
            forecast_comps = f.get_forecast_components()
            fc_map = {c['code']: c for c in forecast_comps}

            for cc in current_comps:
                fc = fc_map.get(cc['code'], {})
                c_amt = cc.get('amount', 0)
                f_amt = fc.get('amount', 0)
                ws.write(row, 0, f.employee_id.name, tfmt)
                ws.write(row, 1, cc.get('code', ''), tfmt)
                ws.write(row, 2, cc.get('name', ''), tfmt)
                ws.write(row, 3, cc.get('wfp_category', ''), tfmt)
                ws.write(row, 4, c_amt, nfmt)
                ws.write(row, 5, f_amt, nfmt)
                ws.write(row, 6, f_amt - c_amt, nfmt)
                row += 1

    def _export_monthly(self, wb, hfmt, nfmt, pfmt, tfmt):
        ws = wb.add_worksheet('Monthly Projections')
        headers = [
            'Period', 'Headcount', 'Total Base', 'Total Gross',
            'Total Employer Cost', 'Total TCOW', 'Delta vs Current',
        ]
        for col, h in enumerate(headers):
            ws.write(0, col, h, hfmt)
            ws.set_column(col, col, 18)

        projections = self.scenario_id.monthly_projection_ids.sorted(
            key=lambda p: (p.year, int(p.month))
        )
        for row, p in enumerate(projections, start=1):
            ws.write(row, 0, p.period_label, tfmt)
            ws.write(row, 1, p.headcount, nfmt)
            ws.write(row, 2, p.total_base, nfmt)
            ws.write(row, 3, p.total_gross, nfmt)
            ws.write(row, 4, p.total_employer_cost, nfmt)
            ws.write(row, 5, p.total_cost_to_company, nfmt)
            ws.write(row, 6, p.delta_vs_current, nfmt)
