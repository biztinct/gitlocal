# -*- coding: utf-8 -*-
"""`pb.goal` — one thing somebody is trying to do this year.

A GOAL WITHOUT A KEY RESULT IS A WISH, which is why the sheet refuses to go in
without at least one on every goal. The goal is the sentence a person says out
loud ("grow the north region"); the key results are the two or three numbers
that make it answerable.

THE WEIGHT BELONGS TO THE MANAGER. The employee writes what they are going to
do; the manager says which of it matters most, and the sheet cannot be agreed
until those add up to a hundred. That is enforced in three places and they all
say the same sentence: the record's own `_require_weights`, the engine's
pre-decision hook, and the board.

`locked` IS A COLUMN AND NOT A COMPUTE. It is written once, by the lock, and it
is what makes a goal read-only afterwards — a compute reading the sheet's state
would be identical today and would quietly change meaning the day somebody adds
a state, and a read-only rule that changes meaning is a read-only rule nobody
can rely on.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .goals_common import MAX_KRS, RATINGS, RATING_LABEL, SET_EDITABLE

_logger = logging.getLogger(__name__)


class PbGoal(models.Model):
    _name = 'pb.goal'
    _description = 'Goal'
    _order = 'set_id, sequence, id'

    sequence = fields.Integer(default=10)
    set_id = fields.Many2one(
        'pb.goal.set', string='Goal sheet', required=True, index=True,
        ondelete='cascade')
    #: RELATED **STORED**, because the board filters and groups on it and a
    #: non-stored related cannot go in a search-view domain (R10). It follows a
    #: raw-SQL parent update only if the migration re-points it explicitly
    #: (R9); there is no such migration here and there is not meant to be.
    employee_id = fields.Many2one(
        'hr.employee', string='Whose goal', related='set_id.employee_id',
        store=True, index=True, readonly=True)
    cycle_id = fields.Many2one(
        'pb.goal.cycle', string='Goal year', related='set_id.cycle_id',
        store=True, index=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='set_id.company_id',
        store=True, index=True, readonly=True)
    state = fields.Selection(
        related='set_id.state', string='Status', store=True, readonly=True,
        index=True)

    title = fields.Char(string='What they are going to do', required=True)
    description = fields.Text(
        string='Why it matters and what good looks like', required=True,
        help='A sentence or two. What changes if this goes well, and how '
             'anybody would know.')
    date_start = fields.Date(string='From')
    date_end = fields.Date(string='Done by', required=True)
    weight = fields.Float(
        string='Weight', default=0.0,
        help='How much of the year this goal is, out of 100. The manager sets '
             'these and they have to add up to 100 before the sheet can be '
             'agreed.')
    self_rating = fields.Selection(
        RATINGS, string='How they think it will go',
        help='The employee\'s own view when they send the sheet in.')
    template_id = fields.Many2one(
        'pb.goal.template', string='Started from', ondelete='set null',
        readonly=True)
    locked = fields.Boolean(
        string='Locked', default=False, copy=False, readonly=True,
        help='Set when the HR lead locks the sheet. A locked goal cannot be '
             'reworded; progress on its key results still moves.')

    kr_ids = fields.One2many('pb.goal.kr', 'goal_id', string='Key results')
    kr_count = fields.Integer(string='Key results', compute='_compute_progress',
                              store=True)
    progress = fields.Float(
        string='How far along', compute='_compute_progress', store=True,
        aggregator='avg',
        help='The average of how far the key results have got.')

    # ------------------------------------------------------------- computed
    @api.depends('kr_ids', 'kr_ids.progress')
    def _compute_progress(self):
        for goal in self:
            krs = goal.kr_ids
            goal.kr_count = len(krs)
            goal.progress = round(
                sum(krs.mapped('progress')) / len(krs), 1) if krs else 0.0

    def _compute_display_name(self):
        for goal in self:
            goal.display_name = goal.title or _('Goal')

    def _rating_word(self):
        self.ensure_one()
        return RATING_LABEL.get(self.self_rating or '', '')

    # -------------------------------------------------------------- guards
    @api.constrains('weight')
    def _check_weight(self):
        for goal in self:
            if goal.weight < 0 or goal.weight > 100:
                raise ValidationError(_(
                    "A weight is somewhere between 0 and 100. \"%(what)s\" is "
                    "set to %(n)s.", what=goal.title or '',
                    n=round(goal.weight, 2)))

    @api.constrains('date_start', 'date_end', 'set_id')
    def _check_dates(self):
        for goal in self:
            if goal.date_start and goal.date_end \
                    and goal.date_end < goal.date_start:
                raise ValidationError(_(
                    "\"%s\" is meant to be done before it starts.",
                    goal.title or ''))
            cycle = goal.set_id.sudo().cycle_id
            if not cycle or not goal.date_end:
                continue
            # INSIDE THE YEAR, and the refusal says what the year is. A date
            # outside it is almost always a typo in the year part, and a
            # message that repeats the boundaries is a message somebody can
            # act on without opening another screen.
            if not (cycle.date_start <= goal.date_end <= cycle.date_end):
                raise ValidationError(_(
                    "\"%(what)s\" is meant to be done by %(when)s, which is "
                    "outside %(cycle)s — that runs from %(start)s to "
                    "%(end)s.", what=goal.title or '', when=goal.date_end,
                    cycle=cycle.name or '', start=cycle.date_start,
                    end=cycle.date_end))

    @api.constrains('kr_ids')
    def _check_kr_count(self):
        for goal in self:
            if len(goal.kr_ids) > MAX_KRS:
                raise ValidationError(_(
                    "%(n)s key results on one goal is more than anybody "
                    "measures. Keep it to %(max)s.", n=len(goal.kr_ids),
                    max=MAX_KRS))

    # ------------------------------------------- what a lock actually stops
    #: The columns a LOCKED goal still accepts. Everything else is the plan,
    #: and the plan is what the lock is about. `locked` itself is here because
    #: the lock has to be able to set it, and `sequence` because reordering a
    #: list is not changing it.
    #: B2 added five more: marking a goal COMPLETE, the score that follows
    #: from its key results, and the archive flag the year-end close sets.
    #: None of them is the plan — they are what happened to the plan — and a
    #: lock that refused them would freeze the very columns the rest of the
    #: year is about.
    _AFTER_LOCK = {'locked', 'sequence', 'progress', 'kr_count',
                   'done_at', 'done_by_id', 'score', 'scored', 'active'}
    #: The columns the EMPLOYEE may never write, locked or not. Weight is the
    #: manager's word (and the record rule enforces it as well — a rule and a
    #: guard, because a rule cannot say "this field but not that one").
    _MANAGER_ONLY = {'weight'}

    def write(self, vals):
        if not self.env.su:
            touched = set(vals) - self._AFTER_LOCK
            locked = self.filtered('locked')
            if locked and touched:
                raise UserError(_(
                    "%(what)s has been agreed and locked, so it cannot be "
                    "changed. Move the numbers on its key results instead, or "
                    "ask HR to send the sheet back.",
                    what=', '.join('"%s"' % (g.title or '') for g in locked[:3])
                ))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            locked = self.filtered(
                lambda g: g.locked or g.set_id.state not in SET_EDITABLE)
            if locked:
                raise UserError(_(
                    "This sheet has been sent in, so its goals cannot be "
                    "deleted. Ask for it to be sent back if something has to "
                    "change."))
        return super().unlink()
