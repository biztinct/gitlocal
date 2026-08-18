# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.ess.workforce`` — the own-only facade behind the four "My Work" pages.

THE ONE RULE
------------
Not a single method here takes an employee. Every one of them starts with
``_own_employee()``, which resolves the employee from ``self.env.user`` by an
explicit search (C18.26 — never ``env.user.employee_id``, which is
company-dependent and silently picks a different person in a multi-company
tenant). There is therefore no parameter to forge: the adversarial tests in
``tests/test_p8_adversarial.py`` pass another employee's id into every public
method here and every one of them answers about the CALLER.

WHY THE READS ARE SUDO AND THE ACLS ARE NOT WIDENED
---------------------------------------------------
``hr.shift.planning`` and ``hr.overtime.request`` carry no ``base.group_user``
ACL row (``pb_hr_workforce/security/ir.model.access.csv``), on purpose: they are
officer models. P8 does NOT add one. The portal reads them sudo, scoped to the
resolved own employee — pb_me_portal's doctrine, where "the route boundary is
the PII gate, not field ACLs" — which means the widening is exactly one
employee wide and expires with the request, while a plain user hitting those
models directly over ``call_kw`` is still refused outright. Widening the ACL
would have been the weaker choice: it opens the model to every internal user
and then relies on a record rule to close it again.

WHY THE MUTATIONS ARE NOT SUDO
------------------------------
A punch fix is an ``hr.attendance.correction`` created AS THE REAL USER, with
``employee_id`` forced to the resolved own employee before the values ever reach
``create`` (I-H3: an employee files only for themselves, and the server decides
what "themselves" means). A leave is a plain ``hr.leave`` in the normal chain.
Neither writes a punch, an approval state or a payroll figure — this module owns
no state machine (W12).
"""

from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# How far the schedule page looks: the current week and the next one. Past
# shifts inside the current week stay visible (read-only) — an employee needs to
# see the week they are IN, not the week they have left.
_SCHEDULE_WEEKS = 2

_PLANNED_STATES = ('published', 'completed')
_APPROVED_LEAVE_STATES = ('validate', 'validate1')
_OPEN_LEAVE_STATES = ('confirm', 'validate1')

# A hard ceiling on every own-scope list. One employee cannot realistically have
# thousands of rows, but an unbounded search on a portal route is a denial of
# service waiting for the one record that proves otherwise.
_LIST_CAP = 120


class PbEssWorkforce(models.AbstractModel):
    _name = 'pb.ess.workforce'
    _description = 'ESS Workforce (own-only employee facade)'

    # ================================================================ identity
    @api.model
    def _own_employee(self):
        """The session user's employee, current company first (C18.26).

        Byte-identical in intent to ``pb_me_portal``'s ``_ess_employee`` — an
        employee linked to several companies must resolve to the one the user is
        actually working in, not to the lowest id.
        """
        Emp = self.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', self.env.user.id),
                          ('company_id', '=', self.env.company.id)], limit=1)
        return emp or Emp.search([('user_id', '=', self.env.user.id)], limit=1)

    @api.model
    def _require_own_employee(self):
        emp = self._own_employee()
        if not emp:
            raise UserError(_(
                "No employee record is linked to your user account. "
                "Ask HR to link it before using My Work."))
        return emp

    # ================================================================= helpers
    @api.model
    def _tzinfo(self, emp):
        """The employee's wall clock (W63): a shift stored in UTC has to be read
        back where the person works, or an 08:00 Vietnamese shift reads 01:00."""
        name = (emp.tz if emp else None) or self.env.user.tz or 'UTC'
        try:
            return pytz.timezone(name)
        except Exception:                                     # pragma: no cover
            return pytz.UTC

    @api.model
    def _hhmm(self, dt_utc, tzinfo):
        if not dt_utc:
            return ''
        return pytz.UTC.localize(dt_utc).astimezone(tzinfo).strftime('%H:%M')

    @api.model
    def _monday(self, day=False):
        d = fields.Date.to_date(day) or fields.Date.context_today(self)
        return d - timedelta(days=d.weekday())

    # =============================================================== schedule
    @api.model
    def get_my_schedule(self, week_start=False):
        """This week + next, as shift cards with their acknowledgment state.

        ``week_start`` is a VIEW parameter (which Monday), never an identity
        one. Whatever it says, the shifts come back for the caller.
        """
        emp = self._require_own_employee()
        first = self._monday(week_start)
        last = first + timedelta(days=7 * _SCHEDULE_WEEKS - 1)
        tzinfo = self._tzinfo(emp)
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()

        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', '=', emp.id),
            ('date', '>=', first), ('date', '<=', last),
            ('state', 'in', _PLANNED_STATES),
        ], order='date, start_datetime', limit=_LIST_CAP)

        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', '=', emp.id),
            ('state', 'in', _APPROVED_LEAVE_STATES),
            ('date_from', '<=', datetime.combine(last, time.max)),
            ('date_to', '>=', datetime.combine(first, time.min)),
        ])
        leave_days = {}
        for lv in leaves:
            df = lv.request_date_from or (lv.date_from.date() if lv.date_from else None)
            dt = lv.request_date_to or (lv.date_to.date() if lv.date_to else df)
            if not (df and dt):
                continue
            cur = max(df, first)
            stop = min(dt, last)
            while cur <= stop:
                leave_days[cur.isoformat()] = lv.holiday_status_id.name or _('Leave')
                cur += timedelta(days=1)

        by_day = {}
        for s in shifts:
            by_day.setdefault(s.date.isoformat(), []).append(
                self._shift_card(s, tzinfo, now))

        weeks = []
        pending = 0
        for w in range(_SCHEDULE_WEEKS):
            wstart = first + timedelta(days=7 * w)
            days = []
            for i in range(7):
                d = wstart + timedelta(days=i)
                iso = d.isoformat()
                cards = by_day.get(iso, [])
                pending += sum(1 for c in cards if c['can_ack'])
                days.append({
                    'date': iso,
                    'label': d.strftime('%a'),
                    'day_num': d.day,
                    'month': d.strftime('%b'),
                    'is_today': d == today,
                    'is_past': d < today,
                    'is_weekend': d.weekday() >= 5,
                    'shifts': cards,
                    'leave': leave_days.get(iso, ''),
                })
            hours = round(sum(c['hours'] for d in days for c in d['shifts']), 1)
            n_pending = sum(1 for d in days for c in d['shifts'] if c['can_ack'])
            weeks.append({
                'week_start': wstart.isoformat(),
                'label': _('This week') if w == 0 else _('Next week'),
                'days': days,
                # W80.2 — a SENTENCE is one msgid. Assembled here rather than
                # from `<t>` fragments in the template, because a translator
                # cannot reorder fragments and word order is exactly what
                # differs between English and Vietnamese.
                'hours_label': _('%(hours)s h scheduled', hours=hours),
                'confirm_label': _('Confirm week (%(count)s)', count=n_pending),
                'pending': n_pending,
            })

        return {
            'week_start': first.isoformat(),
            'prev_week': (first - timedelta(days=7)).isoformat(),
            'next_week': (first + timedelta(days=7)).isoformat(),
            'weeks': weeks,
            'pending': pending,
            'pending_label': (_('%(count)s shifts still to confirm', count=pending)
                              if pending else _('Everything confirmed')),
            'employee': {'id': emp.id, 'name': emp.name or ''},
        }

    @api.model
    def _shift_card(self, shift, tzinfo, now):
        """One shift, in the employee's wall clock, with its ack state.

        ``can_ack`` is the affordance test and it is deliberately the SAME
        predicate the token page and ``ack_shift`` use — a button that offers
        what the server would refuse is W29's door that can only produce an
        error.
        """
        tmpl = shift.shift_template_id
        return {
            'id': shift.id,
            'name': tmpl.name if tmpl else _('Shift'),
            'code': (tmpl.code or '') if tmpl else '',
            'start': self._hhmm(shift.start_datetime, tzinfo),
            'end': self._hhmm(shift.end_datetime, tzinfo),
            'hours': round(shift.planned_hours or 0.0, 2),
            'hours_label': _('%(hours)s h',
                             hours=round(shift.planned_hours or 0.0, 2)),
            'state': shift.state,
            'ack_state': shift.ack_state,
            'acked_at': self._hhmm(shift.acked_at, tzinfo) if shift.acked_at else '',
            'acked_on': shift.acked_at.date().isoformat() if shift.acked_at else '',
            'can_ack': shift._ess_can_ack(now=now),
            'note': shift.note or '',
        }

    @api.model
    def ack_shift(self, shift_id):
        """Acknowledge ONE of the caller's own shifts.

        The id is looked up inside the caller's OWN shifts, never browsed and
        then checked: a browse-then-compare leaks existence through the shape of
        the failure, and this way a foreign id simply is not in the set.
        """
        emp = self._require_own_employee()
        try:
            sid = int(shift_id)
        except (TypeError, ValueError):
            raise UserError(_("Unknown shift."))
        shift = self.env['hr.shift.planning'].sudo().search([
            ('id', '=', sid), ('employee_id', '=', emp.id)], limit=1)
        if not shift:
            raise UserError(_("That shift is not on your schedule."))
        done = shift._ess_ack('portal')
        return {'ok': bool(done), 'id': shift.id, 'ack_state': shift.ack_state}

    @api.model
    def ack_week(self, week_start=False):
        """"Confirm week" — acknowledge every still-pending own shift in it."""
        emp = self._require_own_employee()
        first = self._monday(week_start)
        last = first + timedelta(days=6)
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', '=', emp.id),
            ('date', '>=', first), ('date', '<=', last),
            ('state', 'in', _PLANNED_STATES),
        ], limit=_LIST_CAP)
        n = 0
        for s in shifts:
            if s._ess_ack('portal'):
                n += 1
        return {'ok': True, 'acked': n, 'week_start': first.isoformat()}

    # ============================================================== timesheet
    @api.model
    def get_my_week(self, week_start=False):
        """The caller's own person-week, on the P1a data contract.

        Reuses ``pb.time.hub``'s arithmetic through its ungated private twin
        ``_person_week`` (W53): the public ``get_person_week`` is officer-gated,
        and calling it here would raise AccessError for every employee on earth.
        The gate that replaces it is "this is MY employee record", which is a
        stronger question than the officer one, not a weaker one.
        """
        emp = self._require_own_employee()
        data = self.env['pb.time.hub'].sudo()._person_week(emp, week_start)
        if not data:
            return {}
        first = fields.Date.to_date(data['week_start'])
        # the open fix requests, so a day already under review does not offer
        # "request a fix" a second time (and the page can show its state)
        Corr = self.env['hr.attendance.correction'].sudo()
        corrs = Corr.search([
            ('employee_id', '=', emp.id),
            ('date', '>=', first), ('date', '<=', first + timedelta(days=6)),
        ], order='id desc', limit=_LIST_CAP)
        by_day = {}
        for c in corrs:
            by_day.setdefault(c.date.isoformat(), {
                'id': c.id, 'state': c.state, 'reason': c.reason or '',
                'error': c.apply_error or '',
            })
        for d in data['days']:
            d['fix'] = by_day.get(d['date'])
            d['can_fix'] = (not d['fix']
                            and fields.Date.to_date(d['date'])
                            <= fields.Date.context_today(self))
        data['prev_week'] = (first - timedelta(days=7)).isoformat()
        data['next_week'] = (first + timedelta(days=7)).isoformat()
        return data

    @api.model
    def request_fix(self, day, reason, check_in=False, check_out=False):
        """File an attendance correction FOR MYSELF and submit it.

        The employee is forced server-side, and this is the only place in the
        module that creates one. It is created AS THE REAL USER so the chain's
        own ``_approval_can`` sees a truthful ``create_uid`` — which is also what
        stops the filer from later approving it (safety rail 2, C18.27).
        """
        emp = self._require_own_employee()
        d = fields.Date.to_date(day)
        if not d:
            raise UserError(_("Pick the day you want corrected."))
        if d > fields.Date.context_today(self):
            raise UserError(_("You cannot request a fix for a future day."))
        reason = (reason or '').strip()
        if not reason:
            raise UserError(_("Tell your manager what went wrong on that day."))

        vals = {
            # FORCED. Not read from the caller, not validated from the caller —
            # the caller has no say in whose day this is (I-H3).
            'employee_id': emp.id,
            'company_id': emp.company_id.id or self.env.company.id,
            'date': d,
            'correction_type': 'create',
            'reason': reason,
            'exception_kind': 'ess_portal',
        }
        tzinfo = self._tzinfo(emp)
        ci = self._parse_wall_clock(d, check_in, tzinfo)
        co = self._parse_wall_clock(d, check_out, tzinfo)
        if ci:
            vals['new_check_in'] = ci
        if co:
            vals['new_check_out'] = co
        if not ci:
            # A "create" correction needs a check-in before it may be SUBMITTED
            # (hr.attendance.correction._check_ready_to_submit). Without times
            # the employee is reporting "this day is wrong, look at it", which
            # is a legitimate request — it stays a DRAFT for the officer to
            # complete, rather than being refused at the door.
            corr = self.env['hr.attendance.correction'].create(vals)
            return {'ok': True, 'id': corr.id, 'state': corr.state}
        corr = self.env['hr.attendance.correction'].create(vals)
        corr.action_submit()     # as the real user — the chain's own gate
        return {'ok': True, 'id': corr.id, 'state': corr.state}

    @api.model
    def _parse_wall_clock(self, day, hhmm, tzinfo):
        """"08:30" on `day`, in the employee's timezone → the naive UTC value
        Odoo stores (W63 — a wall clock written verbatim is a different shift)."""
        raw = (hhmm or '').strip()
        if not raw:
            return False
        try:
            hh, mm = [int(x) for x in raw.split(':')[:2]]
            local = tzinfo.localize(datetime.combine(day, time(hh, mm)))
        except (ValueError, TypeError):
            raise UserError(_("Enter a time as HH:MM, for example 08:30."))
        return local.astimezone(pytz.UTC).replace(tzinfo=None)

    # ================================================================== leave
    @api.model
    def get_my_leave(self):
        """Own balances (allocation-based types), own requests, appliable types.

        The balance arithmetic is the Leave Command Center's, restated for ONE
        employee rather than borrowed: ``pb.timeoff._balances`` is a paged
        org-wide board behind ``_require_officer``, and pulling a single row out
        of it would mean either widening that gate or paging 4 500 people to
        find one. Same two read_groups, same "validated allocations minus
        validated taken" definition — the number an employee sees is the number
        the officer sees.
        """
        emp = self._require_own_employee()
        Leave = self.env['hr.leave'].sudo()
        types = self.env['hr.leave.type'].sudo().search(
            [('requires_allocation', '=', True)])
        balances = []
        if types:
            alloc = self.env['hr.leave.allocation'].sudo().read_group(
                [('employee_id', '=', emp.id), ('state', '=', 'validate'),
                 ('holiday_status_id', 'in', types.ids)],
                ['number_of_days:sum'], ['holiday_status_id'], lazy=False)
            taken = Leave.read_group(
                [('employee_id', '=', emp.id), ('state', '=', 'validate'),
                 ('holiday_status_id', 'in', types.ids)],
                ['number_of_days:sum'], ['holiday_status_id'], lazy=False)
            a_by = {g['holiday_status_id'][0]: g.get('number_of_days') or 0.0
                    for g in alloc if g.get('holiday_status_id')}
            t_by = {g['holiday_status_id'][0]: g.get('number_of_days') or 0.0
                    for g in taken if g.get('holiday_status_id')}
            for t in types:
                a = a_by.get(t.id, 0.0)
                k = t_by.get(t.id, 0.0)
                balances.append({
                    'id': t.id, 'name': t.name,
                    'allocated': round(a, 2), 'taken': round(k, 2),
                    'balance': round(a - k, 2),
                    'balance_label': _('%(balance)s days left',
                                       balance=round(a - k, 2)),
                    'used_label': _('%(taken)s of %(allocated)s days used',
                                    taken=round(k, 2), allocated=round(a, 2)),
                    'low': (a - k) <= 2.0 and a > 0,
                })

        leaves = Leave.search([('employee_id', '=', emp.id)],
                              order='date_from desc', limit=_LIST_CAP)
        rows = []
        for lv in leaves:
            df = lv.request_date_from or (lv.date_from.date() if lv.date_from else None)
            dt = lv.request_date_to or (lv.date_to.date() if lv.date_to else df)
            rows.append({
                'id': lv.id,
                'type': lv.holiday_status_id.name or _('Leave'),
                'date_from': df.isoformat() if df else '',
                'date_to': dt.isoformat() if dt else '',
                'days': round(lv.number_of_days or 0.0, 2),
                'state': lv.state,
                'state_label': self._leave_state_label(lv.state),
                'note': lv.name or '',
            })

        # Appliable types: whatever the employee's company offers. Company-scoped
        # (C18.11/18) — a shared type (company_id unset) is offered too.
        co = emp.company_id.id or self.env.company.id
        appliable = self.env['hr.leave.type'].sudo().search(
            ['|', ('company_id', '=', False), ('company_id', '=', co)],
            order='name')
        return {
            'employee': {'id': emp.id, 'name': emp.name or ''},
            'balances': balances,
            'requests': rows,
            'types': [{'id': t.id, 'name': t.name} for t in appliable],
            'pending': sum(1 for r in rows if r['state'] in _OPEN_LEAVE_STATES),
        }

    @api.model
    def _leave_state_label(self, state):
        return {
            'draft': _('To submit'),
            'confirm': _('Waiting approval'),
            'validate1': _('Second approval'),
            'validate': _('Approved'),
            'refuse': _('Refused'),
            'cancel': _('Cancelled'),
        }.get(state, state or '')

    @api.model
    def apply_leave(self, type_id, date_from, date_to, note=False):
        """Create MY OWN leave, in the normal chain, as the real user.

        No sudo anywhere in this method: core ``hr.leave`` already lets an
        employee file for themselves, and its own validation (overlap, balance,
        working calendar) is exactly the validation this request must face. The
        employee is forced the same way the correction's is.
        """
        emp = self._require_own_employee()
        if not type_id:
            raise UserError(_("Choose a leave type."))
        if not (date_from and date_to):
            raise UserError(_("Pick the first and the last day."))
        df = fields.Date.to_date(date_from)
        dt = fields.Date.to_date(date_to)
        if not (df and dt):
            raise UserError(_("Those dates could not be read."))
        if dt < df:
            raise UserError(_("The last day cannot be before the first."))
        leave = self.env['hr.leave'].create({
            'employee_id': emp.id,           # FORCED (I-H3)
            'holiday_status_id': int(type_id),
            'request_date_from': df,
            'request_date_to': dt,
            'name': (note or '').strip() or _('Requested from My Work'),
        })
        if hasattr(leave, 'action_confirm'):
            leave.action_confirm()
        return {'ok': True, 'id': leave.id, 'state': leave.state}

    # =============================================================== overtime
    @api.model
    def get_my_overtime(self):
        """Own overtime requests, READ ONLY.

        Overtime is grid-entered and manager-approved by design (W50); an
        employee filing their own OT would be a new write path into a money
        input, which this phase's non-goals forbid outright. This page exists so
        the employee can see what was recorded and what it was worth.
        """
        emp = self._require_own_employee()
        reqs = self.env['hr.overtime.request'].sudo().search(
            [('employee_id', '=', emp.id)], order='date desc, id desc',
            limit=_LIST_CAP)
        cfg_by_type = {}
        for c in self.env['hr.overtime.config'].sudo().search([('active', '=', True)]):
            cfg_by_type.setdefault(c.overtime_type, c)
        rows = []
        total_approved = 0.0
        for r in reqs:
            cfg = cfg_by_type.get(r.overtime_type)
            approved = r.approved_hours or 0.0
            total_approved += approved if r.state == 'approved' else 0.0
            rows.append({
                'id': r.id,
                'date': r.date.isoformat() if r.date else '',
                'type': r.overtime_type or '',
                'type_label': (cfg.name if cfg and cfg.name
                               else (r.overtime_type or '').replace('_', ' ').title()),
                'rate': (cfg.rate_display if cfg and cfg.rate_display else ''),
                'planned': round(r.planned_hours or 0.0, 2),
                'actual': round(r.actual_hours or 0.0, 2),
                'approved': round(approved, 2),
                'state': r.state,
                'reason': r.reason or '',
            })
        return {
            'employee': {'id': emp.id, 'name': emp.name or ''},
            'rows': rows,
            'total_approved': round(total_approved, 2),
            'pending': sum(1 for r in rows if r['state'] in ('draft', 'submitted')),
        }

    # ================================================================ counters
    @api.model
    def get_my_counters(self):
        """The three /my home card counters, in ONE call with one gate.

        Returns zeros rather than raising when the user has no employee: a
        portal home that 500s because somebody's HR record is not linked yet is
        worse than a home with empty cards (T1).
        """
        emp = self._own_employee()
        if not emp:
            return {'shift_pending': 0, 'leave_pending': 0, 'overtime_pending': 0}
        first = self._monday()
        last = first + timedelta(days=7 * _SCHEDULE_WEEKS - 1)
        now = fields.Datetime.now()
        shifts = self.env['hr.shift.planning'].sudo().search([
            ('employee_id', '=', emp.id),
            ('date', '>=', first), ('date', '<=', last),
            ('state', 'in', _PLANNED_STATES),
            ('ack_state', '=', 'pending'),
        ], limit=_LIST_CAP)
        return {
            'shift_pending': sum(1 for s in shifts if s._ess_can_ack(now=now)),
            'leave_pending': self.env['hr.leave'].sudo().search_count(
                [('employee_id', '=', emp.id), ('state', 'in', _OPEN_LEAVE_STATES)]),
            'overtime_pending': self.env['hr.overtime.request'].sudo().search_count(
                [('employee_id', '=', emp.id),
                 ('state', 'in', ('draft', 'submitted'))]),
        }
