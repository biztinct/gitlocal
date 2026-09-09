# -*- coding: utf-8 -*-
"""`pb.budget` — the Budget lens's facade.

One read builds the whole board: the year, its twelve months, every function the
reader is allowed to see, what each was given, what each has spent, and how that
compares with WHERE THE YEAR IS. That last comparison is the point of the whole
screen — "70% spent" is neither good nor bad until you know whether it is March
or November.

THE BOUNDARY IS ENFORCED HERE AND IN THE RECORD RULES, BOTH.
Every read below runs with the caller's own rights — no sudo on the budget rows —
so `ir.rule` is what decides which functions come back, and the facade's own gate
decides whether the screen opens at all. Two locks on one door, deliberately: the
rules protect the model from every other route into it, and the gate means a
person who holds nothing gets one plain sentence instead of a raw permission
error out of the ORM.

WHAT IT NEVER DOES
  * It never sums two currencies as though they were one. Where the budgets in
    scope are in more than one currency, everything is reported in the group's
    reporting currency; where a rate for that is missing, the affected rows are
    NAMED and left out rather than converted at one for one (R23).
  * It never writes. Writing is the upload wizard, the expense model and the
    actuals job — three doors, each with its own permission.
"""

import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .budget_common import (BOARD_ROW_CAP, BUDGET_TYPES, EXPENSE_ROW_CAP,
                            TYPE_KEYS, counted, fold, param_int, safe,
                            type_label)

_logger = logging.getLogger(__name__)

#: Anybody holding one of these may open the board; what they then SEE is the
#: record rules' business, not this tuple's.
GATE_GROUPS = (
    'pb_budget.group_budget_viewer',
    'pb_budget.group_budget_manager',
    'pb_budget.group_budget_finance',
)
EDIT_GROUPS = (
    'pb_budget.group_budget_manager',
)
#: How far ahead of the calendar a function has to be before the board calls it
#: hot. Five points of the year is roughly a fortnight — inside the noise of
#: when a pay run happens to land; fifteen is a month and a half, which is not.
WATCH_AT = 5.0
OVER_AT = 15.0
CALM_AT = -10.0
#: How far a MONTH may sit from its own budget before the board calls it over
#: or under it. A month is not a year: there is no calendar to run ahead of
#: inside one, so the comparison is simply the budget, and five points either
#: way is the noise of which side of a month-end a pay run happened to land.
MONTH_BAND = 5.0


class PbBudget(models.AbstractModel):
    _name = 'pb.budget'
    _description = 'Budget board — read-only facade'

    # ================================================================= access
    @api.model
    def _is_admin(self):
        return self.env.user.has_group('base.group_system')

    @api.model
    def _has(self, groups):
        for g in groups:
            try:
                if self.env.user.has_group(g):
                    return True
            except (ValueError, KeyError):     # the group is not on this DB
                continue
        return False

    @api.model
    def _require(self):
        if self._is_admin() or self._has(GATE_GROUPS):
            return
        raise AccessError(_(
            "Budgets are shown to the people who hold one — a function head, "
            "the budget team or finance. Ask an administrator to add you if "
            "you should be seeing this."))

    @api.model
    def _require_edit(self):
        if self._is_admin() or self._has(EDIT_GROUPS):
            return
        raise AccessError(_(
            "Only the budget team can change a budget. You can read the "
            "figures and export them."))

    @api.model
    def can_edit(self):
        return bool(self._is_admin() or self._has(EDIT_GROUPS))

    # ================================================================ the year
    @api.model
    def _fy_start_month(self):
        m = param_int(self.env, 'pb_budget.fy_start_month', 1)
        return m if 1 <= m <= 12 else 1

    @api.model
    def _fy_months(self, fy):
        start_month = self._fy_start_month()
        first = date(int(fy), start_month, 1)
        return [first + relativedelta(months=i) for i in range(12)]

    @api.model
    def _fy_label(self, fy):
        if self._fy_start_month() == 1:
            return str(fy)
        return '%s/%s' % (fy, str(int(fy) + 1)[-2:])

    @api.model
    def _current_fy(self, today=None):
        today = today or fields.Date.context_today(self)
        start_month = self._fy_start_month()
        return today.year if today.month >= start_month else today.year - 1

    @api.model
    def _pace(self, fy, today=None):
        """How far through the year the CALENDAR is, 0–100.

        Whole months elapsed plus the fraction of the one we are in — a budget
        board that jumps ten points on the first of the month tells people the
        wrong thing for a fortnight either side of it.
        """
        today = today or fields.Date.context_today(self)
        months = self._fy_months(fy)
        first, last = months[0], months[-1]
        if today < first:
            return 0.0
        if today > last + relativedelta(months=1) - relativedelta(days=1):
            return 100.0
        elapsed = (today.year - first.year) * 12 + (today.month - first.month)
        days_in = (first + relativedelta(months=elapsed + 1)
                   - first - relativedelta(months=elapsed)).days or 30
        return round(min(100.0, (elapsed + (today.day - 1) / days_in) / 12 * 100), 1)

    # =============================================================== a period
    # A PERIOD IS A SCOPE, EQUAL TO THE YEAR (TIDY rule 13, LOOK rule 18).
    # Everything the year view has — the numbers, the words, the colours, the
    # drill and the exports — a month has too, and so does a STRETCH of months.
    # A period never becomes a filter on a year board: it replaces the year as
    # the thing every figure is about.
    #
    # ONE VOCABULARY, THREE SHAPES (LOOK P3 R1/R2). Everything downstream is
    # handed `mkeys` — the ordered list of month keys the scope covers, which
    # for the whole year is all twelve. A month, a quarter, "March to June" and
    # the year are then ONE code path with a different list, which is what makes
    # rule 18 a property of the code rather than a promise about it. A stretch
    # of exactly one month IS a month and a stretch of twelve IS the year, so
    # nothing downstream ever has two ways to say the same thing.
    @api.model
    def _month_keys(self, fy):
        return [m.strftime('%Y-%m') for m in self._fy_months(fy)]

    @api.model
    def _month_date(self, key):
        """`'2026-03'` -> 1 March 2026, or None if it is not a month at all."""
        try:
            year, mon = str(key or '').split('-')
            return date(int(year), int(mon), 1)
        except (TypeError, ValueError):
            return None

    @api.model
    def _month_bounds(self, key):
        first = self._month_date(key)
        return first, first + relativedelta(months=1) - relativedelta(days=1)

    @api.model
    def _month_in_fy(self, month, fy):
        """The month asked for, only if it is one of THIS year's twelve.

        A deep link that names a month outside the year on screen is not an
        error and never an empty board: it falls back to the whole year, which
        is what the reader would have got had they not been sent anywhere.
        `'current'` is accepted so a saved link or a palette row can mean
        "this month" for ever rather than rotting on a fixed date.
        """
        key = str(month or '').strip()
        if key == 'current':
            key = fields.Date.context_today(self).strftime('%Y-%m')
        return key if key in self._month_keys(fy) else ''

    @api.model
    def _month_state(self, key, today=None):
        today = today or fields.Date.context_today(self)
        first, last = self._month_bounds(key)
        if today < first:
            return 'future'
        if today > last:
            return 'past'
        return 'current'

    @api.model
    def _month_pace(self, key, today=None):
        """How far through the MONTH the calendar is, 0–100.

        A finished month is 100 and a month that has not started is 0, so the
        notch on every tile means the same thing it means on the year board:
        where the calendar is.
        """
        today = today or fields.Date.context_today(self)
        first, last = self._month_bounds(key)
        if today > last:
            return 100.0
        if today < first:
            return 0.0
        return round((today.day - 1) / last.day * 100, 1)

    @api.model
    def _month_words(self, day, full=False):
        """The month's name in the reader's own language.

        `strftime` answers in the SERVER's locale, which is C — so a Vietnamese
        reader would be shown "Mar" on a screen where every other word is
        Vietnamese. Babel ships with the platform and knows the reader's.
        """
        try:
            from babel.dates import format_date
            return format_date(
                day, 'LLLL' if full else 'LLL',
                locale=(self.env.context.get('lang') or 'en_US'))
        except Exception:                          # noqa: BLE001
            return day.strftime('%B' if full else '%b')

    @api.model
    def _month_title(self, day):
        """"March 2026" — the month AND the year, because a budget figure with
        no year on it is the one number nobody can check."""
        try:
            from babel.dates import format_date
            return format_date(day, 'LLLL y',
                               locale=(self.env.context.get('lang') or 'en_US'))
        except Exception:                          # noqa: BLE001
            return day.strftime('%B %Y')

    @api.model
    def _short(self, value):
        """The same four characters the tiles print.

        A sentence about a tile and the tile itself must never disagree, so the
        server rounds money for a SENTENCE exactly as the browser rounds it for
        a tile — 12.4bn in both places, never 12.4bn beside 12,431,004,522.
        """
        val = float(value or 0.0)
        size = abs(val)
        if size >= 1e12:
            return '%.1ftn' % (val / 1e12)
        if size >= 1e9:
            return '%.1fbn' % (val / 1e9)
        if size >= 1e6:
            return '%.1fm' % (val / 1e6)
        if size >= 1e3:
            return '%.0fk' % (val / 1e3)
        return '{:,.0f}'.format(val)

    # ----------------------------------------------------------- a stretch
    @api.model
    def _fy_quarters(self, fy):
        """The four quarters of the FISCAL year, whatever month it starts in.

        A company whose year opens in July has a Q1 of July, August and
        September, and the chip's own words say so — a reader on a July start
        is never left guessing which three months "Q1" means (R5).
        """
        keys = self._month_keys(fy)
        out = []
        for i in range(4):
            span = keys[i * 3:(i + 1) * 3]
            out.append({
                'key': 'Q%s' % (i + 1),
                'label': 'Q%s' % (i + 1),
                'name': self._quarter_name(i + 1, fy),
                'title': self._span_words(self._month_date(span[0]),
                                          self._month_date(span[-1])),
                'keys': span,
            })
        return out

    @api.model
    def _quarter_name(self, n, fy):
        """"Q2 2026", and "Q1 2026/27" where the year is not the calendar's."""
        return _("Q%(n)s %(year)s", n=n, year=self._fy_label(fy))

    @api.model
    def _quarter_of(self, mkeys, fy):
        """The quarter these months ARE, or nothing. Never "roughly"."""
        want = list(mkeys or [])
        for q in self._fy_quarters(fy):
            if q['keys'] == want:
                return q['key']
        return ''

    @api.model
    def _span_words(self, first, last):
        """"April to June" — one format string, never two glued fragments, or
        no translator can put the words in their own order."""
        return _("%(first)s to %(last)s",
                 first=self._month_words(first, full=True),
                 last=self._month_words(last, full=True))

    @api.model
    def _period_in_fy(self, period, fy):
        """The months a period covers, in order, always inside THIS year.

        Accepts nothing (the whole year), `'YYYY-MM'`, `'current'`,
        `'YYYY-MM..YYYY-MM'` and `'Q1'`…`'Q4'`. A stretch that hangs off the end
        of the year is CLAMPED to it; one that lands entirely outside it, and
        anything this cannot read at all, falls back to the whole year. A saved
        link is never an error and never a blank board (ledger rule 21), and
        `'current'` goes on meaning "now" for ever so a bookmark cannot rot.
        """
        keys = self._month_keys(fy)
        raw = str(period or '').strip()
        if not raw:
            return list(keys)
        if raw.upper() in ('Q1', 'Q2', 'Q3', 'Q4'):
            n = int(raw[1])
            return list(keys[(n - 1) * 3:n * 3])
        if '..' in raw:
            lo_raw, _sep, hi_raw = raw.partition('..')
            lo = self._month_date(self._as_month_key(lo_raw))
            hi = self._month_date(self._as_month_key(hi_raw))
            if not lo or not hi:
                return list(keys)
            if lo > hi:                      # dragged right to left; same span
                lo, hi = hi, lo
            span = [k for k in keys if lo <= self._month_date(k) <= hi]
            return span or list(keys)
        one = self._month_in_fy(raw, fy)
        return [one] if one else list(keys)

    @api.model
    def _as_month_key(self, raw):
        """One end of a stretch, with `'current'` resolved to this month."""
        key = str(raw or '').strip()
        if key == 'current':
            return fields.Date.context_today(self).strftime('%Y-%m')
        return key

    @api.model
    def _period_pace(self, mkeys, today=None):
        """How far the calendar is through the STRETCH, 0–100.

        Wholly behind us is 100, wholly ahead is 0, and one we are standing
        inside is the share of its days that have gone. It is `_month_pace`'s
        own idea widened, not a second one: over a single month the two answer
        the same number to the decimal, which is the point of T6.
        """
        keys = list(mkeys or [])
        if not keys:
            return 0.0
        today = today or fields.Date.context_today(self)
        first = self._month_date(keys[0])
        last = self._month_bounds(keys[-1])[1]
        if today > last:
            return 100.0
        if today < first:
            return 0.0
        total = (last - first).days + 1
        return round(min(100.0, (today - first).days / total * 100), 1)

    @api.model
    def _period_state(self, mkeys, today=None):
        today = today or fields.Date.context_today(self)
        keys = list(mkeys or [])
        if not keys:
            return 'current'
        first = self._month_date(keys[0])
        last = self._month_bounds(keys[-1])[1]
        if today < first:
            return 'future'
        if today > last:
            return 'past'
        return 'current'

    @api.model
    def _scope(self, fy, mkeys, today=None):
        """What this whole board is ABOUT: a year, one month, or a stretch.

        R1 — a stretch of ONE month reports itself as a month and a stretch of
        TWELVE reports itself as the year, so a reader who drags across the
        whole strip gets the year board they already know rather than a second,
        subtly different one, and nothing downstream has two names for one
        thing. `keys` is the ordered list of months in scope in every shape,
        including the year's own twelve, so the strip has one thing to read.
        """
        today = today or fields.Date.context_today(self)
        all_keys = self._month_keys(fy)
        keys = [k for k in (mkeys or []) if k in all_keys]
        if not keys or len(keys) == len(all_keys):
            now = self._current_fy(today)
            return {
                'kind': 'year',
                'key': str(fy),
                'keys': list(all_keys),
                'quarter': '',
                'label': self._fy_label(fy),
                'name': self._fy_label(fy),
                'short': self._fy_label(fy),
                'state': ('current' if fy == now
                          else ('past' if fy < now else 'future')),
            }
        if len(keys) == 1:
            first = self._month_date(keys[0])
            return {
                'kind': 'month',
                'key': keys[0],
                'keys': keys,
                'quarter': '',
                'label': self._month_title(first),
                'name': self._month_words(first, full=True),
                'short': self._month_words(first),
                'state': self._month_state(keys[0], today),
            }
        first = self._month_date(keys[0])
        last = self._month_date(keys[-1])
        quarter = self._quarter_of(keys, fy)
        return {
            'kind': 'range',
            'key': '%s..%s' % (keys[0], keys[-1]),
            'keys': keys,
            'quarter': quarter,
            'label': self._span_label(first, last, fy, quarter),
            'name': self._span_name(first, last, fy, quarter),
            'short': self._span_short(first, last, quarter),
            'state': self._period_state(keys, today),
        }

    @api.model
    def _span_label(self, first, last, fy, quarter=''):
        """What a stretch is CALLED, in words somebody would say out loud.

        A quarter names itself and then names its months, because "Q1" alone is
        a guess on any year that does not start in January. A stretch inside one
        calendar year carries the year once at the end; one that crosses the
        turn of the year carries it on both months, or "December to February" is
        a sentence with two possible meanings.
        """
        if quarter:
            return _("%(quarter)s · %(months)s",
                     quarter=self._quarter_name(int(quarter[1]), fy),
                     months=self._span_words(first, last))
        if first.year == last.year:
            return _("%(first)s to %(last)s %(year)s",
                     first=self._month_words(first, full=True),
                     last=self._month_words(last, full=True),
                     year=first.year)
        return _("%(first)s to %(last)s",
                 first=self._month_title(first), last=self._month_title(last))

    @api.model
    def _span_name(self, first, last, fy, quarter=''):
        """The short way to say it inside a sentence — "Q2 2026", "March to
        June", and the full both-years form when the stretch crosses a year."""
        if quarter:
            return self._quarter_name(int(quarter[1]), fy)
        if first.year == last.year:
            return self._span_words(first, last)
        return _("%(first)s to %(last)s",
                 first=self._month_title(first), last=self._month_title(last))

    @api.model
    def _span_short(self, first, last, quarter=''):
        if quarter:
            return quarter
        return _("%(first)s–%(last)s",
                 first=self._month_words(first), last=self._month_words(last))

    # ================================================================ the board
    @api.model
    def get_board(self, fy=None, budget_type='manpower', currency='report',
                  row_cap=None, period=None):
        """Everything the lens draws, in one call.

        `period` is nothing (the whole year), `'YYYY-MM'` inside the year,
        `'current'`, `'YYYY-MM..YYYY-MM'` or `'Q1'`…`'Q4'`. Whatever it names,
        the whole payload is about those months — the totals, the words, the
        colours and the pace — while every function keeps its twelve `months[]`
        so the spark on its tile still draws the whole year with the chosen
        ones lit.
        """
        self._require()
        fy = int(fy or self._current_fy())
        btype = budget_type if budget_type in TYPE_KEYS else 'manpower'
        months = self._fy_months(fy)
        cap = int(row_cap or BOARD_ROW_CAP)
        mkeys = self._period_in_fy(period, fy)
        scope = self._scope(fy, mkeys)
        pace = (self._pace(fy) if scope['kind'] == 'year'
                else self._period_pace(scope['keys']))

        # The company clause is EXPLICIT, not left to the record rule. The rule
        # is the boundary for every other route into the model; a facade that
        # is one day called under `sudo()` — a report render, a job, a wizard —
        # would otherwise quietly widen to every company, which is exactly how
        # another company's departments got into a company-scoped PDF.
        rows = self.env['pb.budget.line'].search([
            ('pb_budget_type', '=', btype),
            ('period_month', '>=', months[0]),
            ('period_month', '<=', months[-1]),
            ('company_id', 'in', self.env.companies.ids),
        ], order='period_month, department_id', limit=cap)
        truncated = 1 if len(rows) >= cap else 0

        fx = self.env['pb.budget.fx']
        presentation = fx.presentation_currency()
        currencies = {r.pb_currency_id for r in rows if r.pb_currency_id}
        one_currency = list(currencies)[0] if len(currencies) == 1 else None
        mode = currency if currency in ('report', 'local') else 'report'
        forced = ''
        if mode == 'local' and not one_currency and len(currencies) > 1:
            mode = 'report'
            forced = _(
                "These budgets are kept in %s different currencies, so they can "
                "only be added up in %s.",
                len(currencies), presentation.name if presentation else '')

        payload = self._matrix(rows, months, mode, presentation, one_currency,
                               pace, scope)
        payload.update({
            'ok': True,
            'fy': fy,
            'fy_label': self._fy_label(fy),
            'fy_options': self._fy_options(fy),
            'budget_type': btype,
            'type_label': type_label(btype, self.env),
            'type_options': [{'key': k, 'label': type_label(k, self.env)}
                             for k, _l in BUDGET_TYPES],
            'months': [{'key': m.strftime('%Y-%m'),
                        'label': self._month_words(m),
                        'name': self._month_words(m, full=True),
                        'title': self._month_title(m),
                        'year': m.year,
                        'date': str(m)} for m in months],
            'scope': scope,
            # The four brackets over the strip: the common stretch, named in
            # this company's own fiscal year rather than the calendar's (R5).
            'quarters': self._fy_quarters(fy),
            'pace': pace,
            'year_pace': self._pace(fy),
            'truncated': truncated,
            'can_edit': self.can_edit(),
            'last_sync': self.env['ir.config_parameter'].sudo().get_param(
                'pb_budget.actuals_last_run') or '',
            'forced_currency_note': forced,
        })
        payload['kpis'] = self._kpis(payload)
        # The strip is sent WHATEVER the scope: its whole job is to show, before
        # anybody clicks anything, which months ran hot.
        payload['strip'] = self._strip(payload)
        payload['headline'] = self._headline_scope(payload)
        return payload

    @api.model
    def _headline_scope(self, payload):
        """One sentence about whatever this board is about."""
        if payload['scope']['kind'] == 'year':
            return self._headline(payload)
        return self._headline_month(payload)

    @api.model
    def _fy_options(self, fy):
        """The years there is anything to look at, plus this one and next."""
        years = set()
        rows = safe(lambda: self.env['pb.budget.line'].search_read(
            [], ['period_month'], limit=BOARD_ROW_CAP), [], 'the year list') or []
        for r in rows:
            if r.get('period_month'):
                d = r['period_month']
                years.add(d.year if self._fy_start_month() == 1
                          else (d.year if d.month >= self._fy_start_month()
                                else d.year - 1))
        now = self._current_fy()
        years |= {now, now + 1, int(fy)}
        return [{'key': y, 'label': self._fy_label(y)} for y in sorted(years)]

    # --------------------------------------------------------------- the grid
    @api.model
    def _matrix(self, rows, months, mode, presentation, one_currency, pace,
                scope):
        """Rows -> functions -> departments -> months, in ONE currency.

        WHEN A PERIOD IS THE SCOPE the function and department totals count only
        the rows of the months that period covers — one of them, three of them
        or any stretch — and the twelve `months[]` are still filled from every
        row: the tile's numbers become March's, its spark stays the year's.
        A function with nothing in the chosen months keeps its TILE — a board
        whose tiles rearrange themselves on every press is a board nobody can
        learn, and "this function spent nothing in March" is an answer.
        """
        keys = [m.strftime('%Y-%m') for m in months]
        funcs, unknown, unbudgeted = {}, 0, 0
        cur = (one_currency if mode == 'local' and one_currency
               else presentation)
        # THE ONE CODE PATH. In year scope this set holds all twelve, so the
        # membership test below is true for every row and the year board is the
        # board it always was; a month is a set of one and a stretch a set of
        # however many. There is no second branch to keep in step.
        by_year = scope['kind'] == 'year'
        in_scope = set(scope['keys'])
        state = scope['state']

        for rec in rows:
            budget, spent, known = self._amounts(rec, mode, cur)
            if not known:
                unknown += 1
                continue
            fid = rec.pb_function_id.id or (rec.department_id.id or 0)
            fname = (rec.pb_function_id.name or rec.department_id.name
                     or _('Whole company'))
            f = funcs.setdefault(fid, {
                'id': fid, 'name': fname, 'budget': 0.0, 'spent': 0.0,
                'year_budget': 0.0, 'year_spent': 0.0,
                'months': {k: {'budget': 0.0, 'spent': 0.0} for k in keys},
                'departments': {}, 'unbudgeted': False, 'rows': 0,
            })
            mkey = rec.period_month.strftime('%Y-%m')
            f['year_budget'] += budget
            f['year_spent'] += spent
            if mkey in f['months']:
                f['months'][mkey]['budget'] += budget
                f['months'][mkey]['spent'] += spent
            if mkey not in in_scope:
                continue
            if rec.pb_unbudgeted:
                unbudgeted += 1
            f['budget'] += budget
            f['spent'] += spent
            f['rows'] += 1
            f['unbudgeted'] = f['unbudgeted'] or rec.pb_unbudgeted
            did = rec.department_id.id or 0
            d = f['departments'].setdefault(did, {
                'id': did,
                'name': rec.department_id.name or _('Whole company'),
                'budget': 0.0, 'spent': 0.0, 'unbudgeted': False,
            })
            d['budget'] += budget
            d['spent'] += spent
            d['unbudgeted'] = d['unbudgeted'] or rec.pb_unbudgeted

        out = []
        for f in funcs.values():
            f['months'] = [dict(f['months'][k], key=k) for k in keys]
            f['departments'] = sorted(
                f['departments'].values(), key=lambda d: -abs(d['spent']))
            for d in f['departments']:
                d['variance'] = round(d['spent'] - d['budget'], 2)
                d['variance_pct'] = (round(d['variance'] / d['budget'] * 100, 1)
                                     if d['budget'] else 0.0)
            f['budget'] = round(f['budget'], 2)
            f['spent'] = round(f['spent'], 2)
            f['year_budget'] = round(f['year_budget'], 2)
            f['year_spent'] = round(f['year_spent'], 2)
            f['left'] = round(f['budget'] - f['spent'], 2)
            f['variance'] = round(f['spent'] - f['budget'], 2)
            f['variance_pct'] = (round(f['variance'] / f['budget'] * 100, 1)
                                 if f['budget'] else 0.0)
            f['burn'] = round(f['spent'] / f['budget'] * 100, 1) if f['budget'] else 0.0
            f['pace'] = pace
            f['gap'] = round(f['burn'] - pace, 1) if f['budget'] else 0.0
            f['tone'] = (self._tone(f) if by_year
                         else self._tone_month(f, state))
            f['tone_label'] = (self._tone_label(f) if by_year
                               else self._tone_label_month(f))
            out.append(f)
        # SORTED BY THE YEAR, ALWAYS. In year scope that is what it always was;
        # in month scope it is what keeps every tile where the reader left it
        # when they clicked a month.
        out.sort(key=lambda f: (-abs(f['year_spent']), f['name']))

        return {
            'functions': out,
            'currency': {
                'mode': mode,
                'code': cur.name if cur else '',
                'symbol': cur.symbol if cur else '',
                'position': cur.position if cur else 'after',
                'digits': cur.decimal_places if cur else 2,
                'report_code': presentation.name if presentation else '',
                'local_available': bool(one_currency),
                'local_code': one_currency.name if one_currency else '',
            },
            'fx_unknown': unknown,
            'fx_note': (self.env['pb.budget.fx'].unknown_rate_note(
                one_currency or (rows[:1].pb_currency_id if rows else None),
                presentation) if unknown else ''),
            'unbudgeted': unbudgeted,
        }

    @api.model
    def _amounts(self, rec, mode, cur):
        if mode == 'local':
            return (round(rec.forecast_cost or 0.0, 2),
                    round(rec.actual_cost or 0.0, 2), True)
        rep = rec.pb_reported(presentation=cur)
        return rep['budget'], rep['spent'], rep['known']

    @api.model
    def _tone(self, f):
        """Four words, and a number beside every one of them.

        Colour alone is never the message — every tile carries its percentage
        and its word, so the board reads correctly to somebody who cannot tell
        the amber from the rose.
        """
        if not f['budget'] and f['spent']:
            return 'none'
        if not f['budget']:
            return 'calm'
        if f['gap'] > OVER_AT:
            return 'over'
        if f['gap'] > WATCH_AT:
            return 'watch'
        if f['gap'] < CALM_AT:
            return 'calm'
        return 'onpace'

    @api.model
    def _tone_label(self, f):
        return {
            'none': _('No budget set'),
            'over': _('Ahead of the year'),
            'watch': _('Running warm'),
            'onpace': _('On pace'),
            'calm': _('Behind the year'),
        }.get(f['tone'], '')

    @api.model
    def _tone_month(self, f, state='past'):
        """The five words a MONTH can be, and the number beside each of them.

        A month has no calendar to run ahead of — the whole of it is either
        spent or it is not — so the comparison is the budget itself, and the
        answer is over it, close to it, or under it. A month that has not
        happened yet says so instead of reading as a triumph of thrift.
        """
        if state == 'future' and not f['spent']:
            return 'notyet'
        if not f['budget']:
            return 'none'
        band = abs(f['budget']) * MONTH_BAND / 100.0
        if f['spent'] > f['budget'] + band:
            return 'over'
        if abs(f['spent'] - f['budget']) <= band:
            return 'onpace'
        return 'calm'

    @api.model
    def _tone_label_month(self, f):
        return {
            'over': _('Over budget'),
            'onpace': _('Close to budget'),
            'calm': _('Under budget'),
            'none': _('No budget set'),
            'notyet': _('Not yet'),
        }.get(f['tone'], '')

    # ---------------------------------------------------------------- the KPIs
    @api.model
    def _kpis(self, payload):
        funcs = payload['functions']
        budget = round(sum(f['budget'] for f in funcs), 2)
        spent = round(sum(f['spent'] for f in funcs), 2)
        pace = payload['pace']
        burn = round(spent / budget * 100, 1) if budget else 0.0
        return {
            'budget': budget,
            'spent': spent,
            'left': round(budget - spent, 2),
            'burn': burn,
            'pace': pace,
            'gap': round(burn - pace, 1) if budget else 0.0,
            'hot': len([f for f in funcs if f['tone'] in ('over', 'watch')]),
            'unbudgeted': len([f for f in funcs if f['tone'] == 'none']),
            'functions': len(funcs),
            # A month is answered by its variance, not by its pace: how far the
            # spend fell either side of the budget, in money and in points.
            'variance': round(spent - budget, 2),
            'variance_pct': (round((spent - budget) / budget * 100, 1)
                             if budget else 0.0),
            'over': len([f for f in funcs if f['tone'] == 'over']),
        }

    # ----------------------------------------------------------- the strip
    @api.model
    def _strip(self, payload, today=None):
        """Twelve chips that answer before anybody clicks anything.

        Built from the SAME functions the board underneath is drawing, so the
        strip and the tiles can never disagree — and summed from every
        function's twelve months, so it is the whole year whichever month is
        in scope.
        """
        today = today or fields.Date.context_today(self)
        totals = {m['key']: {'budget': 0.0, 'spent': 0.0}
                  for m in payload['months']}
        for f in payload['functions']:
            for mo in f['months']:
                if mo['key'] in totals:
                    totals[mo['key']]['budget'] += mo['budget'] or 0.0
                    totals[mo['key']]['spent'] += mo['spent'] or 0.0
        out = []
        for m in payload['months']:
            cell = {'budget': round(totals[m['key']]['budget'], 2),
                    'spent': round(totals[m['key']]['spent'], 2)}
            state = self._month_state(m['key'], today)
            cell['tone'] = self._tone_month(cell, state)
            out.append({
                'key': m['key'],
                'label': m['label'],
                'name': m['name'],
                'title': m['title'],
                'budget': cell['budget'],
                'spent': cell['spent'],
                'left': round(cell['budget'] - cell['spent'], 2),
                'variance': round(cell['spent'] - cell['budget'], 2),
                'variance_pct': (round((cell['spent'] - cell['budget'])
                                       / cell['budget'] * 100, 1)
                                 if cell['budget'] else 0.0),
                # The micro bar's fill, capped so a month that spent three
                # times its budget does not draw over the chip beside it.
                'share': (round(min(100.0, cell['spent'] / cell['budget'] * 100), 1)
                          if cell['budget'] else 0.0),
                'has_budget': bool(cell['budget']),
                'tone': cell['tone'],
                'tone_label': self._tone_label_month(cell),
                'state': state,
            })
        return out

    @api.model
    def _headline(self, payload):
        """One sentence, built in ONE expression so its spaces survive (R34)."""
        k = payload['kpis']
        cur = payload['currency']['code']
        if not payload['functions']:
            return _("Nothing has been budgeted for %s yet.", payload['fy_label'])
        if not k['budget']:
            return _(
                "No budget has been set for %(year)s, and %(spent)s %(cur)s has "
                "already been spent across %(n)s.",
                year=payload['fy_label'], spent='{:,.0f}'.format(k['spent']),
                cur=cur, n=counted(k['functions'], _("1 function"),
                                   _("%s functions")))
        if k['gap'] > OVER_AT:
            return _(
                "%(burn)s%% of the %(year)s budget is spent and the year is "
                "%(pace)s%% gone — spending is running ahead of the calendar.",
                burn='{:,.0f}'.format(k['burn']), year=payload['fy_label'],
                pace='{:,.0f}'.format(k['pace']))
        if k['gap'] < CALM_AT:
            return _(
                "%(burn)s%% of the %(year)s budget is spent against a year that "
                "is %(pace)s%% gone — comfortably inside it.",
                burn='{:,.0f}'.format(k['burn']), year=payload['fy_label'],
                pace='{:,.0f}'.format(k['pace']))
        return _(
            "%(burn)s%% of the %(year)s budget is spent and the year is "
            "%(pace)s%% gone — about where it should be.",
            burn='{:,.0f}'.format(k['burn']), year=payload['fy_label'],
            pace='{:,.0f}'.format(k['pace']))

    @api.model
    def _headline_month(self, payload):
        """One sentence about a period smaller than the year, in ONE expression
        each (R34).

        Five shapes, and which one a reader gets is the answer to a different
        question every time: has it started, was anything budgeted, is it still
        running, did anybody go over, and by how much did the rest come in.

        FOUR OF THE FIVE read correctly about a stretch as well as about a
        month — "March to June has no budget set", "Q2 2026: 4 of 9 functions
        went over budget" — so they are the same sentences and the same terms
        in the catalogue rather than a second set that could drift. The one
        that does not is the running one, which says "the month's budget" out
        loud; a stretch gets its own.
        """
        k = payload['kpis']
        scope = payload['scope']
        cur = payload['currency']['code']
        overs = [f for f in payload['functions'] if f['tone'] == 'over']
        if scope['state'] == 'future' and not k['spent']:
            return _("%s has not started.", scope['name'])
        if not payload['functions']:
            return _("Nothing has been budgeted for %s yet.", scope['label'])
        if not k['budget']:
            return _(
                "%(month)s has no budget set; %(spent)s %(cur)s was spent.",
                month=scope['name'], spent=self._short(k['spent']), cur=cur)
        if scope['state'] == 'current':
            if scope['kind'] == 'range':
                return _(
                    "%(period)s so far: %(burn)s%% of the budget for those "
                    "months spent, with %(pace)s%% of them gone.",
                    period=scope['name'], burn='{:,.0f}'.format(k['burn']),
                    pace='{:,.0f}'.format(k['pace']))
            return _(
                "%(month)s so far: %(burn)s%% of the month's budget spent with "
                "%(pace)s%% of the month gone.",
                month=scope['name'], burn='{:,.0f}'.format(k['burn']),
                pace='{:,.0f}'.format(k['pace']))
        if overs:
            worst = max(overs, key=lambda f: f['variance'])
            return _(
                "%(month)s: %(n)s of %(total)s functions went over budget; "
                "%(name)s by the most (%(amount)s %(cur)s, %(pct)s%% over).",
                month=scope['name'], n=len(overs), total=k['functions'],
                name=worst['name'], amount=self._short(worst['variance']),
                cur=cur, pct='{:,.0f}'.format(worst['variance_pct']))
        if k['left'] >= 0:
            return _(
                "%(month)s came in %(amount)s %(cur)s under budget across "
                "%(n)s.", month=scope['name'], amount=self._short(k['left']),
                cur=cur, n=counted(k['functions'], _("1 function"),
                                   _("%s functions")))
        return _(
            "%(month)s came in %(amount)s %(cur)s over budget across %(n)s.",
            month=scope['name'], amount=self._short(-k['left']), cur=cur,
            n=counted(k['functions'], _("1 function"), _("%s functions")))

    # =============================================================== the drill
    @api.model
    def get_function(self, function_id, fy=None, budget_type='manpower',
                     currency='report', period=None):
        """One function, opened: its months, its departments, its expenses.

        In any scope narrower than the year everything below the twelve-bar
        chart is that period's — the departments, the expenses, the rows — and
        the chart itself keeps the whole year with the chosen months lit,
        because the question a person opens a period to ask is almost always
        "compared with what".
        """
        self._require()
        fy = int(fy or self._current_fy())
        btype = budget_type if budget_type in TYPE_KEYS else 'manpower'
        months = self._fy_months(fy)
        board = self.get_board(fy, btype, currency, None, period)
        scope = board['scope']
        mkeys = [] if scope['kind'] == 'year' else list(scope['keys'])
        func = next((f for f in board['functions']
                     if f['id'] == int(function_id or 0)), None)
        if not func:
            return {'ok': False,
                    'message': _("That function has nothing budgeted for "
                                 "%s.", scope['label'])}
        out = {
            'ok': True,
            'function': func,
            'currency': board['currency'],
            'months': board['months'],
            'scope': scope,
            'pace': board['pace'],
            'expenses': self._expenses(function_id, months, btype, mkeys),
            'rows': self._rows(function_id, months, btype,
                               board['currency']['mode'],
                               self._board_currency(board['currency']), mkeys),
        }
        if mkeys:
            out['compare'] = self._compare(function_id, mkeys, btype, board,
                                           func)
        return out

    # ---------------------------------------------------------- how it compares
    @api.model
    def _compare(self, function_id, mkeys, btype, board, func):
        """Four small figures beside the period: this one, the stretch of the
        same length immediately before it, the same stretch a year ago, and
        what a month of this year is worth on average. The year-ago figure is
        left BLANK when there is no year ago — an absent comparison is a fact,
        and inventing a zero for it would make every first year of a budget
        look like a collapse.
        """
        mode = board['currency']['mode']
        cur = self._board_currency(board['currency'])
        firsts = [self._month_date(k) for k in mkeys]
        span = len(firsts)
        prev = [d - relativedelta(months=span) for d in firsts]
        ago = [d - relativedelta(years=1) for d in firsts]
        drawn = len([m for m in func['months']
                     if m['budget'] or m['spent']]) or 12
        return {
            'this': {
                'has': True, 'key': board['scope']['key'],
                'label': board['scope']['name'],
                'budget': func['budget'], 'spent': func['spent'],
            },
            'last': self._compare_cell(function_id, prev, btype, mode, cur),
            'last_year': self._compare_cell(function_id, ago, btype, mode, cur),
            'average': {
                'has': True, 'key': '',
                'label': _("Monthly average"),
                'budget': round(func['year_budget'] / drawn, 2),
                'spent': round(func['year_spent'] / drawn, 2),
            },
        }

    @api.model
    def _compare_cell(self, function_id, firsts, btype, mode, cur):
        """One comparison figure over however many months it is made of."""
        recs = self.env['pb.budget.line'].search([
            ('pb_function_id', '=', int(function_id or 0)),
            ('pb_budget_type', '=', btype),
            ('period_month', 'in', firsts),
            ('company_id', 'in', self.env.companies.ids),
        ], limit=BOARD_ROW_CAP)
        first, last = firsts[0], firsts[-1]
        label = (self._month_title(first) if first == last
                 else _("%(first)s to %(last)s",
                        first=self._month_title(first),
                        last=self._month_title(last)))
        cell = {'has': bool(recs), 'key': first.strftime('%Y-%m'),
                'label': label, 'budget': 0.0, 'spent': 0.0}
        for rec in recs:
            budget, spent, known = self._amounts(rec, mode, cur)
            if not known:
                continue
            cell['budget'] += budget
            cell['spent'] += spent
        cell['budget'] = round(cell['budget'], 2)
        cell['spent'] = round(cell['spent'], 2)
        return cell

    @api.model
    def _board_currency(self, block):
        """The currency record the board reported in — resolved ONCE, from the
        code the payload already carries, so the drill can never quietly report
        in a different one."""
        if not block.get('code'):
            return self.env['pb.budget.fx'].presentation_currency()
        return self.env['res.currency'].sudo().search(
            [('name', '=', block['code'])], limit=1)

    @api.model
    def _expenses(self, function_id, months, btype, mkeys=()):
        if btype == 'manpower':
            return []
        first = self._month_date(mkeys[0]) if mkeys else months[0]
        last = self._month_date(mkeys[-1]) if mkeys else months[-1]
        recs = self.env['pb.budget.expense'].search([
            ('function_id', '=', int(function_id or 0)),
            ('budget_type', '=', btype),
            ('period_month', '>=', first),
            ('period_month', '<=', last),
            ('company_id', 'in', self.env.companies.ids),
        ], order='spend_date desc', limit=EXPENSE_ROW_CAP)
        return [{
            'id': r.id, 'name': r.name or '',
            'date': str(r.spend_date or ''),
            'department': r.department_id.name or '',
            'supplier': r.supplier or '',
            'amount': r.amount or 0.0,
            'currency': r.currency_id.name or '',
            'note': r.note or '',
        } for r in recs]

    @api.model
    def _rows(self, function_id, months, btype, mode, cur, mkeys=()):
        first = self._month_date(mkeys[0]) if mkeys else months[0]
        last = self._month_date(mkeys[-1]) if mkeys else months[-1]
        recs = self.env['pb.budget.line'].search([
            ('pb_function_id', '=', int(function_id or 0)),
            ('pb_budget_type', '=', btype),
            ('period_month', '>=', first),
            ('period_month', '<=', last),
            ('company_id', 'in', self.env.companies.ids),
        ], order='period_month, department_id', limit=BOARD_ROW_CAP)
        out = []
        for rec in recs:
            budget, spent, known = self._amounts(rec, mode, cur)
            out.append({
                'id': rec.id,
                'month': rec.period_month.strftime('%Y-%m'),
                'month_label': self._month_title(rec.period_month),
                'department': rec.department_id.name or _('Whole company'),
                'budget': budget, 'spent': spent,
                'left': round(budget - spent, 2),
                'known': known,
                'source': dict(rec._fields['pb_source'].selection).get(
                    rec.pb_source, ''),
                'own_currency': rec.pb_currency_id.name or '',
                'manual_rate': rec.pb_manual_rate or 0.0,
                'unbudgeted': rec.pb_unbudgeted,
                'synced': str(rec.pb_actual_synced_on or ''),
            })
        return out

    # =============================================================== the doors
    @api.model
    def refresh_actuals(self):
        """The button, and it does EXACTLY what the night does (R53)."""
        self._require_edit()
        report = self.env['pb.budget.actuals'].sudo().run_now()
        return {'ok': True, 'report': report,
                'message': self._sync_sentence(report)}

    @api.model
    def _sync_sentence(self, report):
        if report.get('off'):
            return _(
                "Automatic spend figures are switched off. %s "
                "department-months would have been written.",
                report.get('would_write', 0))
        bits = [_("%s department-months updated.", report.get('written', 0))]
        if report.get('created'):
            bits.append(_("%s had no budget set and were added, flagged.",
                          report.get('created')))
        if report.get('pending_runs'):
            bits.append(_(
                "%s pay runs have not been summarised yet, so they are not in "
                "these figures.", report.get('pending_runs')))
        if report.get('skipped_fx'):
            bits.append(_(
                "%s rows were left alone because there is no exchange rate for "
                "the money they are kept in.", report.get('skipped_fx')))
        return ' '.join(bits)

    @api.model
    def department_options(self, term=None, limit=20):
        """A department picker that finds "Kỹ thuật" when you type "ky thuat".

        Accents are folded in PYTHON over a `search_read` of two columns —
        Postgres on this box has no `unaccent` (R78) and a domain `ilike` would
        simply not match.
        """
        self._require()
        recs = self.env['hr.department'].search_read(
            [('company_id', 'in', self.env.companies.ids)],
            ['id', 'display_name', 'company_id'], limit=500)
        needle = fold(term or '')
        out = [r for r in recs if not needle
               or needle in fold(r.get('display_name') or '')]
        return [{'id': r['id'], 'name': r.get('display_name') or '',
                 'company': (r.get('company_id') or [0, ''])[1]}
                for r in out[:int(limit or 20)]]

    @api.model
    def add_expense(self, vals):
        """Add an HR-operations or admin expense from the lens."""
        self._require_edit()
        vals = dict(vals or {})
        if not (vals.get('name') or '').strip():
            raise UserError(_("Say what the money was for."))
        try:
            amount = float(vals.get('amount') or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            raise UserError(_("Put in what it cost."))
        btype = vals.get('budget_type')
        if btype not in ('hr_ops', 'admin'):
            raise UserError(_(
                "An expense belongs to HR operations or to Admin. What people "
                "are paid comes from the pay runs themselves and is never "
                "typed in here."))
        rec = self.env['pb.budget.expense'].create({
            'name': vals['name'].strip(),
            'spend_date': vals.get('spend_date') or fields.Date.context_today(self),
            'budget_type': btype,
            'department_id': int(vals.get('department_id') or 0) or False,
            'amount': amount,
            'supplier': (vals.get('supplier') or '').strip(),
            'note': (vals.get('note') or '').strip(),
            'company_id': self.env.company.id,
            'currency_id': self.env.company.currency_id.id,
        })
        return {'ok': True, 'id': rec.id,
                'message': _("Added — it counts against %(month)s's %(type)s "
                             "budget.",
                             month=rec.period_month.strftime('%B %Y'),
                             type=type_label(btype, self.env))}

    @api.model
    def export_board(self, fy=None, budget_type='manpower', currency='report',
                     kind='xlsx', period=None):
        """The matrix as a workbook, or the scope as a page.

        A period on screen is that period in the file, and the file SAYS which
        one it is about in its own title: what a person exports is what they
        were looking at, or the export is a second answer to the question they
        had already had answered — and a document that does not name its period
        is one that will be read next year and believed.
        """
        self._require()
        return self.env['pb.budget.export'].build(
            fy=fy, budget_type=budget_type, currency=currency, kind=kind,
            period=period)
