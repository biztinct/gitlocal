# -*- coding: utf-8 -*-
"""Praise travels the route the business chose, and the prize with it.

WHAT WAS TRUE BEFORE. Two rungs in code: the nominee's own manager, then the
recognition team. It shared a catalogue row with cash awards, so a business
could not check a bonus and let a thank-you through.

WHAT IS TRUE NOW. Its own catalogue row — **Recognition** — and its own route.
The default is the same two rungs: **Their manager, then the HR lead**.

THE AMOUNT IS DECIDED AT THE END, SO IT IS NOT PART OF THE STAMP. Every
request carries a stamp of what was sent in, and the engine refuses to carry
out an approval whose subject has changed underneath it. Recognition is the
one consumer where the LAST approver sets a value on the record —
`action_recognise(amount)` writes the prize before it says yes — so the stamp
here covers the story and the person, which is what everybody in the route is
actually agreeing to, and never the amount they are agreeing.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

RECOGNITION_PROCESS_KEY = 'recognition'

register_chain(
    'pb.rnr.nomination', RECOGNITION_PROCESS_KEY,
    submit_state='submitted',
    driven=('manager', 'done'),
    employee_field='nominee_id',
    amount_field='award_amount',
)


class PbRnrNominationApproval(models.Model):
    _inherit = 'pb.rnr.nomination'

    _approval_process_key = RECOGNITION_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Recognition · %s", self._person(self.nominee_id).name or '')

    def _chain_facts(self):
        self.ensure_one()
        return {
            'value': {'value': self.value_id.name or '', 'unit': ''},
            'public': {'value': bool(self.public), 'unit': ''},
            'award_amount': {'value': float(self.award_amount or 0.0),
                             'unit': self.currency_id.name or ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'value': {'type': 'char', 'label': _('Which value it shows')},
            'public': {'type': 'bool', 'label': _('Can be shown on the wall')},
            'award_amount': {'type': 'decimal',
                             'label': _('Prize asked for')},
        }

    def _chain_revision_values(self):
        """What everyone in the route is agreeing to: the story, not the money."""
        self.ensure_one()
        return {'nominee': self.nominee_id.id,
                'story': (self.story or '').strip(),
                'value': self.value_id.id}

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [{'label': _('Nominated by'),
                  'value': self._person(self.nominator_id).name or ''}]
        if self.value_id:
            chips.append({'label': _('Value'), 'value': self.value_id.name or ''})
        if self.cycle_id:
            chips.append({'label': _('Quarter'), 'value': self.cycle_id.name or ''})
        return {'title': _('The story'), 'columns': [], 'rows': [],
                'chips': chips, 'note': (self.story or '')[:240]}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead',
                                  'pb_rnr.group_rnr_manager')
        return Seed.lay(
            company, RECOGNITION_PROCESS_KEY, 'Recognition',
            route(manager_step(_('Their manager')),
                  role_step(_('HR lead'), 'hr_lead')),
            binding_note='The route every piece of recognition follows unless '
                         'a part of the business is given its own.',
            model_name='pb.rnr.nomination',
            role_keys=('hr_lead',),
            reason='Set up when recognition approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.rnr.nomination']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_rnr: %s has no recognition route',
                              company.name)
    return done
