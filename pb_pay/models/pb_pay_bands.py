# -*- coding: utf-8 -*-
"""`pb.pay.bands` — the only server surface the Pay Bands screen talks to.

The shape is the one `pb_assets`, `pb.decision.room`, `pb.group.room` and
`pb.assignments` established: an `AbstractModel` facade, `@api.model` reads,
every independent figure inside `_safe()` so one failure answers an empty card
instead of taking the screen down, a cap on anything a caller controls, and a
SERVER-SIDE gate that is the boundary. A reader with no permission gets an
EMPTY, EXPLAINED screen rather than an access dialog.

THE ONE IDEA WORTH READING BEFORE THE CODE
------------------------------------------
A band screen that opens empty is useless, and on a real database it opens
empty: nobody has ever written a band. So the empty state is not a page of
teaching with a button on it — it is a PROPOSAL. `suggest_bands` reads the
wages this company actually pays, groups its job titles into families and
levels from the words in them, and hands back a complete board of SUGGESTED
bands, dots and health cards that draws exactly like a real one and is saved
only if somebody presses "Use these". Day one looks like day two hundred.

WHAT THIS FACADE MAY NOT DO
---------------------------
Write a wage. Nothing here touches `hr.contract.wage`, `hr.payslip` or
`hr.employee`; the only tables it writes are its own three. Dragging a band's
edge moves the BAND, which is a statement of intent, and never a person's pay.
"""

import io
import csv
import base64
import logging
import time
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .bands_approval import BANDS_WRITE

from .pb_pay_band import COUNTRIES, COUNTRY_CURRENCY, MAX_LEVEL

_logger = logging.getLogger(__name__)

WRITE_GROUPS = (
    'pb_pay.group_pay_manager',
    'pb_group.group_group_admin',
)
READ_GROUPS = (
    'pb_pay.group_pay_manager',
    'pb_pay.group_pay_viewer',
    'pb_group.group_group_admin',
    'hr.group_hr_manager',
)

#: EVERY PERSON IS DRAWN (TIDY ledger rule 12). A band picture may never say
#: "and N more not drawn" — if there are too many people for named marks the
#: picture CHANGES SHAPE, it never drops anybody. So the server sends two
#: things: `wages`, one integer per person, always complete, which the browser
#: bins into pips and columns; and `dots`, the named, hoverable form, only
#: while a band is small enough for every dot to carry a name without
#: overlapping. Above that line the names are read back on demand through
#: `people_between`, one bin at a time.
DOT_LIMIT = 24
#: A person can be asked for by name one bin at a time; this caps one answer.
PEOPLE_BETWEEN_LIMIT = 20
MAX_ROWS = 60           # rows inside a health drawer
MAX_IMPORT = 500        # rows accepted from one spreadsheet

#: Tenure, in months, for the two sides of the compression question.
NEW_JOINER_MONTHS = 12
LONG_SERVING_MONTHS = 36

#: The words that put a job title in a family. Checked in order, so a
#: "Warehouse Operative" is Logistics rather than Operations. Deliberately
#: small and readable: it is a SUGGESTION a person then edits, not a taxonomy.
FAMILY_WORDS = [
    ('Engineering', ('engineer', 'developer', 'devops', 'architect',
                     'programmer', 'tech lead', 'qa ')),
    ('Logistics', ('driver', 'rider', 'dispatch', 'warehouse', 'fleet',
                   'delivery', 'logistic')),
    ('Construction', ('construction', 'site', 'steel', 'foreman', 'mason',
                      'scaffold')),
    ('Sales & Retail', ('sales', 'cashier', 'store', 'retail', 'shop',
                        'merchand', 'marketing')),
    ('Finance', ('account', 'finance', 'audit', 'treasur', 'payroll')),
    ('People & Legal', ('hr ', 'human', 'people', 'recruit', 'legal',
                        'counsel', 'compliance')),
    ('Quality & Safety', ('quality', 'qc ', 'safety', 'inspector', 'hse')),
    ('Data & Analysis', ('data', 'analyst', 'analytic', 'research')),
    ('Operations', ('operator', 'operative', 'production', 'machine',
                    'assembly', 'line ', 'shift', 'plant', 'worker')),
]

#: The words that put a job title on a level. Highest match wins.
LEVEL_WORDS = [
    (8, ('director', 'chief', 'head of', 'vp ', 'general manager')),
    (7, ('manager', 'counsel', 'principal')),
    (6, ('lead', 'supervisor', 'foreman', 'area ')),
    (5, ('senior', 'specialist', 'engineer', 'accountant', 'analyst',
         'officer')),
    (4, ('inspector', 'leader', 'coordinator', 'technician')),
    (3, ('associate', 'assistant', 'junior', 'clerk')),
]
DEFAULT_LEVEL = 2

#: Short-form money. The suffix is translated, so a Vietnamese reader gets
#: "tỷ" where an English one gets "B", and the SYMBOL is written once (WF22).
_SHORT_STEPS = ((1e9, 'B'), (1e6, 'M'), (1e3, 'K'))


class PbPayBands(models.AbstractModel):
    _name = 'pb.pay.bands'
    # GROUP P7 — every read on this screen goes through `who sees what`.
    # A reader with no visibility row is narrowed by nothing at all.
    _inherit = ['pb.group.scoped']
    _description = 'Pay bands'

    # ================================================================= gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as error:      # noqa: BLE001
            _logger.debug('Pay bands figure failed: %s', error)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        if user._is_admin():
            return True
        return any(self._safe(lambda n=n: user.has_group(n), default=False)
                   for n in READ_GROUPS)

    @api.model
    def _can_write(self):
        user = self.env.user
        if user._is_admin():
            return True
        return any(self._safe(lambda n=n: user.has_group(n), default=False)
                   for n in WRITE_GROUPS)

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "You can look at the pay bands, but changing one is for a pay "
                "manager. Ask one of them to make the change."))
        return True

    # ================================================================= money
    @api.model
    def _money(self, amount, currency):
        """One amount, written the way this currency writes it."""
        currency = currency or self.env.company.currency_id
        decimals = currency.decimal_places if currency else 2
        text = '{:,.{d}f}'.format(float(amount or 0.0), d=decimals)
        symbol = currency.symbol if currency else ''
        if currency and currency.position == 'before':
            return '%s%s' % (symbol, text)
        return '%s %s' % (text, symbol)

    @api.model
    def _short(self, amount, currency):
        """"₫184M" — the compact form, symbol written exactly once (WF22)."""
        currency = currency or self.env.company.currency_id
        symbol = currency.symbol if currency else ''
        value = float(amount or 0.0)
        sign = '-' if value < 0 else ''
        value = abs(value)
        labels = {'B': _('B'), 'M': _('M'), 'K': _('K')}
        for step, key in _SHORT_STEPS:
            if value >= step:
                shown = value / step
                digits = 1 if shown < 10 else 0
                body = '{:,.{d}f}{s}'.format(shown, d=digits, s=labels[key])
                break
        else:
            body = '{:,.0f}'.format(value)
        if currency and currency.position == 'before':
            return '%s%s%s' % (sign, symbol, body)
        return '%s%s %s' % (sign, body, symbol)

    @api.model
    def _people_phrase(self, count):
        """"1 person" or "24 people".

        The platform's `_()` has no plural form, and "1 people" on a band that
        holds one person is the kind of thing a reader notices before they
        notice anything else on the screen.
        """
        count = int(count or 0)
        if count == 1:
            return _('1 person')
        return _('%(count)s people', count=count)

    # ============================================================ the reading
    @api.model
    def _companies(self, company_ids=None):
        """Every company the reader may see, narrowed by what they asked for.

        `res.users.company_ids` and never `env.companies`: the switcher is a
        menu, and a person looking at pay bands for a group should not have to
        tick five boxes first (GR27, GR37 — this family has cost four bugs).
        """
        allowed = self.env.user.company_ids
        # GROUP P7 — narrowed to what this reader may see, and untouched for
        # anybody who has not been limited.
        visible = set(self._visible_companies(allowed.ids))
        allowed = allowed.filtered(lambda c: c.id in visible)
        if company_ids:
            wanted = {int(c) for c in company_ids}
            narrowed = allowed.filtered(lambda c: c.id in wanted)
            if narrowed:
                return narrowed
        return allowed

    @api.model
    def get_board(self, company_ids=None, family_id=0, country=''):
        started = time.time()
        blank = {
            'allowed': False, 'can_write': False, 'lanes': [], 'families': [],
            'countries': [], 'companies': [], 'health': [], 'unbanded': {},
            'suggestion': None, 'levels': list(range(1, MAX_LEVEL + 1)),
            'filters': {}, 'has_bands': False, 'ms': 0,
        }
        if not self._can_read():
            return blank
        companies = self._companies(company_ids)
        board = dict(blank)
        board.update({
            'allowed': True,
            'can_write': self._can_write(),
            'companies': [{'id': c.id, 'name': c.display_name,
                           'currency': c.currency_id.name}
                          for c in companies],
            'families': self._safe(lambda: self._families(), default=[]),
            'countries': self._safe(lambda: self._countries(), default=[]),
            'filters': {
                'company_ids': companies.ids,
                'family_id': int(family_id or 0),
                'country': country or '',
            },
        })
        rows = self._safe(
            lambda: self._positions(companies, family_id, country), default=[])
        bands = self._safe(
            lambda: self._bands_for(companies, family_id, country), default=[])
        board['has_bands'] = bool(
            self.env['pb.pay.band'].sudo().search_count([]))
        board['lanes'] = self._safe(
            lambda: self._lanes(bands, rows, companies), default=[])
        board['unbanded'] = self._safe(
            lambda: self._unbanded(rows, companies), default={})
        # The rows and the tenure query are handed DOWN rather than read a
        # second time: the board already knows every position, and the health
        # cards would otherwise repeat a 4,500-row read and two SQL passes for
        # figures built from exactly the same facts.
        board['health'] = self._safe(
            lambda: self.health_cards(companies.ids, rows=rows,
                                      companies=companies), default=[])
        board['ms'] = int((time.time() - started) * 1000)
        return board

    @api.model
    def _families(self):
        return [{'id': f.id, 'name': f.name, 'bands': f.band_count}
                for f in self.env['pb.pay.family'].sudo().search([])]

    @api.model
    def _countries(self):
        counted = defaultdict(int)
        for band in self.env['pb.pay.band'].sudo().search([]):
            counted[band.country_code] += 1
        return [{'code': code, 'label': label, 'bands': counted.get(code, 0)}
                for code, label in COUNTRIES]

    @api.model
    def _bands_for(self, companies, family_id=0, country=''):
        day = fields.Date.context_today(self)
        domain = [('date_from', '<=', day),
                  '|', ('date_to', '=', False), ('date_to', '>=', day)]
        if family_id:
            domain.append(('family_id', '=', int(family_id)))
        if country:
            domain.append(('country_code', '=', country))
        bands = self.env['pb.pay.band'].sudo().search(domain)
        ids = set(companies.ids)
        return bands.filtered(
            lambda b: not b.company_ids or (set(b.company_ids.ids) & ids))

    @api.model
    def _positions(self, companies, family_id=0, country=''):
        """Every open contract's place, with the name to print on its dot."""
        if not companies:
            return []
        domain = [('company_id', 'in', companies.ids)]
        rows = self.env['pb.pay.position'].sudo().search_read(
            domain, ['employee_id', 'contract_id', 'company_id', 'job_id',
                     'band_id', 'wage', 'currency_id', 'position_pct',
                     'compa', 'state'])
        out = []
        for row in rows:
            out.append({
                'id': row['id'],
                'employee_id': (row['employee_id'] or [0])[0],
                'name': (row['employee_id'] or [0, ''])[1],
                'contract_id': (row['contract_id'] or [0])[0],
                'company_id': (row['company_id'] or [0])[0],
                'job_id': (row['job_id'] or [0])[0],
                'job': (row['job_id'] or [0, ''])[1],
                'band_id': (row['band_id'] or [0])[0],
                'currency_id': (row['currency_id'] or [0])[0],
                'wage': row['wage'],
                'pct': row['position_pct'],
                'compa': row['compa'],
                'state': row['state'],
            })
        return out

    @api.model
    def _lane_axis(self, bands, rows, currency):
        """The shared money axis a lane's bands are drawn on.

        ONE axis for every band in a currency, because the whole point of the
        picture is that a level 2 band and a level 8 band can be compared at a
        glance. The awkward part is the tail: one person paid four times the
        top of the highest band stretches the axis until every band is a
        sliver and the picture says nothing.

        So the axis runs to the top of the highest BAND, or to the pay of the
        95th person out of a hundred, whichever is greater — and the handful
        beyond it sit ON the right-hand edge with the lane saying how many and
        what the edge is worth. A clamped dot is always an "above the band"
        dot, so it is already marked, already counted, and its real pay is on
        its own label.
        """
        band_top = max([band['max'] for band in bands] or [0]) or 0.0
        wages = sorted(row['wage'] for row in rows if row['wage'])
        percentile = 0.0
        if wages:
            percentile = wages[min(len(wages) - 1, int(len(wages) * 0.95))]
        high = (max(band_top, percentile) or (wages[-1] if wages else 1.0)) \
            * 1.08
        high = high or 1.0
        beyond = sum(1 for wage in wages if wage > high)
        ticks = []
        for step in range(0, 5):
            value = high * step / 4.0
            ticks.append({'value': value,
                          'label': self._short(value, currency),
                          'first': step == 0,
                          'last': step == 4})
        note = ''
        if beyond:
            # The WHOLE sentence branches, not just the count: the platform's
            # `_()` has no plural form (GR42) and a phrase dropped into one
            # frame cannot fix the verb beside it (RIZE R117). On AB Mauri
            # most lanes hold exactly one person out here, and "1 people are
            # paid" is the first thing a reader sees.
            edge = self._short(high, currency)
            note = _(
                '1 person is paid more than %(edge)s and sits on the '
                'right-hand edge. Their own pay is on their label.',
                edge=edge) if beyond == 1 else _(
                '%(count)s people are paid more than %(edge)s and sit on the '
                'right-hand edge. Their own pay is on their label.',
                count=beyond, edge=edge)
        return {'min': 0.0, 'max': high, 'ticks': ticks, 'beyond': beyond,
                'note': note}

    @api.model
    def _family_axes(self, entries, wages_for, currency):
        """One money axis per job family, for a reader who asks to fit to it.

        The shared axis above is the RIGHT default and stays the default: the
        whole point of the picture is that a level 2 band and a level 8 band
        can be compared at a glance. But a company whose cleaners and whose
        directors are in the same currency draws the cleaning family as a
        sliver, and "how wide is this band compared with its own neighbours"
        is a real question the shared axis cannot answer.

        So every family also gets its own axis, computed by exactly the same
        rule as the shared one (the top of the highest band or the 95th
        person, whichever is greater, and the tail named rather than hidden —
        ledger GR43). Which one is drawn is the reader's choice, remembered
        in their own browser, and the screen says out loud that widths stop
        being comparable between families while it is on.

        Computed here rather than in the browser because the tick labels are
        MONEY, and money is written the way its own currency writes it, not
        the way the reader's browser happens to.
        """
        groups, order = {}, []
        for entry in entries:
            key = entry.get('family') or ''
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(entry)
        out = []
        for key in order:
            members = groups[key]
            rows = [{'wage': wage} for wage in wages_for(members)]
            out.append({
                'key': key,
                'name': key or _('No job family'),
                'bands': len(members),
                'axis': self._lane_axis(members, rows, currency),
            })
        return out

    @api.model
    def _dot(self, row, band, currency):
        span = (band['max'] - band['min']) or 1.0
        pct = ((row['wage'] - band['min']) / span) * 100.0
        return {
            'id': row['employee_id'],
            'name': row['name'],
            'job': row['job'],
            'wage': row['wage'],
            'wage_label': self._money(row['wage'], currency),
            'pct': round(pct, 1),
            'state': row['state'],
        }

    @api.model
    def _band_dict(self, band, currency=None):
        currency = currency or band.currency_id
        countries = dict(COUNTRIES)
        since = _('In force since %(day)s',
                  day=fields.Date.to_string(band.date_from))
        return {
            'id': band.id,
            'name': band.name,
            'family': band.family_id.name,
            'family_id': band.family_id.id,
            'level': band.level,
            'country': countries.get(band.country_code, band.country_code),
            'country_code': band.country_code,
            'currency_id': currency.id,
            'currency_code': currency.name,
            'min': band.min_amount,
            'mid': band.mid_amount,
            'max': band.max_amount,
            'min_label': self._money(band.min_amount, currency),
            'mid_label': self._money(band.mid_amount, currency),
            'max_label': self._money(band.max_amount, currency),
            'min_short': self._short(band.min_amount, currency),
            'max_short': self._short(band.max_amount, currency),
            'date_from': fields.Date.to_string(band.date_from),
            'date_to': fields.Date.to_string(band.date_to) if band.date_to
            else '',
            'since_label': since,
            'jobs': [{'id': link.job_id.id, 'name': link.job_id.display_name,
                      'link_id': link.id} for link in band.job_ids],
            'note': band.note or '',
            'suggested': False,
        }

    @api.model
    def _fill_band(self, entry, rows, currency):
        """Put the people on a band and count how they stand.

        `wages` is EVERY person's pay, sorted, as whole units of the currency —
        the complete list, however many there are, because the picture is
        binned in the browser and rule 12 says nobody is dropped. Rounding to
        whole units is not a loss: the picture is drawn at eight pixels to a
        bin, which on any real money axis is millions of dong wide.

        `dots` — the named form — is sent only while the band is small enough
        to draw one mark per person with a name on it. Above that, names are
        fetched a bin at a time by `people_between`, so the payload of a
        four-thousand-person board stays small and no name is ever shipped
        that nobody asked for.
        """
        entry = dict(entry)
        inside = [r for r in rows if r['band_id'] == entry['id']]
        inside.sort(key=lambda r: r['wage'])
        entry['people'] = len(inside)
        entry['below'] = sum(1 for r in inside if r['state'] == 'below')
        entry['above'] = sum(1 for r in inside if r['state'] == 'above')
        entry['in_band'] = entry['people'] - entry['below'] - entry['above']
        entry['wages'] = [int(round(r['wage'] or 0)) for r in inside]
        # The browser writes the money on a bin's own label, so it needs the
        # symbol and which side of the number it goes (WF22: written once).
        entry['symbol'] = currency.symbol if currency else ''
        entry['symbol_before'] = bool(currency
                                      and currency.position == 'before')
        entry['dots'] = ([self._dot(r, entry, currency) for r in inside]
                         if len(inside) <= DOT_LIMIT else [])
        entry['people_scope'] = {'band_id': entry['id']}
        wages = [r['wage'] for r in inside if r['wage']]
        entry['median'] = self._median(wages)
        entry['median_label'] = self._money(entry['median'], currency) \
            if wages else ''
        entry['median_note'] = _('median %(amount)s',
                                 amount=self._short(entry['median'], currency)) \
            if wages else ''
        entry.update(self._band_labels(entry, currency))
        return entry

    @api.model
    def _band_labels(self, entry, currency):
        """Every line under a band as ONE string.

        The whitespace between two adjacent template nodes is whitespace the
        browser may collapse, so a sentence assembled from four of them can
        render as one run-on word (ledger GR22) — and it is untranslatable
        besides, because Vietnamese does not put those pieces in that order.
        """
        return {
            'sub_label': _(
                '%(people)s · %(low)s to %(high)s',
                people=self._people_phrase(entry.get('people', 0)),
                low=entry.get('min_short', ''),
                high=entry.get('max_short', '')),
            'below_label': _('%(count)s below', count=entry.get('below', 0)),
            'above_label': _('%(count)s above', count=entry.get('above', 0)),
        }

    @api.model
    def _lanes(self, bands, rows, companies):
        """Bands grouped by the money they are written in.

        Two currencies in one picture would put a Singapore dollar beside a
        dong on the same axis, which is the one thing a money chart may never
        do. Each currency gets its OWN lane with its own axis (§8).
        """
        by_currency = defaultdict(list)
        for band in bands:
            by_currency[band.currency_id].append(band)
        lanes = []
        for currency, members in by_currency.items():
            entries = [self._band_dict(b, currency) for b in members]
            entries = [self._fill_band(e, rows, currency) for e in entries]
            entries.sort(key=lambda e: (e['family'], e['level']))
            lanes.append({
                'currency_id': currency.id,
                'currency_code': currency.name,
                'symbol': currency.symbol,
                'title': _('%(code)s · %(count)s bands',
                           code=currency.name, count=len(entries)),
                'axis': self._lane_axis(
                    entries,
                    [r for r in rows
                     if r['band_id'] in {e['id'] for e in entries}],
                    currency),
                'families': self._family_axes(
                    entries,
                    lambda group: [
                        r['wage'] for r in rows
                        if r['band_id'] in {m['id'] for m in group}],
                    currency),
                'bands': entries,
            })
        lanes.sort(key=lambda lane: -sum(b['people'] for b in lane['bands']))
        return lanes

    @api.model
    def _unbanded(self, rows, companies):
        """The people whose job has no band yet — a lane, never a silence."""
        loose = [r for r in rows if not r['band_id']]
        by_job = defaultdict(list)
        for row in loose:
            by_job[(row['job_id'], row['job'])].append(row['wage'])
        currency = companies[:1].currency_id if companies \
            else self.env.company.currency_id
        jobs = []
        for (job_id, job), wages in by_job.items():
            median = self._median(wages)
            jobs.append({
                'id': job_id, 'name': job or _('No job on record'),
                'people': len(wages), 'median': median,
                'median_label': self._money(median, currency),
            })
        jobs.sort(key=lambda j: -j['people'])
        return {'people': len(loose), 'jobs': jobs[:MAX_ROWS],
                'title': _('Not in a band yet — %(people)s',
                           people=self._people_phrase(len(loose))),
                'more': max(0, len(jobs) - MAX_ROWS)}

    # ==================================================== who is in that bin
    @api.model
    def people_between(self, scope, low, high, limit=PEOPLE_BETWEEN_LIMIT):
        """The people standing in one slice of a band, by name.

        This is the half of rule 12 the picture cannot draw. Above two dozen
        people a band is drawn as columns, which say HOW MANY and never WHO —
        so a column is a button, and pressing it asks this. The answer is
        scoped exactly as the board is (the reader's own companies, narrowed
        again by what they are allowed to see), cut to a page, and it says how many
        there are in total so "and N more" is a fact about the LIST rather
        than about the picture.
        """
        blank = {'total': 0, 'rows': [], 'allowed': False, 'more': 0,
                 'more_label': '', 'title': ''}
        if not self._can_read():
            return blank
        scope = dict(scope or {})
        limit = int(limit or PEOPLE_BETWEEN_LIMIT)
        limit = max(1, min(limit, PEOPLE_BETWEEN_LIMIT))
        low, high = float(low or 0.0), float(high or 0.0)
        if high < low:
            low, high = high, low
        companies = self._companies()
        if not companies:
            return blank

        band_id = int(scope.get('band_id') or 0)
        if band_id:
            band = self.env['pb.pay.band'].sudo().browse(band_id).exists()
            if not band:
                return blank
            currency = band.currency_id
            edges = (band.min_amount, band.max_amount)
            found = self.env['pb.pay.position'].sudo().search_read(
                [('band_id', '=', band_id),
                 ('company_id', 'in', companies.ids),
                 ('wage', '>=', low), ('wage', '<=', high)],
                ['employee_id', 'job_id', 'wage'], order='wage asc')
            people = [{'employee_id': (r['employee_id'] or [0])[0],
                       'name': (r['employee_id'] or [0, ''])[1],
                       'job': (r['job_id'] or [0, ''])[1],
                       'wage': r['wage']} for r in found]
        else:
            # A suggested band: the same buckets `suggest_bands` built, read
            # again rather than remembered, so nothing the browser sends can
            # widen what comes back.
            family = scope.get('family') or ''
            level = int(scope.get('level') or 0)
            company_id = int(scope.get('company_id') or 0)
            edges = (float(scope.get('min') or 0.0),
                     float(scope.get('max') or 0.0))
            wanted = companies.filtered(lambda c: c.id == company_id) \
                if company_id else companies
            if not wanted:
                return blank
            currency = wanted[:1].currency_id or self.env.company.currency_id
            rows = self._tenure_rows(wanted)
            names = {job.id: job.display_name
                     for job in self.env['hr.job'].sudo().browse(
                         list({r['job_id'] for r in rows if r['job_id']}))}
            people = []
            for row in rows:
                title = names.get(row['job_id'])
                if not title or not row['wage']:
                    continue
                if self._family_for(title) != family:
                    continue
                if self._level_for(title) != level:
                    continue
                if row['wage'] < low or row['wage'] > high:
                    continue
                people.append({'employee_id': row['employee_id'],
                               'name': row['name'], 'job': title,
                               'wage': row['wage']})
            people.sort(key=lambda p: p['wage'])

        listed = people[:limit]
        rows = []
        for person in listed:
            wage = person['wage']
            state = 'in'
            if wage < edges[0]:
                state = 'below'
            elif wage > edges[1]:
                state = 'above'
            rows.append({
                'id': person['employee_id'],
                'name': person['name'] or _('Somebody with no name on record'),
                'job': person['job'] or _('No job on record'),
                'wage': wage,
                'wage_label': self._money(wage, currency),
                'state': state,
            })
        more = max(0, len(people) - len(listed))
        return {
            'allowed': True,
            'total': len(people),
            'rows': rows,
            'more': more,
            'more_label': _('and %(count)s more.', count=more) if more else '',
            'title': _('%(people)s · %(low)s to %(high)s',
                       people=self._people_phrase(len(people)),
                       low=self._short(low, currency),
                       high=self._short(high, currency)),
        }

    @api.model
    def _median(self, values):
        values = sorted(v for v in values if v is not None)
        if not values:
            return 0.0
        middle = len(values) // 2
        if len(values) % 2:
            return float(values[middle])
        return (values[middle - 1] + values[middle]) / 2.0

    # =========================================================== health cards
    @api.model
    def health_cards(self, company_ids=None, rows=None, companies=None):
        """The five questions nobody remembers to ask.

        Every card carries its own DEFINITION in the words the screen shows,
        because a number whose method is a mystery is worse than no number:
        somebody will act on it and be unable to say why.
        """
        if not self._can_read():
            return []
        if companies is None:
            companies = self._companies(company_ids)
        if rows is None:
            rows = self._safe(lambda: self._positions(companies), default=[])
        tenure = self._safe(lambda: self._tenure_rows(companies), default=[])
        cards = [
            self._safe(lambda: self._card_outside(rows, companies, 'below'),
                       default=None),
            self._safe(lambda: self._card_outside(rows, companies, 'above'),
                       default=None),
            self._safe(lambda: self._card_compression(companies, tenure),
                       default=None),
            self._safe(lambda: self._card_inversion(companies, tenure),
                       default=None),
            self._safe(lambda: self._card_spread(rows, companies),
                       default=None),
        ]
        return [c for c in cards if c]

    @api.model
    def _currency_of(self, company_id, companies):
        company = companies.filtered(lambda c: c.id == company_id)
        return company[:1].currency_id or self.env.company.currency_id

    @api.model
    def _card_outside(self, rows, companies, side):
        hits = [r for r in rows if r['state'] == side]
        hits.sort(key=lambda r: r['pct'], reverse=(side == 'above'))
        listed = []
        cost = defaultdict(float)
        bands = {b.id: b for b in self.env['pb.pay.band'].sudo().browse(
            list({r['band_id'] for r in hits if r['band_id']}))}
        for row in hits[:MAX_ROWS]:
            band = bands.get(row['band_id'])
            currency = self._currency_of(row['company_id'], companies)
            edge = (band.min_amount if side == 'below' else band.max_amount) \
                if band else 0.0
            listed.append({
                'id': row['employee_id'], 'name': row['name'],
                'job': row['job'],
                'band': band.name if band else '',
                'wage_label': self._money(row['wage'], currency),
                'edge_label': self._money(edge, currency),
                'pct': round(row['pct'], 1),
            })
        for row in hits:
            band = bands.get(row['band_id'])
            if not band:
                continue
            if side == 'below':
                cost[row['company_id']] += max(
                    0.0, band.min_amount - row['wage'])
        totals = []
        for company_id, amount in cost.items():
            currency = self._currency_of(company_id, companies)
            totals.append(self._short(amount * 12, currency))
        if side == 'below':
            label = _('Paid below the band')
            blurb = _(
                'Their pay is under the lowest amount their band allows.')
            money = _('%(cost)s a year would bring everybody back in',
                      cost=' · '.join(totals)) if totals else ''
        else:
            label = _('Paid above the band')
            blurb = _(
                'Their pay is over the highest amount their band allows. That '
                'is not always wrong — it is always worth knowing.')
            money = ''
        return {
            'key': side, 'label': label, 'count': len(hits),
            'tone': 'rose' if side == 'below' else 'warn',
            'icon': 'trendingDown' if side == 'below' else 'trendingUp',
            'blurb': blurb, 'money': money, 'rows': listed,
            'more': max(0, len(hits) - len(listed)),
            'more_label': _('and %(count)s more.',
                            count=max(0, len(hits) - len(listed))),
            'method': _(
                'Every open contract, measured against the band in force '
                'today for its job.'),
        }

    @api.model
    def _tenure_rows(self, companies):
        """Wage, job, company and months of service, in one statement."""
        if not companies:
            return []
        self.env.cr.execute("""
            SELECT DISTINCT ON (c.employee_id)
                   c.employee_id, e.name, c.company_id,
                   COALESCE(c.job_id, v.job_id) AS job_id,
                   COALESCE(c.wage, 0)::float,
                   c.date_start
              FROM hr_contract c
              JOIN hr_employee e ON e.id = c.employee_id AND e.active
         LEFT JOIN hr_version v ON v.id = e.current_version_id
             WHERE c.state = 'open' AND c.active AND c.company_id IN %s
          ORDER BY c.employee_id, c.date_start ASC NULLS LAST, c.id ASC
        """, [tuple(companies.ids)])
        today = fields.Date.context_today(self)
        out = []
        for emp_id, name, company_id, job_id, wage, start in \
                self.env.cr.fetchall():
            months = 0
            if start:
                months = (today.year - start.year) * 12 \
                    + (today.month - start.month)
            out.append({'employee_id': emp_id, 'name': name,
                        'company_id': company_id, 'job_id': job_id,
                        'wage': wage, 'months': months})
        return out

    @api.model
    def _card_compression(self, companies, rows=None):
        rows = self._tenure_rows(companies) if rows is None else rows
        jobs = defaultdict(list)
        for row in rows:
            if row['job_id']:
                jobs[(row['company_id'], row['job_id'])].append(row)
        hits = []
        for key, people in jobs.items():
            old = [p['wage'] for p in people
                   if p['months'] >= LONG_SERVING_MONTHS]
            if len(old) < 3:
                continue
            middle = self._median(old)
            for person in people:
                if person['months'] < NEW_JOINER_MONTHS \
                        and person['wage'] > middle:
                    hits.append((person, middle, key))
        hits.sort(key=lambda h: -(h[0]['wage'] - h[1]))
        names = {job.id: job.display_name
                 for job in self.env['hr.job'].sudo().browse(
                     list({k[1] for _p, _m, k in hits}))}
        listed = []
        for person, middle, key in hits[:MAX_ROWS]:
            currency = self._currency_of(person['company_id'], companies)
            listed.append({
                'id': person['employee_id'], 'name': person['name'],
                'job': names.get(key[1], ''),
                'wage_label': self._money(person['wage'], currency),
                'edge_label': self._money(middle, currency),
                'pct': person['months'],
            })
        return {
            'key': 'compression', 'label': _('Newer people paid more'),
            'count': len(hits), 'tone': 'warn', 'icon': 'arrowLeftRight',
            'blurb': _(
                'Somebody in their first year is paid more than the middle of '
                'what long-serving people in the same job earn.'),
            'money': '', 'rows': listed,
            'more': max(0, len(hits) - len(listed)),
            'more_label': _('and %(count)s more.',
                            count=max(0, len(hits) - len(listed))),
            'method': _(
                'Less than %(new)s months of service, paid above the middle '
                'of everybody with %(old)s months or more in the same job and '
                'company. Jobs with fewer than three long-serving people are '
                'skipped.', new=NEW_JOINER_MONTHS, old=LONG_SERVING_MONTHS),
        }

    @api.model
    def _card_inversion(self, companies, tenure=None):
        if tenure is None:
            tenure = self._tenure_rows(companies)
        rows = {r['employee_id']: r for r in tenure}
        if not rows:
            return None
        self.env.cr.execute("""
            SELECT id, parent_id FROM hr_employee
             WHERE id IN %s AND parent_id IS NOT NULL
        """, [tuple(rows.keys())])
        hits = []
        for emp_id, parent_id in self.env.cr.fetchall():
            report = rows.get(emp_id)
            manager = rows.get(parent_id)
            if not report or not manager:
                continue
            if manager['company_id'] != report['company_id']:
                # Two entities, two currencies, and no honest comparison
                # without a rate — so the card does not make one (rule 7).
                continue
            if manager['wage'] and report['wage'] > manager['wage']:
                hits.append((manager, report))
        hits.sort(key=lambda h: -(h[1]['wage'] - h[0]['wage']))
        listed = []
        for manager, report in hits[:MAX_ROWS]:
            currency = self._currency_of(manager['company_id'], companies)
            listed.append({
                'id': manager['employee_id'], 'name': manager['name'],
                'job': _('reports: %(name)s', name=report['name']),
                'wage_label': self._money(manager['wage'], currency),
                'edge_label': self._money(report['wage'], currency),
                'pct': 0,
            })
        return {
            'key': 'inversion', 'label': _('A manager paid less'),
            'count': len(hits), 'tone': 'rose', 'icon': 'userX',
            'blurb': _(
                'Somebody is paid less than a person who reports to them.'),
            'money': '', 'rows': listed,
            'more': max(0, len(hits) - len(listed)),
            'more_label': _('and %(count)s more.',
                            count=max(0, len(hits) - len(listed))),
            'method': _(
                'Open contracts only, and only where both people are paid by '
                'the same company — two entities keep their books in two '
                'currencies and there is no honest comparison without a rate.'),
        }

    @api.model
    def _card_spread(self, rows, companies):
        by_band = defaultdict(list)
        for row in rows:
            if row['band_id'] and row['wage']:
                by_band[row['band_id']].append(row['wage'])
        bands = {b.id: b for b in self.env['pb.pay.band'].sudo().browse(
            list(by_band.keys()))}
        listed = []
        for band_id, wages in by_band.items():
            band = bands.get(band_id)
            if not band or len(wages) < 2:
                continue
            low, high = min(wages), max(wages)
            if low <= 0:
                continue
            listed.append({
                'id': band_id, 'name': band.name, 'job': '',
                'wage_label': self._money(low, band.currency_id),
                'edge_label': self._money(high, band.currency_id),
                'pct': round((high / low - 1.0) * 100.0, 1),
            })
        listed.sort(key=lambda r: -r['pct'])
        wide = [r for r in listed if r['pct'] >= 100.0]
        return {
            'key': 'spread', 'label': _('How wide each band has become'),
            'count': len(wide), 'tone': 'teal', 'icon': 'sliders',
            'blurb': _(
                'The highest paid person in a band, next to the lowest. A very '
                'wide band is usually two jobs wearing one name.'),
            'money': '', 'rows': listed[:MAX_ROWS],
            'more': max(0, len(listed) - MAX_ROWS),
            'more_label': _('and %(count)s more.',
                            count=max(0, len(listed) - MAX_ROWS)),
            'method': _(
                'Highest pay divided by lowest pay inside each band. Counted '
                'here when the highest is at least twice the lowest.'),
        }

    # ============================================================= the hero
    @api.model
    def move_edge(self, band_id, side, amount, dry_run=True):
        """Drag an edge. Answers what it would cost before it does anything.

        The DRY RUN is the point: the sentence under the picture has to be true
        while somebody is still dragging, so the cost is computed from the
        proposed edge and nothing is written until they let go. The answer
        carries the band's PREVIOUS three numbers so the undo is exact rather
        than a second guess at what they were.
        """
        if not self._can_read():
            raise AccessError(_("You cannot read the pay bands."))
        band = self.env['pb.pay.band'].sudo().browse(int(band_id)).exists()
        if not band:
            raise UserError(_("That band no longer exists."))
        if side not in ('min', 'max'):
            raise UserError(_("A band has a lowest and a highest edge."))
        amount = float(amount or 0.0)
        currency = band.currency_id
        low = amount if side == 'min' else band.min_amount
        high = amount if side == 'max' else band.max_amount
        if high <= low:
            return {
                'ok': False,
                'sentence': _(
                    "The lowest amount has to stay under the highest one."),
                'outliers': [], 'count': 0, 'cost': 0.0, 'cost_label': '',
            }
        mid = band.mid_amount
        mid = min(max(mid, low), high)

        rows = self.env['pb.pay.position'].sudo().search_read(
            [('band_id', '=', band.id)],
            ['employee_id', 'job_id', 'wage', 'position_pct'])
        outliers, cost = [], 0.0
        for row in rows:
            wage = row['wage'] or 0.0
            gap = 0.0
            if wage < low:
                gap = low - wage
            elif wage > high:
                gap = 0.0       # nobody is paid DOWN to fit a band
            if wage < low or wage > high:
                outliers.append({
                    'id': (row['employee_id'] or [0])[0],
                    'name': (row['employee_id'] or [0, ''])[1],
                    'job': (row['job_id'] or [0, ''])[1],
                    'wage': wage,
                    'wage_label': self._money(wage, currency),
                    'gap': gap,
                    'gap_label': self._money(gap, currency) if gap else '',
                    'side': 'below' if wage < low else 'above',
                })
                cost += gap
        outliers.sort(key=lambda o: -o['gap'])
        yearly = cost * 12.0
        if not outliers:
            sentence = _("Nobody falls outside the band there.")
        elif cost:
            sentence = _(
                '%(cost)s a year to bring %(people)s back in',
                cost=self._short(yearly, currency),
                people=self._people_phrase(
                    len([o for o in outliers if o['side'] == 'below'])))
        else:
            sentence = _('%(people)s would sit above the band',
                         people=self._people_phrase(len(outliers)))

        answer = {
            'ok': True,
            'band_id': band.id,
            'side': side,
            'amount': amount,
            'amount_label': self._money(amount, currency),
            'min': low, 'mid': mid, 'max': high,
            'previous': {'min': band.min_amount, 'mid': band.mid_amount,
                         'max': band.max_amount},
            'outliers': outliers[:MAX_ROWS],
            'count': len(outliers),
            'cost': yearly,
            'cost_label': self._short(yearly, currency),
            'sentence': sentence,
            'saved': False,
        }
        if not dry_run:
            # The gate belonged here and was not here: the dry run reads, the
            # let-go WRITES, and only the write branch ever asked.
            self._require_write()
            held = self._bands_propose(
                'move_edge',
                _("Move the %(side)s edge of %(band)s",
                  side=_('lowest') if side == 'min' else _('highest'),
                  band=band.display_name or ''),
                payload={'band_id': band.id, 'side': side, 'amount': amount},
                snapshot={'min': band.min_amount, 'mid': band.mid_amount,
                          'max': band.max_amount},
                facts=self._band_facts(band, low, high, len(rows)),
                target=band)
            if held is not None:
                answer.update(held)
                return answer
            band.write({'min_amount': low, 'mid_amount': mid,
                        'max_amount': high})
            self.env['pb.pay.position'].sudo().recompute_all(
                self._companies().ids)
            answer['saved'] = True
        return answer

    # =================================================== is anybody checking?
    @api.model
    def _bands_propose(self, kind, title, payload, snapshot=None, facts=None,
                       target=None):
        """Write the change down and ask. None means "carry on and write".

        The approved apply calls straight back into these methods, so the flag
        it sets is what tells them apart.
        """
        if self.env.context.get(BANDS_WRITE) \
                or 'pb.bands.proposal' not in self.env:
            return None
        answer = self.env['pb.bands.proposal'].propose(
            kind, title, payload=payload, snapshot=snapshot or {},
            facts=facts or {}, target=target).answer()
        if answer.get('applied'):
            return None
        return {'ok': True, 'saved': False, 'pending': True,
                'reference': answer.get('reference'),
                'with_whom': answer.get('with_whom'),
                'route': answer.get('route'),
                'sentence': _("Sent for approval — %s",
                              answer.get('with_whom') or _('your approver'))}

    @api.model
    def _band_facts(self, band, low=None, high=None, people=0):
        """The three things a route about pay bands wants to know."""
        was_low = band.min_amount if band else 0.0
        was_high = band.max_amount if band else 0.0
        moves = []
        if low is not None and was_low:
            moves.append(abs(low - was_low) / was_low * 100.0)
        if high is not None and was_high:
            moves.append(abs(high - was_high) / was_high * 100.0)
        return {
            'bands_changed': {'value': 1, 'unit': ''},
            'max_move_pct': {'value': round(max(moves or [0.0]), 2),
                             'unit': '%'},
            'employees_affected': {'value': int(people or 0), 'unit': ''},
        }

    @api.model
    def set_band_range(self, band_id, minimum, middle, maximum):
        """Put a band's three numbers back — what Undo calls."""
        self._require_write()
        band = self.env['pb.pay.band'].sudo().browse(int(band_id)).exists()
        if not band:
            raise UserError(_("That band no longer exists."))
        held = self._bands_propose(
            'set_range',
            _("Put %s back where it was", band.display_name or ''),
            payload={'band_id': band.id, 'min': float(minimum),
                     'mid': float(middle), 'max': float(maximum)},
            snapshot={'min': band.min_amount, 'mid': band.mid_amount,
                      'max': band.max_amount},
            facts=self._band_facts(band, float(minimum), float(maximum)),
            target=band)
        if held is not None:
            return held
        band.write({'min_amount': float(minimum), 'mid_amount': float(middle),
                    'max_amount': float(maximum)})
        self.env['pb.pay.position'].sudo().recompute_all(self._companies().ids)
        return {'ok': True}

    # ======================================================== place a new hire
    @api.model
    def place_hire(self, job_id=None, level=0, experience_pct=50):
        """What to offer somebody joining, and why.

        The suggestion is the MIDDLE of the band nudged by up to a tenth
        either way for experience — which is what a compensation team does by
        hand — and it is shown beside what the people already doing the job
        are paid, because a band is intent and a payroll is fact.
        """
        if not self._can_read():
            raise AccessError(_("You cannot read the pay bands."))
        job = self.env['hr.job'].sudo().browse(int(job_id or 0)).exists()
        if not job:
            return {'ok': False,
                    'sentence': _("Pick a job to place somebody in.")}
        companies = self._companies()
        currency = job.company_id.currency_id or self.env.company.currency_id
        link = self.env['pb.pay.band.job'].sudo().search(
            [('job_id', '=', job.id)], limit=1)
        band = link.band_id if link else self.env['pb.pay.band']
        if level:
            same = self.env['pb.pay.band'].sudo().search([
                ('family_id', '=', band.family_id.id),
                ('level', '=', int(level)),
                ('country_code', '=', band.country_code),
            ], limit=1) if band else self.env['pb.pay.band']
            if same:
                band = same
        rows = self.env['pb.pay.position'].sudo().search_read(
            [('job_id', '=', job.id),
             ('company_id', 'in', companies.ids or [0])],
            ['employee_id', 'wage', 'position_pct'])
        wages = sorted(r['wage'] for r in rows if r['wage'])
        median = self._median(wages)
        answer = {
            'ok': True,
            'job': job.display_name,
            'job_id': job.id,
            'people': len(wages),
            'median': median,
            'median_label': self._money(median, currency) if wages else '',
            'lowest_label': self._money(wages[0], currency) if wages else '',
            'highest_label': self._money(wages[-1], currency) if wages else '',
            'market_label': _(
                '%(people)s already doing this job are paid from %(low)s to '
                '%(high)s, with %(mid)s in the middle.',
                people=self._people_phrase(len(wages)),
                low=self._money(wages[0], currency) if wages else '',
                high=self._money(wages[-1], currency) if wages else '',
                mid=self._money(median, currency) if wages else '')
            if wages else '',
            'experience_pct': int(experience_pct or 50),
            'levels': [],
            'band': None,
            'offer': 0.0,
            'offer_label': '',
            'sentence': '',
            'dots': [],
        }
        if not band:
            answer['sentence'] = _(
                "%(job)s is not in a band yet. Put it in one and the suggested "
                "offer appears here; until then the best guide is what "
                "%(people)s already doing it are paid.",
                job=job.display_name, people=self._people_phrase(len(wages)))
            return answer
        currency = band.currency_id or currency
        entry = self._band_dict(band, currency)
        entry = self._fill_band(entry, self._positions(companies), currency)
        span = (band.max_amount - band.min_amount) or 1.0
        # ±10% of the band's own width, from "new to this level" to "does this
        # already". The middle is 50.
        nudge = ((int(experience_pct or 50) - 50) / 50.0) * 0.10 * span
        offer = band.mid_amount + nudge
        offer = min(max(offer, band.min_amount), band.max_amount)
        answer.update({
            'band': entry,
            'offer': offer,
            'offer_label': self._money(offer, currency),
            'sentence': _(
                'Offer %(offer)s. That is inside %(band)s and %(compare)s '
                'what %(people)s already doing this job are paid.',
                offer=self._money(offer, currency), band=band.name,
                people=self._people_phrase(len(wages)),
                compare=(_('above') if wages and offer > median
                         else _('below') if wages and offer < median
                         else _('level with'))),
            'levels': [
                {'level': other.level, 'id': other.id, 'name': other.name}
                for other in self.env['pb.pay.band'].sudo().search([
                    ('family_id', '=', band.family_id.id),
                    ('country_code', '=', band.country_code)])],
        })
        return answer

    # ============================================== suggestions and the empty
    @api.model
    def _family_for(self, title):
        low = (' %s ' % (title or '')).lower()
        for name, words in FAMILY_WORDS:
            if any(word in low for word in words):
                return name
        return 'Other'

    @api.model
    def _level_for(self, title):
        low = (' %s ' % (title or '')).lower()
        for level, words in LEVEL_WORDS:
            if any(word in low for word in words):
                return level
        return DEFAULT_LEVEL

    @api.model
    def suggest_families(self, company_ids=None):
        """The job families this company's own job titles fall into."""
        if not self._can_read():
            return []
        companies = self._companies(company_ids)
        rows = self._tenure_rows(companies)
        names = {job.id: job.display_name
                 for job in self.env['hr.job'].sudo().browse(
                     list({r['job_id'] for r in rows if r['job_id']}))}
        grouped = defaultdict(lambda: {'jobs': [], 'people': 0})
        for row in rows:
            title = names.get(row['job_id'])
            if not title:
                continue
            bucket = grouped[self._family_for(title)]
            bucket['people'] += 1
            if title not in bucket['jobs']:
                bucket['jobs'].append(title)
        existing = {f.name for f in
                    self.env['pb.pay.family'].sudo().search([])}
        out = []
        for name, bucket in grouped.items():
            out.append({
                'name': name,
                'people': bucket['people'],
                'jobs': sorted(bucket['jobs'])[:12],
                'job_count': len(bucket['jobs']),
                'exists': name in existing,
            })
        out.sort(key=lambda f: -f['people'])
        return out

    @api.model
    def suggest_bands(self, company_ids=None):
        """A whole board of bands this company has not written yet.

        THE EMPTY STATE'S ANSWER. Every job title is put in a family and on a
        level from the words in it; the people on that family and level give
        the range — a tenth off the bottom quarter, the middle, a tenth over
        the top quarter — and the board draws exactly as a real one does, with
        every dot in its place, marked SUGGESTED. Nothing is written.
        """
        if not self._can_read():
            return {'lanes': [], 'families': [], 'people': 0}
        companies = self._companies(company_ids)
        rows = self._tenure_rows(companies)
        names = {job.id: job.display_name
                 for job in self.env['hr.job'].sudo().browse(
                     list({r['job_id'] for r in rows if r['job_id']}))}
        buckets = defaultdict(list)
        job_of = defaultdict(set)
        for row in rows:
            title = names.get(row['job_id'])
            if not title or not row['wage']:
                continue
            key = (self._family_for(title), self._level_for(title),
                   row['company_id'])
            buckets[key].append(row)
            job_of[key].add((row['job_id'], title))

        countries = dict(COUNTRIES)
        proposals = []
        for (family, level, company_id), people in buckets.items():
            company = companies.filtered(lambda c: c.id == company_id)[:1]
            currency = company.currency_id or self.env.company.currency_id
            country = (company.country_id.code or '') if company else ''
            if country not in countries:
                country = 'VN'
            wages = sorted(p['wage'] for p in people)
            quarter = wages[max(0, int(len(wages) * 0.25) - 1)]
            three_quarter = wages[min(len(wages) - 1, int(len(wages) * 0.75))]
            low = round(quarter * 0.9, 2)
            high = round(three_quarter * 1.1, 2)
            middle = round(self._median(wages), 2)
            middle = min(max(middle, low), high)
            proposals.append({
                'family': family, 'level': level, 'country_code': country,
                'country': countries.get(country, country),
                'currency_id': currency.id, 'currency_code': currency.name,
                'company_id': company_id,
                'company': company.display_name if company else '',
                'min': low, 'mid': middle, 'max': high,
                'min_label': self._money(low, currency),
                'mid_label': self._money(middle, currency),
                'max_label': self._money(high, currency),
                'min_short': self._short(low, currency),
                'max_short': self._short(high, currency),
                'jobs': [{'id': job_id, 'name': title}
                         for job_id, title in sorted(job_of[(
                             family, level, company_id)],
                             key=lambda pair: pair[1])],
                'people': len(wages),
                'name': _('%(family)s · level %(level)s · %(country)s',
                          family=family, level=level,
                          country=countries.get(country, country)),
                'suggested': True,
                'id': 0,
                'note': '',
                'since_label': '',
                'date_from': fields.Date.to_string(
                    fields.Date.context_today(self)),
                'date_to': '',
                'family_id': 0,
                'level_label': str(level),
            })

        # The dots, placed on the proposed ranges rather than on saved ones.
        lanes = defaultdict(list)
        for proposal in proposals:
            span = (proposal['max'] - proposal['min']) or 1.0
            key = (proposal['family'], proposal['level'],
                   proposal['company_id'])
            currency = self.env['res.currency'].browse(
                proposal['currency_id'])
            dots, wages, below, above = [], [], 0, 0
            people = sorted(buckets[key], key=lambda p: p['wage'])
            small = len(people) <= DOT_LIMIT
            for person in people:
                state = 'in'
                if person['wage'] < proposal['min']:
                    state, below = 'below', below + 1
                elif person['wage'] > proposal['max']:
                    state, above = 'above', above + 1
                wages.append(int(round(person['wage'] or 0)))
                if small:
                    dots.append({
                        'id': person['employee_id'], 'name': person['name'],
                        'job': names.get(person['job_id'], ''),
                        'wage': person['wage'],
                        'wage_label': self._money(person['wage'], currency),
                        'pct': round(((person['wage'] - proposal['min'])
                                      / span) * 100.0, 1),
                        'state': state,
                    })
            median = self._median([p['wage'] for p in buckets[key]])
            proposal.update({
                'dots': dots, 'wages': wages, 'below': below, 'above': above,
                'symbol': currency.symbol if currency else '',
                'symbol_before': bool(currency
                                      and currency.position == 'before'),
                'in_band': proposal['people'] - below - above,
                'median': median,
                'median_label': self._money(median, currency),
                'median_note': _('median %(amount)s',
                                 amount=self._short(median, currency))
                if wages else '',
                # A proposal has no row to look up, so it carries everything
                # the server needs to find exactly these people again — the
                # bucket it came from, and the edges it is drawn with.
                'people_scope': {
                    'band_id': 0,
                    'family': proposal['family'],
                    'level': proposal['level'],
                    'company_id': proposal['company_id'],
                    'country': proposal['country_code'],
                    'min': proposal['min'],
                    'max': proposal['max'],
                },
            })
            # A suggested band draws EXACTLY like a saved one, sentences and
            # all: an empty state that looks half-built is a page nobody
            # trusts enough to press the button on.
            proposal.update(self._band_labels(
                proposal, self.env['res.currency'].browse(
                    proposal['currency_id'])))
            lanes[proposal['currency_code']].append(proposal)

        out = []
        for code, members in lanes.items():
            currency = self.env['res.currency'].browse(
                members[0]['currency_id'])
            members.sort(key=lambda b: (b['family'], b['level']))
            out.append({
                'currency_id': currency.id,
                'currency_code': code,
                'symbol': currency.symbol,
                'title': _('%(code)s · %(count)s bands',
                           code=code, count=len(members)),
                # Measured on EVERY wage, not on the dots: a band over the dot
                # limit sends no dots at all, and an axis drawn from a subset
                # is an axis that moves when the picture changes shape.
                'axis': self._lane_axis(
                    members,
                    [{'wage': wage} for band in members
                     for wage in band['wages']], currency),
                'families': self._family_axes(
                    members,
                    lambda group: [wage for band in group
                                   for wage in band['wages']],
                    currency),
                'bands': members,
            })
        out.sort(key=lambda lane: -sum(b['people'] for b in lane['bands']))
        return {
            'lanes': out,
            'families': sorted({p['family'] for p in proposals}),
            'people': sum(p['people'] for p in proposals),
            'bands': len(proposals),
        }

    @api.model
    def accept_suggestion(self, proposals):
        """Write the suggested bands, families and job links for real."""
        self._require_write()
        proposals = list(proposals or [])[:MAX_IMPORT]
        held = self._bands_propose(
            'accept_suggestion',
            _("Accept %s suggested band(s)", len(proposals)),
            payload={'proposals': proposals},
            facts={'bands_changed': {'value': len(proposals), 'unit': ''},
                   'max_move_pct': {'value': 0.0, 'unit': '%'},
                   'employees_affected': {'value': 0, 'unit': ''}})
        if held is not None:
            return dict(held, made={'families': 0, 'bands': 0, 'jobs': 0,
                                    'skipped': []})
        Family = self.env['pb.pay.family'].sudo()
        Band = self.env['pb.pay.band'].sudo()
        Link = self.env['pb.pay.band.job'].sudo()
        made = {'families': 0, 'bands': 0, 'jobs': 0, 'skipped': []}
        today = fields.Date.context_today(self)
        for proposal in proposals:
            name = (proposal.get('family') or '').strip()
            if not name:
                continue
            family = Family.search([('name', '=', name)], limit=1)
            if not family:
                family = Family.create({'name': name})
                made['families'] += 1
            level = int(proposal.get('level') or 1)
            country = proposal.get('country_code') or 'VN'
            band = Band.search([('family_id', '=', family.id),
                                ('level', '=', level),
                                ('country_code', '=', country)], limit=1)
            if band:
                made['skipped'].append(band.name)
            else:
                band = Band.create({
                    'family_id': family.id, 'level': level,
                    'country_code': country,
                    'currency_id': int(proposal.get('currency_id') or 0)
                    or self.env.company.currency_id.id,
                    'min_amount': float(proposal.get('min') or 0),
                    'mid_amount': float(proposal.get('mid') or 0),
                    'max_amount': float(proposal.get('max') or 0),
                    'date_from': today,
                    'note': 'Suggested from what this company pays today.',
                })
                made['bands'] += 1
            for job in proposal.get('jobs') or []:
                job_id = int(job.get('id') or 0)
                if not job_id:
                    continue
                if Link.search([('job_id', '=', job_id)], limit=1):
                    continue
                try:
                    Link.create({'band_id': band.id, 'job_id': job_id})
                    made['jobs'] += 1
                except Exception as error:      # noqa: BLE001
                    _logger.info('pb_pay: job %s not linked: %s',
                                 job_id, error)
        self.env['pb.pay.position'].sudo().recompute_all(
            self._companies().ids)
        return made

    # ================================================= import and export
    @api.model
    def export_bands(self):
        """Every band as a spreadsheet, in the columns the import reads."""
        if not self._can_read():
            raise AccessError(_("You cannot read the pay bands."))
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['Job family', 'Level', 'Country', 'Currency',
                         'Lowest', 'Middle', 'Highest', 'In force from',
                         'In force until', 'Jobs'])
        for band in self.env['pb.pay.band'].sudo().search([]):
            writer.writerow([
                band.family_id.name, band.level, band.country_code,
                band.currency_id.name, band.min_amount, band.mid_amount,
                band.max_amount, fields.Date.to_string(band.date_from),
                fields.Date.to_string(band.date_to) if band.date_to else '',
                '; '.join(band.job_ids.mapped('job_id.display_name')),
            ])
        raw = buffer.getvalue().encode('utf-8')
        return {
            'name': 'pay-bands.csv',
            'content': base64.b64encode(raw).decode('ascii'),
            'rows': len(self.env['pb.pay.band'].sudo().search([])),
        }

    @api.model
    def import_bands(self, content, dry_run=True):
        """Read a spreadsheet. Every row is checked before any row is written.

        A file with one bad line in it is the normal case, not the exception,
        so the preview lists EVERY row with what is wrong with it and the good
        ones are imported on their own. A refusal that throws the file away
        is a dead end (§8).
        """
        if not self._can_read():
            raise AccessError(_("You cannot read the pay bands."))
        try:
            raw = base64.b64decode(content or '')
            text = raw.decode('utf-8-sig')
        except Exception:       # noqa: BLE001
            return {'ok': False, 'rows': [], 'good': 0, 'bad': 0,
                    'sentence': _(
                        "That file could not be read. Save it as a CSV and "
                        "try again.")}
        reader = csv.reader(io.StringIO(text))
        try:
            header = next(reader)
        except StopIteration:
            return {'ok': False, 'rows': [], 'good': 0, 'bad': 0,
                    'sentence': _("That file is empty.")}
        countries = dict(COUNTRIES)
        rows, good = [], []
        for number, raw_row in enumerate(reader, start=2):
            if number - 1 > MAX_IMPORT:
                break
            if not any((cell or '').strip() for cell in raw_row):
                continue
            cells = (list(raw_row) + [''] * 9)[:9]
            family, level, country, code, low, mid, high, since, until = cells
            problems = []
            if not (family or '').strip():
                problems.append(_("no job family"))
            try:
                level_value = int(float(level or 0))
            except ValueError:
                level_value = 0
            if not 1 <= level_value <= MAX_LEVEL:
                problems.append(_("the level has to be a number from 1 to "
                                  "%(top)s", top=MAX_LEVEL))
            country = (country or '').strip().upper()
            if country not in countries:
                problems.append(_("%(code)s is not a country this product "
                                  "runs payroll for", code=country or '—'))
            numbers = {}
            for key, cell in (('min', low), ('mid', mid), ('max', high)):
                try:
                    numbers[key] = float(str(cell).replace(',', '').strip()
                                         or 0)
                except ValueError:
                    numbers[key] = 0.0
                    problems.append(_("%(cell)s is not an amount", cell=cell))
            if not problems and not (numbers['min'] <= numbers['mid']
                                     <= numbers['max']):
                problems.append(_("lowest, middle and highest are not in "
                                  "that order"))
            currency = self.env['res.currency'].with_context(
                active_test=False).search(
                    [('name', '=', (code or '').strip().upper()
                      or COUNTRY_CURRENCY.get(country, ''))], limit=1)
            if not currency:
                problems.append(_("%(code)s is not a currency on file",
                                  code=code or '—'))
            entry = {
                'line': number, 'family': family, 'level': level_value,
                'country': country,
                'country_label': countries.get(country, country),
                'currency': currency.name if currency else (code or ''),
                'currency_id': currency.id if currency else 0,
                'min': numbers['min'], 'mid': numbers['mid'],
                'max': numbers['max'],
                'min_label': self._money(numbers['min'], currency),
                'mid_label': self._money(numbers['mid'], currency),
                'max_label': self._money(numbers['max'], currency),
                'date_from': (since or '').strip(),
                'date_to': (until or '').strip(),
                'problem': ' · '.join(problems),
            }
            rows.append(entry)
            if not problems:
                good.append(entry)
        answer = {
            'ok': True, 'rows': rows, 'good': len(good),
            'bad': len(rows) - len(good), 'header': header, 'made': 0,
            'sentence': _(
                '%(good)s row(s) ready, %(bad)s to fix.',
                good=len(good), bad=len(rows) - len(good)),
        }
        if dry_run or not good:
            return answer
        self._require_write()
        held = self._bands_propose(
            'import',
            _("Import %s band(s) from a spreadsheet", len(good)),
            payload={'rows': good},
            facts={'bands_changed': {'value': len(good), 'unit': ''},
                   'max_move_pct': {'value': 0.0, 'unit': '%'},
                   'employees_affected': {'value': 0, 'unit': ''}})
        if held is not None:
            answer.update(held)
            return answer
        answer['made'] = self._write_import(good)
        self.env['pb.pay.position'].sudo().recompute_all(
            self._companies().ids)
        answer['sentence'] = _('%(made)s band(s) saved.',
                               made=answer['made'])
        return answer

    @api.model
    def _write_import(self, rows):
        Family = self.env['pb.pay.family'].sudo()
        Band = self.env['pb.pay.band'].sudo()
        today = fields.Date.context_today(self)
        made = 0
        for row in rows:
            name = row['family'].strip()
            family = Family.search([('name', '=', name)], limit=1) \
                or Family.create({'name': name})
            existing = Band.search([
                ('family_id', '=', family.id), ('level', '=', row['level']),
                ('country_code', '=', row['country'])], limit=1)
            values = {
                'min_amount': row['min'], 'mid_amount': row['mid'],
                'max_amount': row['max'],
                'currency_id': row['currency_id']
                or self.env.company.currency_id.id,
            }
            if existing:
                existing.write(values)
            else:
                values.update({
                    'family_id': family.id, 'level': row['level'],
                    'country_code': row['country'],
                    'date_from': row['date_from'] or today,
                    'date_to': row['date_to'] or False,
                    'note': 'Imported from a spreadsheet.',
                })
                Band.create(values)
            made += 1
        return made

    # =============================================================== editing
    @api.model
    def save_band(self, values):
        self._require_write()
        values = dict(values or {})
        band_id = int(values.pop('id', 0) or 0)
        clean = {}
        for key in ('family_id', 'level', 'country_code', 'currency_id',
                    'min_amount', 'mid_amount', 'max_amount', 'date_from',
                    'date_to', 'note'):
            if key in values:
                clean[key] = values[key]
        Band = self.env['pb.pay.band'].sudo()
        existing = Band.browse(band_id).exists() if band_id else Band
        if band_id and not existing:
            raise UserError(_("That band no longer exists."))
        held = self._bands_propose(
            'save_band',
            _("Save the band %s", existing.display_name or clean.get('level')
              or _('new band')),
            payload={'values': dict(clean, id=band_id)},
            snapshot=({'min': existing.min_amount, 'mid': existing.mid_amount,
                       'max': existing.max_amount} if existing else {}),
            facts=self._band_facts(existing,
                                   clean.get('min_amount'),
                                   clean.get('max_amount')),
            target=existing or None)
        if held is not None:
            return held
        if existing:
            band = existing
            band.write(clean)
        else:
            band = Band.create(clean)
        self.env['pb.pay.position'].sudo().recompute_all(self._companies().ids)
        return {'ok': True, 'id': band.id, 'name': band.name}

    @api.model
    def link_job(self, band_id, job_id):
        self._require_write()
        band = self.env['pb.pay.band'].sudo().browse(int(band_id)).exists()
        job = self.env['hr.job'].sudo().browse(int(job_id)).exists()
        held = self._bands_propose(
            'link_job',
            _("Pay %(job)s from %(band)s", job=job.display_name or '',
              band=band.display_name or ''),
            payload={'band_id': int(band_id), 'job_id': int(job_id)},
            facts=self._band_facts(band),
            target=band or None)
        if held is not None:
            return held
        link = self.env['pb.pay.band.job'].sudo().create({
            'band_id': int(band_id), 'job_id': int(job_id)})
        self.env['pb.pay.position'].sudo().recompute_all(self._companies().ids)
        return {'ok': True, 'id': link.id}

    @api.model
    def unlink_job(self, link_id):
        self._require_write()
        link = self.env['pb.pay.band.job'].sudo().browse(int(link_id)).exists()
        held = self._bands_propose(
            'unlink_job',
            _("Take %s out of its band", link.display_name or ''),
            payload={'link_id': int(link_id)},
            facts=self._band_facts(link.band_id if link else None),
            target=link or None)
        if held is not None:
            return held
        self.env['pb.pay.band.job'].sudo().browse(int(link_id)).unlink()
        self.env['pb.pay.position'].sudo().recompute_all(self._companies().ids)
        return {'ok': True}

    @api.model
    def recompute_positions(self, company_ids=None):
        if not self._can_read():
            raise AccessError(_("You cannot read the pay bands."))
        started = time.time()
        made = self.env['pb.pay.position'].sudo().recompute_all(
            self._companies(company_ids).ids)
        return {'ok': True, 'rows': made,
                'ms': int((time.time() - started) * 1000)}

    @api.model
    def jobs_without_a_band(self, company_ids=None):
        """For the "put this job in a band" picker."""
        if not self._can_read():
            return []
        companies = self._companies(company_ids)
        taken = set(self.env['pb.pay.band.job'].sudo().search(
            []).mapped('job_id').ids)
        rows = self.env['pb.pay.position'].sudo()._read_group(
            [('company_id', 'in', companies.ids or [0]),
             ('job_id', '!=', False)], ['job_id'], ['__count'])
        out = [{'id': job.id, 'name': job.display_name, 'people': count}
               for job, count in rows if job and job.id not in taken]
        out.sort(key=lambda j: -j['people'])
        return out[:MAX_ROWS * 4]
