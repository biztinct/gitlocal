# -*- coding: utf-8 -*-
"""An asset request follows the route the business chose, not the one in here.

WHAT WAS TRUE BEFORE. Two rungs, written in code: somebody's manager agreed
they needed it, then the asset team agreed to hand one over. A company that
wanted a third signature for anything expensive, or none at all for a mouse,
had no way to say so.

WHAT IS TRUE NOW. The same two rungs ship as the DEFAULT ROUTE — "Their
manager, then the Equipment team" — published for every company, so day one
behaves exactly like day zero. From there it is a route like any other: add a
step, put a condition on it, set it to "No approval needed", give one part of
the business its own. The buttons on the form are unchanged and now drive the
engine (`biz_approval_workflow/models/chain_shim.py`).
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

#: The catalogue row this kind of record is approved under.
ASSETS_PROCESS_KEY = 'assets'

register_chain(
    'pb.asset.request', ASSETS_PROCESS_KEY,
    submit_state='submitted',
    driven=('manager_approved', 'approved'),
    date_field='needed_by',
)


class PbAssetRequestApproval(models.Model):
    _inherit = 'pb.asset.request'

    _approval_process_key = ASSETS_PROCESS_KEY

    # ------------------------------------------------------------ the facts
    def _chain_title(self):
        self.ensure_one()
        return _("%(what)s for %(who)s",
                 what=self.category_id.name or _('Equipment'),
                 who=self.employee_id.name or '')

    def _chain_facts(self):
        self.ensure_one()
        return {
            'category': {'value': self.category_id.name or '', 'unit': ''},
            'spare_available': {'value': bool(self.spare_asset_id),
                                'unit': ''},
            'country': {'value': self.country_id.name or '', 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'category': {'type': 'char', 'label': _('What they need')},
            'spare_available': {'type': 'bool',
                                'label': _('There is a spare already')},
            'country': {'type': 'char', 'label': _('Country')},
        }

    def _approval_detail(self, request):
        """Why this one, and whether the cupboard already has it."""
        self.ensure_one()
        chips = [{'label': _('Needed by'),
                  'value': self.needed_by and str(self.needed_by) or _('Not said')}]
        if self.spare_asset_id:
            chips.append({'label': _('Spare in the cupboard'),
                          'value': self.spare_asset_id.display_name or ''})
        return {
            'title': _('What was asked for'),
            'columns': [], 'rows': [], 'chips': chips,
            'note': (self.justification or '')[:240],
        }

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'equipment',
                                  'pb_assets.group_assets_manager')
        return Seed.lay(
            company, ASSETS_PROCESS_KEY, 'Asset requests',
            route(manager_step(_('Their manager')),
                  role_step(_('Equipment team'), 'equipment')),
            binding_note='The route every request for equipment follows '
                         'unless a part of the business is given its own.',
            model_name='pb.asset.request',
            role_keys=('equipment',),
            reason='Set up when asset approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.asset.request']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_assets: %s has no asset route yet',
                              company.name)
    return done
