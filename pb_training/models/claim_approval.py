# -*- coding: utf-8 -*-
"""The claim's own route: one rung, the HR lead.

ONE RUNG AND NOT TWO, and the rung is a ROLE rather than a manager. "I paid for
a course, please pay me back" is a question about a budget, and the budget
belongs to the company rather than to the person's own line manager — whose
answer would be yes to their own team and no to somebody else's, which is what
a training allowance exists to stop.

AND IT IS THE LAST APPROVAL THE MONEY GETS. The award this raises is created
already agreed (see `claim.py`), so the HR lead's press IS the sign-off on the
amount. That is deliberate: asking the head of pay to agree the same figure
again is a rung people learn to click through, and the thing that still needs a
human is PAYING it, which happens on the Awards screen and is nobody's business
here.

WHAT THE ROUTE MAY CHOOSE ON: the amount (with its real currency as the unit,
never a type — AM25), what is left of the allowance, whether it is over, and
the course. A business that wants the head of pay asked for anything over ten
million, or the manager asked first, writes that condition ON THE ROUTE. It
does not need a developer, which is the whole point of the Matrix.

THE FACTS ARE READ UNDER `sudo()` (AM40). The maker is the employee, who holds
no training permission at all and could not otherwise read the allowance their
own claim is measured against.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

CLAIM_PROCESS_KEY = 'training_claim'

#: NO `date_field`, AND THAT IS THE WHOLE OF A LIVE DEFECT.
#
# The shim's `_chain_date()` reads the named field and falls back to TODAY, and
# the engine uses that date for two things: which part of the business the
# request belongs to, and — the one that bit — WHO HELD THE RESPONSIBILITY ON
# THAT DAY (`responsibility.resolve(..., on_date)`).
#
# `paid_on` is the day somebody paid a college, which on a real claim is weeks
# or months before they get round to claiming. Naming it here asked the engine
# "who was the HR lead back in August", and on this database the answer was
# nobody: the seat starts on 15 September. The request went straight to
# **blocked** with "Nobody holds HR lead for Payobook Vietnam JSC yet" over a
# seat that was sitting right there, and the Agree button did nothing at all.
#
# An approval route asks who holds the seat NOW, because now is when the
# decision is being made — which is also what the engine's own `repair()` does
# when it unsticks a blocked request (`engine.py:1495`, `context_today`). A
# date field belongs here only when the request is genuinely ABOUT a date in
# the past and the people are meant to be resolved as of it.
register_chain(
    'pb.training.claim', CLAIM_PROCESS_KEY,
    submit_state='submitted',
    driven=('approved',),
    employee_field='employee_id',
    amount_field='amount',
    currency_field='currency_id',
)


def claim_route():
    return route(role_step(_('HR lead'), 'hr_lead'))


class PbTrainingClaimApproval(models.Model):
    _inherit = 'pb.training.claim'

    _approval_process_key = CLAIM_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Training claim · %(who)s · %(course)s",
                 who=self.employee_id.sudo().name or '',
                 course=self.course_name or '')

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().company_id[:1] or self.env.company

    def _chain_facts(self):
        self.ensure_one()
        rec = self.sudo()
        facts = rec._allowance_facts()
        # THE UNIT IS THE CURRENCY, NEVER THE WORD "MONEY" (AM25). A route
        # written as "over 10,000,000" has to mean dong to somebody reading it
        # in Singapore, so the unit is the claim's own currency code.
        unit = rec.currency_id.name or ''
        return {
            'amount': {'value': float(rec.amount or 0.0), 'unit': unit},
            'allowance_left': {'value': float(facts['left']), 'unit': unit},
            'over_allowance': {
                'value': bool(rec.amount > facts['left']), 'unit': ''},
            'course': {'value': rec.course_name or '', 'unit': ''},
            'provider': {'value': rec.provider or '', 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'amount': {'type': 'float', 'label': _('What it cost')},
            'allowance_left': {'type': 'float',
                               'label': _('What is left of their allowance')},
            'over_allowance': {'type': 'bool',
                               'label': _('More than they have left')},
            'course': {'type': 'char', 'label': _('Which course')},
            'provider': {'type': 'char', 'label': _('Who ran it')},
        }

    def _chain_revision_values(self):
        """What the HR lead is agreeing to: this amount and these two files.

        NEVER `write_date` (AM32) and never the allowance — the allowance is
        true of the world rather than of the request, and a stamp over it would
        refuse a perfectly good approval the day somebody set next year's
        budget.
        """
        self.ensure_one()
        return {
            'amount': round(float(self.amount or 0.0), 2),
            'currency': self.currency_id.id,
            'invoice': self.invoice_attachment_id.id,
            'certificate': self.certificate_attachment_id.id,
        }

    def _approval_detail(self, request):
        self.ensure_one()
        from .training_common import money_words
        facts = self.sudo()._allowance_facts()
        chips = [
            {'label': _('Course'), 'value': self.course_name or ''},
            {'label': _('What it cost'),
             'value': money_words(self.env, self.amount, self.currency_id)},
            {'label': _('Paid on'), 'value': str(self.paid_on or '')},
            {'label': _('Allowance left'),
             'value': money_words(self.env, facts['left'], facts['currency'])},
        ]
        if self.provider:
            chips.append({'label': _('Who ran it'), 'value': self.provider})
        if self.amount > facts['left']:
            chips.append({'label': _('Careful'),
                          'value': _('this is more than they have left')})
        rows = []
        if self.invoice_attachment_id:
            rows.append([_('Receipt'), self.invoice_attachment_id.name or ''])
        if self.certificate_attachment_id:
            rows.append([_('Certificate'),
                         self.certificate_attachment_id.name or ''])
        return {'title': _('Paying somebody back for a course'),
                'columns': [_('File'), _('Name')], 'rows': rows,
                'chips': chips, 'note': self.note or ''}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        return Seed.lay(
            company, CLAIM_PROCESS_KEY, 'Training cost claim',
            claim_route(),
            binding_note='Who agrees to pay somebody back for a course they '
                         'paid for themselves. By default the HR lead, who is '
                         'the person the training allowance belongs to. A '
                         'business that wants the head of pay asked as well '
                         'for a large amount adds that rung here, with a '
                         'condition on the amount.',
            model_name='pb.training.claim',
            role_keys=('hr_lead',),
            reason='Set up when training claims were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.training.claim']._approval_seed_default(company):
                done += 1
        except Exception:               # noqa: BLE001 — never die on a seed
            _logger.exception('pb_training: %s has no route for training '
                              'claims', company.name)
    return done
