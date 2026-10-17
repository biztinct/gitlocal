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
                 'line_ids.pay_role', 'line_ids.component_detail',
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

    @staticmethod
    def _pb_fold_subtotals(rows):
        """Split a bucket into what an employee reads and what it adds up to.

        `detail` rows are the components themselves; the rest are either
        subtotals OF those components or stand-alone amounts that sit outside
        them. The TOTAL is the non-detail rows — that is what `component_detail`
        means and what the pay run header counts.

        The LIST is the other way round: a payslip that shows both "Actual gross
        salary ₫8,000,000" and "Total monthly income ₫9,100,000" and then a gross
        of ₫9,100,000 reads as if a line went missing. So the one non-detail row
        that exactly equals the sum of the detail rows is recognised as their
        subtotal and dropped from the list — it is already on screen as the
        Gross (or Deductions) figure. Every other row stays, and when nothing
        matches, nothing is hidden.
        """
        detail_sum = sum(r['amount'] for r in rows if r['detail'])
        outer = [r for r in rows if not r['detail']]
        # Every row folded into a total that is not itself on the payslip leaves
        # nothing to count. That is a mis-flagged scheme, not a payslip of zero:
        # count the components rather than print ₫0.
        total = sum(r['amount'] for r in outer) if outer else detail_sum
        listed = rows
        if detail_sum:
            folded = [r for r in outer if round(r['amount']) == round(detail_sum)]
            if len(folded) == 1:
                listed = [r for r in rows if r is not folded[0]]
        return listed, total

    def _pb_build_statement(self):
        self.ensure_one()
        emp = self.employee_id
        company = self.company_id or self.env.company
        # SCHEMECTX P1 — the payslip is written in the money its own scheme
        # pays in. The company's is the answer only for a slip with no scheme
        # behind it, which is what this always was.
        cur = False
        config = getattr(self, 'formula_config_id', False)
        if config and getattr(config, 'currency_id', False):
            cur = config.currency_id
        cur = cur or company.currency_id

        # Line-level statement. Lines are bucketed by their salary-rule category
        # (type/code), NOT just by sign, so:
        #   * employee deductions (insurance / tax / loan) reduce take-home,
        #   * EMPLOYER contributions (employer SI/HI/UI, trade-union fund) are kept
        #     OUT of the employee's gross/deductions/net (shown separately),
        #   * the mid-cycle advance is shown as a reduction so the figures
        #     reconcile: Gross − Deductions − Advance = Net (on every cycle).
        earnings, deductions, employer = [], [], []
        gross = net = 0.0
        has_end_adv = has_mid_adv = False
        # A scheme built from a workbook carries its own subtotals as ordinary
        # components: "Total monthly income" sits on the payslip next to the
        # base salary and the allowances it is the sum OF. `component_detail`
        # is the flag that says "this amount is already inside another line's
        # total"; the pay run header has skipped those rows since VALUEKIND P5
        # and this statement never did — so it added every leaf on top of its
        # own subtotal and printed a gross of ₫34.4m against a true ₫9.1m.
        # Totals now count the same rows the run header counts.
        for line in self.line_ids:
            cat = line.category_id
            code = (line.code or '').upper()
            ccode = (cat.code or '').upper()
            ctype = (cat.category_type or '') if (cat and 'category_type' in cat._fields) else ''
            # VALUEKIND P5 — the scheme's own answer, stamped on the line when
            # the payslip was computed, outranks the salary-rule category.
            #
            # This was the LAST consumer reading the category, and it is the one
            # an employee actually sees. On the reference tenant every category
            # is typed `allowance` — `ctype` matched nothing, and the statement
            # bucketed correctly only because the category CODES happened to be
            # right and each branch had a code fallback. That is a payslip that
            # is correct by luck. `pay_role` is maintained on a screen people
            # can reach, and it is what the pay run header and the Analytics
            # Explorer already count.
            #
            # The category stays as the fallback, untouched, for lines written
            # before the stamp existed — so no historical payslip re-buckets.
            role = getattr(line, 'pay_role', False) or ''
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
                if role == 'net' or ctype == 'net' or ccode in NET_CODES:
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
            row = {'name': label, 'code': line.code or '', 'amount': abs(amt),
                   'detail': bool(getattr(line, 'component_detail', False))}
            # A component counted in hours or days, or one the scheme calls
            # information, is not money and belongs in none of these three
            # buckets. Before P5 such a component could carry `earning` and was
            # kept out of the totals by the Subtotal flag alone.
            if role == 'info':
                continue
            # Employer cost — informational only, never in gross/deductions/net.
            if role == 'employer_cost' or (
                    not role and (ctype == EMPLOYER_CAT_TYPE
                                  or ccode in EMPLOYER_CAT_CODES)):
                employer.append(row)
                continue
            # The scheme's own net-pay component. It is not an earning, and it
            # is the ANSWER for take-home: reading it here means the hero no
            # longer has to infer net from gross − deductions, which is how a
            # mis-typed subtotal turned ₫8,190,000 of take-home into −₫149.5m.
            # Only a non-detail one — a scheme can carry an intermediate net
            # (`Net Income VND`) that is folded into the real one.
            if role == 'net' or (not role and (ctype == 'net' or ccode in NET_CODES)):
                if not row['detail'] and not net:
                    net = amt
                continue
            # `amt < 0` stays unconditional. A line the scheme calls an earning
            # but which came out negative is a correction that REDUCES pay;
            # filing it under earnings would print it as a positive one, since
            # the row carries `abs(amt)`.
            if role == 'deduction' or amt < 0 or (
                    not role and (ctype in DED_CAT_TYPES
                                  or ccode in DED_CAT_CODES)):
                deductions.append(row)
            else:
                earnings.append(row)

        # Totals count only the rows that are not already inside another line's
        # total — the same rule as the pay run header (`_pb_bucket_sql`).
        earnings, earn_total = self._pb_fold_subtotals(earnings)
        deductions, ded_total = self._pb_fold_subtotals(deductions)
        employer, emp_total = self._pb_fold_subtotals(employer)
        if not gross:
            gross = earn_total
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
