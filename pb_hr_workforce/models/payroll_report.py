# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class PayrollReport(models.TransientModel):
    """Backend API for the Rippling-style Payroll Report Dashboard."""
    _name = 'hr.payroll.report.api'
    _description = 'Payroll Report API'

    @staticmethod
    def _sum_category(lines, codes):
        """Total the lines in these rule categories, skipping subtotals."""
        return sum(l.total for l in lines
                   if l.category_id and (l.category_id.code or '').upper() in codes
                   and l.pb_counts_in_totals())

    @staticmethod
    def _breakdown(lines, prev_lines, signed=False):
        """One row per component, with the previous period's figure beside it.

        NO EARLIER PAYSLIP IS NOT A CHANGE OF ZERO. Where there is nothing to
        compare against, the difference is left at zero so the screen shows a
        dash — subtracting an absent figure said everybody's pay had just gone
        up by the whole of it.
        """
        rows = []
        for line in lines:
            if not line.total:
                continue
            prev = prev_lines.filtered(
                lambda x: x.salary_rule_id.id == line.salary_rule_id.id)
            prev_val = prev[0].total if prev else 0.0
            current = line.total if signed else abs(line.total)
            previous = prev_val if signed else abs(prev_val)
            rows.append({
                'name': line.name,
                'code': line.code,
                'current': current,
                'previous': previous,
                'diff': (current - previous) if prev_lines else 0.0,
            })
        return rows

    @api.model
    def get_batch_report(self, batch_id):
        """
        Employee-level payroll data for a specific batch run,
        with comparison to the previous batch.
        """
        batch = self.env['hr.payslip.run'].browse(batch_id)
        if not batch.exists():
            return {'error': _('Batch not found')}

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

            # Which band each line belongs in is the scheme's own answer, read
            # through the shared helper so this screen can never disagree with
            # the pay run it was opened from. Reading the rule category here
            # instead reported ₫0 gross and ₫10,747,123,945 deductions against
            # a run of ₫2,060,124,305 and ₫289,886,044.
            totals = lines.pb_pay_totals()
            gross = totals['gross']
            net = totals['net']
            deductions = totals['deductions']
            # Basic and Allowances are columns of their own, not bands of net
            # pay, so they stay on the rule category — but only over the lines
            # the totals above already count, so a subtotal is never added on
            # top of the components it is a subtotal of.
            basic = self._sum_category(lines, ('BASIC',))
            allowances = self._sum_category(lines, ('ALW', 'ALLOWANCE'))

            # Get previous slip for comparison
            prev_slip = prev_slips.filtered(lambda s: s.employee_id.id == emp.id)
            prev_gross = prev_net = prev_deductions = prev_basic = 0
            if prev_slip:
                prev_lines = prev_slip[0].line_ids
                prev_totals = prev_lines.pb_pay_totals()
                prev_gross = prev_totals['gross']
                prev_net = prev_totals['net']
                prev_deductions = prev_totals['deductions']
                prev_basic = self._sum_category(prev_lines, ('BASIC',))

            # Detect changes (related events)
            events = []
            if gross != prev_gross and prev_gross:
                diff = gross - prev_gross
                if abs(diff) > 0:
                    amount = '{:,.0f}'.format(abs(diff))
                    events.append(_("Gross pay increased by %s", amount)
                                  if diff > 0 else
                                  _("Gross pay decreased by %s", amount))
            if basic != prev_basic and prev_basic:
                diff = basic - prev_basic
                if abs(diff) > 0:
                    events.append(_("Basic salary changed by %s",
                                    '{:+,.0f}'.format(diff)))

            # Earnings and deductions breakdowns. Both list exactly the lines
            # the figures above are made of — a breakdown that does not add up
            # to the number it sits under is worse than no breakdown.
            prev_line_ids = prev_slip[0].line_ids if prev_slip \
                else self.env['hr.payslip.line']
            earnings = self._breakdown(
                lines.pb_lines_in_band('gross'), prev_line_ids, signed=True)
            deduction_lines = self._breakdown(
                lines.pb_lines_in_band('deductions'), prev_line_ids)

            dept = emp.department_id.name if emp.department_id else _('Unassigned')
            dept_totals.setdefault(dept, {'gross': 0, 'net': 0, 'deductions': 0, 'count': 0})
            dept_totals[dept]['gross'] += gross
            dept_totals[dept]['net'] += net
            # Already totalled as magnitudes, so no outer abs() here: one at
            # the end cannot put back what opposite signs cancelled on the way.
            dept_totals[dept]['deductions'] += deductions
            dept_totals[dept]['count'] += 1

            employees.append({
                'id': emp.id,
                'name': emp.name,
                'job_title': emp.job_title or '',
                'department': dept,
                'avatar_url': f'/web/image/hr.employee/{emp.id}/avatar_128',
                'gross': gross,
                'net': net,
                'deductions': deductions,
                'basic': basic,
                'allowances': allowances,
                'prev_gross': prev_gross,
                'prev_net': prev_net,
                'prev_deductions': prev_deductions,
                # A dash, not a rise, where this person has no earlier payslip
                # to be compared with — see :meth:`_breakdown`.
                'diff_gross': (gross - prev_gross) if prev_slip else 0.0,
                'diff_net': (net - prev_net) if prev_slip else 0.0,
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

