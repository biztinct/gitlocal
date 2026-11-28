# -*- coding: utf-8 -*-
"""Home › TEAM — one screen for somebody who manages people (NAV P3c).

WHO "MY TEAM" IS. The product has three answers (the whole branch under me,
the people whose requests wait on my seat, my direct reports). TEAM uses the
narrowest one for PEOPLE: the active employees whose manager (`parent_id`) is
an employee record of mine — the same rule as the goals and probation record
rules and `pb.my.training.team()`. Decisions are the other answer: what waits
on MY seat in the one inbox, read as me.

WHAT THIS READS. Every other module is asked through `self.env.get(...)` and a
savepoint, so this module gains no dependency and a database without, say,
Probation simply has no Probation key in the payload (absent, not zero). Reads
run as the system but every domain is pinned to the report ids or to my own
uid — the boundary is written in the search, never assumed.

WHAT THIS NEVER SENDS. No amount, salary, wage, budget or cost; no growth-plan
anything; no red flags, no training detail from a probation row; nobody who is
not one of my direct reports. `test_team_p3c` walks the whole payload for the
forbidden words.
"""
import base64
import logging
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)

#: pb_today's own state tuples (pb_today/models/pb_today.py:73-74), restated
#: because importing them would make this module depend on pb_today.
_PLANNED_STATES = ('published', 'completed')
_APPROVED_LEAVE_STATES = ('validate', 'validate1')

#: The manager's part of a probation review (probation_board.js `flowStepOf`
#: "talk"): putting the answers together, the 1:1, and the recommendation.
_PROBATION_MINE = ('consolidation', 'one_on_one', 'verdict')
#: A recommendation that has gone to the HR lead or the CEO is theirs now.
_PROBATION_NOT_MINE_GATES = ('hr', 'ceo', 'approved')

#: Hiring requests still in flight (pb_hiring REQUEST_STATES), and the two in
#: which the manager is the one who has to write it.
_HIRING_OPEN = ('asked', 'writing', 'sent_in', 'hr_ok')
_HIRING_ON_ME = ('asked', 'writing')

#: Look-ahead windows for "due": a monthly check-in within a week, a goal
#: review within two weeks. Anything already late is always shown.
_CHECKIN_AHEAD_DAYS = 7
_REVIEW_AHEAD_DAYS = 14

#: Rows per conversation list before "+N more", and avatars before "+N".
ROW_CAP = 5
PEOPLE_CAP = 40

#: The inbox areas (biz_approval_workflow/models/process.py AREAS).
_AREAS = ('pay', 'money', 'data', 'people', 'time', 'setup', 'platform',
          'other')

#: The "Waiting on you" tiles, in screen order. Each card lands on exactly one.
TILE_ORDER = ('time_off', 'overtime', 'expenses', 'people', 'other')


def _short_name(name):
    """The given name — the last word of a Vietnamese name — or the whole
    name when it is two words or fewer (pb_payruns `_short_name`)."""
    words = (name or '').replace('DEMO ', '', 1).split()
    return ' '.join(words) if len(words) <= 2 else words[-1]


def _initials(name):
    words = [w for w in (name or '').replace('DEMO ', '', 1).split() if w]
    if not words:
        return ''
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def _has_photo(emp):
    """A real picture, not the one-letter SVG the employee record makes
    for itself when nobody uploaded one (hr_employee.py `_avatar_generate_svg`)."""
    raw = emp.image_128
    if not raw:
        return False
    head = base64.b64decode(raw[:24] if isinstance(raw, bytes) else
                            raw[:24].encode())
    return not head.lstrip().startswith((b'<?xml', b'<svg'))


def _tile_of(card):
    """Which "Waiting on you" tile one inbox card belongs to."""
    key = card.get('process_key') or ''
    area = card.get('area') or 'other'
    if key == 'leave':
        return 'time_off'
    if area == 'time':
        return 'overtime'
    if key in ('expense', 'trip'):
        return 'expenses'
    if area == 'people':
        return 'people'
    return 'other'


class PbHomeTeam(models.AbstractModel):
    _name = 'pb.home.team'
    _description = 'Home: my team'

    # ================================================================ guards
    def _safe(self, label, fn, default=None):
        """One read in a savepoint. A failed statement poisons the whole
        transaction on this platform, so a swallowed error needs one."""
        try:
            with self.env.cr.savepoint():
                return fn()
        except AccessError:
            _logger.debug('pb.home.team: %s not readable by uid %s',
                          label, self.env.uid)
            return default
        except Exception:                               # noqa: BLE001
            _logger.warning('pb.home.team: %s fell back', label,
                            exc_info=True)
            return default

    def _model(self, name):
        """`env[name]` when that module is installed, else None."""
        return self.env.get(name)

    # ================================================================ who
    @api.model
    def _report_domain(self):
        return [('parent_id.user_id', '=', self.env.uid),
                ('active', '=', True)]

    @api.model
    def can_open(self):
        """The lens probe: does anybody report to me? Never raises."""
        try:
            return bool(self.env['hr.employee'].sudo().search_count(
                self._report_domain(), limit=1))
        except Exception:                               # noqa: BLE001
            return False

    @api.model
    def _reports(self):
        companies = self.env.companies.ids or [self.env.company.id]
        return self.env['hr.employee'].sudo().search(
            self._report_domain() + [('company_id', 'in', companies)],
            order='name, id')

    # ================================================================ words
    @api.model
    def _day(self, d, pattern='EEE d MMM'):
        if not d:
            return ''
        return self._safe('a date', lambda: format_date(
            self.env, d, date_format=pattern), default=d.strftime('%a %d %b'))

    @api.model
    def _when(self, d, today):
        """"due today" / "due tomorrow" / "due Thu 22 Oct" / "6 days late"."""
        if not d:
            return ''
        days = (d - today).days
        if days < -1:
            return _('%(n)s days late', n=-days)
        if days == -1:
            return _('1 day late')
        if days == 0:
            return _('due today')
        if days == 1:
            return _('due tomorrow')
        return _('due %(day)s', day=self._day(d))

    # ================================================================ the call
    @api.model
    def get_team(self):
        """Everything Home › TEAM draws, in one call. Raises nothing."""
        today = fields.Date.context_today(self)
        reports = self._safe('the reports', self._reports,
                             self.env['hr.employee'].sudo().browse())
        ids = set(reports.ids)
        st = {'today': today, 'reports': reports, 'ids': ids,
              'now': fields.Datetime.now()}

        people = self._safe('today', lambda: self._today(st), None)
        if people is None:
            people = self._today_plain(st)
        out = {
            'today': fields.Date.to_string(today),
            'today_label': self._day(today, 'EEEE d MMMM'),
            'size': len(reports),
            'people': people['rows'][:PEOPLE_CAP],
            'people_more': max(0, len(people['rows']) - PEOPLE_CAP),
            'counts': people['counts'],
            'can_360': bool(self._safe('the 360 gate', self._can_360, False)),
        }
        sections = (
            ('decisions', 'pb.approval.inbox', self._decisions),
            ('probation', 'pb.probation.review', self._probation),
            ('goals', 'pb.goal.checkin', self._goals),
            ('training', 'pb.my.training', self._training),
            ('hiring', 'pb.hiring.requisition', self._hiring),
        )
        for key, model, fn in sections:
            if self._model(model) is None:
                continue                    # not installed: absent, not zero
            value = self._safe(key, lambda fn=fn: fn(st), None)
            if value is not None:
                out[key] = value
        out['due_total'] = self._due_total(out)
        return out

    @api.model
    def _due_total(self, out):
        """How many things on this screen ask the reader to act."""
        n = (out.get('decisions') or {}).get('total', 0)
        n += (out.get('probation') or {}).get('total', 0)
        n += (out.get('goals') or {}).get('total', 0)
        n += (out.get('training') or {}).get('overdue_people', 0)
        n += (out.get('hiring') or {}).get('on_me', 0)
        return n

    # ================================================================ today
    @api.model
    def _person(self, emp):
        return {
            'id': emp.id,
            'name': emp.name or '',
            'short': _short_name(emp.name),
            'initials': _initials(emp.name),
            # The public record: every internal user may read its picture.
            # Only a real photo is drawn; without one the face is the
            # person's initials (the generated avatar is one letter, and
            # "D" for every "DEMO …" name says nothing).
            'avatar': ('/web/image/hr.employee.public/%s/avatar_128' % emp.id
                       if self._safe('a photo', lambda: _has_photo(emp),
                                     False) else ''),
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '')
            or '',
        }

    @api.model
    def _works_today(self, emp, today):
        cal = emp.resource_calendar_id
        if not cal:
            return True
        return bool(self._safe('a working calendar',
                               lambda: cal._works_on_date(today), True))

    @api.model
    def _leaves_today(self, st):
        """{employee id: hr.leave} — approved leave covering today."""
        Leave = self._model('hr.leave')
        if Leave is None or not st['ids']:
            return {}
        start = datetime.combine(st['today'], time.min)
        end = datetime.combine(st['today'], time.max)
        rows = Leave.sudo().search([
            ('employee_id', 'in', list(st['ids'])),
            ('state', 'in', _APPROVED_LEAVE_STATES),
            ('date_from', '<=', end), ('date_to', '>=', start),
        ])
        out = {}
        for lv in rows:
            out.setdefault(lv.employee_id.id, lv)
        return out

    @api.model
    def _punches_today(self, st):
        """{employee id: [hr.attendance]} for today, first punch first."""
        Att = self._model('hr.attendance')
        if Att is None or not st['ids']:
            return {}
        start = datetime.combine(st['today'], time.min)
        end = datetime.combine(st['today'], time.max)
        rows = Att.sudo().search([
            ('employee_id', 'in', list(st['ids'])),
            ('check_in', '>=', start), ('check_in', '<=', end),
        ], order='check_in')
        out = {}
        for a in rows:
            out.setdefault(a.employee_id.id, []).append(a)
        return out

    @api.model
    def _shifts_today(self, st):
        Shift = self._model('hr.shift.planning')
        if Shift is None or not st['ids']:
            return {}
        rows = Shift.sudo().search([
            ('employee_id', 'in', list(st['ids'])),
            ('date', '=', st['today']),
            ('state', 'in', _PLANNED_STATES),
        ])
        out = {}
        for s in rows:
            out.setdefault(s.employee_id.id, []).append(s)
        return out

    @api.model
    def _today(self, st):
        """Who is in, late, not started, on leave or off — the Today board's
        own state words, computed over my reports only.

        With `pb_today` installed its row builder decides the state and the
        lateness (one rule for both screens); without it the punches and the
        leave decide, and nobody is ever called late."""
        Today = self._model('pb.today')
        leaves = self._leaves_today(st)
        punches = self._punches_today(st)
        shifts = self._shifts_today(st) if Today is not None else {}
        Rule = self._model('pb.attendance.rule')
        grace = {}
        rows = []
        counts = {'in': 0, 'late': 0, 'not_started': 0, 'on_leave': 0,
                  'off': 0}
        now = st['now']
        for emp in st['reports']:
            row = self._person(emp)
            leave = leaves.get(emp.id)
            state, late, minutes = None, False, 0
            check_in = ''
            if Today is not None:
                cid = emp.company_id.id
                if cid not in grace:
                    grace[cid] = (self._safe(
                        'the grace minutes',
                        lambda: Rule._grace_for_company(emp.company_id)[0],
                        0) if Rule is not None else 0) or 0
                built = Today.sudo()._row(
                    emp, shifts.get(emp.id) or [], punches.get(emp.id) or [],
                    leave, grace[cid], now, True, None)
                state = built['state']
                late = bool(built['is_late'])
                minutes = int(built['minutes_late'] or 0)
                check_in = built.get('check_in') or ''
            else:
                state, check_in = self._plain_state(
                    emp, punches.get(emp.id) or [], leave)
            if state == 'not_started' and not shifts.get(emp.id) \
                    and not self._works_today(emp, st['today']):
                state = 'off'
            row.update(self._status(state, late, minutes, check_in, leave))
            rows.append(row)
            # The hero's numbers add up to the strip: every person is in
            # exactly one bucket; "late" is a second look across two of them.
            counts[row['bucket']] += 1
            if row['status'] == 'late':
                counts['late'] += 1
        return {'rows': rows, 'counts': counts}

    @api.model
    def _plain_state(self, emp, atts, leave):
        last = atts[-1] if atts else None
        check_in = ''
        if atts:
            check_in = self._safe('a time', lambda: fields.Datetime.context_timestamp(
                self, atts[0].check_in).strftime('%H:%M'), '')
        if last and not last.check_out:
            return 'on_shift', check_in
        if last:
            return 'checked_out', check_in
        if leave:
            return 'on_leave', ''
        return 'not_started', ''

    @api.model
    def _status(self, state, late, minutes, check_in, leave):
        """The four dots — in (green), late (amber), not yet (grey), on leave
        (blue) — plus off today, and the sentence the tooltip reads."""
        if state in ('on_shift', 'checked_out'):
            bucket = 'in'
        elif state in ('on_leave', 'off'):
            bucket = state
        else:
            bucket = 'not_started'
        status = 'late' if late and bucket in ('in', 'not_started') else bucket
        until = ''
        if leave:
            end = leave.request_date_to or (leave.date_to and leave.date_to.date())
            until = self._day(end) if end else ''
        if status == 'late' and bucket == 'not_started':
            words = _('late, not in yet (%(n)s min)', n=minutes)
        elif status == 'late':
            words = _('late %(n)s min', n=minutes)
        elif state == 'checked_out':
            words = _('in today, has left')
        elif bucket == 'in':
            words = (_('in since %(time)s', time=check_in) if check_in
                     else _('in today'))
        elif bucket == 'on_leave':
            words = (_('on leave until %(day)s', day=until) if until
                     else _('on leave'))
        elif bucket == 'off':
            words = _('not working today')
        else:
            words = _('not started yet')
        return {'status': status, 'bucket': bucket,
                'minutes_late': minutes if status == 'late' else 0,
                'words': words}

    @api.model
    def _today_plain(self, st):
        """The strip when even the plain read failed: names, no states."""
        rows = []
        for emp in st['reports']:
            row = self._person(emp)
            row.update({'status': 'not_started', 'bucket': 'not_started',
                        'minutes_late': 0, 'words': _('not started yet')})
            rows.append(row)
        return {'rows': rows, 'counts': {
            'in': 0, 'late': 0, 'not_started': len(rows), 'on_leave': 0,
            'off': 0}}

    @api.model
    def _can_360(self):
        """The People screen's person drawer reads as HR only."""
        People = self._model('pb.people')
        if People is None or not hasattr(People, '_vault_is_hr'):
            return False
        return People._vault_is_hr()

    # ============================================================ decisions
    @api.model
    def _decisions(self, st):
        """What waits on MY seat, counted by tile. Read as me, my scope only:
        the team scope reads as the system and can carry payroll amounts, so
        it is never asked for here, and no card amount leaves this method."""
        inbox = self._model('pb.approval.inbox').list_requests(
            tab='mine', filters={}, cursor=None, scope='me')
        tiles = {key: {'key': key, 'n': 0, 'areas': set()}
                 for key in TILE_ORDER}
        for card in inbox.get('cards') or ():
            if not card.get('mine'):
                continue
            tile = tiles[_tile_of(card)]
            tile['n'] += 1
            tile['areas'].add(card.get('area') or 'other')
        out = []
        for key in TILE_ORDER:
            tile = tiles[key]
            # One filter the inbox can draw: the area every card here shares.
            area = next(iter(tile['areas'])) if len(tile['areas']) == 1 else ''
            out.append({'key': key, 'n': tile['n'],
                        'area': area if area in _AREAS else ''})
        return {
            'total': int((inbox.get('counts') or {}).get('mine') or 0),
            'tiles': out,
        }

    # ============================================================ probation
    @api.model
    def _probation(self, st):
        Review = self._model('pb.probation.review').sudo()
        if not st['ids']:
            return {'rows': [], 'more': 0, 'total': 0, 'door': ''}
        domain = [('manager_user_id', '=', self.env.uid),
                  ('employee_id', 'in', list(st['ids'])),
                  ('state', 'in', _PROBATION_MINE)]
        if 'pb_gate' in Review._fields:
            domain.append(('pb_gate', 'not in', _PROBATION_NOT_MINE_GATES))
        rows = Review.search(domain, order='trial_end, id')
        today = st['today']
        out = []
        for rev in rows:
            emp = rev.employee_id
            due = rev.trial_end
            if rev.state == 'one_on_one':
                what = _('the 1:1 conversation')
                talk = rev.one_on_one_checkin_id
                if talk and talk.scheduled_date:
                    due = talk.scheduled_date
                when = self._when(due, today) if due else _('to arrange')
            else:
                what = (_('read what colleagues said')
                        if rev.state == 'consolidation'
                        else _('your recommendation'))
                when = (_('trial ends %(day)s', day=self._day(due))
                        if due else '')
            out.append({
                'review_id': rev.id,
                'employee_id': emp.id,
                'name': emp.name or '',
                'short': _short_name(emp.name),
                'what': what,
                'when': when,
                'late': bool(due and due < today),
            })
        Board = self._model('pb.probation')
        can_board = bool(self._safe(
            'the probation board gate', lambda: Board._can_read(), False)) \
            if Board is not None else False
        # A plain line manager has no screen to open here: the board is the
        # HR team's, and the review's own form refuses them on a field
        # (`feedback_request_ids`, a lifecycle-group model) — found in the
        # P3c walk. So the rows say what is due and the card says who runs
        # it, rather than offering a door that ends on "no access".
        return {'rows': out[:ROW_CAP], 'more': max(0, len(out) - ROW_CAP),
                'total': len(out), 'door': 'board' if can_board else ''}

    # ================================================================ goals
    @api.model
    def _goals(self, st):
        if not st['ids']:
            return {'rows': [], 'more': 0, 'total': 0, 'can_board': False}
        today = st['today']
        mine = [('manager_user_id', '=', self.env.uid),
                ('employee_id', 'in', list(st['ids'])),
                ('cycle_id.state', '!=', 'closed')]
        rows = []
        Checkin = self._model('pb.goal.checkin').sudo()
        for row in Checkin.search(mine + [
                ('state', 'in', ('planned', 'missed')),
                ('scheduled_date', '<=',
                 today + timedelta(days=_CHECKIN_AHEAD_DAYS))],
                order='scheduled_date, id'):
            missed = row.state == 'missed'
            late = missed or bool(row.scheduled_date
                                  and row.scheduled_date < today)
            if missed:
                when = _('missed')
            else:
                when = self._when(row.scheduled_date, today)
            rows.append({
                'kind': 'checkin', 'id': row.id, 'set_id': row.set_id.id,
                'employee_id': row.employee_id.id,
                'name': row.employee_id.name or '',
                'short': _short_name(row.employee_id.name),
                'what': _('monthly conversation'),
                'when': when, 'late': late,
                'sort': row.scheduled_date or today,
            })
        Review = self._model('pb.goal.review')
        if Review is not None:
            for row in Review.sudo().search(mine + [
                    ('state', '=', 'planned'),
                    ('due_date', '<=',
                     today + timedelta(days=_REVIEW_AHEAD_DAYS))],
                    order='due_date, id'):
                rows.append({
                    'kind': 'review', 'id': row.id, 'set_id': row.set_id.id,
                    'employee_id': row.employee_id.id,
                    'name': row.employee_id.name or '',
                    'short': _short_name(row.employee_id.name),
                    'what': (_('half-way review') if row.kind == 'mid_year'
                             else _('end-of-year review')),
                    'when': self._when(row.due_date, today),
                    'late': bool(row.due_date and row.due_date < today),
                    'sort': row.due_date or today,
                })
        rows.sort(key=lambda r: (not r['late'], r['sort'], r['name']))
        for r in rows:
            r.pop('sort', None)
        Goals = self._model('pb.goals')
        can_board = bool(self._safe(
            'the goals board gate', lambda: Goals.can_open(), False)) \
            if Goals is not None else False
        return {'rows': rows[:ROW_CAP], 'more': max(0, len(rows) - ROW_CAP),
                'total': len(rows), 'can_board': can_board}

    # ============================================================= training
    @api.model
    def _training(self, st):
        """`pb.my.training.team()` — the manager's own training page's read —
        cut down to counts and the names of who is past their date."""
        team = self._model('pb.my.training').team() or {}
        rows = [r for r in team.get('rows') or ()
                if r.get('state') == 'overdue']
        people = []
        seen = set()
        for r in rows:
            if r.get('employee_id') in seen:
                continue
            seen.add(r.get('employee_id'))
            people.append({
                'employee_id': r.get('employee_id'),
                'name': r.get('who') or '',
                'short': _short_name(r.get('who')),
                'course': r.get('course') or '',
                'days_over': int(r.get('days_over') or 0),
            })
        # LEARNING L6: two more quiet chips — certificates of my people that
        # run out within 30 days, and course / more-time requests whose live
        # step waits on me. Counts and names only (no amounts).
        expiring = team.get('expiring_certs') or {}
        waiting = team.get('waiting_on_me') or {}
        return {
            'overdue': int(team.get('overdue') or 0),
            'overdue_people': len(people),
            'due': int(team.get('due') or 0),
            'done': int(team.get('done') or 0),
            'people': people[:ROW_CAP],
            'more': max(0, len(people) - ROW_CAP),
            'expiring': int(expiring.get('count') or 0),
            'expiring_names': [_short_name(n) for n in
                               (expiring.get('names') or [])][:ROW_CAP],
            'waiting': int(waiting.get('count') or 0),
        }

    # =============================================================== hiring
    @api.model
    def _hiring(self, st):
        Req = self._model('pb.hiring.requisition').sudo()
        if 'request_state' not in Req._fields:
            return None
        uid = self.env.uid
        companies = self.env.companies.ids or [self.env.company.id]
        domain = ['|', ('requested_by_user_id', '=', uid),
                  ('asked_user_id', '=', uid),
                  ('request_state', 'in', _HIRING_OPEN),
                  ('company_id', 'in', companies)]
        labels = {
            'asked': _('Waiting for you to write it'),
            'writing': _('You are writing it'),
            'sent_in': _('Sent in, with HR'),
            'hr_ok': _('HR agreed, waiting for the final yes'),
        }
        out = []
        for req in Req.search(domain, order='id desc'):
            mine = (req.requested_by_user_id.id == uid
                    or req.asked_user_id.id == uid
                    or (req.reporting_manager_id
                        and req.reporting_manager_id.user_id.id == uid))
            if req.is_confidential and not mine:
                continue
            on_me = (req.request_state in _HIRING_ON_ME
                     and (req.asked_user_id.id == uid
                          or (not req.asked_user_id
                              and req.requested_by_user_id.id == uid)))
            # The page a manager writes the request on is the link the
            # "please write it" email carries (`/hiring/r/<token>`, the link
            # is the credential). It is handed only to the person it was
            # sent to, and only while it is theirs to write.
            token = req.request_token if on_me and 'request_token' in \
                req._fields else ''
            out.append({
                'id': req.id,
                'write_url': ('/hiring/r/%s' % token) if token else '',
                'title': req.title or req.name or '',
                'ref': req.name or '',
                'state': req.request_state,
                'state_word': labels.get(req.request_state, ''),
                'on_me': bool(on_me),
                'wanted_by': self._day(req.target_start_date)
                if req.target_start_date else '',
            })
        out.sort(key=lambda r: (not r['on_me'], -r['id']))
        Hiring = self._model('pb.hiring')
        can_open = bool(self._safe(
            'the hiring gate', lambda: Hiring.can_open(), False)) \
            if Hiring is not None else False
        return {'rows': out[:ROW_CAP], 'more': max(0, len(out) - ROW_CAP),
                'on_me': sum(1 for r in out if r['on_me']),
                'can_open': can_open}
