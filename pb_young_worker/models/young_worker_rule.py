# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Young-worker rule engine + config (Phase E §3).

Everything under-18 is DATA-driven: a per-company rule owns age bands, each band
carries its daily/weekly hour caps and OT/night blocks. The `pb.young.worker`
AbstractModel is the single engine every gate calls — no age or cap is ever
hardcoded, and a missing birthday is treated as an adult (never a false block),
surfaced only as a data-quality task in the cockpit.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta

from pytz import timezone, utc, UnknownTimeZoneError

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PbYoungWorkerRule(models.Model):
    _name = 'pb.young.worker.rule'
    _description = 'Young Worker Rule Set'
    _order = 'company_id, id'

    name = fields.Char(string='Name', required=True, default=lambda self: _('Young Worker Rules'))
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    # Night window as local wall-clock hours (24h float); default 22:00 → 06:00.
    night_from = fields.Float(string='Night From', default=22.0,
                              help='Start of the protected night window (24h, e.g. 22.0 = 22:00).')
    night_to = fields.Float(string='Night To', default=6.0,
                            help='End of the protected night window (24h, e.g. 6.0 = 06:00).')
    band_ids = fields.One2many('pb.young.worker.band', 'rule_id', string='Age Bands')
    note = fields.Text(string='Notes')

    @api.constrains('band_ids')
    def _check_no_band_overlap(self):
        for rule in self:
            bands = rule.band_ids.sorted(key=lambda b: (b.age_min, b.age_max))
            prev = None
            for b in bands:
                if b.age_min >= b.age_max:
                    raise ValidationError(_(
                        "A young-worker band must have age_min < age_max (got %(lo)s–%(hi)s).",
                        lo=b.age_min, hi=b.age_max))
                if prev is not None and b.age_min < prev.age_max:
                    raise ValidationError(_(
                        "Young-worker age bands may not overlap: %(a)s–%(b)s overlaps "
                        "%(c)s–%(d)s.",
                        a=prev.age_min, b=prev.age_max, c=b.age_min, d=b.age_max))
                prev = b


class PbYoungWorkerBand(models.Model):
    _name = 'pb.young.worker.band'
    _description = 'Young Worker Age Band'
    _order = 'age_min, id'

    rule_id = fields.Many2one('pb.young.worker.rule', string='Rule',
                              required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='rule_id.company_id', store=True, index=True)
    age_min = fields.Integer(string='Age From', required=True,
                             help='Inclusive lower bound (full years).')
    age_max = fields.Integer(string='Age To', required=True,
                             help='Exclusive upper bound (full years).')
    max_hours_day = fields.Float(string='Max Hours / Day', required=True, default=8.0)
    max_hours_week = fields.Float(string='Max Hours / Week', required=True, default=40.0)
    ot_blocked = fields.Boolean(string='Overtime Blocked', default=True)
    night_blocked = fields.Boolean(string='Night Work Blocked', default=True)
    note = fields.Char(string='Label')

    def _caps(self):
        """Serialisable band summary for the grid flags / cockpit."""
        self.ensure_one()
        return {
            'age_min': self.age_min,
            'age_max': self.age_max,
            'max_hours_day': self.max_hours_day,
            'max_hours_week': self.max_hours_week,
            'ot_blocked': self.ot_blocked,
            'night_blocked': self.night_blocked,
            'label': self.note or '',
        }


class PbYoungWorker(models.AbstractModel):
    """The engine — every gate calls these; no logic is duplicated in a gate."""
    _name = 'pb.young.worker'
    _description = 'Young Worker Engine'

    # A little slack over the daily cap so a normal shift that runs a few minutes
    # long doesn't hard-block the punch. Weekly caps are exact (no grace).
    DAILY_GRACE = 0.5

    # ------------------------------------------------------------- rule lookup
    @api.model
    def _has_any_rule(self):
        """Cheap short-circuit for the hot constraint path (no minors → no work)."""
        return bool(self.env['pb.young.worker.rule'].sudo().search_count(
            [('active', '=', True)]))

    @api.model
    def _rule_for_company(self, company):
        company = company or self.env.company
        return self.env['pb.young.worker.rule'].sudo().search(
            [('active', '=', True), ('company_id', '=', company.id)], limit=1)

    # ------------------------------------------------------------- age / band
    @api.model
    def _birthday(self, employee):
        """Birthday read via sudo (the field is HR-group-scoped on hr.employee /
        hr.version in Odoo 19). Field-name-defensive: never guess an age."""
        emp = employee.sudo()
        if 'birthday' in emp._fields:
            return emp.birthday or False
        return False

    @api.model
    def _age(self, employee, on_date):
        """Full years at `on_date`, or None when there is no birthday on file."""
        bday = self._birthday(employee)
        if not bday:
            return None
        return (on_date.year - bday.year
                - ((on_date.month, on_date.day) < (bday.month, bday.day)))

    @api.model
    def get_band(self, employee, on_date):
        """The applicable age band for `employee` on `on_date`, or an empty
        recordset (adult, no birthday, or no rule for the company)."""
        Band = self.env['pb.young.worker.band']
        age = self._age(employee, on_date)
        if age is None:
            return Band
        rule = self._rule_for_company(employee.company_id)
        if not rule:
            return Band
        for b in rule.band_ids:
            if b.age_min <= age < b.age_max:
                return b
        return Band

    @api.model
    def is_minor(self, employee, on_date):
        return bool(self.get_band(employee, on_date))

    # ------------------------------------------------------------- tz helpers
    @api.model
    def _emp_tz_name(self, emp):
        cal = emp.resource_calendar_id or emp.company_id.resource_calendar_id
        name = (cal.tz if cal else False) or emp.tz or self.env.user.tz or 'UTC'
        try:
            timezone(name)
        except UnknownTimeZoneError:
            name = 'UTC'
        return name

    @api.model
    def _day_bounds_utc(self, emp, d):
        """(utc_start, utc_end) naive datetimes bounding the employee-tz local day."""
        tz = timezone(self._emp_tz_name(emp))
        start = tz.localize(datetime.combine(d, time.min)).astimezone(utc).replace(tzinfo=None)
        end = tz.localize(datetime.combine(d, time.max)).astimezone(utc).replace(tzinfo=None)
        return start, end

    @api.model
    def _local_date(self, emp, dt_utc):
        """Local calendar date (employee tz) of a naive-UTC datetime."""
        tz = timezone(self._emp_tz_name(emp))
        return utc.localize(dt_utc).astimezone(tz).date()

    @api.model
    def _att_hours(self, a):
        """Wall-clock span (consistent with the Phase B grid's REG synthesis)."""
        if a.check_in and a.check_out:
            return (a.check_out - a.check_in).total_seconds() / 3600.0
        return a.worked_hours or 0.0

    # ------------------------------------------------------------- hour checks
    @api.model
    def check_day_hours(self, employee, d, extra_hours=0.0):
        band = self.get_band(employee, d)
        if not band:
            return {'ok': True, 'cap': 0.0, 'actual': 0.0, 'band': False}
        start, end = self._day_bounds_utc(employee, d)
        atts = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start), ('check_in', '<=', end),
        ])
        total = sum(self._att_hours(a) for a in atts) + (extra_hours or 0.0)
        cap = band.max_hours_day
        return {'ok': total <= cap + self.DAILY_GRACE, 'cap': cap,
                'actual': round(total, 2), 'band': band}

    @api.model
    def check_week_hours(self, employee, any_date, extra=0.0):
        band = self.get_band(employee, any_date)
        if not band:
            return {'ok': True, 'cap': 0.0, 'actual': 0.0, 'band': False}
        monday = any_date - timedelta(days=any_date.weekday())
        sunday = monday + timedelta(days=6)
        start, _s = self._day_bounds_utc(employee, monday)
        _e, end = self._day_bounds_utc(employee, sunday)
        atts = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start), ('check_in', '<=', end),
        ])
        total = sum(self._att_hours(a) for a in atts) + (extra or 0.0)
        cap = band.max_hours_week
        return {'ok': total <= cap, 'cap': cap, 'actual': round(total, 2),
                'band': band, 'week_start': monday.isoformat()}

    # ------------------------------------------------------------- batch feed
    @api.model
    def check_period(self, employees, date_from, date_to, include_no_birthday=True):
        """Every young-worker violation for `employees` over [date_from, date_to].

        Returns [{employee_id, name, kind, date, detail}] where kind is one of
        day_cap | week_cap | ot | night | no_birthday. Batch: one attendance /
        OT / shift read across the whole cohort. Adults and birthday-less
        employees (unless include_no_birthday) produce nothing — the hot path
        for the general population is a single band lookup per employee.
        """
        df = fields.Date.to_date(date_from)
        dt = fields.Date.to_date(date_to)
        out = []
        if not employees or not df or not dt:
            return out

        # cache the per-company rule once — a division payroll run passes 900+
        # employees and would otherwise search the rule table per employee (§5.5)
        Band = self.env['pb.young.worker.band']
        rule_cache = {}

        def band_for(emp, on_date):
            age = self._age(emp, on_date)
            if age is None:
                return Band
            co = emp.company_id or self.env.company
            if co.id not in rule_cache:
                rule_cache[co.id] = self._rule_for_company(co)
            rule = rule_cache[co.id]
            if not rule:
                return Band
            for b in rule.band_ids:
                if b.age_min <= age < b.age_max:
                    return b
            return Band

        minors = self.env['hr.employee']
        for emp in employees:
            if not self._birthday(emp):
                if include_no_birthday:
                    out.append({
                        'employee_id': emp.id, 'name': emp.name,
                        'kind': 'no_birthday', 'date': dt.isoformat(),
                        'detail': _("No birthday on file — cannot verify young-worker status."),
                    })
                continue
            # minor for any part of the period → run the detailed checks
            if band_for(emp, df) or band_for(emp, dt):
                minors |= emp
        if not minors:
            return out

        Att = self.env['hr.attendance'].sudo()
        # widest UTC window covering [df, dt] local for the whole cohort
        starts = [self._day_bounds_utc(e, df)[0] for e in minors]
        ends = [self._day_bounds_utc(e, dt)[1] for e in minors]
        win_start, win_end = min(starts), max(ends)

        atts = Att.search([
            ('employee_id', 'in', minors.ids),
            ('check_in', '>=', win_start), ('check_in', '<=', win_end),
        ])
        day_hours = defaultdict(float)   # (emp_id, date) -> hours
        week_hours = defaultdict(float)  # (emp_id, monday) -> hours
        for a in atts:
            emp = a.employee_id
            d = self._local_date(emp, a.check_in)
            if not (df <= d <= dt):
                continue
            h = self._att_hours(a)
            day_hours[(emp.id, d)] += h
            week_hours[(emp.id, d - timedelta(days=d.weekday()))] += h

        emp_by_id = {e.id: e for e in minors}
        for (eid, d), h in day_hours.items():
            band = band_for(emp_by_id[eid], d)
            if band and h > band.max_hours_day + self.DAILY_GRACE:
                out.append({
                    'employee_id': eid, 'name': emp_by_id[eid].name,
                    'kind': 'day_cap', 'date': d.isoformat(),
                    'detail': _("%(h).1fh on %(d)s exceeds the %(cap).0fh daily cap.",
                                h=h, d=d.isoformat(), cap=band.max_hours_day),
                })
        for (eid, wk), h in week_hours.items():
            band = band_for(emp_by_id[eid], wk)
            if band and h > band.max_hours_week:
                out.append({
                    'employee_id': eid, 'name': emp_by_id[eid].name,
                    'kind': 'week_cap', 'date': wk.isoformat(),
                    'detail': _("%(h).1fh in the week of %(wk)s exceeds the %(cap).0fh cap.",
                                h=h, wk=wk.isoformat(), cap=band.max_hours_week),
                })

        # OT attempts already on file for a banded worker (each is a breach)
        ot = self.env['hr.overtime.request'].sudo().search([
            ('employee_id', 'in', minors.ids),
            ('date', '>=', df), ('date', '<=', dt),
        ])
        for r in ot:
            band = band_for(r.employee_id, r.date)
            if band and band.ot_blocked:
                out.append({
                    'employee_id': r.employee_id.id, 'name': r.employee_id.name,
                    'kind': 'ot', 'date': r.date.isoformat(),
                    'detail': _("Overtime logged on %(d)s is not permitted under 18.",
                                d=r.date.isoformat()),
                })

        # night-blocked shift assignments overlapping the protected window
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', 'in', minors.ids),
            ('date', '>=', df), ('date', '<=', dt),
            ('state', '!=', 'cancelled'),
        ])
        for s in shifts:
            band = band_for(s.employee_id, s.date)
            if not (band and band.night_blocked):
                continue
            rule = rule_cache.get(s.employee_id.company_id.id) \
                or self._rule_for_company(s.employee_id.company_id)
            if rule and self._shift_hits_night(s.shift_template_id, rule.night_from, rule.night_to):
                out.append({
                    'employee_id': s.employee_id.id, 'name': s.employee_id.name,
                    'kind': 'night', 'date': s.date.isoformat(),
                    'detail': _("Night shift on %(d)s is not permitted under 18.",
                                d=s.date.isoformat()),
                })
        return out

    # ------------------------------------------------------------- night math
    @api.model
    def _shift_hits_night(self, template, night_from, night_to):
        """Does the template's local-hour window overlap the night window?

        Both windows may cross midnight; project onto a linear axis and test the
        night window at day offsets {-24, 0, +24} so a wrap on either side is
        caught. Uses template hours (wall-clock), not the UTC datetimes.
        """
        if not template:
            return False
        s = template.start_hour
        e = template.end_hour + (24.0 if template.is_overnight else 0.0)
        if e <= s:
            return False
        nlen = (night_to - night_from) if night_to > night_from else (night_to + 24.0 - night_from)
        if nlen <= 0:
            return False
        for k in (-24.0, 0.0, 24.0):
            ns = night_from + k
            ne = ns + nlen
            if s < ne and ns < e:   # half-open interval overlap
                return True
        return False
