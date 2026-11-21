# -*- coding: utf-8 -*-
"""Nothing silent — the pay run tells you (WDGAP PR-B §5).

Loans add to the run's ONE "Need review" answer (`hr.payslip.run.
pb_review_flags`, `pb_payslip_review/models/review_flags.py`), so the Run
lens's review step and Pay Run › Payslips count the same payslips:

  * a payslip that owed an instalment and could not take it — the scheme has
    no pay item for loan repayments, the loan is in another currency, or the
    pay data file carried a different amount for that pay item;
  * a payslip whose instalment was CUT so take-home is not below zero (WDGAP
    PR-E, E3): "Loan instalment cut from 1,200,000 to 450,000 so take-home is
    not below zero · 6,750,000 left" (several loans: the newest is cut first,
    and the sentence says so);
  * a payslip whose take-home is still below zero with an instalment in it
    (only when something else than the loan pushes it there after the cut):
    "Loan instalment is more than this month's take-home", as before.

Every payslip that took an instalment also carries `loan_note`
("Loan instalment ₫1,200,000 taken · ₫6,000,000 left"), and the run answers
`pb_loan_notes()` — "3 people have a loan instalment due but this pay scheme
has no pay item for loan repayments" — for the Loans board.
"""
import json
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
            # the loan is WHY take-home is at or below zero (the generic
            # "zero or below" reason is then replaced by the loan's own words)
            loan_is_reason = False
            issue = slip.pb_loan_issue
            if issue:
                reasons.append(self._pb_loan_issue_reason(issue))
            mine = by_slip.get(slip.id) or []
            cut = self._pb_loan_cut_words(slip, mine)
            if cut:
                row['loan_cut'] = True
                row['loan_planned'] = cut['planned']
                row['loan_taken'] = cut['taken']
                row['loan_left'] = cut['left']
                row['loan_note'] = cut['sentence']
                reasons.append(cut['sentence'])
                net = row.get('net')
                if net is None or float_compare(
                        net, 0.0, precision_rounding=cut['currency'].rounding) >= 0:
                    loan_is_reason = True
            if mine and not cut:
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
            if mine:
                currency = mine[0].loan_id.currency_id
                net = row.get('net')
                if net is not None and float_compare(
                        net, 0.0, precision_rounding=currency.rounding) < 0:
                    # take-home before the instalment = net + instalment, and
                    # the instalment is more than that exactly when net < 0
                    # (after a cut: only when something else pushes it there)
                    reasons.append(_("Loan instalment is more than this month's "
                                     "take-home"))
                    loan_is_reason = True
            if not reasons:
                continue
            if row.get('flag') and row.get('kind') == 'zero' and loan_is_reason:
                # the loan IS the reason take-home is below zero: say so —
                # but keep what other modules appended after the zero reason
                # (WDGAP PR merge: PR-C's "Pay on hold" rides as " · …")
                base = row.get('reason') or ''
                row['reason'] = base.split(' · ', 1)[1] if ' · ' in base else ''
            joined = ' · '.join(r for r in [row.get('reason') or ''] + reasons if r)
            row.update(flag=True, reason=joined,
                       kind=row.get('kind') if row.get('flag') and row.get('kind') else 'loan')

    def _pb_loan_cut_words(self, slip, mine):
        """What the take-home floor did on this payslip, in words, or None.

        `{'planned', 'taken', 'left', 'sentence', 'currency'}` — read from the
        payslip's own record of the cut (`pb_loan_cut`)."""
        raw = slip.pb_loan_cut if 'pb_loan_cut' in slip._fields else False
        if not raw:
            return None
        try:
            cut = json.loads(raw)
        except (TypeError, ValueError):
            return None
        planned = cut.get('planned') or {}
        taken = cut.get('taken') or {}
        Loan = self.env['pb.loan'].sudo()
        loans = Loan.browse([int(k) for k in planned]).exists()
        if not loans:
            return None
        currency = loans[:1].currency_id
        line_ids = {line.id for line in mine}
        left = 0.0
        for loan in loans:
            paid_other = sum(x.amount for x in loan.repayment_ids
                             if x.state == 'paid' and x.id not in line_ids)
            left += max((loan.amount or 0.0) - paid_other
                        - float(taken.get(str(loan.id)) or 0.0), 0.0)
        planned_total = currency.round(sum(float(v) for v in planned.values()))
        taken_total = currency.round(sum(float(v) for v in taken.values()))
        left = currency.round(left)
        sentence = _("Loan instalment cut from %(planned)s to %(taken)s so "
                     "take-home is not below zero · %(left)s left",
                     planned=Loan._money(planned_total, currency),
                     taken=Loan._money(taken_total, currency),
                     left=Loan._money(left, currency))
        if len(loans) > 1:
            sentence = '%s %s' % (sentence, _("(newest loan cut first)"))
        return {'planned': planned_total, 'taken': taken_total, 'left': left,
                'sentence': sentence, 'currency': currency}

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
