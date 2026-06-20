# -*- coding: utf-8 -*-
import json
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

GROSS_CODES = ('GROSS',)
NET_CODES = ('NET',)
DED_CODES = ('DED', 'DEDUCTION', 'COMP', 'TAX')

STATE_LABEL = {
    'draft': 'Draft', 'verify': 'Waiting', 'level1': 'HR review',
    'level2': 'GM review', 'done': 'Paid', 'cancel': 'Cancelled',
}


def _initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?') + (parts[-1][0] if len(parts) > 1 else '')).upper()


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    pb_statement_json = fields.Text(
        string='Pay statement', compute='_compute_pb_statement_json')

    @api.depends('line_ids', 'line_ids.total', 'line_ids.category_id',
                 'worked_days_line_ids', 'worked_days_line_ids.number_of_hours',
                 'employee_id', 'date_from', 'date_to', 'struct_id', 'state',
                 'number', 'name')
    def _compute_pb_statement_json(self):
        for slip in self:
            try:
                slip.pb_statement_json = json.dumps(slip._pb_build_statement())
            except Exception as e:
                _logger.debug("payslip statement build failed: %s", e)
                slip.pb_statement_json = '{}'

    def _pb_build_statement(self):
        self.ensure_one()
        emp = self.employee_id
        company = self.company_id or self.env.company
        cur = company.currency_id

        # Line-level statement: list the real, shown components by name. Gross /
        # Net are taken from their category subtotal lines when present. Lines
        # are split into earnings vs deductions by category code / sign.
        earnings, deductions = [], []
        gross = net = ded_total = 0.0
        for line in self.line_ids:
            code = (line.category_id.code or '').upper()
            amt = line.total or 0.0
            if code in NET_CODES:
                net = amt
                continue
            if code in GROSS_CODES:
                gross = amt
                continue
            if not amt:
                continue
            row = {'name': line.name or line.code or '—', 'code': line.code or '',
                   'amount': abs(amt)}
            if code in DED_CODES or amt < 0:
                deductions.append(row)
                ded_total += abs(amt)
            else:
                earnings.append(row)
        if not gross:
            gross = sum(e['amount'] for e in earnings)
        if not net:
            net = gross - ded_total

        worked = []
        for wd in self.worked_days_line_ids:
            worked.append({'label': wd.name or wd.code or '—',
                           'days': wd.number_of_days or 0.0,
                           'hours': wd.number_of_hours or 0.0})

        def _d(d):
            return str(d) if d else ''

        period = ''
        if self.date_from or self.date_to:
            period = '%s – %s' % (_d(self.date_from), _d(self.date_to))

        return {
            'currency': cur.symbol or '',
            'employee': emp.name or '—',
            'initials': _initials(emp.name),
            'job': (emp.job_title or (emp.job_id.name if emp.job_id else '') or ''),
            'dept': (emp.department_id.name if emp.department_id else ''),
            'period': period,
            'structure': self.struct_id.name if self.struct_id else '',
            'reference': self.number or '',
            'state': self.state,
            'state_label': STATE_LABEL.get(self.state, self.state or ''),
            'gross': gross,
            'net': net,
            'deductions_total': ded_total,
            'earnings': earnings,
            'deductions': deductions,
            'worked': worked,
        }
