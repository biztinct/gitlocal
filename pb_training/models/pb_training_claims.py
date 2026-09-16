# -*- coding: utf-8 -*-
"""The Claims tab's server surface — the queue, and the allowance behind it.

THE QUESTION THIS TAB ANSWERS is "whose money is waiting on me". So the order
is PROBLEM FIRST (R113): what has been sent in and nobody has answered, then
what has been agreed and not paid, then the rest — and the tiles count the
three things somebody can act on rather than the three things that are easy to
count.

THE ALLOWANCE PANEL IS ON THE SAME TAB ON PURPOSE. A queue of claims with no
sight of the budget they come out of is a queue somebody approves one at a time
until the money is gone. The panel is the year's figure per company, what has
been agreed against it and what is left — read from the same helper the refusal
sentence uses, so the number on the screen and the number in the refusal can
never disagree.

Same doctrine as the other two tabs: `@api.model` reads, every independent
probe inside its own `_safe()`, row caps that are PARAMETERS, and no sudo in a
read except where a field's own `groups=` forces it.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pb_training_assignments import PbTrainingAssignments
from .training_common import (
    CLAIM_FULFILMENT, CLAIM_STATES, P_CLAIM_LIMIT, P_CLAIM_OVER, as_id, fold,
    flag, money_words, number,
)

_logger = logging.getLogger(__name__)


class PbTrainingClaims(models.AbstractModel):
    _inherit = 'pb.training'

    #: E1's and E2's verbs plus this phase's. Written as the base tuple PLUS
    #: the new ones rather than as a fresh list, so a verb an earlier phase
    #: adds later is not silently dropped by this extension.
    _VERBS = PbTrainingAssignments._VERBS + (
        'approve_claim', 'refuse_claim', 'open_claim', 'new_claim',
        'open_claims', 'open_allowances', 'new_allowance', 'send_pack',
        'open_award',
    )

    # =====================================================================
    #  the tab
    # =====================================================================
    @api.model
    def get_claims(self, filters=None):
        """Every row, every number and the allowance panel, in one read."""
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'kpis': {}}
        filters = filters or {}
        rows = self._safe(lambda: self._claim_rows(filters), default=[])
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'can_admin': self._can_admin(),
            'rows': rows,
            'kpis': self._safe(lambda: self._claim_kpis(rows), default={}),
            'allowances': self._safe(lambda: self._allowance_rows(),
                                     default=[]),
            'states': [{'key': k, 'label': v} for k, v in CLAIM_STATES],
            'fulfilments': [{'key': k, 'label': v}
                            for k, v in CLAIM_FULFILMENT],
            'pack': self._safe(
                lambda: self.env['pb.training.pack'].status(), default={}),
            'over_allowed': flag(self.env, P_CLAIM_OVER),
            'year': fields.Date.today().year,
        }

    def _claim_rows(self, filters):
        cap = number(self.env, P_CLAIM_LIMIT, 200)
        domain = [('company_id', 'in', self.env.companies.ids)]
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        if filters.get('year'):
            domain.append(('year', '=', int(filters['year'])))
        claims = self.env['pb.training.claim'].sudo().search(domain, limit=cap)
        # The award may have moved since anybody last looked — somebody put it
        # into a pay run this morning — so the money column is brought up to
        # date as it is read. A board that says "waiting for a pay run" over an
        # award that was paid last week is a board nobody trusts twice.
        claims.refresh_fulfilment()
        out = [row._payload() for row in claims]
        needle = fold(filters.get('term') or '')
        if needle:
            out = [r for r in out
                   if needle in fold(r['who']) or needle in fold(r['course'])]
        rank = {'submitted': 0, 'approved': 1, 'draft': 2, 'refused': 3}
        return sorted(out, key=lambda r: (rank.get(r['state'], 4),
                                          r['fulfilment'] == 'paid',
                                          -r['id']))

    def _claim_kpis(self, rows):
        waiting = [r for r in rows if r['state'] == 'submitted']
        agreed = [r for r in rows if r['state'] == 'approved']
        unpaid = [r for r in agreed if r['fulfilment'] != 'paid']
        total = sum(r['amount'] for r in agreed)
        return {
            'waiting': len(waiting),
            'waiting_value': sum(r['amount'] for r in waiting),
            'waiting_words': money_words(
                self.env, sum(r['amount'] for r in waiting)),
            'agreed': len(agreed),
            'agreed_words': money_words(self.env, total),
            'unpaid': len(unpaid),
            'unpaid_words': money_words(
                self.env, sum(r['amount'] for r in unpaid)),
            'total': len(rows),
        }

    def _allowance_rows(self):
        """The year's allowance per company, and what is left of it.

        THE COMPANY-WIDE FIGURE AND NOT A ROW PER PERSON. Four thousand rows
        of the same number is not a panel; the people with their own figure are
        listed underneath it, which is the short list that is worth reading.
        """
        year = fields.Date.today().year
        Allowance = self.env['pb.training.allowance'].sudo()
        Claim = self.env['pb.training.claim'].sudo()
        out = []
        for company in self.env['res.company'].sudo().browse(
                self.env.companies.ids):
            row = Allowance.search([
                ('company_id', '=', company.id), ('year', '=', year),
                ('employee_id', '=', False)], limit=1)
            agreed = sum(Claim.search([
                ('company_id', '=', company.id), ('year', '=', year),
                ('state', '=', 'approved')]).mapped('amount'))
            currency = row.currency_id or company.currency_id
            overrides = Allowance.search([
                ('company_id', '=', company.id), ('year', '=', year),
                ('employee_id', '!=', False)])
            out.append({
                'company_id': company.id,
                'company': company.name or '',
                'year': year,
                'id': row.id,
                'amount': row.amount if row else 0.0,
                'amount_words': money_words(self.env,
                                            row.amount if row else 0.0,
                                            currency),
                'agreed': agreed,
                'agreed_words': money_words(self.env, agreed, currency),
                'set': bool(row),
                'people': [{
                    'id': one.id,
                    'who': one.employee_id.sudo().name or '',
                    'amount_words': money_words(self.env, one.amount,
                                                one.currency_id),
                } for one in overrides],
            })
        return out

    # =====================================================================
    #  the things the tab does
    # =====================================================================
    def _claim(self, claim_id):
        row = self.env['pb.training.claim'].sudo().browse(
            as_id(claim_id)).exists()
        if not row:
            raise UserError(_("That claim is not here any more."))
        return row

    @api.model
    def approve_claim(self, claim_id):
        """Agree it. THE PRESS SAYS WHAT SOMEBODY MEANS (AM84).

        The engine says whether it may happen — and it is the engine, not this
        method, that checks the person pressing holds the seat the published
        route asked for. Running it as the caller is the whole point: a sudo
        here would let anybody who can reach this screen agree money.
        """
        self._require_write()
        claim = self._claim(claim_id)
        claim.with_user(self.env.user).action_approve()
        award = claim.incentive_id.sudo()
        if not award:
            return {'message': _("Agreed.")}
        return {'message': _(
            "Agreed. %(amount)s is now an award waiting for a pay run — the "
            "pay team puts it into one from the Awards screen.",
            amount=money_words(self.env, claim.amount, claim.currency_id))}

    @api.model
    def refuse_claim(self, claim_id, note=''):
        self._require_write()
        claim = self._claim(claim_id)
        note = (note or '').strip()[:2000]
        if not note:
            raise UserError(_(
                "Say why. Somebody is being told no about money they have "
                "already spent, and a refusal with no reason is one they will "
                "ask about in an email instead."))
        claim.sudo().write({'refuse_note': note})
        claim.with_user(self.env.user).action_refuse_chain(note)
        return {'message': _("Turned down, and they have been told why.")}

    @api.model
    def send_pack(self):
        """Send the pack now. Managers only — it sends email."""
        answer = self.env['pb.training.pack'].run_now()
        return {'message': answer.get('msg') or ''}

    # =====================================================================
    #  the doors
    # =====================================================================
    @api.model
    def open_claim(self, claim_id):
        self._require_read()
        return self._door(_("Training claim"), 'pb.training.claim',
                          res_id=claim_id)

    @api.model
    def open_claims(self):
        self._require_read()
        return self._door(_("Training claims"), 'pb.training.claim')

    @api.model
    def new_claim(self):
        """A blank claim, raised by the training team for somebody else.

        THE EMPLOYEE'S OWN PAGE IS THE ORDINARY DOOR and this is the other
        one: plenty of companies have somebody in HR who types these up from a
        pile of receipts, and a product that only has the self-service form
        makes that person use somebody else's login.
        """
        self._require_write()
        return self._door(_("New training claim"), 'pb.training.claim',
                          view_mode='form')

    @api.model
    def open_allowances(self):
        self._require_read()
        return self._door(_("Training allowances"), 'pb.training.allowance')

    @api.model
    def new_allowance(self):
        self._require_write()
        return self._door(_("New training allowance"),
                          'pb.training.allowance', view_mode='form')

    @api.model
    def open_award(self, incentive_id):
        """The award a claim became, on its own form."""
        self._require_read()
        return self._door(_("Award"), 'pb.incentive', res_id=incentive_id)

    # =====================================================================
    #  the dispatcher
    # =====================================================================
    @api.model
    def act(self, verb, payload=None):
        payload = payload or {}
        if verb == 'approve_claim':
            return self.approve_claim(payload.get('claim_id'))
        if verb == 'refuse_claim':
            return self.refuse_claim(payload.get('claim_id'),
                                     payload.get('note'))
        if verb == 'open_claim':
            return self.open_claim(payload.get('claim_id'))
        if verb == 'open_award':
            return self.open_award(payload.get('incentive_id'))
        return super().act(verb, payload)
