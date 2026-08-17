# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.close`` — the read model behind the Close lens (mockup C).

ONE QUESTION: is this week safe to hand to payroll?
---------------------------------------------------
Every employee-day of the week is classified into three buckets:

  * **clean**    — inside tolerance on every axis, nothing pending. It needs no
                   human, and the stat strip says so out loud ("41 auto-approved
                   · within 10-min tolerance"): the point of a tolerance is that
                   somebody's attention is spent only where it changes something.
  * **flagged**  — one or more reason chips (`missing_punch`,
                   `missing_checkout`, `variance_over`, `unscheduled_day`,
                   `ot_pending`, `week_variance`). A week with any of these
                   cannot be locked.
  * **reviewed** — a flag a manager consciously waived (`pb.close.review`). It
                   still shows on the board, greyed, because a closed week must
                   be able to answer "what did you decide about this?" — but it
                   no longer blocks the lock.

EVERYTHING IS DERIVED LIVE (P4 §1, and a new W-rule)
----------------------------------------------------
Nothing here reads ``hr.shift.planning.compliance_status``. That field is stale
by construction — a STORED compute over ``now()`` with no cron to re-run it, and
its ``actual_check_in`` / ``actual_check_out`` inputs are never written by any
production code path, only by seeders. A board that decided which weeks reach
payroll from a field nobody maintains would be confidently wrong. The proven
shape is live derivation (``pb_today.py``:295-317), and that is what this does:
shifts + punches + OT + the exception engine's own kinds, folded in Python from
batched reads.

THE DAY IS THE EMPLOYEE'S LOCAL DAY (new W-rule)
------------------------------------------------
A punch is keyed by its EMPLOYEE-LOCAL calendar day, matching
``pb.attendance.exception.engine`` and ``pb.wf.lock``, NOT by ``check_in.date()``
the way the Week Grid and ``pb.time.hub.get_person_week`` key theirs. That is a
deliberate, documented divergence: in VN (UTC+7) an 05:58 local punch is stored
on the previous UTC day, so UTC keying would report a phantom missing punch
against the early shift — precisely what C18.49 forbids — and, worse here, the
board would flag a day that the lock chip beside it calls a different day. A
lock and the board that offers to set it must mean the same Tuesday.

SHIFT STATES: published AND completed (W24)
--------------------------------------------
The exception engine reads ``published`` only; Today reads published + completed.
For a SETTLED week the second is the right question — ``pb_demo`` completes every
past punched shift, so a published-only board would show an almost empty week and
look broken. Same reasoning as ``pb.time.hub.get_person_week``.

MONEY (W12)
-----------
"Est. gross" is DISPLAY MATH on ``hr.contract._pb_hourly_rate()``, published as
an AGGREGATE only — never a per-person rate, never a payslip input, and no salary
rule may call any of this. The payroll bridges are untouched by P4.
"""

import logging
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

_OFFICER_GROUP = 'hr_attendance.group_hr_attendance_officer'

# The shared Workforce row budget (pb_wf_kit/js/wf_rows.js `WF_ROW_CAP`, mirrored
# by the Week Grid and the Timeline). One number across the section, so
# "the first N employees" never means a different N depending on the lens.
_MAX_ROWS = 200
# The flagged TABLE is capped separately: a settled week on a 200-person
# department legitimately produces hundreds of rows, and a payload that carries
# all of them is a payload nobody renders. The TRUE total travels beside the
# capped list (W45) — a capped read that reports `len(items)` tells the officer
# the backlog is shrinking while it grows.
_MAX_FLAGGED = 200

_PLANNED_STATES = ('published', 'completed')

# kind -> (label, tone). `tone` is a class name, never a hex (W1).
_KINDS = {
    'missing_punch':    (lambda: _("Missing punch"), 'rose'),
    'missing_checkout': (lambda: _("Missing punch-out"), 'rose'),
    'variance_over':    (lambda: _("Outside tolerance"), 'amber'),
    'unscheduled_day':  (lambda: _("Unscheduled day"), 'cyan'),
    'ot_pending':       (lambda: _("Overtime undecided"), 'amber'),
    'week_variance':    (lambda: _("Week outside tolerance"), 'amber'),
}


class PbClose(models.AbstractModel):
    _name = 'pb.close'
    _description = 'Weekly Close Cockpit'

    # ================================================================ access
    @api.model
    def _require_officer(self):
        u = self.env.user
        if not (u.has_group(_OFFICER_GROUP) or u.has_group('base.group_system')):
            raise AccessError(_(
                "The weekly Close board is restricted to attendance officers."))

    @api.model
    def _company_ids(self):
        return self.env.companies.ids or [self.env.company.id]

    @api.model
    def _monday(self, week_start):
        """Delegated to the Week-Grid facade, so the Close board and the grid it
        sends officers into can never disagree about which Monday a week is."""
        return self.env['hr.attendance.weekentry']._monday(week_start)

    # =============================================================== the read
    @api.model
    def get_close_data(self, department_id=False, week_start=False, search=False):
        """Mockup C's whole payload for one department-week. Pure READ.

        There is no write path anywhere in this method or anything it calls —
        which is what makes it safe for a lens that re-fetches on every context
        change to call it (W25/W41). Every mutation on this board goes through
        `pb.wf.lock.lock_day` / `unlock_day` or `pb.close.review_flag`, and all
        three are reachable only from a click handler.
        """
        self._require_officer()
        df = self._monday(week_start)
        dt = df + timedelta(days=6)
        days = [df + timedelta(days=i) for i in range(7)]
        today = fields.Date.context_today(self)

        emps, truncated = self._population(department_id, search)
        Lock = self.env['pb.wf.lock']
        locked_days = Lock._locked_dates(self.env.company, days)

        rows, stats, totals = self._classify(emps, df, dt, days, today)
        reviews = self._reviews(emps, df, dt)

        flagged, reviewed_n, clean_n, missing_n = [], 0, 0, 0
        for row in rows:
            key = (row['employee_id'], row['date'], row['kind'])
            row['reviewed'] = key in reviews
            if row['reviewed']:
                row['review_note'] = reviews[key]
                reviewed_n += 1
            else:
                if row['kind'] in ('missing_punch', 'missing_checkout'):
                    missing_n += 1
            row['locked'] = fields.Date.to_date(row['date']) in locked_days
        clean_n = stats['clean']
        # unreviewed first, then by day, then by name — the officer works down
        # the list and the rows they have already dealt with sink.
        rows.sort(key=lambda r: (r['reviewed'], r['date'], r['name']))
        flagged = rows[:_MAX_FLAGGED]
        open_flags = sum(1 for r in rows if not r['reviewed'])

        handoff = self._handoff(emps, df, dt, totals)
        checklist = self._checklist(emps, df, dt, open_flags, days, locked_days)
        can_manage = Lock._pb_can_manage()

        return {
            'week_start': df.isoformat(),
            'week_end': dt.isoformat(),
            'week_no': df.isocalendar()[1],
            'department_id': int(department_id) if department_id else False,
            'days': [{
                'iso': d.isoformat(),
                'label': d.strftime('%a'),
                'sublabel': d.strftime('%b %d'),
                'locked': d in locked_days,
                'is_future': d > today,
            } for d in days],
            'stats': {
                'clean': clean_n,
                'flagged': open_flags,
                'reviewed': reviewed_n,
                'missing': missing_n,
                'days_locked': len([d for d in days if d in locked_days]),
                'days_total': len([d for d in days if d <= today]) or 7,
            },
            'flagged': flagged,
            'flagged_total': len(rows),
            'flagged_shown': len(flagged),
            'handoff': handoff,
            'checklist': checklist,
            # `can_lock` — flags == 0, or every one of them reviewed. The CTA is
            # DISABLED, not hidden, so the officer can see what they are working
            # towards (the checklist beside it says what is missing).
            'can_lock': open_flags == 0,
            'can_manage_locks': can_manage,
            'can_review': self.env['pb.close.review']._pb_can_review(),
            # A week entirely in the future is not "all locked" — `all()` over an
            # empty sequence is True, which would have rendered the handoff rail
            # in its locked state for next week.
            'all_locked': bool([d for d in days if d <= today]) and all(
                d in locked_days for d in days if d <= today),
            'headcount': len(emps),
            'truncated': truncated,
            'tolerance': self._tolerance(),
        }

    # ============================================================ population
    @api.model
    def _population(self, department_id, search):
        co_ids = self._company_ids()
        domain = [('active', '=', True), ('company_id', 'in', co_ids)]
        if department_id:
            domain.append(('department_id', '=', int(department_id)))
        if search:
            domain.append(('name', 'ilike', search))
        emps = self.env['hr.employee'].sudo().search(
            domain, order='name', limit=_MAX_ROWS + 1)
        truncated = 0
        if len(emps) > _MAX_ROWS:
            truncated = len(emps) - _MAX_ROWS
            emps = emps[:_MAX_ROWS]
        return emps, truncated

    @api.model
    def _tolerance(self):
        mins, week_h = self.env['pb.attendance.rule']._variance_for_company(
            self.env.company)
        return {'minutes': mins, 'hours_week': week_h}

    # ========================================================== the classifier
    @api.model
    def _classify(self, emps, df, dt, days, today):
        """The whole board, from batched reads folded in Python.

        Returns ``(rows, stats, totals)`` where `rows` is one dict per FLAG (a
        day with two problems produces two rows, because the officer waives
        problems, not days).
        """
        Grid = self.env['hr.attendance.weekentry']
        var_min, var_week = self.env['pb.attendance.rule']._variance_for_company(
            self.env.company)
        if not emps:
            return [], {'clean': 0}, {'regular': 0.0, 'overtime': 0.0,
                                      'bonus': 0.0, 'emp_hours': {}}

        emp_ids = emps.ids

        # --- shifts (1 query) — published AND completed (W24) --------------
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', 'in', emp_ids),
            ('date', '>=', df), ('date', '<=', dt),
            ('state', 'in', _PLANNED_STATES),
        ])
        shift_by = defaultdict(list)
        for s in shifts:
            shift_by[(s.employee_id.id, s.date)].append(s)

        # --- punches (1 query, a day of slack each side for the tz shift) ---
        atts = self.env['hr.attendance'].sudo().search([
            ('employee_id', 'in', emp_ids),
            ('check_in', '>=', datetime.combine(df - timedelta(days=1), time.min)),
            ('check_in', '<=', datetime.combine(dt + timedelta(days=1), time.max)),
        ])
        tz_cache = {}
        att_by = defaultdict(list)
        for a in atts:
            d = self._local_day(a.employee_id, a.check_in, tz_cache)
            if d and df <= d <= dt:
                att_by[(a.employee_id.id, d)].append(a)

        # --- overtime (1 query) --------------------------------------------
        ot_rows = self.env['hr.overtime.request'].sudo().search_read(
            [('employee_id', 'in', emp_ids),
             ('date', '>=', df), ('date', '<=', dt)],
            ['employee_id', 'date', 'state', 'approved_hours', 'bonus_hours'])
        ot_pending = set()
        ot_approved = ot_bonus = 0.0
        for r in ot_rows:
            eid = r['employee_id'][0] if r['employee_id'] else False
            if r['state'] == 'submitted':
                ot_pending.add((eid, r['date']))
            elif r['state'] == 'approved':
                ot_approved += r['approved_hours'] or 0.0
                ot_bonus += r['bonus_hours'] or 0.0

        # --- days that are legitimately empty --------------------------------
        Engine = self.env['pb.attendance.exception.engine']
        trip_map = Engine._trip_days(emp_ids, df, dt)
        leave_map = Engine._leave_days(emp_ids, df, dt)
        first_contract = Engine._first_contract_day(emp_ids)

        rows = []
        clean = 0
        total_regular = 0.0
        emp_hours = {}

        for emp in emps:
            week_dev = 0.0
            worst = (0.0, None)
            emp_actual = 0.0
            for d in days:
                if d > today:
                    continue
                iso = d.isoformat()
                fc = first_contract.get(emp.id)
                if fc and d < fc:
                    continue
                excused = (iso in trip_map.get(emp.id, ())
                           or iso in leave_map.get(emp.id, ()))

                day_shifts = shift_by.get((emp.id, d), [])
                day_atts = att_by.get((emp.id, d), [])
                # Nothing scheduled and nothing happened is not a fact about
                # this week — it is a rest day. Counting it CLEAN would put two
                # hundred Sundays into "auto-approved" and make the headline
                # number meaningless; counting it flagged would make every
                # weekend an exception.
                if not day_shifts and not day_atts:
                    continue
                sched = round(sum(s.planned_hours or 0.0 for s in day_shifts), 2)
                actual = round(sum(Grid._att_hours(a) for a in day_atts), 2)
                emp_actual += actual
                delta = round(actual - sched, 2)

                if excused:
                    # An approved trip or a validated leave IS the explanation.
                    # Counting it clean would inflate the "auto-approved" number
                    # with days nobody worked; counting it flagged would make
                    # every holiday an exception. It is simply not a row.
                    continue

                kinds = []
                if day_shifts and not day_atts:
                    kinds.append('missing_punch')
                if any(not a.check_out for a in day_atts):
                    kinds.append('missing_checkout')
                if day_atts and not day_shifts and actual > 0:
                    kinds.append('unscheduled_day')
                if (emp.id, d) in ot_pending:
                    kinds.append('ot_pending')

                dev = self._punch_deviation(day_shifts, day_atts)
                if dev is not None and dev > var_min:
                    kinds.append('variance_over')
                if day_shifts:
                    week_dev += abs(delta)
                    if abs(delta) > abs(worst[0]):
                        worst = (delta, d)

                base = {
                    'employee_id': emp.id,
                    'name': emp.name,
                    'job': emp.job_title or (emp.job_id.name if emp.job_id
                                             else '') or '',
                    'dept': emp.department_id.name if emp.department_id else '',
                    'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
                    'date': iso,
                    'day_label': d.strftime('%a %b %d'),
                    'sched': sched,
                    'actual': actual,
                    'delta': delta,
                    'deviation': int(dev) if dev is not None else 0,
                }
                if kinds:
                    for kind in kinds:
                        label, tone = _KINDS[kind]
                        rows.append({**base, 'kind': kind,
                                     'kind_label': label(), 'tone': tone})
                else:
                    clean += 1

            total_regular += emp_actual
            emp_hours[emp.id] = emp_actual

            # --- the WEEK-level tolerance (§3.3) -----------------------------
            # ONE row per employee, not one per day (deviation D2, see the
            # module note below): a person eight minutes off on each of seven
            # days is INSIDE the per-punch tolerance every single time and 56
            # minutes off over the week. That is one fact about one person, and
            # surfacing it as seven identical rows the manager must waive one by
            # one would bury the days that really do need attention.
            if worst[1] and week_dev > var_week:
                label, tone = _KINDS['week_variance']
                rows.append({
                    'employee_id': emp.id,
                    'name': emp.name,
                    'job': emp.job_title or (emp.job_id.name if emp.job_id
                                             else '') or '',
                    'dept': emp.department_id.name if emp.department_id else '',
                    'avatar_url': '/web/image/hr.employee/%s/avatar_128' % emp.id,
                    'date': worst[1].isoformat(),
                    'day_label': worst[1].strftime('%a %b %d'),
                    'sched': 0.0,
                    'actual': 0.0,
                    'delta': round(week_dev, 2),
                    'deviation': 0,
                    'kind': 'week_variance',
                    'kind_label': label(),
                    'tone': tone,
                })

        return (rows, {'clean': clean},
                {'regular': round(total_regular, 2),
                 'overtime': round(ot_approved, 2),
                 'bonus': round(ot_bonus, 2),
                 'emp_hours': emp_hours})

    @api.model
    def _local_day(self, employee, dt_utc, cache):
        """See the module docstring: the EMPLOYEE-LOCAL day, so the board and
        the lock chip beside it mean the same Tuesday."""
        if not dt_utc:
            return False
        tzinfo = cache.get(employee.id)
        if tzinfo is None:
            try:
                tzinfo = pytz.timezone(employee.tz or 'UTC')
            except Exception:
                tzinfo = pytz.UTC
            cache[employee.id] = tzinfo
        return pytz.UTC.localize(dt_utc).astimezone(tzinfo).date()

    @api.model
    def _punch_deviation(self, day_shifts, day_atts):
        """max(|first check-in − shift start|, |last check-out − shift end|) in
        MINUTES, or None when the comparison is not available.

        This is what "|punch vs shift| ≤ variance_minutes" means: the tolerance
        is about the EDGES of the day, not about its total. Two hours short in
        the middle of a shift is a break, not a compliance question; twenty
        minutes late is.
        """
        if not day_shifts or not day_atts:
            return None
        starts = [s.start_datetime for s in day_shifts if s.start_datetime]
        ends = [s.end_datetime for s in day_shifts if s.end_datetime]
        ins = [a.check_in for a in day_atts if a.check_in]
        outs = [a.check_out for a in day_atts if a.check_out]
        devs = []
        if starts and ins:
            devs.append(abs((min(ins) - min(starts)).total_seconds()) / 60.0)
        if ends and outs:
            devs.append(abs((max(outs) - max(ends)).total_seconds()) / 60.0)
        return max(devs) if devs else None

    # ============================================================== reviews
    @api.model
    def _reviews(self, emps, df, dt):
        """{(employee_id, iso, kind): note} for the week — the waived flags."""
        if not emps:
            return {}
        rows = self.env['pb.close.review'].sudo().search_read(
            [('employee_id', 'in', emps.ids),
             ('date', '>=', df), ('date', '<=', dt)],
            ['employee_id', 'date', 'kind', 'note'])
        return {
            ((r['employee_id'][0] if r['employee_id'] else False),
             r['date'].isoformat(), r['kind']): (r['note'] or '')
            for r in rows
        }

    # ======================================================= payroll handoff
    @api.model
    def _handoff(self, emps, df, dt, totals):
        """The right rail's totals. AGGREGATES ONLY (W12).

        `est_gross` multiplies each person's hours by their own rate and then
        SUMS — a company average would be wrong per person by construction (the
        exact trap `hr.contract._pb_hourly_rate` was written to replace). The
        individual rates never leave this method, and the payload reports how
        many people had no resolvable rate rather than printing a confident,
        wrong total (the P2 cost-strip posture).
        """
        out = {
            'regular': totals.get('regular', 0.0),
            'overtime': totals.get('overtime', 0.0),
            'bonus': totals.get('bonus', 0.0),
            'est_gross': 0.0,
            'rate_missing': 0,
            'currency': self.env.company.currency_id.symbol or '',
        }
        emp_hours = totals.get('emp_hours') or {}
        if not emps or not emp_hours:
            return out
        try:
            rates = self.env['hr.shift.planning.grid']._pb_rates(list(emp_hours))
        except Exception:
            _logger.debug('pb.close: rates unavailable', exc_info=True)
            rates = {}
        gross = 0.0
        missing = 0
        ot_hours = out['overtime'] + out['bonus']
        # OT is distributed pro-rata over the population's rates rather than
        # attributed per person: the OT total is already an aggregate here, and
        # inventing a per-person split just to multiply it back up would be a
        # more precise-looking number that is no more true.
        avg_rate = 0.0
        rated = [r for r in rates.values() if r]
        if rated:
            avg_rate = sum(rated) / len(rated)
        for eid, hours in emp_hours.items():
            rate = rates.get(eid) or 0.0
            if not rate:
                # Only somebody who actually worked can be MISSING from the
                # total — footnoting an unrated person who worked zero hours
                # would report a gap that changes nothing.
                if hours:
                    missing += 1
                continue
            gross += rate * hours
        gross += avg_rate * ot_hours
        out['est_gross'] = round(gross, 2)
        out['rate_missing'] = missing
        return out

    # ============================================================= checklist
    @api.model
    def _checklist(self, emps, df, dt, open_flags, days, locked_days):
        """Mockup C's four ticks. Each one is a QUESTION the officer would
        otherwise have to go and check on another screen."""
        ot_open = corr_open = 0
        if emps:
            ot_open = self.env['hr.overtime.request'].sudo().search_count([
                ('employee_id', 'in', emps.ids),
                ('date', '>=', df), ('date', '<=', dt),
                ('state', '=', 'submitted')])
            if 'hr.attendance.correction' in self.env:
                corr_open = self.env['hr.attendance.correction'].sudo(
                ).search_count([
                    ('employee_id', 'in', emps.ids),
                    ('date', '>=', df), ('date', '<=', dt),
                    ('state', '=', 'submitted')])
        unlocked = [d for d in days if d not in locked_days]
        return [
            {'key': 'ot', 'done': ot_open == 0,
             'label': (_("Overtime all decided") if ot_open == 0
                       else _("%s overtime request(s) undecided", ot_open))},
            {'key': 'corrections', 'done': corr_open == 0,
             'label': (_("Corrections all decided") if corr_open == 0
                       else _("%s correction(s) awaiting approval", corr_open))},
            {'key': 'flags', 'done': open_flags == 0,
             'label': (_("No exceptions open") if open_flags == 0
                       else _("%s exception(s) open", open_flags))},
            {'key': 'locks', 'done': not unlocked,
             'label': (_("Every day locked") if not unlocked
                       else _("%s day(s) unlocked", len(unlocked)))},
        ]

    # ================================================================ writes
    # Everything below is a MUTATION and is reachable only from a click handler
    # in the lens (W21.1). None of it is called by `get_close_data`.
    @api.model
    def review_flag(self, employee_id, day, kind, note=False):
        """"Approve as-is" — record a manager waiving one flag.

        Idempotent: waiving the same flag twice returns the existing row rather
        than raising, because the officer's second click is the same decision,
        and a UNIQUE violation is not a message anybody can act on.
        """
        self._require_officer()
        Review = self.env['pb.close.review']
        Review._pb_check_review()
        if kind not in dict(Review._fields['kind'].selection):
            raise UserError(_("Unknown flag type."))
        emp = self.env['hr.employee'].sudo().browse(int(employee_id)).exists()
        if not emp or (emp.company_id
                       and emp.company_id.id not in self._company_ids()):
            raise UserError(_("That employee is not available in this company."))
        day = fields.Date.to_date(day)
        existing = Review.sudo().search([
            ('employee_id', '=', emp.id), ('date', '=', day),
            ('kind', '=', kind)], limit=1)
        if existing:
            return existing.id
        # created AS THE REAL USER: the model's gate and the no-self-review rule
        # must see who is actually clicking (W12 — the pb.team.act posture).
        return Review.create({
            'company_id': emp.company_id.id or self.env.company.id,
            'week_start': Review._monday(day),
            'employee_id': emp.id,
            'date': day,
            'kind': kind,
            'note': (note or '').strip() or False,
        }).id

    @api.model
    def lock_days(self, days, reason=False):
        """Lock a list of days — the CTA's "Lock week & send to payroll".

        A loop over `pb.wf.lock.lock_day`, which re-checks the manager gate for
        every one of them. Stops on the first refusal and reports what landed,
        rather than pretending a partial close succeeded.
        """
        self._require_officer()
        done = []
        for d in (days or []):
            self.env['pb.wf.lock'].lock_day(
                self.env.company.id, fields.Date.to_date(d), reason)
            done.append(fields.Date.to_date(d).isoformat())
        return {'locked': done}

    @api.model
    def unlock_days(self, days, reason):
        """Reopen — the reason is required, and it is recorded (W42)."""
        self._require_officer()
        done = []
        for d in (days or []):
            if self.env['pb.wf.lock'].unlock_day(
                    self.env.company.id, fields.Date.to_date(d), reason):
                done.append(fields.Date.to_date(d).isoformat())
        return {'unlocked': done}
