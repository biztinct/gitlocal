# -*- coding: utf-8 -*-
"""`pb.goals.home` — "Goals waiting on you", on the Home screen.

FOUR KINDS OF THING AND EVERY ONE OF THEM IS A DOOR. Somebody opening Home
should be able to clear their goals obligations without knowing this module
exists:

  * **Sign-offs** — goal sheets and change requests where the route has asked
    THEM. Read through the approval engine's own inbox facade
    (`pb.approval.inbox.list_requests('mine', …)`), NEVER by searching for
    records with a status on them. There is one inbox on this database and a
    second one that answered slightly differently would be worse than none:
    the day they disagree, the person in front of the screen is the one who
    finds out.
  * **Conversations** — this month's check-in, whether they are the manager or
    the employee. Both sides, because either may write it up.
  * **Reviews** — the half-way and end-of-year write-ups they owe.
  * **Their own sheet** — the deadline, if theirs is not in yet.

THE CARD'S COUNT AND THE LIST ARE THE SAME NUMBER, computed once, here. A chip
that counts one thing over a list that shows another is two bugs (R80).

IT NEVER RAISES AND IT NEVER BLANKS HOME. Every section has its own guard: a
database without the approvals screen installed answers `None` to
`env.get('pb.approval.inbox')` and the other three sections still draw. That
guard is also what keeps this module's dependency list honest — `pb_goals`
depends on the approval ENGINE and never on the screen (AM52).
"""

import logging

from odoo import _, api, fields, models

from .goals_common import (
    SET_EDITABLE, SET_STATE_LABEL, counted, due_words,
)
from .goal_set_approval import GOALS_PROCESS_KEY
from .change_approval import CHANGE_PROCESS_KEY

_logger = logging.getLogger(__name__)

#: How many rows the card will ever draw. A Home card is a nudge and not a
#: work queue: past a dozen rows somebody needs the board, and the card says so
#: rather than scrolling for ever.
ROW_CAP = 12


class PbGoalsHome(models.AbstractModel):
    _name = 'pb.goals.home'
    _description = 'Goals waiting on you'

    @api.model
    def _safe(self, label, fn, default=None):
        try:
            return fn()
        except Exception:               # noqa: BLE001 — one probe, one guard
            _logger.warning('pb_goals: the Home card could not work out %s',
                            label, exc_info=True)
            return default

    @api.model
    def _me(self):
        return self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)

    # ==================================================================
    @api.model
    def get_home(self):
        """Everything the Home card draws, in one read."""
        today = fields.Date.today()
        approvals = self._safe('the sign-offs',
                               lambda: self._approvals(), []) or []
        checkins = self._safe('the monthly conversations',
                              lambda: self._checkins(today), []) or []
        reviews = self._safe('the reviews',
                             lambda: self._reviews(today), []) or []
        mine = self._safe('your own goals',
                          lambda: self._mine(today), []) or []
        rows = approvals + checkins + reviews + mine
        total = len(rows)
        return {
            'ok': True,
            'count': total,
            'rows': rows[:ROW_CAP],
            'more': max(0, total - ROW_CAP),
            # A CHIP IS A NUMBER AND THE WORD BESIDE IT, so the count-nouns
            # agree (R46). "1 Conversations" is how a screen announces it was
            # written by a programme. "To decide" and "Your own" are not
            # count-nouns and are right at every number.
            'sections': [
                {'key': 'approve', 'label': _('To decide'),
                 'count': len(approvals)},
                {'key': 'checkin', 'count': len(checkins),
                 'label': counted(len(checkins), _('Conversation'),
                                  _('Conversations'))},
                {'key': 'review', 'count': len(reviews),
                 'label': counted(len(reviews), _('Review'), _('Reviews'))},
                {'key': 'mine', 'label': _('Your own'), 'count': len(mine)},
            ],
            'headline': self._headline(approvals, checkins, reviews, mine),
        }

    @api.model
    def _headline(self, approvals, checkins, reviews, mine):
        """THE WHOLE SENTENCE, never a frame with a number in it (R117)."""
        bits = []
        if approvals:
            bits.append(_("%(n)s to decide", n=len(approvals)))
        if checkins:
            bits.append(_("%(n)s %(word)s to write up", n=len(checkins),
                          word=counted(len(checkins), _('conversation'),
                                       _('conversations'))))
        if reviews:
            bits.append(_("%(n)s %(word)s to write up", n=len(reviews),
                          word=counted(len(reviews), _('review'),
                                       _('reviews'))))
        if mine:
            bits.append(_("your own goals"))
        if not bits:
            return _("Nothing about goals is waiting on you.")
        if len(bits) == 1:
            return _("%s is waiting on you.", bits[0].capitalize())
        return _("%(first)s and %(last)s are waiting on you.",
                 first=', '.join(bits[:-1]), last=bits[-1])

    # ------------------------------------------------------- the sign-offs
    @api.model
    def _approvals(self):
        """What the ROUTE has asked this person, from the one inbox.

        NEVER A SECOND INBOX. `pb.approval.inbox.list_requests('mine', …)`
        already knows what "my turn" means on this database — an open seat
        whose acting user is me, which quietly includes anybody covering for
        somebody else. A search for records in a waiting status would get the
        covering case wrong and nobody would ever find out.
        """
        inbox = self.env.get('pb.approval.inbox')
        if inbox is None:
            return []
        out = []
        for key, icon in ((GOALS_PROCESS_KEY, 'target'),
                          (CHANGE_PROCESS_KEY, 'repeat')):
            try:
                answer = inbox.list_requests(
                    'mine', {'process_key': key}, False, 'me') or {}
            except Exception:           # noqa: BLE001 — one probe, one guard
                _logger.warning('pb_goals: the inbox could not be read for '
                                '%s', key, exc_info=True)
                continue
            for card in (answer.get('cards') or [])[:ROW_CAP]:
                out.append({
                    'kind': 'approve',
                    'id': card.get('id'),
                    'icon': icon,
                    'title': card.get('title') or '',
                    'sub': card.get('sub') or '',
                    'when': card.get('due_at') or '',
                    'late': bool(card.get('late')),
                    'door': 'inbox',
                    'word': _('Decide'),
                })
        return out

    # ---------------------------------------------------- the conversations
    @api.model
    def _checkins(self, today):
        """This month's conversation, and any that are overdue.

        BOTH SIDES OF IT. `manager_user_id = me OR employee = me` is the
        domain, because either may write it up — and a card that only ever
        showed a manager theirs would make an employee a passenger in a
        conversation about their own year.
        """
        me = self._me()
        rows = self.env['pb.goal.checkin'].sudo().search([
            ('state', '=', 'planned'),
            ('scheduled_date', '<=', today),
            ('company_id', 'in', self.env.companies.ids),
            '|', ('manager_user_id', '=', self.env.uid),
            ('employee_id', '=', me.id or 0),
        ], order='scheduled_date', limit=ROW_CAP * 2)
        out = []
        for row in rows:
            whose = row.employee_id.sudo().name or ''
            out.append({
                'kind': 'checkin',
                'id': row.id,
                'icon': 'calendar',
                'title': (_("Your %s check-in", row._month_word())
                          if me and row.employee_id.id == me.id
                          else _("%(who)s · %(month)s check-in", who=whose,
                                 month=row._month_word())),
                'sub': _("Planned for %s", row.scheduled_date),
                'when': str(row.scheduled_date or ''),
                'late': bool(row.scheduled_date
                             and row.scheduled_date < today),
                'door': 'checkin',
                'word': _('Write it up'),
            })
        return out

    # --------------------------------------------------------- the reviews
    @api.model
    def _reviews(self, today):
        rows = self.env['pb.goal.review'].sudo().search([
            ('state', '=', 'planned'),
            ('manager_user_id', '=', self.env.uid),
            ('company_id', 'in', self.env.companies.ids),
        ], order='due_date', limit=ROW_CAP * 2)
        return [{
            'kind': 'review',
            'id': row.id,
            'icon': 'award',
            'title': _("%(who)s · %(what)s",
                       who=row.employee_id.sudo().name or '',
                       what=row._kind_word()),
            'sub': due_words(row.due_date, today) or _("Due %s",
                                                       row.due_date),
            'when': str(row.due_date or ''),
            'late': bool(row.due_date and row.due_date < today),
            'door': 'review',
            'word': _('Write it up'),
        } for row in rows]

    # ------------------------------------------------------- their own sheet
    @api.model
    def _mine(self, today):
        """Their own goals, but only while there is something to do about them.

        A ROW THAT SAYS "AGREED AND LOCKED" IS NOT WAITING ON ANYBODY, and a
        card called "waiting on you" that carries one is a card people learn
        to ignore.
        """
        me = self._me()
        if not me:
            return []
        sheet = self.env['pb.goal.set'].sudo().search([
            ('employee_id', '=', me.id), ('cycle_id.state', '=', 'open'),
        ], order='id desc', limit=1)
        if not sheet or sheet.state not in SET_EDITABLE:
            return []
        return [{
            'kind': 'mine',
            'id': sheet.id,
            'icon': 'pencil',
            'title': (_("Your goals came back with a note")
                      if sheet.state == 'returned'
                      else _("Write your goals for %s",
                             sheet.cycle_id.name or '')),
            'sub': (due_words(sheet.deadline, today)
                    or SET_STATE_LABEL.get(sheet.state, '')),
            'when': str(sheet.deadline or ''),
            'late': bool(sheet.deadline and sheet.deadline < today),
            'door': 'my_goals',
            'word': _('Open my goals'),
        }]

    # ==================================================================
    #  The doors
    # ==================================================================
    @api.model
    def open_row(self, kind, row_id):
        """One door per kind of row. Never a dead end.

        A HAND-BUILT `act_window` DICT CARRIES `views` (R125) — the client
        maps over that field unconditionally and the theme shows the failure
        as a generic "something went wrong" with nothing in the console.
        """
        from .goals_common import as_id
        ident = as_id(row_id)
        if kind == 'approve':
            # The one inbox, on this one request. A client action and not a
            # window action, so there is no `views` to carry.
            return {
                'type': 'ir.actions.client',
                'tag': 'pb_approval_inbox',
                'name': _('Approvals'),
                'params': {'request_id': ident},
            }
        if kind == 'checkin':
            return {
                'type': 'ir.actions.act_window',
                'name': _('Check-in'),
                'res_model': 'pb.goal.checkin',
                'res_id': ident,
                'view_mode': 'form',
                'views': [[False, 'form']],
                'target': 'current',
            }
        if kind == 'review':
            return {
                'type': 'ir.actions.act_window',
                'name': _('Review'),
                'res_model': 'pb.goal.review',
                'res_id': ident,
                'view_mode': 'form',
                'views': [[False, 'form']],
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_url',
            'url': '/my/goals',
            'target': 'self',
        }
