"""Keep genuine deduction refunds without changing legacy sign conventions."""
from odoo import models


def uses_signed_deductions(gross, net, signed, magnitude, explicit, has_gross, has_net):
    """Use signed deductions only when they reconcile this whole payslip.

    Older schemes mix negative insurance charges with positive advances. Their
    magnitudes remain authoritative. A classified refund is different: its
    signed amount reconciles gross to net while its magnitude does not.
    Decide per payslip so the two conventions can coexist in the same run.
    """
    return bool(explicit and has_gross and has_net
                and abs(gross - signed - net) < .01
                and abs(signed - magnitude) >= .01)


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    def pb_pay_totals(self):
        result = dict(gross=0.0, deductions=0.0, net=0.0, employer_cost=0.0)
        for slip in self.mapped('slip_id'):
            selected = self.filtered(lambda line: line.slip_id == slip)
            whole = slip.line_ids
            baseline = super(HrPayslipLine, whole).pb_pay_totals()
            counted = whole.filtered(lambda line: line.pb_counts_in_totals())
            deductions = counted.filtered(lambda line: line.pb_pay_band() == 'DED')
            signed = sum(deductions.mapped('total'))
            apply_signed = uses_signed_deductions(
                baseline['gross'], baseline['net'], signed, baseline['deductions'],
                bool(deductions) and 'pay_role' in self._fields
                and all(line.pay_role == 'deduction' for line in deductions),
                any(line.pb_pay_band() in ('GROSS', 'BASIC', 'ALW') for line in counted),
                any(line.pb_pay_band() == 'NET' for line in counted))
            totals = super(HrPayslipLine, selected).pb_pay_totals()
            if apply_signed:
                totals['deductions'] = sum(line.total for line in selected
                    if line.pb_counts_in_totals() and line.pb_pay_band() == 'DED')
            for key, value in totals.items():
                result[key] += value
        return result
