# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Gate 5 (ADVISORY) — young-worker warnings on the payroll run.

Wraps the base pb.payrun.wizard seams (create_and_compute + compute_batch),
calls super(), then APPENDS young-worker violations to the returned `exceptions`
list — the same surface the Run Payroll cockpit already renders. It NEVER raises
and NEVER skips a slip: a violating minor is still paid (labor-law remediation is
HR's job, not the payroll engine's).

HOW THIS REACHES A RUN — TWO PATHS, ONLY ONE OF THEM THIS SEAM (corrected P7)
-----------------------------------------------------------------------------
The GENERIC (salary-structure) path calls super all the way down, so the append
above fires and the warnings arrive. That is the whole mechanism there.

The DEMO DIVISION path does not. `pb_demo` replaces `create_and_compute` /
`compute_batch` for a division run and returns WITHOUT calling super, so every
wrapper below it — this one included — is skipped.

This docstring used to claim that was handled: "this wrapper must sit OUTSIDE
pb_demo's override in the MRO. Load order guarantees that (pb_young_worker
resolves after pb_demo); test 9 verifies". All three clauses were wrong.
Measured on the live registry the order is the OPPOSITE
(`pb_demo -> pb_close -> pb_young_worker -> pb_payrun_wizard`) — none of these
four modules depends on another, so their relative order is Odoo's
`(depth, name)` accident and pb_demo simply loads last. And "test 9" asserted
the false claim behind an `if pb_demo is installed` guard, on CI databases
where pb_demo is not, so it could never fail.

What actually covers the division path is P4's fix, and it runs in the other
direction: `pb_demo._pb_demo_advisories` calls `_yw_append_exceptions` (and
pb_close's twin) BY NAME. The demo module depends on the product, never the
reverse — making `pb_close` or this module depend on `pb_demo` to be correct
would be a far worse bargain than an explicit hook list. `test_09c` drives that
hook and asserts our rows come out of it.

The append is wrapped defensively so a check failure can never break a payroll
run — asserted by injection in `test_09d`, not assumed.
"""

import logging

from odoo import api, models, _

_logger = logging.getLogger(__name__)

# per-employee cap on appended rows so a bad week doesn't flood the review step
_MAX_ROWS_PER_EMP = 3


class PbPayrunWizardYoungWorker(models.AbstractModel):
    _inherit = 'pb.payrun.wizard'

    def _yw_append_exceptions(self, exceptions, emp_ids, ds, de):
        """Append young-worker rows to `exceptions` (mutated in place)."""
        if not emp_ids or not ds or not de:
            return exceptions
        try:
            emps = self.env['hr.employee'].sudo().browse(emp_ids).exists()
            # no_birthday is a cockpit data-quality task, not a payroll warning —
            # excluded here so a 4.5k run isn't flooded with birthday-less rows
            viols = self.env['pb.young.worker'].check_period(
                emps, ds, de, include_no_birthday=False)
        except Exception:
            _logger.exception("young-worker payroll gate: check_period failed")
            return exceptions
        by_emp = {}
        for v in viols:
            by_emp.setdefault(v['employee_id'], []).append(v)
        for eid, vs in by_emp.items():
            name = vs[0]['name']
            for v in vs[:_MAX_ROWS_PER_EMP]:
                exceptions.append({'emp': name, 'why': _("Young worker: %s") % v['detail']})
            if len(vs) > _MAX_ROWS_PER_EMP:
                exceptions.append({
                    'emp': name,
                    'why': _("Young worker: …and %s more") % (len(vs) - _MAX_ROWS_PER_EMP),
                })
        return exceptions

    @api.model
    def create_and_compute(self, vals):
        result = super().create_and_compute(vals)
        try:
            if (isinstance(result, dict) and 'exceptions' in result
                    and not result.get('needs_confirmation')):
                emp_ids = []
                run_id = result.get('run_id')
                if run_id:
                    run = self.env['hr.payslip.run'].sudo().browse(run_id)
                    emp_ids = run.slip_ids.mapped('employee_id').ids
                self._yw_append_exceptions(
                    result['exceptions'], emp_ids,
                    vals.get('date_start'), vals.get('date_end'))
        except Exception:
            _logger.exception("young-worker payroll gate: create_and_compute")
        return result

    @api.model
    def compute_batch(self, payload):
        result = super().compute_batch(payload)
        try:
            if isinstance(result, dict) and 'exceptions' in result:
                self._yw_append_exceptions(
                    result['exceptions'], payload.get('emp_ids') or [],
                    payload.get('date_start'), payload.get('date_end'))
        except Exception:
            _logger.exception("young-worker payroll gate: compute_batch")
        return result
