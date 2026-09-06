# -*- coding: utf-8 -*-
"""A saved what-if.

Kept on the SERVER and not in one browser, because a plan a board is going to
look at is not a private note: the finance lead has to be able to open the same
one the owner saved, on their own laptop, next week.

The record holds three JSON blobs and one summary. `state` is the levers, and
it is the only thing the room needs to redraw the whole year — everything else
on screen is computed from it. `summary` is the headline numbers as the client
computed them at save time, stored so the comparison table can be drawn without
recomputing twelve months for every row.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

#: How many plans one company may keep. A dock that scrolls is a dock nobody
#: reads; twenty is more than any board has ever needed at once.
MAX_PLANS = 20


class PbDecisionPlan(models.Model):
    _name = 'pb.decision.plan'
    _inherit = ['mail.thread']
    _description = 'Decision Room saved plan'
    _order = 'is_reference desc, write_date desc, id desc'

    name = fields.Char(
        string="Plan name", required=True, tracking=True,
        help="What you would call this in a meeting.")
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, ondelete='cascade',
        default=lambda self: self.env.company, index=True)
    user_id = fields.Many2one(
        'res.users', string="Saved by", default=lambda self: self.env.user,
        ondelete='set null')

    state = fields.Json(
        string="The levers",
        help="Everything you moved: people per team, the raise, overtime, "
             "when the hires arrive, and the revenue target.")
    goals = fields.Json(
        string="The goals",
        help="What you said would make this a good plan.")
    summary = fields.Json(
        string="Headline numbers",
        help="Profit, cost, revenue, demand served, people and margin, as "
             "they stood when the plan was saved.")

    is_reference = fields.Boolean(
        string="Compare against this by default", tracking=True,
        help="One plan per company can be the one everything else is "
             "measured against.")
    note = fields.Text(string="Note")
    active = fields.Boolean(default=True)

    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    _name_uniq = models.Constraint(
        'unique(company_id, name)',
        "A plan with this name already exists.")

    # --------------------------------------------------------------- rails
    @api.constrains('summary', 'state', 'goals')
    def _check_payload(self):
        """The three blobs are objects or they are nothing.

        "Nothing" has three spellings here and all of them are legitimate:
        `None` for a field never written, `False` for one Odoo read back out of
        a NULL column, and `{}` for an empty plan. Only a value that is
        genuinely THERE and genuinely not an object is refused — a list or a
        number would sail through `fields.Json` and break the room on the next
        read, days later, with nothing to point at.
        """
        for plan in self:
            for value, label in ((plan.state, 'state'),
                                 (plan.goals, 'goals'),
                                 (plan.summary, 'summary')):
                if value and not isinstance(value, dict):
                    raise ValidationError(_(
                        "This plan could not be saved: its %s is not in the "
                        "shape the room writes.", label))

    def _drop_other_references(self):
        """At most one reference plan per company."""
        for plan in self.filtered('is_reference'):
            others = self.sudo().search([
                ('company_id', '=', plan.company_id.id),
                ('is_reference', '=', True),
                ('id', '!=', plan.id),
            ])
            if others:
                others.write({'is_reference': False})

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        plans._drop_other_references()
        return plans

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_reference'):
            self._drop_other_references()
        return res
