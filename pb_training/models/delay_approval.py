# -*- coding: utf-8 -*-
"""The delay request's own route: one rung, the person's own manager.

ONE RUNG AND NOT TWO. "I have been off sick and I need another week to finish
the fire-safety course" is a conversation between somebody and their manager.
A route that also asked the HR lead would be a route people go round by simply
not asking — and the whole point of the request is that the new date carries
somebody's name.

WHAT THE ROUTE MAY CHOOSE ON: the reason, how many days, how late it already
is, and whether the trial period is waiting for the course. A company that
wants the HR lead asked for anything over a fortnight, or for anything the
trial period waits on, writes that condition on the route — it does not need a
developer, which is the point of the Matrix.

"THEIR MANAGER" is `employee_id.parent_id.user_id`, read directly, because
plenty of the people these requests are about have no login for the generic
resolver to map back through (AM50) — and the shim already answers it that way
for every consumer that registers an `employee_field`.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, route,
)

from .training_common import DELAY_KIND_LABEL

_logger = logging.getLogger(__name__)

DELAY_PROCESS_KEY = 'training_delay'

register_chain(
    'pb.training.delay', DELAY_PROCESS_KEY,
    submit_state='submitted',
    driven=('approved',),
    employee_field='employee_id',
    date_field='old_due_date',
)


def delay_route():
    return route(manager_step(_('Their manager')))


class PbTrainingDelayApproval(models.Model):
    _inherit = 'pb.training.delay'

    _approval_process_key = DELAY_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("More time · %(who)s · %(course)s",
                 who=self.employee_id.sudo().name or '',
                 course=self.channel_id.sudo().name or '')

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().company_id[:1] or self.env.company

    def _chain_facts(self):
        """Read as the system: the maker is the employee themselves, who holds
        no training permission at all and could not otherwise read the course
        their own request is about (AM40)."""
        self.ensure_one()
        rec = self.sudo()
        assignment = rec.assignment_id
        return {
            'days_asked': {'value': int(rec.days_asked or 0),
                           'unit': _('days')},
            'reason_kind': {'value': DELAY_KIND_LABEL.get(rec.reason_kind, ''),
                            'unit': ''},
            'days_late': {'value': int(assignment._payload()['days_over']
                                       if assignment else 0),
                          'unit': _('days')},
            'blocks_probation': {
                'value': bool(assignment.counts_for_probation)
                if assignment else False, 'unit': ''},
            'course': {'value': rec.channel_id.name or '', 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'days_asked': {'type': 'int', 'label': _('How many more days')},
            'reason_kind': {'type': 'char', 'label': _('Why')},
            'days_late': {'type': 'int',
                          'label': _('How late it already is')},
            'blocks_probation': {
                'type': 'bool',
                'label': _('Their trial period is waiting for it')},
            'course': {'type': 'char', 'label': _('Which course')},
        }

    def _chain_revision_values(self):
        """What the manager is agreeing to: this course, this many days.

        Never the assignment's own due date — that is true of the world rather
        than of the request, and a stamp over it would refuse a perfectly good
        approval the moment the training team moved the date for an unrelated
        reason (AM32).
        """
        self.ensure_one()
        return {'assignment': self.assignment_id.id,
                'days': int(self.days_asked or 0),
                'kind': self.reason_kind or ''}

    def _approval_detail(self, request):
        self.ensure_one()
        assignment = self.assignment_id.sudo()
        chips = [
            {'label': _('Course'), 'value': self.channel_id.sudo().name or ''},
            {'label': _('Was due'),
             'value': str(assignment.due_date or _('no date'))},
            {'label': _('Asking for'),
             'value': _("%s more days", self.days_asked or 0)},
            {'label': _('Why'),
             'value': DELAY_KIND_LABEL.get(self.reason_kind, '')},
        ]
        if assignment.counts_for_probation:
            chips.append({'label': _('Trial period'),
                          'value': _('waiting for this course')})
        return {'title': _('Asking for more time on a course'), 'columns': [],
                'rows': [], 'chips': chips, 'note': self.note or ''}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        return Seed.lay(
            company, DELAY_PROCESS_KEY, 'More time on a course',
            delay_route(),
            binding_note='Who agrees when somebody asks for longer to finish '
                         'a course they have been put on. By default their '
                         'own manager. A business that wants the HR lead '
                         'asked as well — for a long extension, or when the '
                         'trial period is waiting for the course — adds that '
                         'rung here.',
            model_name='pb.training.delay',
            role_keys=(),
            reason='Set up when training assignments were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.training.delay']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_training: %s has no route for asking for '
                              'more time', company.name)
    return done
