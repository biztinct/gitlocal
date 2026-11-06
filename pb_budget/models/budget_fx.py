# -*- coding: utf-8 -*-
"""`pb.budget.fx` — now a thin shim over `pb.fx` (ruling G3).

WHAT THIS FILE USED TO BE, AND WHY IT IS NOT THAT ANY MORE
----------------------------------------------------------
This file held the product's only honest conversion helper: it refused an
implicit 1.0 between two different currencies, it refused to convert a currency
nobody has ever priced, and it answered `(value, known)` so a screen could show
the parts separately rather than a plausible lie. That behaviour was right, and
GROUP phase 1 promoted it — unchanged in spirit — into `pb.fx`, which is now the
ONE conversion service every screen in this product uses.

Two things made the promotion necessary rather than tidy:

  * a group needs a RATE POLICY (which of a month's rates a figure is converted
    at) and a rate DATE on every converted number, neither of which this file
    could express;
  * the company filter here was `self.env.company`, so a rate row owned by the
    head office was invisible to every subsidiary — the whole of ledger gotcha
    GR2.

WHAT IS PRESERVED, EXACTLY
--------------------------
The public surface: `presentation_currency`, `_has_rate`, `rate_known`,
`convert` (still a TWO-tuple) and `unknown_rate_note`. Every caller in
`pb_budget` and every test it has keeps working with no edit.

And the behaviour, deliberately, to the digit:

  * the budget screen has always converted at the rate on or before a given
    DAY, so the shim asks `pb.fx` for the `payment_date` policy rather than
    letting the group's own policy change a budget number that was signed off
    at the old one;
  * the budget screen has always rounded to two decimal places, so the shim
    asks for two rather than the target currency's own — a dong figure here
    keeps the shape its stored numbers and its tests have.
"""

import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)

#: The budget screen's own reading of a rate: the one in force on the day.
BUDGET_POLICY = 'payment_date'
#: And its own rounding, which its stored numbers and its tests are built on.
BUDGET_DECIMALS = 2


class PbBudgetFx(models.AbstractModel):
    _name = 'pb.budget.fx'
    _description = 'Reporting currency and conversion, for budgets'

    @api.model
    def _fx(self):
        return self.env['pb.fx']

    # --------------------------------------------------------------- the rate
    @api.model
    def presentation_currency(self, company=None):
        """The currency a group's budgets are reported in. Never empty."""
        return self._fx().presentation_currency(company)

    @api.model
    def _has_rate(self, currency, day):
        """Has anybody priced this currency, for the companies that may see
        this one's rates? Widened from the active company alone — see GR2."""
        return self._fx().has_rate(currency, day, policy=BUDGET_POLICY)

    @api.model
    def rate_known(self, src, dst, date=None):
        """Is there a real exchange rate between these two, or only silence?"""
        return self._fx().rate(src, dst, date, policy=BUDGET_POLICY)['known']

    # ------------------------------------------------------------ the convert
    @api.model
    def convert(self, amount, src, dst, date=None, manual_rate=0.0):
        """`(value, known)` — never a number this file is not sure of.

        `manual_rate` is a MULTIPLIER on the row's own amount and it always
        wins, because a person who typed a rate has a reason the database does
        not know.
        """
        value, known, _meta = self._fx().convert(
            amount, src, dst, date, policy=BUDGET_POLICY,
            manual_rate=manual_rate, decimals=BUDGET_DECIMALS)
        return value, known

    # ------------------------------------------------------------- the words
    @api.model
    def unknown_rate_note(self, src, dst):
        """What the screen says INSTEAD of a number it cannot stand behind.

        KEPT HERE rather than delegated, and that is on purpose. `pb.fx`'s
        sentence names the MONTH and points at the exchange-rate list, which is
        the right sentence on a group screen. This one points at the budget
        ROW's own manual rate, which only exists on this screen — a reader here
        would otherwise be sent to look for a door that is not in front of
        them. Same refusal, the words each screen can act on.
        """
        return _(
            "Nobody has told this system what one %(src)s is worth in %(dst)s, "
            "so these figures stay in %(src)s. Set an exchange rate, or type "
            "one on the budget row itself.",
            src=src.name if src else '', dst=dst.name if dst else '')
