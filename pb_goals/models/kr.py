# -*- coding: utf-8 -*-
"""`pb.goal.kr` — the number that says whether a goal was met, and its history.

PROGRESS IS NOT A CHANGE OF PLAN. That single sentence is the whole design of
this file: a goal is frozen when the sheet is locked, and a key result's
progress keeps moving anyway, because moving it is the work rather than a
revision of it. So the employee may write `current` and `progress` on their own
key results for the whole year, and may not touch the title, the target or the
measure once the sheet is agreed.

EVERY MOVE IS KEPT. `pb.goal.kr.history` gets a row on every progress change,
with who moved it and what they said — which is what makes a year-end
conversation a conversation about a record rather than about two people's
memories. Written from `write()` and not from a button, so a move made on the
employee's page, on the backend form or by an import all leave the same trail.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PbGoalKr(models.Model):
    _name = 'pb.goal.kr'
    _description = 'Key result'
    _order = 'goal_id, sequence, id'

    sequence = fields.Integer(default=10)
    goal_id = fields.Many2one(
        'pb.goal', string='Goal', required=True, index=True,
        ondelete='cascade')
    set_id = fields.Many2one(
        'pb.goal.set', string='Goal sheet', related='goal_id.set_id',
        store=True, index=True, readonly=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Whose', related='goal_id.employee_id',
        store=True, index=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', related='goal_id.company_id',
        store=True, index=True, readonly=True)

    title = fields.Char(string='What is being measured', required=True)
    measure = fields.Char(
        string='In what', help='The unit, in the words people use: "leads a '
                               'month", "customers", "days", "%".')
    target = fields.Float(string='Target')
    current = fields.Float(string='Where it is now')
    progress = fields.Float(
        string='How far along', default=0.0, aggregator='avg',
        help='0 to 100. Moved by the person whose goal it is, at any time, '
             'including after the sheet is locked.')
    due_date = fields.Date(string='By when')
    history_ids = fields.One2many('pb.goal.kr.history', 'kr_id',
                                  string='Every move')
    last_moved_on = fields.Datetime(string='Last moved', readonly=True,
                                    copy=False)

    # -------------------------------------------------------------- guards
    @api.constrains('progress')
    def _check_progress(self):
        for kr in self:
            if kr.progress < 0 or kr.progress > 100:
                raise ValidationError(_(
                    "Progress is a figure between 0 and 100. \"%(what)s\" is "
                    "set to %(n)s.", what=kr.title or '',
                    n=round(kr.progress, 2)))

    def _compute_display_name(self):
        for kr in self:
            kr.display_name = kr.title or _('Key result')

    #: The columns a LOCKED key result still accepts — the work, not the plan.
    #: B2 added the score and its stamps: a mark out of five is a statement
    #: ABOUT the plan and is made months after it was frozen, so a lock that
    #: refused it would make the year unscoreable.
    _AFTER_LOCK = {'current', 'progress', 'last_moved_on', 'sequence',
                   'score', 'score_value', 'scored_at', 'scored_by_id'}

    #: THE SCORE IS NOT THE EMPLOYEE'S WORD (B2). The employee already said
    #: what they thought in April — that is `self_rating` on the goal, and it
    #: is a different question asked of a different person. A record rule is a
    #: domain and cannot say "this field but not that one", so the rule lets
    #: somebody write their own key results and this says which columns are
    #: not theirs.
    _MANAGER_ONLY = {'score', 'scored_at', 'scored_by_id'}

    def write(self, vals):
        """Write the trail as well as the value, in that order.

        The BEFORE value is read here rather than in a compute, because a
        compute cannot see what a field used to hold and a trail that records
        the new value twice is not a trail.
        """
        before = {kr.id: (kr.progress, kr.current) for kr in self}
        if not self.env.su and (set(vals) & self._MANAGER_ONLY):
            # READ AS THE SYSTEM (R56/R104). The person writing a score is by
            # design the employee's own MANAGER, who holds no HR group — and
            # one field of an `hr.employee` prefetches forty, about forty of
            # which sit behind payroll groups. A guard that reads it as the
            # caller turns "the manager scored a key result" into an
            # AccessError naming forty fields nobody asked for. The security
            # boundary is the record rule that found the row, not this read.
            mine = self.filtered(
                lambda k: k.sudo().employee_id.user_id.id == self.env.uid)
            if mine and not self.env.user.has_group(
                    'pb_goals.group_goals_manager'):
                raise UserError(_(
                    "How a key result went is your manager's word, not "
                    "yours. What you think of it is the rating you gave when "
                    "you wrote the goal."))
        if not self.env.su and (set(vals) - self._AFTER_LOCK):
            locked = self.filtered(lambda k: k.goal_id.locked)
            if locked:
                raise UserError(_(
                    "This goal has been agreed and locked, so its key results "
                    "cannot be reworded or re-targeted. Move the figure "
                    "instead, or ask HR to send the sheet back."))
        result = super().write(vals)
        if 'progress' in vals or 'current' in vals:
            note = self.env.context.get('pb_goals_note') or ''
            stamp = fields.Datetime.now()
            rows = []
            for kr in self:
                was_progress, was_current = before.get(kr.id, (None, None))
                if was_progress == kr.progress and was_current == kr.current:
                    continue
                rows.append({
                    'kr_id': kr.id,
                    'at': stamp,
                    'progress': kr.progress,
                    'current': kr.current,
                    'note': note,
                    'by_user_id': self.env.uid,
                })
            if rows:
                # SUDO, AND ON PURPOSE. The trail is written by whoever moved
                # the number, including an employee who holds no permission on
                # a history table they are not meant to be able to edit. The
                # row names them; the permission is not theirs.
                self.env['pb.goal.kr.history'].sudo().create(rows)
                super(PbGoalKr, self.with_context(
                    pb_goals_trail=True)).write({'last_moved_on': stamp})
        return result

    @api.model
    def move(self, kr_id, progress, current=None, note=''):
        """The one public way to move a key result.

        Public because the employee's own page calls it over the wire; the
        ownership check is inside, on the record, and never in the route (the
        portal controller proves who is asking and this proves the row is
        theirs). A record argument arrives as a plain integer (R43), so the id
        is coerced at the door.
        """
        from .goals_common import as_id
        kr = self.browse(as_id(kr_id)).exists()
        if not kr:
            raise UserError(_("That key result is gone."))
        try:
            value = float(progress)
        except (TypeError, ValueError):
            raise UserError(_("Progress has to be a number between 0 and 100."))
        value = max(0.0, min(100.0, round(value, 2)))
        vals = {'progress': value}
        if current is not None and current != '':
            try:
                vals['current'] = float(current)
            except (TypeError, ValueError):
                pass
        kr.with_context(pb_goals_note=(note or '')[:500]).write(vals)
        return {'ok': True, 'progress': kr.progress, 'current': kr.current,
                'goal_progress': kr.goal_id.progress,
                'set_progress': kr.set_id.progress}


class PbGoalKrHistory(models.Model):
    _name = 'pb.goal.kr.history'
    _description = 'Key result history'
    #: Newest first: the question somebody asks of a history is "what happened
    #: last", and a list that opens on January is a list nobody scrolls.
    _order = 'at desc, id desc'

    kr_id = fields.Many2one('pb.goal.kr', string='Key result', required=True,
                            index=True, ondelete='cascade')
    set_id = fields.Many2one('pb.goal.set', string='Goal sheet',
                             related='kr_id.set_id', store=True, index=True,
                             readonly=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 related='kr_id.company_id', store=True,
                                 index=True, readonly=True)
    at = fields.Datetime(string='When', required=True,
                         default=fields.Datetime.now)
    progress = fields.Float(string='Moved to')
    current = fields.Float(string='Figure')
    note = fields.Char(string='What they said')
    by_user_id = fields.Many2one('res.users', string='Who moved it',
                                 default=lambda self: self.env.user)

    def _compute_display_name(self):
        for row in self:
            row.display_name = _("%(pct)s%% on %(when)s",
                                 pct=int(round(row.progress or 0)),
                                 when=row.at and row.at.date() or '')
