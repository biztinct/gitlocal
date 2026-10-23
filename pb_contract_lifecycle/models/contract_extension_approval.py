# -*- coding: utf-8 -*-
"""Keeping somebody on is its own question, with its own route.

WHAT WAS TRUE BEFORE. One rung, and the person who could give it was worked
out in code: the manager named on the request, or anyone in the HR lifecycle
group. The catalogue row said "Resignations and contract extensions" — one row
for two opposite events, so a business could not check one and wave the other
through.

WHAT IS TRUE NOW. Its own catalogue row and its own route. The default is
**Their manager, then the HR lifecycle team** — the two people who already
have to agree — and how long a contract is being extended for is a fact a
route can condition on.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

from .contract_common import GROUP_MANAGER

_logger = logging.getLogger(__name__)

EXTENSION_PROCESS_KEY = 'extension'

register_chain(
    'pb.contract.extension', EXTENSION_PROCESS_KEY,
    submit_state='pending',
    driven=('approved',),
    date_field='new_date_start',
)


class PbContractExtensionApproval(models.Model):
    _inherit = 'pb.contract.extension'

    _approval_process_key = EXTENSION_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Keep %(who)s on for %(months)s month(s)",
                 who=self.employee_id.name or '', months=self.months or 0)

    def _chain_facts(self):
        self.ensure_one()
        return {
            'months': {'value': self.months or 0, 'unit': _('months')},
            'has_named_approver': {'value': bool(self.approver_user_id),
                                   'unit': ''},
            'escalated': {'value': bool(self.escalated), 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'months': {'type': 'int', 'label': _('How many months')},
            'has_named_approver': {'type': 'bool',
                                   'label': _('Somebody is named on it')},
            'escalated': {'type': 'bool', 'label': _('Already chased')},
        }

    def _approval_manager_uids(self):
        """The person named on the request IS the manager being asked.

        The extension carries `approver_user_id` — worked out when it was
        raised, from the contract and the team around it. Ignoring it in
        favour of the employee's `parent_id` would ask a different person than
        the screen has been promising since the request was made.
        """
        self.ensure_one()
        if self.approver_user_id:
            return self.approver_user_id.ids
        return super()._approval_manager_uids()

    def _chain_revision_values(self):
        """How long, and for whom. A month added after somebody agreed is a
        different agreement."""
        self.ensure_one()
        return {'employee': self.employee_id.id,
                'months': self.months or 0,
                'contract': self.contract_id.id,
                'ends': str(self.new_date_end or '')}

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [
            {'label': _('Contract ends'),
             'value': str(self.review_id.end_date or '')},
            {'label': _('New end date'), 'value': str(self.new_date_end or '')},
        ]
        if self.approve_by:
            chips.append({'label': _('Wanted by'), 'value': str(self.approve_by)})
        return {'title': _('The extension'), 'columns': [], 'rows': [],
                'chips': chips, 'note': (self.reason or '')[:240]}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'lifecycle', GROUP_MANAGER)
        return Seed.lay(
            company, EXTENSION_PROCESS_KEY, 'Contract extensions',
            route(manager_step(_('Their manager')),
                  role_step(_('HR lifecycle team'), 'lifecycle')),
            binding_note='The route every extension follows unless a part of '
                         'the business is given its own.',
            model_name='pb.contract.extension',
            role_keys=('lifecycle',),
            reason='Set up when extension approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.contract.extension']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_contract_lifecycle: %s has no extension '
                              'route', company.name)
    return done
