# -*- coding: utf-8 -*-
"""Reopening a closed pay month is undoing everybody's sign-off.

WHAT WAS TRUE BEFORE. A closed month says "no more changes to this period".
Reopening one was one press with no reason and no record of who did it —
while pay runs, filings and bank files built on that month already existed.

WHAT IS TRUE NOW. Closing stays immediate; locking is the safe direction.
REOPENING needs a reason, writes a proposal (`pb.month.proposal`) and happens
when the route says yes. The route can read how many pay runs were already
finished in that month, which is the fact that usually decides the answer.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

MONTH_PROCESS_KEY = 'month'

#: What reopening a month has always needed.
MONTH_GROUP = 'om_hr_payroll.group_hr_payroll_manager'

#: "This write IS the approved reopen."
MONTH_WRITE = 'pb_month_approved_write'


class PbMonthProposal(models.Model):
    _name = 'pb.month.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed reopen of a pay month'

    _approval_process_key = MONTH_PROCESS_KEY
    _proposal_prefix = 'MON'
    _proposal_gate_groups = (MONTH_GROUP,)
    _proposal_kind_labels = {'reopen': 'Reopen a closed pay month'}
    _proposal_fact_specs = {
        'month': {'type': 'char', 'label': 'Which month'},
        'runs_done_in_month': {'type': 'int',
                               'label': 'Pay runs already finished'},
    }

    def _target(self):
        self.ensure_one()
        if not self.target_model or not self.target_id \
                or self.target_model not in self.env:
            return None
        record = self.env[self.target_model].sudo().browse(
            self.target_id).exists()
        return record or None

    def _live_snapshot(self):
        self.ensure_one()
        target = self._target()
        return {'state': target.state} if target is not None else {}

    def _apply_reopen(self):
        target = self._target()
        if not target:
            raise UserError(_("That month is no longer in the calendar."))
        if target.state != 'closed':
            raise UserError(_("That month is already open."))
        target.with_context(**{MONTH_WRITE: True}).action_reopen()
        target.message_post(body=_(
            "Reopened after approval %(ref)s. Reason: %(why)s",
            ref=self.name, why=self.note or _('none given')))
        return {'calendar_id': target.id, 'state': target.state}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(
            company, 'payroll_mgr',
            ('om_hr_payroll.group_hr_payroll_manager',))
        return Seed.lay(
            company, MONTH_PROCESS_KEY, 'Reopening a pay month',
            route(role_step(_('Payroll manager'), 'payroll_mgr')),
            binding_note='The route reopening a month everybody had closed '
                         'follows.',
            model_name='pb.month.proposal',
            role_keys=('payroll_mgr',),
            reason='Set up when month approvals were switched on')


class ResCompanyMonthSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.month.proposal']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('month: %s has no route yet', company.name)
        return companies


def propose_reopen(calendar, reason=''):
    """Write the reopen down and ask. None means "carry on and reopen"."""
    env = calendar.env
    if env.context.get(MONTH_WRITE) or 'pb.month.proposal' not in env:
        return None
    if calendar.state != 'closed':
        return None
    reason = (reason or '').strip()
    if not reason:
        # A dead end is worse than a refusal, so this says where to go: the
        # form's own button has nowhere to type a reason, and the pay
        # calendar screen asks for one.
        raise UserError(_(
            "Reopening a closed month needs a reason — it is the only "
            "account anybody reviewing this payroll will have of why the "
            "month was taken back. Reopen it from the Pay calendar screen, "
            "which asks for one."))
    Slip = env.get('hr.payslip')
    runs = 0
    if Slip is not None and calendar.pay_date:
        runs = Slip.sudo().search_count([
            ('state', '=', 'done'),
            ('date_from', '<=', calendar.pay_date),
            ('date_to', '>=', calendar.cutoff_date or calendar.pay_date),
        ])
    return env['pb.month.proposal'].propose(
        'reopen',
        _("Reopen %s", calendar.display_name or ''),
        payload={'calendar_id': calendar.id},
        snapshot={'state': calendar.state},
        facts={'month': {'value': str(calendar.display_name or ''),
                         'unit': ''},
               'runs_done_in_month': {'value': runs, 'unit': ''}},
        target=calendar,
        note=reason,
    ).answer()


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.month.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('month: %s has no route yet', company.name)
    return done
