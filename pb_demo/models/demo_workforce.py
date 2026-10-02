# -*- coding: utf-8 -*-
"""Workforce demo enablement — attendance, shift planning, business trips and
extra overtime/leave variety (Sudima Phase K §5.8) — extends pb.demo.generator.

The Weekly Entry / Timecard / Live-Attendance / Shift-Planning / Trips cockpits
are all *facades* that read persistent rows (hr.attendance, hr.shift.planning,
pb.business.trip). Those tables were empty on the demo world, so every one of
those screens opened blank. This seeder fills a focused cohort — the first
~40 adult demo employees, taken in NAME order so they match the cockpit's own
``order='name'`` and land at the top of the grid without any filtering — across
the current + 3 recent weeks, plus a spread of business trips in every approval
state.

Story engineered into the data:
  * one clean device punch per employee per weekday (never 2 → the grid cell
    stays editable, safety rail 2), with a deterministic mix of on-time / late /
    early-leave / overtime / absent days so the compliance board is colourful;
  * a matching shift per weekday: past shifts are COMPLETED with their actual
    punch linked (drives compliance_status), current-week future shifts are
    PUBLISHED (pending);
  * six business trips, one per distinct employee (the overlap guard hard-blocks
    two live trips for the same person), one in each pipeline lane — draft,
    submitted, manager-approved, finance-approved, an APPROVED trip spanning
    today (lights up days-MTD + the presence overlay), and one cancelled;
  * extra overtime across all four rate types + extra pending/validated leaves,
    so the OT Desk queue, Bonus review and Leave Command Center look busy.

All records are generator-owned. clean_demo_employees removes them: attendance
CASCADES on the employee unlink, and shifts + trips are unlinked by employee_id
in demo_employees.clean_demo_employees before the employees go.

Deterministic only — no RNG, so a re-run reproduces the exact same world and the
search_count idempotency guards make action_generate_all safe to repeat.
"""

import logging
from datetime import datetime, time, timedelta

from pytz import timezone, utc

from odoo import fields, models

_logger = logging.getLogger(__name__)

_COHORT = 40        # adult employees seeded with attendance + shifts
_WEEKS_BACK = 3     # current week + this many prior weeks


class PbDemoGenerator(models.TransientModel):
    _inherit = 'pb.demo.generator'

    # ------------------------------------------------------------------ entry
    def ensure_workforce_demos(self):
        """Create/refresh the attendance + shift + trip + extra OT/leave story.
        Called from action_generate_all after the timeoff story."""
        self = self.with_context(**self._GEN_CTX)
        company = self.get_group_company()
        if not company:
            _logger.warning('pb_demo: no demo company; skipping workforce demos')
            return
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        adults = Employee.search([
            ('is_demo', '=', True), ('company_id', '=', company.id),
            ('active', '=', True),
        ], order='name').filtered(lambda e: 'Minor' not in (e.name or ''))
        if not adults:
            _logger.warning('pb_demo: no adult demo employees; skipping workforce demos')
            return
        cohort = adults[:_COHORT]

        cal = self.get_calendar(company)
        tz = timezone((cal and cal.tz) or 'Asia/Ho_Chi_Minh')
        today = fields.Date.context_today(self)
        monday = today - timedelta(days=today.weekday())   # Monday of this week

        self._seed_attendance_shifts(cohort, company, tz, today, monday)
        self._seed_business_trips(cohort, company, today, monday)
        self._thicken_overtime(cohort, company, today)
        self._thicken_leave(cohort, today)
        _logger.info('pb_demo: workforce demos ready (%s employees).', len(cohort))

    # ----------------------------------------------------------------- helpers
    def _local_to_utc(self, tz, d, hour):
        """Naive-UTC datetime for a local wall-clock `hour` (float, 8.5 = 08:30)
        on date `d` — the exact tz→UTC dance the young-worker seeder uses so the
        cockpits (which read UTC and re-localize) show the right day/time."""
        h = int(hour)
        m = int(round((hour - h) * 60))
        return tz.localize(datetime.combine(d, time(h, m))).astimezone(
            utc).replace(tzinfo=None)

    # ----------------------------------------------------- attendance + shifts
    def _seed_attendance_shifts(self, cohort, company, tz, today, monday):
        if 'hr.attendance' not in self.env:
            return
        Att = self.env['hr.attendance'].sudo()
        has_shifts = 'hr.shift.planning' in self.env
        Shift = self.env['hr.shift.planning'].sudo() if has_shifts else None
        template = None
        if has_shifts:
            template = (self.env.ref('pb_hr_workforce.shift_template_morning', False)
                        or self.env['hr.shift.template'].sudo().search(
                            [('active', '=', True)], order='sequence', limit=1))
            if not template:
                _logger.warning('pb_demo: no shift template; shifts skipped')

        for wk in range(-_WEEKS_BACK, 1):
            week_monday = monday + timedelta(days=wk * 7)
            for dow in range(5):                     # Mon–Fri
                d = week_monday + timedelta(days=dow)
                future = d > today
                for idx, emp in enumerate(cohort):
                    variant = (idx + dow + wk) % 9    # deterministic day flavour

                    # --- decide the day's shape -------------------------------
                    # The shift window below is 08:00–16:00 (8 h, matching the
                    # AM template's net duration), so a plain 8 h punch reads
                    # on_time; the variants below bend it late/early/overtime.
                    absent = variant == 8 and not future
                    cin_h, cout_h = 8.0, 16.0
                    if variant == 0:                  # late in
                        cin_h = 8.4                   # 08:24 (> 15-min tolerance)
                    elif variant == 1:                # stayed late (overtime)
                        cout_h = 18.0
                    elif variant == 2:                # left early
                        cout_h = 15.0

                    # --- attendance punch (past/today only, never future) -----
                    ci = co = False
                    if not future and not absent:
                        ci = self._local_to_utc(tz, d, cin_h)
                        co = self._local_to_utc(tz, d, cout_h)
                        if not Att.search_count([('employee_id', '=', emp.id),
                                                 ('check_in', '=', ci)]):
                            # blank pb_entry_source => a real "device" punch, so
                            # the Weekly Entry cell stays editable (rail 2).
                            Att.create({'employee_id': emp.id,
                                        'check_in': ci, 'check_out': co})

                    # --- matching shift ---------------------------------------
                    if not template:
                        continue
                    if Shift.search_count([('employee_id', '=', emp.id),
                                           ('date', '=', d)]):
                        continue
                    svals = {
                        'employee_id': emp.id,
                        'shift_template_id': template.id,
                        'date': d,
                        'start_datetime': self._local_to_utc(tz, d, 8.0),
                        'end_datetime': self._local_to_utc(tz, d, 16.0),
                        'company_id': company.id,
                    }
                    if ci and co:
                        svals['actual_check_in'] = ci
                        svals['actual_check_out'] = co
                    shift = Shift.create(svals)
                    # publish always; complete only the settled (past, punched)
                    # shifts so compliance_status resolves on/late/early/overtime.
                    shift.action_publish()
                    if not future and not absent:
                        shift.action_complete()

    # -------------------------------------------------------- business trips
    def _seed_business_trips(self, cohort, company, today, monday):
        if 'pb.business.trip' not in self.env or len(cohort) < 6:
            return
        Trip = self.env['pb.business.trip'].sudo()
        vn = self.env.ref('base.vn', False)
        policy = self.env.ref('pb_business_trip.policy_vn_tier1', False)
        cat_lodge = self.env.ref('pb_business_trip.cat_lodging', False)
        cat_trans = self.env.ref('pb_business_trip.cat_transport', False)
        cat_meals = self.env.ref('pb_business_trip.cat_meals', False)
        cur = company.currency_id

        def _lines(df):
            out = []
            if cat_lodge:
                out.append((0, 0, {'date': df, 'category_id': cat_lodge.id,
                                   'description': 'Hotel (demo)', 'amount': 1800000.0}))
            if cat_trans:
                out.append((0, 0, {'date': df, 'category_id': cat_trans.id,
                                   'description': 'Airfare (demo)', 'amount': 2400000.0}))
            if cat_meals:
                out.append((0, 0, {'date': df, 'category_id': cat_meals.id,
                                   'description': 'Meals (demo)', 'amount': 600000.0}))
            return out

        # (cohort index, city, days-from-today start, length, target state)
        plan = [
            (10, 'Ho Chi Minh City', 7, 2, 'draft'),
            (11, 'Hanoi', 9, 3, 'submitted'),
            (12, 'Da Nang', 12, 2, 'manager_approved'),
            (13, 'Can Tho', 14, 2, 'finance_approved'),
            (14, 'Ho Chi Minh City', -1, 4, 'approved'),   # spans today
            (15, 'Hai Phong', 21, 2, 'cancelled'),
        ]
        for cidx, city, off, length, target in plan:
            emp = cohort[cidx]
            df = today + timedelta(days=off)
            dt = df + timedelta(days=length - 1)
            if Trip.search_count([('employee_id', '=', emp.id),
                                  ('date_from', '=', df)]):
                continue
            vals = {
                'employee_id': emp.id, 'company_id': company.id,
                'destination_city': city, 'purpose': 'Client engagement (demo)',
                'date_from': df, 'date_to': dt,
                'per_diem_rate': 200000.0, 'advance_amount': 3000000.0,
                'currency_id': cur.id, 'line_ids': _lines(df),
            }
            if vn:
                vals['destination_country_id'] = vn.id
            if policy:
                vals['policy_id'] = policy.id
            trip = Trip.create(vals)
            try:
                self._advance_trip(trip, target)
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo: trip advance to %s failed: %s', target, e)

    def _advance_trip(self, trip, target):
        """Walk a draft trip up its approval chain (sudo => every tier's
        auth check short-circuits True) to the requested lane."""
        if target == 'cancelled':
            trip.action_cancel()
            return
        steps = [
            ('submitted', trip.action_submit),
            ('manager_approved', trip.action_manager_approve),
            ('finance_approved', trip.action_finance_approve),
            ('approved', trip.action_hr_approve),
        ]
        order = [s[0] for s in steps]
        stop = order.index(target)
        for i in range(stop + 1):
            steps[i][1]()

    # ----------------------------------------------------- extra overtime
    def _thicken_overtime(self, cohort, company, today):
        if 'hr.overtime.request' not in self.env or len(cohort) < 7:
            return
        OT = self.env['hr.overtime.request'].sudo()
        last_sat = today - timedelta(days=(today.weekday() + 2) % 7 or 7)
        # (cohort idx, date, type, hours, approve?)
        plan = [
            (2, last_sat, 'weekend', 5.0, False),
            (3, self._recent_weekday(today - timedelta(days=4)), 'holiday', 8.0, True),
            (4, self._recent_weekday(today - timedelta(days=1)), 'night', 3.0, False),
            (5, self._recent_weekday(today - timedelta(days=6)), 'weekday', 5.0, True),
            (6, self._recent_weekday(today - timedelta(days=9)), 'weekend', 4.0, True),
        ]
        for cidx, d, otype, hours, approve in plan:
            emp = cohort[cidx]
            if OT.search_count([('employee_id', '=', emp.id), ('date', '=', d),
                                ('overtime_type', '=', otype)]):
                continue
            r = OT.create({
                'employee_id': emp.id, 'company_id': company.id,
                'date': d, 'overtime_type': otype,
                'planned_hours': hours, 'actual_hours': hours,
                'reason': 'Workload spike (demo)',
            })
            try:
                r.action_submit()
                if approve:
                    r.action_approve()
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo: extra OT (%s) failed: %s', otype, e)

    # -------------------------------------------------------- extra leave
    def _thicken_leave(self, cohort, today):
        """A handful more unpaid leaves (no allocation needed) so the Leave
        Command Center queue + heatmap are not down to a single card."""
        if len(cohort) < 14:
            return
        Leave = self.env['hr.leave'].sudo()
        company = self.get_group_company()
        unpaid = self._ensure_leave_type('Demo Unpaid Leave', False, company)
        # pending (To-Approve) leaves next week
        for emp in cohort[8:12]:
            start = self._recent_weekday(today + timedelta(days=5))
            if not Leave.search_count([
                    ('employee_id', '=', emp.id),
                    ('holiday_status_id', '=', unpaid.id),
                    ('state', 'in', ('confirm', 'validate1'))]):
                Leave.create({
                    'employee_id': emp.id, 'holiday_status_id': unpaid.id,
                    'request_date_from': start,
                    'request_date_to': start + timedelta(days=1),
                    'name': 'Family matters (demo)',
                })
        # a couple of validated past leaves for the balance/heatmap
        for emp in cohort[12:14]:
            start = self._recent_weekday(today - timedelta(days=12))
            if not Leave.search_count([
                    ('employee_id', '=', emp.id),
                    ('holiday_status_id', '=', unpaid.id),
                    ('request_date_from', '=', start)]):
                lv = Leave.create({
                    'employee_id': emp.id, 'holiday_status_id': unpaid.id,
                    'request_date_from': start,
                    'request_date_to': start + timedelta(days=1),
                    'name': 'Unpaid leave (demo)',
                })
                self._validate_leave(lv)
