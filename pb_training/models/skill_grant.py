# -*- coding: utf-8 -*-
"""LEARNING L5 — a course gives skills, and the SKILLS board.

`pb.training.skill.grant` says "finishing this course gives this skill at
this level" — on one of our courses or an outside one. Stock never grants a
skill from a course (ledger F7); this does, on the same crossing that files
the certificate (an assignment finished) and when an outside request is
taken or claimed back.

A SKILL IS NEVER EDITED IN PLACE (handover §5.4, F7). The stock skills
engine keeps one current row per skill and expects history: the new level
goes in through the employee's own `employee_skill_ids` create command, which
the engine itself turns into "close the old row (valid until yesterday) and
add the new one" (`hr.individual.skill.mixin._get_transformed_commands`).
Never a downgrade: a person already at or above the level keeps theirs.
"""

import logging

from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

from .training_common import leg

_logger = logging.getLogger(__name__)


class PbTrainingSkillGrant(models.Model):
    _name = 'pb.training.skill.grant'
    _description = 'Skill a course gives'
    _order = 'id'

    channel_id = fields.Many2one('slide.channel', string='Our course',
                                 index=True, ondelete='cascade')
    outside_course_id = fields.Many2one(
        'pb.training.outside.course', string='Outside course', index=True,
        ondelete='cascade')
    skill_id = fields.Many2one('hr.skill', string='Skill', required=True,
                               ondelete='cascade')
    skill_type_id = fields.Many2one(related='skill_id.skill_type_id',
                                    store=True, string='Skill type')
    skill_level_id = fields.Many2one(
        'hr.skill.level', string='Level', required=True, ondelete='cascade',
        domain="[('skill_type_id', '=', skill_type_id)]")
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.constrains('channel_id', 'outside_course_id')
    def _check_one_course(self):
        for rec in self:
            if bool(rec.channel_id) == bool(rec.outside_course_id):
                raise ValidationError(_(
                    "A skill is given by one course: one of ours or an "
                    "outside one."))

    @api.constrains('skill_id', 'skill_level_id')
    def _check_level(self):
        for rec in self:
            if rec.skill_level_id.skill_type_id != rec.skill_id.skill_type_id:
                raise ValidationError(_(
                    "That level belongs to another kind of skill."))

    def _words(self):
        self.ensure_one()
        return '%s · %s' % (self.skill_id.name or '',
                            self.skill_level_id.name or '')

    # =====================================================================
    #  giving them
    # =====================================================================
    @api.model
    def _grant(self, employee, grants):
        """Give `grants` to one employee. Returns the skills given."""
        emp = employee.sudo()
        if not emp or not grants:
            return []
        current = {s.skill_id.id: s for s in emp.current_employee_skill_ids}
        given, commands = [], []
        for grant in grants.sudo():
            have = current.get(grant.skill_id.id)
            if have and (have.level_progress or 0) >= (
                    grant.skill_level_id.level_progress or 0):
                continue
            commands.append(Command.create({
                'employee_id': emp.id,
                'skill_id': grant.skill_id.id,
                'skill_level_id': grant.skill_level_id.id,
                'skill_type_id': grant.skill_id.skill_type_id.id,
                'valid_from': fields.Date.today(),
            }))
            given.append(grant._words())
        if commands:
            emp.write({'employee_skill_ids': commands})
            leg(self.env, 'say on the record which skills a course gave',
                lambda: emp.message_post(
                    body=Markup('%s') % _("Skills from a finished course: "
                                          "%s.", ', '.join(given)),
                    subtype_xmlid='mail.mt_note'))
        return given


class PbTrainingAssignmentSkills(models.Model):
    _inherit = 'pb.training.assignment'

    def _refresh_one(self, today=None):
        was = self.state
        state = super()._refresh_one(today)
        if state == 'done' and was != 'done':
            grants = self.env['pb.training.skill.grant'].sudo().search(
                [('channel_id', '=', self.channel_id.id)])
            if grants:
                leg(self.env, 'give the skills the course gives',
                    lambda: self.env['pb.training.skill.grant']._grant(
                        self.employee_id, grants))
        return state


class PbTrainingRequestSkills(models.Model):
    _inherit = 'pb.training.request'

    def _after_taken(self):
        res = super()._after_taken()
        if self.kind == 'outside' and self.outside_course_id:
            grants = self.env['pb.training.skill.grant'].sudo().search(
                [('outside_course_id', '=', self.outside_course_id.id)])
            if grants:
                self.env['pb.training.skill.grant']._grant(
                    self.employee_id, grants)
        return res


class SlideChannelSkills(models.Model):
    _inherit = 'slide.channel'

    pb_skill_grant_ids = fields.One2many(
        'pb.training.skill.grant', 'channel_id', string='Skills it gives')


class OutsideCourseSkills(models.Model):
    _inherit = 'pb.training.outside.course'

    skill_grant_ids = fields.One2many(
        'pb.training.skill.grant', 'outside_course_id',
        string='Skills it gives')
