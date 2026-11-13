# -*- coding: utf-8 -*-
"""`pb.pay.fairness` — one honest number per question, computed and never kept.

WHY NOTHING IS STORED
---------------------
A fairness figure is a claim about a company at a moment. Store it and it is
wrong within a month, and the version that is wrong is the one somebody screen-
shots for a board pack. Every number on this screen is computed on the read,
from the payroll that was actually paid, and carries the month it came from and
the number of people it was measured on. There is no table here.

WHERE THE MONEY COMES FROM
--------------------------
`pb.fact.emp`, category `basic`, the newest month whose run is APPROVED and is
not a mid-month advance — that is basic pay, per person, as the payroll paid it
(GROUP P3 built those columns). A company with no payroll history at all falls
back to the wage on its open contracts and the screen SAYS SO, because "we
guessed from the contract" and "this is what we paid" are different claims.

WHAT IT REFUSES TO ANSWER
-------------------------
A gap measured on four people is noise with a decimal point on it. Every
comparison needs five people on each side or it says "not enough people to
compare fairly" — which is a real answer and not an empty card. Two companies
that keep their books in different currencies are never averaged together
unless the reader asks for the group's money, and then every figure carries the
rate badge and the refusal `pb.fx` gives when there is no rate (rule 7).

WHOSE NAMES
-----------
A pay manager sees who is paid least for the same work. A viewer sees how many
there are and not who they are: a fairness screen must not become a way to read
your colleagues' salaries.
"""

import logging
import time
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)

READ_GROUPS = (
    'pb_pay.group_pay_manager',
    'pb_pay.group_pay_viewer',
    'pb_group.group_group_admin',
    'hr.group_hr_manager',
)
NAME_GROUPS = (
    'pb_pay.group_pay_manager',
    'pb_group.group_group_admin',
)

#: Below this many people on either side, a comparison is not made at all.
MIN_SIDE = 5
#: How far under a job's middle counts as "paid least for the same work".
LOW_PAY_GAP = 0.15
MAX_ROWS = 60

SEX_LABELS = {'female': 'Women', 'male': 'Men', 'other': 'Other'}


class PbPayFairness(models.AbstractModel):
    _name = 'pb.pay.fairness'
    # GROUP P7 — every read on this screen goes through `who sees what`.
    # A reader with no visibility row is narrowed by nothing at all.
    _inherit = ['pb.group.scoped']
    _description = 'Fairness'

    # ================================================================= gates
    @api.model
    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception as error:      # noqa: BLE001
            _logger.debug('Fairness figure failed: %s', error)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        if user._is_admin():
            return True
        return any(self._safe(lambda n=n: user.has_group(n), default=False)
                   for n in READ_GROUPS)

    @api.model
    def _can_see_names(self):
        user = self.env.user
        if user._is_admin():
            return True
        return any(self._safe(lambda n=n: user.has_group(n), default=False)
                   for n in NAME_GROUPS)

    # ================================================================= scope
    @api.model
    def get_scopes(self):
        """Group, company, division — the three a fairness answer is asked at.

        Deliberately NOT the Decision Room's five-level tree: a pay gap by
        payroll scheme is a question nobody asks, and every rung offered is a
        rung somebody has to rule out.
        """
        if not self._can_read():
            return []
        companies = self.env['pb.pay.bands']._companies()
        # GROUP P7 — a rung this reader may not stand on is a rung that is not
        # offered. Held to a division, the only question they are asked is
        # their own.
        held = self._visible_divisions()
        out = []
        group = None
        if 'pb.group' in self.env:
            group = self.env['pb.group'].sudo().search([], limit=1)
        if group and len(companies) > 1 and not held:
            out.append({'kind': 'group', 'ref': group.id,
                        'label': group.name,
                        'sub': _('%(count)s companies',
                                 count=len(companies))})
        for company in (companies if not held else companies.browse()):
            out.append({'kind': 'company', 'ref': company.id,
                        'label': company.display_name,
                        'sub': company.currency_id.name})
        if 'pb.division' in self.env:
            heads = self.env['pb.division'].sudo()._heads_by_division()
            # GROUP P7 — a division head is offered their own division and
            # nothing else; empty for everybody who has not been limited.
            only = set(self._visible_divisions())
            for division in self.env['pb.division'].sudo().search([]):
                if not heads.get(division.id):
                    continue
                if only and division.id not in only:
                    continue
                out.append({'kind': 'division', 'ref': division.id,
                            'label': division.name,
                            'sub': _('%(count)s people',
                                     count=heads.get(division.id, 0))})
        return out

    @api.model
    def _resolve_scope(self, kind, ref):
        Bands = self.env['pb.pay.bands']
        companies = Bands._companies()
        # GROUP P7 — somebody held to one division is answered at their
        # division whatever they asked for; the group and company rungs are
        # not theirs to stand on.
        only = self._visible_divisions()
        if only:
            kind, ref = 'division', only[0]
        kind = kind if kind in ('group', 'company', 'division') else 'company'
        if kind == 'company' and ref:
            narrowed = companies.filtered(lambda c: c.id == int(ref))
            if narrowed:
                return {'kind': 'company', 'ref': int(ref),
                        'label': narrowed.display_name,
                        'companies': narrowed, 'division_id': 0}
        if kind == 'division' and ref and 'pb.division' in self.env:
            division = self.env['pb.division'].sudo().browse(
                int(ref)).exists()
            if division:
                inside = companies.filtered(
                    lambda c: c.id in division.company_ids.ids) or companies
                return {'kind': 'division', 'ref': division.id,
                        'label': division.name, 'companies': inside,
                        'division_id': division.id}
        if kind == 'group':
            group = self.env['pb.group'].sudo().search([], limit=1) \
                if 'pb.group' in self.env else None
            return {'kind': 'group', 'ref': group.id if group else 0,
                    'label': group.name if group else _('The whole group'),
                    'companies': companies, 'division_id': 0}
        return self._default_scope(companies)

    @api.model
    def _default_scope(self, companies):
        """Where the screen opens when nobody has said.

        The company the reader is STANDING IN, and failing that the one with
        the most people in it. Taking `companies[:1]` opens a group on
        whichever company happens to have the lowest id — on the demo group
        that is the Singapore entity with nobody in it, and the first thing
        the screen says is "there is nobody to measure", which is true and
        useless.
        """
        if not companies:
            return {'kind': 'company', 'ref': 0, 'label': '',
                    'companies': companies, 'division_id': 0}
        here = companies.filtered(lambda c: c.id == self.env.company.id)
        first = here[:1]
        if not first:
            rows = self.env['pb.pay.position'].sudo()._read_group(
                [('company_id', 'in', companies.ids)],
                ['company_id'], ['__count'])
            counted = {company.id: count for company, count in rows if company}
            first = companies.sorted(
                key=lambda c: -counted.get(c.id, 0))[:1]
        return {'kind': 'company', 'ref': first.id,
                'label': first.display_name,
                'companies': first, 'division_id': 0}

    # ============================================================= the people
    @api.model
    def _from_facts(self, companies):
        """Basic pay per person from the newest approved main-run month."""
        if 'pb.fact.emp' not in self.env or not companies:
            return {}, {}
        cr = self.env.cr
        cr.execute("""
            SELECT company_id, MAX(month)
              FROM pb_fact_emp
             WHERE company_id IN %s AND category_type = 'basic'
               AND basis = 'approved' AND COALESCE(is_advance, FALSE) = FALSE
          GROUP BY company_id
        """, [tuple(companies.ids)])
        months = {row[0]: row[1] for row in cr.fetchall()}
        if not months:
            cr.execute("""
                SELECT company_id, MAX(month)
                  FROM pb_fact_emp
                 WHERE company_id IN %s AND category_type = 'basic'
                   AND COALESCE(is_advance, FALSE) = FALSE
              GROUP BY company_id
            """, [tuple(companies.ids)])
            months = {row[0]: row[1] for row in cr.fetchall()}
        if not months:
            return {}, {}
        pairs = tuple((company_id, month)
                      for company_id, month in months.items())
        cr.execute("""
            SELECT employee_id, company_id, SUM(amount), MAX(division_id)
              FROM pb_fact_emp
             WHERE category_type = 'basic'
               AND (company_id, month) IN %s
               AND employee_id IS NOT NULL
          GROUP BY employee_id, company_id
        """, [pairs])
        paid = {}
        for emp_id, company_id, amount, division_id in cr.fetchall():
            paid[emp_id] = {'wage': float(amount or 0.0),
                            'company_id': company_id,
                            'division_id': division_id or 0}
        return paid, months

    @api.model
    def _people(self, companies, division_id=0):
        """One row per person: pay, sex, job, band level, division."""
        if not companies:
            return [], {}, 'none'
        paid, months = self._from_facts(companies)
        source = 'payroll' if paid else 'contracts'

        cr = self.env.cr
        cr.execute("""
            SELECT DISTINCT ON (c.employee_id)
                   c.employee_id, e.name, c.company_id, v.sex,
                   COALESCE(c.job_id, v.job_id) AS job_id,
                   COALESCE(c.department_id, v.department_id) AS dep_id,
                   COALESCE(c.wage, 0)::float
              FROM hr_contract c
              JOIN hr_employee e ON e.id = c.employee_id AND e.active
         LEFT JOIN hr_version v ON v.id = e.current_version_id
             WHERE c.state = 'open' AND c.active AND c.company_id IN %s
          ORDER BY c.employee_id, c.date_start DESC NULLS LAST, c.id DESC
        """, [tuple(companies.ids)])
        rows = cr.fetchall()

        levels = {}
        for row in self.env['pb.pay.position'].sudo().search_read(
                [('company_id', 'in', companies.ids)],
                ['employee_id', 'band_id']):
            levels[(row['employee_id'] or [0])[0]] = \
                (row['band_id'] or [0])[0]
        bands = {b.id: b for b in self.env['pb.pay.band'].sudo().browse(
            list({v for v in levels.values() if v}))}

        by_department = {}
        chains = {}
        if 'pb.division' in self.env:
            Division = self.env['pb.division'].sudo()
            by_department = self._safe(lambda: Division._links_on(),
                                       default={}) or {}
            chains = self._safe(
                lambda: Division._department_chains(companies.ids),
                default={}) or {}

        people = []
        for emp_id, name, company_id, sex, job_id, dep_id, wage in rows:
            fact = paid.get(emp_id)
            amount = fact['wage'] if fact else wage
            division = fact['division_id'] if fact else 0
            if not division and dep_id:
                for candidate in reversed(chains.get(dep_id) or [dep_id]):
                    if candidate in by_department:
                        division = by_department[candidate]
                        break
            band = bands.get(levels.get(emp_id))
            people.append({
                'employee_id': emp_id, 'name': name,
                'company_id': company_id,
                'sex': (sex or '').lower() or 'unknown',
                'job_id': job_id or 0,
                'division_id': division or 0,
                'level': band.level if band else 0,
                'band': band.name if band else '',
                'wage': float(amount or 0.0),
            })
        if division_id:
            people = [p for p in people if p['division_id'] == division_id]
        return people, months, source

    # ============================================================== the board
    @api.model
    def get_board(self, kind='company', ref=0, group_money=False):
        started = time.time()
        blank = {
            'allowed': False, 'can_see_names': False, 'scope': {},
            'scopes': [], 'headline': '', 'cards': [], 'levels': [],
            'divisions': [], 'spread': [], 'lowest': [], 'method': [],
            'money': {}, 'source': '', 'people': 0, 'ms': 0,
        }
        if not self._can_read():
            return blank
        scope = self._resolve_scope(kind, ref)
        companies = scope['companies']
        people, months, source = self._safe(
            lambda: self._people(companies, scope['division_id']),
            default=([], {}, 'none'))
        money = self._safe(lambda: self._money_meta(companies, group_money),
                           default={}) or {}
        people, dropped = self._safe(
            lambda: self._convert_people(people, companies, money),
            default=(people, [])) or (people, [])
        money['left_out_people'] = len(dropped)
        board = dict(blank)
        board.update({
            'allowed': True,
            'can_see_names': self._can_see_names(),
            'scope': {'kind': scope['kind'], 'ref': scope['ref'],
                      'label': scope['label'],
                      'companies': companies.ids,
                      'company_names': companies.mapped('display_name')},
            'scopes': self._safe(lambda: self.get_scopes(), default=[]) or [],
            'source': source,
            'source_label': self._source_label(source, months),
            'people': len(people),
            'people_label': _('%(count)s people measured.',
                              count=len(people)),
            'money': money,
            'group_money': bool(group_money),
        })
        currency = self._currency_for(companies, money)
        board['cards'] = self._safe(
            lambda: self._cards(people, currency), default=[]) or []
        board['levels'] = self._safe(
            lambda: self._by_level(people), default=[]) or []
        board['divisions'] = self._safe(
            lambda: self._by_division(people), default=[]) or []
        board['spread'] = self._safe(
            lambda: self._same_job_spread(people, currency),
            default=[]) or []
        board['lowest'] = self._safe(
            lambda: self._lowest_paid(people, currency), default=[]) or []
        board['headline'] = self._safe(
            lambda: self._headline(board, people), default='') or ''
        board['method'] = self._method_lines(source, months, companies)
        board['ms'] = int((time.time() - started) * 1000)
        return board

    @api.model
    def _currency_for(self, companies, money):
        if money.get('currency_id'):
            return self.env['res.currency'].browse(money['currency_id'])
        return companies[:1].currency_id or self.env.company.currency_id

    @api.model
    def _money_meta(self, companies, group_money):
        """Which money the figures are written in, and whether they can be.

        A gap is a RATIO, so it survives a currency perfectly well; an amount
        does not. So the ratios are always shown, and the amounts are shown
        only when every company in the scope keeps its books in one currency
        — or when the reader asks for the group's money and there is a rate
        for every pair (rule 7: a missing rate is shown, never guessed).
        """
        currencies = companies.mapped('currency_id')
        one = len(set(currencies.ids)) <= 1
        main = self._main_currency(companies)
        meta = {
            'one_currency': one,
            'currency_id': main.id if main else 0,
            'currency_code': main.name if main else '',
            'codes': sorted(set(currencies.mapped('name'))),
            'converted': False, 'rate_note': '', 'unknown': [],
            'rates': {}, 'left_out': [],
        }
        if one:
            return meta
        if not group_money or 'pb.fx' not in self.env:
            meta['rate_note'] = _(
                'The companies in this view keep their books in %(codes)s. '
                'Two amounts in two currencies cannot be compared without a '
                'rate, so only %(main)s is measured here — switch to the '
                'group\'s money to bring the rest in.',
                codes=' · '.join(meta['codes']),
                main=main.name if main else '')
            meta['left_out'] = [c.display_name for c in companies
                                if c.currency_id != main]
            return meta
        FX = self.env['pb.fx']
        target = FX.presentation_currency(companies[:1]) or main
        unknown, rates = [], {}
        for currency in set(currencies):
            if currency == target:
                rates[currency.id] = 1.0
                continue
            answer = FX.rate(currency, target, company=companies[:1])
            if answer.get('known'):
                rates[currency.id] = answer['rate']
            else:
                unknown.append(currency.name)
        meta.update({
            'currency_id': target.id, 'currency_code': target.name,
            'converted': not unknown, 'unknown': unknown, 'rates': rates,
        })
        if unknown:
            meta['rate_note'] = _(
                'Nobody has priced %(codes)s against %(target)s, so those '
                'companies are left out rather than converted at a rate this '
                'product would have to invent.',
                codes=' · '.join(unknown), target=target.name)
            meta['left_out'] = [c.display_name for c in companies
                                if c.currency_id.name in unknown]
        else:
            meta['rate_note'] = _(
                'Shown in %(target)s at the rate on file.', target=target.name)
        return meta

    @api.model
    def _main_currency(self, companies):
        """The money MOST of these people are actually paid in.

        Not `companies[:1].currency_id`: on the demo group that is the
        Singapore entity with nobody in it, so refusing to mix currencies
        would have thrown away four and a half thousand people and kept one.
        The majority currency is the one a refusal should keep.
        """
        if not companies:
            return self.env['res.currency']
        rows = self.env['pb.pay.position'].sudo()._read_group(
            [('company_id', 'in', companies.ids)], ['company_id'], ['__count'])
        counted = {company.id: count for company, count in rows if company}
        by_currency = {}
        for company in companies:
            currency = company.currency_id
            if currency:
                by_currency[currency] = by_currency.get(currency, 0) \
                    + counted.get(company.id, 0)
        if not by_currency:
            return companies[:1].currency_id
        return max(by_currency.items(), key=lambda pair: pair[1])[0]

    @api.model
    def _convert_people(self, people, companies, meta):
        """Put every wage in ONE money, or leave the ones that cannot out.

        Never a converted amount kept anywhere (rule 7): the multiplication
        happens here, on the read, and the answer carries the rate that did it.
        """
        if meta.get('one_currency') or not people:
            return people, []
        by_company = {c.id: c.currency_id.id for c in companies}
        rates = meta.get('rates') or {}
        target = meta.get('currency_id')
        kept, dropped = [], []
        for person in people:
            currency_id = by_company.get(person['company_id'])
            if currency_id == target:
                kept.append(person)
                continue
            rate = rates.get(currency_id)
            if not rate:
                dropped.append(person)
                continue
            person = dict(person)
            person['wage'] = person['wage'] * rate
            kept.append(person)
        return kept, dropped

    @api.model
    def _source_label(self, source, months):
        if source == 'payroll':
            days = sorted(m for m in months.values() if m)
            # The MONTH, not the first of it: "11/01/2026" reads as a day
            # somebody was paid on, and nobody was paid on that day.
            when = format_date(self.env, days[-1], date_format='MMMM yyyy') \
                if days else ''
            return _('From the payroll paid in %(month)s.', month=when)
        if source == 'contracts':
            return _(
                'No approved payroll to read yet, so these figures come from '
                'the pay written on open contracts.')
        return _('There is nobody to measure in this view.')

    # -------------------------------------------------------------- the maths
    @api.model
    def _median(self, values):
        return self.env['pb.pay.bands']._median(values)

    @api.model
    def _gap(self, women, men):
        """How much less the first group's middle is than the second's."""
        if len(women) < MIN_SIDE or len(men) < MIN_SIDE:
            return None
        female = self._median(women)
        male = self._median(men)
        if male <= 0:
            return None
        return (male - female) / male * 100.0

    @api.model
    def gap_for(self, people):
        """The like-for-like gap over a list of people somebody else built.

        The Pay Review uses this to answer the only fairness question that
        matters while a review is being written: what would this review DO to
        the gap. It hands over its own rows twice — once with the pay people
        are on and once with the pay they would be on — and the difference
        between the two answers is the sentence at the top of the screen.

        `people` is `[{'sex', 'level', 'job_id', 'wage'}]`. Level by level
        where bands exist, job by job where they do not, exactly as the
        Fairness screen does it, so the two can never disagree.
        """
        people = [person for person in (people or [])
                  if float(person.get('wage') or 0.0) > 0]
        if not people:
            return {'gap': None, 'compared': 0, 'basis': 'none',
                    'people': 0}
        has_levels = any(person.get('level') for person in people)
        key = 'level' if has_levels else 'job_id'
        rows = [{'sex': (person.get('sex') or 'unknown'),
                 'level': person.get('level') or 0,
                 'job_id': person.get('job_id') or 0,
                 'wage': float(person.get('wage') or 0.0)}
                for person in people]
        gap, compared, skipped = self._weighted_gap(rows, key)
        return {'gap': gap, 'compared': compared, 'skipped': skipped,
                'basis': 'level' if has_levels else 'job',
                'people': len(rows)}

    @api.model
    def _weighted_gap(self, people, key):
        """The gap inside each bucket, weighted by how many women are in it.

        Comparing every woman's pay with every man's answers a different
        question — it mostly measures who holds which job. Comparing them
        LEVEL BY LEVEL (or job by job when there are no bands yet) and
        weighting by the women in each is the like-for-like number, and it is
        the one a regulator asks for.
        """
        buckets = defaultdict(lambda: {'female': [], 'male': []})
        for person in people:
            if person['sex'] not in ('female', 'male'):
                continue
            buckets[person[key] or 0][person['sex']].append(person['wage'])
        total_weight, total = 0.0, 0.0
        compared, skipped = 0, 0
        for values in buckets.values():
            gap = self._gap(values['female'], values['male'])
            if gap is None:
                skipped += len(values['female']) + len(values['male'])
                continue
            weight = float(len(values['female']))
            total += gap * weight
            total_weight += weight
            compared += len(values['female']) + len(values['male'])
        if not total_weight:
            return None, compared, skipped
        return total / total_weight, compared, skipped

    @api.model
    def _cards(self, people, currency):
        cards = []
        women = [p['wage'] for p in people if p['sex'] == 'female']
        men = [p['wage'] for p in people if p['sex'] == 'male']
        has_levels = any(p['level'] for p in people)
        key = 'level' if has_levels else 'job_id'
        gap, compared, skipped = self._weighted_gap(people, key)
        like_for_like = _('level by level') if has_levels \
            else _('job by job')
        if gap is None:
            sentence = _(
                'Not enough people to compare fairly. A gap needs at least '
                '%(count)s women and %(count)s men doing work at the same '
                '%(unit)s.', count=MIN_SIDE,
                unit=_('level') if has_levels else _('job'))
        elif abs(gap) < 0.05:
            sentence = _('Women and men are paid the same, %(basis)s.',
                         basis=like_for_like)
        elif gap > 0:
            sentence = _(
                'Women earn %(pct)s%% less than men doing work at the same '
                '%(unit)s.', pct='{:,.1f}'.format(gap),
                unit=_('level') if has_levels else _('job'))
        else:
            sentence = _(
                'Women earn %(pct)s%% more than men doing work at the same '
                '%(unit)s.', pct='{:,.1f}'.format(abs(gap)),
                unit=_('level') if has_levels else _('job'))
        cards.append({
            'key': 'gender', 'label': _('Pay gap by gender'),
            'value': None if gap is None else round(gap, 1),
            'value_label': '' if gap is None
            else '{:,.1f}%'.format(gap),
            'tone': 'good' if gap is not None and abs(gap) < 1
            else ('rose' if gap is not None and gap > 3 else 'warn'),
            'sentence': sentence,
            'population': _(
                '%(women)s women and %(men)s men, %(compared)s of them in a '
                'group big enough to compare.',
                women=len(women), men=len(men), compared=compared),
            'method': _(
                'The middle pay of each side, compared %(basis)s and averaged '
                'by how many women are in each. Never a straight average of '
                'everybody: that measures who holds which job.',
                basis=like_for_like),
            'icon': 'scale',
        })

        raw = self._gap(women, men)
        cards.append({
            'key': 'raw', 'label': _('Across everybody'),
            'value': None if raw is None else round(raw, 1),
            'value_label': '' if raw is None else '{:,.1f}%'.format(raw),
            'tone': 'teal',
            'sentence': _('Not enough people to compare fairly.')
            if raw is None else _(
                'Comparing every woman with every man, without regard to the '
                'work, the difference is %(pct)s%%.',
                pct='{:,.1f}'.format(raw)),
            'population': _('%(women)s women, %(men)s men.',
                            women=len(women), men=len(men)),
            'method': _(
                'The middle pay of all women against the middle pay of all '
                'men. Published in some countries; it mostly measures which '
                'jobs each group holds.'),
            'icon': 'users',
        })

        unknown = [p for p in people if p['sex'] not in ('female', 'male')]
        if unknown:
            cards.append({
                'key': 'unknown', 'label': _('Nothing on record'),
                'value': len(unknown), 'value_label': str(len(unknown)),
                'tone': 'warn',
                'sentence': _(
                    '%(count)s people have no gender on their record, so they '
                    'are in no comparison above.', count=len(unknown)),
                'population': '', 'method': '', 'icon': 'alert',
            })
        return cards

    @api.model
    def _by_level(self, people):
        buckets = defaultdict(lambda: {'female': [], 'male': [], 'band': ''})
        for person in people:
            if not person['level']:
                continue
            bucket = buckets[person['level']]
            bucket['band'] = bucket['band'] or person['band']
            if person['sex'] in ('female', 'male'):
                bucket[person['sex']].append(person['wage'])
        out = []
        for level in sorted(buckets):
            bucket = buckets[level]
            gap = self._gap(bucket['female'], bucket['male'])
            out.append({
                'level': level,
                'women': len(bucket['female']),
                'men': len(bucket['male']),
                'gap': None if gap is None else round(gap, 1),
                'gap_label': '' if gap is None else '{:,.1f}%'.format(gap),
                'note': _('Not enough people to compare fairly')
                if gap is None else '',
            })
        return out

    @api.model
    def _by_division(self, people):
        if 'pb.division' not in self.env:
            return []
        buckets = defaultdict(lambda: {'female': [], 'male': []})
        for person in people:
            if not person['division_id'] \
                    or person['sex'] not in ('female', 'male'):
                continue
            buckets[person['division_id']][person['sex']].append(
                person['wage'])
        names = {d.id: d.name for d in self.env['pb.division'].sudo().browse(
            list(buckets.keys())).exists()}
        out = []
        for division_id, bucket in buckets.items():
            gap = self._gap(bucket['female'], bucket['male'])
            out.append({
                'id': division_id,
                'name': names.get(division_id, _('Not in a division')),
                'women': len(bucket['female']),
                'men': len(bucket['male']),
                'gap': None if gap is None else round(gap, 1),
                'gap_label': '' if gap is None else '{:,.1f}%'.format(gap),
                'note': _('Not enough people to compare fairly')
                if gap is None else '',
            })
        out.sort(key=lambda row: -(row['women'] + row['men']))
        return out

    @api.model
    def _same_job_spread(self, people, currency):
        Bands = self.env['pb.pay.bands']
        buckets = defaultdict(list)
        for person in people:
            if person['job_id'] and person['wage']:
                buckets[person['job_id']].append(person['wage'])
        names = {job.id: job.display_name
                 for job in self.env['hr.job'].sudo().browse(
                     list(buckets.keys())).exists()}
        out = []
        for job_id, wages in buckets.items():
            if len(wages) < 2:
                continue
            low, high = min(wages), max(wages)
            middle = self._median(wages)
            out.append({
                'id': job_id, 'name': names.get(job_id, ''),
                'people': len(wages),
                'low_label': Bands._money(low, currency),
                'mid_label': Bands._money(middle, currency),
                'high_label': Bands._money(high, currency),
                'spread': round((high / low - 1.0) * 100.0, 1) if low else 0,
                'spread_label': '{:,.0f}%'.format(
                    (high / low - 1.0) * 100.0) if low else '',
            })
        out.sort(key=lambda row: -row['spread'])
        return out[:MAX_ROWS]

    @api.model
    def _lowest_paid(self, people, currency):
        Bands = self.env['pb.pay.bands']
        buckets = defaultdict(list)
        for person in people:
            if person['job_id'] and person['wage']:
                buckets[person['job_id']].append(person['wage'])
        middles = {job_id: self._median(wages)
                   for job_id, wages in buckets.items() if len(wages) >= 3}
        names = {job.id: job.display_name
                 for job in self.env['hr.job'].sudo().browse(
                     list(middles.keys())).exists()}
        show_names = self._can_see_names()
        hits = []
        for person in people:
            middle = middles.get(person['job_id'])
            if not middle or not person['wage']:
                continue
            under = (middle - person['wage']) / middle
            if under < LOW_PAY_GAP:
                continue
            hits.append({
                'id': person['employee_id'] if show_names else 0,
                'name': person['name'] if show_names else _('Someone'),
                'job': names.get(person['job_id'], ''),
                'wage_label': Bands._money(person['wage'], currency)
                if show_names else '',
                'mid_label': Bands._money(middle, currency),
                'under': round(under * 100.0, 1),
                'under_label': '{:,.1f}%'.format(under * 100.0),
            })
        hits.sort(key=lambda row: -row['under'])
        return hits[:MAX_ROWS]

    @api.model
    def _headline(self, board, people):
        cards = board.get('cards') or []
        gender = next((c for c in cards if c['key'] == 'gender'), None)
        if not people:
            return _('There is nobody to measure in this view yet.')
        if gender and gender['sentence']:
            return gender['sentence']
        return _('%(count)s people measured.', count=len(people))

    @api.model
    def _method_lines(self, source, months, companies):
        lines = [self._source_label(source, months)]
        lines.append(_(
            'Basic monthly pay only. Overtime, bonuses and allowances vary '
            'month to month and would make a gap say more about last month '
            'than about pay.'))
        lines.append(_(
            'A comparison is made only where there are at least %(count)s '
            'people on each side. Everything smaller says so rather than '
            'printing a number nobody should act on.', count=MIN_SIDE))
        lines.append(_(
            '"Paid least for the same work" means at least %(pct)s%% under '
            'the middle pay of everybody in the same job, where at least '
            'three people hold it.', pct=int(LOW_PAY_GAP * 100)))
        if len(set(companies.mapped('currency_id').ids)) > 1:
            lines.append(_(
                'Amounts from companies that keep their books in different '
                'money are never added together without a rate.'))
        return lines

    # ============================================================ the print
    @api.model
    def print_statement(self, kind='company', ref=0, group_money=False):
        """One page a board or a regulator can be handed.

        Self-contained by contract: no script, no stylesheet, no image and no
        URL of any kind, exactly like the Decision Room's brief — it is saved
        to a laptop and mailed on, and a page whose layout depends on a server
        it can no longer reach is not a statement.
        """
        if not self._can_read():
            raise AccessError(_("You cannot read this."))
        board = self.get_board(kind, ref, group_money)
        # ONE sentence rather than four template fragments: the stamp on a
        # printed page has to read as a sentence in every language, and
        # Vietnamese does not put "prepared by" where English does (GR22).
        stamp = _(
            'Prepared by %(reader)s on %(day)s · %(count)s people measured',
            reader=self.env.user.display_name,
            day=format_date(self.env, fields.Date.context_today(self)),
            count=board.get('people') or 0)
        html = self.env['ir.qweb']._render('pb_pay.fairness_statement', {
            'board': board,
            'scope_name': (board.get('scope') or {}).get('label') or '',
            'stamp': stamp,
        })
        return '<!doctype html>\n' + str(html)
