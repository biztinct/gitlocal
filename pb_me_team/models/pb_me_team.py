# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.me.team` — the facts behind a manager's area on the employee home.

WHO IS A MANAGER IS A RELATIONSHIP, NOT A GROUP. The team is the people whose
employee record names the caller's own record as their manager (`parent_id`),
read under sudo after the caller has been resolved from the session — the
same rule `/my/training/team` and the approvals inbox's "My team" queue use.
Nothing here accepts an employee id from the browser.

APPROVALS ARE THE INBOX'S, NEVER THIS FILE'S. Every card, every request and
every decision goes through `pb.approval.inbox` AS THE CALLER (no sudo): the
inbox's record rules decide what may be seen and `biz.approval.engine.decide`
decides what may be done, re-checking the seat each time. This file only adds
the facts a manager needs beside a leave request (the balance after it, and
who else in the team is away then), read after the inbox has shown the
request to the caller.

Every section is optional: a module that is not installed, or a read the
caller has no right to, loses that section and never the page (the
`pb.me.home.optional` pattern).
"""

import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

#: Minutes after the planned start before a first punch counts as late.
LATE_GRACE_MIN = 15
#: Minutes after the planned start before "no clock-in yet" is said.
NO_PUNCH_AFTER_MIN = 60
#: A company with no punch in this many days does not use clocking in; its
#: team board then shows leave only.
CLOCK_IN_USE_DAYS = 14
#: The team calendar's length.
CALENDAR_DAYS = 28
#: A day is a clash when at least this share of the team is away (and at
#: least two people).
CLASH_SHARE = 0.3
#: How far ahead the people moments look.
MOMENT_DAYS = 30
CONTRACT_END_DAYS = 60
PROBATION_DAYS = 30
#: Cards per approvals tab.
APPROVAL_CARDS = 60
LEAVE_LIVE = ('confirm', 'validate1', 'validate')
LEAVE_ASKED = ('confirm', 'validate1')
TABS = ('mine', 'others', 'done')


class PbMeTeam(models.AbstractModel):
    _name = 'pb.me.team'
    _description = "Employee home: a manager's team"

    # ================================================================ basics
    @api.model
    def _home(self):
        return self.env['pb.me.home']

    @api.model
    def _optional(self, model_name, fn, need=()):
        return self._home().optional(model_name, fn, fields=need)

    @api.model
    def team(self, emp):
        """The people who report to `emp` directly, active, by name (sudo)."""
        if not emp:
            return self.env['hr.employee'].sudo().browse()
        return self.env['hr.employee'].sudo().search(
            [('parent_id', '=', emp.id), ('active', '=', True)], order='name')

    @api.model
    def _inbox(self):
        """The approvals inbox AS THE CALLER, or None when this login cannot
        read approvals at all (an employee-only login has no right to)."""
        if 'pb.approval.inbox' not in self.env:
            return None
        try:
            self.env['biz.approval.request'].check_access('read')
        except AccessError:
            return None
        return self.env['pb.approval.inbox']

    @api.model
    def my_turn_count(self):
        inbox = self._inbox()
        if inbox is None:
            return 0
        try:
            with self.env.cr.savepoint(flush=False):
                return len(inbox._my_turn_ids())
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_team: approval count failed', exc_info=True)
            return 0

    @api.model
    def is_manager(self, emp):
        """Shown the manager area: somebody reports to them, or a decision is
        waiting on them."""
        return bool(self.team(emp)) or bool(self.my_turn_count())

    @api.model
    def _tz(self, emp):
        return pytz.timezone(self._home()._pbme_tz_name(emp))

    @api.model
    def _local_now(self, emp, now=None):
        return self._home()._pbme_local_now(emp, now or fields.Datetime.now())

    @api.model
    def _utc_range(self, emp, day):
        """[start, end) of the local calendar `day` as naive UTC datetimes."""
        tz = self._tz(emp)
        start = tz.localize(datetime.combine(day, time.min))
        end = tz.localize(datetime.combine(day + timedelta(days=1), time.min))
        return (start.astimezone(pytz.utc).replace(tzinfo=None),
                end.astimezone(pytz.utc).replace(tzinfo=None))

    @api.model
    def _person(self, member):
        return {
            'id': member.id,
            'name': member.name or '',
            'job': member.job_title or member.job_id.name or '',
            'photo': self._home()._colleague_photo_url(member),
        }

    # ============================================================ approvals
    @api.model
    def approvals(self, tab='mine'):
        """`{tab, cards, counts, can_read}` — the inbox's own cards.

        mine   — waiting on a seat of mine, now;
        others — open, about somebody in my team, decided by somebody else;
        done   — decided, about my team or decided by me.
        """
        tab = tab if tab in TABS else 'mine'
        inbox = self._inbox()
        empty = {'tab': tab, 'cards': [], 'can_read': False,
                 'counts': {'mine': 0, 'others': 0, 'done': 0}}
        if inbox is None:
            return empty
        try:
            with self.env.cr.savepoint(flush=False):
                open_cards = inbox.list_requests(tab='all', scope='team')['cards']
                mine = [c for c in open_cards if c['mine']]
                others = [c for c in open_cards if not c['mine']]
                done = inbox.list_requests(tab='done', scope='team')['cards']
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_team: approvals list failed', exc_info=True)
            return empty
        cards = {'mine': mine, 'others': others, 'done': done}[tab]
        return {
            'tab': tab,
            'cards': cards[:APPROVAL_CARDS],
            'more': len(cards) > APPROVAL_CARDS,
            'can_read': True,
            'counts': {'mine': len(mine), 'others': len(others),
                       'done': len(done)},
        }

    @api.model
    def approval(self, emp, request_id):
        """One request as the inbox's drawer shows it, plus the leave facts.
        None when the caller may not see it."""
        inbox = self._inbox()
        if inbox is None:
            return None
        try:
            with self.env.cr.savepoint(flush=False):
                payload = inbox.get_request(int(request_id or 0), scope='team')
        except (AccessError, UserError):
            return None
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_me_team: request %s failed', request_id,
                            exc_info=True)
            return None
        step = next((s for s in payload.get('steps') or []
                     if s['status'] == 'active'
                     and any(seat['mine'] and seat['status'] == 'open'
                             for seat in s['seats'])), None)
        payload['my_step_key'] = step['key'] if step else ''
        payload['leave'] = self._leave_context(emp, payload['id'])
        return payload

    @api.model
    def decide(self, request_id, step_key, action, reason, lock_revision,
               idempotency_key, use_exception=False):
        """Record one decision through the inbox — the engine allows or
        refuses it."""
        inbox = self._inbox()
        if inbox is None:
            raise AccessError(self.env._("You cannot decide approvals."))
        try:
            lock_revision = int(lock_revision)
        except (TypeError, ValueError):
            lock_revision = None
        return inbox.decide(int(request_id or 0), step_key or '', action,
                            reason=reason or '',
                            expected_lock_revision=lock_revision,
                            idempotency_key=(idempotency_key or '')[:80] or None,
                            use_exception=bool(use_exception))

    @api.model
    def _leave_context(self, emp, request_id):
        """For a leave request: its dates and type, the balance after it, and
        who else in the manager's team is away on those days."""
        req = self.env['biz.approval.request'].sudo().browse(request_id)
        if req.res_model != 'hr.leave' or not req.res_id:
            return None
        leave = self.env['hr.leave'].sudo().browse(req.res_id).exists()
        if not leave:
            return None
        out = {
            'type': leave.holiday_status_id.name or '',
            'date_from': leave.request_date_from,
            'date_to': leave.request_date_to,
            'days': leave.number_of_days,
            'balance_after': None,
            'away': [],
        }
        try:
            with self.env.cr.savepoint(flush=False):
                out['balance_after'] = self._balance_after(leave)
        except Exception:               # noqa: BLE001
            _logger.debug('pb_me_team: no balance for leave %s', leave.id)
        team = self.team(emp) - leave.employee_id
        if team and leave.request_date_from and leave.request_date_to:
            others = self.env['hr.leave'].sudo().search([
                ('employee_id', 'in', team.ids),
                ('state', 'in', LEAVE_LIVE),
                ('request_date_from', '<=', leave.request_date_to),
                ('request_date_to', '>=', leave.request_date_from),
            ], order='request_date_from')
            out['away'] = [{
                'name': o.employee_id.name or '',
                'type': o.holiday_status_id.name or '',
                'date_from': o.request_date_from,
                'date_to': o.request_date_to,
                'asked': o.state in LEAVE_ASKED,
            } for o in others]
            out['team_size'] = len(team) + 1
        return out

    @api.model
    def _balance_after(self, leave):
        """Days left of this type once this request (and any other request
        still waiting) is taken; None for a type that is not counted."""
        lt = leave.holiday_status_id
        if getattr(lt, 'requires_allocation', 'yes') == 'no':
            return None
        data = lt.get_allocation_data(leave.employee_id,
                                      leave.request_date_from)
        for row in data.get(leave.employee_id) or []:
            if len(row) >= 4 and row[3] == lt.id:
                left = row[1].get('virtual_remaining_leaves')
                return None if left is None else round(float(left), 2)
        return None

    # =========================================================== team today
    @api.model
    def _clock_in_use(self, emp, team):
        since = fields.Datetime.now() - timedelta(days=CLOCK_IN_USE_DAYS)
        return bool(self.env['hr.attendance'].sudo().search_count([
            ('employee_id.company_id', '=', emp.company_id.id),
            ('check_in', '>=', since)], limit=1))

    @api.model
    def _planned_start(self, member, day):
        """The first planned hour of `day` on the member's working hours, as
        a float (8.5 = 08:30); None for a day off."""
        cal = member.resource_calendar_id
        if not cal:
            return None
        rows = cal.attendance_ids.filtered(
            lambda a: a.dayofweek == str(day.weekday())
            and not getattr(a, 'display_type', False))
        if not rows:
            return None
        return min(rows.mapped('hour_from'))

    @api.model
    def _public_holiday(self, emp, day):
        lo, hi = self._utc_range(emp, day)
        found = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False),
            ('company_id', 'in', [emp.company_id.id, False]),
            ('date_from', '<', hi), ('date_to', '>', lo)], limit=1)
        return found.name or '' if found else None

    @api.model
    def today(self, emp, now=None):
        """`{rows, counts, clock, holiday}` — one row per person reporting to
        `emp`, with where they are today."""
        team = self.team(emp)
        local_now = self._local_now(emp, now)
        day = local_now.date()
        out = {'rows': [], 'counts': {}, 'clock': False, 'holiday': None,
               'date': day, 'size': len(team)}
        if not team:
            return out
        out['holiday'] = self._optional(
            'resource.calendar.leaves', lambda M: self._public_holiday(emp, day))
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', team.ids), ('state', 'in', LEAVE_LIVE),
            ('request_date_from', '<=', day), ('request_date_to', '>=', day)])
        leave_of = {}
        for lv in leaves:
            # an approved leave wins over one still being asked for
            if lv.employee_id.id not in leave_of or lv.state == 'validate':
                leave_of[lv.employee_id.id] = lv
        clock = bool(self._optional(
            'hr.attendance', lambda M: self._clock_in_use(emp, team)))
        out['clock'] = clock
        punches = {}
        if clock:
            lo, hi = self._utc_range(emp, day)
            for att in self.env['hr.attendance'].sudo().search(
                    [('employee_id', 'in', team.ids), ('check_in', '>=', lo),
                     ('check_in', '<', hi)], order='check_in'):
                punches.setdefault(att.employee_id.id, []).append(att)
        tz = self._tz(emp)
        hour_now = local_now.hour + local_now.minute / 60.0
        counts = {'in': 0, 'leave': 0, 'late': 0, 'missing': 0, 'off': 0,
                  'out': 0, 'unknown': 0}
        for member in team:
            row = self._person(member)
            lv = leave_of.get(member.id)
            atts = punches.get(member.id) or []
            start = self._planned_start(member, day)
            if lv:
                row.update(status='leave', leave_type=lv.holiday_status_id.name or '',
                           asked=lv.state in LEAVE_ASKED,
                           until=lv.request_date_to)
            elif atts:
                first = pytz.utc.localize(atts[0].check_in).astimezone(tz)
                last = atts[-1]
                row['since'] = first.strftime('%H:%M')
                first_h = first.hour + first.minute / 60.0
                if not last.check_out:
                    late = (start is not None
                            and first_h > start + LATE_GRACE_MIN / 60.0)
                    row['status'] = 'late' if late else 'in'
                else:
                    row['status'] = 'out'
                    row['left'] = pytz.utc.localize(last.check_out).astimezone(
                        tz).strftime('%H:%M')
            elif out['holiday'] is not None or start is None:
                row['status'] = 'off'
            elif clock and hour_now > start + NO_PUNCH_AFTER_MIN / 60.0:
                row['status'] = 'missing'
                row['planned'] = '%02d:%02d' % (int(start), round(start % 1 * 60))
            else:
                row['status'] = 'unknown'
            counts[row['status']] += 1
            out['rows'].append(row)
        order = {'missing': 0, 'late': 1, 'leave': 2, 'in': 3, 'out': 4,
                 'unknown': 5, 'off': 6}
        out['rows'].sort(key=lambda r: (order[r['status']], r['name']))
        out['counts'] = counts
        return out

    # ========================================================= the calendar
    @api.model
    def calendar(self, emp, now=None):
        """Who is away over the next four weeks, day by day."""
        team = self.team(emp)
        first = self._local_now(emp, now).date()
        days = [first + timedelta(days=i) for i in range(CALENDAR_DAYS)]
        last = days[-1]
        out = {'days': [], 'rows': [], 'clashes': [], 'size': len(team)}
        if not team:
            return out
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', team.ids), ('state', 'in', LEAVE_LIVE),
            ('request_date_from', '<=', last), ('request_date_to', '>=', first)])
        by_emp = {}
        for lv in leaves:
            by_emp.setdefault(lv.employee_id.id, []).append(lv)
        away_n = [0] * len(days)
        for member in team:
            cells, any_leave = [], False
            for i, d in enumerate(days):
                cell = ''
                for lv in by_emp.get(member.id, []):
                    if lv.request_date_from <= d <= lv.request_date_to:
                        cell = 'asked' if lv.state in LEAVE_ASKED else 'away'
                        if cell == 'away':
                            break
                if cell:
                    away_n[i] += 1
                    any_leave = True
                cells.append(cell)
            out['rows'].append(dict(self._person(member), cells=cells,
                                    any=any_leave))
        out['rows'].sort(key=lambda r: (not r['any'], r['name']))
        limit = max(2, CLASH_SHARE * len(team))
        for i, d in enumerate(days):
            clash = away_n[i] >= limit
            out['days'].append({'date': d, 'weekend': d.weekday() >= 5,
                                'today': i == 0, 'away': away_n[i],
                                'clash': clash})
            if clash:
                out['clashes'].append({'date': d, 'away': away_n[i]})
        return out

    # ============================================================ probation
    @api.model
    def probation(self, emp, now=None):
        """People in the team whose trial period ends within 30 days (or has
        already ended without a decision)."""
        team = self.team(emp)
        if not team or 'pb.probation.review' not in self.env:
            return []
        today = self._local_now(emp, now).date()
        horizon = today + timedelta(days=PROBATION_DAYS)

        def read(Review):
            rows = []
            for member in team:
                if member.pb_probation_state not in ('in_probation', 'extended'):
                    continue
                review = Review.sudo().for_employee(member)
                end = (review.trial_end if review else False) or \
                    member.current_version_id.trial_date_end
                if not end or end > horizon:
                    continue
                rows.append(dict(
                    self._person(member),
                    end=end, days=(end - today).days,
                    extended=member.pb_probation_state == 'extended',
                    stage=dict(review._fields['state'].selection).get(
                        review.state, '') if review else '',
                    mine=bool(review and review.manager_user_id.id == self.env.uid),
                    url='/bizapp/pb.probation.review/%s' % review.id
                        if review else ''))
            rows.sort(key=lambda r: r['end'])
            return rows
        return self._optional('pb.probation.review', read) or []

    # ============================================================== moments
    @api.model
    def moments(self, emp, now=None):
        """Contracts ending, birthdays and work anniversaries coming up."""
        team = self.team(emp)
        today = self._local_now(emp, now).date()
        rows = []
        for member in team:
            version = member.current_version_id
            end = version.contract_date_end if version else False
            if end and today <= end <= today + timedelta(days=CONTRACT_END_DAYS):
                rows.append(dict(self._person(member), kind='contract', date=end,
                                 days=(end - today).days))
            for kind, base in (('birthday', member.birthday),
                               ('anniversary', member.first_contract_date)):
                nxt = self._next_yearly(base, today)
                if not nxt or (nxt - today).days > MOMENT_DAYS:
                    continue
                years = nxt.year - base.year
                if kind == 'anniversary' and years < 1:
                    continue
                rows.append(dict(self._person(member), kind=kind, date=nxt,
                                 days=(nxt - today).days,
                                 years=years if kind == 'anniversary' else 0))
        rows.sort(key=lambda r: (r['date'], r['name']))
        return rows

    @staticmethod
    def _next_yearly(base, today):
        if not base:
            return None
        for year in (today.year, today.year + 1):
            try:
                d = base.replace(year=year)
            except ValueError:          # 29 February
                d = base.replace(year=year, day=28)
            if d >= today:
                return d
        return None

    # ================================================== the chart around me
    @api.model
    def chart(self, emp):
        """My manager, me, and the people who report to me with how many
        report to each of them — the org chart opened at me."""
        team = self.team(emp)
        Emp = self.env['hr.employee'].sudo()
        counts = {}
        if team:
            for row in Emp._read_group(
                    [('parent_id', 'in', team.ids), ('active', '=', True)],
                    ['parent_id'], ['__count']):
                counts[row[0].id] = row[1]
        manager = emp.parent_id
        return {
            'manager': self._person(manager) if manager and manager.active else None,
            'me': self._person(emp),
            'reports': [dict(self._person(m), reports=counts.get(m.id, 0))
                        for m in team],
        }

    # ============================================================ overtime
    @api.model
    def overtime(self, emp, now=None):
        """Overtime this month per person — approved and still asked — against
        the company's monthly limit (0 = no limit set)."""
        team = self.team(emp)
        if not team or 'hr.overtime.request' not in self.env:
            return None
        today = self._local_now(emp, now).date()
        first = today.replace(day=1)

        def read(OT):
            cap = 0.0
            if 'pb.ot.ceiling' in self.env:
                ceil = self.env['pb.ot.ceiling'].sudo()._for_company(emp.company_id)
                cap = float(ceil.monthly_cap or 0.0) if ceil else 0.0
            rows = {}
            for ot in OT.sudo().search([
                    ('employee_id', 'in', team.ids), ('date', '>=', first),
                    ('date', '<=', today),
                    ('state', 'in', ('submitted', 'approved'))]):
                row = rows.setdefault(ot.employee_id.id, {'approved': 0.0,
                                                          'asked': 0.0})
                if ot.state == 'approved':
                    row['approved'] += ot.approved_hours or ot.planned_hours or 0.0
                else:
                    row['asked'] += ot.planned_hours or 0.0
            out = []
            for member in team:
                row = rows.get(member.id)
                if not row:
                    continue
                total = row['approved'] + row['asked']
                out.append(dict(
                    self._person(member), approved=round(row['approved'], 1),
                    asked=round(row['asked'], 1), total=round(total, 1),
                    share=min(100, round(100 * total / cap)) if cap else 0,
                    over=bool(cap and total > cap),
                    near=bool(cap and total >= 0.8 * cap)))
            out.sort(key=lambda r: -r['total'])
            return {'cap': cap, 'month': first, 'rows': out}
        return self._optional('hr.overtime.request', read)

    # ===================================================== missing clock-ins
    @api.model
    def gaps(self, emp, now=None):
        """Working days so far this week with no clock-in and no leave, per
        person. None when the company does not clock in."""
        team = self.team(emp)
        if not team or not self._optional(
                'hr.attendance', lambda M: self._clock_in_use(emp, team)):
            return None
        today = self._local_now(emp, now).date()
        monday = today - timedelta(days=today.weekday())
        days = [monday + timedelta(days=i) for i in range(today.weekday())]
        if not days:
            return {'rows': [], 'since': monday}
        holidays = {d for d in days
                    if self._public_holiday(emp, d) is not None}
        lo = self._utc_range(emp, days[0])[0]
        hi = self._utc_range(emp, days[-1])[1]
        tz = self._tz(emp)
        punched = set()
        for att in self.env['hr.attendance'].sudo().search(
                [('employee_id', 'in', team.ids), ('check_in', '>=', lo),
                 ('check_in', '<', hi)]):
            local = pytz.utc.localize(att.check_in).astimezone(tz).date()
            punched.add((att.employee_id.id, local))
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', team.ids), ('state', 'in', LEAVE_LIVE),
            ('request_date_from', '<=', days[-1]),
            ('request_date_to', '>=', days[0])])
        rows = []
        for member in team:
            missing = []
            for d in days:
                if d in holidays or (member.id, d) in punched:
                    continue
                if self._planned_start(member, d) is None:
                    continue
                if any(lv.employee_id == member and lv.request_date_from <= d
                       <= lv.request_date_to for lv in leaves):
                    continue
                missing.append(d)
            if missing:
                rows.append(dict(self._person(member), days=missing))
        rows.sort(key=lambda r: (-len(r['days']), r['name']))
        return {'rows': rows, 'since': monday}

    # ============================================================ balances
    @api.model
    def balances(self, emp, now=None):
        """Leave still to take, per person, for the counted leave types —
        the two each person has most of."""
        team = self.team(emp)
        if not team:
            return []
        today = self._local_now(emp, now).date()

        def read(LT):
            data = LT.sudo().get_allocation_data(team, today)
            out = []
            for member in team:
                kinds = []
                for row in data.get(member) or []:
                    if len(row) < 4 or row[2] == 'no':
                        continue
                    info = row[1]
                    if not info.get('max_leaves'):
                        continue
                    kinds.append({'type': row[0],
                                  'left': round(float(info.get(
                                      'virtual_remaining_leaves') or 0.0), 1),
                                  'of': round(float(info['max_leaves']), 1),
                                  'unit': info.get('request_unit') or 'day'})
                if kinds:
                    kinds.sort(key=lambda k: -k['of'])
                    out.append(dict(self._person(member), kinds=kinds[:2]))
            out.sort(key=lambda r: -max(k['left'] for k in r['kinds']))
            return out
        return self._optional('hr.leave.type', read) or []

    # ========================================================= new joiners
    @api.model
    def joiners(self, emp, now=None):
        """People who joined in the last 90 days, with their first-weeks
        checklist when there is one."""
        team = self.team(emp)
        today = self._local_now(emp, now).date()
        since = today - timedelta(days=90)
        rows = []
        for member in team:
            start = member.first_contract_date
            if not start or not (since <= start <= today):
                continue
            row = dict(self._person(member), start=start,
                       days=(today - start).days, done=None, total=None,
                       buddy=member.buddy_id.name if 'buddy_id' in member._fields
                       and member.buddy_id else '')
            case = self._optional('pb.journey.case', lambda C: C.sudo().search(
                [('employee_id', '=', member.id)], order='id desc', limit=1),
                need=('employee_id',))
            if case and 'task_ids' in case._fields:
                tasks = case.task_ids
                row['total'] = len(tasks)
                if 'state' in tasks._fields:
                    row['done'] = len(tasks.filtered(
                        lambda t: t.state in ('done', 'skipped')))
            rows.append(row)
        rows.sort(key=lambda r: r['start'], reverse=True)
        return rows

    # ======================================================== I'm away
    @api.model
    def handover(self, emp):
        """My hand-over of approvals: the one in force or coming, and who may
        take it."""
        if self._inbox() is None:
            return None
        Del = self.env['biz.approval.delegation']
        today = fields.Date.context_today(self)
        rows = Del.sudo().search([
            ('principal_user_id', '=', self.env.uid),
            ('state', 'in', ('draft', 'active')),
            ('date_to', '>=', today)], order='date_from')
        companies = self.env.user.company_ids.ids or [self.env.company.id]
        people = self.env['res.users'].sudo().search([
            ('share', '=', False), ('active', '=', True),
            ('id', '!=', self.env.uid), ('company_ids', 'in', companies),
            ('employee_ids', '!=', False)], order='name', limit=300)
        return {
            'rows': [{'id': r.id, 'who': r.delegate_user_id.name or '',
                      'date_from': r.date_from, 'date_to': r.date_to,
                      'reason': r.reason or '',
                      'live': r.date_from <= today} for r in rows],
            'people': [{'id': u.id, 'name': u.name or ''} for u in people],
            'manager_uid': emp.parent_id.user_id.id if emp.parent_id else 0,
            'today': today,
        }

    @api.model
    def set_handover(self, delegate_uid, date_from, date_to, reason):
        """Arrange cover for my own approvals — mine only, as myself (the
        hand-over's own rule lets a person arrange their own)."""
        if self._inbox() is None:
            raise AccessError(self.env._("You cannot hand over approvals."))
        _ = self.env._
        date_from = fields.Date.to_date(date_from or None)
        date_to = fields.Date.to_date(date_to or None)
        if not date_from or not date_to:
            raise UserError(_("Choose the first and the last day you are away."))
        if date_to < fields.Date.context_today(self):
            raise UserError(_("The last day is in the past."))
        try:
            delegate_uid = int(delegate_uid or 0)
        except (TypeError, ValueError):
            delegate_uid = 0
        delegate = self.env['res.users'].sudo().browse(delegate_uid).exists()
        companies = self.env.user.company_ids
        if not delegate or delegate.share or not delegate.active \
                or delegate.id == self.env.uid \
                or not (delegate.company_ids & companies):
            raise UserError(_("Choose who looks after your approvals."))
        reason = (reason or '').strip()[:500] or _('Away')
        row = self.env['biz.approval.delegation'].create({
            'company_id': self.env.company.id,
            'principal_user_id': self.env.uid,
            'delegate_user_id': delegate.id,
            'date_from': date_from,
            'date_to': date_to,
            'reason': reason,
        })
        self.env['biz.approval.event']._log(
            'delegation_changed',
            _("%(a)s is covering for %(b)s",
              a=delegate.name, b=self.env.user.name),
            company=self.env.company, payload={'delegation_id': row.id})
        return row.id

    @api.model
    def end_handover(self, delegation_id):
        row = self.env['biz.approval.delegation'].browse(
            int(delegation_id or 0)).exists()
        if not row or row.principal_user_id.id != self.env.uid:
            raise UserError(self.env._("That hand-over is not yours to stop."))
        row.action_revoke()
        return True

    # ============================================================ home card
    @api.model
    def home_card(self, emp, now=None):
        """The "My team" card's facts, or None for somebody who is not a
        manager."""
        team = self.team(emp)
        turn = self.my_turn_count()
        if not team and not turn:
            return None
        today = self.today(emp, now) if team else None
        return {
            'size': len(team),
            'approvals': turn,
            'today': today,
            'faces': [self._person(m) for m in team[:6]],
            'more_faces': max(0, len(team) - 6),
        }
