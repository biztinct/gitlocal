# -*- coding: utf-8 -*-
import json
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

GROSS_CODES = ('GROSS',)
NET_CODES = ('NET',)
# Employee deductions (reduce take-home): insurance / tax / loan & advance.
DED_CAT_CODES = ('DED', 'DEDUCTION', 'INS', 'TAX', 'LOANDED')
DED_CAT_TYPES = ('deduction', 'social_security', 'tax')
# Employer-side cost — NOT part of the employee's gross/deductions/net.
EMPLOYER_CAT_CODES = ('COMP', 'INSCO')
EMPLOYER_CAT_TYPE = 'employer_cost'

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

        # Line-level statement. Lines are bucketed by their salary-rule category
        # (type/code), NOT just by sign, so:
        #   * employee deductions (insurance / tax / loan) reduce take-home,
        #   * EMPLOYER contributions (employer SI/HI/UI, trade-union fund) are kept
        #     OUT of the employee's gross/deductions/net (shown separately),
        #   * the mid-cycle advance is shown as a reduction so the figures
        #     reconcile: Gross − Deductions − Advance = Net (on every cycle).
        earnings, deductions, employer = [], [], []
        gross = net = ded_total = emp_total = 0.0
        has_end_adv = has_mid_adv = False
        for line in self.line_ids:
            cat = line.category_id
            code = (line.code or '').upper()
            ccode = (cat.code or '').upper()
            ctype = (cat.category_type or '') if (cat and 'category_type' in cat._fields) else ''
            amt = line.total or 0.0
            if code in NET_CODES:
                net = amt
                continue
            if code in GROSS_CODES:
                gross = amt
                continue
            # Mid-cycle advance: a single ADVPAY line. On the MID slip it duplicates
            # NET (skip); on the END slip it is the advance already paid (a reduction).
            if code == 'ADVPAY':
                if ctype == 'net' or ccode in NET_CODES:
                    has_mid_adv = True
                else:
                    has_end_adv = True
                continue
            if not amt:
                continue
            # Multilingual: resolve the component label from the translatable salary
            # rule in the reader's language, falling back to the frozen line snapshot.
            label = (line.salary_rule_id.name if line.salary_rule_id else False) \
                or line.name or line.code or '—'
            row = {'name': label, 'code': line.code or '', 'amount': abs(amt)}
            # Employer cost — informational only, never in gross/deductions/net.
            if ctype == EMPLOYER_CAT_TYPE or ccode in EMPLOYER_CAT_CODES:
                employer.append(row)
                emp_total += abs(amt)
                continue
            # Other net-category helpers (e.g. FULLPAY) are never an earning.
            if ctype == 'net' or ccode in NET_CODES:
                continue
            if ctype in DED_CAT_TYPES or ccode in DED_CAT_CODES or amt < 0:
                deductions.append(row)
                ded_total += abs(amt)
            else:
                earnings.append(row)
        if not gross:
            gross = sum(e['amount'] for e in earnings)
        if not net:
            net = gross - ded_total
        # Bridge = whatever separates (gross − deductions) from net: the advance
        # already paid (END) or the part held back for end-of-month (MID). Showing
        # it as an explicit reduction makes the hero reconcile on every cycle.
        bridge = round(gross - ded_total - net)
        advance = abs(bridge) if abs(bridge) > 1 else 0.0
        if not advance:
            advance_label = ''
        elif has_end_adv:
            advance_label = 'Mid-month advance (paid in cycle 1)'
        elif has_mid_adv:
            advance_label = 'Held back for end of month'
        else:
            advance_label = 'Advance / adjustment'

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
            'advance': advance,
            'advance_label': advance_label,
            'earnings': earnings,
            'deductions': deductions,
            'employer': employer,
            'employer_total': emp_total,
            'worked': worked,
        }
