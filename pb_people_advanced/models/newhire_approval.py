# -*- coding: utf-8 -*-
"""Adding somebody to the payroll is a maker-checker moment.

WHAT WAS TRUE BEFORE. Two guided wizards — "add an employee" and "give them a
contract" — created an employee record and a contract with a wage on it, with
NO permission check of any kind in this module. Anybody who could reach the
screen could put a person on the payroll at any salary.

WHAT IS TRUE NOW. Two things, and the first matters more:

  1. **A permission.** Both doors need the HR role. They always should have.
  2. **A proposal.** The person and the contract are written down and created
     when the route says yes — the HR lead by default, which is exactly the
     maker-checker pair a payroll audit asks for.

ONE PROPOSAL FOR BOTH. "Add an employee and give them a contract" is one press
on the screen and it is one proposal here, carried out in the same order: the
employee first, the contract second, against the employee that was just made.
Two proposals would have meant an employee with no contract sitting on the
payroll while the second one waited.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

NEWHIRE_PROCESS_KEY = 'newhire'

#: What putting somebody on the payroll has always needed, and never checked.
NEWHIRE_GROUPS = ('hr.group_hr_user', 'hr.group_hr_manager')

#: "This write IS the approved change."
NEWHIRE_WRITE = 'pb_newhire_approved_write'


def require_hr(env):
    """The permission these two wizards shipped without."""
    user = env.user
    if user._is_superuser() or any(user.has_group(x) for x in NEWHIRE_GROUPS):
        return True
    raise AccessError(_(
        "Adding somebody to the payroll, or giving them a contract, is for "
        "HR. Ask somebody in HR to do this, or to give you the HR "
        "permission."))


class PbNewHireProposal(models.Model):
    _name = 'pb.newhire.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed new hire'

    _approval_process_key = NEWHIRE_PROCESS_KEY
    _proposal_prefix = 'NEW'
    _proposal_gate_groups = NEWHIRE_GROUPS
    _proposal_kind_labels = {
        'employee': 'Add somebody to the payroll',
        'contract': 'Give somebody a contract',
    }
    _proposal_fact_specs = {
        'wage': {'type': 'decimal', 'label': 'Monthly pay'},
        'has_bank': {'type': 'bool', 'label': 'Bank details given'},
        'contract_type': {'type': 'char', 'label': 'Kind of contract'},
    }

    # --------------------------------------------------------- the applies
    def _apply_employee(self):
        payload = self.payload()
        answer = self.env['pb.people.onboard.wizard'].with_context(
            **{NEWHIRE_WRITE: True}).create_employee(payload.get('values')
                                                     or {})
        if answer.get('error') and not answer.get('employee_id'):
            raise UserError(answer['error'])
        return answer

    def _apply_contract(self):
        payload = self.payload()
        answer = self.env['pb.people.contract.wizard'].with_context(
            **{NEWHIRE_WRITE: True}).create_contract(payload.get('values')
                                                     or {})
        if answer.get('error') and not answer.get('contract_id'):
            raise UserError(answer['error'])
        return answer

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', ('hr.group_hr_manager',))
        return Seed.lay(
            company, NEWHIRE_PROCESS_KEY, 'New people and first contracts',
            route(role_step(_('HR lead'), 'hr_lead')),
            binding_note='The route adding somebody to the payroll follows.',
            model_name='pb.newhire.proposal',
            role_keys=('hr_lead',),
            reason='Set up when new-hire approvals were switched on')


class ResCompanyNewHireSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.newhire.proposal']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('new hire: %s has no route yet', company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.newhire.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('new hire: %s has no route yet', company.name)
    return done


def post_init_hook(env):
    seed_all(env)
