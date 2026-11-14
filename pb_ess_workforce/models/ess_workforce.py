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

THE ONE PUNCH (TIERS T3b)
-------------------------
``clock_toggle`` is the single place this module creates a punch: stock's own
``_attendance_action_change`` on the sudo own-employee, after
``_require_own_employee`` (ledger T-R11), behind a per-company switch and
an explicit action tied to the displayed attendance session. The row it creates
is tagged ``pb_entry_source='portal'``.
"""

import base64
import logging
import re
from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

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

# TIERS T3b — clock in / out from My Payobook.
#: Per-company switch (D3): '1' = on, '0' = off; UNSET = ON. A parameter, never
#: a column on res.company (no new stored field on an existing model).
CLOCK_PARAM = 'pb_ess_workforce.portal_clock.%s'
#: The strip under the button: today and the six days before it.
CLOCK_WEEK_DAYS = 7

# WDGAP QF3 — documents on a leave request (cloned from pb_me_expense, R4).
#: How big one document may be.
LEAVE_DOC_MAX_BYTES = 10 * 1024 * 1024
#: The kinds of file a document may be, decided from its own first bytes.
LEAVE_DOC_MIME = ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')
#: How many documents one leave request may carry.
LEAVE_DOC_MAX = 5

_logger = logging.getLogger(__name__)


def sniff_mimetype(data):
    """The kind of file from its first bytes; '' when it is none we take.
    A copy of `pb_me_expense.models.me_expense.sniff_mimetype` (this module
    does not depend on expenses)."""
    head = bytes(data[:16]) if data else b''
    if head.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if head.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if head.startswith(b'%PDF'):
        return 'application/pdf'
    return ''


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
            # `n_pending` is what the employee can still ACT on (a shift that has
            # started can no longer be confirmed), and it drives the button.
            # `n_acked` / `n_total` are what actually HAPPENED, and they drive
            # the badge — found live: a week holding two unconfirmed past shifts
            # was crowned "All confirmed" because the button had nothing left to
            # do. A control that is stricter or softer than the fact beneath it
            # has to derive from the fact (W42), so the badge is now a count and
            # only a genuinely complete week turns green.
            week_cards = [c for d in days for c in d['shifts']]
            n_pending = sum(1 for c in week_cards if c['can_ack'])
            n_acked = sum(1 for c in week_cards if c['ack_state'] == 'acked')
            n_total = len(week_cards)
            weeks.append({
                'week_start': wstart.isoformat(),
                'label': _('This week') if w == 0 else _('Next week'),
                'days': days,
                'acked': n_acked,
                'total': n_total,
                'all_acked': bool(n_total) and n_acked == n_total,
                'ack_label': _('%(acked)s of %(total)s confirmed',
                               acked=n_acked, total=n_total),
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
            # Plural-safe by construction. English "1 shifts" and Vietnamese's
            # lack of a plural form are the same problem, and a msgid that has
            # to agree with a number in two languages is a msgid that will be
            # wrong in one of them. The number is a value, not part of a
            # conjugated noun phrase.
            'pending_label': (_('Still to confirm: %(count)s', count=pending)
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
        module that creates one. The create runs under ``sudo()`` AFTER
        ``_require_own_employee`` (TIERS T2b, ledger T-R11): an employee login
        (a portal account) holds no ACL on corrections. ``sudo()`` keeps
        ``env.uid``, so the chain's own ``_approval_can`` still sees a truthful
        ``create_uid`` — which is what stops the filer from later approving it
        (safety rail 2, C18.27).
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
            corr = self.env['hr.attendance.correction'].sudo().create(vals)
            return {'ok': True, 'id': corr.id, 'state': corr.state}
        corr = self.env['hr.attendance.correction'].sudo().create(vals)
        corr.action_submit()     # env.uid is still the filer — the chain's own gate
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
    # WDGAP QF3 — half days and hours, withdraw, cancel, documents and the
    # "after this request" preview. THE SAFETY RAILS (handover §3):
    #   R1 every method resolves the employee from the session and refuses a
    #      leave that is not theirs BEFORE any sudo write (`_own_leave`);
    #   R2 sudo skips pb_timeoff's past-date rule and hr_holidays' state
    #      checks, so `_leave_refusal` re-states them for the employee path —
    #      ONE helper behind apply / withdraw / cancel / add a document, and
    #      the same helper answers the page's can_* flags;
    #   R3 a withdraw closes the open approval through the engine (which now
    #      cancels the leave through `hr.leave._approval_withdraw`);
    #   R4 uploads: first bytes decide the kind, 10 MB, 5 per leave, bound to
    #      the leave, tokened links.

    @api.model
    def get_my_leave(self):
        """Own balances (allocation-based types), own requests, appliable types.

        The balance arithmetic is the Leave Command Center's, restated for ONE
        employee rather than borrowed: ``pb.timeoff._balances`` is a paged
        org-wide board behind ``_require_officer``, and pulling a single row out
        of it would mean either widening that gate or paging 4 500 people to
        find one. Same two read_groups, same "validated allocations minus
        validated taken" definition — the number an employee sees is the number
        the officer sees. QF3 adds what is still waiting for approval, as its
        own quiet line (it is not taken until it is approved).
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
            waiting = Leave.read_group(
                [('employee_id', '=', emp.id),
                 ('state', 'in', _OPEN_LEAVE_STATES),
                 ('holiday_status_id', 'in', types.ids)],
                ['number_of_days:sum'], ['holiday_status_id'], lazy=False)
            a_by = {g['holiday_status_id'][0]: g.get('number_of_days') or 0.0
                    for g in alloc if g.get('holiday_status_id')}
            t_by = {g['holiday_status_id'][0]: g.get('number_of_days') or 0.0
                    for g in taken if g.get('holiday_status_id')}
            w_by = {g['holiday_status_id'][0]: g.get('number_of_days') or 0.0
                    for g in waiting if g.get('holiday_status_id')}
            for t in types:
                a = a_by.get(t.id, 0.0)
                k = t_by.get(t.id, 0.0)
                w = round(w_by.get(t.id, 0.0), 2)
                # A tile per configured leave type is CONFIGURATION, not data
                # (W64). This database carries 32 allocation-based types and the
                # live page rendered 32 tiles all reading "0.0 days left" — a
                # wall of identical values that buries the two an employee
                # actually has. Only a type this person has an allocation for,
                # or has taken, is a fact ABOUT THEM.
                if not (a or k):
                    continue
                balances.append({
                    'id': t.id, 'name': t.name,
                    'allocated': round(a, 2), 'taken': round(k, 2),
                    'balance': round(a - k, 2),
                    'balance_label': _('%(balance)s days left',
                                       balance=round(a - k, 2)),
                    'used_label': _('%(taken)s of %(allocated)s days used',
                                    taken=round(k, 2), allocated=round(a, 2)),
                    'low': (a - k) <= 2.0 and a > 0,
                    'pending': w,
                    'pending_label': (
                        '' if not w else
                        _('1 day waiting for approval') if w == 1 else
                        _('%s days waiting for approval', '{:g}'.format(w))),
                })

        leaves = Leave.search([('employee_id', '=', emp.id)],
                              order='date_from desc', limit=_LIST_CAP)
        files_by = self._leave_files_by(leaves)
        rows = []
        for lv in leaves:
            df = lv.request_date_from or (lv.date_from.date() if lv.date_from else None)
            dt = lv.request_date_to or (lv.date_to.date() if lv.date_to else df)
            amount, unit = self._leave_amount(lv)
            rows.append({
                'id': lv.id,
                'type': lv.holiday_status_id.name or _('Leave'),
                'date_from': df.isoformat() if df else '',
                'date_to': dt.isoformat() if dt else '',
                'days': round(lv.number_of_days or 0.0, 2),
                'length_label': self._leave_length_label(amount, unit),
                'period_label': lv._pb_day_part_label(),
                'state': lv.state,
                'state_label': self._leave_state_label(lv.state),
                'note': lv.name or '',
                'can_withdraw': not self._leave_refusal('withdraw', emp, lv),
                'can_cancel': not self._leave_refusal('cancel', emp, lv,
                                                      reason='-'),
                'can_add_document': not self._leave_refusal('document', emp, lv),
                'files': files_by.get(lv.id, []),
            })

        appliable = self._my_appliable_types(emp)
        return {
            'employee': {'id': emp.id, 'name': emp.name or ''},
            'balances': balances,
            'requests': rows,
            'types': [{
                'id': t.id, 'name': t.name,
                # the unit is the KIND's, never a per-request choice (FACTS §2)
                'unit': t.request_unit or 'day',
                'needs_document': bool(t.support_document),
            } for t in appliable],
            'has_half_day': any(t.request_unit == 'half_day' for t in appliable),
            'has_hours': any(t.request_unit == 'hour' for t in appliable),
            'doc_types': [t.name for t in appliable if t.support_document],
            'doc_max': LEAVE_DOC_MAX,
            'pending': sum(1 for r in rows if r['state'] in _OPEN_LEAVE_STATES),
        }

    @api.model
    def _my_appliable_types(self, emp):
        """The leave types this employee may ask for: their company's (C18.11/18,
        a shared type with company_id unset too), narrowed to the country they
        work in — the rule the Time Off "Apply for" drawer uses (pb.timeoff
        `_type_country` / `_emp_country`). A type naming no country is offered
        to everyone."""
        co = emp.company_id.id or self.env.company.id
        types = self.env['hr.leave.type'].sudo().search(
            ['|', ('company_id', '=', False), ('company_id', '=', co)],
            order='name')
        TO = self.env['pb.timeoff'].sudo()
        country = TO._emp_country(emp.sudo())
        return types.filtered(
            lambda t: TO._type_country(t) in ('', country))

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

    # ------------------------------------------------------ small helpers
    @api.model
    def _leave_amount(self, leave):
        """(amount, 'hour'|'day') — hours for a kind counted in hours, the
        unit hr_holidays' own balance is kept in for that kind."""
        if (leave.holiday_status_id.request_unit or 'day') == 'hour':
            return round(float(leave.number_of_hours or 0.0), 2), 'hour'
        return round(float(leave.number_of_days or 0.0), 2), 'day'

    @api.model
    def _leave_length_label(self, amount, unit):
        shown = '{:g}'.format(amount or 0.0)
        if unit == 'hour':
            return _('1 hour') if amount == 1 else _('%s hours', shown)
        if amount == 0.5:
            return _('Half a day')
        return _('1 day') if amount == 1 else _('%s days', shown)

    @api.model
    def _parse_hour(self, raw):
        """'09:30' -> 9.5; None when empty; UserError when unreadable."""
        raw = (raw or '').strip()
        if not raw:
            return None
        try:
            hh, mm = [int(x) for x in raw.split(':')[:2]]
        except (TypeError, ValueError):
            raise UserError(_("Enter a time as HH:MM, for example 08:30."))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise UserError(_("Enter a time as HH:MM, for example 08:30."))
        return hh + mm / 60.0

    @api.model
    def _leave_vals(self, emp, type_id, date_from, date_to, note=False,
                    period_from=None, period_to=None, hour_from=None,
                    hour_to=None):
        """Every check a request must pass, then the values to create it
        with. Shared by apply and the preview, so the preview counts exactly
        what the request will count. The employee is FORCED (I-H3)."""
        if not type_id:
            raise UserError(_("Choose a leave type."))
        offered = self._my_appliable_types(emp)
        try:
            type_id = int(type_id)
        except (TypeError, ValueError):
            type_id = 0
        if type_id not in offered.ids:
            raise UserError(_("Choose a leave type."))
        if not (date_from and date_to):
            raise UserError(_("Pick the first and the last day."))
        try:
            df = fields.Date.to_date(date_from)
            dt = fields.Date.to_date(date_to)
        except (TypeError, ValueError):
            df = dt = None
        if not (df and dt):
            raise UserError(_("Those dates could not be read."))
        if dt < df:
            raise UserError(_("The last day cannot be before the first."))
        leave_type = offered.filtered(lambda t: t.id == type_id)
        unit = leave_type.request_unit or 'day'
        pf = (period_from or '').strip().lower()
        pt = (period_to or '').strip().lower()
        hf, ht = (hour_from or '').strip(), (hour_to or '').strip()
        vals = {
            'employee_id': emp.id,           # FORCED (I-H3)
            'holiday_status_id': type_id,
            'request_date_from': df,
            'request_date_to': dt,
            'name': (note or '').strip() or _('Requested from My Work'),
        }
        if unit == 'half_day':
            if df == dt:
                part = pf if pf in ('am', 'pm') else 'full'
                vals['request_date_from_period'] = 'pm' if part == 'pm' else 'am'
                vals['request_date_to_period'] = 'am' if part == 'am' else 'pm'
            else:
                if pf == 'am':
                    raise UserError(_(
                        "When you ask for several days, the first day can be "
                        "a full day or start in the afternoon."))
                if pt == 'pm':
                    raise UserError(_(
                        "When you ask for several days, the last day can be a "
                        "full day or end in the morning."))
                vals['request_date_from_period'] = 'pm' if pf == 'pm' else 'am'
                vals['request_date_to_period'] = 'am' if pt == 'am' else 'pm'
        elif unit == 'hour':
            if df != dt:
                raise UserError(_(
                    "This kind of leave is counted in hours, so it is asked "
                    "for one day at a time. Pick the same first and last "
                    "day."))
            start, end = self._parse_hour(hf), self._parse_hour(ht)
            if start is None or end is None:
                raise UserError(_(
                    "This kind of leave is counted in hours. Enter the time "
                    "you leave and the time you are back."))
            if start >= end:
                raise UserError(_("The end time must be after the start time."))
            vals['request_hour_from'] = start
            vals['request_hour_to'] = end
        else:
            if pf in ('am', 'pm') or pt in ('am', 'pm') or hf or ht:
                raise UserError(_(
                    "This kind of leave is taken in whole days. Choose Full "
                    "day and leave the times empty, or pick a kind of leave "
                    "that can be taken in half days or hours."))
        return vals, leave_type

    @api.model
    def _own_leave(self, emp, leave_id):
        """The caller's own leave (sudo), or a refusal (R1). The id is never
        trusted: it is looked up inside the caller's own requests."""
        try:
            leave_id = int(leave_id or 0)
        except (TypeError, ValueError):
            leave_id = 0
        leave = self.env['hr.leave'].sudo().browse(leave_id).exists() \
            if leave_id else self.env['hr.leave'].sudo()
        if not leave or leave.employee_id.id != emp.id:
            raise UserError(_("We could not find that request."))
        return leave

    @api.model
    def _leave_first_day(self, leave):
        return leave.request_date_from or (
            leave.date_from.date() if leave.date_from else None)

    @api.model
    def _leave_can_cancel_as(self, leave, user):
        """hr_holidays' own `can_cancel`, asked AS the person (R2). An
        employee login (portal tier) cannot read hr.leave at all, so for it
        the same rule is restated: approved and not started.

        The same restatement answers when core's own compute cannot run as
        the person: it reads ``employee_id.leave_manager_id``, and a plain
        internal login without HR rights is refused the employee's private
        fields there (AccessError "not available for employee public
        profiles", found in this phase's tests) — the rule for one's OWN
        leave does not depend on that field."""
        restated = leave.state in ('validate', 'validate1') \
            and bool(leave.date_from) \
            and leave.date_from > fields.Datetime.now()
        if not user or user.share:
            return restated
        try:
            with self.env.cr.savepoint(flush=False):
                return bool(leave.with_user(user).can_cancel)
        except AccessError:
            return restated
        except UserError:
            return False

    @api.model
    def _leave_refusal(self, action, emp, leave=None, vals=None, reason=None):
        """THE employee-path rule (R2): '' when ``action`` is allowed, else
        the sentence that says why not. ``apply`` asks pb_timeoff's own
        past-date rule as a non-officer (sudo would skip it) and honours the
        `pb_timeoff.lock_past` switch."""
        Leave = self.env['hr.leave'].sudo()
        today = fields.Date.today()        # the SERVER's today, as pb_timeoff
        if action == 'apply':
            if not Leave._pb_lock_past_on():
                return ''
            try:
                Leave._pb_backdate_verdict(vals or {}, as_officer=False)
            except UserError as exc:
                return (exc.args and exc.args[0]) or str(exc)
            return ''
        if not leave or leave.employee_id.id != emp.id:
            return _("We could not find that request.")
        first = self._leave_first_day(leave)
        if action == 'withdraw':
            if leave.state == 'validate':
                return _("This leave is already approved. Use Cancel to call "
                         "it off.")
            if leave.state not in _OPEN_LEAVE_STATES:
                return _("This request is already finished.")
            if not first or first < today:
                return _("This time off has already started, so it cannot "
                         "be changed here. Ask HR.")
            return ''
        if action == 'cancel':
            if leave.state in _OPEN_LEAVE_STATES:
                return _("This request is still waiting for approval. Use "
                         "Withdraw instead.")
            if leave.state != 'validate':
                return _("This request is already finished.")
            if not first or first <= today:
                return _("This time off has already started, so it cannot "
                         "be cancelled here. Ask HR.")
            if not self._leave_can_cancel_as(leave, self.env.user):
                return _("This time off cannot be cancelled here. Ask HR.")
            if not (reason or '').strip():
                return _("Say why you are cancelling it. Your manager will "
                         "see the reason.")
            return ''
        if action == 'document':
            if leave.state not in ('confirm', 'validate1', 'validate'):
                return _("Documents can be added while a request is waiting "
                         "or approved.")
            return ''
        return _("That cannot be done here.")

    @api.model
    def _leave_guard(self, action, emp, leave=None, vals=None, reason=None):
        refusal = self._leave_refusal(action, emp, leave, vals=vals,
                                      reason=reason)
        if refusal:
            raise UserError(refusal)
        return True

    # ------------------------------------------------------------ documents
    @api.model
    def _leave_files_by(self, leaves):
        """{leave id: [{id, name, url, is_image}]} — tokened links (TIERS
        T14/T20): the one link shape that opens for every kind of login."""
        out = {}
        if not leaves:
            return out
        atts = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'hr.leave'), ('res_id', 'in', leaves.ids)],
            order='id')
        for att in atts:
            out.setdefault(att.res_id, []).append(self._leave_file_row(att))
        return out

    @api.model
    def _leave_file_row(self, att):
        return {
            'id': att.id,
            'name': att.name or _('Document'),
            'url': '/web/content/%s?access_token=%s' % (
                att.id, att.sudo().generate_access_token()[0]),
            'is_image': (att.mimetype or '').startswith('image/'),
        }

    @api.model
    def _check_leave_files(self, files, already=0):
        """Every check a document must pass, before anything is created —
        cloned from the expense receipts (R4). ``files`` is a list of
        ``(filename, bytes, declared type)``; the declared type and the
        filename's path are never trusted."""
        clean = []
        for item in files or []:
            if not item:
                continue
            filename, data = (tuple(item) + (None, None))[:2]
            if not data:
                continue
            if len(data) > LEAVE_DOC_MAX_BYTES:
                raise UserError(_(
                    "That file is over 10 MB. Try a smaller photo, or a PDF "
                    "of the page."))
            mimetype = sniff_mimetype(data)
            if mimetype not in LEAVE_DOC_MIME:
                raise UserError(_(
                    "A document can be a photo (JPG, PNG or WEBP) or a PDF. "
                    "Choose another file."))
            name = re.split(r'[\\/]', filename or '')[-1]
            name = re.sub(r'[\x00-\x1f]', '', name).strip()[-120:] or (
                'document.pdf' if mimetype == 'application/pdf'
                else 'document.jpg')
            clean.append({'name': name, 'data': data, 'mimetype': mimetype})
        if already + len(clean) > LEAVE_DOC_MAX:
            raise UserError(_(
                "A request can carry up to %s documents.", LEAVE_DOC_MAX))
        return clean

    @api.model
    def _attach_leave_files(self, leave, clean):
        Att = self.env['ir.attachment'].sudo()
        created = Att
        for row in clean:
            created |= Att.create({
                'name': row['name'],
                'datas': base64.b64encode(row['data']),
                'mimetype': row['mimetype'],
                'res_model': 'hr.leave',
                'res_id': leave.id,
            })
        return created

    # ---------------------------------------------------------------- apply
    @api.model
    def apply_leave(self, type_id, date_from, date_to, note=False,
                    period_from=None, period_to=None, hour_from=None,
                    hour_to=None, files=None):
        """Create MY OWN leave, in the normal chain.

        The create runs under ``sudo()`` AFTER ``_require_own_employee``
        (TIERS T2b, ledger T-R11): an employee login (a portal account) holds no
        ACL on ``hr.leave``. ``sudo()`` keeps ``env.uid``, so ``create_uid`` is
        the employee and the chain's own gates see the truthful filer. Core
        ``hr.leave``'s own validation (overlap, balance, working calendar) still
        runs. Because sudo no longer scopes the leave type by company, the type
        is checked against the ones ``get_my_leave`` offers this person.
        The employee is forced the same way the correction's is.

        QF3: the part of the day (half-day kinds) or the times (hour kinds),
        the documents, and the past-date rule sudo would otherwise skip (R2).
        Nothing is created when any check fails (one savepoint).
        """
        emp = self._require_own_employee()
        vals, leave_type = self._leave_vals(
            emp, type_id, date_from, date_to, note=note,
            period_from=period_from, period_to=period_to,
            hour_from=hour_from, hour_to=hour_to)
        self._leave_guard('apply', emp, vals=vals)
        Leave = self.env['hr.leave'].sudo()
        verdict = Leave._pb_backdate_verdict(
            vals, as_officer=False, refuse=False)
        clean = self._check_leave_files(files)
        with self.env.cr.savepoint():
            leave = Leave.create(vals)
            if hasattr(leave, 'action_confirm'):
                leave.action_confirm()
            if clean:
                self._attach_leave_files(leave, clean)
        if verdict == 'late':
            # sudo made the create look like HR's own entry, so pb_timeoff
            # did not tell HR (it only tells HR about a PERSON's late entry)
            try:
                with self.env.cr.savepoint():
                    leave._pb_alert_hr()
            except Exception:                               # noqa: BLE001
                _logger.warning('pb_ess_workforce: leave %s is backdated and '
                                'HR was not told', leave.id, exc_info=True)
        return {'ok': True, 'id': leave.id, 'state': leave.state}

    @api.model
    def preview_leave(self, type_id, date_from, date_to, period_from=None,
                      period_to=None, hour_from=None, hour_to=None):
        """What a request WOULD count, and what would be left after it.

        Writes nothing: the request is built with ``new()`` and counted by
        hr_holidays' own duration compute (the same one ``create`` runs), and
        the balance is ``virtual_remaining_leaves`` — which already takes off
        the other requests still waiting — minus this one.
        """
        emp = self._require_own_employee()
        try:
            vals, leave_type = self._leave_vals(
                emp, type_id, date_from, date_to, period_from=period_from,
                period_to=period_to, hour_from=hour_from, hour_to=hour_to)
        except UserError as exc:
            return {'ok': False, 'error': (exc.args and exc.args[0]) or ''}
        refusal = self._leave_refusal('apply', emp, vals=vals)
        draft = self.env['hr.leave'].sudo().new(vals)
        amount, unit = self._leave_amount(draft)
        out = {
            'ok': True,
            'error': refusal,
            'amount': amount,
            'unit': unit,
            'amount_label': _('This request: %s',
                              self._leave_length_label(amount, unit)),
            'counted': bool(leave_type.requires_allocation),
            'left_before': None,
            'after': None,
            'after_label': '',
            'over': False,
            'blocked': False,
            'warning': '',
            'needs_document': bool(leave_type.support_document),
        }
        if not leave_type.requires_allocation:
            return out
        row = self._allocation_row(leave_type, emp, vals['request_date_from'])
        if not row or not row.get('max_leaves'):
            out.update(blocked=True, after_label='', warning=_(
                "You have no days of this kind yet, so it cannot be sent. "
                "Ask HR about your balance."))
            return out
        left = round(float(row.get('virtual_remaining_leaves') or 0.0), 2)
        after = round(left - amount, 2)
        out['left_before'] = left
        out['after'] = after
        out['after_label'] = _('After this request: %s left',
                               self._leave_length_label(after, unit))
        if after < 0:
            out['over'] = True
            allowed = bool(row.get('allows_negative')) and \
                after >= -float(row.get('max_allowed_negative') or 0.0)
            out['blocked'] = not allowed
            out['warning'] = _(
                "This is more than you have left. You can still send it; "
                "your approver will see that.") if allowed else _(
                "This is more than you have left, so it cannot be sent. Ask "
                "HR about your balance.")
        return out

    @api.model
    def _allocation_row(self, leave_type, emp, day):
        data = leave_type.sudo().get_allocation_data(emp, day)
        for row in data.get(emp) or []:
            if len(row) >= 4 and row[3] == leave_type.id:
                return row[1]
        return None

    # ----------------------------------------------- withdraw / cancel / add
    @api.model
    def withdraw_leave(self, leave_id):
        """Take back MY OWN request that is still waiting (R3).

        The open approval is withdrawn through the engine (which cancels the
        leave through `hr.leave._approval_withdraw`), inside a savepoint; a
        company with no leave route cancels the leave directly. The leave is
        kept, as "Cancelled" — history, not a deletion.
        """
        emp = self._require_own_employee()
        leave = self._own_leave(emp, leave_id)
        self._leave_guard('withdraw', emp, leave)
        reason = _("Withdrawn by %s", emp.name or '')
        request = leave._leave_open_request() \
            if hasattr(leave, '_leave_open_request') else None
        with self.env.cr.savepoint():
            if request:
                self.env['biz.approval.engine'].sudo().cancel(
                    request.sudo(), reason)
                leave.invalidate_recordset()
            if leave.state != 'cancel':
                leave._pb_cancel_pending(reason)
        leave.invalidate_recordset()
        return {'ok': True, 'id': leave.id, 'state': leave.state}

    @api.model
    def cancel_leave(self, leave_id, reason):
        """Call off MY OWN approved leave that has not started, with a reason
        — hr_holidays' own user cancel (`_action_user_cancel`), which tells
        the manager through the leave's normal message. No new approval."""
        emp = self._require_own_employee()
        leave = self._own_leave(emp, leave_id)
        reason = (reason or '').strip()[:500]
        self._leave_guard('cancel', emp, leave, reason=reason)
        with self.env.cr.savepoint():
            request = leave._leave_open_request() \
                if hasattr(leave, '_leave_open_request') else None
            if request:
                # nothing may be left waiting in an approver's inbox
                self.env['biz.approval.engine'].sudo().cancel(
                    request.sudo(), reason)
            leave._action_user_cancel(reason)
        leave.invalidate_recordset()
        return {'ok': True, 'id': leave.id, 'state': leave.state}

    @api.model
    def add_leave_document(self, leave_id, files):
        """One or more documents on MY OWN request that is waiting or
        approved. Bound to the leave, so every screen that shows the leave's
        papers shows it."""
        emp = self._require_own_employee()
        leave = self._own_leave(emp, leave_id)
        self._leave_guard('document', emp, leave)
        already = self.env['ir.attachment'].sudo().search_count([
            ('res_model', '=', 'hr.leave'), ('res_id', '=', leave.id)])
        clean = self._check_leave_files(files, already=already)
        if not clean:
            raise UserError(_("Choose a photo or a PDF first."))
        with self.env.cr.savepoint():
            created = self._attach_leave_files(leave, clean)
            leave.message_post(
                body=_("Added a document: %s",
                       ', '.join(created.mapped('name'))),
                subtype_xmlid='mail.mt_note')
        return {'ok': True, 'id': leave.id, 'count': len(created)}

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

    # ================================================================== clock
    # TIERS T3b — clock in / out from My Payobook (handover T3B_HANDOVER.md
    # §1, D1–D3). The punch is STOCK's own method, `_attendance_action_change`
    # (hr_attendance/models/hr_employee.py:208-245, no group check), called on
    # the sudo own-employee AFTER `_require_own_employee` — exactly how stock's
    # public kiosk routes call it (hr_attendance/controllers/main.py:193-211).
    # `sudo()` keeps env.uid, so `create_uid` is the employee login.
    @api.model
    def portal_clock_enabled(self, company=None):
        """Is "clock in from My Payobook" on for ``company`` (default: the
        caller's own employee's company)? ON when the parameter is unset (D3).

        Exception-safe: templates call it (the nav pill, the home tile), and a
        page must never 500 on a switch — a failure answers False."""
        try:
            if not company:
                emp = self._own_employee()
                company = emp.company_id if emp else self.env.company
            company = company[:1]
            raw = self.env['ir.config_parameter'].sudo().get_param(
                CLOCK_PARAM % company.id)
            return (raw or '1').strip().lower() not in ('0', 'false', 'off')
        except Exception:               # noqa: BLE001 — a switch never 500s a page
            _logger.warning('pb_ess_workforce: could not read the clock switch',
                            exc_info=True)
            return False

    @api.model
    def _clock_minutes(self, att, now):
        """Minutes one attendance row counts for: stock's own `worked_hours`
        once it is closed (the figure payroll and the timesheet use — it
        leaves out the lunch break of a fixed working schedule), the live
        elapsed time while it is open."""
        if att.check_out:
            return int(round((att.worked_hours or 0.0) * 60))
        return max(0, int((now - att.check_in).total_seconds() // 60))

    @api.model
    def get_my_clock(self, now=None):
        """The caller's clock: state, since when, today and the last 7 days.

        Every value is JSON-safe (the `/my/work/clock/state` route returns this
        dict as is). Times are on the employee's wall clock (`_tzinfo`).
        """
        emp = self._require_own_employee()
        now = now or fields.Datetime.now()
        tzinfo = self._tzinfo(emp)
        local_now = pytz.UTC.localize(now).astimezone(tzinfo)
        today = local_now.date()
        first = today - timedelta(days=CLOCK_WEEK_DAYS - 1)
        start_utc = tzinfo.localize(datetime.combine(first, time.min)).astimezone(
            pytz.UTC).replace(tzinfo=None)

        Att = self.env['hr.attendance'].sudo()
        own = [('employee_id', '=', emp.id)]
        rows = Att.search(own + [('check_in', '>=', start_utc),
                                 ('check_in', '<=', now)],
                          order='check_in asc', limit=_LIST_CAP)
        open_att = Att.search(own + [('check_out', '=', False)],
                              order='check_in desc', limit=1)
        last = Att.search(own, order='check_in desc', limit=1)

        def local(dt):
            return pytz.UTC.localize(dt).astimezone(tzinfo)

        days = {}
        for att in rows:
            day = local(att.check_in).date()
            cell = days.setdefault(day, {'minutes': 0, 'first_in': None,
                                         'last_out': None, 'source': None,
                                         'open': False})
            cell['minutes'] += self._clock_minutes(att, now)
            if cell['first_in'] is None:
                cell['first_in'] = att.check_in
                cell['source'] = att.pb_entry_source or 'device' \
                    if 'pb_entry_source' in att._fields else 'device'
            if att.check_out:
                cell['last_out'] = max(cell['last_out'] or att.check_out,
                                       att.check_out)
            else:
                cell['open'] = True

        week = []
        for i in range(CLOCK_WEEK_DAYS):
            d = first + timedelta(days=i)
            cell = days.get(d) or {}
            week.append({
                'day': d.strftime('%a'),
                'iso': d.isoformat(),
                'minutes': cell.get('minutes', 0),
                'first_in': self._hhmm(cell['first_in'], tzinfo)
                if cell.get('first_in') else '',
                'last_out': self._hhmm(cell['last_out'], tzinfo)
                if cell.get('last_out') else '',
                'source': cell.get('source') or '',
                'open': bool(cell.get('open')),
                'is_today': d == today,
            })
        today_minutes = week[-1]['minutes']
        open_minutes = self._clock_minutes(open_att, now) if open_att else 0

        since = since_label = since_date = ''
        since_ms = 0
        since_days_ago = 0
        if open_att:
            since_local = local(open_att.check_in)
            since = since_local.isoformat()
            since_label = since_local.strftime('%H:%M')
            since_date = since_local.date().isoformat()
            since_ms = int(pytz.UTC.localize(open_att.check_in).timestamp() * 1000)
            since_days_ago = (today - since_local.date()).days

        last_punch = {}
        if last:
            if last.check_out:
                kind, when = 'out', last.check_out
            else:
                kind, when = 'in', last.check_in
            when_local = local(when)
            last_punch = {
                'kind': kind,
                'when': when_local.strftime('%H:%M'),
                'iso': when_local.isoformat(),
                'date': when_local.date().isoformat(),
                'is_today': when_local.date() == today,
            }

        company = emp.company_id
        tracking = bool(company and 'attendance_device_tracking' in company._fields
                        and company.attendance_device_tracking)
        session = open_att or last

        def location(prefix):
            if not session:
                return None
            lat = session['%s_latitude' % prefix]
            lng = session['%s_longitude' % prefix]
            coords = self._clock_coords(lat, lng)
            if not coords:
                return None
            label = '%.6f, %.6f' % coords
            return {'label': label, 'url': 'https://www.google.com/maps?q=%s' % label.replace(' ', '')}

        return {
            'enabled': self.portal_clock_enabled(company),
            'state': 'in' if open_att else 'out',
            'since': since,
            'since_label': since_label,
            'since_date': since_date,
            'since_ms': since_ms,
            'since_days_ago': since_days_ago,
            'open_attendance_id': open_att.id or False,
            'attendance_id': session.id or 0,
            'open_minutes': open_minutes,
            'open_seconds': max(0, int((now - open_att.check_in).total_seconds())) if open_att else 0,
            'session': {
                'started': local(session.check_in).strftime('%d %b %Y, %H:%M:%S'),
                'ended': local(session.check_out).strftime('%d %b %Y, %H:%M:%S') if session.check_out else '',
                'start_location': location('in'),
                'end_location': location('out') if session.check_out else None,
            } if session else None,
            'today_minutes': today_minutes,
            # today's closed rows only — the browser adds the live part
            'today_closed_minutes': today_minutes - (
                open_minutes if open_att and since_days_ago == 0 else 0),
            'week': week,
            'week_minutes': sum(d['minutes'] for d in week),
            'week_max': max([d['minutes'] for d in week] + [0]),
            'last_punch': last_punch,
            # stock's own switch: location, address and browser are only kept
            # when the company turned on "Device & Location Tracking"
            'tracking': tracking,
            'server_now_ms': int(pytz.UTC.localize(now).timestamp() * 1000),
            'today': today.isoformat(),
        }

    @api.model
    def _clock_coords(self, lat, lng):
        """Both coordinates as floats inside the globe, or None — a refused or
        garbled browser location is never an error (D3)."""
        try:
            la, lo = float(lat), float(lng)
        except (TypeError, ValueError):
            return None
        if not (-90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0):
            return None
        if la == 0.0 and lo == 0.0:
            return None
        return la, lo

    @api.model
    def clock_toggle(self, lat=None, lng=None, accuracy=None, nonce=None,
                     ip_address=None, browser=None, action=None,
                     attendance_id=None):
        """Apply the CALLER's explicit in/out action to the displayed session.

        The action and attendance id make repeated or stale forms harmless
        without blocking a legitimate immediate checkout. ``nonce`` is retained
        for call compatibility but unused. ``accuracy`` has no stock
        field and is not stored either. ``ip_address`` / ``browser`` come from
        the route (never from the form) and, like the coordinates, are kept
        only when the company's "Device & Location Tracking" is on — stock's
        own rule for its systray and kiosk punches.
        """
        emp = self._require_own_employee()
        if not self.portal_clock_enabled(emp.company_id):
            raise UserError(_(
                "Clocking in from these pages is switched off for your "
                "company. Use your usual device."))
        try:
            expected_id = int(attendance_id)
        except (TypeError, ValueError, OverflowError):
            expected_id = -1
        if action not in ('in', 'out') or expected_id < 0:
            raise UserError(_(
                "Your clock page has been updated. Check the current status "
                "below and try again."))

        # Serialize portal punches for this employee. An UPDATE (even with
        # an unchanged value) also makes an overlapping repeatable-read
        # transaction retry with a fresh snapshot; a row lock alone does not.
        emp.flush_recordset(['write_date'])
        self.env.cr.execute(
            'UPDATE hr_employee SET write_date = write_date WHERE id = %s',
            [emp.id])
        Att = self.env['hr.attendance'].sudo()
        Att.invalidate_model(['check_in', 'check_out'])
        emp.invalidate_recordset(['attendance_state', 'last_attendance_id'])
        last = Att.search([('employee_id', '=', emp.id)],
                          order='check_in desc', limit=1)
        was_in = emp.sudo().attendance_state == 'checked_in'
        if action == ('in' if was_in else 'out'):
            return dict(self.get_my_clock(), already=True, punched=False)
        if expected_id != (last.id or 0):
            return dict(self.get_my_clock(), changed=True, already=False,
                        punched=False)

        geo = {'mode': 'systray'}
        company = emp.company_id
        if company and 'attendance_device_tracking' in company._fields \
                and company.attendance_device_tracking:
            coords = self._clock_coords(lat, lng)
            if coords:
                geo['latitude'], geo['longitude'] = coords
            if ip_address:
                geo['ip_address'] = str(ip_address)[:64]
            if browser:
                geo['browser'] = str(browser)[:64]

        att = emp.sudo()._attendance_action_change(geo)
        punched = 'out' if was_in else 'in'
        # Tag the row WE created. A check-out closes whatever row is open —
        # possibly a device check-in — and re-labelling that row would strip
        # the device punch of its delete guard (`_is_device_row`), so a
        # check-out only ever confirms a row that is already ours.
        if punched == 'in' and 'pb_entry_source' in att._fields:
            att.sudo().write({'pb_entry_source': 'portal'})
        return dict(self.get_my_clock(), already=False, punched=punched)
