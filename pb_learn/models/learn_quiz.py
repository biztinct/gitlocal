# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LearnQuiz(models.Model):
    """An understanding check.

    Never a memory test: the brief's completion rule is demonstrated
    understanding, so every quiz is one judgement call with a wrong answer that
    is genuinely tempting. The explanation on a wrong option is written as
    recovery ("let's rethink that"), never as rejection.
    """
    _name = 'learn.quiz'
    _description = 'Learn understanding check'
    _order = 'sequence, id'

    lesson_id = fields.Many2one('learn.lesson', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    kind = fields.Selection(
        selection=lambda self: self._selection_kind(),
        required=True, default='choice')
    prompt = fields.Text(required=True, translate=True)
    option_ids = fields.One2many('learn.quiz.option', 'quiz_id')

    @api.model
    def _selection_kind(self):
        return [('choice', self.env._('Single choice'))]

    @api.constrains('option_ids')
    def _check_one_correct(self):
        for quiz in self:
            if quiz.kind == 'choice' and len(quiz.option_ids.filtered('is_correct')) != 1:
                raise ValidationError(
                    self.env._("A single-choice check needs exactly one correct option."))

    def _quiz_dict(self):
        self.ensure_one()
        return {
            'kind': self.kind,
            'prompt': self.prompt,
            'options': [o._option_dict() for o in self.option_ids],
        }


class LearnQuizOption(models.Model):
    _name = 'learn.quiz.option'
    _description = 'Learn understanding check option'
    _order = 'sequence, id'

    quiz_id = fields.Many2one('learn.quiz', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    label = fields.Text(required=True, translate=True)
    is_correct = fields.Boolean(default=False)
    feedback = fields.Text(required=True, translate=True,
                           help="Shown after the learner answers. On a wrong option "
                                "this is the recovery, not a rejection.")

    def _option_dict(self):
        self.ensure_one()
        return {
            'label': self.label,
            'correct': self.is_correct,
            'feedback': self.feedback,
        }
