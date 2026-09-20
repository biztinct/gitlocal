# -*- coding: utf-8 -*-
"""A hiring request travels the route the business published.

THE DEFAULT ROUTE IS THREE RUNGS AND ONE OF THEM IS CONDITIONAL: their
manager, the HR lead, and the Finance approver ONLY when the request asks for
more than the budget has left. That is the whole reason the budget answer is
computed on the record rather than looked up by a human at the end — the route
chooses itself from a fact, and a fact has to exist before anybody can choose
on it.

WHAT AN APPROVER IS AGREEING TO is the role, the number of people and the
money: change any of those and the approval that was given was given to a
different request. The budget STATUS is deliberately NOT in the stamp, because
it is true of the world rather than of the record — somebody else's spend
lands and it moves — and a stamp over it would refuse to carry out a perfectly
good approval (the `_chain_revision_values` doctrine, ledger AM32).
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

from .hiring_common import GROUP_MANAGER

_logger = logging.getLogger(__name__)

HIRING_PROCESS_KEY = 'hiring_request'

register_chain(
    'pb.hiring.requisition', HIRING_PROCESS_KEY,
    submit_state='submitted',
    driven=('manager_ok', 'hr_ok', 'open'),
    employee_field='requested_by_id',
    amount_field='budget_cost',
    currency_field='currency_id',
    date_field='target_start_date',
)


def hiring_route():
    """Today's ladder, written as a route somebody can read and change."""
    return route(
        manager_step(_('Their manager')),
        role_step(_('HR lead'), 'hr_lead', key='hr'),
        role_step(_('Finance approver'), 'finance', key='fin',
                  condition={'fact': 'over_budget', 'op': 'eq',
                             'value': True}),
    )


class PbHiringRequisitionApproval(models.Model):
    _inherit = 'pb.hiring.requisition'

    _approval_process_key = HIRING_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Hiring request · %s", self.title or '')

    def _chain_facts(self):
        """Read as the system, because the facts a route is CHOSEN on must be
        readable by the engine whoever the maker is (ledger AM40). The maker
        here is a department head who may hold no HR permission at all."""
        self.ensure_one()
        rec = self.sudo()
        return {
            'over_budget': {'value': rec.budget_status == 'over', 'unit': ''},
            'budget_known': {'value': rec.budget_status != 'unknown',
                             'unit': ''},
            'headcount': {'value': int(rec.headcount or 0),
                          'unit': _('people')},
            'budget_cost': {'value': float(rec.budget_cost or 0.0),
                            'unit': rec.currency_id.name or ''},
            'role_type': {'value': rec.role_type or '', 'unit': ''},
            'department': {'value': rec.department_id.name or '', 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'over_budget': {'type': 'bool',
                            'label': _('Asks for more than the budget has '
                                       'left')},
            'budget_known': {'type': 'bool',
                             'label': _('There is a budget to check against')},
            'headcount': {'type': 'int', 'label': _('How many people')},
            'budget_cost': {'type': 'decimal',
                            'label': _('What it is expected to cost')},
            'role_type': {'type': 'char', 'label': _('Why it is needed')},
            'department': {'type': 'char',
                           'label': _('Which part of the business')},
        }

    def _chain_revision_values(self):
        self.ensure_one()
        return {
            'title': (self.title or '').strip(),
            'department': self.department_id.id,
            'headcount': int(self.headcount or 0),
            'amount': float(self.budget_cost or 0.0),
            'currency': self.currency_id.id,
        }

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [
            {'label': _('Part of the business'),
             'value': self.department_id.name or ''},
            {'label': _('How many'),
             'value': str(self.headcount or 1)},
        ]
        if self.location or self.country_id:
            chips.append({'label': _('Where'),
                          'value': self.location or self.country_id.name})
        if self.target_start_date:
            chips.append({'label': _('Wanted by'),
                          'value': str(self.target_start_date)})
        chips.append({'label': _('Budget'), 'value': dict(
            self._fields['budget_status'].selection).get(
                self.budget_status, '')})
        return {'title': _('What is being asked for'), 'columns': [],
                'rows': [], 'chips': chips,
                'note': self.budget_note or self.requirements or ''}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', GROUP_MANAGER)
        return Seed.lay(
            company, HIRING_PROCESS_KEY, 'Hiring request', hiring_route(),
            binding_note='The route every hiring request follows unless a '
                         'part of the business is given its own. The Finance '
                         'rung is only asked when the request costs more than '
                         'the budget has left.',
            model_name='pb.hiring.requisition',
            role_keys=('hr_lead', 'finance'),
            reason='Set up when hiring requests were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.hiring.requisition']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_hiring: %s has no hiring route',
                              company.name)
    return done
