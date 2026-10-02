# -*- coding: utf-8 -*-
"""Somebody leaving goes through the route the business chose.

WHAT WAS TRUE BEFORE. Two rungs in code: the person's own manager, then the
HR lifecycle group. Nothing could depend on how much notice was given or on
whose department it was.

WHAT IS TRUE NOW. The same two rungs ship as the default — **Their manager,
then the HR lifecycle team** — and the notice period, the requested last day
and whether this is a regrettable leaver are facts a route can use. Taking a
resignation back still closes its request with a reason, so nobody is left
holding a decision about somebody who is staying.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

from .offboarding_common import GROUP_MANAGER

_logger = logging.getLogger(__name__)

RESIGN_PROCESS_KEY = 'resign'

register_chain(
    'pb.resignation', RESIGN_PROCESS_KEY,
    submit_state='submitted',
    driven=('manager_ok', 'approved'),
    date_field='requested_lwd',
)


class PbResignationApproval(models.Model):
    _inherit = 'pb.resignation'

    _approval_process_key = RESIGN_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Resignation · %s", self.employee_id.name or '')

    def _chain_facts(self):
        self.ensure_one()
        return {
            'notice_days': {'value': self.notice_days or 0, 'unit': _('days')},
            'regrettable': {'value': bool(self.regrettable), 'unit': ''},
            'source': {'value': self.source or 'manual', 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'notice_days': {'type': 'int', 'label': _('Days of notice')},
            'regrettable': {'type': 'bool',
                            'label': _('Somebody the company wanted to keep')},
            'source': {'type': 'selection', 'label': _('Where it came from')},
        }

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [
            {'label': _('Handed in'), 'value': str(self.submit_date or '')},
            {'label': _('Last day asked for'),
             'value': str(self.requested_lwd or '')},
            {'label': _('Notice'), 'value': str(self.notice_days or 0)},
        ]
        if self.departure_reason_id:
            chips.append({'label': _('Reason'),
                          'value': self.departure_reason_id.name or ''})
        return {'title': _('Leaving'), 'columns': [], 'rows': [],
                'chips': chips, 'note': (self.reason_text or '')[:240]}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'lifecycle', GROUP_MANAGER)
        return Seed.lay(
            company, RESIGN_PROCESS_KEY, 'Resignations',
            route(manager_step(_('Their manager')),
                  role_step(_('HR lifecycle team'), 'lifecycle')),
            binding_note='The route every resignation follows unless a part '
                         'of the business is given its own.',
            model_name='pb.resignation',
            role_keys=('lifecycle',),
            reason='Set up when resignation approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.resignation']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_offboarding: %s has no resignation route',
                              company.name)
    return done
