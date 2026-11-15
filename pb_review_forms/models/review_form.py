# -*- coding: utf-8 -*-
"""The review form: one per goal year, written by HR, locked once used.

WHY IT LOCKS. Every answer is keyed on a line of this form. Changing a
question after somebody has answered it would put their answer under a
question they were never asked, so the first review sent in (by either side)
stamps `locked_at`, and from then on only WHEN the manager's part is shown
may still change. A new version is next year's form ("Copy to another year").

WHY A DRAFT CHANGES NOTHING. Only a form `published` for a year is read by
the reviews, the employee pages and the pay review. A year whose form is
still being written behaves exactly as a year with no form (P2 golden rule).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .rf_common import (
    FORM_STATES, MAX_CHOICES, MAX_QUESTIONS, MAX_SKILLS, QUESTION_TYPES,
    REVEAL_MODES, SECTIONS, WHO_ANSWERS,
)

_logger = logging.getLogger(__name__)


class PbReviewForm(models.Model):
    _name = 'pb.review.form'
    _description = 'Review form'
    _order = 'id desc'

    _one_per_year = models.Constraint(
        'unique(cycle_id)',
        'That goal year already has a review form.')

    cycle_id = fields.Many2one(
        'pb.goal.cycle', string='Goal year', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Company', related='cycle_id.company_id',
        store=True, index=True, readonly=True)
    name = fields.Char(string='Name', required=True,
                       default=lambda self: _('End-of-year review'))
    intro = fields.Text(
        string='A word to the employee',
        help='Shown at the top of the form, above the first question.')
    state = fields.Selection(FORM_STATES, string='Status', default='draft',
                             required=True, index=True, copy=False)
    share_goals = fields.Integer(string='Share for the goals score',
                                 default=70)
    share_skills = fields.Integer(string='Share for skills and values',
                                  default=30)
    share_questions = fields.Integer(string='Share for rated questions',
                                     default=0)
    reveal = fields.Selection(
        REVEAL_MODES, string='When the employee sees the manager\'s part',
        default='manager_done', required=True)
    reveal_date = fields.Date(string='Shown from')
    line_ids = fields.One2many('pb.review.form.line', 'form_id',
                               string='Skills, values and questions',
                               copy=True)
    published_at = fields.Datetime(string='In use since', readonly=True,
                                   copy=False)
    published_by_id = fields.Many2one('res.users', string='Put in use by',
                                      readonly=True, copy=False)
    locked_at = fields.Datetime(
        string='Locked on', readonly=True, copy=False,
        help='The day the first review was sent in. From then on the '
             'questions cannot change.')

    # ------------------------------------------------------------- reading
    def _skills(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: l.section == 'skill').sorted(lambda l: (l.sequence,
                                                               l.id))

    def _questions(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: l.section == 'question').sorted(lambda l: (l.sequence,
                                                                  l.id))

    def _manager_rated_questions(self):
        self.ensure_one()
        return self._questions().filtered(
            lambda l: l.qtype == 'rating' and l.who in ('both', 'manager'))

    @api.model
    def _published_for(self, cycle):
        """The form a goal year uses, or an empty recordset."""
        if not cycle:
            return self.sudo().browse()
        return self.sudo().search([('cycle_id', '=', cycle.id),
                                   ('state', '=', 'published')], limit=1)

    # ---------------------------------------------------------- the rules
    @api.constrains('share_goals', 'share_skills', 'share_questions')
    def _check_shares(self):
        for form in self:
            for value in (form.share_goals, form.share_skills,
                          form.share_questions):
                if value < 0 or value > 100:
                    raise ValidationError(_(
                        "A share is a number from 0 to 100."))

    def _problems(self):
        """Everything that stops this form being put in use, in words."""
        self.ensure_one()
        out = []
        total = (self.share_goals or 0) + (self.share_skills or 0) \
            + (self.share_questions or 0)
        if total != 100:
            out.append(_("The shares add up to %(have)s, not 100.",
                         have=total))
        skills = self._skills()
        questions = self._questions()
        if len(skills) > MAX_SKILLS:
            out.append(_("Keep it to %(n)s skills or values at most.",
                         n=MAX_SKILLS))
        if len(questions) > MAX_QUESTIONS:
            out.append(_("Keep it to %(n)s questions at most.",
                         n=MAX_QUESTIONS))
        if self.share_skills and not skills:
            out.append(_("Skills and values have a share but there are none "
                         "on the form."))
        if self.share_questions and not self._manager_rated_questions():
            out.append(_("Rated questions have a share but no question is "
                         "rated by the manager."))
        for line in self.line_ids:
            if not (line.name or '').strip():
                out.append(_("Every skill, value and question needs words."))
                break
        for line in questions.filtered(lambda l: l.qtype == 'choice'):
            if len(line._choice_list()) < 2:
                out.append(_("\"%(q)s\" needs at least two answers to pick "
                             "from.", q=line.name or ''))
        if self.reveal == 'date' and not self.reveal_date:
            out.append(_("Choose the date the manager's part is shown "
                         "from."))
        if self.cycle_id.state == 'closed':
            out.append(_("%(year)s is closed.", year=self.cycle_id.name or ''))
        return out

    def _check_editable(self):
        for form in self:
            if form.locked_at:
                raise UserError(_(
                    "This form is locked: the first review on it was sent in "
                    "on %(day)s. Copy it to another year to change it.",
                    day=fields.Date.to_string(form.locked_at.date())))

    #: What may still change on a locked form: only WHEN the manager's part
    #: is shown (and the status the presses write).
    _OPEN_WHEN_LOCKED = frozenset({'reveal', 'reveal_date', 'locked_at',
                                   'state', 'published_at',
                                   'published_by_id'})

    def write(self, vals):
        if set(vals) - self._OPEN_WHEN_LOCKED:
            self._check_editable()
        if 'cycle_id' in vals and any(f.cycle_id.id != vals['cycle_id']
                                      for f in self):
            raise UserError(_("A form stays with the goal year it was "
                              "written for. Copy it to another year."))
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()

    def _lock_now(self):
        """Stamp the lock the first time a review on it is sent in."""
        for form in self.sudo():
            if not form.locked_at:
                form.write({'locked_at': fields.Datetime.now()})
        return True

    # ------------------------------------------------------------ presses
    def action_publish(self):
        for form in self:
            problems = form._problems()
            if problems:
                raise UserError(' '.join(problems))
            form.write({'state': 'published',
                        'published_at': fields.Datetime.now(),
                        'published_by_id': self.env.uid})
        return True

    def action_unpublish(self):
        for form in self:
            form._check_editable()
            form.write({'state': 'draft'})
        return True


class PbReviewFormLine(models.Model):
    _name = 'pb.review.form.line'
    _description = 'Review form line'
    _order = 'form_id, section, sequence, id'

    form_id = fields.Many2one('pb.review.form', string='Form', required=True,
                              index=True, ondelete='cascade')
    section = fields.Selection(SECTIONS, string='Part', required=True,
                               default='question')
    sequence = fields.Integer(string='Order', default=10)
    name = fields.Char(string='Words', required=True)
    description = fields.Char(string='What good looks like')
    qtype = fields.Selection(QUESTION_TYPES, string='Kind of answer',
                             default='rating', required=True)
    choices = fields.Text(string='Answers to pick from',
                          help='One per line.')
    who = fields.Selection(WHO_ANSWERS, string='Who answers', default='both',
                           required=True)
    required = fields.Boolean(string='Must be answered', default=True)

    @api.model_create_multi
    def create(self, vals_list):
        forms = self.env['pb.review.form'].browse(
            [vals.get('form_id') for vals in vals_list if vals.get('form_id')])
        forms._check_editable()
        return super().create(vals_list)

    def write(self, vals):
        self.form_id._check_editable()
        if 'form_id' in vals:
            self.env['pb.review.form'].browse(vals['form_id'])._check_editable()
        return super().write(vals)

    def unlink(self):
        self.form_id._check_editable()
        return super().unlink()

    def _choice_list(self):
        self.ensure_one()
        rows = [row.strip() for row in (self.choices or '').splitlines()]
        return [row for row in rows if row][:MAX_CHOICES]

    def _kind(self):
        """What answer this line takes: skills are always rated."""
        self.ensure_one()
        return 'rating' if self.section == 'skill' else (self.qtype
                                                          or 'rating')

    def _asks(self, author):
        """Whether `author` ('employee'/'manager') answers this line."""
        self.ensure_one()
        if self.section == 'skill':
            return True
        return self.who == 'both' or self.who == author
