# -*- coding: utf-8 -*-
"""What the year was worth, in one number that can be explained.

THE ARITHMETIC, IN WORDS, BECAUSE SOMEBODY HAS TO BE ABLE TO ARGUE WITH IT.

  1. The MANAGER scores each key result out of five. Nought is "not done" and
     is a real answer; five is "well above". Nobody else scores anything — an
     employee scoring their own key results is a self-assessment, which is the
     `self_rating` they already gave in April and is a different question.
  2. A GOAL's score is the plain average of its key results. Equal-weighted,
     deliberately: a goal's key results are the two or three numbers that
     together say whether it was met, and asking somebody to weight them
     against each other is asking a question nobody has an answer to. The
     weight that matters is the one on the GOAL, and the manager already set
     it.
  3. THE SHEET's score is the weighted average of its goals: Σ (goal weight ×
     goal score) ÷ 100. Which is the whole reason the weights have to add up
     to a hundred, and the whole reason a manager is asked to set them.
  4. The BAND is what the number is called (`pb.goal.band`).

NOTHING IS SCORED UNTIL EVERYTHING IS. A goal with one key result scored and
one not has NO score — not a half-score, not the one number that happens to be
there. Same for the sheet: a sheet with an unscored goal reads "not yet"
rather than a figure that is about to change. A number that is right only if
you know what is missing from it is worse than no number, because a screen
cannot say what is missing from it.

THE FROZEN COPY IS WHAT CLOSING MEANS. Every figure here is a live compute
until the year is closed; `frozen_json` on the sheet is the copy taken at that
moment, and it is what the past-years page reads. A live compute over a closed
year would quietly re-answer the day somebody corrected a weight in a
neighbouring row.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .goals_common import (
    SCORES, SCORE_LABEL, SCORE_MAX, WEIGHT_TOTAL, as_id,
)

_logger = logging.getLogger(__name__)


class PbGoalKrScore(models.Model):
    """The manager's mark on one key result."""

    _inherit = 'pb.goal.kr'

    #: A SELECTION AND NOT A FLOAT. "3" on its own means nothing on a screen
    #: and a translator handed a bare integer has nothing to translate; the
    #: five words are the same five the employee used in April, so "On track"
    #: in the self-rating column and "On track" in the score column are the
    #: same claim made by two people.
    score = fields.Selection(
        SCORES, string='How it went', copy=False, index=True,
        help='Set by the manager at the half-way review and again at the end '
             'of the year. Nought means it was not done; five means it went '
             'well above what was asked.')
    score_value = fields.Float(
        string='Score', compute='_compute_score_value', store=True,
        aggregator='avg', readonly=True,
        help='The same answer as a number, so it can be averaged.')
    scored_at = fields.Datetime(string='Scored on', readonly=True, copy=False)
    scored_by_id = fields.Many2one('res.users', string='Scored by',
                                   readonly=True, copy=False)

    @api.depends('score')
    def _compute_score_value(self):
        for kr in self:
            kr.score_value = float(kr.score) if kr.score else 0.0

    def _score_word(self):
        self.ensure_one()
        return SCORE_LABEL.get(self.score or '', '')


class PbGoalScore(models.Model):
    """A goal's score: the plain average of its key results."""

    _inherit = 'pb.goal'

    #: WHY THERE IS AN `active` AT ALL. Closing a year archives its goals, so
    #: the live lists stop being full of last year's work — and NOTHING about
    #: the numbers changes, because every compute on the sheet reads its goals
    #: with `active_test=False`. An archive that also changed the arithmetic
    #: would make a closed year's score drift the day it was closed.
    active = fields.Boolean(default=True)

    scored = fields.Boolean(string='Scored', compute='_compute_score',
                            store=True, readonly=True)
    score = fields.Float(
        string='Score out of 5', compute='_compute_score', store=True,
        aggregator='avg', readonly=True,
        help='The average of the scores on its key results. Empty until '
             'every one of them has been scored.')
    done_at = fields.Datetime(string='Marked complete on', readonly=True,
                              copy=False)
    done_by_id = fields.Many2one('res.users', string='Marked complete by',
                                 readonly=True, copy=False)

    @api.depends('kr_ids', 'kr_ids.score')
    def _compute_score(self):
        for goal in self:
            krs = goal.kr_ids
            if not krs or any(not kr.score for kr in krs):
                goal.scored = False
                goal.score = 0.0
                continue
            goal.scored = True
            goal.score = round(
                sum(float(kr.score) for kr in krs) / len(krs), 2)

    def _score_words(self):
        """"3.5 out of 5" or "not scored yet" — never a bare 0.0."""
        self.ensure_one()
        if not self.scored:
            return ''
        value = round(self.score or 0.0, 2)
        shown = int(value) if value == int(value) else value
        return _("%(score)s out of %(max)s", score=shown,
                 max=int(SCORE_MAX))

    # ------------------------------------------------------------ complete
    def action_goal_done(self):
        """"This one is finished." The employee's own press.

        IT IS NOT A SCORE AND IT DOES NOT PRETEND TO BE. Marking a goal
        complete says the work is done; what it was worth is still the
        manager's word, at the review. Keeping the two apart is what stops
        "I finished it" and "it went well" being the same claim.
        """
        for goal in self:
            record = goal.sudo()
            if record.done_at:
                continue
            if not self.env.su and not self.env.user.has_group(
                    'pb_goals.group_goals_manager'):
                employee = record.employee_id
                manager = record.set_id.manager_user_id
                if self.env.uid not in (employee.user_id.id, manager.id):
                    raise UserError(_(
                        "A goal is marked complete by the person whose goal "
                        "it is, by their manager, or by the HR team."))
            record.write({'done_at': fields.Datetime.now(),
                          'done_by_id': self.env.uid})
            record.set_id.message_post(body=_(
                "\"%(what)s\" was marked complete by %(who)s.",
                what=record.title or '', who=self.env.user.name or ''))
        return True

    def action_goal_reopen(self):
        """It was not finished after all. Nothing is destroyed by saying so."""
        for goal in self:
            goal.sudo().write({'done_at': False, 'done_by_id': False})
        return True


class PbGoalSetScore(models.Model):
    """The sheet's score, its band, and the copy taken when the year closes."""

    _inherit = 'pb.goal.set'

    scored = fields.Boolean(string='Scored', compute='_compute_set_score',
                            store=True, readonly=True)
    score = fields.Float(
        string='Score out of 5', compute='_compute_set_score', store=True,
        aggregator='avg', readonly=True,
        help='Every goal\'s score, weighted by what the manager said each '
             'goal was worth. Empty until every goal has been scored.')
    score_band = fields.Char(string='Band', compute='_compute_set_score',
                             store=True, readonly=True)
    score_tone = fields.Char(string='Band tone', compute='_compute_set_score',
                             store=True, readonly=True)
    goals_done = fields.Integer(string='Goals finished',
                                compute='_compute_set_score', store=True)
    #: THE COPY TAKEN AT THE MOMENT OF CLOSING. Everything above is a live
    #: compute; this is what the past-years page reads, so a closed year says
    #: the same thing next March as it did the day it was put away.
    frozen_json = fields.Text(string='The year as it was closed',
                              readonly=True, copy=False)
    closed_at = fields.Datetime(string='Closed on', readonly=True, copy=False)
    #: When each rung was reached, so the reports can say how long things took.
    #: `locked_at` is B1's; these two are its missing halves.
    submitted_at = fields.Datetime(string='Sent in on', readonly=True,
                                   copy=False)
    manager_ok_at = fields.Datetime(string='Manager agreed on', readonly=True,
                                    copy=False)

    # ------------------------------------------------------------- the maths
    def _all_goals(self):
        """Every goal on this sheet, archived ones included.

        CLOSING A YEAR ARCHIVES ITS GOALS AND MUST NOT CHANGE ITS NUMBERS. A
        plain `self.goal_ids` filters archived rows out, so a closed sheet's
        weights would fall to nought and its progress to zero the moment it
        was put away — with no error and a perfectly normal-looking screen.
        """
        self.ensure_one()
        return self.sudo().with_context(active_test=False).goal_ids

    @api.depends('goal_ids', 'goal_ids.score', 'goal_ids.scored',
                 'goal_ids.weight', 'goal_ids.done_at', 'goal_ids.active')
    def _compute_set_score(self):
        for record in self:
            goals = record._all_goals()
            record.goals_done = len(goals.filtered('done_at'))
            total_weight = sum(goals.mapped('weight'))
            if not goals or any(not goal.scored for goal in goals) \
                    or total_weight <= 0:
                record.scored = False
                record.score = 0.0
                record.score_band = ''
                record.score_tone = ''
                continue
            value = round(sum((goal.weight or 0.0) * (goal.score or 0.0)
                              for goal in goals) / total_weight, 2)
            record.scored = True
            record.score = value
            band = record._band_for(value)
            record.score_band = band.name if band else ''
            record.score_tone = band.tone if band else ''

    def _band_for(self, value):
        """The band a score falls in — highest first, first match wins."""
        self.ensure_one()
        for band in self.sudo().cycle_id._bands():
            if band.holds(value):
                return band
        return self.env['pb.goal.band'].sudo().browse()

    def _score_words(self):
        self.ensure_one()
        if not self.scored:
            return ''
        value = round(self.score or 0.0, 2)
        shown = int(value) if value == int(value) else value
        if self.score_band:
            return _("%(score)s out of %(max)s · %(band)s", score=shown,
                     max=int(SCORE_MAX), band=self.score_band)
        return _("%(score)s out of %(max)s", score=shown, max=int(SCORE_MAX))

    def _unscored_goals(self):
        """The goals still waiting for a mark, for a sentence somebody reads."""
        self.ensure_one()
        return self._all_goals().filtered(lambda g: not g.scored)

    # ------------------------------------------------------------- scoring
    def _may_score(self):
        """Whose word a score is: the manager's, or the HR team's.

        NEVER THE EMPLOYEE'S, and that is enforced here AND in
        `pb.goal.kr.write` — a record rule is a domain and cannot say "this
        field but not that one", so the rule lets the owner write their key
        results and the guard says which columns.
        """
        self.ensure_one()
        if self.env.user.has_group('pb_goals.group_goals_manager'):
            return True
        return bool(self.sudo().manager_user_id.id == self.env.uid)

    def score_key_results(self, scores):
        """Score some key results. `scores` is `{kr_id: '0'..'5'}`.

        PARTIAL IS ALLOWED HERE, unlike the weights. A manager scores a year
        over two sittings and a screen that refuses to save nine marks because
        the tenth is not decided yet is a screen that loses nine marks.
        """
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_(
                "This year has been closed, so the scores cannot change. "
                "They are what they were on the day it was put away."))
        if not self._may_score():
            raise UserError(_(
                "Key results are scored by the person's own manager or by "
                "the HR team."))
        wanted = {int(key): str(value or '')
                  for key, value in dict(scores or {}).items()}
        allowed = dict(SCORES)
        mine = {kr.id: kr for kr in self._all_goals().mapped('kr_ids')}
        stamp = fields.Datetime.now()
        touched = self.env['pb.goal.kr'].sudo().browse()
        for kr_id, value in wanted.items():
            kr = mine.get(kr_id)
            if not kr:
                # A KEY RESULT THAT IS NOT ON THIS SHEET IS NOT AN ERROR TO
                # SHOUT ABOUT, it is a stale screen. Skipped, and the caller
                # is told how many landed.
                continue
            if value and value not in allowed:
                raise UserError(_(
                    "A score is one of nought to five. \"%s\" is not one of "
                    "them.", value))
            kr.sudo().write({
                'score': value or False,
                'scored_at': stamp if value else False,
                'scored_by_id': self.env.uid if value else False,
            })
            touched |= kr
        self.invalidate_recordset(['score', 'scored', 'score_band'])
        return {
            'ok': True,
            'saved': len(touched),
            'scored': bool(self.sudo().scored),
            'score': round(self.sudo().score or 0.0, 2),
            'band': self.sudo().score_band or '',
            'sentence': self._scoring_sentence(),
        }

    def _scoring_sentence(self):
        """What is left to do, in words, with the arithmetic in them."""
        self.ensure_one()
        record = self.sudo()
        if record.scored:
            return _(
                "Every key result is scored. %(who)s comes out at "
                "%(words)s.", who=record.employee_id.name or _('This person'),
                words=record._score_words())
        left = record._unscored_goals()
        if not left:
            return _("Nothing to score on this sheet yet.")
        return _(
            "%(n)s still to score: %(which)s. The sheet gets a score once "
            "every key result on it has one.", n=len(left),
            which=', '.join('"%s"' % (goal.title or '')
                            for goal in left[:4]))

    # ------------------------------------------------------- what closing is
    def _freeze(self):
        """The copy taken when the year closes. Read, never recomputed."""
        self.ensure_one()
        record = self.sudo()
        goals = record._all_goals().sorted(lambda g: (g.sequence, g.id))
        return json.dumps({
            'at': str(fields.Datetime.now()),
            'cycle': record.cycle_id.name or '',
            'employee': record.employee_id.name or '',
            'score': round(record.score or 0.0, 2) if record.scored else None,
            'band': record.score_band or '',
            'progress': round(record.progress or 0.0, 1),
            'weight_total': round(record.weight_total or 0.0, 1),
            'goals': [{
                'title': goal.title or '',
                'weight': round(goal.weight or 0.0, 1),
                'progress': round(goal.progress or 0.0, 1),
                'score': round(goal.score or 0.0, 2) if goal.scored else None,
                'done': bool(goal.done_at),
                'krs': [{
                    'title': kr.title or '',
                    'measure': kr.measure or '',
                    'target': kr.target or 0.0,
                    'current': kr.current or 0.0,
                    'progress': round(kr.progress or 0.0, 1),
                    'score': kr.score or '',
                } for kr in goal.kr_ids.sorted(lambda k: (k.sequence, k.id))],
            } for goal in goals],
        })

    def frozen(self):
        """The frozen copy, as a dict a screen can draw. `{}` if not closed."""
        self.ensure_one()
        try:
            return json.loads(self.frozen_json or '{}') or {}
        except (TypeError, ValueError):
            return {}
