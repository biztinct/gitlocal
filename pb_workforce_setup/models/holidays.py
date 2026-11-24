# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Step 5 "Holidays" (WFSETUP P4, handover §2.1) — facade methods.

Storage is unchanged: a day off is a `resource.calendar.leaves` row with no
resource on the company's working calendar, made ONLY through
`pb.holidays._create_row` (it creates a century out and writes the real UTC
bounds — facts F, ledger WS16) and read through `pb.holidays._column` (the
holidays board's own reader, with the kind from `pb_timeoff`'s journey).

Rights: `pb.holidays.add / add_many / remove` check `env.user` against the
time-off officer groups (`pb.timeoff._require_officer`) — `sudo()` does not
change `env.user`, so an attendance manager would still be refused there.
The studio therefore runs ITS OWN gate (attendance manager) plus an explicit
"this company only" check, then calls the private writers `_create_row` and
`_forget_demo` with sudo. This is the deliberate, owner-accepted widening of
§2.1, limited to this facade; an attendance officer is still refused.

Kinds: `pb.holidays.add` stores the field default `public`. A company day
off is written `pb_holiday_kind = 'company'` straight after `_create_row`, as
`pb_timeoff`'s own import publish does (`holiday_journey.py` publish_import).

Every add / remove re-marks the future roster (`remark_days`, P3) and says
what changed.
"""

import json
from datetime import date, timedelta
from pathlib import Path

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

KINDS = ('public', 'company', 'collective')
_HERE = Path(__file__).resolve().parent.parent
_REFERENCE_COUNTRIES = {'ID': 'Indonesia', 'VN': 'Vietnam', 'SG': 'Singapore', 'IN': 'India'}
_YEAR_SPAN = 2


class WorkforceSetupHolidays(models.AbstractModel):
    _inherit = 'pb.workforce.setup'

    # ============================================================ suggestions
    @api.model
    def _suggestion_rows(self, code, year):
        """[{date, name}] suggested for this country and year, or []. Our own
        list first (`data/holiday_suggestions.json`); for 2026 the reference
        rows `pb_timeoff` already ships (rows marked as a conflict left out)."""
        code = (code or '').upper()
        try:
            ours = json.loads((_HERE / 'data' / 'holiday_suggestions.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            ours = {}
        rows = ((ours.get(code) or {}).get(str(year))) or []
        if not rows and code in _REFERENCE_COUNTRIES:
            try:
                from odoo.modules.module import get_module_path
                path = Path(get_module_path('pb_timeoff')) / 'data' / 'holiday_reference.json'
                reference = json.loads(path.read_text(encoding='utf-8'))
            except Exception:                                   # noqa: BLE001 — a missing file is "no list"
                reference = []
            rows = [{'date': r['date'], 'name': r['name']} for r in reference
                    if r.get('country') == _REFERENCE_COUNTRIES[code] and not r.get('conflict')
                    and str(r.get('date', '')).startswith('%s-' % year)]
        out = []
        for r in rows:
            try:
                day = fields.Date.to_date(r['date'])
            except (KeyError, ValueError, TypeError):
                continue
            if day and day.year == year and (r.get('name') or '').strip():
                out.append({'date': day.isoformat(), 'name': self._suggestion_name(r['name'].strip())})
        return sorted(out, key=lambda r: r['date'])

    @api.model
    def _suggestion_name(self, name):
        """A suggested holiday's name in the user's language (P5a): the names
        of our own list and of the `pb_timeoff` reference rows for the
        countries we suggest. An unknown name is shown as it is."""
        names = {
            'New Year': _("New Year"),
            'Tet holiday': _("Tet holiday"),
            'Tet (Lunar New Year)': _("Tet (Lunar New Year)"),
            'Hung Kings Day': _("Hung Kings Day"),
            'Reunification Day': _("Reunification Day"),
            'Labour Day': _("Labour Day"),
            'National Day': _("National Day"),
            '2026 New Year': _("2026 New Year"),
            'New Year’s Holiday': _("New Year’s Holiday"),
            'Lunar New Year (Tet) Holidays': _("Lunar New Year (Tet) Holidays"),
            'Hung Kings Commemoration Day': _("Hung Kings Commemoration Day"),
            'Reunification Day – International Labor Day': _("Reunification Day – International Labor Day"),
            'International Labor Day': _("International Labor Day"),
            'Independence day': _("Independence day"),
            'Vietnam Cultural Day': _("Vietnam Cultural Day"),
            'Chinese New Year 2576 Kongzili': _("Chinese New Year 2576 Kongzili"),
            'Isra Mi‘raj of the Prophet Muhammad SAW.': _("Isra Mi‘raj of the Prophet Muhammad SAW."),
            'Hari Suci Nyepi': _("Hari Suci Nyepi"),
            'Eid al-Fitr 1447 Hijri': _("Eid al-Fitr 1447 Hijri"),
            'Good Friday': _("Good Friday"),
            'Ascension Day of Jesus Christ': _("Ascension Day of Jesus Christ"),
            'Eid al-Adha 1446 Hijri': _("Eid al-Adha 1446 Hijri"),
            'Pancasila Day': _("Pancasila Day"),
            'Islamic New Year 1 Muharram 1447 Hijri': _("Islamic New Year 1 Muharram 1447 Hijri"),
            'Independence Day of Indonesia': _("Independence Day of Indonesia"),
            'Mawlid of Prophet Muhammad SAW.': _("Mawlid of Prophet Muhammad SAW."),
            'Christmas Day': _("Christmas Day"),
            'Christmas': _("Christmas"),
            'Christmas Boxing Day': _("Christmas Boxing Day"),
        }
        return names.get(name, name)

    @api.model
    def _suggestion_note(self, code):
        if (code or '').upper() == 'VN':
            return _("Tet and Hung Kings follow the lunar calendar, and the extra National Day holiday is announced each year. Check the government notice before you confirm.")
        return _("Some of these days move from year to year or are announced by the government. Check the government notice before you confirm.")

    # ============================================================ reading
    @api.model
    def _holiday_year(self, year):
        today = self._today()
        try:
            year = int(year) if year else today.year
        except (TypeError, ValueError):
            year = today.year
        return year if 2000 <= year <= 2200 else today.year

    @api.model
    def _days_off(self, company, year):
        """This company's days off touching `year`, as the holidays board reads
        them (local days in the calendar's zone, kind included)."""
        column = self.env['pb.holidays']._column(
            company, date(year, 1, 1), date(year, 12, 31), self._today()) or {}
        days = []
        for row in column.get('rows', []):
            kind = row.get('kind') or 'public'
            days.append({
                'id': row['id'],
                'date': row['date'],
                'date_to': row.get('date_to') or row['date'],
                'name': row.get('name') or '',
                'kind': kind if kind in KINDS else 'public',
                'days': row.get('days') or 1,
            })
        return days

    @api.model
    def _off_dates(self, days, year=None):
        """The set of dates covered by `days` (ranges expanded), in `year`."""
        out = set()
        for d in days:
            cur = fields.Date.to_date(d['date'])
            last = fields.Date.to_date(d['date_to']) or cur
            while cur <= last:
                if year is None or cur.year == year:
                    out.add(cur)
                cur += timedelta(days=1)
        return out

    @api.model
    def _main_week(self):
        """The company's most-used working week today (most people on it)."""
        members = self._covering(self._today())
        if not members:
            return self.env['pb.shift.pattern']
        counts = {}
        for m in members:
            counts[m.pattern_id] = counts.get(m.pattern_id, 0) + 1
        return max(counts, key=lambda p: (counts[p], -p.id))

    @api.model
    def _rest_weekdays(self):
        """Weekdays (0 = Monday) that are off in EVERY week of the company's
        most-used working week; without one, weekdays its working calendar
        has no hours on. Shading only."""
        pattern = self._main_week()
        if pattern:
            slots = pattern._pb_slot_map()
            cycle = max(1, pattern.cycle_days or 1)
            start = self._monday()
            worked = set()
            for i in range(cycle * 7):
                day = start + timedelta(days=i)
                if pattern._pb_cycle_index(day, 0) in slots:
                    worked.add(day.weekday())
            return [w for w in range(7) if w not in worked]
        calendar = self.env.company.sudo().resource_calendar_id
        if not calendar:
            return []
        hours = {int(a.dayofweek) for a in calendar.attendance_ids if not a.display_type}
        return [w for w in range(7) if hours and w not in hours]

    @api.model
    def holidays(self, year=None):
        """Step 5: this company's year of days off (handover §2.1)."""
        self._gate_read()
        company = self.env.company.sudo()           # ledger WS2
        today = self._today()
        year = self._holiday_year(year)
        calendar = company.resource_calendar_id
        days = self._days_off(company, year)
        rest = self._rest_weekdays()
        off = self._off_dates(days, year)
        first = date(year, 1, 1)
        n_days = (date(year, 12, 31) - first).days + 1
        working = sum(1 for i in range(n_days)
                      if (first + timedelta(days=i)).weekday() not in rest
                      and (first + timedelta(days=i)) not in off)
        confirmed_year = company.pb_wfs_holidays_year or 0
        return {
            'year': year,
            'today': fields.Date.to_string(today),
            'years': [today.year + n for n in range(-1, _YEAR_SPAN + 1)],
            'can_edit': self._can_edit() and bool(calendar),
            'has_calendar': bool(calendar),
            'calendar': calendar.name or '' if calendar else '',
            'days': days,
            'rest_weekdays': rest,
            'working_days': working,
            'off_count': len(off),
            'suggestions': self._suggestions(company, year, off),
            'confirmed': confirmed_year >= year,
            'confirmed_year': confirmed_year,
            # October to December: next year's days off are the next question
            'nudge': (year + 1) if (today.month >= 10 and year == today.year
                                     and confirmed_year < year + 1) else False,
        }

    @api.model
    def _suggestions(self, company, year, off=None):
        code = company.country_id.code or ''
        rows = self._suggestion_rows(code, year)
        if not rows:
            return False
        if off is None:
            off = self._off_dates(self._days_off(company, year), year)
        missing = [r for r in rows if fields.Date.to_date(r['date']) not in off]
        return {
            'country': company.country_id.name or code,
            'code': code,
            'year': year,
            'count': len(rows),
            'missing': missing,
            'note': self._suggestion_note(code),
        }

    # ============================================================ writing
    @api.model
    def _holiday_target(self):
        """(company, calendar) for a write: the edit gate, then THIS company
        and its working calendar. sudo only after the gate."""
        self._gate_edit()
        company = self.env.company.sudo()
        calendar = company.resource_calendar_id
        if not calendar:
            raise UserError(_("Choose the company's normal working calendar first."))
        return company, calendar

    @api.model
    def _own_day_off(self, row_id):
        row = self.env['resource.calendar.leaves'].sudo().browse(self._int(row_id)).exists()
        if (not row or row.resource_id or row.time_type != 'leave'
                or row.company_id != self.env.company):
            raise UserError(_("That day is not on this company's calendar."))
        return row

    @api.model
    def _day_label(self, day):
        return format_date(self.env, day, date_format='EEE d MMM')

    @api.model
    def _remark_sentence(self, remark):
        n = (remark or {}).get('changed', {}).get('holiday', 0)
        back = (remark or {}).get('changed', {}).get('normal', 0) + \
            (remark or {}).get('changed', {}).get('rest_day', 0)
        if n == 1:
            return _("1 planned shift is now paid as public holiday.")
        if n:
            return _("%s planned shifts are now paid as public holiday.", self._num(n))
        if back == 1:
            return _("1 planned shift is back to its usual pay.")
        if back:
            return _("%s planned shifts are back to their usual pay.", self._num(back))
        return ''

    @api.model
    def _parse_holiday(self, value):
        try:
            day = fields.Date.to_date(value) if value else None
        except (TypeError, ValueError):
            day = None
        if not day:
            raise UserError(_("Pick a day on the calendar."))
        return day

    @api.model
    def add_day_off(self, day, name=None, kind='company', date_to=None):
        """One day off (a company day off unless told otherwise)."""
        company, calendar = self._holiday_target()
        day = self._parse_holiday(day)
        last = self._parse_holiday(date_to) if date_to else day
        if last < day:
            raise UserError(_("The last day cannot be before the first day."))
        kind = kind if kind in KINDS else 'company'
        name = (name or '').strip() or (_("Company day off") if kind == 'company' else _("Public holiday"))
        taken = self._off_dates(self._days_off(company, day.year))
        if last.year != day.year:
            taken |= self._off_dates(self._days_off(company, last.year))
        cur = day
        while cur <= last:
            if cur in taken:
                raise UserError(_("%s is already a day off.", self._day_label(cur)))
            cur += timedelta(days=1)
        Holidays = self.env['pb.holidays'].sudo()
        row = Holidays._create_row(company, calendar, name[:200], day, last)
        if not row:
            raise UserError(_("%s is already a day off.", self._day_label(day)))
        if row.pb_holiday_kind != kind:
            row.sudo().write({'pb_holiday_kind': kind})
        remark = self.remark_days()
        head = (_("%s is now a company day off.", self._day_label(day)) if kind == 'company'
                else _("%s is now a public holiday.", self._day_label(day)))
        return {'ids': [row.id], 'summary': ' '.join(p for p in (head, self._remark_sentence(remark)) if p),
                'remark': remark}

    @api.model
    def remove_day_off(self, row_id):
        return self.remove_days_off([row_id])

    @api.model
    def remove_days_off(self, row_ids):
        """Take days off away again (also the Undo of an add). All of them or
        none: every row must be a day off of THIS company."""
        self._holiday_target()
        if not isinstance(row_ids, (list, tuple)) or not row_ids:
            raise UserError(_("Pick a day on the calendar."))
        rows = self.env['resource.calendar.leaves'].sudo()
        for rid in row_ids:
            rows |= self._own_day_off(rid)
        company = self.env.company.sudo()
        tz = self.env['pb.holidays']._tz(company.resource_calendar_id, company)
        Holidays = self.env['pb.holidays']
        restore = [{
            'date': Holidays._local_date(r.date_from, tz).isoformat(),
            'date_to': (Holidays._local_date(r.date_to, tz) or Holidays._local_date(r.date_from, tz)).isoformat(),
            'name': r.name or '',
            'kind': r.pb_holiday_kind or 'public',
        } for r in rows]
        names = rows.mapped('name')
        Holidays.sudo()._forget_demo(rows)
        rows.unlink()
        remark = self.remark_days()
        if len(rows) == 1:
            head = _("%s is a working day again.", self._day_label(fields.Date.to_date(restore[0]['date'])))
        else:
            head = _("%s days off removed.", len(rows))
        return {'removed': len(rows), 'names': names, 'restore': restore,
                'summary': ' '.join(p for p in (head, self._remark_sentence(remark)) if p),
                'remark': remark}

    @api.model
    def restore_days_off(self, rows):
        """Undo of a remove: put the same days back, all or nothing."""
        company, calendar = self._holiday_target()
        if not isinstance(rows, (list, tuple)) or not rows:
            raise UserError(_("Nothing to put back."))
        Holidays = self.env['pb.holidays'].sudo()
        made = []
        with self.env.cr.savepoint():
            for r in rows:
                if not isinstance(r, dict):
                    raise UserError(_("Nothing to put back."))
                day = self._parse_holiday(r.get('date'))
                last = self._parse_holiday(r.get('date_to')) if r.get('date_to') else day
                kind = r.get('kind') if r.get('kind') in KINDS else 'company'
                row = Holidays._create_row(company, calendar, (r.get('name') or '').strip()[:200]
                                           or _("Company day off"), day, last)
                if not row:
                    raise UserError(_("%s is already a day off.", self._day_label(day)))
                if row.pb_holiday_kind != kind:
                    row.write({'pb_holiday_kind': kind})
                made.append(row.id)
        remark = self.remark_days()
        head = (_("%s is a day off again.", self._day_label(self._parse_holiday(rows[0].get('date'))))
                if len(made) == 1 else _("%s days off put back.", len(made)))
        return {'ids': made, 'summary': ' '.join(p for p in (head, self._remark_sentence(remark)) if p),
                'remark': remark}

    @api.model
    def add_suggested(self, year):
        """Every suggested public holiday not yet on the calendar, all or
        nothing (one savepoint): a clash refuses the whole call by name."""
        company, calendar = self._holiday_target()
        year = self._holiday_year(year)
        sugg = self._suggestions(company, year)
        if not sugg:
            raise UserError(_("There is no list of public holidays for this country and year."))
        missing = sugg['missing']
        if not missing:
            return {'added': 0, 'ids': [], 'summary': _("All of them are already on the calendar.")}
        Holidays = self.env['pb.holidays'].sudo()
        made = []
        with self.env.cr.savepoint():
            for r in missing:
                day = fields.Date.to_date(r['date'])
                try:
                    row = Holidays._create_row(company, calendar, r['name'][:200], day, day)
                except UserError:
                    row = False
                if not row:
                    raise UserError(_("%(name)s on %(day)s is already on the calendar. Nothing was added.",
                                      name=r['name'], day=self._day_label(day)))
                if row.pb_holiday_kind != 'public':
                    row.write({'pb_holiday_kind': 'public'})
                made.append(row.id)
        remark = self.remark_days()
        head = (_("1 public holiday added.") if len(made) == 1
                else _("%s public holidays added.", len(made)))
        return {'added': len(made), 'ids': made,
                'summary': ' '.join(p for p in (head, self._remark_sentence(remark)) if p),
                'remark': remark}

    @api.model
    def confirm_holidays(self, year):
        self._gate_edit()
        year = self._holiday_year(year)
        company = self.env.company.sudo()
        if not company.resource_calendar_id:
            raise UserError(_("Choose the company's normal working calendar first."))
        if (company.pb_wfs_holidays_year or 0) < year:
            company.write({'pb_wfs_holidays_year': year})
        n = len(self._off_dates(self._days_off(company, year), year))
        return {'year': year, 'summary': (_("Holidays for %(year)s confirmed: 1 day off.", year=year) if n == 1
                                          else _("Holidays for %(year)s confirmed: %(n)s days off.", year=year, n=n))}

    @api.model
    def _holidays_step(self):
        company = self.env.company.sudo()
        year = company.pb_wfs_holidays_year or 0
        if year >= self._today().year:
            n = len(self._off_dates(self._days_off(company, year), year))
            return {'state': 'done', 'text': (_("1 day off in %s", year) if n == 1
                                              else _("%(n)s days off in %(year)s", n=n, year=year))}
        return {'state': 'todo', 'text': _("Check and confirm")}
