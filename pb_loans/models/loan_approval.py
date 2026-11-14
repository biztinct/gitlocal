# -*- coding: utf-8 -*-
"""A loan is money leaving the company, so it travels a real route.

Cloned from the awards adapter (`pb_comp_ben/models/incentive_approval.py`):
the chain shim drives `pb.loan.state` — sending in moves it to "Waiting for
approval", the whole route saying yes moves it to "Running". The default route
every company gets is ONE step, the Head of pay, filled from whoever holds the
payroll manager group today. The catalogue row (`data/approval_process.xml`)
is marked as money, so the one Approvals inbox never offers it for "approve
selected" (WDGAP QF1 `_can_bulk`).
"""
import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

LOAN_PROCESS_KEY = 'loan'

register_chain(
    'pb.loan', LOAN_PROCESS_KEY,
    submit_state='waiting',
    driven=('running',),
    amount_field='amount',
    # No date_field on purpose: the engine asks who holds a responsibility ON
    # that date, and a loan whose first pay month is behind a holder's start
    # date found nobody and blocked ("Nobody holds Head of pay"). A loan is
    # approved by whoever holds the seat today (ledger PRB-W1).
)


class PbLoanApproval(models.Model):
    _inherit = 'pb.loan'

    _approval_process_key = LOAN_PROCESS_KEY

    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'pay_head',
                                  ('pb_hr_payroll_base.group_payroll_base_manager',))
        return Seed.lay(
            company, LOAN_PROCESS_KEY, 'Loans and salary advances',
            route(role_step(_('Head of pay'), 'pay_head')),
            binding_note='The route every loan and salary advance follows '
                         'unless a part of the business is given its own.',
            model_name='pb.loan',
            role_keys=('pay_head',),
            reason='Set up when loan approvals were switched on')


class ResCompanyLoanSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    self.env['pb.loan'].sudo()._approval_seed_default(company)
            except Exception:       # noqa: BLE001 — a company must still be made
                _logger.exception('pb_loans: %s has no loan route', company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with env.cr.savepoint():
                if env['pb.loan']._approval_seed_default(company):
                    done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_loans: %s has no loan route', company.name)
    return done
