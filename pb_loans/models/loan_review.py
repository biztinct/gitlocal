# -*- coding: utf-8 -*-
"""Nothing silent — the pay run tells you (WDGAP PR-B §5).

Loans add to the run's ONE "Need review" answer (`hr.payslip.run.
pb_review_flags`, `pb_payslip_review/models/review_flags.py`), so the Run
lens's review step and Pay Run › Payslips count the same payslips:

  * a payslip that owed an instalment and could not take it — the scheme has
    no pay item for loan repayments, the loan is in another currency, or the
    pay data file carried a different amount for that pay item;
  * a payslip whose instalment is more than the person's take-home before it
    (the take-home after it is below zero). The amount is NOT changed — a net
    pay floor is a later phase.

Every payslip that took an instalment also carries `loan_note`
("Loan instalment ₫1,200,000 taken · ₫6,000,000 left"), and the run answers
`pb_loan_notes()` — "3 people have a loan instalment due but this pay scheme
has no pay item for loan repayments" — for the Loans board.
"""
import logging

from odoo import _, api, models
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class HrPayslipRunLoanFlags(models.Model):
    _inherit = 'hr.payslip.run'

    def pb_review_flags(self, slip_ids=None):
        out = super().pb_review_flags(slip_ids=slip_ids)
        try:
            self._pb_loans_flags(out)
        except Exception:       # noqa: BLE001 — a flag never breaks a screen
            _logger.exception('pb_loans: review flags failed on run %s', self.id)
        return out

    @api.model
    def _pb_loan_issue_reason(self, issue):
        return {
            'no_item': _("Loan instalment due, but this pay scheme has no pay item "
                         "for loan repayments"),
            'currency': _("Loan instalment due, but the loan is in another "
                          "currency than this pay scheme"),
            'other_source': _("Loan instalment not taken: the pay data file has "
                              "another amount for loan repayments"),
            'error': _("Loan instalment could not be applied"),
        }.get(issue, '')

    def _pb_loans_flags(self, out):
        if not out:
            return
        Slip = self.env['hr.payslip'].sudo()
        slips = Slip.browse(list(out)).exists()
        Line = self.env['pb.loan.repayment'].sudo()
        lines = Line.search([('payslip_id', 'in', slips.ids), ('kind', '=', 'payroll'),
                             ('state', 'in', ('reserved', 'paid'))])
        by_slip = {}
        for line in lines:
            by_slip.setdefault(line.payslip_id.id, []).append(line)
        for slip in slips:
            row = out.get(slip.id)
            if row is None or slip.state == 'cancel':
                continue
            reasons = []
            issue = slip.pb_loan_issue
            if issue:
                reasons.append(self._pb_loan_issue_reason(issue))
            mine = by_slip.get(slip.id) or []
            if mine:
                currency = mine[0].loan_id.currency_id
                taken = currency.round(sum(l.amount for l in mine))
                left = 0.0
                for line in mine:
                    loan = line.loan_id
                    paid_other = sum(x.amount for x in loan.repayment_ids
                                     if x.state == 'paid' and x.id != line.id)
                    left += max((loan.amount or 0.0) - paid_other - line.amount, 0.0)
                Loan = self.env['pb.loan']
                row['loan_taken'] = taken
                row['loan_left'] = currency.round(left)
                row['loan_note'] = _("Loan instalment %(taken)s taken · %(left)s left",
                                     taken=Loan._money(taken, currency),
                                     left=Loan._money(left, currency))
                net = row.get('net')
                if net is not None and float_compare(
                        net, 0.0, precision_rounding=currency.rounding) < 0:
                    # take-home before the instalment = net + instalment, and
                    # the instalment is more than that exactly when net < 0
                    reasons.append(_("Loan instalment is more than this month's "
                                     "take-home"))
            if not reasons:
                continue
            if row.get('flag') and row.get('kind') == 'zero' and any(
                    'take-home' in r for r in reasons):
                # the loan IS the reason take-home is below zero: say so
                row['reason'] = ''
            joined = ' · '.join(r for r in [row.get('reason') or ''] + reasons if r)
            row.update(flag=True, reason=joined,
                       kind=row.get('kind') if row.get('flag') and row.get('kind') else 'loan')

    def pb_loan_notes(self):
        """`[sentence]` — what this run did not take, by reason, in words."""
        self.ensure_one()
        slips = self.slip_ids.filtered(lambda s: s.state != 'cancel' and s.pb_loan_issue)
        out = []
        for issue in ('no_item', 'currency', 'other_source', 'error'):
            n = len(slips.filtered(lambda s: s.pb_loan_issue == issue))
            if not n:
                continue
            if issue == 'no_item':
                out.append(_("1 person has a loan instalment due but this pay scheme "
                             "has no pay item for loan repayments.") if n == 1 else
                           _("%s people have a loan instalment due but this pay "
                             "scheme has no pay item for loan repayments.", n))
            elif issue == 'currency':
                out.append(_("1 person has a loan in another currency than this pay "
                             "scheme, so nothing was taken.") if n == 1 else
                           _("%s people have a loan in another currency than this "
                             "pay scheme, so nothing was taken.", n))
            elif issue == 'other_source':
                out.append(_("1 person's pay data file has another amount for loan "
                             "repayments, so the instalment was not taken.") if n == 1
                           else _("%s people's pay data file has another amount for "
                                  "loan repayments, so the instalment was not taken.", n))
            else:
                out.append(_("1 loan instalment could not be applied.") if n == 1 else
                           _("%s loan instalments could not be applied.", n))
        return out


class PbPayslipReviewLoans(models.AbstractModel):
    _inherit = 'pb.payslip.review'

    @api.model
    def get_slip_detail(self, slip_id):
        answer = super().get_slip_detail(slip_id)
        try:
            slip = self.env['hr.payslip'].browse(int(slip_id or 0)).exists()
            if slip and isinstance(answer, dict) and slip.payslip_run_id:
                row = slip.payslip_run_id.sudo().pb_review_flags([slip.id]).get(slip.id) or {}
                answer['loan_note'] = row.get('loan_note') or ''
        except Exception:       # noqa: BLE001
            _logger.exception('pb_loans: slip detail note failed for %s', slip_id)
        return answer
