# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.time.pay`` — what the clock says, worked out once for the weekly Close.

ONE READ, TWO ANSWERS
---------------------
For every person-day of a Close week this engine works out, LIVE from the
punches (never from the shift model's stored status, ledger S5-2):

  * the OVERTIME the punches suggest — time worked outside the expected window
    and beyond the expected hours; and
  * the LATE and EARLY minutes — the first punch-in after the expected start
    and the last punch-out before the expected end, past the company's grace.

WHAT IS "EXPECTED" (owner ruling L6)
------------------------------------
A published (or completed) shift first — the board the manager already reads.
Where no shift was published, the person's NORMAL WORKING HOURS: the working
schedule on their employee record, read through the calendar's own interval
engine (so two-week schedules and lunch are the calendar's business, not ours).
A day with neither is a rest day: everything worked is overtime, and nobody can
be late for it. A company public holiday (a company closure, finding 4) is the
same, and its overtime is public-holiday overtime.

WHICH PUNCHES COUNT
-------------------
Real ones: the clock machine, the employee's own clock-in page, a correction or
an import. A weekly-grid entry is typed hours with a made-up 08:00 start, so a
day holding one is skipped — reading a lateness off a time nobody punched would
be inventing a fact about a person.

LIKE WITH LIKE (FACTS risk "lunch break skew")
----------------------------------------------
Expected hours are net of the break (`planned_hours`) or of the calendar's
lunch; worked hours are the core `worked_hours`, also net of the calendar's
lunch. The suggestion is the SMALLER of "time outside the window" and "worked
beyond expected", so somebody who came in late and stayed late to make it up is
not offered overtime, and a lunch break is never offered as overtime either.

ROUNDING AND NOISE (report owner question)
------------------------------------------
Suggested hours are rounded DOWN to the quarter hour, and nothing at or under
the company's Close tolerance is suggested. Late and early minutes count from
the expected time, in whole minutes, once they are past the grace minutes.

NOTHING HERE WRITES ON A READ
-----------------------------
`_week` is pure. Every write is in a facade method the Close section calls from
a click (the W21.1 rule of the Close lens), and each is gated, per row, inside
its own savepoint, with refusals collected rather than swallowed.
"""

import logging
import math
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

#: Pay item code -> which minutes it receives. Underscore-free and pairwise
#: non-substring against every code in the registry (C18.2): OTHRS150 OTHRS200
#: OTHRS300 OTHRSNGT BONHRS REGHRS TOTHRS WORKDAYS TRIPDAYS PERDIEM INLOAN.
LATE_INPUT_CODES = {'LATEMIN': 'late', 'EARLYMIN': 'early'}
#: Application-data source key -> which minutes it answers. NOT under
#: `period.`: the engine answers "missing" for every `period.` key when a
#: person has no work calendar, and these do not depend on one.
LATE_SOURCE_KEYS = {'time.late_minutes': 'late',
                    'time.early_minutes': 'early'}
#: Payslip states in which a payslip is still being worked out — the only
#: ones that may take (or let go of) confirmed minutes.
COMPUTING_STATES = ('draft', 'verify')
#: How a value fed from confirmed minutes names itself in a payslip's sources.
LATE_VIA = 'late_minutes'

#: The Close board's row budget (the Workforce `WF_ROW_CAP`).
MAX_ROWS = 200
#: Shift states the Close reads (W24: published AND completed).
PLANNED_STATES = ('published', 'completed')
#: Entry sources that are typed hours, not punches.
TYPED_SOURCES = ('grid',)
#: Overtime kinds a suggestion may carry, in the order a day is classified.
DAY_KINDS = ('holiday', 'weekend', 'weekday')

#: Who may DECIDE on the Close (accept, dismiss, confirm, excuse) — the same
#: people who may waive a Close flag (`pb.close.review._pb_can_review`).
_DECIDE_GATE = 'pb.close.review'


def _quarter_down(hours):
    """Round DOWN to the quarter hour; never a negative."""
    if not hours or hours <= 0:
        return 0.0
    return math.floor(hours * 4 + 1e-9) / 4.0


def _hours(delta):
    return delta.total_seconds() / 3600.0


def _overlap(a_start, a_end, b_start, b_end):
    start, end = max(a_start, b_start), min(a_end, b_end)
    return max(0.0, _hours(end - start)) if end > start else 0.0


class PbTimePay(models.AbstractModel):
    _name = 'pb.time.pay'
    _description = 'Time into pay: suggestions and late minutes'

    # ================================================================ gates
    @api.model
    def _require_reader(self):
        """Reading is the Close board's own gate."""
        self.env['pb.close']._require_officer()

    @api.model
    def _can_decide(self):
        return self.env[_DECIDE_GATE]._pb_can_review()

    @api.model
    def _require_decider(self):
        self._require_reader()
        if not self._can_decide():
            raise AccessError(_(
                "Accepting overtime and confirming late minutes is for "
                "attendance managers and payroll managers."))

    @api.model
    def _own_employee_ids(self):
        """The session user's own employee records, in every company
        (C18.26: never `env.user.employee_id`, which answers for one)."""
        return set(self.env['hr.employee'].sudo().with_context(
            active_test=False).search([('user_id', '=', self.env.uid)]).ids)

    # ========================================================= the calendar
    @api.model
    def _company_tz(self, company):
        calendar = company.sudo().resource_calendar_id
        name = (calendar.tz if calendar else None) \
            or company.sudo().partner_id.tz or 'UTC'
        try:
            return pytz.timezone(name)
        except Exception:                                   # noqa: BLE001
            return pytz.UTC

    @api.model
    def _closure_days(self, companies, d_from, d_to):
        """{company_id: set(date)} of COMPANY PUBLIC HOLIDAYS (finding 4).

        A public holiday on this version is a company closure: a
        `resource.calendar.leaves` row with no resource, written by the
        Holidays screen (`pb.holidays`). The days are read in the company
        calendar's own timezone, which is how that screen draws them.
        """
        out = {c.id: set() for c in companies}
        if not companies:
            return out
        start = datetime.combine(d_from - timedelta(days=1), time.min)
        end = datetime.combine(d_to + timedelta(days=1), time.max)
        rows = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False),
            ('company_id', 'in', companies.ids),
            ('time_type', '=', 'leave'),
            ('date_from', '<=', end),
            ('date_to', '>=', start),
        ])
        tz_cache = {}
        for row in rows:
            company = row.company_id
            if company.id not in tz_cache:
                tz_cache[company.id] = self._company_tz(company)
            tzinfo = tz_cache[company.id]
            first = pytz.UTC.localize(row.date_from).astimezone(tzinfo).date()
            last = pytz.UTC.localize(row.date_to).astimezone(tzinfo).date()
            day = first
            while day <= last:
                if d_from <= day <= d_to:
                    out.setdefault(company.id, set()).add(day)
                day += timedelta(days=1)
        return out

    @api.model
    def _ot_configs(self, company):
        """{overtime_type: config} — active rules of the company, then the
        global ones. NOT the nationality-keyed lookup of the request
        (ledger S5-5): a kind of day is the company's question."""
        rows = self.env['hr.overtime.config'].sudo().search([
            ('active', '=', True),
            '|', ('company_id', '=', company.id), ('company_id', '=', False),
        ], order='company_id desc, sequence, id')
        out = {}
        for row in rows:
            out.setdefault(row.overtime_type, row)
        return out

    @api.model
    def _kind_for(self, wanted, configs):
        """The kind a suggestion carries: the one the day is, or — when the
        company has no rule for it — the next more ordinary one."""
        chain = {'holiday': ('holiday', 'weekend', 'weekday'),
                 'weekend': ('weekend', 'weekday'),
                 'weekday': ('weekday',)}.get(wanted, ('weekday',))
        for kind in chain:
            if kind in configs:
                return kind
        return 'weekday'

    # ============================================================ the reads
    @api.model
    def _shift_windows(self, emps, d_from, d_to):
        rows = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', 'in', emps.ids),
            ('date', '>=', d_from), ('date', '<=', d_to),
            ('state', 'in', PLANNED_STATES),
        ])
        out = {}
        for shift in rows:
            if not (shift.start_datetime and shift.end_datetime):
                continue
            key = (shift.employee_id.id, shift.date)
            cur = out.get(key)
            if cur is None:
                out[key] = {'basis': 'shift', 'start': shift.start_datetime,
                            'end': shift.end_datetime,
                            'hours': shift.planned_hours or 0.0}
            else:
                cur['start'] = min(cur['start'], shift.start_datetime)
                cur['end'] = max(cur['end'], shift.end_datetime)
                cur['hours'] += shift.planned_hours or 0.0
        return out

    @api.model
    def _hours_windows(self, emps, d_from, d_to):
        """{(emp_id, local date): window} from each person's working schedule.

        One call to the calendar's interval engine per CALENDAR, for all of its
        people. A flexible schedule has no window, so it answers nothing.
        """
        out = {}
        by_cal = defaultdict(lambda: self.env['hr.employee'])
        for emp in emps:
            cal = emp.resource_calendar_id
            if cal and not getattr(cal, 'flexible_hours', False) \
                    and emp.resource_id:
                by_cal[cal] |= emp
        start = pytz.UTC.localize(datetime.combine(
            d_from - timedelta(days=1), time.min))
        end = pytz.UTC.localize(datetime.combine(
            d_to + timedelta(days=2), time.min))
        for cal, people in by_cal.items():
            try:
                found = cal.sudo()._attendance_intervals_batch(
                    start, end, resources=people.resource_id)
            except Exception:                               # noqa: BLE001
                _logger.debug('pb_time_pay: working hours of %s unreadable',
                              cal.id, exc_info=True)
                continue
            for emp in people:
                for (a, b, _att) in found.get(emp.resource_id.id) or []:
                    day = a.date()
                    if not (d_from <= day <= d_to) or b <= a:
                        continue
                    s = a.astimezone(pytz.UTC).replace(tzinfo=None)
                    e = b.astimezone(pytz.UTC).replace(tzinfo=None)
                    key = (emp.id, day)
                    cur = out.get(key)
                    if cur is None:
                        out[key] = {'basis': 'hours', 'start': s, 'end': e,
                                    'hours': _hours(e - s)}
                    else:
                        cur['start'] = min(cur['start'], s)
                        cur['end'] = max(cur['end'], e)
                        cur['hours'] += _hours(e - s)
        return out

    @api.model
    def _punches(self, emps, d_from, d_to):
        """{(emp_id, local date): [attendance]} — the Close's own local day."""
        Close = self.env['pb.close']
        rows = self.env['hr.attendance'].sudo().search([
            ('employee_id', 'in', emps.ids),
            ('check_in', '>=', datetime.combine(d_from - timedelta(days=1),
                                                time.min)),
            ('check_in', '<=', datetime.combine(d_to + timedelta(days=1),
                                                time.max)),
        ], order='check_in')
        out = defaultdict(list)
        cache = {}
        for att in rows:
            day = Close._local_day(att.employee_id, att.check_in, cache)
            if day and d_from <= day <= d_to:
                out[(att.employee_id.id, day)].append(att)
        return out

    @api.model
    def _night_segments(self, config, emp_tz, day):
        """The night window(s) touching a local day, as naive-UTC pairs."""
        if not config:
            return []
        t_from, t_to = config.time_from or 0.0, config.time_to or 0.0
        if t_from == t_to:
            return []

        def at(d, h):
            hh = int(h)
            mm = int(round((h - hh) * 60))
            if hh >= 24:
                d, hh = d + timedelta(days=1), hh - 24
            local = emp_tz.localize(datetime.combine(d, time(hh, mm)))
            return local.astimezone(pytz.UTC).replace(tzinfo=None)

        out = []
        for d in (day - timedelta(days=1), day, day + timedelta(days=1)):
            if t_from < t_to:
                out.append((at(d, t_from), at(d, t_to)))
            else:
                out.append((at(d, t_from), at(d + timedelta(days=1), t_to)))
        return out

    # ============================================================= the week
    @api.model
    def _week(self, emps, d_from, d_to, today=None):
        """``(suggestions, late)`` for these people over [d_from, d_to]. PURE.

        ``suggestions`` — [{key, employee_id, date, kind, hours, basis,
        worked, expected}]; ``late`` — [{key, employee_id, date, kind,
        minutes, basis, expected_at, actual_at}]. Days after ``today`` are
        never read (a day that has not happened is nobody's overtime).
        """
        today = today or fields.Date.context_today(self)
        d_to = min(d_to, today)
        if not emps or d_to < d_from:
            return [], []
        emps = emps.sudo()
        companies = emps.company_id
        closures = self._closure_days(companies, d_from, d_to)
        shifts = self._shift_windows(emps, d_from, d_to)
        hours = self._hours_windows(emps, d_from, d_to)
        punches = self._punches(emps, d_from, d_to)
        Engine = self.env['pb.attendance.exception.engine']
        trip_map = Engine._trip_days(emps.ids, d_from, d_to)
        leave_map = Engine._leave_days(emps.ids, d_from, d_to)
        try:
            leave_parts = Engine._leave_parts(emps.ids, d_from, d_to)
        except Exception:                                   # noqa: BLE001
            leave_parts = {}
        first_contract = Engine._first_contract_day(emps.ids)
        Rule = self.env['pb.attendance.rule']
        rules, configs, tz_cache = {}, {}, {}

        suggestions, late = [], []
        for emp in emps:
            company = emp.company_id
            if company.id not in rules:
                g_in, g_out, _open = Rule._grace_for_company(company)
                var_min, _var_week = Rule._variance_for_company(company)
                rules[company.id] = (g_in, g_out, var_min)
                configs[company.id] = self._ot_configs(company)
            g_in, g_out, var_min = rules[company.id]
            cfg = configs[company.id]
            try:
                emp_tz = pytz.timezone(emp.tz or 'UTC')
            except Exception:                               # noqa: BLE001
                emp_tz = pytz.UTC
            tz_cache[emp.id] = emp_tz
            day = d_from
            while day <= d_to:
                cur, day = day, day + timedelta(days=1)
                fc = first_contract.get(emp.id)
                if fc and cur < fc:
                    continue
                iso = cur.isoformat()
                if iso in trip_map.get(emp.id, ()) \
                        or iso in leave_map.get(emp.id, ()):
                    continue
                atts = punches.get((emp.id, cur)) or []
                if not atts:
                    continue
                if any((a.pb_entry_source or '') in TYPED_SOURCES
                       for a in atts):
                    continue        # typed hours, not punches
                holiday = cur in closures.get(company.id, ())
                window = shifts.get((emp.id, cur)) or hours.get((emp.id, cur))
                closed = [a for a in atts if a.check_in and a.check_out]
                still_open = len(closed) != len(atts)

                # ---------------------------------------------- lateness
                if window and not holiday \
                        and (emp.id, iso) not in leave_parts:
                    first_in = min(a.check_in for a in atts if a.check_in)
                    mins = (first_in - window['start']).total_seconds() / 60.0
                    if mins > g_in:
                        late.append(self._late_row(
                            emp, cur, 'late', int(mins), window,
                            first_in))
                    if closed and not still_open:
                        last_out = max(a.check_out for a in closed)
                        mins = (window['end'] - last_out).total_seconds() / 60.0
                        if mins > g_out:
                            late.append(self._late_row(
                                emp, cur, 'early', int(mins), window,
                                last_out))

                # ---------------------------------------------- overtime
                if not closed or still_open:
                    continue
                worked = sum(a.worked_hours or 0.0 for a in closed)
                segments = []
                if window and not holiday:
                    for a in closed:
                        if a.check_in < window['start']:
                            segments.append((a.check_in,
                                             min(a.check_out, window['start'])))
                        if a.check_out > window['end']:
                            segments.append((max(a.check_in, window['end']),
                                             a.check_out))
                    outside = sum(_hours(e - s) for s, e in segments if e > s)
                    excess = worked - (window['hours'] or 0.0)
                    total = min(outside, excess) if outside > 0 and excess > 0 \
                        else 0.0
                    wanted = 'weekday'
                    basis = window['basis']
                else:
                    segments = [(a.check_in, a.check_out) for a in closed]
                    outside = sum(_hours(e - s) for s, e in segments)
                    total = worked
                    wanted = 'holiday' if holiday else 'weekend'
                    basis = 'holiday' if holiday else 'rest'
                if total * 60.0 <= var_min:
                    continue
                night_cfg = cfg.get('night')
                night = 0.0
                if night_cfg and outside > 0:
                    windows = self._night_segments(night_cfg, emp_tz, cur)
                    in_night = sum(_overlap(s, e, ns, ne)
                                   for s, e in segments
                                   for ns, ne in windows)
                    night = total * min(1.0, in_night / outside)
                day_kind = self._kind_for(wanted, cfg)
                parts = [(day_kind, _quarter_down(total - night))]
                if night_cfg:
                    parts.append(('night', _quarter_down(night)))
                else:
                    parts = [(day_kind, _quarter_down(total))]
                for kind, h in parts:
                    if h <= 0:
                        continue
                    suggestions.append({
                        'key': '%s:%s:%s' % (emp.id, iso, kind),
                        'employee_id': emp.id,
                        'date': iso,
                        'kind': kind,
                        'hours': h,
                        'basis': basis,
                        'worked': round(worked, 2),
                        'expected': round(window['hours'], 2)
                        if window and not holiday else 0.0,
                    })
        return suggestions, late

    @api.model
    def _late_row(self, emp, day, kind, minutes, window, actual):
        return {
            'key': '%s:%s:%s' % (emp.id, day.isoformat(), kind),
            'employee_id': emp.id,
            'date': day.isoformat(),
            'kind': kind,
            'minutes': int(minutes),
            'basis': window['basis'],
            'expected_at': window['start'] if kind == 'late' else window['end'],
            'actual_at': actual,
        }

    # ====================================================== scheme answers
    @api.model
    def _schemes_of(self, company):
        Config = self.env['hr.formula.config'].sudo()
        domain = [('state', '!=', 'archived')]
        if 'company_id' in Config._fields:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', '=', company.id)]
        return Config.search(domain)

    @api.model
    def _late_in_pay(self, company):
        """Is a late or early minutes pay item mapped in any live scheme of
        this company? Until one is, the Close shows the minutes for
        information and never holds the week for them."""
        schemes = self._schemes_of(company)
        if not schemes:
            return False
        Rule = self.env['hr.formula.rule'].sudo()
        domain = [('config_id', 'in', schemes.ids),
                  ('column_type', '=', 'input')]
        keyed = 'application_source_key' in Rule._fields
        if keyed:
            domain += ['|', ('code', 'in', list(LATE_INPUT_CODES)),
                       ('application_source_key', 'in',
                        list(LATE_SOURCE_KEYS))]
        else:
            domain += [('code', 'in', list(LATE_INPUT_CODES))]
        return bool(Rule.search_count(domain))

    @api.model
    def _file_schemes(self, company):
        """The live schemes of this company that ask for a PAY DATA FILE —
        the same predicate the Run payroll screen uses to show its file step
        (a spreadsheet lane switched on and a pay item bound to a column).
        Those payslips never read overtime requests or confirmed minutes
        (ledger S5-1), so the Close lists them and says so."""
        schemes = self._schemes_of(company).filtered(
            lambda c: getattr(c, 'source_excel_enabled', True))
        if not schemes or 'hr.formula.rule.source' not in self.env:
            return schemes.browse()
        sources = self.env['hr.formula.rule.source'].sudo().search([
            ('kind', '=', 'excel'), ('rule_id.config_id', 'in', schemes.ids)])
        ids = {s.rule_id.config_id.id for s in sources if (s.key or '').strip()}
        return schemes.filtered(lambda c: c.id in ids)

    # =================================================== time off in lieu
    @api.model
    def _toil_kind(self, company, create=True):
        """The company's "Time off in lieu" kind of leave, made the first time
        a manager gives time off. Counted in hours, against an allowance,
        paid, never after the event, never deducted from core overtime.
        Nothing is made by install (silent-install rule)."""
        Type = self.env['hr.leave.type'].sudo().with_context(active_test=False)
        kind = Type.search([('pb_toil_kind', '=', True),
                            ('company_id', '=', company.id)], limit=1)
        if kind:
            if not kind.active:
                raise UserError(_(
                    "The \"Time off in lieu\" kind of leave is switched off for "
                    "%s. Switch it back on before giving time off.",
                    company.name))
            return kind
        if not create:
            return kind
        vals = {
            'name': 'Time off in lieu',
            'company_id': company.id,
            'pb_toil_kind': True,
            'requires_allocation': True,
            'request_unit': 'hour',
            'time_type': 'leave',
        }
        fields_ = Type._fields
        if fields_['requires_allocation'].type == 'selection':
            vals['requires_allocation'] = 'yes'
        optional = {
            'pb_pay_treatment': 'paid',
            'pb_pay_funding': 'employer',
            'pb_backdate_ok': False,
            'overtime_deductible': False,
            'unpaid': False,
        }
        for name, value in optional.items():
            if name in fields_:
                vals[name] = value
        kind = Type.create(vals)
        langs = {code for code, _n in self.env['res.lang'].get_installed()}
        names = {'vi_VN': 'Nghỉ bù', 'id_ID': 'Cuti pengganti lembur'}
        names = {k: v for k, v in names.items() if k in langs}
        if names:
            try:
                kind.update_field_translations('name', names)
            except Exception:                               # noqa: BLE001
                _logger.debug('pb_time_pay: kind name translations',
                              exc_info=True)
        return kind

    # ======================================================= Close payload
    @api.model
    def _close_payload(self, department_id=False, week_start=False,
                       search=False):
        """What the Close section draws. PURE (W21/W25)."""
        self._require_reader()
        Close = self.env['pb.close']
        df = Close._monday(week_start)
        dt = df + timedelta(days=6)
        today = fields.Date.context_today(self)
        emps, _truncated = Close._population(department_id, search)
        suggestions, late = self._week(emps, df, dt, today)
        names = {e.id: e for e in emps}
        company = self.env.company
        locked = self.env['pb.wf.lock']._locked_dates(
            company, [df + timedelta(days=i) for i in range(7)])
        own = self._own_employee_ids()

        # ---- suggestions: minus what already has a request or was dismissed
        existing = set()
        if emps:
            for r in self.env['hr.overtime.request'].sudo().search_read(
                    [('employee_id', 'in', emps.ids),
                     ('date', '>=', df), ('date', '<=', dt)],
                    ['employee_id', 'date', 'overtime_type']):
                existing.add((r['employee_id'][0], r['date'].isoformat(),
                              r['overtime_type']))
            for r in self.env['pb.time.ot.dismiss'].sudo().search_read(
                    [('employee_id', 'in', emps.ids),
                     ('date', '>=', df), ('date', '<=', dt)],
                    ['employee_id', 'date', 'kind']):
                existing.add((r['employee_id'][0], r['date'].isoformat(),
                              r['kind']))
        kind_labels = dict(self.env['hr.overtime.request']._fields[
            'overtime_type']._description_selection(self.env))
        basis_labels = self._basis_labels()
        sugg_rows = []
        for s in suggestions:
            if (s['employee_id'], s['date'], s['kind']) in existing:
                continue
            emp = names.get(s['employee_id'])
            day = fields.Date.to_date(s['date'])
            sugg_rows.append(dict(
                s, **self._person(emp, day),
                kind_label=kind_labels.get(s['kind'], s['kind']),
                basis_label=basis_labels.get(s['basis'], ''),
                locked=day in locked,
                own=s['employee_id'] in own))
        sugg_total = len(sugg_rows)
        sugg_hours = round(sum(r['hours'] for r in sugg_rows), 2)

        # ---- late and early: live rows merged with the stored decisions
        Late = self.env['pb.time.late'].sudo()
        stored = {}
        if emps:
            for row in Late.search([('employee_id', 'in', emps.ids),
                                    ('date', '>=', df), ('date', '<=', dt)]):
                stored[row._key()] = row
        live = {r['key']: r for r in late}
        late_rows = []
        for key in sorted(set(live) | set(stored)):
            r = live.get(key)
            row = stored.get(key)
            emp = names.get((r or {}).get('employee_id')
                            or (row.employee_id.id if row else 0))
            if not emp:
                continue
            day = fields.Date.to_date(r['date'] if r else row.date)
            minutes_live = r['minutes'] if r else 0
            state = row.state if row else 'open'
            changed = bool(row) and row.minutes != minutes_live
            tz = pytz.timezone(emp.tz or 'UTC') if emp.tz else pytz.UTC
            late_rows.append(dict(
                self._person(emp, day),
                key=key, employee_id=emp.id, date=day.isoformat(),
                kind=(r or {}).get('kind') or row.kind,
                kind_label=(_("Late arrival")
                            if ((r or {}).get('kind') or row.kind) == 'late'
                            else _("Early leave")),
                minutes=minutes_live,
                decided_minutes=row.minutes if row else 0,
                state=state,
                changed=changed,
                expected=self._clock(r['expected_at'], tz) if r else '',
                actual=self._clock(r['actual_at'], tz) if r else '',
                expected_at=fields.Datetime.to_string(r['expected_at'])
                if r else False,
                actual_at=fields.Datetime.to_string(r['actual_at'])
                if r else False,
                basis=(r or {}).get('basis') or (row.basis if row else False),
                basis_label=basis_labels.get((r or {}).get('basis')
                                             or (row.basis if row else ''),
                                             ''),
                locked=day in locked,
                paid=bool(row) and row.pay_state == 'paid',
                held=bool(row) and row.pay_state == 'held',
                own=emp.id in own,
                note=(row.note or '') if row else ''))
        # undecided = no decision yet, or the punches changed since it was made
        open_n = sum(1 for r in late_rows
                     if (r['state'] == 'open' and r['minutes'])
                     or (r['changed'] and not r['paid']))
        late_rows.sort(key=lambda r: (r['state'] != 'open' and not r['changed'],
                                      r['date'], r['name']))
        stats = {
            'open': open_n,
            'confirmed': sum(1 for r in late_rows if r['state'] == 'confirmed'),
            'excused': sum(1 for r in late_rows if r['state'] == 'excused'),
            'minutes_confirmed': sum(r['decided_minutes'] for r in late_rows
                                     if r['state'] == 'confirmed'),
            'minutes_open': sum(r['minutes'] for r in late_rows
                                if r['state'] == 'open'),
        }
        files = self._file_schemes(company)
        grace_in, grace_out, _o = self.env[
            'pb.attendance.rule']._grace_for_company(company)
        return {
            'suggestions': sugg_rows[:MAX_ROWS],
            'suggestions_total': sugg_total,
            'suggestions_hours': sugg_hours,
            'late': late_rows[:MAX_ROWS],
            'late_total': len(late_rows),
            'late_stats': stats,
            'late_in_pay': self._late_in_pay(company),
            'grace_in': grace_in,
            'grace_out': grace_out,
            'file_schemes': [c.name for c in files][:12],
            'file_month': self._file_month(emps, df, dt, files)
            if files else {},
            'can_decide': self._can_decide(),
            'toil_kind': bool(self._toil_kind(company, create=False)),
        }

    @api.model
    def _basis_labels(self):
        return {
            'shift': _("Compared with the shift"),
            'hours': _("Compared with working hours"),
            'rest': _("Rest day"),
            'holiday': _("Public holiday"),
        }

    @api.model
    def _person(self, emp, day):
        if not emp:
            return {'name': '', 'avatar_url': '', 'day_label': ''}
        return {
            'name': emp.name or '',
            'dept': emp.department_id.name if emp.department_id else '',
            'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'day_label': day.strftime('%a %b %d') if day else '',
        }

    @api.model
    def _clock(self, dt_utc, tzinfo):
        if not dt_utc:
            return ''
        return pytz.UTC.localize(dt_utc).astimezone(tzinfo).strftime('%H:%M')

    @api.model
    def _file_month(self, emps, df, dt, files):
        """For schemes paid from a pay data file: per person, the month's
        figures the file has to carry — overtime to PAY (time off excluded)
        by kind, and the confirmed late and early minutes. The month is the
        one the Close week's Monday is in."""
        if not emps:
            return {}
        first = df.replace(day=1)
        last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        out = {}
        Req = self.env['hr.overtime.request'].sudo()
        for r in Req.search([('employee_id', 'in', emps.ids),
                             ('date', '>=', first), ('date', '<=', last),
                             ('state', '=', 'approved')]):
            if r.pb_comp_choice == 'time_off':
                continue
            row = out.setdefault(r.employee_id.id, {
                'employee_id': r.employee_id.id, 'name': r.employee_id.name,
                'ot': defaultdict(float), 'late': 0, 'early': 0})
            row['ot'][r.overtime_type] += (r.approved_hours or 0.0)
            row['ot']['bonus'] += (r.bonus_hours or 0.0)
        for late in self.env['pb.time.late'].sudo().search([
                ('employee_id', 'in', emps.ids), ('state', '=', 'confirmed'),
                ('date', '>=', first), ('date', '<=', last)]):
            row = out.setdefault(late.employee_id.id, {
                'employee_id': late.employee_id.id,
                'name': late.employee_id.name,
                'ot': defaultdict(float), 'late': 0, 'early': 0})
            row[late.kind] += late.minutes
        rows = []
        for row in sorted(out.values(), key=lambda r: r['name'] or ''):
            ot = row.pop('ot')
            row.update({k: round(ot.get(k, 0.0), 2) for k in
                        ('weekday', 'weekend', 'holiday', 'night', 'bonus')})
            rows.append(row)
        return {'month': first.strftime('%B %Y'), 'rows': rows[:MAX_ROWS]}

    # ============================================================ the doors
    # Everything below WRITES and is reachable only from a click.
    @api.model
    def _live_suggestions(self, department_id, week_start, search):
        payload = self._close_payload(department_id, week_start, search)
        return {r['key']: r for r in payload['suggestions']}

    @api.model
    def accept_suggestions(self, keys, choice='pay', department_id=False,
                           week_start=False, search=False):
        """Turn suggestions into ordinary overtime requests and send them on
        the overtime route. The set is the one on screen (rebuilt through the
        same read), never a list of hours the browser made up."""
        self._require_decider()
        if choice not in ('pay', 'time_off'):
            raise UserError(_("Unknown choice."))
        live = self._live_suggestions(department_id, week_start, search)
        Req = self.env['hr.overtime.request'].sudo()
        basis_words = self._basis_labels()
        created, skipped = [], []
        for key in keys or []:
            s = live.get(key)
            if not s:
                skipped.append({'key': key, 'name': '', 'date': '',
                                'reason': _("This suggestion is no longer on "
                                            "the board.")})
                continue
            if s['own']:
                skipped.append({'key': key, 'name': s['name'],
                                'date': s['date'],
                                'reason': _("You cannot accept overtime for "
                                            "yourself.")})
                continue
            emp = self.env['hr.employee'].sudo().browse(s['employee_id'])
            reason = _("Suggested from clock punches: worked %(worked)s h, "
                       "expected %(expected)s h (%(basis)s).",
                       worked='{:g}'.format(s['worked']),
                       expected='{:g}'.format(s['expected']),
                       basis=basis_words.get(s['basis'], ''))
            try:
                with self.env.cr.savepoint():
                    req = Req.with_context(**{
                        'pb_time_pay_choice': choice}).create({
                        'employee_id': emp.id,
                        'date': s['date'],
                        'overtime_type': s['kind'],
                        'planned_hours': s['hours'],
                        'actual_hours': s['hours'],
                        'reason': reason,
                        'company_id': emp.company_id.id
                        or self.env.company.id,
                        'pb_from_punches': True,
                    })
                    req.action_submit()
                created.append(req.id)
            except (AccessError, UserError, ValidationError) as exc:
                skipped.append({'key': key, 'name': s['name'],
                                'date': s['date'], 'reason': str(exc)})
        return {'created': len(created), 'request_ids': created,
                'skipped': skipped, 'requested': len(keys or [])}

    @api.model
    def dismiss_suggestion(self, key, note=False, department_id=False,
                           week_start=False, search=False):
        """"Not overtime" — the suggestion stops showing, and why is kept."""
        self._require_decider()
        live = self._live_suggestions(department_id, week_start, search)
        s = live.get(key)
        if not s:
            raise UserError(_("This suggestion is no longer on the board."))
        if s['own']:
            raise UserError(_("You cannot decide about your own overtime."))
        Dismiss = self.env['pb.time.ot.dismiss'].sudo()
        emp = self.env['hr.employee'].sudo().browse(s['employee_id'])
        found = Dismiss.search([('employee_id', '=', emp.id),
                                ('date', '=', s['date']),
                                ('kind', '=', s['kind'])], limit=1)
        if found:
            return found.id
        return Dismiss.create({
            'employee_id': emp.id, 'company_id': emp.company_id.id,
            'date': s['date'], 'kind': s['kind'], 'hours': s['hours'],
            'note': (note or '').strip() or False,
            'user_id': self.env.uid}).id

    @api.model
    def decide_late(self, keys, decision, note=False, department_id=False,
                    week_start=False, search=False):
        """Confirm (it counts for pay) or Excuse (it does not) late and early
        minutes, one or many. The minutes recorded are the ones on screen,
        rebuilt from the punches by the same read."""
        self._require_decider()
        if decision not in ('confirmed', 'excused'):
            raise UserError(_("Unknown decision."))
        payload = self._close_payload(department_id, week_start, search)
        rows = {r['key']: r for r in payload['late']}
        Late = self.env['pb.time.late'].sudo()
        done, skipped = 0, []
        note = (note or '').strip() or False
        for key in keys or []:
            r = rows.get(key)
            if not r:
                skipped.append({'key': key, 'name': '', 'date': '',
                                'reason': _("This row is no longer on the "
                                            "board.")})
                continue
            try:
                with self.env.cr.savepoint():
                    Late._decide(r, decision, note)
                done += 1
            except (AccessError, UserError, ValidationError) as exc:
                skipped.append({'key': key, 'name': r['name'],
                                'date': r['date'], 'reason': str(exc)})
        return {'decided': done, 'decision': decision, 'skipped': skipped,
                'requested': len(keys or [])}

    @api.model
    def set_overtime_choice(self, request_ids, choice):
        """"Pay it" or "Give time off" on overtime that is not decided yet,
        by somebody who may decide it (the overtime model's own rule)."""
        if choice not in ('pay', 'time_off'):
            raise UserError(_("Unknown choice."))
        Req = self.env['hr.overtime.request']
        results = []
        for rid in request_ids or []:
            rec = Req.browse(int(rid)).exists()
            if not rec:
                results.append({'id': rid, 'ok': False,
                                'error': _("No longer exists.")})
                continue
            try:
                with self.env.cr.savepoint():
                    rec._pb_set_choice(choice)
                results.append({'id': rec.id, 'ok': True})
            except (AccessError, UserError, ValidationError) as exc:
                results.append({'id': rec.id, 'ok': False,
                                'error': str(exc)})
        return {'results': results}
