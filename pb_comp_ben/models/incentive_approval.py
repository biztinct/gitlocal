# -*- coding: utf-8 -*-
"""An award is money leaving the company, so it travels a real route.

WHAT WAS TRUE BEFORE. One rung in code: whoever held the head-of-pay group
said yes. A business that wanted the person's own manager to agree first, or a
second signature above a certain amount, could not have it.

WHAT IS TRUE NOW. The same rung ships as the default — **the Head of pay** —
and the award's own amount is the request's amount, so a size can be put on
any extra step. Awards are marked as money in the catalogue, so publishing a
one-person route asks the publisher to confirm that choice and records it.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

AWARDS_PROCESS_KEY = 'awards'

register_chain(
    'pb.incentive', AWARDS_PROCESS_KEY,
    submit_state='submitted',
    driven=('approved',),
    amount_field='amount',
    date_field='period_month',
)


class PbIncentiveApproval(models.Model):
    _inherit = 'pb.incentive'

    _approval_process_key = AWARDS_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("%(kind)s for %(who)s",
                 kind=dict(self._fields['kind'].selection or []).get(
                     self.kind, _('Award')),
                 who=self._person().name or '')

    def _chain_facts(self):
        self.ensure_one()
        return {
            'kind': {'value': self.kind or '', 'unit': ''},
            'amount': {'value': float(self.amount or 0.0),
                       'unit': self.currency_id.name or ''},
            'from_recognition': {'value': self.source == 'rnr', 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'kind': {'type': 'selection', 'label': _('What kind of award')},
            'amount': {'type': 'decimal', 'label': _('Amount')},
            'from_recognition': {'type': 'bool',
                                 'label': _('Came from recognition')},
        }

    def _chain_kind_key(self):
        self.ensure_one()
        return self.kind or 'any'

    @api.model
    def _chain_kinds(self):
        from .comp_common import INCENTIVE_KINDS
        return [{'key': key, 'label': label} for key, label in INCENTIVE_KINDS]

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [
            {'label': _('Pay it in'),
             'value': self.period_month.strftime('%b %Y')
             if self.period_month else ''},
            {'label': _('Amount'),
             'value': '{:,.0f} {}'.format(float(self.amount or 0.0),
                                          self.currency_id.name or '')},
        ]
        return {'title': _('The award'), 'columns': [], 'rows': [],
                'chips': chips, 'note': (self.reason or '')[:240]}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'pay_head',
                                  'pb_comp_ben.group_comp_head')
        return Seed.lay(
            company, AWARDS_PROCESS_KEY, 'Awards',
            route(role_step(_('Head of pay'), 'pay_head')),
            binding_note='The route every award follows unless a part of the '
                         'business is given its own.',
            model_name='pb.incentive',
            role_keys=('pay_head',),
            reason='Set up when award approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.incentive']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_comp_ben: %s has no award route',
                              company.name)
    return done
