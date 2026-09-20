# -*- coding: utf-8 -*-
"""What B2 adds to `/my/goals`: the rest of the year, from the employee's side.

FIVE THINGS, AND EVERY ONE OF THEM IS SOMETHING THE EMPLOYEE CAN DO RATHER
THAN SOMETHING THEY ARE SHOWN.

  * **This month's conversation.** Either side may write it up, so the
    employee's own page has the box. A check-in the employee filled in is a
    better record than one nobody filled in, and it is theirs to start.
  * **Why their reviews are what they are.** The applicability sentence, in
    the words they were emailed, on the page — because a rule somebody is told
    once in an email is a rule they will ask about in March.
  * **"Ask to change it."** The one way to move a goal after it is agreed, and
    the request goes to the same two people who agreed it.
  * **Marking a goal complete.** Finishing something is a thing worth being
    able to say out loud, and it is not a score.
  * **Past years.** The whole of a closed year, read from the copy frozen when
    it was put away — never recomputed, because a closed year that re-answers
    is a closed year nobody believes.

THE CONTROLLER STILL HOLDS NO RULES. Every refusal here is a sentence this file
wrote, so the journey a person walks in a browser is the journey the test suite
walks in Python.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .goals_common import (
    CHANGE_KINDS, CHANGE_OPEN, MAX_KRS, SET_STATE_LABEL, as_id, due_words,
)
from .pb_my_goals import _pct

_logger = logging.getLogger(__name__)


def _tidy(value):
    """"4.2" and "88", never "88.0" (R207).

    THE FROZEN COPY KEEPS REAL NUMBERS — it is the audit record of what the
    year came out at and rounding it for a screen would be rounding the
    evidence. So the tidying happens on the way OUT, here, every time a
    frozen figure is handed to a page.
    """
    if value is None:
        return None
    number = round(float(value), 2)
    return int(number) if number == int(number) else number


class PbMyGoalsYear(models.AbstractModel):
    _inherit = 'pb.my.goals'

    # ==================================================================
    #  The page
    # ==================================================================
    @api.model
    def home(self):
        """B1's page, plus the year that is happening to it."""
        payload = super().home()
        if not payload.get('ok') or payload.get('empty'):
            return payload
        sheet = self._current()
        today = fields.Date.today()
        payload.update({
            'checkin': self._checkin(sheet, today),
            'checkins_done': self._checkins_done(sheet),
            'reviews': self._reviews(sheet, today),
            'why_reviews': sheet.applicability_note or '',
            'prorated': bool(sheet.prorated),
            'changes': self._changes(sheet),
            'may_change': sheet.state == 'locked',
            'change_kinds': [
                {'key': key, 'label': label} for key, label in CHANGE_KINDS
                # THE EMPLOYEE'S OWN PAGE OFFERS THREE OF THE FOUR. Changing
                # the weights is the manager's word — it always was — so
                # asking for a reweight from here would be asking for
                # something this page has never let anybody type.
                if key != 'reweight'],
            'scores': self._scores(sheet),
            'closed': sheet.state == 'closed',
            'max_krs': MAX_KRS,
        })
        # `_others` is B1's; it gains the frozen score so a past year says
        # what it came out at rather than only how far along it got.
        payload['others'] = self._others_with_scores(sheet)
        # WHETHER EACH GOAL IS FINISHED, STAMPED ONTO B1'S OWN GOAL DICTS
        # rather than sent as a second list the template has to join against.
        # Two lists about the same rows is how a screen ends up showing one
        # goal's tick beside another goal's title.
        done = {goal.id: bool(goal.done_at)
                for goal in sheet.with_context(active_test=False).goal_ids}
        for row in payload.get('goals') or []:
            row['done'] = done.get(row['id'], False)
        return payload

    # -------------------------------------------------- the conversation
    @api.model
    def _checkin(self, sheet, today):
        """The one the page offers to write up: the oldest still open."""
        row = self.env['pb.goal.checkin'].sudo().search([
            ('set_id', '=', sheet.id), ('state', '=', 'planned'),
        ], order='month', limit=1)
        if not row:
            return {}
        return {
            'id': row.id,
            'month_word': row._month_word(),
            'planned': str(row.scheduled_date or ''),
            'due_words': due_words(row.scheduled_date, today),
            'overdue': bool(row.scheduled_date
                            and row.scheduled_date < today),
            'manager': sheet.manager_employee_id.sudo().name or '',
        }

    @api.model
    def _checkins_done(self, sheet):
        """The months already written up, newest first. Evidence, not a log."""
        rows = self.env['pb.goal.checkin'].sudo().search([
            ('set_id', '=', sheet.id), ('state', 'in', ('done', 'missed')),
        ], order='month desc', limit=12)
        return [{
            'id': row.id,
            'month_word': row._month_word(),
            'state': row.state,
            'state_word': row._state_word(),
            'note': row.progress_note or '',
            'blockers': row.blockers or '',
            'who': row.done_by_id.name or '',
            'when': str(row.done_at or '')[:10],
        } for row in rows]

    @api.model
    def write_up_checkin(self, checkin_id, note, blockers=''):
        """The employee's own write-up. Ownership proved, then done."""
        row = self._own_checkin(checkin_id)
        row.action_checkin_done(note, blockers)
        return {'ok': True, 'sentence': _(
            "Written up. %s is on the record, and your manager can see it.",
            row._month_word())}

    @api.model
    def _own_checkin(self, checkin_id):
        row = self.env['pb.goal.checkin'].sudo().browse(
            as_id(checkin_id)).exists()
        me = self._me()
        if not row or not me or row.employee_id.id != me.id:
            raise UserError(_(
                "That one is not yours. If you think it should be, tell your "
                "HR team."))
        return row

    # ------------------------------------------------------- the reviews
    @api.model
    def _reviews(self, sheet, today):
        rows = self.env['pb.goal.review'].sudo().search(
            [('set_id', '=', sheet.id)], order='due_date')
        return [{
            'id': row.id,
            'kind_word': row._kind_word(),
            'due': str(row.due_date or ''),
            'due_words': ('' if row.state == 'done'
                          else due_words(row.due_date, today)),
            'state': row.state,
            'state_word': row._state_word(),
            'manager_note': row.manager_note or '',
            'employee_note': row.employee_note or '',
            'when': str(row.done_at or '')[:10],
        } for row in rows]

    @api.model
    def say_on_review(self, review_id, note):
        """What the employee wants on the record before it is written up.

        THE ONE THING THEY MAY WRITE ON A REVIEW, and it is deliberately not a
        score: the manager scores, the employee says what they want said, and
        keeping those two apart is what makes the review a conversation rather
        than a negotiation over a number.
        """
        row = self.env['pb.goal.review'].sudo().browse(
            as_id(review_id)).exists()
        me = self._me()
        if not row or not me or row.employee_id.id != me.id:
            raise UserError(_("That one is not yours."))
        if row.state == 'done':
            raise UserError(_(
                "That review has been written up already. Talk to your "
                "manager if something is missing from it."))
        written = (note or '').strip()
        if not written:
            raise UserError(_("Write what you would like said."))
        row.write({'employee_note': written})
        return {'ok': True, 'sentence': _(
            "Saved. Your manager reads this when they write the review up.")}

    # ------------------------------------------------- asking for a change
    @api.model
    def _changes(self, sheet):
        rows = self.env['pb.goal.change'].sudo().search(
            [('set_id', '=', sheet.id)], order='id desc', limit=12)
        return [{
            'id': row.id,
            'kind_word': row._kind_word(),
            'summary': row.summary or '',
            'reason': row.reason or '',
            'state': row.state,
            'state_word': row._state_word(),
            'open': row.state in CHANGE_OPEN,
            'agreed': row.state == 'approved',
            'refused': row.state == 'refused',
            'refuse_note': row.refuse_note or '',
            'when': str(row.create_date or '')[:10],
            'applied': str(row.applied_at or '')[:10],
        } for row in rows]

    @api.model
    def ask_for_change(self, kind, values, reason, goal_id=None):
        """"Ask to change it." The employee's one door after the lock."""
        sheet = self._current()
        if not sheet:
            raise UserError(_("You have no goal sheet open."))
        if sheet.state != 'locked':
            raise UserError(_(
                "Your goals are %s. You only have to ask once they have been "
                "agreed and locked.",
                (SET_STATE_LABEL.get(sheet.state, sheet.state) or '').lower()))
        if kind == 'reweight':
            raise UserError(_(
                "What each goal is worth is your manager's word. Ask them to "
                "change the weights and they can do it from their side."))
        if goal_id:
            # OWNERSHIP PROVED BEFORE ANYTHING IS READ OR WRITTEN. A crafted
            # request must never reach somebody else's goal.
            self._own('pb.goal', goal_id)
        change = self.env['pb.goal.change'].raise_change(
            sheet.id, kind, values, reason, goal_id)
        change.action_change_submit()
        return {'ok': True, 'change_id': change.id, 'sentence': _(
            "Asked. %(who)s looks at it first, then the HR team. You will "
            "hear either way.",
            who=sheet.manager_employee_id.sudo().name or _('Your manager'))}

    # ---------------------------------------------------- marking one done
    @api.model
    def mark_goal_done(self, goal_id, done=True):
        goal = self._own('pb.goal', goal_id)
        if done:
            goal.action_goal_done()
            return {'ok': True, 'sentence': _(
                "\"%s\" is marked complete. Your manager sees it on their "
                "side.", goal.title or '')}
        goal.action_goal_reopen()
        return {'ok': True, 'sentence': _("\"%s\" is open again.",
                                          goal.title or '')}

    # ---------------------------------------------------------- the scores
    @api.model
    def _scores(self, sheet):
        """What the manager has said so far, and nothing they have not.

        A SCORE THAT IS HALF IN IS NOT SHOWN AS A NUMBER. An employee who
        reads "2.0" over a sheet where one of three goals has been marked
        would spend the afternoon on a figure that is about to change.
        """
        if sheet.state == 'closed':
            frozen = sheet.frozen()
            return {
                'shown': True,
                'closed': True,
                'scored': frozen.get('score') is not None,
                'score': _tidy(frozen.get('score')),
                'band': frozen.get('band') or '',
                'goals': frozen.get('goals') or [],
                'sentence': _(
                    "This year is finished. %(what)s",
                    what=(_("You came out at %(score)s out of 5 — %(band)s.",
                            score=_tidy(frozen.get('score')),
                            band=frozen.get('band') or '')
                          if frozen.get('score') is not None
                          else _("It was closed without a score."))),
            }
        if not sheet.scored:
            return {'shown': False, 'closed': False, 'scored': False,
                    'sentence': _(
                        "Your manager scores your key results at the half-way "
                        "review and again at the end of the year. Nothing is "
                        "shown here until every one of them has a mark.")}
        return {
            'shown': True,
            'closed': False,
            'scored': True,
            'score': round(sheet.score or 0.0, 2),
            'band': sheet.score_band or '',
            'sentence': _(
                "Your manager has scored everything. You are at %s so far — "
                "it is final when the year is closed.", sheet._score_words()),
        }

    @api.model
    def _others_with_scores(self, current):
        """Past years, each with what it came out at."""
        sets = self._my_sets()
        out = []
        for other in sets:
            if current and other.id == current.id:
                continue
            frozen = other.frozen() if other.state == 'closed' else {}
            out.append({
                'id': other.id,
                'cycle': other.cycle_id.name or '',
                'state_word': SET_STATE_LABEL.get(other.state, other.state),
                'closed': other.state == 'closed',
                'progress': _tidy(frozen.get('progress')
                                  if frozen.get('progress') is not None
                                  else (other.progress or 0.0)),
                'score': _tidy(frozen.get('score')),
                'band': frozen.get('band') or '',
                'goals': frozen.get('goals') or [],
            })
        return out[:6]

    @api.model
    def past_year(self, set_id):
        """One closed year, opened out — read from the frozen copy.

        NEVER RECOMPUTED. A closed year read live would re-answer the day
        somebody corrected a weight somewhere else, and a past year that
        changes is a past year nobody believes.
        """
        sheet = self._own('pb.goal.set', set_id)
        frozen = sheet.frozen()
        if not frozen:
            return {'ok': True, 'live': True, 'cycle': sheet.cycle_id.name
                    or '', 'goals': [], 'sentence': _(
                        "That year has not been closed yet, so it is still "
                        "the page above.")}
        # EVERY FIGURE TIDIED ON THE WAY OUT, and none of them changed in the
        # frozen copy itself.
        goals = []
        for goal in frozen.get('goals') or []:
            goals.append(dict(
                goal,
                weight=_tidy(goal.get('weight')),
                progress=_tidy(goal.get('progress')),
                score=_tidy(goal.get('score')),
                krs=[dict(kr,
                          progress=_tidy(kr.get('progress')),
                          target=_tidy(kr.get('target')),
                          current=_tidy(kr.get('current')))
                     for kr in (goal.get('krs') or [])]))
        return dict(frozen, ok=True, live=False, id=sheet.id, goals=goals,
                    progress=_tidy(frozen.get('progress')),
                    score=_tidy(frozen.get('score')))
