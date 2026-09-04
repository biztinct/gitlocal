# -*- coding: utf-8 -*-
"""`pb.budget.fx` — one reporting currency, and an honest refusal to invent one.

WHY THIS FILE EXISTS (ruling D2, second half)
---------------------------------------------
The presentation-currency capability was written inside `pb_demo`
(`pb_demo/models/res_company.py:16-40`) — a demo module, which is the wrong home
for a rule about how a group reports its money. D2 says promote it out.

THE CHOICE MADE HERE, AND WHY IT IS NOT A RELOCATION.
`pb_demo` is INSTALLED on this database and its `res.company.presentation_currency_id`
column already exists and already holds whatever an administrator set. Moving the
FIELD would mean either a second column with the same meaning (two answers to one
question) or editing pb_demo, which changes a demo module's behaviour for the sake
of a budget screen.

So the LOGIC is promoted and the COLUMN is left where it is:

  * every rule about which currency a number is reported in lives HERE, in a
    product module, and nothing in `pb_budget` imports `pb_demo` or depends on it;
  * the field is PROBED — `'presentation_currency_id' in res.company._fields` —
    and used when it is there, which on this database it is;
  * where it is absent (a tenant without pb_demo), the reporting currency is the
    ROOT company's own currency, which is the same answer pb_demo's helper gives
    when nobody has set one.

The result: this module works identically with or without pb_demo, pb_demo's
behaviour is untouched, and there is exactly one definition of "the reporting
currency" in the product. Should the field ever be promoted into a core module
too, this file keeps working — it asks the registry, not a module name.

THE HONESTY RAIL (R23)
----------------------
`currency._convert()` with no rate returns the amount UNCHANGED. It does not
raise and it does not answer zero: 32,000,000 ₫ comes back as "32,000,000 USD".
So before this file converts anything it asks whether the two currencies are
actually reported at DIFFERENT rates. If they are not, nobody has told the
database what a dong is worth, and the honest answer is no number at all.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PbBudgetFx(models.AbstractModel):
    _name = 'pb.budget.fx'
    _description = 'Reporting currency and conversion, for budgets'

    # --------------------------------------------------------------- the rate
    @api.model
    def presentation_currency(self, company=None):
        """The currency a group's budgets are reported in.

        The ROOT company's presentation currency when this build has that field
        and it is set, else the root company's own currency, else the active
        company's. Never `False` — a caller that has to null-check a currency
        writes the null-check in five places and forgets one.
        """
        company = company or self.env.company
        root = company
        # A parent chain is short; the guard is against a cycle, not depth.
        for _hop in range(10):
            if not root.parent_id:
                break
            root = root.parent_id
        if 'presentation_currency_id' in self.env['res.company']._fields:
            picked = root.sudo().presentation_currency_id
            if picked:
                return picked
        return root.currency_id or company.currency_id or self.env.company.currency_id

    @api.model
    def _has_rate(self, currency, day):
        """Has anybody ever told this database what this currency is worth?

        THE PRIMARY TEST, and it had to be. R23's original tell — two different
        currencies coming back at exactly 1.0 — is necessary but not sufficient
        on a database that holds rates for SOME currencies: a currency with no
        rate row at all silently defaults to 1.0, so converting it into one that
        DOES have a rate produces a plausible-looking number built on a fiction.
        A brand-new currency converted into dong came back "known" at 26,330 to
        one, which is the same lie R23 records wearing a different hat. What is
        actually being asked is whether a `res.currency.rate` row exists, so
        that is what is asked.

        AND WHOSE ROW IT IS. A rate row belongs to a COMPANY, and `_get_rates`
        reads only the rows whose company is empty or is the one being
        converted for. So the probe asks exactly what the conversion will ask —
        anything looser answers "known" about a rate the conversion is then not
        allowed to use. On this tenant every rate row belongs to company 1, so
        the operating company genuinely cannot convert, and the per-row manual
        rate is the answer rather than a number nobody can stand behind.
        """
        if not currency:
            return False
        return bool(self.env['res.currency.rate'].sudo().search_count([
            ('currency_id', '=', currency.id), ('name', '<=', day),
            '|', ('company_id', '=', False),
            ('company_id', '=', self.env.company.id)]))

    @api.model
    def rate_known(self, src, dst, date=None):
        """Is there a real exchange rate between these two, or only silence?

        Same currency both sides is trivially known — there is nothing to
        convert. Otherwise BOTH sides need a rate of their own, and the rate
        between them must not be the 1.0 that means "nobody said".
        """
        if not src or not dst or src == dst:
            return True
        day = date or fields.Date.context_today(self)
        if not (self._has_rate(src, day) and self._has_rate(dst, day)):
            return False
        try:
            # `@api.model` on `res.currency` (base/models/res_currency.py:273) —
            # called on the model, with both currencies passed in.
            a = self.env['res.currency']._get_conversion_rate(
                src, dst, self.env.company, day)
        except Exception:                      # noqa: BLE001 — an unknown rate
            _logger.debug('pb_budget: no conversion rate %s -> %s', src.name, dst.name)
            return False
        # A rate of exactly 1.0 between two different currencies is the tell.
        return bool(a) and abs(a - 1.0) > 1e-9

    # ------------------------------------------------------------ the convert
    @api.model
    def convert(self, amount, src, dst, date=None, manual_rate=0.0):
        """`(value, known)` — never a number this file is not sure of.

        `manual_rate` is a MULTIPLIER on the row's own amount: reporting =
        amount x rate. It is the row's answer and it always wins, because a
        person who typed a rate has a reason the database does not know.
        """
        amount = float(amount or 0.0)
        if manual_rate and float(manual_rate) > 0:
            return round(amount * float(manual_rate), 2), True
        if not src or not dst or src == dst:
            return round(amount, 2), True
        if not self.rate_known(src, dst, date):
            return 0.0, False
        day = date or fields.Date.context_today(self)
        try:
            return round(src._convert(amount, dst, self.env.company, day,
                                      round=False), 2), True
        except Exception as e:                 # noqa: BLE001
            _logger.debug('pb_budget: conversion failed: %s', e)
            return 0.0, False

    # ------------------------------------------------------------- the words
    @api.model
    def unknown_rate_note(self, src, dst):
        """What the screen says INSTEAD of a number it cannot stand behind."""
        return _(
            "Nobody has told this system what one %(src)s is worth in %(dst)s, "
            "so these figures stay in %(src)s. Set an exchange rate, or type "
            "one on the budget row itself.",
            src=src.name if src else '', dst=dst.name if dst else '')
