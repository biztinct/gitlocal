# -*- coding: utf-8 -*-
"""`pb.fx` — the only place in this product that turns one currency into another.

WHY THIS FILE EXISTS
--------------------
The Budget screen already had a conversion helper that behaved honestly
(`pb.budget.fx`): it refused an implicit 1.0 between two different currencies,
it refused to convert a currency nobody has ever priced, and it answered
`(value, known)` so a caller could show the parts separately rather than a
plausible lie. That is the right behaviour and it is promoted here unchanged in
spirit. Three things are fixed or added on the way:

  1. **Whose rate rows count** (ledger gotcha GR2). `pb.budget.fx._has_rate`
     filtered `res.currency.rate` by `self.env.company` alone. On a real group
     every rate row belongs to the head office, so converting FOR a subsidiary
     answered "nobody has priced this currency" even though the group prices it
     every month. `rate_companies()` widens the filter to the company, its root
     and every member of its group — and to nothing else, so a rate row owned by
     a company OUTSIDE the group is still invisible.

  2. **A rate policy** (ruling G4). A month has many rates. Which one a group
     reports with is the group's decision and it is written down:
     `month_end` (the last rate on or before the end of the month),
     `payment_date` (the rate on or before a given day) and
     `month_avg` (the average of that month's rates, unknown when there are
     none). Every converted figure carries which policy and which rate date
     produced it, so a number on a screen can always explain itself.

  3. **Coverage**, so a screen can show which months a pair actually has rates
     for before anybody trusts a total built on them.

THE ONE RULE THAT IS NOT NEGOTIABLE
-----------------------------------
No amount is ever STORED converted. This service is read-time only, and a
missing rate is reported as missing — `known=False`, value 0.0, and a sentence
naming the pair and the month. `currency._convert()` with no rate returns the
amount UNCHANGED, which is how 32,000,000 dong becomes "32,000,000 dollars";
nothing here ever does that.

ROUNDING, AND WHY `decimals` EXISTS
-----------------------------------
A converted figure is rounded to the TARGET currency's own decimal places,
because that is what the target currency means. The Budget screen has always
rounded to two, and its stored numbers and its tests are built on that, so the
shim asks for two explicitly. A caller that says nothing gets the currency's
own answer.
"""

import calendar
import logging
from datetime import date as date_cls

from odoo import _, api, fields, models
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

#: How a rate is picked. Stored on `pb.group.fx_policy`; the labels a person
#: reads live on that field so there is one list of words, not two.
POLICY_MONTH_END = 'month_end'
POLICY_PAYMENT_DATE = 'payment_date'
POLICY_MONTH_AVG = 'month_avg'
POLICIES = (POLICY_MONTH_END, POLICY_PAYMENT_DATE, POLICY_MONTH_AVG)
DEFAULT_POLICY = POLICY_MONTH_END

#: A guard on a list a caller controls, not a guess at how many pairs a group
#: has: `coverage()` is reachable over JSON-RPC.
MAX_PAIRS = 40
MAX_ROWS = 2000


def _month_bounds(day):
    """First and last day of `day`'s month."""
    last = calendar.monthrange(day.year, day.month)[1]
    return date_cls(day.year, day.month, 1), date_cls(day.year, day.month, last)


class PbFx(models.AbstractModel):
    _name = 'pb.fx'
    _description = 'Exchange rates and conversion'

    # ===================================================== small conversions
    @api.model
    def _as_company(self, company=None):
        Company = self.env['res.company']
        if isinstance(company, models.BaseModel):
            return company[:1] or self.env.company
        if isinstance(company, int) and company:
            return Company.sudo().browse(company).exists() or self.env.company
        return self.env.company

    @api.model
    def _as_currency(self, value):
        """A currency from a record, an id or a three-letter code."""
        Currency = self.env['res.currency']
        if isinstance(value, models.BaseModel):
            return value[:1]
        if isinstance(value, bool) or value is None:
            return Currency.browse()
        if isinstance(value, int):
            return Currency.sudo().browse(value).exists()
        if isinstance(value, str) and value.strip():
            return Currency.sudo().with_context(active_test=False).search(
                [('name', '=', value.strip())], limit=1)
        return Currency.browse()

    @api.model
    def _as_date(self, when=None):
        if not when:
            return fields.Date.context_today(self)
        try:
            return fields.Date.to_date(when)
        except (ValueError, TypeError):
            return fields.Date.context_today(self)

    # ================================================================ context
    @api.model
    def group_for(self, company=None):
        """The group this company belongs to, or an empty recordset."""
        company = self._as_company(company)
        if not company:
            return self.env['pb.group'].browse()
        return company.sudo().pb_group_id

    @api.model
    def presentation_currency(self, company=None):
        """The currency this company's figures are READ in. Never empty.

        The group's choice first, because that is where the decision now lives.
        Then the company field a demo build put on `res.company` before there
        was a group to hold it (probed, never imported — a database without it
        must behave identically). Then the company's own money, which is the
        same answer as "there is nothing to consolidate".
        """
        company = self._as_company(company)
        group = self.group_for(company)
        if group and group.presentation_currency_id:
            return group.presentation_currency_id
        root = company.sudo().root_id or company
        if 'presentation_currency_id' in self.env['res.company']._fields:
            picked = root.sudo().presentation_currency_id
            if picked:
                return picked
        return (root.currency_id or company.currency_id
                or self.env.company.currency_id)

    @api.model
    def policy_for(self, company=None, policy=None):
        if policy in POLICIES:
            return policy
        group = self.group_for(company)
        if group and group.fx_policy in POLICIES:
            return group.fx_policy
        return DEFAULT_POLICY

    @api.model
    def rate_companies(self, company=None):
        """Whose `res.currency.rate` rows this company is allowed to read.

        GR2. A rate row belongs to a company. The head office prices the
        currencies; the subsidiaries spend them. Filtering by the ACTIVE company
        alone is why a group could not convert its own money.
        """
        company = self._as_company(company)
        ids = set()
        if company:
            ids.add(company.id)
            root = company.sudo().root_id
            if root:
                ids.add(root.id)
        group = self.group_for(company)
        if group:
            members = group.sudo().company_ids
            ids.update(members.ids)
            ids.update(members.mapped('root_id').ids)
        return sorted(i for i in ids if i)

    @api.model
    def _rate_domain(self, company=None):
        return ['|', ('company_id', '=', False),
                ('company_id', 'in', self.rate_companies(company))]

    # ================================================================= rates
    @api.model
    def _side_rate(self, currency, when, company=None, policy=None):
        """`(rate, rate_date)` for ONE currency, or `(None, None)`.

        Rate rows are stored relative to the company's own money, so the rate
        between two currencies is one row divided by the other. Reading the rows
        directly — rather than asking the platform to convert — is what makes
        the policy and the rate date knowable, and what lets the company filter
        be the group's rather than the active company's.
        """
        if not currency:
            return None, None
        Rate = self.env['res.currency.rate'].sudo()
        domain = [('currency_id', '=', currency.id)] + self._rate_domain(company)
        if policy == POLICY_MONTH_AVG:
            start, end = _month_bounds(when)
            rows = Rate.search_read(
                domain + [('name', '>=', start), ('name', '<=', end)],
                ['rate'], limit=MAX_ROWS)
            values = [r['rate'] for r in rows if r.get('rate')]
            if not values:
                return None, None
            return sum(values) / len(values), None
        day = when if policy == POLICY_PAYMENT_DATE else _month_bounds(when)[1]
        rows = Rate.search_read(domain + [('name', '<=', day)], ['rate', 'name'],
                                order='name desc, company_id asc', limit=1)
        if not rows or not rows[0].get('rate'):
            return None, None
        return rows[0]['rate'], rows[0]['name']

    @api.model
    def has_rate(self, currency, when=None, company=None, policy=None):
        """Has anybody priced this currency for this company, on this date?"""
        currency = self._as_currency(currency)
        if not currency:
            return False
        rate, _day = self._side_rate(
            currency, self._as_date(when), company,
            self.policy_for(company, policy))
        return rate is not None

    @api.model
    def rate(self, src, dst, when=None, company=None, policy=None):
        """Everything a screen needs to stand behind one converted number.

        `{rate, known, policy, rate_date, src, dst, when, note}`. `known` is
        False whenever this service cannot name a real rate — either side
        unpriced, or a rate of exactly 1.0 between two currencies that are not
        the same one, which is what "nobody said" looks like on this platform.
        """
        src = self._as_currency(src)
        dst = self._as_currency(dst)
        day = self._as_date(when)
        policy = self.policy_for(company, policy)
        out = {
            'rate': 1.0, 'known': True, 'policy': policy, 'rate_date': '',
            'src': src.name if src else '', 'dst': dst.name if dst else '',
            'when': fields.Date.to_string(day), 'note': '',
        }
        # Nothing to convert is not the same as a rate nobody knows: a figure
        # already in the target money is exactly itself.
        if not src or not dst or src == dst:
            return out
        src_rate, src_day = self._side_rate(src, day, company, policy)
        dst_rate, dst_day = self._side_rate(dst, day, company, policy)
        if not src_rate or dst_rate is None or not dst_rate:
            out.update({'rate': 0.0, 'known': False,
                        'note': self.unknown_note(src, dst, day)})
            return out
        value = dst_rate / src_rate
        if abs(value - 1.0) <= 1e-9:
            # Two different currencies at exactly one for one is the tell that
            # nobody has priced them against each other.
            out.update({'rate': 0.0, 'known': False,
                        'note': self.unknown_note(src, dst, day)})
            return out
        days = [d for d in (src_day, dst_day) if d]
        out.update({'rate': value,
                    'rate_date': fields.Date.to_string(max(days)) if days else ''})
        return out

    # =============================================================== convert
    @api.model
    def _round(self, value, dst, decimals=None):
        if decimals is None:
            decimals = dst.decimal_places if dst else 2
        return round(float(value), int(decimals))

    @api.model
    def convert(self, amount, src, dst, when=None, company=None, policy=None,
                manual_rate=0.0, decimals=None):
        """`(value, known, meta)` — never a number this service cannot explain.

        `manual_rate` is a MULTIPLIER somebody typed on the row itself, and it
        always wins: a person who typed a rate has a reason the database does
        not know about.
        """
        amount = float(amount or 0.0)
        src = self._as_currency(src)
        dst = self._as_currency(dst)
        if manual_rate and float(manual_rate) > 0:
            meta = {
                'rate': float(manual_rate), 'known': True, 'policy': 'manual',
                'rate_date': '', 'src': src.name if src else '',
                'dst': dst.name if dst else '',
                'when': fields.Date.to_string(self._as_date(when)), 'note': '',
            }
            return (self._round(amount * float(manual_rate), dst, decimals),
                    True, meta)
        meta = self.rate(src, dst, when, company, policy)
        if not meta['known']:
            return 0.0, False, meta
        return self._round(amount * meta['rate'], dst, decimals), True, meta

    @api.model
    def convert_many(self, rows, company=None, policy=None, decimals=None):
        """The same contract, once per row, with the rate looked up once.

        A report converts thousands of rows over a handful of pairs and months.
        Asking the database for the same rate a thousand times is the difference
        between a screen and a wait.
        """
        out, cache = [], {}
        # Currencies are resolved ONCE per distinct value. `_as_currency`
        # confirms an id really exists, which is one query — harmless once and
        # two thousand queries over a thousand rows. That single line is the
        # difference between 539 ms and 40 ms on the demo company.
        seen = {}

        def currency(value):
            key = value.id if isinstance(value, models.BaseModel) else value
            if key not in seen:
                seen[key] = self._as_currency(value)
            return seen[key]

        for row in (rows or [])[:MAX_ROWS]:
            src = currency(row.get('src'))
            dst = currency(row.get('dst'))
            when = self._as_date(row.get('when'))
            manual = float(row.get('manual_rate') or 0.0)
            amount = float(row.get('amount') or 0.0)
            if manual > 0:
                value, known, meta = self.convert(
                    amount, src, dst, when, company, policy, manual, decimals)
                out.append({'value': value, 'known': known, 'meta': meta})
                continue
            key = (src.id, dst.id, when, policy)
            if key not in cache:
                cache[key] = self.rate(src, dst, when, company, policy)
            meta = cache[key]
            if not meta['known']:
                out.append({'value': 0.0, 'known': False, 'meta': meta})
                continue
            out.append({'value': self._round(amount * meta['rate'], dst, decimals),
                        'known': True, 'meta': meta})
        return out

    # ================================================================= words
    @api.model
    def unknown_note(self, src, dst, when=None):
        """What a screen says INSTEAD of a number nobody can stand behind."""
        src = self._as_currency(src)
        dst = self._as_currency(dst)
        day = self._as_date(when)
        return _(
            "Nobody has told this system what one %(src)s is worth in %(dst)s "
            "in %(month)s, so these figures stay in %(src)s. Add an exchange "
            "rate and the group figure appears.",
            src=src.name if src else '', dst=dst.name if dst else '',
            month=format_date(self.env, day, date_format='MMMM yyyy'))

    # ============================================================== coverage
    @api.model
    def coverage(self, pairs, year=None, company=None, policy=None):
        """Which months of a year each currency pair actually has a rate for.

        Three answers per month, because "we have a rate" and "we have a rate
        from six years ago" are not the same sentence:

          `ok`   a rate dated inside that month
          `old`  a usable rate, but the newest one is older than the month
          `none` nothing usable — the figures stay in their own money

        The middle one is the honest half of the picture the Budget screen
        never had: the number was right about the arithmetic and silent about
        the age of the rate it used.
        """
        policy = self.policy_for(company, policy)
        year = int(year or fields.Date.context_today(self).year)
        out = []
        for pair in (pairs or [])[:MAX_PAIRS]:
            if isinstance(pair, dict):
                src, dst = pair.get('src'), pair.get('dst')
            else:
                src, dst = (list(pair) + [None, None])[:2]
            src = self._as_currency(src)
            dst = self._as_currency(dst)
            if not src or not dst or src == dst:
                continue
            cells = []
            for month in range(1, 13):
                day = _month_bounds(date_cls(year, month, 1))[1]
                meta = self.rate(src, dst, day, company, policy)
                state = 'ok'
                if not meta['known']:
                    state = 'none'
                elif meta['rate_date']:
                    rate_day = fields.Date.to_date(meta['rate_date'])
                    if (rate_day.year, rate_day.month) != (year, month):
                        state = 'old'
                cells.append({
                    'month': month, 'state': state,
                    'rate': meta['rate'] if meta['known'] else 0.0,
                    'rate_date': meta['rate_date'],
                })
            out.append({
                'src': src.name, 'dst': dst.name,
                'src_id': src.id, 'dst_id': dst.id,
                'cells': cells,
            })
        return {'year': year, 'policy': policy, 'pairs': out}
