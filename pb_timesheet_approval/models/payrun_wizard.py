# -*- coding: utf-8 -*-
"""Unapproved weeks, on the pay run that is about to pay for them.

ADVISORY BY DEFAULT, exactly like `pb_close`'s unclosed-week lines and for the
same reason: a week nobody signed off is a PROCESS problem for HR, and refusing
to pay people over it is a position the payroll engine has no business taking
on its own. A company that does want that position has a switch for it
(`Block the run until every week is approved`), and then the refusal is the
business's choice rather than the software's.

Everything after `super()` is inside a try/except, and the block — the one
thing here that can stop a run — is raised deliberately and named.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: A period is a month; more than this many lines help nobody.
_MAX_ROWS = 8


class PbPayrunWizardTimesheets(models.AbstractModel):
    _inherit = 'pb.payrun.wizard'

    def _timesheet_append_exceptions(self, exceptions, emp_ids, ds, de):
        """Append one advisory row per person-week nobody has approved."""
        company = self.env.company
        if not company.pb_timesheet_payroll:
            return exceptions
        rows = self.env['pb.timesheet.packet'].weeks_missing_approval(
            emp_ids, ds, de, limit=200)
        if not rows:
            return exceptions
        lines = []
        for row in rows[:_MAX_ROWS]:
            if row['state'] == 'pending':
                why = _("The week of %(week)s is still waiting for its "
                        "approval.", week=row['week_label'])
            elif row['state'] == 'returned':
                why = _("The week of %(week)s was sent back and has not been "
                        "sent in again.", week=row['week_label'])
            else:
                why = _("The week of %(week)s has not been sent in for "
                        "approval.", week=row['week_label'])
            lines.append({'emp': row['employee'], 'why': why})
        if company.pb_timesheet_block_run:
            lines.append({
                'emp': _("Weekly timesheets"),
                'why': _("%(n)s week(s) in this period have not been approved. "
                         "This company does not allow a run on hours that have "
                         "not been signed off.", n=len(rows)),
            })
        else:
            lines.append({
                'emp': _("Weekly timesheets"),
                'why': _("%(n)s week(s) in this period have not been approved. "
                         "The run still computes — this is a note, not a "
                         "block.", n=len(rows)),
            })
        seen = {(r.get('emp'), r.get('why')) for r in exceptions}
        exceptions.extend(line for line in lines
                          if (line['emp'], line['why']) not in seen)
        return exceptions

    def _timesheet_require_approved(self, emp_ids, ds, de):
        """The refusal, when the company asked for one."""
        company = self.env.company
        if not (company.pb_timesheet_payroll
                and company.pb_timesheet_block_run):
            return
        rows = self.env['pb.timesheet.packet'].weeks_missing_approval(
            emp_ids, ds, de, limit=5)
        if not rows:
            return
        named = '; '.join('%s — %s' % (r['employee'], r['week_label'])
                          for r in rows)
        raise UserError(_(
            "This pay run cannot be computed yet: some weeks in the period "
            "have not been approved.\n\n%(who)s\n\nApprove those weeks, or "
            "turn off “Block the run until every week is approved” in the "
            "company settings.", who=named))

    # ------------------------------------------------------------- the seams
    @api.model
    def create_and_compute(self, vals):
        # The refusal has to be asked BEFORE the run exists, and at that moment
        # the only list of people is the one the wizard itself is about to
        # compute for — the same `_eligible_employees()` the body uses.
        emp_ids = list(vals.get('emp_ids') or [])
        if not emp_ids:
            try:
                emp_ids = list(self._eligible_employees() or [])
            except Exception:   # noqa: BLE001
                emp_ids = []
        self._timesheet_require_approved(emp_ids, vals.get('date_start'),
                                         vals.get('date_end'))
        result = super().create_and_compute(vals)
        try:
            if (isinstance(result, dict) and 'exceptions' in result
                    and not result.get('needs_confirmation')):
                run_id = result.get('run_id')
                if run_id:
                    run = self.env['hr.payslip.run'].sudo().browse(run_id)
                    emp_ids = run.slip_ids.mapped('employee_id').ids
                self._timesheet_append_exceptions(
                    result['exceptions'], emp_ids, vals.get('date_start'),
                    vals.get('date_end'))
        except UserError:
            raise
        except Exception:       # noqa: BLE001 — an advisory never stops a run
            _logger.exception('weekly timesheet advisory: create_and_compute')
        return result

    @api.model
    def compute_batch(self, payload):
        self._timesheet_require_approved(payload.get('emp_ids') or [],
                                         payload.get('date_start'),
                                         payload.get('date_end'))
        result = super().compute_batch(payload)
        try:
            if isinstance(result, dict) and 'exceptions' in result:
                self._timesheet_append_exceptions(
                    result['exceptions'], payload.get('emp_ids') or [],
                    payload.get('date_start'), payload.get('date_end'))
        except UserError:
            raise
        except Exception:       # noqa: BLE001
            _logger.exception('weekly timesheet advisory: compute_batch')
        return result
