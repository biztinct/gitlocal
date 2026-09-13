# -*- coding: utf-8 -*-
"""Fixing a punch is a request like any other — and a five-minute fix need not be.

WHAT WAS TRUE BEFORE. One rung: an attendance officer, or the person's own
line manager, said yes and the punch was corrected. Every correction cost the
same attention, whether it moved a clock-out by four minutes or invented a
whole shift.

WHAT IS TRUE NOW. The default route is "Their manager", and it carries the
condition the old ladder could not express: a correction worth **fifteen
minutes or more** goes to somebody, and a smaller one is applied at once and
recorded. A business that wants every minute checked deletes the condition; a
business that wants none sets the whole process to "No approval needed".

THE PUNCH IS CORRECTED AT THE END OF THE ROUTE, NOT AT THE FIRST YES. The old
Approve button applied the correction and then advanced the chain, which was
right when the chain was one rung long. Under a route of three it would have
written the punch on the first approver's press (ledger AM81), so the apply
moves to `_approval_apply` — the one thing the engine calls when the WHOLE
route has said yes.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, route,
)

_logger = logging.getLogger(__name__)

CORRECTION_PROCESS_KEY = 'correction'

#: Under this, a correction is applied as soon as it is filed and recorded.
SMALL_CORRECTION_MINUTES = 15

register_chain(
    'hr.attendance.correction', CORRECTION_PROCESS_KEY,
    submit_state='submitted',
    driven=('approved',),
    date_field='date',
)


class HrAttendanceCorrectionApproval(models.Model):
    _inherit = 'hr.attendance.correction'

    _approval_process_key = CORRECTION_PROCESS_KEY

    # ------------------------------------------------------------ the facts
    def _correction_minutes(self):
        """How much time this correction moves, in minutes.

        The one number a business actually wants to condition on: a punch four
        minutes out is a typo, and two hours is a claim.
        """
        self.ensure_one()
        punch = self.attendance_id
        if self.correction_type == 'delete':
            if punch and punch.check_in and punch.check_out:
                return int((punch.check_out - punch.check_in)
                           .total_seconds() // 60)
            return 0
        if self.correction_type == 'create':
            if self.new_check_in and self.new_check_out:
                return int((self.new_check_out - self.new_check_in)
                           .total_seconds() // 60)
            return 0
        minutes = 0
        if self.new_check_in and punch and punch.check_in:
            minutes += abs(int((self.new_check_in - punch.check_in)
                               .total_seconds() // 60))
        if self.new_check_out and punch and punch.check_out:
            minutes += abs(int((self.new_check_out - punch.check_out)
                               .total_seconds() // 60))
        return minutes

    def _chain_title(self):
        self.ensure_one()
        return _("Attendance fix · %(who)s · %(day)s",
                 who=self.employee_id.name or '', day=self.date or '')

    def _chain_facts(self):
        self.ensure_one()
        return {
            'minutes': {'value': self._correction_minutes(),
                        'unit': _('minutes')},
            'correction_type': {'value': self.correction_type or '',
                                'unit': ''},
            'from_exception': {'value': bool(self.exception_kind), 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'minutes': {'type': 'int', 'label': _('Minutes being changed')},
            'correction_type': {'type': 'selection',
                                'label': _('What kind of fix')},
            'from_exception': {'type': 'bool',
                               'label': _('Raised by the system itself')},
        }

    def _chain_kind_key(self):
        self.ensure_one()
        return self.correction_type or 'any'

    @api.model
    def _chain_kinds(self):
        return [{'key': 'create', 'label': _('A missing punch')},
                {'key': 'adjust', 'label': _('A time to move')},
                {'key': 'delete', 'label': _('A punch to remove')}]

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [{'label': _('Day'), 'value': str(self.date or '')},
                 {'label': _('Minutes'),
                  'value': str(self._correction_minutes())}]
        if self.new_check_in:
            chips.append({'label': _('New check-in'),
                          'value': str(self.new_check_in)})
        if self.new_check_out:
            chips.append({'label': _('New check-out'),
                          'value': str(self.new_check_out)})
        return {'title': _('The fix'), 'columns': [], 'rows': [],
                'chips': chips, 'note': (self.reason or '')[:240]}

    # ------------------------------------------------------- the one button
    def action_approve(self):
        """One press = one decision on the live route (or the old ladder)."""
        managed = self.filtered(
            lambda r: r._chain_spec() and r._engine_managed()
            and r._chain_open_request())
        for rec in managed:
            rec._chain_decide('approve')
        rest = self - managed
        if rest:
            return super(HrAttendanceCorrectionApproval, rest).action_approve()
        return True

    def _approval_apply(self, request):
        """The punch is written once, when the whole route has said yes."""
        self.ensure_one()
        if self.state == 'approved':
            return True
        try:
            with self.env.cr.savepoint():
                self._apply()
        except (ValidationError, UserError, AccessError) as exc:
            reason = (exc.args and exc.args[0]) or str(exc)
            # Deliberately raised rather than written: the engine runs this
            # inside its own savepoint, so anything written here would be
            # rolled back with the exception. The request keeps the approval
            # and says, in the approver's own inbox, why it could not be
            # carried out — which is the honest end of this path.
            raise UserError(_(
                "The correction was approved but could not be applied: %s",
                reason))
        return super()._approval_apply(request)

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        return self.env['biz.approval.seed'].lay(
            company, CORRECTION_PROCESS_KEY, 'Attendance corrections',
            route(manager_step(
                _('Their manager'),
                condition={'fact': 'minutes', 'op': 'gte',
                           'value': SMALL_CORRECTION_MINUTES})),
            binding_note='Anything worth a quarter of an hour or more goes to '
                         'the person\'s manager; a smaller fix is applied at '
                         'once and recorded.',
            model_name='hr.attendance.correction',
            reason='Set up when attendance approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['hr.attendance.correction']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_attendance_flow: %s has no correction route',
                              company.name)
    return done
