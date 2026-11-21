# -*- coding: utf-8 -*-
"""Owner ruling TA1 (2026-11-16): settling a trip cash advance is approved by
ONE second person, the Head of pay.

The loans pattern (`pb_loans/models/loan_approval.py`): the chain shim drives
`pb.trip.advance.state` — finance settling it moves it to "Settlement waiting
for approval"; the route saying yes moves it to "Settled" and only then are
the claims set against the advance and the unspent part opened to the pay run
(`_settle_apply`). Sent back or turned down → back to "Given", with the
reason, for finance to settle again. The default route every company gets is
ONE step, the Head of pay (`pay_head`, filled from the payroll manager group —
the seat loans, fund payments and back pay use). The catalogue row is money,
so it is never approved in a batch.

WHO MAY NOT APPROVE. The engine's own independence rule, as each database has
it set (no new rule here): the person who settled is the request's submitter
and a maker; the employee it is about is its subject.

A SETTLEMENT WITH NOTHING TO TAKE BACK follows the same route: it still
decides how much of each claim the advance covers, i.e. how much the person
is paid for those claims — money either way.
"""
import logging

from odoo import _, api, models
from odoo.tools.misc import formatLang

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

ADVANCE_PROCESS_KEY = 'tripadvance'

register_chain(
    'pb.trip.advance', ADVANCE_PROCESS_KEY,
    submit_state='waiting',
    driven=('settled',),
    draft_state='given',
    refuse_state='given',
    reverse_to=('given',),
    amount_field='amount',
    # No date_field (ledger PRB-W1): whoever holds the seat today decides.
)


class PbTripAdvanceApproval(models.Model):
    _inherit = 'pb.trip.advance'

    _approval_process_key = ADVANCE_PROCESS_KEY

    # ------------------------------------------------------------ the ladder
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'settled':
            for adv in self:
                adv._settle_apply()
        return res

    def _approval_return(self, request, reason):
        res = super(PbTripAdvanceApproval, self.sudo())._approval_return(request, reason)
        self._settle_undo(reason)
        return res

    def _approval_reject(self, request, reason):
        res = super(PbTripAdvanceApproval, self.sudo())._approval_reject(request, reason)
        self._settle_undo(reason, refused=True)
        return res

    def _approval_apply(self, request):
        # as the system: the Head of pay holds no expense right (W2B-2)
        return super(PbTripAdvanceApproval, self.sudo())._approval_apply(request)

    # ------------------------------------------------------------ the request
    def _approval_context(self):
        """Read under sudo (W2B-2). The makers are the person who settled it
        (never the person who once recorded the cash as given: that is a
        different act), the subject is the employee."""
        ctx = super(PbTripAdvanceApproval, self.sudo())._approval_context()
        adv = self.sudo()
        makers = set(ctx.get('maker_uids') or []) - {adv.create_uid.id}
        if adv.settled_by:
            makers.add(adv.settled_by.id)
        if adv.employee_id.user_id:
            makers.add(adv.employee_id.user_id.id)
        makers.discard(False)
        ctx['maker_uids'] = sorted(makers)
        return ctx

    def _chain_revision_values(self):
        """What the Head of pay signs for: these claims at these amounts,
        this advance, this way of taking the rest back."""
        self.ensure_one()
        adv = self.sudo()
        preview = adv._settle_preview()
        return {'amount': float(adv.amount or 0.0),
                'employee': adv.employee_id.id,
                'claims': sorted([c.id, round(float(a), 2)] for c, a in preview['claims']),
                'how': adv.recover_how or ''}

    def _chain_title(self):
        self.ensure_one()
        adv = self.sudo()
        return _("Trip cash advance · %(who)s · %(trip)s", who=adv.employee_id.name or '',
                 trip=adv.trip_id.name or '')

    def _chain_facts(self):
        self.ensure_one()
        adv = self.sudo()
        unit = adv.currency_id.name or ''
        return {
            'amount': {'value': float(adv.amount or 0.0), 'unit': unit},
            'unspent': {'value': float(adv.unspent or 0.0), 'unit': unit},
            'claimed': {'value': float(adv.claimed or 0.0), 'unit': unit},
            'from_pay': {'value': adv.recover_how == 'pay' and bool(adv.unspent),
                         'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'amount': {'type': 'decimal', 'label': _('Advance given')},
            'unspent': {'type': 'decimal', 'label': _('Not spent')},
            'claimed': {'type': 'decimal', 'label': _('Claimed against it')},
            'from_pay': {'type': 'bool', 'label': _('Taken back from pay')},
        }

    def _approval_detail(self, request):
        self.ensure_one()
        adv = self.sudo()
        env = self.env
        preview = adv._settle_preview()
        money = lambda v: formatLang(env, v or 0.0, currency_obj=adv.currency_id)  # noqa: E731
        rows = [{'head': claim.name or '', 'sub': _('Claimed against the advance'),
                 'cells': [money(amount)], 'tone': 'on'}
                for claim, amount in preview['claims'][:20]]
        chips = [{'label': _('Advance given'), 'value': money(adv.amount)},
                 {'label': _('Claimed against it'), 'value': money(adv.claimed)}]
        if adv.unspent:
            chips.append({'label': _('Not spent'), 'value': money(adv.unspent)})
            chips.append({'label': _('Comes back'),
                          'value': _('From the next pay') if adv.recover_how == 'pay'
                          else _('Paid back by the person')})
        if adv.extra_due:
            chips.append({'label': _('Spent above the advance'),
                          'value': money(adv.extra_due)})
        if adv.settled_by:
            chips.append({'label': _('Settled by'), 'value': adv.settled_by.name or ''})
        return {'title': _('What the advance was spent on'), 'columns': [_('Amount')],
                'rows': rows, 'chips': chips,
                'note': _("Approving sets these claims against the advance; what was not "
                          "spent is then taken back as chosen.")}

    # ------------------------------------------------------------ the route
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'pay_head',
                                  ('pb_hr_payroll_base.group_payroll_base_manager',))
        return Seed.lay(
            company, ADVANCE_PROCESS_KEY, 'Trip cash advance settlements',
            route(role_step(_('Head of pay'), 'pay_head')),
            binding_note='The route every trip cash advance settlement follows '
                         'unless a part of the business is given its own.',
            model_name='pb.trip.advance',
            role_keys=('pay_head',),
            reason='Set up when trip advance settlements needed approval')


class ResCompanyTripAdvanceSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    self.env['pb.trip.advance'].sudo()._approval_seed_default(company)
            except Exception:       # noqa: BLE001 — a company must still be made
                _logger.exception('pb_trip_advance: %s has no settlement route',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with env.cr.savepoint():
                if env['pb.trip.advance']._approval_seed_default(company):
                    done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_trip_advance: %s has no settlement route',
                              company.name)
    return done
