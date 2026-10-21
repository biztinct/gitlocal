# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""NAV P3d — Home › Ask HR as a Payobook board.

ONE READ (`get_board`) and ONE WRITE (`act`). Both run AS THE READER — never
sudo — so the record rules decide what is on the board: the HR team sees every
question (`rule_pb_ask_hr_ticket_hr`), anybody else only the questions they
asked themselves (`rule_pb_ask_hr_ticket_own`). An employee holds read access
only, so `act` refuses them before a single record is touched, and the model's
own ACL would refuse them anyway.

`act` never changes a state by itself: every verb calls the method the native
form calls (`action_take`, `action_hand_to`, `action_close_with_note`), so the
board and the form cannot drift apart.

The median first reply is a plain number, not a service level: over the
questions asked in the last 30 days, the time from asking to HR's first public
answer (or to "Mark answered" when HR answered another way). No targets, no
pauses, labelled as exactly that.
"""
import statistics
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext

from .ticket import OPEN_STATES, STATES

#: Steps of the board, in order. A question is at exactly one of them.
STEP_KEYS = [key for key, _label in STATES]

#: How many closed questions the board carries (the count is always exact).
CLOSED_CAP = 60
#: A safety cap on open questions (a queue this long is a different problem).
OPEN_CAP = 500
#: The window of the median first reply, in days.
MEDIAN_DAYS = 30
#: A new question nobody has moved for more than this many working days is
#: amber on the board.
LATE_WORKING_DAYS = 2


def _working_days_between(start, end):
    """Monday-to-Friday days from ``start`` (a date) up to, not including,
    ``end`` (a date). Two days on a Thursday for a Tuesday question."""
    if not start or not end or end <= start:
        return 0
    days, cur = 0, start
    while cur < end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return days


class PbAskHr(models.AbstractModel):
    _name = 'pb.ask.hr'
    _description = 'Ask HR board'

    # ------------------------------------------------------------ who reads
    @api.model
    def _can_act(self):
        """The HR team (and administrators): the people the model lets write."""
        return self.env['pb.ask.hr.ticket'].has_access('write')

    @api.model
    def _can_ask(self):
        """Does the reader have an employee record to ask from?"""
        return bool(self.env['hr.employee.public'].search_count(
            [('user_id', '=', self.env.uid)], limit=1))

    # -------------------------------------------------------------- words
    @api.model
    def _span_words(self, seconds):
        """A length of time in the reader's language: "2 hours", "3 days"."""
        _ = self.env._
        if seconds < 3600:
            return _('less than an hour')
        hours = int(seconds // 3600)
        if hours < 24:
            return _('1 hour') if hours == 1 else _('%s hours', hours)
        days = int(seconds // 86400)
        return _('1 day') if days == 1 else _('%s days', days)

    @api.model
    def _median_words(self, seconds):
        _ = self.env._
        if seconds < 86400:
            hours = max(1, round(seconds / 3600))
            return _('1 hour') if hours == 1 else _('%s hours', hours)
        days = round(seconds / 86400, 1)
        if days == int(days):
            days = int(days)
        if days == 1:
            return _('1 day')
        # the reader's decimal mark: "1.4" in English, "1,4" in Vietnamese
        point = self.env['res.lang']._get_data(code=self.env.lang or 'en_US').decimal_point or '.'
        return _('%s days', str(days).replace('.', point))

    # ---------------------------------------------------------- the median
    @api.model
    def _first_replies(self, tickets):
        """{ticket id: when HR first answered}. HR's first PUBLIC comment
        (`_pb_public_messages` — never a note), or "Mark answered" when it
        came first; read through the reader's own access to the questions."""
        out = {}
        for ticket in tickets:
            employee = ticket._pb_employee_partners()
            first = False
            for msg in ticket._pb_public_messages():
                if not (msg.author_id & employee):
                    first = msg.date
                    break
            if ticket.answered_on and (not first or ticket.answered_on < first):
                first = ticket.answered_on
            if first:
                out[ticket.id] = first
        return out

    @api.model
    def _median_first_reply(self, now):
        Ticket = self.env['pb.ask.hr.ticket']
        asked = Ticket.search([('create_date', '>=', now - timedelta(days=MEDIAN_DAYS))])
        firsts = self._first_replies(asked)
        spans = [max(0.0, (firsts[t.id] - t.create_date).total_seconds())
                 for t in asked if t.id in firsts]
        if not spans:
            return {'n': 0, 'words': ''}
        median = statistics.median(spans)
        return {'n': len(spans), 'seconds': median, 'words': self._median_words(median)}

    # --------------------------------------------------------------- cards
    @api.model
    def _person_rows(self, employees):
        """Name and department of each asker, read through the PUBLIC
        employee model (readable by every internal user; the private one is
        the HR team's)."""
        out = {}
        try:
            for pub in self.env['hr.employee.public'].browse(employees.ids).exists():
                out[pub.id] = {'department': pub.department_id.display_name or ''}
        except AccessError:
            out = {}
        return out

    @api.model
    def _card(self, ticket, ctx):
        _ = self.env._
        now = ctx['now']
        categories = ctx['categories']
        person = ctx['people'].get(ticket.employee_id.id, {})
        text = html2plaintext(ticket.description or '').strip()
        line = ' '.join(text.split())
        if line == (ticket.name or '').strip():
            line = ''   # the question is its subject: say it once
        if len(line) > 160:
            line = line[:157].rstrip() + '…'
        asked = ticket.create_date or now
        late = bool(ticket.state == 'new' and _working_days_between(
            ctx['local'](asked), ctx['today']) > LATE_WORKING_DAYS)
        last_by = ticket.last_public_by
        if ctx['can_act']:
            # HR reads it: the person wrote last and it is waiting on HR
            unread = bool(last_by == 'employee' and ticket.state in ('new', 'with_hr'))
        else:
            # the person reads it: HR answered and it is their turn
            unread = bool(last_by == 'hr' and ticket.state == 'answered')
        owner = ticket.user_id
        return {
            'id': ticket.id,
            'number': ticket.number or '',
            'subject': ticket.name or '',
            'line': line,
            'state': ticket.state,
            'category': ticket.category or 'other',
            'category_label': categories.get(ticket.category or 'other', ''),
            'employee_id': ticket.employee_id.id,
            'person': ticket.employee_name or '',
            'department': person.get('department', ''),
            'initials': ticket._pb_initials(ticket.employee_name),
            'owner_id': owner.id or 0,
            'owner': owner.name or '',
            'mine': bool(owner and owner.id == self.env.uid),
            'age': self._span_words((now - asked).total_seconds()),
            'asked_on': fields.Datetime.to_string(asked),
            'late': late,
            'answered_week': bool(ticket.answered_on
                                  and ticket.answered_on >= ctx['week_start']),
            'unread': unread,
            'unread_words': (_('They replied') if ctx['can_act'] else _('HR replied'))
            if unread else '',
        }

    @api.model
    def _week_start(self, today):
        """Monday 00:00 of this week in the reader's time zone, as UTC."""
        monday = today - timedelta(days=today.weekday())
        try:
            tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        except pytz.UnknownTimeZoneError:
            tz = pytz.UTC
        return tz.localize(datetime.combine(monday, time.min)).astimezone(
            pytz.UTC).replace(tzinfo=None)

    # ---------------------------------------------------------------- read
    @api.model
    def get_board(self):
        """Everything Home › Ask HR draws, in the reader's language."""
        _ = self.env._
        Ticket = self.env['pb.ask.hr.ticket']
        Ticket.check_access('read')
        can_act = self._can_act()
        now = fields.Datetime.now()
        local = lambda dt: fields.Datetime.context_timestamp(self, dt).date()  # noqa: E731
        today = local(now)

        counts = dict.fromkeys(STEP_KEYS, 0)
        for state, count in Ticket._read_group([], ['state'], ['__count']):
            if state in counts:
                counts[state] = count

        open_tickets = Ticket.search([('state', 'in', OPEN_STATES)],
                                     order='create_date desc, id desc', limit=OPEN_CAP)
        closed = Ticket.search([('state', '=', 'closed')],
                               order='closed_on desc, id desc', limit=CLOSED_CAP)
        tickets = open_tickets | closed
        categories = dict(Ticket._fields['category']._description_selection(self.env))
        week_start = self._week_start(today)
        ctx = {
            'now': now, 'local': local, 'today': today, 'can_act': can_act,
            'week_start': week_start,
            'categories': categories,
            'people': self._person_rows(tickets.employee_id),
        }
        cards = [self._card(t, ctx) for t in open_tickets] \
            + [self._card(t, ctx) for t in closed]

        new_late = sum(1 for c in cards if c['late'])
        mine_with_hr = sum(1 for c in cards if c['mine'] and c['state'] == 'with_hr')
        unowned = sum(1 for c in cards if not c['owner_id'] and c['state'] in OPEN_STATES)

        answered_week = Ticket.search_count([('answered_on', '>=', week_start)])

        last = Ticket.search([('answered_on', '!=', False)], order='answered_on desc', limit=1)
        last_words = ''
        if last:
            last_words = _('Last question answered %s ago.',
                           self._span_words((now - last.answered_on).total_seconds()))

        board = {
            'can_act': can_act,
            'can_ask': self._can_ask(),
            'me': self.env.uid,
            'counts': counts,
            'total': sum(counts.values()),
            'open_total': sum(counts[k] for k in OPEN_STATES),
            'new_late': new_late,
            'mine_with_hr': mine_with_hr,
            'unowned': unowned,
            'answered_week': answered_week,
            'last_answered_words': last_words,
            'closed_shown': len(closed),
            'closed_capped': counts['closed'] > len(closed),
            'cards': cards,
            'categories': [{'key': k, 'label': v} for k, v in categories.items()],
        }
        if can_act:
            board['median'] = self._median_first_reply(now)
        return board

    @api.model
    def get_owners(self):
        """The people a question can be handed to: active internal users in
        the HR team (or administrators) of the companies being looked at."""
        if not self._can_act():
            raise AccessError(self.env._('Only the HR team can hand a question on.'))
        groups = [g.id for g in (self.env.ref('hr.group_hr_user', raise_if_not_found=False),
                                 self.env.ref('base.group_system', raise_if_not_found=False)) if g]
        users = self.env['res.users'].search([
            ('share', '=', False), ('active', '=', True),
            ('all_group_ids', 'in', groups),
            ('company_ids', 'in', self.env.companies.ids),
        ], order='name', limit=200)
        rows = [{'id': u.id, 'name': u.name, 'me': u.id == self.env.uid} for u in users]
        rows.sort(key=lambda r: (not r['me'], r['name'].lower()))
        return rows

    # --------------------------------------------------------------- write
    @api.model
    def act(self, verb, payload=None):
        """Take it / Hand to… / Close with a note, on one card or several.

        ``payload``: ``{'ids': [...], 'user_id': id, 'note': str,
        'tell': bool}``. Returns what happened in words for the toast."""
        _ = self.env._
        payload = payload or {}
        if not self._can_act():
            raise AccessError(_('Only the HR team can do that.'))
        ids = [int(i) for i in (payload.get('ids') or []) if str(i).isdigit()]
        # as the reader: a question they cannot read is not touched
        tickets = self.env['pb.ask.hr.ticket'].search([('id', 'in', ids)])
        if not tickets:
            raise UserError(_('Those questions are no longer here. Read the board again.'))
        if verb == 'take':
            todo = tickets.filtered(lambda t: t.state != 'closed')
            todo.action_take()
        elif verb == 'hand':
            todo = tickets.filtered(lambda t: t.state != 'closed')
            todo.action_hand_to(payload.get('user_id'))
        elif verb == 'close':
            todo = tickets.filtered(lambda t: t.state != 'closed')
            todo.action_close_with_note(payload.get('note'), bool(payload.get('tell')))
        else:
            raise UserError(_('That is not something this board can do.'))
        skipped = len(tickets) - len(todo)
        n = len(todo)
        if verb == 'take':
            words = _('You have it.') if n == 1 else _('You have %s questions.', n)
        elif verb == 'hand':
            owner = self.env['res.users'].browse(int(payload.get('user_id') or 0))
            words = (_('Handed to %s.', owner.name) if n == 1
                     else _('%(n)s questions handed to %(name)s.', n=n, name=owner.name))
        else:
            words = _('Closed.') if n == 1 else _('%s questions closed.', n)
        if skipped:
            words = '%s %s' % (words, _('%s already closed, left as they were.', skipped)
                               if skipped > 1 else _('1 already closed, left as it was.'))
        return {'done': n, 'skipped': skipped, 'message': words}
