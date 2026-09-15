# -*- coding: utf-8 -*-
"""Reopening a closed day is taking the week back after everybody signed it.

WHAT WAS TRUE BEFORE. A closed day is the statement "these hours are final".
Reopening one let somebody edit attendance that a pay run may already have
been built on. The lock model asked for an attendance or payroll MANAGER; the
Close cockpit's bulk door asked only for an OFFICER — so the cheaper of the
two doors was the one that gave the wider right.

WHAT IS TRUE NOW. Both doors ask for the manager permission, and both write a
proposal (`pb.unlock.proposal`). The day is reopened when the route says yes —
by the approver, who must hold the same permission. Closing a day is not held:
locking is the safe direction.

THE REASON WAS ALREADY REQUIRED AND STILL IS. It travels on the proposal and
lands on the day's own record when the reopen happens, exactly as before, so
the chatter note a reviewer reads is unchanged.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

UNLOCK_PROCESS_KEY = 'unlock'

#: What reopening a day has always needed on the lock model — and what the
#: cockpit's bulk door asked for instead until this phase.
UNLOCK_GROUPS = ('hr_attendance.group_hr_attendance_manager',
                 'om_hr_payroll.group_hr_payroll_manager')

#: "This write IS the approved reopen."
UNLOCK_WRITE = 'pb_unlock_approved_write'


class PbUnlockProposal(models.Model):
    _name = 'pb.unlock.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed reopen of a closed day'

    _approval_process_key = UNLOCK_PROCESS_KEY
    _proposal_prefix = 'UNL'
    _proposal_gate_groups = UNLOCK_GROUPS
    _proposal_kind_labels = {'unlock': 'Reopen closed days'}
    _proposal_fact_specs = {
        'days': {'type': 'int', 'label': 'Days being reopened'},
        'days_in_closed_payroll': {
            'type': 'bool', 'label': 'Some are in a finished pay run'},
    }

    def _live_snapshot(self):
        """Which of those days are still closed, right now."""
        self.ensure_one()
        payload = self.payload()
        Lock = self.env.get('pb.wf.lock')
        if Lock is None:
            return {}
        locked = Lock.sudo().search([
            ('company_id', '=', (self.company_id or self.env.company).id),
            ('date', 'in', payload.get('days') or []),
            ('state', '=', 'locked')])
        return {'still_closed': len(locked)}

    def _apply_unlock(self):
        payload = self.payload()
        company_id = (self.company_id or self.env.company).id
        Lock = self.env['pb.wf.lock'].with_context(**{UNLOCK_WRITE: True})
        done = []
        for day in payload.get('days') or []:
            if Lock.unlock_day(company_id, day, payload.get('reason')):
                done.append(day)
        if not done:
            raise UserError(_(
                "None of those days is closed any more, so there was nothing "
                "to reopen."))
        return {'unlocked': done}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(
            company, 'payroll_mgr',
            ('om_hr_payroll.group_hr_payroll_manager',
             'hr_attendance.group_hr_attendance_manager'))
        return Seed.lay(
            company, UNLOCK_PROCESS_KEY, 'Reopening closed days',
            route(role_step(_('Payroll manager'), 'payroll_mgr')),
            binding_note='The route reopening a day everybody had signed off '
                         'follows.',
            model_name='pb.unlock.proposal',
            role_keys=('payroll_mgr',),
            reason='Set up when reopen approvals were switched on')


class ResCompanyUnlockSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.unlock.proposal']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('unlock: %s has no route yet', company.name)
        return companies


def propose_unlock(env, days, reason):
    """Write the reopen down and ask. None means "carry on and reopen".

    THE REASON IS REFUSED HERE, NOT ONLY IN `unlock_day`. Two doors reach a
    reopen — the lock model itself and the Close cockpit's bulk button — and
    the cockpit's one used to get its refusal for free, because it looped
    through the lock model. Now that it proposes instead, a rail that lived
    only in `unlock_day` would have been silently dropped on that path: the
    proposal would be written, applied, refused INSIDE the apply, and the
    refusal recorded on a request rather than raised at the person who typed
    nothing. The rule belongs to the proposal, which is what both doors share.
    """
    if env.context.get(UNLOCK_WRITE) or 'pb.unlock.proposal' not in env:
        return None
    days = [str(d) for d in (days or [])]
    if not days:
        return None
    reason = (reason or '').strip()
    if not reason:
        raise UserError(_(
            "Reopening a closed day needs a reason — it is the only account "
            "anyone reviewing this payroll will have of why the week was "
            "taken back."))
    return env['pb.unlock.proposal'].propose(
        'unlock',
        _("Reopen %s closed day(s)", len(days)),
        payload={'days': days, 'reason': reason},
        snapshot={'still_closed': len(days)},
        facts={'days': {'value': len(days), 'unit': ''},
               'days_in_closed_payroll': {
                   'value': _in_finished_run(env, days), 'unit': ''}},
        note=reason,
    ).answer()


def _in_finished_run(env, days):
    """Does a finished pay run already cover one of these days?"""
    Slip = env.get('hr.payslip')
    if Slip is None or not days:
        return False
    return bool(Slip.sudo().search_count([
        ('state', '=', 'done'),
        ('date_from', '<=', max(days)),
        ('date_to', '>=', min(days)),
    ]))


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.unlock.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('unlock: %s has no route yet', company.name)
    return done


def post_init_hook(env):
    seed_all(env)
