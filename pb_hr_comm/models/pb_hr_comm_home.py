# -*- coding: utf-8 -*-
"""`pb.hr.comm.home` — "Coming up", on the Home screen.

WHAT IS ABOUT TO BE SAID, AND WHOSE WEEK IT IS. Two things belong on a Home
card about communications and they are not the same thing: the announcements
that go out in the next seven days, and the colleagues with a birthday or a
work anniversary in those same seven days. The first is what somebody needs to
know before they send their own email; the second is the one thing on the
whole screen that is about a person rather than a process.

IT IS OPEN TO EVERYBODY WITH A LOGIN, and that is the point. An announcement
is about to be sent TO these people — telling them it is coming is not a
permission, it is the courtesy the module exists for. What a person may do
about it still depends on the record rules: somebody who looks after a post
gets a row that opens it, and everybody else gets a row that reads.

A DEAD END IS THE ONE THING THIS CARD MUST NOT BE. With nothing coming up it
still says so in a sentence and still shows the week's birthdays, rather than
disappearing off a screen somebody has learnt to look at.
"""

import logging

from datetime import timedelta

from odoo import _, api, fields, models

from .comm_common import (
    GROUP_MANAGER, POST_RANK, POST_STATE_LABEL, POST_TONE, as_id, counted,
    when_words,
)

_logger = logging.getLogger(__name__)

#: How many rows the card may carry. It is a card, not a register (R76).
ROW_CAP = 8

#: How many celebrations the card may carry beside them.
CELEBRATION_CAP = 8


class PbHrCommHome(models.AbstractModel):
    _name = 'pb.hr.comm.home'
    _description = 'Announcements coming up'

    @api.model
    def _safe(self, label, fn, default=None):
        try:
            return fn()
        except Exception:               # noqa: BLE001 — one probe, one guard
            _logger.warning('pb_hr_comm: the Home card could not work out %s',
                            label, exc_info=True)
            return default

    @api.model
    def get_home(self):
        """The next seven days, in one read.

        THE COUNT AND THE LIST ARE THE SAME NUMBER, computed once here. A chip
        that counts one thing over a list that shows another is two bugs
        (R80), and this card has two sections that could each drift on their
        own.
        """
        now = fields.Datetime.now()
        rows = self._safe('what is coming up',
                          lambda: self._coming(now), []) or []
        parties = self._safe('the birthdays',
                             lambda: self._celebrations(), []) or []
        mine = [row for row in rows if row['mine']]
        return {
            'rows': rows[:ROW_CAP],
            'more': max(len(rows) - ROW_CAP, 0),
            'count': len(rows),
            'mine': len(mine),
            'celebrations': parties[:CELEBRATION_CAP],
            'celebration_more': max(len(parties) - CELEBRATION_CAP, 0),
            'headline': self._headline(rows, mine, parties),
            'may_plan': (self.env.user.has_group('pb_hr_comm.group_comm_user')
                         or self.env.user.has_group(GROUP_MANAGER)),
        }

    @api.model
    def _coming(self, now):
        horizon = now + timedelta(days=7)
        posts = self.env['pb.hr.comm.post'].search([
            ('company_id', 'in', self.env.companies.ids),
            ('state', 'in', ('draft', 'submitted', 'scheduled', 'sending')),
            ('send_at', '>=', now - timedelta(hours=1)),
            ('send_at', '<=', horizon),
        ], order='send_at asc, id asc', limit=40)
        out = []
        for post in posts:
            out.append({
                'id': post.id,
                'kind': 'post',
                'title': post.subject or '',
                'sub': '%s · %s' % (post.audience_note or '',
                                    post.sudo().company_id.name or ''),
                'word': when_words(post.send_at, now),
                'state': post.state,
                'state_word': POST_STATE_LABEL.get(post.state, post.state),
                'tone': POST_TONE.get(post.state, 'wait'),
                'rank': POST_RANK.get(post.state, 9),
                'icon': 'megaphone',
                'mine': post.sudo().responsible_user_id.id == self.env.uid,
                'people': post.recipient_count or 0,
            })
        # PROBLEM FIRST, THEN SOONEST (R113): something waiting on a decision
        # comes above something that is simply on its way, and inside a band
        # the one that happens first.
        out.sort(key=lambda row: (0 if row['mine'] else 1, row['rank']))
        return out

    @api.model
    def _celebrations(self):
        if 'pb.rnr.celebration' not in self.env:
            return []
        rows = self.env['pb.rnr.celebration'].upcoming_celebrations(
            days=7, company_ids=self.env.companies.ids, limit=20)
        return [{
            'name': row['name'],
            'initials': row['initials'],
            'avatar': row['avatar'],
            'kind': row['kind'],
            'day_label': row['day_label'],
            'years_label': row['years_label'],
            'icon': 'cake' if row['kind'] == 'birthday' else 'award',
        } for row in rows]

    @api.model
    def _headline(self, rows, mine, parties):
        """One sentence that does the arithmetic for the reader."""
        if not rows and not parties:
            return _("Nothing is going out this week, and nobody in your "
                     "companies is celebrating.")
        parts = []
        if rows:
            parts.append(_(
                "%(n)s %(what)s going out in the next seven days",
                n=len(rows),
                what=counted(len(rows), _('announcement is'),
                             _('announcements are'))))
        if mine:
            parts.append(_(
                "%(n)s of them %(what)s yours", n=len(mine),
                what=counted(len(mine), _('is'), _('are'))))
        if parties:
            parts.append(_(
                "%(n)s %(what)s to say something to",
                n=len(parties),
                what=counted(len(parties), _('colleague'), _('colleagues'))))
        return '%s.' % ', and '.join(parts) if len(parts) < 3 else \
            '%s, and %s.' % (', '.join(parts[:-1]), parts[-1])

    # ------------------------------------------------------------- the doors
    @api.model
    def open_row(self, kind, row_id):
        """Every row is a door (the Home-card contract)."""
        if kind == 'post':
            return self.env['pb.hr.comm'].open_post(as_id(row_id))
        return self.env['pb.hr.comm'].open_celebrations()
