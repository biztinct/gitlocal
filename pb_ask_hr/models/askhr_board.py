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


#: Cards per page on the filtered list ("Show N more" brings the next).
PAGE_SIZE = 60
#: Sections whose values are employees: counted as the reader, NAMED through
#: the public employee model (the private one is the HR team's).
PUBLIC_LABELS = ('asker',)


class PbAskHr(models.AbstractModel):
    _name = 'pb.ask.hr'
    _description = 'Ask HR board'
    # The shared filter panel (pb_filter_kit, FILTER wave 4). The searches are
    # never sudoed: the record rules split the HR team (every question) from
    # everybody else (their own), so every count beside a value is the
    # reader's own and no wider.
    _inherit = ['pb.filter.mixin']

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

    # ------------------------------------------------------- the filter panel
    # The board used to load up to 500 open and 60 closed questions and filter
    # them in the browser (one step at a time). The panel now counts on the
    # server over every question the reader may see, the step strip is a
    # filter in it, and the cards come one page at a time. `get_board` stays
    # as it was for anything else that reads it (R4).

    def _pbf_model(self):
        return 'pb.ask.hr.ticket'

    def _pbf_screen(self):
        return 'askhr'

    def _pbf_base_domain(self):
        return []

    def _pbf_search_fields(self):
        return ['number', 'name', 'employee_name', 'description',
                'employee_id.department_id.name']

    def _pbf_sorts(self):
        _ = self.env._
        return [
            {'key': 'newest', 'label': _('Newest first'),
             'order': 'create_date desc, id desc'},
            {'key': 'oldest', 'label': _('Waiting longest first'),
             'order': 'create_date asc, id asc'},
            {'key': 'active', 'label': _('Latest activity first'),
             'order': 'last_activity_on desc nulls last, id desc'},
            {'key': 'closed', 'label': _('Recently closed first'),
             'order': 'closed_on desc nulls last, id desc'},
        ]

    @api.model
    def _late_new_ids(self):
        """New questions nobody has moved for more than LATE_WORKING_DAYS
        working days — the same rule the amber card uses, in ONE read of the
        new questions the reader may see."""
        key = ('pb_ask_hr.late_new', self.env.uid)
        cache = self.env.cr.cache
        if key in cache:
            return cache[key]
        today = fields.Datetime.context_timestamp(self, fields.Datetime.now()).date()
        found = self.env['pb.ask.hr.ticket'].search_read(
            [('state', '=', 'new')], ['create_date'])
        out = []
        for row in found:
            asked = row['create_date']
            if asked and _working_days_between(
                    fields.Datetime.context_timestamp(self, asked).date(),
                    today) > LATE_WORKING_DAYS:
                out.append(row['id'])
        cache[key] = out
        return out

    @api.model
    def _pbf_late(self):
        return [('id', 'in', self._late_new_ids())]

    @api.model
    def _pbf_not_late(self):
        return [('state', '=', 'new'), ('id', 'not in', self._late_new_ids())]

    @api.model
    def _week_start_date(self):
        today = fields.Datetime.context_timestamp(self, fields.Datetime.now()).date()
        return today - timedelta(days=today.weekday())

    def _pbf_spec(self):
        _ = self.env._
        hr = self._can_act()
        spec = [
            # ---- pinned: where it is, what it is about, who has it
            {'key': 'step', 'label': _('Where it is'), 'icon': 'listChecks',
             'group': 'other', 'type': 'selection', 'path': 'state', 'pinned': True},
            {'key': 'category', 'label': _('Category'), 'icon': 'layers',
             'group': 'other', 'type': 'selection', 'path': 'category', 'pinned': True},
            {'key': 'owner', 'label': _('Who in HR has it'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'user_id', 'pinned': True,
             'none_label': _('Nobody has it yet')},
        ]
        if hr:
            spec += [
                {'key': 'mine', 'label': _('Mine'), 'icon': 'user',
                 'group': 'people', 'type': 'choice',
                 'options': [
                     {'value': 'yes', 'label': _('I have it'), 'tone': 'blue',
                      'domain': [('user_id', '=', self.env.uid)]},
                     {'value': 'no', 'label': _('Somebody else, or nobody'), 'tone': 'slate',
                      'domain': ['|', ('user_id', '=', False), ('user_id', '!=', self.env.uid)]},
                 ]},
                {'key': 'late', 'label': _('Waiting'), 'icon': 'clock',
                 'group': 'other', 'type': 'choice',
                 'help': _('New questions nobody has moved for more than 2 working days.'),
                 'options': [
                     {'value': 'yes', 'label': _('New, over 2 working days'), 'tone': 'amber',
                      'domain_method': '_pbf_late'},
                     {'value': 'no', 'label': _('New, within 2 working days'), 'tone': 'green',
                      'domain_method': '_pbf_not_late'},
                 ]},
            ]
        spec += [
            {'key': 'asker', 'label': _('Who asked'), 'icon': 'user',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id'},
            {'key': 'department', 'label': _('Their department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.department_id',
             'none_label': _('No department')},
            {'key': 'asked', 'label': _('Asked'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'create_date', 'presets': 'past',
             'none_label': _('Not recorded')},
            {'key': 'answered', 'label': _('Answered'), 'icon': 'messageSquare',
             'group': 'dates', 'type': 'date', 'path': 'answered_on', 'presets': 'past',
             'none_label': _('Not answered yet')},
            {'key': 'closed', 'label': _('Closed'), 'icon': 'checkCircle',
             'group': 'dates', 'type': 'date', 'path': 'closed_on', 'presets': 'past',
             'none_label': _('Still open')},
            {'key': 'closed_by', 'label': _('Closed by'), 'icon': 'userCheck',
             'group': 'people', 'type': 'selection', 'path': 'closed_by',
             'none_label': _('Still open')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id'},
        ]
        return spec

    def _pbf_builtin_views(self):
        _ = self.env._
        open_steps = list(OPEN_STATES)
        week = fields.Date.to_string(self._week_start_date())
        if not self._can_act():
            return [
                {'key': 'open', 'label': _('Open questions'), 'icon': 'messageSquare',
                 'filters': {'step': open_steps}},
                {'key': 'yourturn', 'label': _('Answered, your turn'),
                 'filters': {'step': ['answered']}},
                {'key': 'closed', 'label': _('Closed'), 'filters': {'step': ['closed']}},
                {'key': 'all', 'label': _('Everything you asked'), 'filters': {}},
            ]
        return [
            {'key': 'open', 'label': _('Open questions'), 'icon': 'messageSquare',
             'filters': {'step': open_steps}},
            {'key': 'nobody', 'label': _('Nobody has it yet'),
             'filters': {'step': open_steps, 'owner': [False]}},
            {'key': 'mine', 'label': _('Mine'), 'filters': {'mine': ['yes']}},
            {'key': 'week', 'label': _('Answered this week'),
             'filters': {'answered': {'from': week}}},
            {'key': 'late', 'label': _('New, waiting'), 'filters': {'late': ['yes']}},
            {'key': 'closed', 'label': _('Closed'), 'filters': {'step': ['closed']}},
        ]

    @api.model
    def _pbf_list_values(self, s, domain, selected=None):
        """Askers: counted as the reader, named through the public employee
        model, the way the cards name them."""
        if s.get('key') not in PUBLIC_LABELS:
            return super()._pbf_list_values(s, domain, selected)
        rows = []
        groups = self._pbf_records()._read_group(domain, [s['path']], ['__count'])
        names = {}
        try:
            ids = [v.id for v, _n in groups if v]
            names = {p.id: p.display_name for p in
                     self.env['hr.employee.public'].browse(ids).exists()}
        except AccessError:
            names = {}
        for value, count in groups:
            if not value:
                continue
            rows.append({'v': value.id, 'label': names.get(value.id) or str(value.id), 'n': count})
        rows.sort(key=lambda r: (-r['n'], (r['label'] or '').lower()))
        more = len(rows) > 300
        rows = rows[:300]
        have = {r['v'] for r in rows}
        missing = [v for v in (selected or []) if v not in have]
        if missing:
            rows.extend(self._pbf_label_values(s, missing))
        return rows, more

    @api.model
    def _pbf_label_values(self, s, values):
        if s.get('key') not in PUBLIC_LABELS:
            return super()._pbf_label_values(s, values)
        out = []
        for v in values:
            label = str(v)
            try:
                pub = self.env['hr.employee.public'].browse(int(v)).exists()
                label = pub.display_name if pub else self.env._('Removed')
            except Exception:  # noqa: BLE001
                pass
            out.append({'v': v, 'label': label, 'n': 0})
        return out

    @api.model
    def _check_read(self):
        self.env['pb.ask.hr.ticket'].check_access('read')

    @api.model
    def pbf_layout(self):
        try:
            self._check_read()
        except AccessError as e:
            return {'refused': str(e.args[0] if e.args else e)}
        return super().pbf_layout()

    @api.model
    def get_head(self):
        """Everything the board draws except the cards: who reads, the
        numbers line and the strip's notes, counted over every question the
        reader may see (whatever is filtered)."""
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
        week_start = self._week_start(today)
        categories = dict(Ticket._fields['category']._description_selection(self.env))
        last = Ticket.search([('answered_on', '!=', False)], order='answered_on desc', limit=1)
        last_words = ''
        if last:
            last_words = _('Last question answered %s ago.',
                           self._span_words((now - last.answered_on).total_seconds()))
        head = {
            'can_act': can_act,
            'can_ask': self._can_ask(),
            'me': self.env.uid,
            'counts': counts,
            'total': sum(counts.values()),
            'open_total': sum(counts[k] for k in OPEN_STATES),
            'new_late': len(self._late_new_ids()),
            'mine_with_hr': Ticket.search_count([('state', '=', 'with_hr'),
                                                 ('user_id', '=', self.env.uid)]),
            'unowned': Ticket.search_count([('state', 'in', OPEN_STATES),
                                            ('user_id', '=', False)]),
            'answered_week': Ticket.search_count([('answered_on', '>=', week_start)]),
            'week_start': fields.Date.to_string(self._week_start_date()),
            'last_answered_words': last_words,
            'categories': [{'key': k, 'label': v} for k, v in categories.items()],
        }
        if can_act:
            head['median'] = self._median_first_reply(now)
        return head

    @api.model
    def get_ticket_page(self, filters=None, search=None, sort=None, offset=0,
                        limit=PAGE_SIZE):
        """One page of cards for the panel's state, and the strip's four step
        counts said about the same filters (every filter but the step one)."""
        Ticket = self.env['pb.ask.hr.ticket']
        Ticket.check_access('read')
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        tickets = Ticket.search(domain, order=self.pbf_order(sort) or 'create_date desc, id desc',
                                offset=offset, limit=limit)
        now = fields.Datetime.now()
        local = lambda dt: fields.Datetime.context_timestamp(self, dt).date()  # noqa: E731
        today = local(now)
        ctx = {
            'now': now, 'local': local, 'today': today, 'can_act': self._can_act(),
            'week_start': self._week_start(today),
            'categories': dict(Ticket._fields['category']._description_selection(self.env)),
            'people': self._person_rows(tickets.employee_id),
        }
        cards = [self._card(t, ctx) for t in tickets]
        out = {'cards': cards, 'total': Ticket.search_count(domain), 'offset': offset}
        if not offset:
            steps = dict.fromkeys(STEP_KEYS, 0)
            try:
                for state, count in Ticket._read_group(
                        self.pbf_domain(filters, search, skip='step'), ['state'], ['__count']):
                    if state in steps:
                        steps[state] = count
            except Exception:  # noqa: BLE001 — the strip shows zeros, never breaks
                pass
            out['steps'] = steps
        return out

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
