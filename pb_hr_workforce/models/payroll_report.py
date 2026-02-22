# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class PayrollReport(models.TransientModel):
    """Backend API for the Rippling-style Payroll Report Dashboard."""
    _name = 'hr.payroll.report.api'
    _description = 'Payroll Report API'

    @api.model
    def get_batch_report(self, batch_id):
        """
        Employee-level payroll data for a specific batch run,
        with comparison to the previous batch.
        """
        batch = self.env['hr.payslip.run'].browse(batch_id)
        if not batch.exists():
            return {'error': 'Batch not found'}

        # Find previous batch (same structure/company, earlier date)
        prev_batch = self.env['hr.payslip.run'].search([
            ('id', '!=', batch.id),
            ('date_end', '<', batch.date_start),
            ('state', '!=', 'cancel'),
        ], order='date_end desc', limit=1)

        # Current batch payslips
        current_slips = batch.slip_ids.filtered(lambda s: s.state != 'cancel')
        prev_slips = prev_batch.slip_ids.filtered(lambda s: s.state != 'cancel') if prev_batch else self.env['hr.payslip']

        # Build employee rows
        employees = []
        dept_totals = {}  # dept_name -> {gross, net, deductions, employer_cost, count}

        for slip in current_slips:
            emp = slip.employee_id
            lines = slip.line_ids

            # Categorize lines
            gross = sum(l.total for l in lines if l.category_id.code == 'GROSS')
            net = sum(l.total for l in lines if l.category_id.code == 'NET')
            deductions = sum(l.total for l in lines if l.category_id.code in ('DED', 'DEDUCTION', 'COMP'))
            basic = sum(l.total for l in lines if l.category_id.code == 'BASIC')
            allowances = sum(l.total for l in lines if l.category_id.code in ('ALW', 'ALLOWANCE'))

            # Get previous slip for comparison
            prev_slip = prev_slips.filtered(lambda s: s.employee_id.id == emp.id)
            prev_gross = prev_net = prev_deductions = prev_basic = 0
            if prev_slip:
                prev_lines = prev_slip[0].line_ids
                prev_gross = sum(l.total for l in prev_lines if l.category_id.code == 'GROSS')
                prev_net = sum(l.total for l in prev_lines if l.category_id.code == 'NET')
                prev_deductions = sum(l.total for l in prev_lines if l.category_id.code in ('DED', 'DEDUCTION', 'COMP'))
                prev_basic = sum(l.total for l in prev_lines if l.category_id.code == 'BASIC')

            # Detect changes (related events)
            events = []
            if gross != prev_gross and prev_gross:
                diff = gross - prev_gross
                if abs(diff) > 0:
                    direction = 'increased' if diff > 0 else 'decreased'
                    events.append(f"Gross pay {direction} by {abs(diff):,.0f}")
            if basic != prev_basic and prev_basic:
                diff = basic - prev_basic
                if abs(diff) > 0:
                    events.append(f"Basic salary changed by {diff:+,.0f}")

            # Earnings breakdown
            earnings = []
            for l in lines.filtered(lambda x: x.total > 0 and x.category_id.code in ('BASIC', 'ALW', 'ALLOWANCE', 'GROSS')):
                prev_val = 0
                if prev_slip:
                    prev_line = prev_slip[0].line_ids.filtered(lambda x: x.salary_rule_id.id == l.salary_rule_id.id)
                    prev_val = prev_line[0].total if prev_line else 0
                earnings.append({
                    'name': l.name,
                    'code': l.code,
                    'current': l.total,
                    'previous': prev_val,
                    'diff': l.total - prev_val,
                })

            # Deductions breakdown
            deduction_lines = []
            for l in lines.filtered(lambda x: x.category_id.code in ('DED', 'DEDUCTION', 'COMP')):
                prev_val = 0
                if prev_slip:
                    prev_line = prev_slip[0].line_ids.filtered(lambda x: x.salary_rule_id.id == l.salary_rule_id.id)
                    prev_val = prev_line[0].total if prev_line else 0
                deduction_lines.append({
                    'name': l.name,
                    'code': l.code,
                    'current': abs(l.total),
                    'previous': abs(prev_val),
                    'diff': abs(l.total) - abs(prev_val),
                })

            dept = emp.department_id.name if emp.department_id else 'Unassigned'
            dept_totals.setdefault(dept, {'gross': 0, 'net': 0, 'deductions': 0, 'count': 0})
            dept_totals[dept]['gross'] += gross
            dept_totals[dept]['net'] += net
            dept_totals[dept]['deductions'] += abs(deductions)
            dept_totals[dept]['count'] += 1

            employees.append({
                'id': emp.id,
                'name': emp.name,
                'job_title': emp.job_title or '',
                'department': dept,
                'avatar_url': f'/web/image/hr.employee/{emp.id}/avatar_128',
                'gross': gross,
                'net': net,
                'deductions': abs(deductions),
                'basic': basic,
                'allowances': allowances,
                'prev_gross': prev_gross,
                'prev_net': prev_net,
                'prev_deductions': abs(prev_deductions),
                'diff_gross': gross - prev_gross,
                'diff_net': net - prev_net,
                'events': events,
                'earnings': earnings,
                'deduction_lines': deduction_lines,
            })

        # Sort by name
        employees.sort(key=lambda e: e['name'])

        # Department chart data
        dept_chart = []
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e']
        for i, (dept, data) in enumerate(sorted(dept_totals.items())):
            dept_chart.append({
                'name': dept,
                'net': data['net'],
                'gross': data['gross'],
                'deductions': data['deductions'],
                'count': data['count'],
                'color': colors[i % len(colors)],
            })

        total_gross = sum(d['gross'] for d in dept_totals.values())
        total_net = sum(d['net'] for d in dept_totals.values())
        total_deductions = sum(d['deductions'] for d in dept_totals.values())

        return {
            'batch': {
                'id': batch.id,
                'name': batch.name,
                'date_start': batch.date_start.isoformat() if batch.date_start else '',
                'date_end': batch.date_end.isoformat() if batch.date_end else '',
                'state': batch.state,
            },
            'prev_batch': {
                'id': prev_batch.id if prev_batch else False,
                'name': prev_batch.name if prev_batch else '',
            },
            'employees': employees,
            'dept_chart': dept_chart,
            'summary': {
                'total_employees': len(employees),
                'total_gross': total_gross,
                'total_net': total_net,
                'total_deductions': total_deductions,
                'changes': sum(1 for e in employees if e['events']),
            },
        }

    @api.model
    def get_all_batches(self):
        """Return list of batches for dropdown selection."""
        batches = self.env['hr.payslip.run'].search(
            [('state', '!=', 'cancel')],
            order='date_end desc', limit=24,
        )
        return [{
            'id': b.id,
            'name': b.name,
            'date_start': b.date_start.isoformat() if b.date_start else '',
            'date_end': b.date_end.isoformat() if b.date_end else '',
            'state': b.state,
            'count': len(b.slip_ids),
        } for b in batches]


class HrPayslipRunPayrollReport(models.Model):
    """Extend payslip run to add Payroll Report button."""
    _inherit = 'hr.payslip.run'

    def action_open_payroll_report(self):
        """Open the Rippling-style Payroll Report for this batch."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'payroll_report_dashboard',
            'name': f'Payroll Report — {self.name}',
            'context': {'batch_id': self.id},
        }

