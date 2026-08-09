# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LearnLesson(models.Model):
    _name = 'learn.lesson'
    _description = 'Learn lesson'
    _order = 'sequence, id'

    key = fields.Char(required=True, index=True)
    station_id = fields.Many2one('learn.station', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    goal = fields.Text(translate=True)
    duration_min = fields.Integer(default=5)
    step_ids = fields.One2many('learn.step', 'lesson_id')
    quiz_ids = fields.One2many('learn.quiz', 'lesson_id')

    _sql_constraints = [
        ('key_uniq', 'unique(key)', 'A lesson key must be unique.'),
    ]

    def _lesson_dict(self):
        self.ensure_one()
        return {
            'key': self.key,
            'name': self.name,
            'goal': self.goal or '',
            'duration_min': self.duration_min,
            'steps': [s._step_dict() for s in self.step_ids],
            'quizzes': [q._quiz_dict() for q in self.quiz_ids],
        }


class LearnStep(models.Model):
    _name = 'learn.step'
    _description = 'Learn lesson step'
    _order = 'sequence, id'

    lesson_id = fields.Many2one('learn.lesson', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    kicker = fields.Char(translate=True, help="Small caps label above the title.")
    title = fields.Char(required=True, translate=True)
    body = fields.Text(required=True, translate=True,
                       help="Inline HTML is allowed: <b>, <i>, <br/>. No block markup.")
    tip = fields.Text(translate=True)
    consequence = fields.Text(
        translate=True,
        help="Shown as the 'Before you do this' card: scope, reversibility, "
             "what to verify first. Present only on steps that precede a risky action.")

    screen = fields.Char(required=True, help="Practice screen key this step renders.")
    anchor = fields.Char(help="Anchor key. Must exist in static/src/anchors.json.")

    visual = fields.Selection(
        selection=lambda self: self._selection_visual(),
        default='none', required=True)
    # The visual's non-prose parameters. Kept as flat scalars rather than a
    # JSON blob so that (a) they are greppable and (b) jsonb values do not
    # translate in this codebase, which would be a trap waiting for the day
    # someone puts a label in here.
    moment_from = fields.Char(help="trace: anchor key the line starts at.")
    moment_to = fields.Char(help="trace: anchor key the line ends at.")
    moment_chain = fields.Char(help="pipeline: which lifecycle chain to step through.")
    moment_which = fields.Char(help="morph: which before/after pair to toggle.")

    line_ids = fields.One2many('learn.step.line', 'step_id')

    @api.model
    def _selection_visual(self):
        return [
            ('none', self.env._('Spotlight only')),
            ('trace', self.env._('Traced line')),
            ('morph', self.env._('Before / after toggle')),
            ('calc', self.env._('Calculation breakdown')),
            ('pipeline', self.env._('Lifecycle stepper')),
            ('list', self.env._('Bullet list')),
        ]

    def _step_dict(self):
        self.ensure_one()
        return {
            'kicker': self.kicker or '',
            'title': self.title,
            'body': self.body,
            'tip': self.tip or '',
            'consequence': self.consequence or '',
            'screen': self.screen,
            'anchor': self.anchor or '',
            'visual': self.visual,
            'moment_from': self.moment_from or '',
            'moment_to': self.moment_to or '',
            'moment_chain': self.moment_chain or '',
            'moment_which': self.moment_which or '',
            'lines': [ln._line_dict() for ln in self.line_ids],
        }


class LearnStepLine(models.Model):
    """Rows a visual needs, when those rows belong to the lesson.

    Morph before/after captions, bullets and callouts share one table because
    they share one shape — a translatable label and a non-translatable value.
    The T / non-T split is the point: a translator can reword a caption but
    cannot turn +15 into +25.

    Deliberately NOT here: calc breakdowns and lifecycle stages. Those are
    product facts, the practice screens draw them from the fixture, and the
    contract checker guards them there. Copying them into a lesson row would
    give one fact two owners.
    """
    _name = 'learn.step.line'
    _description = 'Learn step line'
    _order = 'sequence, id'

    step_id = fields.Many2one('learn.step', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    role = fields.Selection(
        selection=lambda self: self._selection_role(),
        required=True, default='bullet')
    label = fields.Char(translate=True)
    value = fields.Char(help="Numbers, keys, anchor ids. NEVER translated.")
    note = fields.Text(translate=True)

    @api.model
    def _selection_role(self):
        return [
            ('morph_before', self.env._('Before')),
            ('morph_after', self.env._('After')),
            ('bullet', self.env._('Bullet')),
            ('warn', self.env._('Warning')),
            ('ok', self.env._('Confirmation')),
        ]

    def _line_dict(self):
        self.ensure_one()
        return {
            'role': self.role,
            'label': self.label or '',
            'value': self.value or '',
            'note': self.note or '',
        }
