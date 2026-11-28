# -*- coding: utf-8 -*-
"""The course request's route: their manager, then the HR lead when money is
involved (LEARNING L5).

TWO RUNGS, THE SECOND ONE CONDITIONAL. "Can I take this course" is first a
conversation with the person's own manager — it is their time and their
team. When the course costs money it is also a question about the training
allowance, which belongs to the company and not to the manager, so the HR
lead decides after the manager. The second rung carries a CONDITION on the
`amount` fact (`> 0`), which the engine evaluates when the request is sent
in: a free course or one of ours goes to the manager only (handover §3.2 —
the engine branches on a condition, so one route is enough; no second
route keyed by amount).

NO `date_field` (ledger F1, the claim's live defect): a route asks who holds
the seat NOW.

A business that wants something else — the HR lead for anything over five
million, or nobody but the manager — changes the route in the Matrix; that is
what the facts are for.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

from .training_common import REQUEST_KIND_LABEL, money_words

_logger = logging.getLogger(__name__)

REQUEST_PROCESS_KEY = 'training_request'

register_chain(
    'pb.training.request', REQUEST_PROCESS_KEY,
    submit_state='submitted',
    driven=('approved',),
    employee_field='employee_id',
    amount_field='amount',
    currency_field='currency_id',
)

#: The HR lead is asked only when the course costs money.
MONEY_CONDITION = {'fact': 'amount', 'op': 'gt', 'value': 0}


def request_route():
    return route(
        manager_step(_('Their manager')),
        role_step(_('HR lead'), 'hr_lead', condition=dict(MONEY_CONDITION)),
    )


class PbTrainingRequestApproval(models.Model):
    _inherit = 'pb.training.request'

    _approval_process_key = REQUEST_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Course request · %(who)s · %(course)s",
                 who=self.employee_id.sudo().name or '',
                 course=self.course_name or '')

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().company_id[:1] or self.env.company

    def _chain_facts(self):
        """Read as the system (AM40): the maker is the employee."""
        self.ensure_one()
        rec = self.sudo()
        facts = rec._facts()
        unit = rec.currency_id.name or ''
        left_after = facts['left'] - float(rec.amount or 0.0)
        return {
            'amount': {'value': float(rec.amount or 0.0), 'unit': unit},
            'allowance_left': {'value': float(max(left_after, 0.0)),
                               'unit': unit},
            'over_allowance': {'value': bool(rec.amount > facts['left']),
                               'unit': ''},
            'kind': {'value': REQUEST_KIND_LABEL.get(rec.kind, ''),
                     'unit': ''},
            'course': {'value': rec.course_name or '', 'unit': ''},
            'provider': {'value': rec.provider or '', 'unit': ''},
            'why': {'value': (rec.why or '')[:200], 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'amount': {'type': 'decimal', 'label': _('What it costs')},
            'allowance_left': {
                'type': 'decimal',
                'label': _('What is left of their allowance after this')},
            'over_allowance': {'type': 'bool',
                               'label': _('More than they have left')},
            'kind': {'type': 'char', 'label': _('What they are asking for')},
            'course': {'type': 'char', 'label': _('Which course')},
            'provider': {'type': 'char', 'label': _('Who runs it')},
            'why': {'type': 'char', 'label': _('Why')},
        }

    def _chain_revision_values(self):
        """What is being agreed: this course, this cost (AM32 — never
        `write_date`, never the allowance)."""
        self.ensure_one()
        return {
            'kind': self.kind or '',
            'channel': self.channel_id.id,
            'outside': self.outside_course_id.id,
            'course': self.course_name or '',
            'amount': round(float(self.amount or 0.0), 2),
            'currency': self.currency_id.id,
        }

    def _approval_detail(self, request):
        """Rows are DICTS (`head`/`sub`/`cells`/`tone`) — the Inbox drops
        anything else (ledger F10)."""
        self.ensure_one()
        rec = self.sudo()
        facts = rec._facts()
        chips = [
            {'label': _('Course'), 'value': rec.course_name or ''},
            {'label': _('What it costs'), 'value': rec.amount_words()},
        ]
        if rec.provider:
            chips.append({'label': _('Who runs it'), 'value': rec.provider})
        if rec.amount > 0:
            chips.append({'label': _('Allowance left'),
                          'value': money_words(self.env, facts['left'],
                                               facts['currency'])})
            if rec.amount > facts['left']:
                chips.append({'label': _('Careful'),
                              'value': _('this is more than they have left')})
        if rec.when_words:
            chips.append({'label': _('When'), 'value': rec.when_words})
        rows = []
        if rec.url:
            rows.append({'head': _('Link'), 'sub': '',
                         'cells': [rec.url[:40]], 'tone': ''})
        return {'title': _('Asking to take a course'),
                'columns': [_('Where')], 'rows': rows,
                'chips': chips, 'note': rec.why or ''}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        return Seed.lay(
            company, REQUEST_PROCESS_KEY, 'Course request',
            request_route(),
            binding_note='Who agrees when somebody asks to take a course. By '
                         'default their own manager, and the HR lead after '
                         'them when the course costs money (the money comes '
                         'out of the training allowance). Change the '
                         'condition on the second rung to ask the HR lead '
                         'only above an amount.',
            model_name='pb.training.request',
            role_keys=('hr_lead',),
            reason='Set up when course requests were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.training.request']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_training: %s has no route for course '
                              'requests', company.name)
    return done
