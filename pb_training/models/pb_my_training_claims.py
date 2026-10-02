# -*- coding: utf-8 -*-
"""`/my/training/claims` — what is left of my allowance, and what I have asked
for.

WHO "ME" IS HAS NOT CHANGED and is still never a parameter. Every method here
resolves the session user's own employee record; no route and no method takes
an employee id, so there is no URL anybody can craft that shows them somebody
else's claims or claims against somebody else's allowance.

THE ALLOWANCE COMES FIRST ON THE PAGE, and that is the design. "How much can I
spend" is the question people come to this page with; the list of what they
have already asked for is what they come back for. A page that opened on an
empty list would answer the second question and leave the first one to an
email.

AND IT SAYS SO WHEN THERE IS NO ALLOWANCE. Zero is an ANSWER — "no training
allowance has been set for 2026, ask the training team" — never an empty box
with a currency symbol beside it.
"""

import logging

from odoo import _, api, fields, models

from .training_common import (
    ASSIGN_OPEN, CLAIM_FULFILMENT_LABEL, CLAIM_STATE_LABEL, money_words,
)

_logger = logging.getLogger(__name__)


class PbMyTrainingClaims(models.AbstractModel):
    _inherit = 'pb.my.training'

    # =====================================================================
    #  the page
    # =====================================================================
    @api.model
    def claims(self, year=None):
        """Everything `/my/training/claims` puts on the screen, in one read."""
        emp = self._my_employee()
        year = int(year or fields.Date.today().year)
        blank = {
            'has_employee': False, 'name': '', 'year': year,
            'allowance': 0.0, 'allowance_words': '', 'agreed': 0.0,
            'agreed_words': '', 'left': 0.0, 'left_words': '',
            'percent': 0, 'set': False, 'rows': [], 'courses': [],
            'waiting': 0, 'currency': '',
        }
        if not emp:
            return blank
        Claim = self.env['pb.training.claim']
        facts = Claim._facts_for(emp, year)
        rows = Claim.sudo().search([('employee_id', '=', emp.id)])
        rows.refresh_fulfilment()
        payload = [self._claim_tile(row) for row in rows]
        return {
            'has_employee': True,
            'name': emp.name or '',
            'year': year,
            'allowance': facts['allowance'],
            'allowance_words': money_words(self.env, facts['allowance'],
                                           facts['currency']),
            'agreed': facts['agreed'],
            'agreed_words': money_words(self.env, facts['agreed'],
                                        facts['currency']),
            'left': facts['left'],
            'left_words': money_words(self.env, facts['left'],
                                      facts['currency']),
            'percent': int(round(100.0 * facts['agreed'] / facts['allowance']))
            if facts['allowance'] else 0,
            'set': bool(facts['allowance']),
            'currency': (facts['currency'].name or ''),
            'rows': payload,
            'waiting': len([r for r in payload if r['state'] == 'submitted']),
            'courses': self._claimable_courses(emp),
        }

    def _claim_tile(self, row):
        """One claim, as a card on a phone.

        THE REFUSAL NOTE IS ON THE CARD. A "turned down" with the reason
        swallowed is the same as nothing happening, which is how a person ends
        up claiming for the same course three times.
        """
        data = row._payload()
        data['state_word'] = CLAIM_STATE_LABEL.get(row.state, '')
        data['money_word'] = CLAIM_FULFILMENT_LABEL.get(row.fulfilment or '',
                                                        '')
        return data

    def _claimable_courses(self, employee):
        """The courses they are on, offered as a starting point on the form.

        IT IS A CONVENIENCE AND NOT A RULE. The ordinary training claim is for
        an OUTSIDE course nobody put them on — that is what a training
        allowance is for — so the course box is free text and this list only
        saves typing when the claim happens to be about one of ours.
        """
        rows = self.env['pb.training.assignment'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ASSIGN_OPEN + ('done',)),
        ], limit=40)
        return [{'id': row.id, 'name': row.channel_id.sudo().name or ''}
                for row in rows if row.channel_id]

    # =====================================================================
    #  making one
    # =====================================================================
    @api.model
    def raise_claim(self, values, invoice=None, certificate=None):
        """One press: the claim is made AND sent in. See `claim.raise_claim`."""
        return self.env['pb.training.claim'].raise_claim(
            values, invoice=invoice, certificate=certificate)

    @api.model
    def claims_count(self):
        """The number on the portal home card. Cheap, and never raises."""
        try:
            emp = self._my_employee()
            if not emp:
                return 0
            return self.env['pb.training.claim'].sudo().search_count(
                [('employee_id', '=', emp.id)])
        except Exception:                   # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: the claims count could not be read',
                            exc_info=True)
            return 0
