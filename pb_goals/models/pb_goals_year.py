# -*- coding: utf-8 -*-
"""What B2 adds to the Goals board: the year, not just the setting-up of it.

THE BOARD GROWS THREE TABS AND THE DRAWER GROWS THREE SECTIONS. B1's board
answered "has everybody written their goals"; this answers "is anything
happening to them" — the monthly conversations, the changes people have asked
for, and what the year is coming out at.

EVERYTHING HERE IS A SEPARATE FILE AND A SEPARATE PAYLOAD, on purpose. A tab is
drawn BEFORE its own data arrives (R195) and a refresh button must re-read what
is on the screen rather than whatever it was written against (R188) — both of
which are far easier to get right when each tab has one reader with one name.

NOTHING RECOMPUTES A NUMBER THE SERVER ALREADY WORKED OUT. The compliance
percentage on this board and the compliance percentage on the Insights lens
come from the same arithmetic in `pb.goals.analytics`, because two screens that
disagree about the same figure are two screens nobody trusts.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .goals_common import (
    CHANGE_KIND_LABEL, CHANGE_OPEN, P_ROW_LIMIT, SCORES, as_id, counted,
    due_words, number,
)

_logger = logging.getLogger(__name__)


class PbGoalsYear(models.AbstractModel):
    _inherit = 'pb.goals'

    # ==================================================================
    #  The drawer's three new sections
    # ==================================================================
    @api.model
    def get_set(self, set_id):
        """B1's drawer, plus the year that has happened to the sheet.

        EACH SECTION HAS ITS OWN `_safe` PROBE (R92/R158). A phase that adds a
        section to an existing drawer has to assume the drawer is opened by
        somebody who holds none of its groups — the person who ASKED for the
        change, for instance — and a section that throws would take the other
        eight with it.
        """
        payload = super().get_set(set_id)
        if not payload.get('ok'):
            return payload
        sheet = self.env['pb.goal.set'].sudo().browse(as_id(set_id))
        today = fields.Date.today()
        payload.update({
            'checkins': self._safe('the check-ins',
                                   lambda: self._checkin_rows(sheet, today),
                                   []) or [],
            'reviews': self._safe('the reviews',
                                  lambda: self._review_rows(sheet, today),
                                  []) or [],
            'changes': self._safe('the change requests',
                                  lambda: self._change_rows(sheet), []) or [],
            'audit': self._safe('what has been changed',
                                lambda: self._audit_rows(sheet), []) or [],
            'scores': self._safe('the scores',
                                 lambda: self._score_rows(sheet), {}) or {},
            'applicability': self._safe(
                'which reviews they get',
                lambda: self._applicability(sheet), {}) or {},
            'score_options': [{'key': key, 'label': label}
                              for key, label in SCORES],
            'may_score': self._safe('who may score',
                                    lambda: sheet._may_score(), False),
            'may_checkin': self._safe(
                'who may write up a check-in',
                lambda: self._may_checkin_here(sheet), False),
            'may_change': self._safe(
                'who may ask for a change',
                lambda: sheet.state == 'locked', False),
            'closed': sheet.state == 'closed',
        })
        return payload

    @api.model
    def _may_checkin_here(self, sheet):
        if self._is_hr():
            return True
        me = self._me()
        return bool(sheet.manager_user_id.id == self.env.uid
                    or (me and sheet.employee_id.id == me.id))

    @api.model
    def _checkin_rows(self, sheet, today):
        rows = self.env['pb.goal.checkin'].sudo().search(
            [('set_id', '=', sheet.id)], order='month desc', limit=24)
        return [{
            'id': row.id,
            'month': str(row.month or ''),
            'month_word': row._month_word(),
            'planned': str(row.scheduled_date or ''),
            'state': row.state,
            'state_word': row._state_word(),
            'note': row.progress_note or '',
            'blockers': row.blockers or '',
            'done_on': str(row.done_at or '')[:10],
            'done_by': row.done_by_id.name or '',
            'overdue': bool(row.state == 'planned' and row.scheduled_date
                            and row.scheduled_date < today),
            'snapshot': row.snapshot_rows(),
        } for row in rows]

    @api.model
    def _review_rows(self, sheet, today):
        rows = self.env['pb.goal.review'].sudo().search(
            [('set_id', '=', sheet.id)], order='due_date')
        return [{
            'id': row.id,
            'kind': row.kind,
            'kind_word': row._kind_word(),
            'due': str(row.due_date or ''),
            'due_words': ('' if row.state == 'done'
                          else due_words(row.due_date, today)),
            'state': row.state,
            'state_word': row._state_word(),
            'manager_note': row.manager_note or '',
            'employee_note': row.employee_note or '',
            'done_on': str(row.done_at or '')[:10],
            'score': round(row.score_at_review or 0.0, 2)
            if row.state == 'done' else 0.0,
        } for row in rows]

    @api.model
    def _change_rows(self, sheet):
        rows = self.env['pb.goal.change'].sudo().search(
            [('set_id', '=', sheet.id)], order='id desc', limit=30)
        out = [{
            'id': row.id,
            'kind': row.kind,
            'kind_word': row._kind_word(),
            'summary': row.summary or '',
            'reason': row.reason or '',
            'state': row.state,
            'state_word': row._state_word(),
            'rank': row._rank(),
            'asked_by': row.requested_by_id.name or '',
            'asked_on': str(row.create_date or '')[:10],
            'applied_on': str(row.applied_at or '')[:10],
            'refuse_note': row.refuse_note or '',
            'open': row.state in CHANGE_OPEN,
        } for row in rows]
        # PROBLEM FIRST (R113): what somebody has to do about it, worst first.
        out.sort(key=lambda r: (r['rank'], r['asked_on']))
        return out

    @api.model
    def _audit_rows(self, sheet):
        rows = self.env['pb.goal.audit'].sudo().search(
            [('set_id', '=', sheet.id)], order='at desc', limit=30)
        return [{
            'id': row.id,
            'at': str(row.at or '')[:16],
            'who': row.by_user_id.name or '',
            'what': row.what or '',
            'reason': row.reason or '',
            'goal': row.goal_id.sudo().title or '',
            'kind_word': CHANGE_KIND_LABEL.get(row.kind, row.kind or ''),
        } for row in rows]

    @api.model
    def _score_rows(self, sheet):
        """The marks, goal by goal, with what is still missing said in words."""
        goals = []
        for goal in sheet.with_context(active_test=False).goal_ids.sorted(
                lambda g: (g.sequence, g.id)):
            goals.append({
                'id': goal.id,
                'title': goal.title or '',
                'weight': round(goal.weight or 0.0, 1),
                'scored': bool(goal.scored),
                'score': round(goal.score or 0.0, 2),
                'score_words': goal._score_words(),
                'done': bool(goal.done_at),
                'done_on': str(goal.done_at or '')[:10],
                'changed': goal._changed_words(),
                'krs': [{
                    'id': kr.id,
                    'title': kr.title or '',
                    'score': kr.score or '',
                    'score_word': kr._score_word(),
                    'progress': round(kr.progress or 0.0, 1),
                } for kr in goal.kr_ids.sorted(lambda k: (k.sequence, k.id))],
            })
        return {
            'goals': goals,
            'scored': bool(sheet.scored),
            'score': round(sheet.score or 0.0, 2),
            'band': sheet.score_band or '',
            'tone': sheet.score_tone or '',
            'words': sheet._score_words(),
            'sentence': sheet._scoring_sentence(),
            'goals_done': sheet.goals_done,
        }

    @api.model
    def _applicability(self, sheet):
        return {
            'note': sheet.applicability_note or '',
            'mid_year': bool(sheet.applies_mid_year),
            'year_end': bool(sheet.applies_year_end),
            'prorated': bool(sheet.prorated),
            'covered_from': str(sheet.covered_from or ''),
            'joined_on': str(sheet.joined_on or ''),
        }

    # ==================================================================
    #  The presses
    # ==================================================================
    @api.model
    def write_up_checkin(self, checkin_id, note, blockers=''):
        row = self.env['pb.goal.checkin'].sudo().browse(
            as_id(checkin_id)).exists()
        if not row:
            raise UserError(_("That check-in is not there any more."))
        row.action_checkin_done(note, blockers)
        return {'ok': True, 'state': row.state,
                'sentence': _("Written up. %s is on the record now.",
                              row._month_word())}

    @api.model
    def write_up_review(self, review_id, manager_note, employee_note=''):
        row = self.env['pb.goal.review'].sudo().browse(
            as_id(review_id)).exists()
        if not row:
            raise UserError(_("That review is not there any more."))
        row.action_review_done(manager_note, employee_note)
        return {'ok': True, 'state': row.state,
                'sentence': _("%s written up.", row._kind_word())}

    @api.model
    def score_key_results(self, set_id, scores):
        sheet = self.env['pb.goal.set'].browse(as_id(set_id)).exists()
        if not sheet:
            raise UserError(_("That goal sheet is not there any more."))
        sheet.check_access('read')
        return sheet.score_key_results(scores)

    @api.model
    def mark_goal_done(self, goal_id, done=True):
        goal = self.env['pb.goal'].sudo().browse(as_id(goal_id)).exists()
        if not goal:
            raise UserError(_("That goal is not there any more."))
        goal.set_id.check_access('read')
        if done:
            goal.action_goal_done()
            return {'ok': True, 'done': True,
                    'sentence': _("\"%s\" is marked complete.",
                                  goal.title or '')}
        goal.action_goal_reopen()
        return {'ok': True, 'done': False,
                'sentence': _("\"%s\" is open again.", goal.title or '')}

    @api.model
    def ask_for_change(self, set_id, kind, values, reason, goal_id=None):
        change = self.env['pb.goal.change'].raise_change(
            set_id, kind, values, reason, goal_id)
        # SENT IN STRAIGHT AWAY, because a request left in draft on a board
        # is a request nobody knows about. A draft state exists for the
        # record's own sake and not as a step somebody has to remember.
        change.action_change_submit()
        return {'ok': True, 'change_id': change.id, 'state': change.state,
                'sentence': _(
                    "Asked. %(who)s looks at it first, then the HR lead.",
                    who=change.set_id.manager_employee_id.sudo().name
                    or _('Their manager'))}

    @api.model
    def decide_change(self, change_id, action, note=''):
        """Agree, send back or turn down a change — from the board.

        THE ROUTE IS STILL THE ROUTE. These call the record's own presses,
        which under a published route hand the decision straight to the
        engine; the board is a door onto the same machinery and never a way
        around it.
        """
        change = self.env['pb.goal.change'].sudo().browse(
            as_id(change_id)).exists()
        if not change:
            raise UserError(_("That request is not there any more."))
        if action == 'refuse':
            change.action_change_refuse(note)
            word = _("Turned down.")
        elif action == 'manager_ok':
            change.action_change_manager_ok()
            word = _("Agreed. It goes to the HR lead next.")
        elif action == 'approve':
            change.action_change_approve()
            word = _("Agreed and carried out.")
        else:
            raise UserError(_("That is not something to do with a request."))
        return {'ok': True, 'state': change.state, 'sentence': word}

    # ==================================================================
    #  Closing the year
    # ==================================================================
    @api.model
    def preview_close(self, cycle_id):
        return self.env['pb.goal.cycle'].preview_close(cycle_id)

    @api.model
    def close_cycle(self, cycle_id, with_gaps=False):
        return self.env['pb.goal.cycle'].close_cycle(cycle_id, with_gaps)

    # ==================================================================
    #  The board's three new tabs
    # ==================================================================
    @api.model
    def get_year(self, cycle_id=None, tab='checkins', filters=None):
        """One tab's worth of the year. ONE READER PER TAB (R188).

        A refresh that re-read the sheets while the check-ins tab was showing
        left the tab exactly as stale as it was — found live on another
        module's board, and the fix is a payload per tab with its own name.
        """
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'stats': [],
                    'why': _("Goal sheets are for the people they belong to, "
                             "their manager and the HR team.")}
        filters = dict(filters or {})
        today = fields.Date.today()
        cycle_id = int(cycle_id or 0)
        if tab == 'changes':
            rows = self._safe('the change requests',
                              lambda: self._year_changes(cycle_id, filters),
                              []) or []
        elif tab == 'reviews':
            rows = self._safe('the reviews',
                              lambda: self._year_reviews(cycle_id, today),
                              []) or []
        elif tab == 'scores':
            rows = self._safe('the scores',
                              lambda: self._year_scores(cycle_id), []) or []
        else:
            tab = 'checkins'
            rows = self._safe('the check-ins',
                              lambda: self._year_checkins(cycle_id, today),
                              []) or []
        return {
            'allowed': True,
            'tab': tab,
            'rows': rows,
            'today': str(today),
            'stats': self._safe('the numbers',
                                lambda: self._year_stats(tab, rows),
                                []) or [],
            'headline': self._safe('the headline',
                                   lambda: self._year_headline(tab, rows),
                                   '') or '',
        }

    @api.model
    def _limit(self):
        return number(self.env, P_ROW_LIMIT, 400)

    @api.model
    def _year_checkins(self, cycle_id, today):
        """THE CURRENT MONTH AND ANYTHING STILL OPEN BEHIND IT.

        Read as the CALLER so the record rules decide whose rows these are —
        a manager gets their team's and the HR team gets the company's,
        without this file having to know which.
        """
        domain = [('state', 'in', ('planned', 'missed'))]
        if cycle_id:
            domain.append(('cycle_id', '=', cycle_id))
        rows = self.env['pb.goal.checkin'].search(
            domain, order='scheduled_date', limit=self._limit())
        out = []
        for row in rows:
            employee = row.employee_id.sudo()
            out.append({
                'id': row.id,
                'set_id': row.set_id.id,
                'name': employee.name or '',
                'avatar': '/web/image/hr.employee/%s/avatar_128' % employee.id,
                'manager': row.manager_employee_id.sudo().name or '',
                'department': row.department_id.sudo().name or '',
                'month': str(row.month or ''),
                'month_word': row._month_word(),
                'planned': str(row.scheduled_date or ''),
                'state': row.state,
                'state_word': row._state_word(),
                'due_words': ('' if row.state == 'missed'
                              else due_words(row.scheduled_date, today)),
                'overdue': bool(row.state == 'planned' and row.scheduled_date
                                and row.scheduled_date < today),
                'missed': row.state == 'missed',
            })
        out.sort(key=lambda r: (not r['missed'], not r['overdue'],
                                r['planned'] or '9999', r['name']))
        return out

    @api.model
    def _year_reviews(self, cycle_id, today):
        domain = []
        if cycle_id:
            domain.append(('cycle_id', '=', cycle_id))
        rows = self.env['pb.goal.review'].search(
            domain, order='due_date', limit=self._limit())
        out = []
        for row in rows:
            employee = row.employee_id.sudo()
            out.append({
                'id': row.id,
                'set_id': row.set_id.id,
                'name': employee.name or '',
                'avatar': '/web/image/hr.employee/%s/avatar_128' % employee.id,
                'manager': row.manager_employee_id.sudo().name or '',
                'kind': row.kind,
                'kind_word': row._kind_word(),
                'due': str(row.due_date or ''),
                'due_words': ('' if row.state == 'done'
                              else due_words(row.due_date, today)),
                'state': row.state,
                'state_word': row._state_word(),
                'overdue': bool(row.state == 'planned' and row.due_date
                                and row.due_date < today),
            })
        out.sort(key=lambda r: (r['state'] == 'done', not r['overdue'],
                                r['due'] or '9999', r['name']))
        return out

    @api.model
    def _year_changes(self, cycle_id, filters):
        domain = []
        if cycle_id:
            domain.append(('cycle_id', '=', cycle_id))
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        rows = self.env['pb.goal.change'].search(
            domain, order='id desc', limit=self._limit())
        out = []
        for row in rows:
            employee = row.employee_id.sudo()
            out.append({
                'id': row.id,
                'set_id': row.set_id.id,
                'name': employee.name or '',
                'avatar': '/web/image/hr.employee/%s/avatar_128' % employee.id,
                'kind': row.kind,
                'kind_word': row._kind_word(),
                'summary': row.summary or '',
                'reason': row.reason or '',
                'state': row.state,
                'state_word': row._state_word(),
                'rank': row._rank(),
                'asked_by': row.requested_by_id.name or '',
                'asked_on': str(row.create_date or '')[:10],
                'open': row.state in CHANGE_OPEN,
            })
        out.sort(key=lambda r: (r['rank'], r['asked_on']))
        return out

    @api.model
    def _year_scores(self, cycle_id):
        domain = [('state', 'in', ('locked', 'closed'))]
        if cycle_id:
            domain.append(('cycle_id', '=', cycle_id))
        rows = self.env['pb.goal.set'].search(
            domain, order='id', limit=self._limit())
        out = []
        for sheet in rows:
            employee = sheet.employee_id.sudo()
            out.append({
                'id': sheet.id,
                'set_id': sheet.id,
                'name': employee.name or '',
                'avatar': '/web/image/hr.employee/%s/avatar_128' % employee.id,
                'manager': sheet.manager_employee_id.sudo().name or '',
                'department': sheet.department_id.sudo().name or '',
                'goals': sheet.goal_count,
                'done': sheet.goals_done,
                'progress': round(sheet.progress or 0.0, 1),
                'scored': bool(sheet.scored),
                'score': round(sheet.score or 0.0, 2),
                'band': sheet.score_band or '',
                'tone': sheet.score_tone or '',
                'year_end': bool(sheet.applies_year_end),
                'prorated': bool(sheet.prorated),
                'closed': sheet.state == 'closed',
            })
        # UNSCORED FIRST — a scoring screen is opened to find what is left.
        out.sort(key=lambda r: (r['scored'], -r['score'], r['name']))
        return out

    @api.model
    def _year_stats(self, tab, rows):
        # A TILE'S LABEL IS READ AS THE SECOND HALF OF A SENTENCE, so the
        # count-nouns agree with their number (R46). "1 Months missed" is how
        # a screen announces it was written by a programme; the labels that
        # are not count-nouns — "Past their day", "Written up" — are already
        # right at every number and are left alone.
        if tab == 'checkins':
            missed = len([r for r in rows if r['missed']])
            overdue = len([r for r in rows if r['overdue']])
            owed = len(rows) - missed
            return [
                {'key': 'open', 'value': owed, 'icon': 'calendar',
                 'label': counted(owed, _('Conversation to have'),
                                  _('Conversations to have'))},
                {'key': 'overdue', 'label': _('Past their day'),
                 'value': overdue, 'icon': 'clock',
                 'tone': 'warn' if overdue else ''},
                {'key': 'missed', 'value': missed, 'icon': 'alert',
                 'label': counted(missed, _('Month missed'),
                                  _('Months missed')),
                 'tone': 'bad' if missed else ''},
            ]
        if tab == 'reviews':
            done = len([r for r in rows if r['state'] == 'done'])
            overdue = len([r for r in rows if r['overdue']])
            left = len(rows) - done
            return [
                {'key': 'due', 'value': left, 'icon': 'award',
                 'label': counted(left, _('Review to write up'),
                                  _('Reviews to write up'))},
                {'key': 'done', 'label': _('Written up'), 'value': done,
                 'icon': 'checkCircle', 'tone': 'good'},
                {'key': 'overdue', 'label': _('Past their date'),
                 'value': overdue, 'icon': 'alert',
                 'tone': 'bad' if overdue else ''},
            ]
        if tab == 'changes':
            waiting = len([r for r in rows if r['open']])
            agreed = len([r for r in rows if r['state'] == 'approved'])
            refused = len([r for r in rows if r['state'] == 'refused'])
            return [
                {'key': 'waiting', 'label': _('Waiting on somebody'),
                 'value': waiting, 'icon': 'clock',
                 'tone': 'warn' if waiting else ''},
                {'key': 'agreed', 'label': _('Agreed and carried out'),
                 'value': agreed, 'icon': 'checkCircle', 'tone': 'good'},
                {'key': 'refused', 'label': _('Turned down'),
                 'value': refused, 'icon': 'xCircle'},
            ]
        scored = len([r for r in rows if r['scored']])
        marks = [r['score'] for r in rows if r['scored']]
        average = round(sum(marks) / len(marks), 2) if marks else 0
        return [
            {'key': 'sheets', 'value': len(rows), 'icon': 'target',
             'label': counted(len(rows), _('Agreed goal sheet'),
                              _('Agreed goal sheets'))},
            {'key': 'scored', 'label': _('Scored'), 'value': scored,
             'icon': 'award', 'tone': 'good' if scored else ''},
            {'key': 'left', 'label': _('Still to score'),
             'value': len(rows) - scored, 'icon': 'pencil',
             'tone': 'warn' if len(rows) - scored else ''},
            {'key': 'avg', 'label': _('Average so far'),
             'value': average if marks else '—', 'icon': 'trendingUp'},
        ]

    @api.model
    def _year_headline(self, tab, rows):
        """One sentence per tab, whole, with the arithmetic in it (R117)."""
        if tab == 'checkins':
            if not rows:
                return _(
                    "Every monthly conversation that was owed has happened. "
                    "New ones open on the day of the month the goal year "
                    "asks for.")
            missed = len([r for r in rows if r['missed']])
            overdue = len([r for r in rows if r['overdue']])
            first = _("%(n)s %(word)s to have.", n=len(rows) - missed,
                      word=counted(len(rows) - missed, _('conversation'),
                                   _('conversations')))
            if overdue:
                first += ' ' + _("%(n)s %(word)s past the day it was planned "
                                 "for.", n=overdue,
                                 word=counted(overdue, _('is'), _('are')))
            if missed:
                first += ' ' + _("%(n)s %(word)s missed and the month is "
                                 "over.", n=missed,
                                 word=counted(missed, _('month was'),
                                              _('months were')))
            return first
        if tab == 'reviews':
            if not rows:
                return _(
                    "No reviews are open yet. A half-way or end-of-year "
                    "review appears here a month before it is due.")
            done = len([r for r in rows if r['state'] == 'done'])
            return _("%(done)s of %(total)s %(word)s written up.", done=done,
                     total=len(rows),
                     word=counted(len(rows), _('review'), _('reviews')))
        if tab == 'changes':
            if not rows:
                return _(
                    "Nobody has asked to change an agreed goal. When somebody "
                    "does, it comes here for their manager and then the HR "
                    "lead.")
            waiting = len([r for r in rows if r['open']])
            return _("%(n)s %(word)s asked for, %(w)s still waiting on "
                     "somebody.", n=len(rows),
                     word=counted(len(rows), _('change'), _('changes')),
                     w=waiting)
        if not rows:
            return _(
                "No goals have been agreed on this year yet, so there is "
                "nothing to score.")
        scored = len([r for r in rows if r['scored']])
        return _("%(scored)s of %(total)s %(word)s scored.", scored=scored,
                 total=len(rows),
                 word=counted(len(rows), _('goal sheet'), _('goal sheets')))

    # ==================================================================
    #  The doors
    # ==================================================================
    @api.model
    def open_checkin(self, checkin_id):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Check-in'),
            'res_model': 'pb.goal.checkin',
            'res_id': as_id(checkin_id),
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    @api.model
    def open_change(self, change_id):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Change request'),
            'res_model': 'pb.goal.change',
            'res_id': as_id(change_id),
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    @api.model
    def open_numbers(self):
        """Through to the Insights lens, where the whole picture is."""
        return {
            'type': 'ir.actions.client',
            'tag': 'pb_goals_numbers',
            'name': _('Goal numbers'),
        }
