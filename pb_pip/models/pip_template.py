# -*- coding: utf-8 -*-
"""A starting point, never a straitjacket.

A template carries the shape of a plan — how long it runs, how often the
check-ins land, what the coaching note starts out saying and which two or three
areas it is usually about. Everything it produces is COPIED onto the case, in
the same doctrine P0 set for journey steps: a plan is the person's own copy, so
editing a template never re-writes somebody's running plan under them.
"""

from odoo import api, fields, models, _

from .pip_common import CHECKIN_FREQS


class PbPipTemplate(models.Model):
    _name = 'pb.pip.template'
    _description = 'Improvement Plan Template'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    default_weeks = fields.Integer(
        string='How long it runs (weeks)', default=6,
        help='Long enough for somebody to actually change something, short '
             'enough that the answer is not a year away. Six weeks is the '
             'usual answer; four is the shortest that is fair.')
    checkin_freq = fields.Selection(
        CHECKIN_FREQS, string='Check in', default='weekly', required=True,
        help='How often the person and their manager sit down while the plan '
             'is running. Every one of these is put in the diary the moment '
             'the plan starts.')
    coaching_body_html = fields.Html(
        string='Coaching note — starting text', sanitize=True, translate=True,
        help='What HR opens the coaching conversation with. It is copied onto '
             'the case and edited there, so changing this never rewrites a '
             'conversation somebody is already having.')
    focus_line_ids = fields.One2many(
        'pb.pip.template.line', 'template_id', string='The usual areas',
        copy=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Improvement plan template')

    @api.constrains('default_weeks')
    def _check_weeks(self):
        for rec in self:
            if rec.default_weeks and not (1 <= rec.default_weeks <= 26):
                raise ValueError(_(
                    "A plan runs between one and twenty-six weeks. Anything "
                    "longer is not a plan, it is a performance review."))


class PbPipTemplateLine(models.Model):
    _name = 'pb.pip.template.line'
    _description = 'Improvement Plan Template — focus area'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'pb.pip.template', string='Template', required=True, index=True,
        ondelete='cascade')
    name = fields.Char(string='The area', required=True, translate=True)
    description = fields.Text(
        string='What good looks like', translate=True,
        help='Written as something a person could actually do, and somebody '
             'else could actually see.')
    sequence = fields.Integer(default=10)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Focus area')
