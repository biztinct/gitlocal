# -*- coding: utf-8 -*-
"""The advert's own route: ONE rung, and it is a person rather than a role.

WHY IT IS NOT THE SAME ROUTE AS THE REQUEST. A hiring request is a decision
about money and head count and it belongs to the business. An advert is a
description of a job and it belongs to whoever will manage the person doing
it. Putting both through one catalogue row would mean a business that wants
Finance to see the money cannot let the wording through without them.

"THEIR MANAGER" MEANS SOMETHING DIFFERENT HERE, so the hook is overridden:
the manager step on this route asks the person who ASKED FOR THE ROLE, not the
manager of the person who wrote the version (ledger AM50 reached from a new
direction — the record names who it is for, so ask the record).
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, route,
)

_logger = logging.getLogger(__name__)

JD_PROCESS_KEY = 'hiring_jd'

register_chain(
    'pb.hiring.jd', JD_PROCESS_KEY,
    submit_state='submitted',
    driven=('approved',),
    employee_field=None,
    date_field=None,
)


class PbHiringJdApproval(models.Model):
    _inherit = 'pb.hiring.jd'

    _approval_process_key = JD_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Advert · %(title)s (v%(n)s)",
                 title=self.title or '', n=self.version or 1)

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().requisition_id.company_id[:1] or self.env.company

    def _chain_facts(self):
        self.ensure_one()
        rec = self.sudo()
        return {
            'version': {'value': int(rec.version or 1), 'unit': ''},
            'department': {'value': rec.requisition_id.department_id.name or '',
                           'unit': ''},
            'headcount': {'value': int(rec.requisition_id.headcount or 0),
                          'unit': _('people')},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'version': {'type': 'int', 'label': _('Which version')},
            'department': {'type': 'char',
                           'label': _('Which part of the business')},
            'headcount': {'type': 'int', 'label': _('How many people')},
        }

    def _chain_revision_values(self):
        """The words ARE the thing being agreed, so they are in the stamp.

        The doctrine's own carve-out (ledger AM32): a consumer whose OWN
        values are what somebody is signing for stamps them. Editing the
        advert after it has gone out for agreement has to send it round
        again, because otherwise the agreement is to something nobody read.
        """
        self.ensure_one()
        return {'title': (self.title or '').strip(),
                'body': (self.body or '').strip(),
                'summary': (self.summary or '').strip()}

    def _approval_detail(self, request):
        self.ensure_one()
        req = self.requisition_id
        chips = [{'label': _('For'), 'value': req.name or ''},
                 {'label': _('Version'), 'value': str(self.version or 1)}]
        if req.department_id:
            chips.append({'label': _('Part of the business'),
                          'value': req.department_id.name})
        return {'title': _('The advert'), 'columns': [], 'rows': [],
                'chips': chips, 'note': self.summary or ''}

    def _approval_manager_uids(self):
        """The hiring manager, named on the record."""
        self.ensure_one()
        return self._jd_approver_uids()

    def _approval_skip_manager_uids(self):
        """Nobody is skipped: this route has one rung and skipping it would
        leave the advert with no approver at all."""
        self.ensure_one()
        return []

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        return Seed.lay(
            company, JD_PROCESS_KEY, 'Job description', route(
                manager_step(_('The hiring manager'))),
            binding_note='Who agrees the wording of an advert before it goes '
                         'out. By default the person who asked for the role.',
            model_name='pb.hiring.jd',
            role_keys=(),
            reason='Set up when hiring requests were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.hiring.jd']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_hiring: %s has no advert route',
                              company.name)
    return done
