# -*- coding: utf-8 -*-
"""The reusable checklist behind every journey."""

import logging

from odoo import api, fields, models, _

from .lifecycle_common import (
    ANCHORS, ASSIGNEE_RULES, CASE_TYPES, STEP_KINDS,
)

_logger = logging.getLogger(__name__)


class PbJourneyTemplate(models.Model):
    _name = 'pb.journey.template'
    _description = 'Journey Template'
    _order = 'sequence, name, id'

    name = fields.Char(string='Name', required=True, translate=True)
    case_type = fields.Selection(
        CASE_TYPES, string='Journey type', required=True, default='onboarding',
        help='What kind of employee event this checklist is for.')
    country_id = fields.Many2one(
        'res.country', string='Country',
        help='Leave empty to use this checklist everywhere. Set a country and '
             'it is only offered for people working there.')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    step_ids = fields.One2many(
        'pb.journey.template.step', 'template_id', string='Steps', copy=True)
    step_count = fields.Integer(compute='_compute_step_count', string='Steps')
    note = fields.Text(string='Notes')

    # A WARNING, not a constraint. Two checklists for the same event in the same
    # country is a normal thing to have for a week while one replaces the other;
    # blocking it would only teach people to deactivate the wrong one in a hurry.
    overlap_warning = fields.Char(
        compute='_compute_overlap_warning', string='Heads up')

    @api.depends('step_ids')
    def _compute_step_count(self):
        for rec in self:
            rec.step_count = len(rec.step_ids)

    @api.depends('case_type', 'country_id', 'company_id', 'active')
    def _compute_overlap_warning(self):
        for rec in self:
            rec.overlap_warning = False
            if not rec.active or not rec.case_type:
                continue
            domain = [('case_type', '=', rec.case_type),
                      ('country_id', '=', rec.country_id.id)]
            if isinstance(rec.id, int):
                domain.append(('id', '!=', rec.id))
            twin = self.search(domain, limit=1)
            if twin:
                rec.overlap_warning = _(
                    "'%(other)s' already covers this journey type and country. "
                    "The newest one is used when a journey is started.",
                    other=twin.name)

    @api.model
    def pick_for(self, case_type, country_id=False, company_id=False):
        """The checklist a new journey of this kind should use.

        Most specific first: the country's own, then the one with no country.
        A company's own beats a shared one. Nothing found is not an error — a
        journey with no template is an empty checklist somebody fills by hand.
        """
        base = [('case_type', '=', case_type), ('active', '=', True)]
        if company_id:
            base.append(('company_id', 'in', [False, company_id]))
        for extra in ([('country_id', '=', country_id)] if country_id else [],
                      [('country_id', '=', False)]):
            found = self.search(base + extra, order='sequence, id', limit=1)
            if found:
                return found
        return self.browse()


class PbJourneyTemplateStep(models.Model):
    _name = 'pb.journey.template.step'
    _description = 'Journey Template Step'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'pb.journey.template', string='Checklist', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Step', required=True, translate=True)
    description = fields.Text(string='What to do')
    anchor = fields.Selection(
        ANCHORS, string='Counts from', required=True, default='case_open')
    offset_days = fields.Integer(
        string='Days', default=0,
        help='Days before (negative) or after (positive) the date it counts '
             'from. 0 means on the day itself.')
    assignee_rule = fields.Selection(
        ASSIGNEE_RULES, string='Owner', required=True, default='hr')
    assignee_user_id = fields.Many2one(
        'res.users', string='Person',
        help='Only used when the owner is a specific person.')
    step_kind = fields.Selection(
        STEP_KINDS, string='Kind', required=True, default='task')
    blocking_ff = fields.Boolean(
        string='Blocks final settlement',
        help='The final settlement cannot be paid until this step is done.')
    escalation_days = fields.Integer(
        string='Escalate after (days)', default=3,
        help='How many days a step may stay overdue before the lifecycle '
             'managers are told.')
    mail_template_id = fields.Many2one(
        'mail.template', string='Email to send',
        help='Used when the kind is an automatic email.')
    letter_template_id = fields.Many2one(
        'pb.letter.template', string='Letter',
        help='Used when the kind is a letter.')
    form_questions_json = fields.Text(
        string='Questions',
        help='The questions to ask, as a list of '
             '{"key", "label", "type", "options"} entries. Used when the kind '
             'is a form.')
    company_id = fields.Many2one(
        related='template_id.company_id', store=True, index=True)

    @api.onchange('assignee_rule')
    def _onchange_assignee_rule(self):
        if self.assignee_rule != 'user':
            self.assignee_user_id = False
