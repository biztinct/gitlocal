# -*- coding: utf-8 -*-
"""The cover's own route: one rung, the recruiter's manager.

ONE RUNG AND NOT TWO, deliberately. Handing your candidates to a colleague for
a fortnight is a decision about workload, not about money or head count — and
a route that asked the HR lead as well would be a route people go around by
simply not telling anybody.

"THEIR MANAGER" IS RESOLVED ON THE RECORD and the answer says where it came
from: the hiring rule for the recruiter's company and country first (a table a
business filled in on purpose), then the org chart. `_chain_title` carries it,
so an approver opening their inbox can see why this landed on them.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, route,
)

_logger = logging.getLogger(__name__)

COVER_PROCESS_KEY = 'hiring_cover'

register_chain(
    'pb.hiring.cover', COVER_PROCESS_KEY,
    submit_state='submitted',
    driven=('approved',),
    employee_field=None,
    date_field='date_from',
)


def cover_route():
    return route(manager_step(_("The recruiter's manager")))


class PbHiringCoverApproval(models.Model):
    _inherit = 'pb.hiring.cover'

    _approval_process_key = COVER_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        where = {
            'rule': _('named by the hiring rule'),
            'chart': _('their manager on the org chart'),
        }.get(self.approver_source, _('nobody could be found'))
        return _("Cover · %(who)s for %(for_whom)s (%(where)s)",
                 who=self.cover_user_id.name or '',
                 for_whom=self.recruiter_id.name or '', where=where)

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().company_id[:1] or self.env.company

    def _chain_facts(self):
        self.ensure_one()
        rec = self.sudo()
        days = 0
        if rec.date_from and rec.date_to:
            days = (rec.date_to - rec.date_from).days + 1
        return {
            'days': {'value': int(days), 'unit': _('days')},
            'roles': {'value': int(rec.requisition_count or 0),
                      'unit': _('roles')},
            'recruiter': {'value': rec.recruiter_id.name or '', 'unit': ''},
            'cover': {'value': rec.cover_user_id.name or '', 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'days': {'type': 'int', 'label': _('How long')},
            'roles': {'type': 'int', 'label': _('Roles they would pick up')},
            'recruiter': {'type': 'char', 'label': _('Who is away')},
            'cover': {'type': 'char', 'label': _('Who is standing in')},
        }

    def _chain_revision_values(self):
        self.ensure_one()
        return {'cover': self.cover_user_id.id,
                'from': str(self.date_from or ''),
                'to': str(self.date_to or '')}

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [
            {'label': _('Who is away'), 'value': self.recruiter_id.name or ''},
            {'label': _('Standing in'),
             'value': self.cover_user_id.name or ''},
            {'label': _('From'), 'value': str(self.date_from or '')},
            {'label': _('Until'), 'value': str(self.date_to or '')},
            {'label': _('Roles they would pick up'),
             'value': str(self.requisition_count or 0)},
        ]
        return {'title': _('Standing in for a recruiter'), 'columns': [],
                'rows': [], 'chips': chips, 'note': self.reason or ''}

    def _approval_manager_uids(self):
        self.ensure_one()
        return self.approver_user_id.ids

    def _approval_skip_manager_uids(self):
        """Nobody is skipped: this route has one rung and skipping it would
        leave the cover with no approver at all."""
        self.ensure_one()
        return []

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        return Seed.lay(
            company, COVER_PROCESS_KEY, 'Recruiter cover', cover_route(),
            binding_note="Who agrees that a colleague picks up a recruiter's "
                         "roles while they are away. By default the "
                         "recruiter's own manager — from the hiring rule for "
                         "their country if there is one, and from the org "
                         "chart if there is not.",
            model_name='pb.hiring.cover',
            role_keys=(),
            reason='Set up when recruiter cover was switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.hiring.cover']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_hiring: %s has no cover route', company.name)
    return done
