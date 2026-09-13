# -*- coding: utf-8 -*-
"""A rise, and a whole round of rises, on the route the business chose.

WHAT WAS TRUE BEFORE. Three rungs in code for both — the pay manager, then
finance (only when the rise was above guidance), then whoever held the
sign-off group. The middle step's condition was a company setting read in
Python; the rest was a dictionary nobody could edit.

WHAT IS TRUE NOW. The same three rungs ship as the default for both records —
**HR lead, then the Finance approver when it is above guidance, then the
Country director** — with the "above guidance" test carried as a FACT, so the
condition is now something a business can see, change or remove.

WHAT DID NOT CHANGE. Applying a pay change still writes wages, and it is
still a separate press after the approval (safety rail 3): `applied` and
`closed` come after the route's last rung, so the route never writes a wage by
itself. Taking one back closes its request with the reason.

A NOTE ON "THEIR MANAGER". The handover asked for a manager step at the front
of both routes. There is none in today's ladder, and there is a harder reason
than fidelity: `pb.pay.change` gives no read at all to an ordinary internal
user, so a line manager who holds no pay role would be given a seat and then
refused the record by the ORM at the moment they tried to decide it. A
business that wants its managers in this route gives them the Pay viewer role
and adds the step — which is a choice with a visible cost, not a default.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

from .pb_pay_change import GROUP_CEO, GROUP_FINANCE, GROUP_MANAGER

_logger = logging.getLogger(__name__)

PAYCHANGE_PROCESS_KEY = 'paychange'
PAYREVIEW_PROCESS_KEY = 'payreview'

register_chain(
    'pb.pay.change', PAYCHANGE_PROCESS_KEY,
    submit_state='proposed',
    driven=('hr_review', 'finance', 'approved'),
    amount_field='new_wage',
    date_field='effective_date',
    reverse_to=('draft',),
)

register_chain(
    'pb.pay.review', PAYREVIEW_PROCESS_KEY,
    submit_state='proposed',
    driven=('hr_review', 'finance', 'approved'),
    amount_field='budget_amount',
    date_field='effective_date',
    reverse_to=('draft',),
    employee_field=None,
)


def _pay_route():
    """Today's ladder, as a route somebody can read and change."""
    return route(
        role_step(_('HR lead'), 'hr_lead', key='hr'),
        role_step(_('Finance approver'), 'finance', key='fin',
                  condition={'fact': 'above_guidance', 'op': 'eq',
                             'value': True}),
        role_step(_('Country director'), 'director', key='signoff'),
    )


def _seed_pay_roles(env, company):
    Seed = env['biz.approval.seed']
    Seed.fill_role_from_group(company, 'hr_lead', GROUP_MANAGER)
    Seed.fill_role_from_group(company, 'finance', GROUP_FINANCE)
    Seed.fill_role_from_group(company, 'director', GROUP_CEO)


class PbPayChangeApproval(models.Model):
    _inherit = 'pb.pay.change'

    _approval_process_key = PAYCHANGE_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Pay change · %s", self.employee_id.name or '')

    def _chain_facts(self):
        self.ensure_one()
        return {
            'pct': {'value': float(self.pct or 0.0), 'unit': '%'},
            'new_wage': {'value': float(self.new_wage or 0.0),
                         'unit': self.currency_id.name or ''},
            'above_guidance': {'value': bool(self.needs_finance()), 'unit': ''},
            'kind': {'value': self.kind or '', 'unit': ''},
            'above_band': {'value': float(self.position_after or 0.0) > 100.0,
                           'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'pct': {'type': 'percent', 'label': _('How big the rise is')},
            'new_wage': {'type': 'decimal', 'label': _('New pay')},
            'above_guidance': {'type': 'bool',
                               'label': _('Bigger than the guidance allows')},
            'kind': {'type': 'selection', 'label': _('Why')},
            'above_band': {'type': 'bool',
                           'label': _('Above the top of the band')},
        }

    def _chain_kind_key(self):
        self.ensure_one()
        return self.kind or 'any'

    def _approval_detail(self, request):
        self.ensure_one()
        rows = [{
            'head': self.employee_id.name or '',
            'sub': self.new_job_id.name or '',
            'cells': ['{:,.0f}'.format(float(self.current_wage or 0.0)),
                      '{:,.0f}'.format(float(self.new_wage or 0.0)),
                      '{:+.1f}%'.format(float(self.pct or 0.0))],
            'tone': 'on'}]
        chips = [{'label': _('Starts on'),
                  'value': str(self.effective_date or '')}]
        if self.band_id:
            chips.append({'label': _('Band'), 'value': self.band_id.name or ''})
        if self.guidance_pct:
            chips.append({'label': _('Guidance'),
                          'value': '{:.1f}%'.format(
                              float(self.guidance_pct))})
        return {'title': _('The change'),
                'columns': [_('Now'), _('Proposed'), _('Rise')],
                'rows': rows, 'chips': chips,
                'note': (self.reason or '')[:240]}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        _seed_pay_roles(self.env, company)
        return self.env['biz.approval.seed'].lay(
            company, PAYCHANGE_PROCESS_KEY, 'Pay changes', _pay_route(),
            binding_note='The route every pay change follows unless a part '
                         'of the business is given its own.',
            model_name='pb.pay.change',
            role_keys=('hr_lead', 'finance', 'director'),
            reason='Set up when pay-change approvals were switched on')


class PbPayReviewApproval(models.Model):
    _inherit = 'pb.pay.review'

    _approval_process_key = PAYREVIEW_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Pay review · %s", self.name or '')

    def _chain_facts(self):
        self.ensure_one()
        over = float(self.allocated_amount or 0.0) > float(
            self.budget_amount or 0.0)
        return {
            'budget': {'value': float(self.budget_amount or 0.0),
                       'unit': self.currency_id.name or ''},
            'proposed': {'value': float(self.allocated_amount or 0.0),
                         'unit': self.currency_id.name or ''},
            'people': {'value': self.people or 0, 'unit': ''},
            'above_guidance': {'value': over, 'unit': ''},
            'blocked_rows': {'value': self.lines_blocked or 0, 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'budget': {'type': 'decimal', 'label': _('Budget for the year')},
            'proposed': {'type': 'decimal',
                         'label': _('What is being proposed')},
            'people': {'type': 'int', 'label': _('How many people')},
            'above_guidance': {'type': 'bool',
                               'label': _('More than the budget allows')},
            'blocked_rows': {'type': 'int',
                             'label': _('Rows that stop approval')},
        }

    def _chain_kind_key(self):
        self.ensure_one()
        return self.scope_kind or 'any'

    @api.model
    def _chain_kinds(self):
        return [{'key': 'company', 'label': _('One company')},
                {'key': 'division', 'label': _('One division')},
                {'key': 'scheme', 'label': _('One payroll scheme')}]

    def _approval_card_count(self, request):
        self.ensure_one()
        return _("1 person") if self.people == 1 else _("%s people",
                                                        self.people or 0)

    def _approval_detail(self, request):
        self.ensure_one()
        rows = [{
            'head': line.employee_id.name or '',
            'sub': line.department_id.name or '',
            'cells': ['{:,.0f}'.format(float(
                getattr(line, 'current_wage', 0.0) or 0.0)),
                '{:,.0f}'.format(float(
                    getattr(line, 'new_wage', 0.0) or 0.0))],
            'tone': 'on'} for line in self.line_ids[:30]]
        chips = [
            {'label': _('Budget'),
             'value': '{:,.0f}'.format(float(self.budget_amount or 0.0))},
            {'label': _('Proposed'),
             'value': '{:,.0f}'.format(float(self.allocated_amount or 0.0))},
            {'label': _('People'), 'value': str(self.people or 0)},
        ]
        note = self.note or ''
        if self.people and len(rows) < self.people:
            note = (note + ' ' if note else '') + _(
                "Showing the first %(shown)s of %(total)s people.",
                shown=len(rows), total=self.people)
        return {'title': _('Who is in this review'),
                'columns': [_('Now'), _('Proposed')], 'rows': rows,
                'chips': chips, 'note': note}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        _seed_pay_roles(self.env, company)
        return self.env['biz.approval.seed'].lay(
            company, PAYREVIEW_PROCESS_KEY, 'Pay reviews', _pay_route(),
            binding_note='The route every round of rises follows unless a '
                         'part of the business is given its own.',
            model_name='pb.pay.review',
            role_keys=('hr_lead', 'finance', 'director'),
            reason='Set up when pay-review approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        for model in ('pb.pay.change', 'pb.pay.review'):
            try:
                if env[model]._approval_seed_default(company):
                    done += 1
            except Exception:   # noqa: BLE001 — an upgrade must not die here
                _logger.exception('pb_pay: %s has no %s route', company.name,
                                  model)
    return done
