# -*- coding: utf-8 -*-
"""A LIVING PRESENT for Mission Control (Workforce P6) — extends pb.demo.generator.

``ensure_workforce_demos`` (demo_workforce.py) builds the workforce STORY, but
every date it produces is derived from the day it last ran, so the demo world
freezes the moment nobody regenerates it. On 2026-08-18 the live apex database
had its newest demo punch on 2026-07-24: Mission Control opened on an empty
week, every tile read zero, and the Close board had nothing to close.

``ensure_workforce_current()`` is the answer to that, and it is deliberately a
SEPARATE entry point from ``ensure_workforce_demos``: it can be run on its own,
any number of times, without regenerating the world (no employees, no contracts,
no payslips — a 4 500-employee compute is not something a "refresh the present"
button may trigger).

WHAT IT GUARANTEES
------------------
* **TODAY-anchored.** Every date is derived from ``fields.Date.context_today``,
  never from a constant. A rerun a week later moves the whole window.
* **Idempotent.** Run twice, get the same world: every section keys on the
  natural identity of what it writes ((employee, day) for a shift or a punch,
  (employee, day, type) for overtime, (employee, date_from) for a trip) and
  skips what is already there. Nothing is ever created twice.
* **Self-healing.** A rerun CLOSES the open punches the previous run left on
  earlier days (§"today" seeds check-ins with no check-out on purpose), so a
  demo world that was refreshed a week ago does not accumulate a fortnight of
  people who never went home.
* **Demo-owned.** The cohort is ``hr.employee.is_demo`` employees of the demo
  company only. That is the module's established ownership model — attendance
  cascades on the employee, and ``clean_demo_employees`` unlinks shifts, trips,
  overtime, leaves and corrections BY ``employee_id`` — so nothing here needs a
  new ownership column and nothing here can reach a real employee's row.
* **Never destructive.** It only ever ADDS. It does not rewrite a shift, punch,
  leave or trip that already exists on a seeded day, because it cannot tell a
  previous run's row from an officer's — so it treats every existing row as the
  officer's. The exceptions are all cases where it CAN tell: the self-heal above
  (closing an open punch on a past day, which is what an officer would do
  anyway), advancing a settled published shift to ``completed``, and the grid
  provenance stamp below, which only ever touches a punch whose timestamps match
  the deterministic plan to the second — i.e. a row this seeder demonstrably
  wrote itself.

THE CALENDAR'S TIMEZONE (P7)
---------------------------
``_p6_tz`` pins Vietnam for everything this seeder writes, and W55 put the same
zone on the demo EMPLOYEES. Neither of those reaches the third place a Workforce
surface looks for a clock: ``hr.attendance.weekentry._emp_tz`` resolves the
working CALENDAR first (``emp.resource_calendar_id or
company.resource_calendar_id``), and only then the employee. The demo company's
calendar is Odoo's stock 40-hour one, which ships ``Europe/Brussels`` — so an
officer typing "8" into a Week Grid cell got a punch written at 08:00 Brussels,
which is 13:00 in Ho Chi Minh City. Every seeded row was in the right place and
every HAND-ENTERED one was five hours out. ``_p6_align_calendars`` stamps the
demo company's own calendars so the three clocks finally agree; a calendar the
demo company does not OWN is left alone even if a demo employee is on it, because
that row is shared with real companies (see the method).

UTC-DAY SAFETY (W51)
--------------------
Punches are seeded between 07:00 and 22:00 Vietnam local time, i.e. 00:00–15:00
UTC on the SAME calendar day. That is not a coincidence — it is the reason the
seeder never uses the night template. ``pb.close`` / ``pb.wf.lock`` /
``pb.attendance.exception.engine`` key a punch by the employee-LOCAL day while
``pb.today`` and the Week Grid key it by ``check_in.date()`` (UTC); inside that
window the two answers are identical, so every Workforce surface agrees about
which Tuesday it is looking at. A 05:58 or a 23:30 local punch would not.

YOUNG WORKERS
-------------
The two demo minors are IN the cohort (they are Retail employees like everyone
else and a demo where the under-18s vanish from the roster teaches the wrong
thing), but their days are cut to fit the VN bands with room to spare: the
17-year-old works 7.5 h/day (cap 8 h/day, 40 h/week → 37.5 h), the 14-year-old
3.5 h/day on four days (cap 4 h/day, 20 h/week → 14 h). Neither ever gets an
OPEN punch, because an open punch's hours are measured against *now* and would
sail past the daily cap by the afternoon. Their pre-existing over-cap violation
week (June, ``demo_employees._YW_DEMOS``) is far outside this window and is left
exactly as it is — it is a fixture the Guard cockpit demo depends on.
"""

import logging
from datetime import datetime, time, timedelta

from pytz import timezone, utc

from odoo import fields, models

_logger = logging.getLogger(__name__)

# The window. 14 days of settled past (two full weeks of Close-board material),
# today, and a week of forward roster so the Schedule lens looks planned-ahead.
_DAYS_BACK = 14
_DAYS_FWD = 7

# The demo world's country clock. Used for the seeded shift/punch wall times AND
# stamped onto the demo employees themselves — see `_p6_tz` (W55) and
# `_p6_align_timezones`, each of which cost this phase a live run to find.
_DEMO_TZ = 'Asia/Ho_Chi_Minh'

# The cohort. A union of two shapes on purpose:
#   * `_GLOBAL_TAKE` demo adults by NAME across the whole company, so the
#     UNFILTERED Week Grid / roster (which is `order='name', limit=200`) opens
#     with live rows at the top rather than 200 empty ones;
#   * `_DEPT_TAKE` by name inside each of four named cost centres, so a
#     department-scoped lens is dense rather than showing one person in twelve.
_GLOBAL_TAKE = 24
_DEPT_TAKE = 16
_DEPT_NAMES = ('Stores - North', 'Assembly Line A', 'Fleet - HCMC', 'Finance')

# The ONE department that enters its hours by hand (P7). Everything else in the
# demo world punches on a device, which is the truth for a factory and is also
# what makes the Week Grid's REG cells read-only there — `get_week_entries`
# offers an editable REG cell only when the day holds exactly one punch AND that
# punch carries `pb_entry_source='grid'` (attendance_weekentry.py:256). With no
# grid punch anywhere in the demo, the grid's whole keyboard story — type, Tab,
# fill-down, undo, the tray — could not be shown without first making an edit,
# and the first edit is the thing you are trying to demonstrate.
#
# Concentrated in one named department rather than sprinkled, for two reasons:
# a department filter then produces a screen that is entirely editable instead
# of a checkerboard, and the rest of the world keeps its honest device
# provenance for the Attendance-Control story.
_GRID_DEPT = 'Stores - North'
# How many OT chips that department carries across the settled + current week.
# Enough that the chip vocabulary (draft / submitted / approved, weekday /
# weekend, a bonus split) is all visible on one screen; few enough that the
# cells are still mostly hours.
_DEPT_OT_TAKE = 8

# Shift templates by code (hr.shift.template). NEVER the night template: see the
# UTC-day note in the module docstring, and minors may not be assigned it at all.
_TPL_DAY = 'AM'        # 08:00–17:00, 8 h net
_TPL_OFFICE = 'OFF'    # 08:30–17:30, 8 h net
_TPL_AFTERNOON = 'PM'  # 14:00–22:00, 7.5 h net

# The day flavours whose shift may be COMPLETED. Everything else stays
# `published` on purpose: `pb.attendance.exception.engine` only reads published
# shifts (W24) and derives late / early_leave / missing_punch from their stored
# compliance status, so completing a day that went wrong is the same thing as
# deleting the exception it raised.
_COMPLETABLE = ('on_time', 'grace', 'long', 'noshow_today')

# The two demo minors, by the names demo_employees.py owns them under.
_MINOR_17 = 'Demo Minor 17 (Young Worker)'
_MINOR_14 = 'Demo Minor 14 (Young Worker)'
# (daily hours, days per week) — comfortably inside the VN bands (8/40, 4/20).
_MINOR_SHAPE = {_MINOR_17: (7.5, 5), _MINOR_14: (3.5, 4)}

# Driver demo logins (§3.7). Passwordless like every other pb_demo login
# (C18.14); an admin sets a password at demo time. These exist so the Today
# board's map card has live pins WITHOUT waking the archived route-sim seed
# drivers, which are a different feature with a deliberate off switch.
_DRIVERS = [
    {'login': 'driver1.demo@payobook.com', 'name': 'Demo Driver (HCMC)',
     'dept': 'Fleet - HCMC', 'lat': 10.7769, 'lon': 106.7009},
    {'login': 'driver2.demo@payobook.com', 'name': 'Demo Driver (Hanoi)',
     'dept': 'Fleet - Hanoi', 'lat': 21.0278, 'lon': 105.8342},
]


class PbDemoGenerator(models.TransientModel):
    _inherit = 'pb.demo.generator'

    # ================================================================= entry
    def ensure_workforce_current(self):
        """Refresh the demo world's PRESENT. Idempotent, today-anchored.

        Returns a dict of per-section counts (what was created this run), which
        is what the tests assert on and what a live run is reported from.
        """
        self = self.with_context(**self._GEN_CTX)
        out = {'cohort': 0, 'timezones': 0, 'calendars': 0, 'healed': 0,
               'shifts': 0, 'drafts': 0, 'completed': 0, 'punches': 0,
               'open_today': 0, 'grid_punches': 0, 'overtime': 0,
               'dept_overtime': 0, 'leaves': 0, 'trips': 0, 'corrections': 0,
               'drivers': 0}

        company = self.get_group_company()
        if not company:
            _logger.warning('pb_demo P6: no demo company; nothing to refresh')
            return out

        tz = self._p6_tz(company)
        today = fields.Date.context_today(self)
        start = today - timedelta(days=_DAYS_BACK)
        end = today + timedelta(days=_DAYS_FWD)

        cohort = self._p6_cohort(company)
        if not cohort:
            _logger.warning('pb_demo P6: no demo employees; nothing to refresh')
            return out
        out['cohort'] = len(cohort)

        # Days the cohort is legitimately away — computed BEFORE the punch
        # section so a person on approved leave or an approved trip does not
        # also clock in. (`pb.close` treats both as the explanation for an empty
        # day; a punch on top of one is a contradiction, not a demo.)
        excused = self._p6_plan_excused(cohort, today)

        # The whole window, decided ONCE and in pure Python: what each person
        # works and what they punched. Both the shift section and the punch
        # section read it, so a shift's `actual_*` and the punch it describes
        # can never tell two different stories.
        specs = self._p6_specs(cohort, tz, today, start, end, excused)

        # Each section in its own savepoint: one refusal (a young-worker cap, a
        # trip overlap, a leave-validation quirk) must never abort the rest.
        # The InFailedSqlTransaction lesson — see demo_timeoff.ensure_timeoff_demos.
        self._p6_section(out, 'timezones', self._p6_align_timezones, company)
        self._p6_section(out, 'calendars', self._p6_align_calendars, company)
        self._p6_section(out, 'self-heal', self._p6_heal_open_punches,
                         cohort, tz, specs, today, start)
        self._p6_section(out, 'shifts', self._p6_seed_shifts,
                         cohort, company, specs, today, start, end)
        self._p6_section(out, 'punches', self._p6_seed_punches,
                         cohort, tz, specs, today, start)
        # After the punches exist: the stamp identifies a row this seeder wrote
        # by matching the plan to the second, so it has to run once the plan has
        # been realised.
        self._p6_section(out, 'grid punches', self._p6_mark_grid_punches,
                         cohort, company, tz, specs, today, start)
        self._p6_section(out, 'overtime', self._p6_seed_overtime,
                         cohort, company, today)
        self._p6_section(out, 'dept overtime', self._p6_seed_dept_overtime,
                         cohort, company, specs, today, excused)
        self._p6_section(out, 'leave', self._p6_seed_leave,
                         cohort, company, today)
        self._p6_section(out, 'trips', self._p6_seed_trips,
                         cohort, company, today)
        self._p6_section(out, 'corrections', self._p6_seed_correction,
                         cohort, company, tz, specs, today)
        self._p6_section(out, 'drivers', self._p6_seed_drivers,
                         company, tz, today)

        _logger.info('pb_demo P6: workforce present refreshed %s → %s: %s',
                     start, end, out)
        return out

    def _p6_section(self, out, label, fn, *args):
        """Run one section inside its own savepoint, folding its counts into
        `out`. A failure is logged and skipped — never raised (§5: the seeder
        must never raise on rerun)."""
        try:
            with self.env.cr.savepoint():
                counts = fn(*args) or {}
                for k, v in counts.items():
                    out[k] = out.get(k, 0) + v
        except Exception as e:   # pragma: no cover - defensive by design
            _logger.warning('pb_demo P6: section %s skipped: %s', label, e,
                            exc_info=True)

    # ================================================================ cohort
    def _p6_cohort(self, company):
        """The seeded population, ordered by name and de-duplicated.

        Order matters: every Workforce roster reads `order='name'` with a 200-row
        cap, so a cohort taken in name order lands where the officer is looking.
        """
        Employee = self.env['hr.employee'].sudo()
        base = [('is_demo', '=', True), ('company_id', '=', company.id),
                ('active', '=', True)]
        picked = Employee.browse()

        # (a) the alphabetical head of the whole demo company
        picked |= Employee.search(base, order='name', limit=_GLOBAL_TAKE)

        # (b) the alphabetical head of each named cost centre
        Dept = self.env['hr.department'].sudo()
        for dname in _DEPT_NAMES:
            dept = Dept.search([('name', '=', dname),
                                ('company_id', '=', company.id)], limit=1)
            if not dept:
                continue
            picked |= Employee.search(
                base + [('department_id', '=', dept.id)],
                order='name', limit=_DEPT_TAKE)

        # (c) the two minors, always — a roster the under-18s are missing from
        # teaches the wrong lesson about this product.
        for name in (_MINOR_17, _MINOR_14):
            picked |= Employee.search(base + [('name', '=', name)], limit=1)

        # single stable order for every deterministic index below
        return picked.sorted(key=lambda e: (e.name or '', e.id))

    # ============================================================== helpers
    def _p6_tz(self, company):
        """The demo world's wall clock. VIETNAM, and deliberately NOT the
        working calendar's tz.

        Found live, and it cost this seeder a whole run. The demo company's
        `resource.calendar` is Odoo's stock "Standard 40 hours/week", which
        carries `tz = Europe/Brussels` — nobody ever set it, because nothing in
        payroll reads it. Deriving the demo's wall clock from it (which is what
        `demo_workforce.py` does) puts an "08:00" Vietnamese shift at 06:00 UTC,
        i.e. 13:00 in Ho Chi Minh City, and it puts the afternoon shift's end at
        03:00 the NEXT morning local — straight through the midnight the
        Workforce surfaces key their days on (W51).

        The visible symptom was worse than the cosmetics: at 08:56 in Vietnam
        the working day had not started yet in Brussels, so the Today board's
        live population came out EMPTY on a run whose entire purpose was to
        fill it. A demo world whose clock is seven hours behind its own country
        is alive only in the afternoon.

        Pinned rather than looked up: this generator builds one country
        (`demo_catalog.GROUP_COMPANY_NAME` is "Payobook Vietnam JSC"), the two
        sibling seeders already fall back to this same zone, and a wrong tz here
        is silent in every test that does not know what time it should be.
        """
        return timezone(_DEMO_TZ)

    def _p6_utc(self, tz, d, hour):
        """Naive-UTC datetime for local wall-clock `hour` (8.5 → 08:30) on `d`."""
        h = int(hour)
        m = int(round((hour - h) * 60))
        return tz.localize(datetime.combine(d, time(h, m))).astimezone(
            utc).replace(tzinfo=None)

    def _p6_day_bounds(self, tz, d):
        """(start, end) naive-UTC bounds of the LOCAL day `d`."""
        return (self._p6_utc(tz, d, 0.0),
                tz.localize(datetime.combine(d, time(23, 59, 59))).astimezone(
                    utc).replace(tzinfo=None))

    def _p6_templates(self):
        Tpl = self.env['hr.shift.template'].sudo()
        out = {}
        for code in (_TPL_DAY, _TPL_OFFICE, _TPL_AFTERNOON):
            out[code] = Tpl.search([('code', '=', code),
                                    ('active', '=', True)], limit=1)
        fallback = out.get(_TPL_DAY) or Tpl.search(
            [('active', '=', True)], order='sequence', limit=1)
        for code in list(out):
            if not out[code]:
                out[code] = fallback
        return out

    def _p6_template_code(self, idx, emp):
        """Which template this person works. Deterministic, and never night."""
        if emp.name in _MINOR_SHAPE:
            return _TPL_DAY
        dept = emp.department_id.name or ''
        if dept in ('Finance',):
            return _TPL_OFFICE
        if idx % 9 == 4:                 # a visible afternoon crew
            return _TPL_AFTERNOON
        return _TPL_DAY

    def _p6_works(self, idx, emp, d):
        """Does this person have a shift on `d`? Sundays never; Saturdays for a
        quarter of the cohort; minors only on their reduced week."""
        wd = d.weekday()
        if wd == 6:
            return False
        shape = _MINOR_SHAPE.get(emp.name)
        if shape:
            return wd < shape[1]         # first N weekdays of the week
        if wd == 5:
            return idx % 4 == 0
        return True

    def _p6_shape(self, idx, d):
        """The day's flavour — a deterministic 25-slot wheel, so a rerun
        reproduces exactly the same world and the mix stays realistic:
        ~4% absent, ~4% late beyond grace, ~8% late inside it, ~4% early
        leave, ~4% a long day, the rest on time."""
        v = (idx * 7 + d.toordinal() * 3) % 25
        if v == 24:
            return ('absent', 0.0, 0.0)
        if v == 23:
            return ('late', 28.0, 0.0)          # grace is 15 min → a real flag
        if v in (21, 22):
            return ('grace', 9.0, 0.0)          # late, but forgiven
        if v == 20:
            return ('early', 0.0, -50.0)
        if v == 19:
            return ('long', 0.0, 120.0)
        if v == 18:
            return ('noshow_today', 0.0, 0.0)   # today only: simply not in yet
        return ('on_time', float(-6 + (v % 5) * 2), 0.0)

    def _p6_window(self, tpl, emp):
        """(start_hour, end_hour) in LOCAL hours — the template's NET duration,
        never its `end_hour`.

        `hr.shift.template.duration` is the paid time, `end_hour − start_hour`
        includes the unpaid break: the AM template runs 08:00–17:00 and is worth
        8 h. Building the shift (and the punch that matches it) from `end_hour`
        makes every single day a +1.0 h overshoot, which is inside the per-punch
        variance and OUTSIDE the weekly one — so the Close board fills with one
        "Week outside tolerance" row per person and buries the days that really
        do need attention (W54's failure mode, arrived at from the data side).
        Observed live before this was fixed: a wall of +1.0 rows across the
        whole cohort. `demo_workforce.py` already punched 08:00–16:00 for the
        same reason; this makes the shift agree with it.
        """
        start = tpl.start_hour or 8.0
        shape = _MINOR_SHAPE.get(emp.name)
        if shape:
            return (start, start + shape[0])
        return (start, start + (tpl.duration or 8.0))

    # ========================================================== the day plan
    def _p6_specs(self, cohort, tz, today, start, end, excused):
        """{(employee_id, date): spec} for the whole window.

        A spec is ``{'tpl', 'start', 'end', 'ci', 'co', 'draft', 'past'}`` where
        `ci`/`co` are the intended punch (both False = no punch that day, `co`
        False with a `ci` = a deliberately open one). Pure computation: no
        query, no write, no randomness — which is what makes the whole seeder
        reproducible and its tests cheap.
        """
        tpls = self._p6_templates()
        now = fields.Datetime.now()
        # The two most recent settled workdays carry the deliberate missing
        # check-outs (Time·Exceptions + the Close board's `missing_checkout`).
        recent = []
        d = today - timedelta(days=1)
        while len(recent) < 2 and d >= start:
            if d.weekday() < 5:
                recent.append(d)
            d -= timedelta(days=1)
        adults = [e for e in cohort if e.name not in _MINOR_SHAPE]
        no_out = set()
        if adults and recent:
            no_out.add((adults[3 % len(adults)].id, recent[0]))
            no_out.add((adults[11 % len(adults)].id, recent[0]))
            if len(recent) > 1:
                no_out.add((adults[7 % len(adults)].id, recent[1]))

        specs = {}
        for idx, emp in enumerate(cohort):
            tpl = tpls[self._p6_template_code(idx, emp)]
            if not tpl:
                continue
            is_minor = emp.name in _MINOR_SHAPE
            away = excused.get(emp.id, ())
            d = start
            while d <= end:
                if not self._p6_works(idx, emp, d):
                    d += timedelta(days=1)
                    continue
                sh, eh = self._p6_window(tpl, emp)
                s_dt = self._p6_utc(tz, d, sh)
                e_dt = self._p6_utc(tz, d, eh)
                spec = {
                    'tpl': tpl, 'start': s_dt, 'end': e_dt,
                    'ci': False, 'co': False, 'past': d < today, 'kind': '',
                    # an APPROVED absence, not a missing punch — the difference
                    # matters to the correction picker below
                    'excused': d.isoformat() in away,
                    # a slice of next week stays DRAFT so the publish flow has
                    # something to publish (§3.1)
                    'draft': d > today + timedelta(days=3) and idx % 7 == 2,
                }
                if d <= today and d.isoformat() not in away:
                    kind, in_off, out_off = self._p6_shape(idx, d)
                    spec['kind'] = kind
                    if is_minor and kind != 'absent':
                        spec['kind'] = 'on_time'
                        # A minor's day is never bent: no late arrival, no long
                        # evening, no open punch. The VN daily cap is a HARD
                        # constraint that fires under sudo, and an open punch is
                        # measured against `now`.
                        kind, in_off, out_off = ('on_time', 0.0, 0.0)
                    if kind != 'absent':
                        if d == today:
                            if not (kind == 'noshow_today' or is_minor):
                                ci = s_dt + timedelta(minutes=in_off)
                                if ci <= now - timedelta(minutes=5):
                                    spec['ci'] = ci      # OPEN — on shift now
                        else:
                            ci = s_dt + timedelta(minutes=in_off)
                            co = e_dt + timedelta(minutes=out_off)
                            if co <= ci:
                                co = ci + timedelta(hours=1)
                            spec['ci'] = ci
                            spec['co'] = False if (emp.id, d) in no_out else co
                specs[(emp.id, d)] = spec
                d += timedelta(days=1)
        return specs

    def _p6_bulk_create(self, Model, vals_list, label):
        """Create `vals_list` in one shot; on a refusal, fall back to row-by-row
        so a single bad row costs one row and not the batch."""
        if not vals_list:
            return Model.browse()
        try:
            with self.env.cr.savepoint():
                return Model.create(vals_list)
        except Exception as e:
            _logger.warning('pb_demo P6: %s batch refused (%s) — retrying '
                            'row by row', label, e)
        made = Model.browse()
        for vals in vals_list:
            try:
                with self.env.cr.savepoint():
                    made |= Model.create(vals)
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo P6: %s row skipped: %s', label, e)
        return made

    # ============================================================ timezones
    def _p6_align_timezones(self, company):
        """Give the demo employees the timezone of the country they work in.

        Found live, one lens after W55's calendar bug: with the roster correctly
        seeded at 08:00 Vietnam time, the Today board rendered
        "Morning Shift · 03:00–11:00". `pb.today._tzinfo` resolves an employee's
        clock as ``emp.tz or self.env.user.tz or UTC`` — and a demo employee has
        NO tz, because `demo_employees.generate_employees` never set one — so
        every time on every Workforce surface was being printed in whatever zone
        the person LOOKING at the demo happens to sit in. A Vietnamese factory
        whose morning shift starts at three in the morning is not a demo.

        The same field is what `pb.close`, `pb.wf.lock` and the exception engine
        key their employee-LOCAL day on (W51), so setting it also makes the day
        they mean identical to the day this seeder wrote — which is the whole
        point of the 07:00–22:00 band in the module docstring.

        This OVERWRITES rather than fills a blank, and the live data is why: the
        first version only touched employees with no tz and changed exactly
        nothing, because `hr.employee.tz` is `resource_resource.tz` and Odoo
        seeds it from whoever ran the create. On the apex database that is
        **Europe/Brussels for 4 500 demo employees and Australia/Sydney for the
        two demo minors** — nobody chose either, and neither is a decision worth
        preserving in a company called Payobook Vietnam JSC. Scoped to
        `is_demo` employees of the demo company, which pb_demo owns outright.
        """
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        wrong = Employee.search([
            ('is_demo', '=', True), ('company_id', '=', company.id),
            ('tz', '!=', _DEMO_TZ),
        ])
        if not wrong:
            return {}
        wrong.write({'tz': _DEMO_TZ})
        _logger.info('pb_demo P6: set the VN timezone on %s demo employees.',
                     len(wrong))
        return {'timezones': len(wrong)}

    def _p6_align_calendars(self, company):
        """Give the demo company's WORKING CALENDARS the country's timezone.

        The third clock, and the last one still set to Belgium. W55 fixed the
        seeder's own wall time and P6 fixed the employees', but
        ``hr.attendance.weekentry._emp_tz`` (attendance_weekentry.py:70) reads
        the working CALENDAR first and the employee only as a fallback:

            cal = emp.resource_calendar_id or emp.company_id.resource_calendar_id
            name = (cal.tz or emp.tz or self.env.user.tz or 'UTC')

        So the field this seeder so carefully set was never consulted by the one
        surface that WRITES punches. `_save_reg` builds a check-in from the
        cell's hours in that zone, which means an officer typing "8" into a
        Vietnamese demo produced a punch at 08:00 Brussels = 13:00 local — a row
        that then failed the seeder's own UTC-day rule (W51) and read as an
        afternoon shift on every board. The bug is invisible in every fixture
        suite, because a fixture calendar is whatever the test made it.

        SCOPE, and why it is narrower than it looks. Only calendars the demo
        company OWNS (`company_id == company`) are stamped. A calendar with no
        company is GLOBAL — Odoo ships several — and a demo employee sitting on
        one would make "fix the demo world" quietly rewrite the working hours of
        every real company on the database. If that is ever the case here, it is
        logged and skipped rather than followed: pb_demo owns demo rows, not the
        rows they happen to point at.
        """
        Cal = self.env['resource.calendar'].sudo().with_context(active_test=False)
        mine = Cal.search([('company_id', '=', company.id)])
        wrong = mine.filtered(lambda c: c.tz != _DEMO_TZ)

        # Loud about the case the scope rule refuses to handle silently.
        foreign = self.env['hr.employee'].sudo().with_context(
            active_test=False).search([
                ('is_demo', '=', True), ('company_id', '=', company.id),
                ('resource_calendar_id', '!=', False),
                ('resource_calendar_id', 'not in', mine.ids),
            ])
        if foreign:
            _logger.warning(
                'pb_demo P7: %s demo employees work a calendar the demo company '
                'does not own (%s) — left alone, it is shared with real '
                'companies. Their Week Grid cells will still resolve a foreign '
                'timezone.', len(foreign),
                ', '.join(sorted(set(foreign.mapped(
                    'resource_calendar_id.display_name')))))
        if not wrong:
            return {}
        wrong.write({'tz': _DEMO_TZ})
        _logger.info('pb_demo P7: set the VN timezone on %s demo calendars (%s).',
                     len(wrong), ', '.join(wrong.mapped('display_name')))
        return {'calendars': len(wrong)}

    # ============================================================ self-heal
    def _p6_heal_open_punches(self, cohort, tz, specs, today, start):
        """Close the open check-ins a PREVIOUS run left on earlier days.

        The today section deliberately seeds check-ins with no check-out (the
        board has to show a live "on shift now" population). Tomorrow those are
        stale, and a fortnight of them would make every person in the demo look
        like they never went home. A rerun closes them at their shift's end
        (else eight hours after the punch), which is exactly the correction an
        officer would file.

        The two or three CURRENT missing check-outs are exempt: they are the
        material Time·Exceptions and the Close board's `missing_checkout` flag
        are made of, and the plan says so (`spec['ci']` with no `spec['co']`).
        As the window rolls forward they stop being planned and the next rerun
        closes them, so the demo's open exceptions stay at the front.
        """
        Att = self.env['hr.attendance'].sudo()
        day_start, _e = self._p6_day_bounds(tz, today)
        floor, _f = self._p6_day_bounds(tz, start - timedelta(days=7))
        stale = Att.search([
            ('employee_id', 'in', cohort.ids),
            ('check_out', '=', False),
            ('check_in', '<', day_start),
            ('check_in', '>=', floor),
        ])
        healed = 0
        for att in stale:
            local_day = utc.localize(att.check_in).astimezone(tz).date()
            planned = specs.get((att.employee_id.id, local_day))
            if planned and planned['ci'] and not planned['co']:
                continue
            shift = self.env['hr.shift.planning'].sudo().search(
                [('employee_id', '=', att.employee_id.id),
                 ('date', '=', att.check_in.date())], limit=1)
            end_dt = shift.end_datetime if shift else False
            if not end_dt or end_dt <= att.check_in:
                end_dt = att.check_in + timedelta(hours=8)
            try:
                with self.env.cr.savepoint():
                    att.write({'check_out': end_dt})
                    healed += 1
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo P6: could not close punch %s: %s',
                                att.id, e)
        return {'healed': healed}

    # =============================================================== shifts
    def _p6_seed_shifts(self, cohort, company, specs, today, start, end):
        """The roster across the whole window, plus a handful of drafts.

        A PAST day that went to plan is created already `completed` with its
        punch linked; a day that went wrong (nobody came, nobody clocked out)
        stays `published` on purpose — the exception engine only reads published
        rows (W24), so completing a broken day would empty the Exceptions queue
        of everything except absences. Today and the forward roster are
        `published`, except the deliberate draft slice.
        """
        Shift = self.env['hr.shift.planning'].sudo()

        # existing (employee, day) pairs — one query, not one per cell. An
        # existing row is somebody else's (an officer's, or a previous run's)
        # and is never rewritten.
        existing = set()
        for row in Shift.search_read(
                [('employee_id', 'in', cohort.ids),
                 ('date', '>=', start), ('date', '<=', end)],
                ['employee_id', 'date']):
            existing.add((row['employee_id'][0], row['date']))

        buckets = {'draft': [], 'published': [], 'completed': []}
        for (eid, d), spec in specs.items():
            if (eid, d) in existing:
                continue
            vals = {
                'employee_id': eid,
                'shift_template_id': spec['tpl'].id,
                'date': d,
                'start_datetime': spec['start'],
                'end_datetime': spec['end'],
                'company_id': company.id,
            }
            if spec['past'] and spec['ci']:
                vals['actual_check_in'] = spec['ci']
                if spec['co']:
                    vals['actual_check_out'] = spec['co']
            if spec['draft']:
                buckets['draft'].append(vals)
            elif (spec['past'] and spec['ci'] and spec['co']
                  and spec['kind'] in _COMPLETABLE):
                buckets['completed'].append(vals)
            else:
                buckets['published'].append(vals)

        drafts = self._p6_bulk_create(Shift, buckets['draft'], 'draft shift')
        pubs = self._p6_bulk_create(Shift, buckets['published'], 'shift')
        done = self._p6_bulk_create(Shift, buckets['completed'], 'settled shift')
        (pubs | done).action_publish()
        done.action_complete()
        return {'shifts': len(pubs) + len(done), 'drafts': len(drafts),
                'completed': len(done)}

    def _p6_settle_shifts(self, cohort, specs, today, start):
        """Advance an already-existing published shift to `completed` when the
        day did go to plan. This is the rerun path: a shift seeded as FUTURE by
        an earlier run has no `actual_*` and is still published when its day
        finally settles.

        Only a day the plan calls uneventful is completed — see `_COMPLETABLE`.
        """
        Shift = self.env['hr.shift.planning'].sudo()
        pubs = Shift.search([
            ('employee_id', 'in', cohort.ids),
            ('date', '>=', start), ('date', '<', today),
            ('state', '=', 'published'),
            ('actual_check_in', '!=', False),
            ('actual_check_out', '!=', False),
        ]).filtered(lambda s: (specs.get((s.employee_id.id, s.date)) or {})
                    .get('kind') in _COMPLETABLE)
        if not pubs:
            return 0
        try:
            with self.env.cr.savepoint():
                pubs.action_complete()
                return len(pubs)
        except Exception as e:   # pragma: no cover
            _logger.warning('pb_demo P6: settling %s shifts failed: %s',
                            len(pubs), e)
            return 0

    # =============================================================== punches
    def _p6_seed_punches(self, cohort, tz, specs, today, start):
        """One punch per worked day — never two, so the Weekly-Entry cell stays
        editable (pb_hr_workforce safety rail 2) — and an OPEN check-in for most
        of the cohort today, which is what makes the board look live."""
        Att = self.env['hr.attendance'].sudo()
        Shift = self.env['hr.shift.planning'].sudo()

        # existing punches keyed by (employee, LOCAL day) — one query
        lo, _x = self._p6_day_bounds(tz, start)
        _y, hi = self._p6_day_bounds(tz, today)
        taken = set()
        # Core `hr.attendance` refuses a new punch while the employee's previous
        # one is still open ("hasn't checked out since …"), and the seeder leaves
        # two or three open ON PURPOSE. Those people therefore cannot clock in
        # today — which is not a bug to work around but the correct story: a
        # person whose Friday punch was never closed shows up as an open
        # exception, not as somebody who quietly started a new day.
        still_open = set()
        for a in Att.search([('employee_id', 'in', cohort.ids),
                             ('check_in', '>=', lo), ('check_in', '<=', hi)]):
            taken.add((a.employee_id.id,
                       utc.localize(a.check_in).astimezone(tz).date()))
            if not a.check_out:
                still_open.add(a.employee_id.id)
        for (eid, d), spec in specs.items():
            if d < today and spec['ci'] and not spec['co']:
                still_open.add(eid)

        vals_list = []
        for (eid, d), spec in specs.items():
            if d > today or not spec['ci'] or (eid, d) in taken:
                continue
            if d == today and eid in still_open:
                continue
            vals_list.append({'employee_id': eid, 'check_in': spec['ci'],
                              'check_out': spec['co'] or False})
        made = self._p6_bulk_create(Att, vals_list, 'punch')
        # Counted from what LANDED, never from what was intended.
        open_today = len(made.filtered(
            lambda a: not a.check_out
            and utc.localize(a.check_in).astimezone(tz).date() == today))

        # Link the punch to a shift that pre-dates this run and therefore has no
        # `actual_*` of its own (the rerun path — a fresh run set them at create).
        gaps = Shift.search([
            ('employee_id', 'in', cohort.ids),
            ('date', '>=', start), ('date', '<=', today),
            ('state', 'in', ('published', 'completed')),
            ('actual_check_in', '=', False),
        ])
        for s in gaps:
            spec = specs.get((s.employee_id.id, s.date))
            if not (spec and spec['ci']):
                continue
            upd = {'actual_check_in': spec['ci']}
            if spec['co']:
                upd['actual_check_out'] = spec['co']
            try:
                with self.env.cr.savepoint():
                    s.write(upd)
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo P6: linking shift %s failed: %s', s.id, e)

        settled = self._p6_settle_shifts(cohort, specs, today, start)
        return {'punches': len(made), 'open_today': open_today,
                'completed': settled}

    # ========================================================= grid provenance
    def _p6_dept_slice(self, cohort, company, dept_name):
        """The demo employees of one named cost centre, in the cohort's own
        stable order. Adults only — a minor's hours are a hard constraint, not a
        demo surface, and neither the grid slice nor the OT desk may bend them.
        """
        dept = self.env['hr.department'].sudo().search(
            [('name', '=', dept_name), ('company_id', '=', company.id)], limit=1)
        if not dept:
            return []
        return [e for e in cohort
                if e.department_id == dept and e.name not in _MINOR_SHAPE]

    def _p6_mark_grid_punches(self, cohort, company, tz, specs, today, start):
        """Make ONE department's week editable in the Week Grid.

        `get_week_entries` unlocks a REG cell only for a day holding exactly one
        punch whose `pb_entry_source` is `'grid'`; a blank source means a device
        punch, and the grid refuses to edit those on purpose (safety rail 2 —
        the device is the system of record and the correction flow is where you
        argue with it). Every punch this seeder writes is a device punch, which
        is correct and which also left the grid's entire keyboard story
        undemonstrable on a fresh demo.

        WHY THIS MAY REWRITE A ROW when §"never destructive" says it may not.
        The rule exists because the seeder cannot normally tell its own row from
        an officer's. Here it can, exactly: the plan (`_p6_specs`) is pure and
        deterministic, so a punch is one this seeder wrote if and only if its
        check-in and check-out equal the planned ones TO THE SECOND. Anything
        else — an officer's correction, an imported row, a punch somebody moved
        by a minute — fails the match and is left alone. The write itself
        changes provenance only; no time, no employee, no day moves.
        """
        people = self._p6_dept_slice(cohort, company, _GRID_DEPT)
        if not people:
            _logger.info('pb_demo P7: no "%s" department — no grid slice',
                         _GRID_DEPT)
            return {}
        ids = [e.id for e in people]
        Att = self.env['hr.attendance'].sudo()
        lo, _x = self._p6_day_bounds(tz, start)
        _y, hi = self._p6_day_bounds(tz, today)

        by_day = {}
        for a in Att.search([('employee_id', 'in', ids),
                             ('check_in', '>=', lo), ('check_in', '<=', hi)]):
            key = (a.employee_id.id,
                   utc.localize(a.check_in).astimezone(tz).date())
            by_day.setdefault(key, []).append(a)

        todo = Att.browse()
        for key, atts in by_day.items():
            # two punches on a day are not editable in the grid whatever their
            # source, so stamping them would promise an edit the cell refuses
            if len(atts) != 1:
                continue
            att = atts[0]
            spec = specs.get(key)
            if not spec or not spec['ci'] or not spec['co']:
                continue
            if att.pb_entry_source == 'grid':
                continue
            if att.check_in != spec['ci'] or att.check_out != spec['co']:
                continue          # somebody else's row, or somebody edited ours
            todo |= att
        if not todo:
            return {}
        todo.write({'pb_entry_source': 'grid'})
        _logger.info('pb_demo P7: %s punches in %s are now grid-entered.',
                     len(todo), _GRID_DEPT)
        return {'grid_punches': len(todo)}

    # ============================================================== overtime
    def _p6_seed_overtime(self, cohort, company, today):
        """A small, deliberately-shaped overtime desk.

        Two of the SUBMITTED rows are CLEAN by `pb.team._ot_clean_map`'s
        definition — planned == actual, ceiling headroom, day not locked — so
        the dock's "Approve all N clean" batch has something honest to offer,
        and one is deliberately NOT (a human edited the hours after entry),
        which is the whole reason the batch counts rather than sweeping.
        """
        if 'hr.overtime.request' not in self.env:
            return {}
        OT = self.env['hr.overtime.request'].sudo()
        adults = [e for e in cohort if e.name not in _MINOR_SHAPE]
        if len(adults) < 30:
            return {}

        last_sat = today - timedelta(days=(today.weekday() + 2) % 7 or 7)
        # (employee, date, type, planned, actual, target state)
        plan = [
            (adults[20], self._recent_weekday(today - timedelta(days=3)),
             'weekday', 3.0, 3.0, 'submitted'),      # CLEAN
            (adults[21], self._recent_weekday(today - timedelta(days=4)),
             'weekday', 2.5, 2.5, 'submitted'),      # CLEAN
            (adults[22], self._recent_weekday(today - timedelta(days=2)),
             'weekday', 4.0, 3.0, 'submitted'),      # edited after entry
            (adults[23], self._recent_weekday(today - timedelta(days=8)),
             'weekday', 3.0, 3.0, 'approved'),
            (adults[24], last_sat, 'weekend', 5.0, 5.0, 'approved'),
            (adults[25], self._recent_weekday(today - timedelta(days=1)),
             'weekday', 2.0, 2.0, 'draft'),
        ]
        made = 0
        for emp, d, otype, planned, actual, target in plan:
            if OT.search_count([('employee_id', '=', emp.id), ('date', '=', d),
                                ('overtime_type', '=', otype)]):
                continue
            try:
                with self.env.cr.savepoint():
                    r = OT.create({
                        'employee_id': emp.id, 'company_id': company.id,
                        'date': d, 'overtime_type': otype,
                        'planned_hours': planned, 'actual_hours': actual,
                        'reason': 'Delivery push (demo)',
                    })
                    if target in ('submitted', 'approved'):
                        r.action_submit()
                    if target == 'approved':
                        r.action_approve()
                    made += 1
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo P6: OT %s/%s skipped: %s', emp.name, d, e)
        return {'overtime': made}

    def _p6_seed_dept_overtime(self, cohort, company, specs, today, excused):
        """A DENSE overtime week for the one department the grid can edit.

        `_p6_seed_overtime` above shapes the OT DESK — six requests chosen so
        the dock's "approve all N clean" batch has honest material. They are
        spread across the whole company by design, which means the Week Grid,
        filtered to any one department, shows at most one chip and usually none.
        A grid whose chip vocabulary (draft / submitted / approved, weekday /
        weekend, the hours themselves) can only be seen by first entering some
        overtime is a grid that cannot be demonstrated read-only.

        So the same department that got the editable REG cells also carries
        `_DEPT_OT_TAKE` chips, across the SETTLED week and the CURRENT one — the
        two weeks an officer actually opens. Every one of them sits on a day the
        person really worked (there is a shift and a punch): an OT claim on an
        empty day is an anomaly, and seeding anomalies to make a screen look
        busy is how a demo teaches the wrong reflex.

        Mostly `approved` and `draft` on purpose. A `submitted` row is an
        `ot_pending` flag on the Close board, and this method exists to fill a
        grid, not to inflate somebody else's queue — exactly one is submitted so
        the state's dot is on screen.
        """
        if 'hr.overtime.request' not in self.env:
            return {}
        people = self._p6_dept_slice(cohort, company, _GRID_DEPT)
        if not people:
            return {}
        OT = self.env['hr.overtime.request'].sudo()

        monday = today - timedelta(days=today.weekday())
        last_monday = monday - timedelta(days=7)
        # settled week first — a chip on a closed-looking week is the one that
        # proves the grid reads history, not just this morning
        candidates = [last_monday + timedelta(days=i) for i in range(6)]
        candidates += [monday + timedelta(days=i) for i in range(6)
                       if monday + timedelta(days=i) <= today]

        # hours and state wheels: deterministic, and both prime-ish against the
        # number of people so the mix does not stripe by row
        hours_wheel = (2.0, 1.5, 3.0, 2.5, 2.0, 1.5, 3.0)
        state_wheel = ('approved', 'draft', 'approved', 'submitted',
                       'approved', 'draft', 'approved', 'draft')

        # `filled` counts SLOTS (including ones a previous run filled) so the
        # target is reached once and not re-reached every week; `created` counts
        # only what THIS run wrote, which is what the idempotency test reads and
        # what every other section here reports.
        filled = created = 0
        used = set()
        for i, emp in enumerate(people):
            if filled >= _DEPT_OT_TAKE:
                break
            away = excused.get(emp.id, ())
            day = None
            for j in range(len(candidates)):
                d = candidates[(i * 3 + j) % len(candidates)]
                if (emp.id, d) in used or d.isoformat() in away:
                    continue
                spec = specs.get((emp.id, d))
                # a day with a shift AND a completed punch — the only kind an
                # overtime claim can honestly sit on
                if not spec or not spec['ci'] or not spec['co']:
                    continue
                day = d
                break
            if not day:
                continue
            otype = 'weekend' if day.weekday() >= 5 else 'weekday'
            if OT.search_count([('employee_id', '=', emp.id), ('date', '=', day),
                                ('overtime_type', '=', otype)]):
                used.add((emp.id, day))
                filled += 1        # already there: this slot is filled
                continue
            hrs = hours_wheel[i % len(hours_wheel)]
            target = state_wheel[i % len(state_wheel)]
            try:
                with self.env.cr.savepoint():
                    r = OT.create({
                        'employee_id': emp.id, 'company_id': company.id,
                        'date': day, 'overtime_type': otype,
                        'planned_hours': hrs, 'actual_hours': hrs,
                        'reason': 'Stock take (demo)',
                    })
                    if target in ('submitted', 'approved'):
                        r.action_submit()
                    if target == 'approved':
                        r.action_approve()
                    used.add((emp.id, day))
                    filled += 1
                    created += 1
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo P7: dept OT %s/%s skipped: %s',
                                emp.name, day, e)
        if created:
            _logger.info('pb_demo P7: %s new overtime chips in %s (%s slots '
                         'filled).', created, _GRID_DEPT, filled)
        return {'dept_overtime': created}

    # ================================================================= leave
    def _p6_plan_excused(self, cohort, today):
        """{employee_id: {iso, …}} — the days the seeder intends to be AWAY.

        Computed before anything is written so the punch loop can skip them: a
        person cannot both be on approved leave and have clocked in.
        """
        out = {}
        monday = today - timedelta(days=today.weekday())
        adults = [e for e in cohort if e.name not in _MINOR_SHAPE]
        if len(adults) < 42:
            return out
        for emp, first, days in self._p6_leave_plan(adults, monday):
            out.setdefault(emp.id, set()).update(
                (first + timedelta(days=i)).isoformat() for i in range(days))
        for emp, first, days in self._p6_trip_plan(adults, today, monday):
            out.setdefault(emp.id, set()).update(
                (first + timedelta(days=i)).isoformat() for i in range(days))
        return out

    def _p6_leave_plan(self, adults, monday):
        return [(adults[30], monday + timedelta(days=1), 2),
                (adults[31], monday + timedelta(days=3), 1)]

    def _p6_seed_leave(self, cohort, company, today):
        """One or two APPROVED leaves inside the current week — Today's on-leave
        tile and the Schedule overlay both need at least one."""
        monday = today - timedelta(days=today.weekday())
        adults = [e for e in cohort if e.name not in _MINOR_SHAPE]
        if len(adults) < 42:
            return {}
        Leave = self.env['hr.leave'].sudo()
        unpaid = self._ensure_leave_type('Demo Unpaid Leave', False, company)
        made = 0
        for emp, first, days in self._p6_leave_plan(adults, monday):
            last = first + timedelta(days=days - 1)
            if Leave.search_count([
                    ('employee_id', '=', emp.id),
                    ('state', 'in', ('validate', 'validate1')),
                    ('request_date_from', '<=', last),
                    ('request_date_to', '>=', first)]):
                continue
            try:
                with self.env.cr.savepoint():
                    lv = Leave.create({
                        'employee_id': emp.id,
                        'holiday_status_id': unpaid.id,
                        'request_date_from': first,
                        'request_date_to': last,
                        'name': 'Approved time off (demo)'})
                    self._validate_leave(lv)
                    made += 1
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo P6: leave for %s skipped: %s', emp.name, e)
        return {'leaves': made}

    # ================================================================= trips
    def _p6_trip_plan(self, adults, today, monday):
        """One approved trip inside the current week (the violet overlay on
        Time·Timeline) and one submitted trip waiting on next week."""
        return [(adults[40], monday + timedelta(days=2), 2),
                (adults[41], monday + timedelta(days=8), 2)]

    def _p6_seed_trips(self, cohort, company, today):
        if 'pb.business.trip' not in self.env:
            return {}
        adults = [e for e in cohort if e.name not in _MINOR_SHAPE]
        if len(adults) < 42:
            return {}
        Trip = self.env['pb.business.trip'].sudo()
        monday = today - timedelta(days=today.weekday())
        vn = self.env.ref('base.vn', False)
        policy = self.env.ref('pb_business_trip.policy_vn_tier1', False)
        cat_lodge = self.env.ref('pb_business_trip.cat_lodging', False)
        cat_trans = self.env.ref('pb_business_trip.cat_transport', False)

        plan = self._p6_trip_plan(adults, today, monday)
        targets = ['approved', 'submitted']
        cities = ['Da Nang', 'Hai Phong']
        made = 0
        for (emp, first, days), target, city in zip(plan, targets, cities):
            last = first + timedelta(days=days - 1)
            # The model hard-blocks two live trips for one person, so an
            # employee who already has ANY trip is left alone entirely.
            if Trip.search_count([('employee_id', '=', emp.id)]):
                continue
            lines = []
            if cat_lodge:
                lines.append((0, 0, {'date': first, 'category_id': cat_lodge.id,
                                     'description': 'Hotel (demo)',
                                     'amount': 1600000.0}))
            if cat_trans:
                lines.append((0, 0, {'date': first, 'category_id': cat_trans.id,
                                     'description': 'Flights (demo)',
                                     'amount': 2200000.0}))
            vals = {
                'employee_id': emp.id, 'company_id': company.id,
                'destination_city': city,
                'purpose': 'Site visit (demo)',
                'date_from': first, 'date_to': last,
                'per_diem_rate': 200000.0, 'advance_amount': 2500000.0,
                'currency_id': company.currency_id.id, 'line_ids': lines,
            }
            if vn:
                vals['destination_country_id'] = vn.id
            if policy:
                vals['policy_id'] = policy.id
            try:
                with self.env.cr.savepoint():
                    trip = Trip.create(vals)
                    self._advance_trip(trip, target)
                    made += 1
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo P6: trip for %s skipped: %s', emp.name, e)
        return {'trips': made}

    # =========================================================== corrections
    def _p6_seed_correction(self, cohort, company, tz, specs, today):
        """One SUBMITTED correction on a day that really IS missing a punch —
        the Attendance-Control pipeline card and the Approvals dock's fourth
        source. Filed against a real absence rather than an invented day, so
        approving it in a demo actually repairs something. An EXCUSED day (leave
        or trip) is skipped: there is nothing to correct about an approved
        absence, and filing one would be the demo teaching the wrong reflex.
        """
        if 'hr.attendance.correction' not in self.env:
            return {}
        Corr = self.env['hr.attendance.correction'].sudo()
        Shift = self.env['hr.shift.planning'].sudo()
        Att = self.env['hr.attendance'].sudo()
        minors = set(_MINOR_SHAPE)

        candidates = sorted(
            ((eid, d) for (eid, d), sp in specs.items()
             if sp['past'] and not sp['ci'] and not sp['excused']
             and d >= today - timedelta(days=7) and d.weekday() < 5),
            key=lambda k: (-k[1].toordinal(), k[0]))
        for eid, d in candidates:
            emp = cohort.browse(eid)
            if not emp.exists() or emp.name in minors:
                continue
            shift = Shift.search([('employee_id', '=', eid),
                                  ('date', '=', d)], limit=1)
            if not shift:
                continue
            lo, hi = self._p6_day_bounds(tz, d)
            if Att.search_count([('employee_id', '=', eid),
                                 ('check_in', '>=', lo), ('check_in', '<=', hi)]):
                continue
            # idempotency: one correction per (employee, day) — and once ANY
            # seeded correction exists in the window there is nothing to add
            if Corr.search_count([('employee_id', '=', eid), ('date', '=', d)]):
                return {}
            try:
                with self.env.cr.savepoint():
                    rec = Corr.create({
                        'employee_id': eid,
                        'company_id': company.id,
                        'date': d,
                        'correction_type': 'create',
                        'new_check_in': shift.start_datetime,
                        'new_check_out': shift.end_datetime,
                        'reason': 'Badge failed at the gate (demo)',
                        'exception_kind': 'missing_punch',
                    })
                    rec.action_submit()
                return {'corrections': 1}
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo P6: correction skipped: %s', e)
                return {}
        _logger.info('pb_demo P6: no missing-punch day to file a correction on')
        return {}

    # =============================================================== drivers
    def _p6_seed_drivers(self, company, tz, today):
        """Live pins for the Today board's map card.

        Deliberately NOT the route-sim seed drivers: those ship archived and are
        woken only by the demo-mode pill (pb_driver_checkin.toggle_demo), which
        also starts a live simulator — leaving it on is exactly what §3.7 says
        not to do. Instead two DEMO employees are given a passwordless login in
        the driver group, today's open punch and a fresh position, so the map is
        populated by demo-owned rows that nothing has to keep running.
        """
        grp = self.env.ref('pb_driver_checkin.group_pb_driver', False)
        if not grp or 'biz.geo.ping' not in self.env:
            return {}
        Employee = self.env['hr.employee'].sudo()
        Dept = self.env['hr.department'].sudo()
        Att = self.env['hr.attendance'].sudo()
        Ping = self.env['biz.geo.ping'].sudo()
        now = fields.Datetime.now()
        made = 0

        for spec in _DRIVERS:
            try:
                with self.env.cr.savepoint():
                    user = self._ensure_demo_login(
                        spec['login'], spec['name'], company)
                    dept = Dept.search([('name', '=', spec['dept']),
                                        ('company_id', '=', company.id)], limit=1)
                    domain = [('is_demo', '=', True), ('active', '=', True),
                              ('company_id', '=', company.id)]
                    if dept:
                        domain.append(('department_id', '=', dept.id))
                    # The one this login already drives (so a rerun keeps the
                    # same person), else the first FREE demo employee in the
                    # fleet — never one that is already somebody's ESS login,
                    # because `_link_user_employee` would silently steal it.
                    emp = Employee.search(
                        domain + [('user_id', '=', user.id)], limit=1)
                    if not emp:
                        emp = Employee.search(
                            domain + [('user_id', '=', False)],
                            order='name', limit=1)
                    if not emp:
                        continue
                    if grp.id not in user.group_ids.ids:
                        user.sudo().write({'group_ids': [(4, grp.id)]})
                    self._link_user_employee(user, emp)

                    # today's open punch — the pin needs somebody on shift
                    lo, hi = self._p6_day_bounds(tz, today)
                    if not Att.search_count([('employee_id', '=', emp.id),
                                             ('check_in', '>=', lo),
                                             ('check_in', '<=', hi)]):
                        Att.create({'employee_id': emp.id,
                                    'check_in': now - timedelta(hours=2)})
                    # a fresh position (the map ages pins; a rerun refreshes it)
                    Ping.create({
                        'user_id': user.id, 'latitude': spec['lat'],
                        'longitude': spec['lon'], 'accuracy_m': 12.0,
                        'source': 'real', 'ping_time': now,
                        'company_id': company.id,
                    })
                    made += 1
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo P6: driver %s skipped: %s',
                                spec['login'], e)
        return {'drivers': made}
