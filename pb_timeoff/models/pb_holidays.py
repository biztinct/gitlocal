# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.holidays` — the public-holiday calendar, for everybody.

WHAT WAS TRUE BEFORE. A public holiday is a `resource.calendar.leaves` row
with no resource on it, buried three clicks inside the working-hours record of
one company's calendar. Nobody outside the HR team ever saw one, and on this
database there was exactly ONE row, on the company nobody works in — so a
Vietnamese employee asking "is the 30th of April a day off?" had nowhere at all
to look.

WHAT IS TRUE NOW. One screen with every company's year side by side, and the
same list on the employee's own page. **Everybody may read it**, which is the
whole requirement: the business runs in several countries and somebody in
Hanoi planning a call with Singapore needs Singapore's calendar, not just
their own.

TWO RULES THIS FILE OBEYS.

1. **The read is sudo over PUBLIC rows only.** `resource_id` empty is the
   whole of the filter and it is written into every search here, never left to
   a caller: a row WITH a resource is one person's own time off and reading it
   is not what this screen is for.
2. **Writing is an officer's.** `_require_officer` is `pb.timeoff`'s own gate,
   reused rather than restated so the two surfaces can never disagree about
   who the HR team is.
"""

import logging
from datetime import date, datetime, time

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: How many company columns the board draws. A business with more than this
#: many operating companies wants a filter, not a wider screen — and an
#: unbounded loop over companies is the kind of thing that is fine on a demo
#: and slow on a group.
_MAX_COMPANIES = 8

#: How far either side of this year the year strip reaches.
_YEAR_SPAN = 2


class PbHolidays(models.AbstractModel):
    _name = 'pb.holidays'
    _description = 'Public holidays'

    # ------------------------------------------------------------- plumbing
    @api.model
    def _safe(self, fn, default=None):
        """One try/except per independent probe (ledger: never a shared one),
        logged at WARNING with the traceback — a swallowed failure logged at
        DEBUG is invisible on a live server (R92)."""
        try:
            return fn()
        except Exception:                                   # noqa: BLE001
            _logger.warning('pb_timeoff: a holidays probe failed',
                            exc_info=True)
            return default

    @api.model
    def _today(self):
        """The SERVER's today, never `context_today` (R36/R154). A calendar
        everybody reads must say the same date to everybody reading it."""
        return fields.Date.today()

    @api.model
    def _tz(self, calendar, company):
        name = (calendar.tz if calendar else None) \
            or (company.partner_id.tz if company else None) or 'UTC'
        try:
            return pytz.timezone(name)
        except Exception:                                   # noqa: BLE001
            return pytz.UTC

    @api.model
    def _local_date(self, dt_utc, tzinfo):
        if not dt_utc:
            return None
        return pytz.UTC.localize(dt_utc).astimezone(tzinfo).date()

    @api.model
    def _bounds(self, day_from, day_to, tzinfo):
        """A whole day, in the calendar's own timezone, stored as UTC."""
        start = tzinfo.localize(datetime.combine(day_from, time.min))
        end = tzinfo.localize(datetime.combine(day_to, time.max))
        return (start.astimezone(pytz.UTC).replace(tzinfo=None),
                end.astimezone(pytz.UTC).replace(tzinfo=None))

    @api.model
    def _companies(self):
        """Every company, the reader's own first.

        NOT `env.companies`. The requirement is the one thing that makes this
        screen worth building: all countries visible to all. Scoping it to the
        session's allowed companies would give a Vietnamese employee exactly
        the calendar they already knew about.
        """
        Company = self.env['res.company'].sudo()
        mine = self.env.company
        rest = Company.search([('id', '!=', mine.id)], order='id')
        return (mine + rest)[:_MAX_COMPANIES]

    @api.model
    def _can_edit(self):
        try:
            self.env['pb.timeoff']._require_officer()
            return True
        except Exception:                                   # noqa: BLE001
            return False

    # ---------------------------------------------------------------- read
    @api.model
    def year(self, year=False):
        """Every company's public holidays for one year."""
        today = self._today()
        try:
            year = int(year) if year else today.year
        except (TypeError, ValueError):
            year = today.year
        first = date(year, 1, 1)
        last = date(year, 12, 31)

        columns = []
        next_overall = None
        for company in self._companies():
            column = self._safe(
                lambda c=company: self._column(c, first, last, today),
                default=None)
            if not column:
                continue
            columns.append(column)
            nxt = column.get('next')
            if nxt and (next_overall is None
                        or nxt['date'] < next_overall['date']):
                next_overall = dict(nxt, company=column['name'])

        return {
            'year': year,
            'today': today.isoformat(),
            'years': [today.year + n
                      for n in range(-_YEAR_SPAN, _YEAR_SPAN + 1)],
            'companies': columns,
            'can_edit': self._can_edit(),
            'next': next_overall,
        }

    @api.model
    def _column(self, company, first, last, today):
        calendar = company.sudo().resource_calendar_id
        tzinfo = self._tz(calendar, company)
        from_utc, to_utc = self._bounds(first, last, tzinfo)
        rows = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False),
            ('company_id', '=', company.id),
            ('time_type', '=', 'leave'),
            ('date_from', '<=', to_utc),
            ('date_to', '>=', from_utc),
        ], order='date_from')

        out = []
        nxt = None
        for row in rows:
            day_from = self._local_date(row.date_from, tzinfo)
            day_to = self._local_date(row.date_to, tzinfo) or day_from
            if not day_from:
                continue
            days = (day_to - day_from).days + 1
            entry = {
                'id': row.id,
                'date': day_from.isoformat(),
                'date_to': day_to.isoformat(),
                'name': row.name or _('Public holiday'),
                'weekday': day_from.strftime('%a'),
                'month': day_from.strftime('%b'),
                'day': day_from.day,
                'days': days,
                'is_past': day_to < today,
                'is_today': day_from <= today <= day_to,
            }
            out.append(entry)
            if nxt is None and day_to >= today:
                nxt = {'date': entry['date'], 'name': entry['name'],
                       'days_away': (day_from - today).days}

        country = company.sudo().country_id
        return {
            'id': company.id,
            'name': company.name,
            'country': country.name if country else '',
            'country_code': (country.code or '') if country else '',
            # A company with no working-hours record cannot be given a holiday
            # at all, and saying so on the empty column is the difference
            # between a screen that teaches and a button that fails.
            'has_calendar': bool(calendar),
            'calendar': calendar.name if calendar else '',
            'rows': out,
            'count': len(out),
            'next': nxt,
        }

    # --------------------------------------------------------------- write
    @api.model
    def _company_for_write(self, company_id):
        self.env['pb.timeoff']._require_officer()
        company = self.env['res.company'].sudo().browse(
            int(company_id or 0)).exists()
        if not company:
            raise UserError(_("Pick a company first."))
        calendar = company.resource_calendar_id
        if not calendar:
            raise UserError(_(
                "%s has no working hours set up yet, so there is nowhere to "
                "put a holiday. Set its working hours first and the calendar "
                "will appear here.", company.name))
        return company, calendar

    @api.model
    def _parse_day(self, raw):
        value = None
        try:
            value = fields.Date.to_date(raw) if raw else None
        except (ValueError, TypeError):
            value = None
        if not value:
            raise UserError(_(
                "\"%(given)s\" is not a date this reads. Write it as "
                "%(shape)s — for example %(example)s.",
                given=raw or '', shape='YYYY-MM-DD', example='2026-04-30'))
        return value

    @api.model
    def _create_row(self, company, calendar, name, day_from, day_to):
        """The write itself. `False` when that day is already on the calendar
        under that name — which is a SKIP and not a failure, so pasting a year
        in twice cannot double it."""
        tzinfo = self._tz(calendar, company)
        from_utc, to_utc = self._bounds(day_from, day_to, tzinfo)
        clash = self.env['resource.calendar.leaves'].sudo().search_count([
            ('resource_id', '=', False),
            ('company_id', '=', company.id),
            ('name', '=', name),
            ('date_from', '<=', to_utc), ('date_to', '>=', from_utc),
        ])
        if clash:
            return False
        row = self.env['resource.calendar.leaves'].sudo().create({
            'name': name,
            'calendar_id': calendar.id,
            'date_from': from_utc,
            'date_to': to_utc,
            'time_type': 'leave',
        })
        # THE STOCK CREATE CONVERTS THE TIMES A SECOND TIME, and only when the
        # person writing the holiday is in a different timezone from the
        # calendar. `hr_holidays`' `_prepare_public_holidays_values` reads a
        # public-holiday create as "these datetimes are in the ACTING USER's
        # timezone" and shifts them into the calendar's — which is right for
        # somebody typing into the native form and wrong for a caller that has
        # already done the conversion properly. Live symptom: a three-day
        # holiday entered from Vietnam onto a Brussels calendar was stored ten
        # hours out and read back as FOUR days, with nothing on any screen.
        #
        # `write` does no such conversion, so the two values are put back
        # exactly as they were worked out. One extra UPDATE, and the row means
        # the same thing whoever entered it.
        if row.date_from != from_utc or row.date_to != to_utc:
            row.write({'date_from': from_utc, 'date_to': to_utc})
        self._register_demo(row, _('Public holidays'))
        return row

    @api.model
    def add(self, company_id, name, date_from, date_to=False):
        """One holiday, on one company's working-hours calendar."""
        company, calendar = self._company_for_write(company_id)
        name = (name or '').strip()
        if not name:
            raise UserError(_("Give the day a name people will recognise."))
        day_from = self._parse_day(date_from)
        day_to = self._parse_day(date_to) if date_to else day_from
        if day_to < day_from:
            raise UserError(_("The last day cannot be before the first day."))
        row = self._create_row(company, calendar, name, day_from, day_to)
        if not row:
            raise UserError(_(
                "%(name)s is already on %(company)s's calendar for those "
                "days.", name=name, company=company.name))
        return {'ok': True, 'id': row.id}

    @api.model
    def add_many(self, company_id, lines_text):
        """A whole year pasted in, one holiday per line.

        A LINE THAT IS WRONG IS NAMED AND NOTHING IS WRITTEN. Half a year on
        the calendar and half a year in an error message is the worst of both:
        the reader cannot tell which half landed, and pasting it again would
        double the half that did.
        """
        company, calendar = self._company_for_write(company_id)
        parsed = []
        for number, raw in enumerate((lines_text or '').splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            bits = [b.strip() for b in line.split('|')]
            if len(bits) < 2 or not bits[0] or not bits[1]:
                raise UserError(_(
                    "Line %(n)s does not read as a holiday: \"%(line)s\". "
                    "Each line is a name, a vertical bar and a date — "
                    "Tết | 2026-02-17 — with a second date after another bar "
                    "when it runs over several days.",
                    n=number, line=line[:80]))
            try:
                day_from = self._parse_day(bits[1])
                day_to = self._parse_day(bits[2]) if len(bits) > 2 \
                    and bits[2] else day_from
            except UserError as err:
                raise UserError(_(
                    "Line %(n)s: %(why)s",
                    n=number, why=(err.args and err.args[0]) or '')) from err
            if day_to < day_from:
                raise UserError(_(
                    "Line %(n)s ends before it starts.", n=number))
            parsed.append((bits[0], day_from, day_to))
        if not parsed:
            raise UserError(_("There is nothing in the box to add."))

        added, already = 0, []
        for name, day_from, day_to in parsed:
            if self._create_row(company, calendar, name, day_from, day_to):
                added += 1
            else:
                already.append(name)
        return {'ok': True, 'added': added, 'already': already}

    @api.model
    def remove(self, row_id):
        """Take one holiday off again — a row added by mistake with no way
        back is a dead end."""
        self.env['pb.timeoff']._require_officer()
        row = self.env['resource.calendar.leaves'].sudo().browse(
            int(row_id or 0)).exists()
        if not row or row.resource_id:
            # A row with a resource is one person's own time off. This screen
            # has never shown one and must never delete one.
            raise UserError(_("That day is not on the public calendar."))
        row.unlink()
        return {'ok': True}

    # ---------------------------------------------------------------- demo
    @api.model
    def _register_demo(self, records, label):
        """Demo rows go on the register the owner's Remove button reads
        (ledger rule 9). The guard keeps `pb_demo_seed` optional on a tenant
        that has not got it."""
        if not (records and (records[0].name or '').upper().startswith('DEMO')):
            return
        seed = self.env.get('pb.demo.seed')
        if seed is None:
            return
        try:
            seed.register(records, label)
        except Exception:                                   # noqa: BLE001
            _logger.warning('pb_timeoff: a demo holiday was not registered',
                            exc_info=True)

    # ------------------------------------------------------- the own page
    @api.model
    def my_year(self, year=False):
        """The same answer, for `/my/holidays`. One reader, one set of facts —
        the page a person walks in a browser is the one the tests walk."""
        data = self.year(year)
        data['can_edit'] = False
        return data

    @api.model
    def next_one(self):
        """The next public holiday on the reader's OWN company, for the home
        card. `False` when the year has none left, which the card says."""
        today = self._today()
        column = self._safe(
            lambda: self._column(self.env.company,
                                 today, date(today.year + 1, 12, 31), today),
            default=None)
        nxt = (column or {}).get('next')
        if not nxt:
            return False
        return nxt


def counted(number, one, many):
    """"1 day" and "2 days", never "1 day(s)" (R46/R219)."""
    return '%s %s' % (number, one if number == 1 else many)
