# -*- coding: utf-8 -*-
"""A trip costs money before anybody travels, so it goes to a real route.

WHAT WAS TRUE BEFORE. Three rungs in code: the line manager, then finance,
then HR. Nothing could depend on the size of the advance, so a two-day trip
with no cash advance needed the same three signatures as a fortnight abroad.

WHAT IS TRUE NOW. The same three rungs ship as the default — **Their manager,
then the Finance approver, then the HR lead** — with the cash advance carried
as the request's AMOUNT, so a business can put a size on the finance step (or
any step) without a developer. Trips are one of the processes marked as money,
so a one-person route asks the publisher to confirm it.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

TRIP_PROCESS_KEY = 'trip'

register_chain(
    'pb.business.trip', TRIP_PROCESS_KEY,
    submit_state='submitted',
    driven=('manager_approved', 'finance_approved', 'approved'),
    amount_field='advance_amount',
    date_field='date_from',
)


class PbBusinessTripApproval(models.Model):
    _inherit = 'pb.business.trip'

    _approval_process_key = TRIP_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Trip · %(who)s · %(where)s",
                 who=self.employee_id.name or '',
                 where=(self.destination_city
                        or self.destination_country_id.name
                        or _('not said')))

    def _chain_facts(self):
        self.ensure_one()
        return {
            'days': {'value': self.duration_days or 0, 'unit': _('days')},
            'advance': {'value': float(self.advance_amount or 0.0),
                        'unit': self.currency_id.name or ''},
            'estimated_total': {'value': float(self.estimated_total or 0.0),
                                'unit': self.currency_id.name or ''},
            'abroad': {'value': bool(
                self.destination_country_id
                and self.company_id.country_id
                and self.destination_country_id != self.company_id.country_id),
                'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'days': {'type': 'int', 'label': _('How many days')},
            'advance': {'type': 'decimal', 'label': _('Cash advance')},
            'estimated_total': {'type': 'decimal',
                                'label': _('What it is expected to cost')},
            'abroad': {'type': 'bool', 'label': _('Outside the country')},
        }

    def _approval_detail(self, request):
        self.ensure_one()
        rows = [{'head': line.description or line.category_id.name or '',
                 'sub': str(line.date or ''),
                 'cells': ['{:,.0f}'.format(float(line.amount or 0.0))],
                 'tone': 'on'}
                for line in self.line_ids[:20]]
        chips = [
            {'label': _('From'), 'value': str(self.date_from or '')},
            {'label': _('To'), 'value': str(self.date_to or '')},
        ]
        if self.per_diem_total:
            chips.append({'label': _('Per diem'),
                          'value': '{:,.0f}'.format(
                              float(self.per_diem_total))})
        return {'title': _('What it is expected to cost'),
                'columns': [_('Amount')], 'rows': rows, 'chips': chips,
                'note': (self.purpose or '')[:240]}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'finance',
                                  'om_hr_payroll.group_hr_payroll_manager')
        Seed.fill_role_from_group(company, 'hr_lead', 'hr.group_hr_manager')
        return Seed.lay(
            company, TRIP_PROCESS_KEY, 'Business trips',
            route(manager_step(_('Their manager')),
                  role_step(_('Finance approver'), 'finance'),
                  role_step(_('HR lead'), 'hr_lead')),
            binding_note='The route every trip follows unless a part of the '
                         'business is given its own.',
            model_name='pb.business.trip',
            role_keys=('finance', 'hr_lead'),
            reason='Set up when trip approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.business.trip']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_business_trip: %s has no trip route',
                              company.name)
    return done
