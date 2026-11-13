# -*- coding: utf-8 -*-
"""One thing that has to change, and how anybody will know it did.

THE METRIC IS NOT OPTIONAL DECORATION. An improvement plan whose objectives are
"communicate better" and "be more proactive" is a plan that cannot be passed or
failed on evidence, only on somebody's mood — which is the failure mode this
whole model exists to make harder. So the case refuses to start a plan whose
objectives have no `metric` on them, in words, naming the objective.
"""

from odoo import api, fields, models, _

from .pip_common import OBJECTIVE_STATES, OBJECTIVE_STATE_LABEL


class PbPipObjective(models.Model):
    _name = 'pb.pip.objective'
    _description = 'Growth Plan Objective'
    _order = 'sequence, id'

    case_id = fields.Many2one(
        'pb.pip.case', string='Plan', required=True, index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', related='case_id.employee_id',
        store=True, readonly=True, index=True)
    name = fields.Char(string='What has to change', required=True)
    metric = fields.Char(
        string='What good looks like',
        help='In a sentence somebody else could check. "Every ticket picked '
             'up within a working day" — not "better responsiveness".')
    target = fields.Char(
        string='The number, if there is one',
        help='Leave it empty when there honestly is not one. A made-up target '
             'is worse than none.')
    weight = fields.Integer(
        string='Weight', default=1,
        help='Used only to say which of these matters most when they do not '
             'all land the same way.')
    status = fields.Selection(
        OBJECTIVE_STATES, string='Where it stands', default='on_track',
        required=True, index=True)
    notes = fields.Text(string='Notes')
    sequence = fields.Integer(default=10)
    # A REAL COLUMN, related and stored, so the company record rule on this
    # model is a plain indexed test rather than a join through the case on
    # every read (R9's cousin: a stored related is a column and has to be
    # re-pointed explicitly if a parent ever moves).
    company_id = fields.Many2one(
        'res.company', string='Company', related='case_id.company_id',
        store=True, readonly=True, index=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Objective')

    @api.constrains('weight')
    def _check_weight(self):
        for rec in self:
            if rec.weight and rec.weight < 1:
                raise ValueError(_("A weight is one or more."))

    def status_label(self):
        self.ensure_one()
        return OBJECTIVE_STATE_LABEL.get(self.status, self.status or '')

    def action_set_status(self, status):
        """Change where one objective stands, and say so on the plan.

        Posted rather than written quietly: "at risk" appearing on somebody's
        plan three weeks in is the moment a conversation should happen, and a
        silent field change is a conversation nobody has.
        """
        if status not in OBJECTIVE_STATE_LABEL:
            raise ValueError(_("That is not one of the four."))
        for rec in self:
            was = rec.status
            if was == status:
                continue
            rec.status = status
            if rec.case_id:
                rec.case_id.message_post(body=_(
                    "%(what)s moved from %(was)s to %(now)s.",
                    what=rec.name or _('An objective'),
                    was=OBJECTIVE_STATE_LABEL.get(was, was or ''),
                    now=OBJECTIVE_STATE_LABEL.get(status, status)))
        return True
